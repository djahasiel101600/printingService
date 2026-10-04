import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileText,
  Minus,
  Plus,
  QrCode,
  Trash2,
  Upload,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/components/auth";
import SpecFields, { DEFAULT_SPEC } from "@/components/SpecFields";
import { GuestDetailsCard, type GuestMethod } from "@/pages/NewOrderPage";
import { api, apiErrorMessage, saveGuestOrder } from "@/lib/api";
import { formatBytes, paperSizeLabel, qualityLabel } from "@/lib/constants";
import type {
  Capabilities,
  CheckoutResponse,
  EstimateResponse,
  Order,
  PrintSpecification,
  Quote,
  ShopPaymentSettings,
} from "@/lib/types";

/** Mirrors PREVIEWABLE_EXTENSIONS in backend/apps/orders/models.py. */
const ACCEPTED_TYPES =
  ".pdf,.jpg,.jpeg,.png,.webp,.docx,.xlsx,.pptx,.txt,.md,.csv";

const STEP_LABELS = ["Upload", "Settings", "Details", "Payment", "Review"];

type PaymentChoice = "full" | "partial" | "pickup";

/**
 * Mobile-first scan-to-print wizard (PRD FR-16..18), entered via the shop's
 * QR code at `/q`. Five steps — upload → settings → details → payment →
 * review — then a confirmation screen with the QR Ph code (or "pay when you
 * collect"). State is held in memory only; nothing is persisted until the
 * order is created on the Review step.
 */
