import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Check, Eye, Search, Trash2, Upload, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/auth";
import { api, apiErrorMessage, saveGuestOrder } from "@/lib/api";
import { formatBytes } from "@/lib/constants";
import type { Capabilities, CustomerOption, Order, PrintSpecification, Quote } from "@/lib/types";
import SpecFields, { DEFAULT_SPEC } from "@/components/SpecFields";

export type GuestMethod = "email" | "phone" | "facebook";

/** Mirrors PREVIEWABLE_EXTENSIONS in backend/apps/orders/models.py. */
const ACCEPTED_TYPES =
  ".pdf,.jpg,.jpeg,.png,.webp,.docx,.xlsx,.pptx,.txt,.md,.csv";
/** Extensions the printer accepts directly, so only these get a local preview. */
const PRINTABLE_TYPES = ["pdf", "jpg", "jpeg", "png", "webp"];

interface GuestDetailsProps {
  name: string;
  method: GuestMethod;
  value: string;
  onName: (v: string) => void;
  onMethod: (v: GuestMethod) => void;
  onValue: (v: string) => void;
  title?: string;
  description?: string;
}

/** Shared "who is this order for" card — guests filling their own details and
 * admins entering a walk-in customer's details use the same UI.
 * Exported for the /q quick-print wizard. */
export function GuestDetailsCard({
  name, method, value, onName, onMethod, onValue,
  title = "Your details",
  description = "So we can send you updates about your order.",
}: GuestDetailsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="guest-name">Name</Label>
          <Input id="guest-name" value={name} onChange={(e) => onName(e.target.value)} required />
        </div>
        <div className="space-y-1.5">
          <Label>Contact method</Label>
          <RadioGroup value={method} onValueChange={(v) => onMethod(v as GuestMethod)} className="flex gap-2">
            <div className="flex items-center space-x-2 rounded-md border p-2.5">
              <RadioGroupItem value="email" id="gm-email" />
              <Label htmlFor="gm-email" className="cursor-pointer font-normal">Email</Label>
            </div>
            <div className="flex items-center space-x-2 rounded-md border p-2.5">
              <RadioGroupItem value="phone" id="gm-phone" />
              <Label htmlFor="gm-phone" className="cursor-pointer font-normal">Phone</Label>
            </div>
            <div className="flex items-center space-x-2 rounded-md border p-2.5">
              <RadioGroupItem value="facebook" id="gm-fb" />
              <Label htmlFor="gm-fb" className="cursor-pointer font-normal">Facebook</Label>
            </div>
          </RadioGroup>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="guest-value">
            {method === "email" ? "Email address" : method === "phone" ? "Phone number" : "Facebook name"}
          </Label>
          <Input
            id="guest-value"
            type={method === "email" ? "email" : "text"}
            value={value}
            onChange={(e) => onValue(e.target.value)}
            required
          />
        </div>
      </CardContent>
    </Card>
  );
}

