import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/auth";
import { api, apiErrorMessage } from "@/lib/api";
import type { Capabilities, Order, PrintSpecification } from "@/lib/types";
import SpecFields, { DEFAULT_SPEC } from "@/components/SpecFields";

export default function NewOrderPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [spec, setSpec] = useState<PrintSpecification>(DEFAULT_SPEC);
  const [guestName, setGuestName] = useState("");
  const [guestMethod, setGuestMethod] = useState<"email" | "phone" | "facebook">("email");
  const [guestValue, setGuestValue] = useState("");

  const capabilitiesQuery = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => {
      const { data } = await api.get<Capabilities>("/printing/capabilities/");
      return data;
    },
  });

  const submitMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      formData.append("spec", JSON.stringify(spec));
      if (!user) {
        formData.append("guest_name", guestName);
        formData.append("guest_contact_method", guestMethod);
        formData.append("guest_contact_value", guestValue);
      }
      const { data } = await api.post<Order>("/orders/", formData);
      return data;
    },
    onSuccess: (order) => {
      toast.success(`Order ${order.tracking_id} created!`);
      navigate(`/orders/${order.id}`);
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
    if (!user && (!guestName || !guestValue)) {
      toast.error("Please provide your name and contact details.");
      return;
    }
    submitMutation.mutate();
  }

  const capabilities = capabilitiesQuery.data ?? null;

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">New Print Order</h1>
        <p className="text-muted-foreground">
          Upload your files and choose printing options. A real person reviews every job before it prints.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Files</CardTitle>
          <CardDescription>Upload PDFs or images (JPG/PNG).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label
            htmlFor="file-upload"
            className="flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-6 text-center hover:border-primary/50"
          >
            <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
            <span className="text-sm font-medium">Click to upload or drag files here</span>
            <span className="text-xs text-muted-foreground">PDF, JPG, PNG</span>
            <input
              id="file-upload"
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={onFileChange}
              className="hidden"
            />
          </label>
          {files.length > 0 && (
            <ul className="space-y-2">
              {files.map((f, idx) => (
                <li key={idx} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm">
                  <span className="truncate">{f.name} <span className="text-muted-foreground">({(f.size / 1024).toFixed(0)} KB)</span></span>
                  <button type="button" onClick={() => removeFile(idx)} className="text-destructive hover:text-destructive/80">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
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
            <SpecFields capabilities={capabilities} value={spec} onChange={setSpec} />
          )}
        </CardContent>
      </Card>

      {!user && (
        <Card>
          <CardHeader>
            <CardTitle>Your details</CardTitle>
            <CardDescription>So we can send you updates about your order.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="guest-name">Name</Label>
              <Input id="guest-name" value={guestName} onChange={(e) => setGuestName(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>Contact method</Label>
              <RadioGroup value={guestMethod} onValueChange={(v) => setGuestMethod(v as "email" | "phone" | "facebook")} className="flex gap-2">
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
                {guestMethod === "email" ? "Email address" : guestMethod === "phone" ? "Phone number" : "Facebook name"}
              </Label>
              <Input id="guest-value" type={guestMethod === "email" ? "email" : "text"} value={guestValue} onChange={(e) => setGuestValue(e.target.value)} required />
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      <div className="flex justify-end gap-3">
        <Button type="button" variant="outline" onClick={() => navigate("/")}>Cancel</Button>
        <Button type="submit" disabled={submitMutation.isPending}>
          {submitMutation.isPending ? "Submitting…" : "Place Order"}
        </Button>
      </div>
    </form>
  );
}