export default function QuickPrintPage() {
  const { user } = useAuth();

  const [step, setStep] = useState(1);
  const [files, setFiles] = useState<File[]>([]);
  /** Orientation only affects picture files, so the control follows the uploads. */
  const hasImages = files.some((file) => /\.(jpe?g|png|webp)$/i.test(file.name));
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [spec, setSpec] = useState<PrintSpecification>(DEFAULT_SPEC);
  const [guestName, setGuestName] = useState("");
  const [guestMethod, setGuestMethod] = useState<GuestMethod>("email");
  const [guestValue, setGuestValue] = useState("");
  const [paymentChoice, setPaymentChoice] = useState<PaymentChoice | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Confirmation state — set once the order exists (see placeOrder()).
  const [createdOrder, setCreatedOrder] = useState<Order | null>(null);
  const [qrResult, setQrResult] = useState<CheckoutResponse | null>(null);
  const [checkoutFailed, setCheckoutFailed] = useState(false);
  const [paid, setPaid] = useState(false);

  const capabilitiesQuery = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => (await api.get<Capabilities>("/printing/capabilities/")).data,
  });
  const capabilities = capabilitiesQuery.data ?? null;

  const settingsQuery = useQuery({
    queryKey: ["payment-settings"],
    queryFn: async () => (await api.get<ShopPaymentSettings>("/payments/settings/")).data,
  });
  const allowPickup = settingsQuery.data?.allow_pay_on_pickup ?? false;

  const sizes = capabilities?.paperSizes ?? [];
  const currentSize = sizes.find((s) => s.paperSize === spec.media_size) ?? sizes[0];
  const currentType =
    currentSize?.paperTypes.find((t) => t.paperType === spec.media_type) ??
    currentSize?.paperTypes[0];
  const supportsDuplex = currentType?.doubleSided ?? true;
  const qualityOptions = currentType?.printQualities ?? ["draft", "normal", "high"];

  // -------------------------------------------------- step 1: page estimate
  const estimateMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      const { data } = await api.post<EstimateResponse>("/orders/estimate/", formData);
      return data;
    },
    onSuccess: (data) => {
      setEstimate(data);
      setStep(2);
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  // Editing the file list invalidates the counts.
  useEffect(() => {
    setEstimate(null);
  }, [files]);

  // ------------------------------------------------- step 2: live quote
  // Debounced so chips/steppers don't hammer POST /orders/quote/.
  interface QuoteInput {
    spec: PrintSpecification;
    pageCounts: number[];
    labels: string[];
  }
  const [quoteInput, setQuoteInput] = useState<QuoteInput | null>(null);
  useEffect(() => {
    if (!estimate) {
      setQuoteInput(null);
      return;
    }
    const next: QuoteInput = {
      spec,
      pageCounts: estimate.files.map((f) => f.page_count),
      labels: estimate.files.map((f) => f.name),
    };
    const timer = setTimeout(() => setQuoteInput(next), 350);
    return () => clearTimeout(timer);
  }, [estimate, spec]);

  const quoteQuery = useQuery({
    queryKey: ["quick-quote", quoteInput],
    enabled: quoteInput !== null,
    queryFn: async () => {
      if (!quoteInput) return null;
      const specs = quoteInput.pageCounts.map((page_count, index) => ({
        page_count,
        label: quoteInput.labels[index] ?? `File ${index + 1}`,
        media_size: quoteInput.spec.media_size,
        media_type: quoteInput.spec.media_type,
        color_mode: quoteInput.spec.color_mode,
        print_quality: quoteInput.spec.print_quality,
        sides: quoteInput.spec.sides,
        copies: quoteInput.spec.copies,
      }));
      const { data } = await api.post<Quote>("/orders/quote/", { files: specs });
      return data;
    },
    retry: false,
  });
  const quote = quoteQuery.data;

  // ------------------------------------- steps 4-5: create order + checkout
  const createMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      formData.append("spec", JSON.stringify(spec));
      if (!user) {
        formData.append("guest_name", guestName.trim());
        formData.append("guest_contact_method", guestMethod);
        formData.append("guest_contact_value", guestValue.trim());
      }
      const { data } = await api.post<{ order: Order; quote: Quote }>("/orders/", formData);
      return data.order;
    },
  });

  const checkoutMutation = useMutation({
    mutationFn: async (order: Order) => {
      const payload: Record<string, unknown> = {
        order_id: order.id,
        method: paymentChoice === "pickup" ? "pickup" : "qrph",
      };
      if (paymentChoice !== "pickup") payload.payment_type = paymentChoice;
      const { data } = await api.post<CheckoutResponse>("/payments/checkout/", payload);
      return data;
    },
  });

  /**
   * Create the order, then take payment. The guest ref is saved to
   * localStorage BEFORE checkout so a failed checkout can never orphan the
   * order — the customer still finds it under My Orders / Order detail,
   * which has its own retry-payment path.
   */
  async function placeOrder() {
    let order: Order;
    try {
      order = await createMutation.mutateAsync();
    } catch (err) {
      toast.error(apiErrorMessage(err));
      return;
    }
    setCreatedOrder(order);
    if (!user) {
      saveGuestOrder({
        id: order.id,
        tracking_id: order.tracking_id,
        created_at: order.created_at,
      });
    }
    try {
      const checkout = await checkoutMutation.mutateAsync(order);
      if (checkout.method === "qrph") setQrResult(checkout);
      // pickup: backend moved the order straight to pending_review.
    } catch (err) {
      setCheckoutFailed(true);
      toast.error(apiErrorMessage(err));
    }
  }

  // ------------------------------------------------ confirmation: polling
  const statusQuery = useQuery({
    queryKey: ["order", String(createdOrder?.id ?? 0), user ? "auth" : `guest:${createdOrder?.tracking_id ?? ""}`],
    enabled: Boolean(createdOrder && qrResult) && !paid,
    retry: false,
    refetchInterval: 4000,
    queryFn: async () => {
      const { data } = await api.get<Order>(`/orders/${createdOrder!.id}/`, {
        params: user ? undefined : { tracking_id: createdOrder!.tracking_id },
      });
      return data;
    },
  });
  useEffect(() => {
    const status = statusQuery.data?.status;
    if (status && status !== "draft" && status !== "awaiting_payment") setPaid(true);
  }, [statusQuery.data]);

  const simulateMutation = useMutation({
    mutationFn: async (paymentId: number) =>
      (await api.post("/payments/webhook/simulate/", { payment_id: paymentId })).data,
    onSuccess: () => {
      toast.success("Payment confirmed!");
      setPaid(true);
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  // ------------------------------------------------------------- helpers
  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    if (selected.length) setFiles((prev) => [...prev, ...selected]);
    e.target.value = "";
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  /** Switch paper size, fixing up dependent fields the new size may not offer. */
  function pickSize(size: string) {
    const nextSize = sizes.find((s) => s.paperSize === size);
    const types = nextSize?.paperTypes ?? [];
    const typeCodes = types.map((t) => t.paperType);
    const mediaType =
      types.length === 0 || typeCodes.includes(spec.media_type)
        ? spec.media_type
        : types[0].paperType;
    const typeDetail = types.find((t) => t.paperType === mediaType);
    const qualitiesForType = typeDetail?.printQualities ?? qualityOptions;
    setSpec({
      ...spec,
      media_size: size,
      media_type: mediaType,
      sides: (typeDetail?.doubleSided ?? true) && spec.sides !== "none" ? spec.sides : "none",
      print_quality: (qualitiesForType.includes(spec.print_quality)
        ? spec.print_quality
        : (qualitiesForType[1] ?? "normal")) as PrintSpecification["print_quality"],
    });
  }

  function stepCanContinue(): boolean {
    if (step === 1) return files.length > 0 && estimate !== null;
    if (step === 3 && !user) {
      return Boolean(guestName.trim() && guestValue.trim());
    }
    if (step === 4) return paymentChoice !== null;
    return true;
  }

  function handleContinue() {
    if (step === 1) {
      if (files.length > 0 && !estimate) estimateMutation.mutate();
      return;
    }
    if (step === 4 && !stepCanContinue()) return;
    setStep((s) => Math.min(5, s + 1));
  }

  function handleBack() {
    setStep((s) => Math.max(1, s - 1));
  }

  function resetWizard() {
    setStep(1);
    setFiles([]);
    setEstimate(null);
    setQuoteInput(null);
    setSpec(DEFAULT_SPEC);
    setGuestName("");
    setGuestMethod("email");
    setGuestValue("");
    setPaymentChoice(null);
    setCreatedOrder(null);
    setQrResult(null);
    setCheckoutFailed(false);
    setPaid(false);
    setAdvancedOpen(false);
  }

  const busy =
    estimateMutation.isPending ||
    createMutation.isPending ||
    checkoutMutation.isPending;

  // ------------------------------------------------- confirmation screen
  if (createdOrder) {
    const orderLink = `/orders/${createdOrder.id}`;
    if (paid) {
      return (
        <div className="mx-auto max-w-lg">
          <Card className="border-green-200 bg-green-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-800">
                <CheckCircle2 className="h-5 w-5" /> Payment received!
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-green-700">
              <p>
                Order <strong className="tracking-wider">{createdOrder.tracking_id}</strong> is
                paid. Our staff reviews every job before it hits the printer.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild><Link to={orderLink}>View order status</Link></Button>
                <Button asChild variant="outline">
                  <Link to="/q" onClick={resetWizard}>Start a new print job</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }

    if (checkoutFailed) {
      return (
        <div className="mx-auto max-w-lg">
          <Card className="border-amber-200 bg-amber-50">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-amber-800">
                <Wallet className="h-5 w-5" /> Order created — payment pending
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-amber-700">
              <p>
                Your order <strong className="tracking-wider">{createdOrder.tracking_id}</strong>{" "}
                was created, but we couldn't start the payment. You can pay any time from the
                order page.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button asChild><Link to={orderLink}>Open order &amp; pay</Link></Button>
                <Button asChild variant="outline">
                  <Link to="/q" onClick={resetWizard}>Start over</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }

    if (qrResult) {
      return (
        <div className="mx-auto max-w-lg">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <QrCode className="h-5 w-5" /> Scan to pay with QR Ph
              </CardTitle>
              <CardDescription>
                Order {createdOrder.tracking_id}
                {qrResult.expires_at && (
                  <> · expires {new Date(qrResult.expires_at).toLocaleTimeString()}</>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-center">
              {qrResult.qr_image_url ? (
                <img
                  src={qrResult.qr_image_url}
                  alt="QR Ph payment code"
                  className="mx-auto h-64 w-64 rounded-md border bg-white object-contain"
                />
              ) : (
                <div className="mx-auto flex h-64 w-64 items-center justify-center rounded-md border bg-muted">
                  <QrCode className="h-16 w-16 text-muted-foreground" />
                </div>
              )}
              <p className="text-sm">
                Amount: <strong>₱{(qrResult.amount_peso ?? 0).toFixed(2)}</strong>
              </p>
              <p className="text-xs text-muted-foreground">
                Open your bank or e-wallet app, scan the code, and confirm the payment.
                This page checks for payment every few seconds.
              </p>
              <Separator />
              {qrResult.mock_mode && qrResult.payment_id ? (
                <Button
                  className="w-full"
                  onClick={() => qrResult.payment_id && simulateMutation.mutate(qrResult.payment_id)}
                  disabled={simulateMutation.isPending}
                >
                  <Wallet className="mr-2 h-4 w-4" />
                  {simulateMutation.isPending
                    ? "Confirming…"
                    : "Simulate successful payment (mock mode)"}
                </Button>
              ) : (
                <Button className="w-full" variant="outline" onClick={() => statusQuery.refetch()}>
                  I've paid — check status
                </Button>
              )}
              <Button asChild className="w-full" variant="ghost">
                <Link to={orderLink}>View order details</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }

    // Pay upon pickup: order already sits in the review queue.
    return (
      <div className="mx-auto max-w-lg">
        <Card className="border-green-200 bg-green-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-800">
              <CheckCircle2 className="h-5 w-5" /> Order placed!
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-green-700">
            <p>
              Tracking ID <strong className="tracking-wider">{createdOrder.tracking_id}</strong>{" "}
              — pay when you collect your printout. Bring ₱
              {(createdOrder.balance_due_peso || createdOrder.subtotal_peso).toFixed(2)}.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button asChild><Link to={orderLink}>View order</Link></Button>
              <Button asChild variant="outline">
                <Link to="/q" onClick={resetWizard}>Start a new print job</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---------------------------------------------------------- the wizard
  return (
    <div className="mx-auto max-w-lg space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <FileText className="h-6 w-6 text-primary" /> Quick print
        </h1>
        <p className="text-sm text-muted-foreground">
          Upload, choose your settings, pay — we review every job before printing.
        </p>
      </div>

      {/* progress stepper */}
      <ol className="flex items-start justify-between gap-1" aria-label="Progress">
        {STEP_LABELS.map((label, index) => {
          const number = index + 1;
          const done = number < step;
          const current = number === step;
          return (
            <li key={label} className="flex flex-1 flex-col items-center gap-1">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${
                  done
                    ? "bg-primary text-primary-foreground"
                    : current
                      ? "border-2 border-primary text-primary"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {done ? "✓" : number}
              </span>
              <span
                className={`text-center text-[11px] leading-tight ${
                  current ? "font-medium text-foreground" : "text-muted-foreground"
                }`}
              >
                {label}
              </span>
            </li>
          );
        })}
      </ol>

      {/* ---------------------------------------------------- step 1: upload */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" /> Upload your files
            </CardTitle>
            <CardDescription>
              PDFs and images print directly; Word/Excel files are converted by the shop first.
              Max 20MB each.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="flex h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed text-sm text-muted-foreground transition hover:border-primary hover:text-foreground">
              <Upload className="h-6 w-6" />
              <span className="font-medium">Tap to choose files</span>
              <span className="text-xs">or drop them here</span>
              <input
                type="file"
                multiple
                accept={ACCEPTED_TYPES}
                className="sr-only"
                onChange={onFileChange}
              />
            </label>
            {estimate && (
              <p className="text-sm font-medium">
                {estimate.total_pages} page{estimate.total_pages === 1 ? "" : "s"} to print
              </p>
            )}
            {files.length > 0 && (
              <ul className="space-y-2">
                {files.map((file, index) => (
                  <li
                    key={`${file.name}-${index}`}
                    className="flex items-center justify-between gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatBytes(file.size)}
                        {estimate &&
                          ` · ${estimate.files[index]?.page_count ?? "?"} page${
                            estimate.files[index]?.page_count === 1 ? "" : "s"
                          }`}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="rounded p-2 text-destructive hover:bg-destructive/10"
                      aria-label={`Remove ${file.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {/* --------------------------------------------- step 2: print settings */}
      {step === 2 && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Print settings</CardTitle>
              <CardDescription>
                Black &amp; white or color, paper, copies and sides — the price updates as you go.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* color toggle cards */}
              <div className="grid grid-cols-2 gap-3">
                {([
                  { value: "mono", title: "Black & white", hint: "Cheapest" },
                  { value: "color", title: "Color", hint: "Full color" },
                ] as const).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setSpec({ ...spec, color_mode: option.value })}
                    className={`flex h-24 flex-col items-center justify-center gap-0.5 rounded-lg border-2 text-sm font-medium transition ${
                      spec.color_mode === option.value
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    {option.title}
                    <span className="text-xs font-normal text-muted-foreground">{option.hint}</span>
                  </button>
                ))}
              </div>

              {/* paper size chips */}
              <div className="space-y-1.5">
                <span className="text-sm font-medium">Paper size</span>
                <div className="flex flex-wrap gap-2">
                  {(sizes.length > 0 ? sizes.map((s) => s.paperSize) : ["ps_a4"]).map((size) => (
                    <button
                      key={size}
                      type="button"
                      onClick={() => pickSize(size)}
                      className={`h-9 rounded-full border px-3 text-sm transition ${
                        spec.media_size === size
                          ? "border-primary bg-primary/10 font-medium text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {paperSizeLabel(size)}
                    </button>
                  ))}
                </div>
              </div>

              {/* quality chips */}
              <div className="space-y-1.5">
                <span className="text-sm font-medium">Quality</span>
                <div className="flex flex-wrap gap-2">
                  {qualityOptions.map((quality) => (
                    <button
                      key={quality}
                      type="button"
                      onClick={() =>
                        setSpec({ ...spec, print_quality: quality as PrintSpecification["print_quality"] })}
                      className={`h-9 rounded-full border px-3 text-sm transition ${
                        spec.print_quality === quality
                          ? "border-primary bg-primary/10 font-medium text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {qualityLabel(quality).split(" (")[0]}
                    </button>
                  ))}
                </div>
              </div>

              {/* copies stepper */}
              <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <p className="text-sm font-medium">Copies</p>
                  <p className="text-xs text-muted-foreground">of every file</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-11 w-11"
                    aria-label="Fewer copies"
                    disabled={spec.copies <= 1}
                    onClick={() => setSpec({ ...spec, copies: Math.max(1, spec.copies - 1) })}
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <span className="w-8 text-center text-lg font-semibold">{spec.copies}</span>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-11 w-11"
                    aria-label="More copies"
                    disabled={spec.copies >= 99}
                    onClick={() => setSpec({ ...spec, copies: Math.min(99, spec.copies + 1) })}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              {/* single/double-sided */}
              <div className="grid grid-cols-2 gap-3">
                {([
                  { value: "none", title: "Single-sided", hint: "One side per sheet" },
                  { value: "long", title: "Double-sided", hint: "Saves paper & money" },
                ] as const).map((option) => {
                  const disabled = option.value !== "none" && !supportsDuplex;
                  const active = spec.sides === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      disabled={disabled}
                      onClick={() => setSpec({ ...spec, sides: option.value })}
                      className={`flex h-20 flex-col items-center justify-center gap-0.5 rounded-lg border-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                        active ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                      }`}
                    >
                      {option.title}
                      <span className="text-xs font-normal text-muted-foreground">
                        {disabled ? "Not available for this paper" : option.hint}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* advanced settings (full spec editor) */}
              <div className="rounded-md border">
                <Button
                  type="button"
                  variant="ghost"
                  className="w-full justify-between px-3"
                  onClick={() => setAdvancedOpen((open) => !open)}
                >
                  <span className="text-sm font-medium">Advanced settings</span>
                  {advancedOpen ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
                {advancedOpen && (
                  <div className="border-t p-3">
                    {capabilitiesQuery.isLoading ? (
                      <Skeleton className="h-40 w-full" />
                    ) : (
                      <SpecFields capabilities={capabilities} value={spec} onChange={setSpec}
                        showOrientation={hasImages} />
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* live price bar */}
          <div className="rounded-lg border bg-card px-4 py-3 shadow-sm">
            {quoteQuery.isFetching ? (
              <p className="text-sm text-muted-foreground">Updating price…</p>
            ) : quote ? (
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-muted-foreground">Estimated total</p>
                  <p className="text-2xl font-bold">₱{quote.subtotal_peso.toFixed(2)}</p>
                </div>
                <p className="text-right text-xs text-muted-foreground">
                  {estimate?.total_pages ?? 0} page{estimate?.total_pages === 1 ? "" : "s"} ×{" "}
                  {spec.copies} cop{spec.copies === 1 ? "y" : "ies"}
                  <br />
                  {spec.color_mode === "color" ? "Color" : "Black & white"} ·{" "}
                  {spec.sides === "none" ? "single-sided" : "double-sided"}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                The price appears here as soon as it's quoted.
              </p>
            )}
          </div>
        </>
      )}

      {/* ------------------------------------------- step 3: contact + notes */}
      {step === 3 && (
        <>
          {user ? (
            <Card>
              <CardHeader>
                <CardTitle>Your details</CardTitle>
                <CardDescription>
                  This order will be linked to your account ({user.email}).
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <GuestDetailsCard
              name={guestName}
              method={guestMethod}
              value={guestValue}
              onName={setGuestName}
              onMethod={setGuestMethod}
              onValue={setGuestValue}
            />
          )}
          <Card>
            <CardHeader>
              <CardTitle>Notes for the shop</CardTitle>
              <CardDescription>
                Page ranges, staples, deadlines — anything that helps us get it right.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                id="quick-notes"
                rows={3}
                placeholder="e.g. print pages 1–10 double-sided, staple top-left"
                value={spec.free_text_instructions ?? ""}
                onChange={(e) => setSpec({ ...spec, free_text_instructions: e.target.value })}
              />
            </CardContent>
          </Card>
        </>
      )}

      {/* --------------------------------------------- step 4: payment method */}
      {step === 4 && (
        <Card>
          <CardHeader>
            <CardTitle>How do you want to pay?</CardTitle>
            <CardDescription>
              {quote
                ? `Total ₱${quote.subtotal_peso.toFixed(2)} — QR Ph payments are confirmed automatically.`
                : "QR Ph payments are confirmed automatically."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {([
              {
                choice: "full" as const,
                title: "Pay in full",
                detail: quote ? `₱${quote.subtotal_peso.toFixed(2)} now via QR Ph` : "QR Ph",
                icon: QrCode,
                disabled: false,
                note: undefined as string | undefined,
              },
              {
                choice: "partial" as const,
                title: "Pay a down payment",
                detail: quote
                  ? `From ₱${quote.min_partial_peso.toFixed(2)} now, rest on pickup`
                  : "QR Ph — pay part now",
                icon: Wallet,
                disabled: quote ? quote.min_partial_peso >= quote.subtotal_peso : false,
                note: quote && quote.min_partial_peso >= quote.subtotal_peso
                  ? "Already the full amount — pay in full instead."
                  : undefined,
              },
            ]).map((option) => {
              const Icon = option.icon;
              const active = paymentChoice === option.choice;
              return (
                <button
                  key={option.choice}
                  type="button"
                  disabled={option.disabled}
                  onClick={() => setPaymentChoice(option.choice)}
                  className={`flex w-full items-center justify-between gap-3 rounded-lg border-2 p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-40 ${
                    active ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                  }`}
                >
                  <div>
                    <p className="font-medium">{option.title}</p>
                    <p className="text-sm text-muted-foreground">{option.detail}</p>
                    {option.note && (
                      <p className="text-xs text-muted-foreground">{option.note}</p>
                    )}
                  </div>
                  <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
                </button>
              );
            })}

            {allowPickup ? (
              (() => {
                const active = paymentChoice === "pickup";
                return (
                  <button
                    type="button"
                    onClick={() => setPaymentChoice("pickup")}
                    className={`flex w-full items-center justify-between gap-3 rounded-lg border-2 p-4 text-left transition ${
                      active ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                    }`}
                  >
                    <div>
                      <p className="font-medium">Pay when you collect</p>
                      <p className="text-sm text-muted-foreground">
                        No payment now — bring cash or scan the shop's QR Ph at pickup.
                      </p>
                    </div>
                    <Wallet className="h-5 w-5 shrink-0 text-muted-foreground" />
                  </button>
                );
              })()
            ) : (
              <p className="text-xs text-muted-foreground">
                Pay upon pickup is currently disabled by the shop.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* ------------------------------------------------ step 5: review */}
      {step === 5 && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Review your order</CardTitle>
              <CardDescription>Check everything, then place the order.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div>
                <p className="mb-1 font-medium">Files</p>
                <ul className="space-y-1 rounded-md bg-muted/50 px-3 py-2">
                  {estimate?.files.map((entry, index) => (
                    <li key={index} className="flex justify-between gap-3">
                      <span className="truncate">{entry.name}</span>
                      <span className="shrink-0 text-muted-foreground">
                        {entry.page_count} page{entry.page_count === 1 ? "" : "s"}
                        {!entry.print_ready && " · converted by shop"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="mb-1 font-medium">Print settings</p>
                <p className="text-muted-foreground">
                  {paperSizeLabel(spec.media_size)} ·{" "}
                  {spec.color_mode === "color" ? "Color" : "Black & white"} ·{" "}
                  {qualityLabel(spec.print_quality).split(" (")[0]} ·{" "}
                  {spec.sides === "none" ? "single-sided" : "double-sided"} · {spec.copies} cop
                  {spec.copies === 1 ? "y" : "ies"}
                </p>
              </div>
              {!user && (
                <div>
                  <p className="mb-1 font-medium">Contact</p>
                  <p className="text-muted-foreground">
                    {guestName} · {guestMethod}: {guestValue}
                  </p>
                </div>
              )}
              {(spec.free_text_instructions ?? "").trim() && (
                <div>
                  <p className="mb-1 font-medium">Notes</p>
                  <p className="whitespace-pre-wrap text-muted-foreground">
                    {spec.free_text_instructions}
                  </p>
                </div>
              )}
              <div>
                <p className="mb-1 font-medium">Payment</p>
                <p className="text-muted-foreground">
                  {paymentChoice === "full" && "Pay in full now via QR Ph"}
                  {paymentChoice === "partial" && quote && (
                    <>Down payment ₱{quote.min_partial_peso.toFixed(2)} now via QR Ph</>
                  )}
                  {paymentChoice === "pickup" && "Pay when you collect"}
                </p>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <span className="font-medium">Total</span>
                <span className="text-2xl font-bold">
                  {quote ? `₱${quote.subtotal_peso.toFixed(2)}` : "—"}
                </span>
              </div>
              {quote && quote.min_partial_peso < quote.subtotal_peso && (
                <p className="text-xs text-muted-foreground">
                  Minimum down payment: ₱{quote.min_partial_peso.toFixed(2)}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* -------------------------------------------------- sticky CTA bar */}
      <div className="sticky bottom-0 z-30 -mx-4 mt-6 border-t bg-background/95 px-4 py-3 backdrop-blur">
        <div className="flex gap-3">
          {step > 1 ? (
            <Button
              variant="outline"
              className="h-12 flex-1"
              onClick={handleBack}
              disabled={busy}
            >
              <ArrowLeft className="mr-2 h-4 w-4" /> Back
            </Button>
          ) : (
            <Button asChild variant="outline" className="h-12 flex-1">
              <Link to="/">Cancel</Link>
            </Button>
          )}
          {step < 5 ? (
            <Button
              className="h-12 flex-1"
              onClick={handleContinue}
              // Step 1's Continue *starts* the page-count estimate (which then
              // advances), so it only needs files — not a finished estimate.
              disabled={
                busy || (step === 1 ? files.length === 0 : !stepCanContinue())
              }
            >
              {estimateMutation.isPending ? (
                <>
                  <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Counting pages…
                </>
              ) : (
                <>
                  Continue <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          ) : (
            <Button
              className="h-12 flex-1"
              onClick={placeOrder}
              disabled={busy || !stepCanContinue()}
            >
              {createMutation.isPending || checkoutMutation.isPending ? (
                "Placing order…"
              ) : (
                <>
                  Place order <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}