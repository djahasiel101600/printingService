import { useEffect, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent, ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Check,
  Eye,
  FileImage,
  FileText,
  Loader2,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/components/auth";
import { api, apiErrorMessage, saveGuestOrder } from "@/lib/api";
import { formatBytes } from "@/lib/constants";
import type {
  Capabilities,
  CustomerOption,
  Order,
  PrintSpecification,
  Quote,
} from "@/lib/types";
import SpecFields, { DEFAULT_SPEC } from "@/components/SpecFields";
import { cn } from "@/lib/utils";

export type GuestMethod = "email" | "phone" | "facebook";

/** Mirrors PREVIEWABLE_EXTENSIONS in backend/apps/orders/models.py. */
const ACCEPTED_TYPES =
  ".pdf,.jpg,.jpeg,.png,.webp,.docx,.xlsx,.pptx,.txt,.md,.csv";
/** Same list without the dots, so dropped files can be checked the way the picker checks them. */
const ACCEPTED_EXTENSIONS = ACCEPTED_TYPES.split(",").map((t) => t.slice(1));
/** Extensions the printer accepts directly, so only these get a local preview. */
const PRINTABLE_TYPES = ["pdf", "jpg", "jpeg", "png", "webp"];
const IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"];

const CONTACT_METHODS: { value: GuestMethod; label: string; id: string }[] = [
  { value: "email", label: "Email", id: "gm-email" },
  { value: "phone", label: "Phone", id: "gm-phone" },
  { value: "facebook", label: "Facebook", id: "gm-fb" },
];

const CONTACT_FIELD: Record<
  GuestMethod,
  { label: string; placeholder: string }
> = {
  email: { label: "Email address", placeholder: "name@example.com" },
  phone: { label: "Phone number", placeholder: "Mobile number" },
  facebook: {
    label: "Facebook name",
    placeholder: "Name on your Facebook profile",
  },
};

const extensionOf = (name: string) =>
  name.split(".").pop()?.toLowerCase() ?? "";
/** Two picks of the same file are the same file, whatever the order they arrive in. */
const fileKey = (f: File) => `${f.name}:${f.size}:${f.lastModified}`;
const customerName = (c: CustomerOption) =>
  c.first_name || c.last_name
    ? `${c.first_name} ${c.last_name}`.trim()
    : c.email;

/** Waits for typing to pause so the customer search doesn't fire on every keystroke. */
function useDebounced<T>(value: T, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Numbered card titles, since the page really is a sequence of steps. */
function StepTitle({ step, children }: { step?: number; children: ReactNode }) {
  return (
    <CardTitle className="flex items-center gap-2.5">
      {step !== undefined && (
        <span
          aria-hidden="true"
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
        >
          {step}
        </span>
      )}
      {children}
    </CardTitle>
  );
}

interface FormErrors {
  files?: string;
  name?: string;
  value?: string;
}

interface GuestDetailsProps {
  name: string;
  method: GuestMethod;
  value: string;
  onName: (v: string) => void;
  onMethod: (v: GuestMethod) => void;
  onValue: (v: string) => void;
  title?: string;
  description?: string;
  /** Optional, so existing callers (the /q wizard) keep working unchanged. */
  step?: number;
  errors?: { name?: string; value?: string };
}

/** Shared "who is this order for" card — guests filling their own details and
 * admins entering a walk-in customer's details use the same UI.
 * Exported for the /q quick-print wizard. */
export function GuestDetailsCard({
  name,
  method,
  value,
  onName,
  onMethod,
  onValue,
  title = "Your details",
  description = "So we can send you updates about your order.",
  step,
  errors,
}: GuestDetailsProps) {
  const field = CONTACT_FIELD[method];
  return (
    <Card>
      <CardHeader>
        <StepTitle step={step}>{title}</StepTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="guest-name">Name</Label>
          <Input
            id="guest-name"
            value={name}
            onChange={(e) => onName(e.target.value)}
            autoComplete="name"
            required
            aria-invalid={!!errors?.name}
            aria-describedby={errors?.name ? "guest-name-error" : undefined}
            className={cn(
              errors?.name &&
                "border-destructive focus-visible:ring-destructive",
            )}
          />
          {errors?.name && (
            <p id="guest-name-error" className="text-sm text-destructive">
              {errors.name}
            </p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label id="guest-method-label">How should we contact you?</Label>
          <RadioGroup
            value={method}
            onValueChange={(v) => onMethod(v as GuestMethod)}
            aria-labelledby="guest-method-label"
            className="flex flex-wrap gap-2"
          >
            {CONTACT_METHODS.map((m) => (
              // The whole box is the label, so the tap target is the box, not the 16px radio.
              <Label
                key={m.value}
                htmlFor={m.id}
                className={cn(
                  "flex min-w-[7rem] flex-1 cursor-pointer items-center gap-2 rounded-md border p-2.5 font-normal transition-colors",
                  method === m.value
                    ? "border-primary bg-primary/5 font-medium"
                    : "hover:bg-accent/50",
                )}
              >
                <RadioGroupItem value={m.value} id={m.id} />
                {m.label}
              </Label>
            ))}
          </RadioGroup>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="guest-value">{field.label}</Label>
          <Input
            id="guest-value"
            type={
              method === "email" ? "email" : method === "phone" ? "tel" : "text"
            }
            autoComplete={
              method === "email" ? "email" : method === "phone" ? "tel" : "off"
            }
            placeholder={field.placeholder}
            value={value}
            onChange={(e) => onValue(e.target.value)}
            required
            aria-invalid={!!errors?.value}
            aria-describedby={errors?.value ? "guest-value-error" : undefined}
            className={cn(
              errors?.value &&
                "border-destructive focus-visible:ring-destructive",
            )}
          />
          {errors?.value && (
            <p id="guest-value-error" className="text-sm text-destructive">
              {errors.value}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function NewOrderPage({
  adminMode = false,
}: {
  adminMode?: boolean;
}) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  /** Orientation only affects picture files, so the control follows the uploads. */
  const hasImages = files.some((file) =>
    /\.(jpe?g|png|webp)$/i.test(file.name),
  );
  const [localPreview, setLocalPreview] = useState<{
    file: File;
    url: string;
  } | null>(null);
  const [spec, setSpec] = useState<PrintSpecification>(DEFAULT_SPEC);
  const [guestName, setGuestName] = useState("");
  const [guestMethod, setGuestMethod] = useState<GuestMethod>("email");
  const [guestValue, setGuestValue] = useState("");
  // Admin "order on behalf of a customer" helpers
  const [customerSearch, setCustomerSearch] = useState("");
  const debouncedSearch = useDebounced(customerSearch);
  const [selectedCustomer, setSelectedCustomer] =
    useState<CustomerOption | null>(null);
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [uploadPct, setUploadPct] = useState<number | null>(null);

  const capabilitiesQuery = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => {
      const { data } = await api.get<Capabilities>("/printing/capabilities/");
      return data;
    },
  });

  const customersQuery = useQuery({
    queryKey: ["admin-customers", debouncedSearch],
    queryFn: async () => {
      const { data } = await api.get<CustomerOption[]>("/admin/customers/", {
        params: { search: debouncedSearch.trim() },
      });
      return data;
    },
    enabled:
      adminMode && debouncedSearch.trim().length >= 1 && !selectedCustomer,
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
      const { data } = await api.post<{ order: Order; quote: Quote }>(
        "/orders/",
        formData,
        {
          // Large PDFs can take a while; show that something is happening.
          onUploadProgress: (e) =>
            setUploadPct(
              e.total ? Math.round((e.loaded / e.total) * 100) : null,
            ),
        },
      );
      return data.order;
    },
    onSuccess: (order) => {
      if (adminMode) {
        toast.success(
          `Order ${order.tracking_id} created for ${order.client_name}.`,
        );
        navigate(`/admin/orders/${order.id}`);
        return;
      }
      if (!user) {
        saveGuestOrder({
          id: order.id,
          tracking_id: order.tracking_id,
          created_at: order.created_at,
        });
      }
      toast.success(`Order ${order.tracking_id} created!`);
      navigate(`/orders/${order.id}`, {
        state: { justCreated: true, trackingId: order.tracking_id },
      });
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err));
    },
    onSettled: () => setUploadPct(null),
  });

  // Object URLs hold the whole file in memory until revoked. Revoke when the
  // preview changes, closes, or the page unmounts.
  useEffect(() => {
    return () => {
      if (localPreview) URL.revokeObjectURL(localPreview.url);
    };
  }, [localPreview]);

  // Losing a list of chosen files to a stray refresh is the worst moment on this page.
  useEffect(() => {
    if (files.length === 0 || submitMutation.isPending) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [files.length, submitMutation.isPending]);

  /** Shared by the file picker and drag-and-drop, so both enforce the same rules. */
  function addFiles(incoming: File[]) {
    if (incoming.length === 0) return;
    const known = new Set(files.map(fileKey));
    const accepted: File[] = [];
    const rejected: string[] = [];
    let duplicates = 0;
    for (const f of incoming) {
      if (!ACCEPTED_EXTENSIONS.includes(extensionOf(f.name))) {
        rejected.push(f.name);
      } else if (known.has(fileKey(f))) {
        duplicates += 1;
      } else {
        known.add(fileKey(f));
        accepted.push(f);
      }
    }
    if (accepted.length > 0) {
      setFiles((prev) => [...prev, ...accepted]);
      setErrors((prev) => ({ ...prev, files: undefined }));
    }
    if (rejected.length > 0) {
      toast.error(
        `${rejected.length === 1 ? rejected[0] : `${rejected.length} files`} can't be printed. ` +
          "Accepted: PDF, JPG, PNG, WEBP, DOCX, XLSX, PPTX, TXT, MD, CSV.",
      );
    }
    if (duplicates > 0) {
      toast.info(
        duplicates === 1
          ? "That file is already in your list."
          : `${duplicates} files were already in your list.`,
      );
    }
  }

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(e.target.files ?? []));
    // Clear the input so picking the same file again after removing it still fires.
    e.target.value = "";
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  const needsGuestDetails = adminMode ? !selectedCustomer : !user;

  function validate(): FormErrors {
    const next: FormErrors = {};
    if (files.length === 0) next.files = "Add at least one file to print.";
    if (needsGuestDetails) {
      if (!guestName.trim()) {
        next.name = adminMode
          ? "Enter the customer's name."
          : "Enter your name.";
      }
      const value = guestValue.trim();
      if (!value) {
        next.value = `Enter ${adminMode ? "the customer's" : "your"} ${CONTACT_FIELD[guestMethod].label.toLowerCase()}.`;
      } else if (guestMethod === "email" && !/^\S+@\S+\.\S+$/.test(value)) {
        next.value = "Enter a valid email address.";
      }
    }
    return next;
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next = validate();
    setErrors(next);
    if (Object.keys(next).length > 0) {
      toast.error(
        adminMode && !selectedCustomer && (next.name || next.value)
          ? "Select a registered customer, or enter the customer's name and contact details."
          : "Please fix the highlighted fields.",
      );
      // Move focus to the first problem so keyboard and screen-reader users land on it.
      const firstId = next.files
        ? "file-upload"
        : next.name
          ? "guest-name"
          : "guest-value";
      document.getElementById(firstId)?.focus();
      return;
    }
    submitMutation.mutate();
  }

  const capabilities = capabilitiesQuery.data ?? null;
  const showGuestCard = needsGuestDetails;
  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  const isSubmitting = submitMutation.isPending;

  // Step numbers follow what is actually on screen.
  const customerStep = 3;
  const guestStep = adminMode ? 4 : 3;

  // What's still missing, shown beside the submit button so it never feels like a surprise.
  const missing: string[] = [];
  if (files.length === 0) missing.push("at least one file");
  if (needsGuestDetails && (!guestName.trim() || !guestValue.trim()))
    missing.push("contact details");

  const forWhom = adminMode
    ? selectedCustomer
      ? customerName(selectedCustomer)
      : guestName.trim() || "Not set yet"
    : user
      ? user.first_name || user.email
      : guestName.trim() || "Not set yet";

  return (
    <>
      <form onSubmit={onSubmit} noValidate className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">
            {adminMode ? "New order for a customer" : "New print order"}
          </h1>
          <p className="max-w-2xl text-muted-foreground">
            {adminMode
              ? "Create an order on behalf of a customer. It will appear in Admin → Orders like any other order."
              : "Upload your files and choose printing options. A real person reviews every job before it prints."}
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <StepTitle step={1}>Files</StepTitle>
                <CardDescription>
                  Upload PDFs, images (JPG/PNG/WEBP) or documents (Word, Excel,
                  PowerPoint, TXT). You can preview PDFs and images before
                  ordering.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <label
                  htmlFor="file-upload"
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={(e) => {
                    // Moving over a child element fires dragleave on the label; ignore that.
                    if (!e.currentTarget.contains(e.relatedTarget as Node))
                      setDragging(false);
                  }}
                  onDrop={onDrop}
                  className={cn(
                    "flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-6 text-center transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
                    dragging
                      ? "border-primary bg-primary/5"
                      : errors.files
                        ? "border-destructive/60"
                        : "hover:border-primary/50 hover:bg-accent/30",
                  )}
                >
                  <Upload
                    className="mb-2 h-8 w-8 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <span className="text-sm font-medium">
                    {dragging
                      ? "Drop to add files"
                      : "Drop files here, or click to browse"}
                  </span>
                  <span className="mt-0.5 text-xs text-muted-foreground">
                    PDF, JPG, PNG, WEBP, DOCX, XLSX, PPTX, TXT, MD, CSV
                  </span>
                  {/* Visually hidden, not display:none, so it stays reachable by keyboard. */}
                  <input
                    id="file-upload"
                    type="file"
                    multiple
                    accept={ACCEPTED_TYPES}
                    onChange={onFileChange}
                    aria-invalid={!!errors.files}
                    aria-describedby={errors.files ? "files-error" : undefined}
                    className="sr-only"
                  />
                </label>
                {errors.files && (
                  <p
                    id="files-error"
                    role="alert"
                    className="text-sm text-destructive"
                  >
                    {errors.files}
                  </p>
                )}
                {files.length > 0 && (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <p className="text-muted-foreground" aria-live="polite">
                        {files.length} {files.length === 1 ? "file" : "files"} ·{" "}
                        {formatBytes(totalBytes)}
                      </p>
                      {files.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="text-muted-foreground"
                          onClick={() => setFiles([])}
                        >
                          Remove all
                        </Button>
                      )}
                    </div>
                    <ul className="space-y-2">
                      {files.map((f, idx) => {
                        const extension = extensionOf(f.name);
                        const printReady = PRINTABLE_TYPES.includes(extension);
                        const Icon = IMAGE_TYPES.includes(extension)
                          ? FileImage
                          : FileText;
                        return (
                          <li
                            key={fileKey(f)}
                            className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2 text-sm"
                          >
                            <div className="flex min-w-0 items-center gap-3">
                              <Icon
                                className="h-5 w-5 shrink-0 text-muted-foreground"
                                aria-hidden="true"
                              />
                              <div className="min-w-0">
                                <p className="truncate">{f.name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {extension.toUpperCase()} ·{" "}
                                  {formatBytes(f.size)}
                                </p>
                                {!printReady && (
                                  <p className="text-xs text-amber-700 dark:text-amber-400">
                                    We&apos;ll read this for you, then print it
                                    as PDF.
                                  </p>
                                )}
                              </div>
                            </div>
                            <div className="flex shrink-0 items-center gap-1">
                              {printReady && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() =>
                                    setLocalPreview({
                                      file: f,
                                      url: URL.createObjectURL(f),
                                    })
                                  }
                                >
                                  <Eye
                                    className="mr-1 h-4 w-4"
                                    aria-hidden="true"
                                  />
                                  Preview
                                </Button>
                              )}
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-destructive hover:text-destructive/80"
                                onClick={() => removeFile(idx)}
                                aria-label={`Remove ${f.name}`}
                              >
                                <Trash2
                                  className="h-4 w-4"
                                  aria-hidden="true"
                                />
                              </Button>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <StepTitle step={2}>Print options</StepTitle>
                <CardDescription>
                  Choose how you want your files printed.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {capabilitiesQuery.isError && (
                  <div
                    role="alert"
                    className="flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm"
                  >
                    <span>
                      We couldn&apos;t load the print options. Check your
                      connection and try again.
                    </span>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => capabilitiesQuery.refetch()}
                    >
                      Try again
                    </Button>
                  </div>
                )}
                {capabilitiesQuery.isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (
                  <SpecFields
                    capabilities={capabilities}
                    value={spec}
                    onChange={setSpec}
                    showOrientation={hasImages}
                  />
                )}
              </CardContent>
            </Card>

            {adminMode && (
              <Card>
                <CardHeader>
                  <StepTitle step={customerStep}>Customer</StepTitle>
                  <CardDescription>
                    Link this order to a registered customer's account (the
                    guest details below are then skipped), or leave it empty and
                    enter walk-in details instead.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedCustomer ? (
                    <div className="flex items-center justify-between gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-900 dark:bg-green-950/40">
                      <span className="flex min-w-0 items-center gap-2">
                        <Check
                          className="h-4 w-4 shrink-0 text-green-600"
                          aria-hidden="true"
                        />
                        <span className="font-medium">
                          {customerName(selectedCustomer)}
                        </span>
                        <span className="truncate text-muted-foreground">
                          {selectedCustomer.email}
                        </span>
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 shrink-0 text-muted-foreground hover:text-foreground"
                        onClick={() => setSelectedCustomer(null)}
                        aria-label="Clear selected customer"
                      >
                        <X className="h-4 w-4" aria-hidden="true" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="relative">
                        <Search
                          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <Input
                          type="search"
                          aria-label="Search customers"
                          placeholder="Search customers by name, email or phone…"
                          value={customerSearch}
                          onChange={(e) => setCustomerSearch(e.target.value)}
                          className="pl-9"
                        />
                      </div>
                      {customersQuery.isFetching && (
                        <Skeleton className="h-10 w-full" />
                      )}
                      {customersQuery.isError && (
                        <p role="alert" className="text-sm text-destructive">
                          Couldn&apos;t search customers. Try again in a moment.
                        </p>
                      )}
                      {!customersQuery.isFetching &&
                        customersQuery.data &&
                        customersQuery.data.length > 0 && (
                          <ul className="max-h-52 divide-y overflow-auto rounded-md border">
                            {customersQuery.data.map((c) => (
                              <li key={c.id}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSelectedCustomer(c);
                                    setCustomerSearch("");
                                  }}
                                  className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
                                >
                                  <span className="min-w-0 truncate">
                                    <span className="font-medium">
                                      {customerName(c)}
                                    </span>
                                    <span className="ml-2 text-muted-foreground">
                                      {c.email}
                                    </span>
                                  </span>
                                  {c.phone && (
                                    <span className="shrink-0 text-muted-foreground">
                                      {c.phone}
                                    </span>
                                  )}
                                </button>
                              </li>
                            ))}
                          </ul>
                        )}
                      {!customersQuery.isFetching &&
                        customersQuery.data &&
                        customersQuery.data.length === 0 &&
                        debouncedSearch.trim() && (
                          <p className="text-sm text-muted-foreground">
                            No registered customers match &ldquo;
                            {debouncedSearch.trim()}&rdquo;. Enter walk-in
                            details below instead.
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
                onName={(v) => {
                  setGuestName(v);
                  setErrors((prev) => ({ ...prev, name: undefined }));
                }}
                onMethod={(v) => {
                  setGuestMethod(v);
                  setErrors((prev) => ({ ...prev, value: undefined }));
                }}
                onValue={(v) => {
                  setGuestValue(v);
                  setErrors((prev) => ({ ...prev, value: undefined }));
                }}
                step={guestStep}
                errors={{ name: errors.name, value: errors.value }}
                title={adminMode ? "Walk-in customer details" : "Your details"}
                description={
                  adminMode
                    ? "Enter the customer's details so they can track this order. Required unless you selected an account above."
                    : "So we can send you updates about your order."
                }
              />
            )}
          </div>

          {/* Stays in view on desktop so the submit button is never a long scroll away. */}
          <aside className="lg:sticky lg:top-20">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Order summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Files</dt>
                    <dd className="text-right font-medium">
                      {files.length > 0
                        ? `${files.length} · ${formatBytes(totalBytes)}`
                        : "None yet"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">
                      {adminMode ? "Customer" : "Order for"}
                    </dt>
                    <dd className="min-w-0 truncate text-right font-medium">
                      {forWhom}
                    </dd>
                  </div>
                </dl>

                <Separator />

                {missing.length > 0 && (
                  <p className="text-sm text-muted-foreground">
                    Still needed: {missing.join(" and ")}.
                  </p>
                )}

                <div className="space-y-2">
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isSubmitting}
                  >
                    {isSubmitting && (
                      <Loader2
                        className="mr-2 h-4 w-4 animate-spin"
                        aria-hidden="true"
                      />
                    )}
                    {isSubmitting
                      ? uploadPct !== null && uploadPct < 100
                        ? `Uploading ${uploadPct}%`
                        : "Submitting…"
                      : adminMode
                        ? "Create order"
                        : "Place order"}
                  </Button>
                  {isSubmitting && uploadPct !== null && (
                    <div
                      role="progressbar"
                      aria-label="Upload progress"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={uploadPct}
                      className="h-1.5 overflow-hidden rounded-full bg-muted"
                    >
                      <div
                        className="h-full bg-primary transition-[width]"
                        style={{ width: `${uploadPct}%` }}
                      />
                    </div>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    disabled={isSubmitting}
                    onClick={() => navigate(adminMode ? "/admin" : "/")}
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          </aside>
        </div>
      </form>

      <Dialog
        open={!!localPreview}
        onOpenChange={(next) => {
          if (!next) setLocalPreview(null);
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="truncate text-base">
              {localPreview?.file.name}
            </DialogTitle>
            <DialogDescription className="sr-only">
              Preview of the selected file
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[70vh] overflow-auto rounded-md bg-muted/40">
            {localPreview?.file.name.toLowerCase().endsWith(".pdf") ? (
              <iframe
                src={localPreview.url}
                title={localPreview.file.name}
                className="h-[70vh] w-full"
              />
            ) : localPreview ? (
              <div className="flex justify-center p-4">
                <img
                  src={localPreview.url}
                  alt={localPreview.file.name}
                  className="max-h-[65vh] object-contain"
                />
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