export default function NewOrderPage({ adminMode = false }: { adminMode?: boolean }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  /** Orientation only affects picture files, so the control follows the uploads. */
  const hasImages = files.some((file) => /\.(jpe?g|png|webp)$/i.test(file.name));
  const [localPreview, setLocalPreview] = useState<{ file: File; url: string } | null>(null);
  const [spec, setSpec] = useState<PrintSpecification>(DEFAULT_SPEC);
  const [guestName, setGuestName] = useState("");
  const [guestMethod, setGuestMethod] = useState<GuestMethod>("email");
  const [guestValue, setGuestValue] = useState("");
  // Admin "order on behalf of a customer" helpers
  const [customerSearch, setCustomerSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerOption | null>(null);

  const capabilitiesQuery = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => {
      const { data } = await api.get<Capabilities>("/printing/capabilities/");
      return data;
    },
  });

  const customersQuery = useQuery({
    queryKey: ["admin-customers", customerSearch],
    queryFn: async () => {
      const { data } = await api.get<CustomerOption[]>("/admin/customers/", {
        params: { search: customerSearch.trim() },
      });
      return data;
    },
    enabled: adminMode && customerSearch.trim().length >= 1 && !selectedCustomer,
  });

  const submitMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      formData.append("spec", JSON.stringify(spec));
      if (adminMode) {
        if (selectedCustomer) {
          formData.append("customer_user_id", String(selectedCustomer.id));
        } else {
          formData.append("guest_name", guestName);
          formData.append("guest_contact_method", guestMethod);
          formData.append("guest_contact_value", guestValue);
        }
      } else if (!user) {
        formData.append("guest_name", guestName);
        formData.append("guest_contact_method", guestMethod);
        formData.append("guest_contact_value", guestValue);
      }
      // The API answers { order, quote } — never treat the envelope as the order.
      const { data } = await api.post<{ order: Order; quote: Quote }>("/orders/", formData);
      return data.order;
    },
    onSuccess: (order) => {
      if (adminMode) {
        toast.success(`Order ${order.tracking_id} created for ${order.client_name}.`);
        navigate(`/admin/orders/${order.id}`);
        return;
      }
      if (!user) {
        saveGuestOrder({ id: order.id, tracking_id: order.tracking_id, created_at: order.created_at });
      }
      toast.success(`Order ${order.tracking_id} created!`);
      navigate(`/orders/${order.id}`, { state: { justCreated: true, trackingId: order.tracking_id } });
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err));
    },
  });

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    setFiles((prev) => [...prev, ...selected]);
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) {
      toast.error("Please upload at least one file.");
      return;
    }
    if (adminMode) {
      if (!selectedCustomer && (!guestName.trim() || !guestValue.trim())) {
        toast.error("Select a registered customer, or enter the customer's name and contact details.");
        return;
      }
    } else if (!user && (!guestName.trim() || !guestValue.trim())) {
      toast.error("Please provide your name and contact details.");
      return;
    }
    submitMutation.mutate();
  }

  const capabilities = capabilitiesQuery.data ?? null;
  const showGuestCard = adminMode ? !selectedCustomer : !user;

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {adminMode ? "New order for a customer" : "New Print Order"}
        </h1>
        <p className="text-muted-foreground">
          {adminMode
            ? "Create an order on behalf of a customer. It will appear in Admin → Orders like any other order."
            : "Upload your files and choose printing options. A real person reviews every job before it prints."}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Files</CardTitle>
          <CardDescription>
            Upload PDFs, images (JPG/PNG/WEBP) or documents (Word, Excel,
            PowerPoint, TXT). You can preview everything before ordering.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label
            htmlFor="file-upload"
            className="flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-6 text-center hover:border-primary/50"
          >
            <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
            <span className="text-sm font-medium">Click to upload or drag files here</span>
            <span className="text-xs text-muted-foreground">
              PDF · JPG · PNG · WEBP · DOCX · XLSX · PPTX · TXT · CSV
            </span>
            <input
              id="file-upload"
              type="file"
              multiple
              accept={ACCEPTED_TYPES}
              onChange={onFileChange}
              className="hidden"
            />
          </label>
          {files.length > 0 && (
            <ul className="space-y-2">
              {files.map((f, idx) => {
                const extension = f.name.split(".").pop()?.toLowerCase() ?? "";
                const printReady = PRINTABLE_TYPES.includes(extension);
                return (
                  <li key={idx}
                    className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2 text-sm">
                    <div className="min-w-0">
                      <span className="truncate">{f.name}{" "}
                        <span className="text-muted-foreground">({formatBytes(f.size)})</span>
                      </span>
                      {!printReady && (
                        <p className="text-[11px] text-amber-700">
                          We&apos;ll read this for you, then print it as PDF.
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {printReady && (
                        <Button type="button" variant="ghost" size="sm"
                          onClick={() => setLocalPreview({ file: f, url: URL.createObjectURL(f) })}>
                          <Eye className="mr-1 h-4 w-4" /> Preview
                        </Button>
                      )}
                      <button type="button" onClick={() => removeFile(idx)}
                        className="text-destructive hover:text-destructive/80"
                        aria-label={`Remove ${f.name}`}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Print options</CardTitle>
          <CardDescription>Choose how you want your files printed.</CardDescription>
        </CardHeader>
        <CardContent>
          {capabilitiesQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : (
            <SpecFields capabilities={capabilities} value={spec} onChange={setSpec}
              showOrientation={hasImages} />
          )}
        </CardContent>
      </Card>

      {adminMode && (
        <Card>
          <CardHeader>
            <CardTitle>Customer</CardTitle>
            <CardDescription>
              Link this order to a registered customer's account (the guest details below are then
              skipped), or leave it empty and enter walk-in details instead.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {selectedCustomer ? (
              <div className="flex items-center justify-between rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm">
                <span className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-600" />
                  <span className="font-medium">
                    {selectedCustomer.first_name || selectedCustomer.last_name
                      ? `${selectedCustomer.first_name} ${selectedCustomer.last_name}`.trim()
                      : selectedCustomer.email}
                  </span>
                  <span className="text-muted-foreground">{selectedCustomer.email}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedCustomer(null)}
                  className="text-muted-foreground hover:text-foreground"
                  aria-label="Clear selected customer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search customers by name, email or phone…"
                    value={customerSearch}
                    onChange={(e) => setCustomerSearch(e.target.value)}
                    className="pl-9"
                  />
                </div>
                {customersQuery.isLoading && <Skeleton className="h-10 w-full" />}
                {customersQuery.data && customersQuery.data.length > 0 && (
                  <ul className="max-h-52 overflow-auto rounded-md border">
                    {customersQuery.data.map((c) => (
                      <li key={c.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedCustomer(c);
                            setCustomerSearch("");
                          }}
                          className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                        >
                          <span className="truncate">
                            <span className="font-medium">
                              {c.first_name || c.last_name ? `${c.first_name} ${c.last_name}`.trim() : c.email}
                            </span>
                            <span className="ml-2 text-muted-foreground">{c.email}</span>
                          </span>
                          {c.phone && <span className="ml-2 shrink-0 text-muted-foreground">{c.phone}</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {customersQuery.data && customersQuery.data.length === 0 && customerSearch.trim() && (
                  <p className="text-sm text-muted-foreground">
                    No registered customers match "{customerSearch.trim()}".
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {showGuestCard && (
        <GuestDetailsCard
          name={guestName}
          method={guestMethod}
          value={guestValue}
          onName={setGuestName}
          onMethod={setGuestMethod}
          onValue={setGuestValue}
          title={adminMode ? "Walk-in customer details" : "Your details"}
          description={
            adminMode
              ? "Enter the customer's details so they can track this order. Required unless you selected an account above."
              : "So we can send you updates about your order."
          }
        />
      )}

      <Separator />

      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={() => navigate(adminMode ? "/admin" : "/")}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitMutation.isPending}>
          {submitMutation.isPending ? "Submitting…" : adminMode ? "Create Order" : "Place Order"}
        </Button>
      </div>
    <Dialog open={!!localPreview} onOpenChange={(next) => {
        if (!next && localPreview) URL.revokeObjectURL(localPreview.url);
        setLocalPreview(null);
      }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="truncate text-base">{localPreview?.file.name}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-auto rounded-md bg-muted/40">
            {localPreview?.file.name.toLowerCase().endsWith(".pdf") ? (
              <iframe src={localPreview.url} title={localPreview.file.name}
                className="h-[70vh] w-full" />
            ) : localPreview ? (
              <div className="flex justify-center p-4">
                <img src={localPreview.url} alt={localPreview.file.name}
                  className="max-h-[65vh] object-contain" />
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </form>
  );
}

