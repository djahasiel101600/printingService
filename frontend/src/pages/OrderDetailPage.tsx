import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  Copy,
  Eye,
  FileText,
  FileUp,
  History,
  Info,
  Loader2,
  LogIn,
  QrCode,
  Wallet,
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
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import FilePreviewDialog from "@/components/FilePreviewDialog";
import { useAuth } from "@/components/auth";
import { api, apiErrorMessage, loadGuestOrders } from "@/lib/api";
import type {
  CheckoutResponse,
  Order,
  OrderFile,
  ShopPaymentSettings,
} from "@/lib/types";
import { cn } from "@/lib/utils";

interface CreatedState {
  justCreated?: boolean;
  trackingId?: string;
}

/** Thousands separators make larger totals readable at a glance. */
const peso = (n: number) =>
  `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const dateTime = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

/** Payment status as a small coloured chip. Unknown statuses fall back to neutral. */
function paymentChipClass(status: string) {
  const s = status.toLowerCase();
  if (s.includes("paid") || s.includes("success")) {
    return "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300";
  }
  if (s.includes("fail") || s.includes("expire") || s.includes("cancel")) {
    return "bg-destructive/10 text-destructive";
  }
  return "bg-muted text-muted-foreground";
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const location = useLocation();
  const queryClient = useQueryClient();
  const justCreated = Boolean(
    (location.state as CreatedState | null)?.justCreated,
  );

  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [showCheckout, setShowCheckout] = useState(false);
  const [qrResult, setQrResult] = useState<CheckoutResponse | null>(null);
  const [previewFile, setPreviewFile] = useState<OrderFile | null>(null);
  const [reuploadFile, setReuploadFile] = useState<OrderFile | null>(null);
  const reuploadInput = useRef<HTMLInputElement>(null);

  // Orders placed without an account are proven by their tracking ID, which
  // is stored on this device right after checkout (see NewOrderPage).
  const guestRef = !user
    ? loadGuestOrders().find((o) => String(o.id) === id)
    : undefined;
  const canView = Boolean(user || guestRef);

  const {
    data: order,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: [
      "order",
      id,
      user ? "auth" : `guest:${guestRef?.tracking_id ?? ""}`,
    ],
    enabled: canView,
    retry: false,
    refetchInterval: showCheckout && qrResult ? 4000 : false,
    queryFn: async () => {
      const { data } = await api.get<Order>(`/orders/${id}/`, {
        params: user ? undefined : { tracking_id: guestRef?.tracking_id },
      });
      return data;
    },
  });

  const settingsQuery = useQuery({
    queryKey: ["payment-settings"],
    queryFn: async () =>
      (await api.get<ShopPaymentSettings>("/payments/settings/")).data,
  });

  const checkoutMutation = useMutation({
    mutationFn: async (payload: {
      method: "qrph" | "pickup";
      payment_type?: "full" | "partial";
    }) => {
      const { data } = await api.post<CheckoutResponse>("/payments/checkout/", {
        order_id: Number(id),
        method: payload.method,
        ...(payload.method === "qrph"
          ? { payment_type: payload.payment_type }
          : {}),
      });
      return data;
    },
    onSuccess: (data) => {
      if (data.method === "pickup") {
        toast.success(
          "Pay upon pickup selected — settle the balance when you collect your order.",
        );
        setShowCheckout(false);
        setQrResult(null);
      } else {
        setQrResult(data);
      }
      queryClient.invalidateQueries({ queryKey: ["order", id] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const simulateMutation = useMutation({
    mutationFn: async (paymentId: number) =>
      (await api.post("/payments/webhook/simulate/", { payment_id: paymentId }))
        .data,
    onSuccess: () => {
      toast.success("Payment received! Your order is now in review.");
      setShowCheckout(false);
      setQrResult(null);
      queryClient.invalidateQueries({ queryKey: ["order", id] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  // The shop asked for changes: replace one file with a corrected version.
  // Guests post the tracking ID as the ownership proof (multipart body).
  const reuploadMutation = useMutation({
    mutationFn: async ({ file, upload }: { file: OrderFile; upload: File }) => {
      const body = new FormData();
      body.append("file", upload);
      if (guestRef?.tracking_id)
        body.append("tracking_id", guestRef.tracking_id);
      const { data } = await api.post<Order>(
        `/orders/${id}/files/${file.id}/reupload/`,
        body,
      );
      return data;
    },
    // Read the target from the mutation variables (not state) so the toast
    // always names the file that was actually replaced.
    onSuccess: (data, variables) => {
      const updated = data.files.find((f) => f.id === variables.file.id);
      toast.success(
        updated
          ? `Uploaded v${updated.current_version} of ${updated.file_name}.`
          : "Revised file uploaded.",
      );
      setReuploadFile(null);
      queryClient.invalidateQueries({ queryKey: ["order", id] });
      queryClient.invalidateQueries({ queryKey: ["my-orders"] });
    },
    onError: (err) => {
      setReuploadFile(null);
      toast.error(apiErrorMessage(err));
    },
  });

  // Hand the order back to the shop: revision_requested -> pending_review.
  // The server also requires at least one v2+ file, mirrored here for UX.
  const resubmitMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<Order>(
        `/orders/${id}/resubmit/`,
        guestRef?.tracking_id ? { tracking_id: guestRef.tracking_id } : {},
      );
      return data;
    },
    onSuccess: () => {
      toast.success("Revised files sent back for review.");
      queryClient.invalidateQueries({ queryKey: ["order", id] });
      queryClient.invalidateQueries({ queryKey: ["my-orders"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  // Close the payment dialog by itself once the order is no longer payable
  // (e.g. the webhook confirmed the payment while we were polling).
  const payable =
    order?.status === "draft" || order?.status === "awaiting_payment";
  useEffect(() => {
    if (showCheckout && order && !payable) {
      setShowCheckout(false);
      setQrResult(null);
    }
  }, [showCheckout, order, payable]);

  if (!canView) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in or track your order</CardTitle>
          <CardDescription>
            This order was not placed from this device, so we need to confirm it
            belongs to you.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Button asChild className="flex-1">
            <Link to="/login">
              <LogIn className="mr-2 h-4 w-4" aria-hidden="true" /> Log in
            </Link>
          </Button>
          <Button asChild variant="outline" className="flex-1">
            <Link to="/track">Track with tracking ID</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Skeleton mirrors the real layout so the page doesn't jump when data arrives.
  if (isLoading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading order">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="space-y-6">
            <Skeleton className="h-56 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }
  if (isError || !order) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Order not available</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            We couldn&apos;t load this order. It may belong to a different
            account.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => refetch()}>
              Try again
            </Button>
            <Button asChild variant="outline">
              <Link to="/track">Track an order</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const canPay = payable && order.balance_due_peso > 0;
  const allowPickup = settingsQuery.data?.allow_pay_on_pickup ?? false;
  const needsRevision = order?.status === "revision_requested";
  // At least one file already replaced (v2+) — mirrors the server rule so
  // the customer cannot bounce an untouched order back into the queue.
  const hasRevisedFiles = Boolean(
    order?.files.some((f) => (f.current_version ?? 1) > 1),
  );
  const revisedCount = order.files.filter(
    (f) => (f.current_version ?? 1) > 1,
  ).length;
  const paidPct =
    order.subtotal_peso > 0
      ? Math.min(
          100,
          Math.round((order.amount_paid_peso / order.subtotal_peso) * 100),
        )
      : 0;
  const paidInFull = order.balance_due_peso <= 0 && order.amount_paid_peso > 0;

  async function copyTrackingId() {
    try {
      await navigator.clipboard.writeText(order!.tracking_id);
      toast.success("Tracking ID copied!");
    } catch {
      // Clipboard access can be blocked (insecure origin, permissions).
      toast.error(
        "Couldn't copy automatically. Select the tracking ID and copy it manually.",
      );
    }
  }

  /**
   * What the customer has to do next. Shown first when it's their move.
   *
   * Gated on the *status*, not the note: a revision requested without a
   * message used to render nothing here, so the customer saw the Replace
   * buttons but no "Submit revised files for review" button — and the
   * order could never leave revision_requested. The note is optional
   * copy; the button is driven by needsRevision alone.
   */
  const revisionCard = needsRevision || order.revision_note ? (
    <Card className="border-orange-200 bg-orange-50 dark:border-orange-900 dark:bg-orange-950/30">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base text-orange-800 dark:text-orange-300">
          <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
          {needsRevision ? "Revision requested" : "Earlier revision request"}
        </CardTitle>
        {needsRevision && (
          <CardDescription className="text-orange-700 dark:text-orange-400">
            The shop needs updated files before this order can be printed.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {order.revision_note ? (
          <p className="whitespace-pre-wrap text-sm text-orange-800 dark:text-orange-300">
            {order.revision_note}
          </p>
        ) : (
          needsRevision && (
            <p className="text-sm text-orange-800 dark:text-orange-300">
              The shop asked you to replace the uploaded files. Use the
              Replace button on each file below, then submit them for
              review.
            </p>
          )
        )}
        {needsRevision && (
          <div className="space-y-2">
            <p className="text-xs text-orange-700 dark:text-orange-400">
              Files replaced: {revisedCount} of {order.files.length}
            </p>
            <Button
              className="w-full"
              onClick={() => resubmitMutation.mutate()}
              disabled={!hasRevisedFiles || resubmitMutation.isPending}
            >
              {resubmitMutation.isPending && (
                <Loader2
                  className="mr-2 h-4 w-4 animate-spin"
                  aria-hidden="true"
                />
              )}
              {resubmitMutation.isPending
                ? "Resubmitting…"
                : "Submit revised files for review"}
            </Button>
            {!hasRevisedFiles && (
              <p className="text-xs text-orange-700 dark:text-orange-400">
                Replace at least one file (each upload is kept as a new
                version), then send the order back for review.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  ) : null;

  return (
    <div className="space-y-6">
      {justCreated && !bannerDismissed && (
        <Card className="border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/40">
          <CardHeader className="flex-row items-start justify-between space-y-0 pb-3">
            <CardTitle className="flex items-center gap-2 text-green-800 dark:text-green-300">
              <CheckCircle2 className="h-5 w-5 shrink-0" aria-hidden="true" />{" "}
              Order placed successfully!
            </CardTitle>
            <Button
              variant="ghost"
              size="icon"
              className="-mr-2 -mt-2 h-8 w-8 text-green-800 hover:bg-green-100 dark:text-green-300 dark:hover:bg-green-900/50"
              onClick={() => setBannerDismissed(true)}
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-green-700 dark:text-green-400">
            <p>
              Your tracking ID is{" "}
              <strong className="font-mono tracking-wider">
                {order.tracking_id}
              </strong>{" "}
              — save it or copy it; you&apos;ll need it to follow your order.
            </p>
            <p>
              Next step: complete your payment (or choose pay upon pickup), then
              our staff reviews your job before it goes to the printer.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button size="sm" variant="outline" onClick={copyTrackingId}>
                <Copy className="mr-2 h-4 w-4" aria-hidden="true" /> Copy
                tracking ID
              </Button>
              {user && (
                <Button asChild size="sm" variant="outline">
                  <Link to="/orders">View my orders</Link>
                </Button>
              )}
              <Button asChild size="sm" variant="outline">
                <Link to="/track">Track later</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        <Link
          to={user ? "/orders" : "/track"}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          {user ? "My orders" : "Track an order"}
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1">
              <h1 className="truncate text-2xl font-bold tracking-wide">
                {order.tracking_id}
              </h1>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 text-muted-foreground"
                onClick={copyTrackingId}
                aria-label="Copy tracking ID"
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {order.client_name} · Submitted {dateTime(order.created_at)}
            </p>
          </div>
          <StatusBadge status={order.status} display={order.status_display} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        {/* On phones this comes first: payment and revisions are the things to act on. */}
        <aside className="order-first space-y-6 lg:sticky lg:top-20 lg:order-none">
          {needsRevision && revisionCard}

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">Payment</CardTitle>
                {paidInFull && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800 dark:bg-green-950 dark:text-green-300">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />{" "}
                    Paid in full
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="space-y-2 text-sm">
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-muted-foreground">Total</dt>
                  <dd className="font-medium">{peso(order.subtotal_peso)}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-muted-foreground">Paid</dt>
                  <dd className="font-medium">
                    {peso(order.amount_paid_peso)}
                  </dd>
                </div>
                <Separator />
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="font-medium">Balance</dt>
                  <dd className="text-2xl font-bold">
                    {peso(order.balance_due_peso)}
                  </dd>
                </div>
              </dl>

              <div
                role="progressbar"
                aria-label="Amount paid"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={paidPct}
                className="h-1.5 overflow-hidden rounded-full bg-muted"
              >
                <div
                  className="h-full bg-primary transition-[width]"
                  style={{ width: `${paidPct}%` }}
                />
              </div>

              {order.payment_method === "pickup" &&
                order.balance_due_peso > 0 && (
                  <div className="flex gap-2 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300">
                    <Info
                      className="mt-0.5 h-4 w-4 shrink-0"
                      aria-hidden="true"
                    />
                    <p>
                      You chose to <strong>pay upon pickup</strong> — bring{" "}
                      {peso(order.balance_due_peso)} when you collect your
                      printout.
                    </p>
                  </div>
                )}

              {canPay && (
                <Button
                  className="w-full"
                  onClick={() => setShowCheckout(true)}
                >
                  <QrCode className="mr-2 h-4 w-4" aria-hidden="true" /> Pay now
                  — {peso(order.subtotal_peso)}
                </Button>
              )}
            </CardContent>
          </Card>
        </aside>

        <div className="space-y-6">
          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2 space-y-0">
              <CardTitle>Files ({order.files.length})</CardTitle>
              <span className="text-xs text-muted-foreground">
                {needsRevision
                  ? "Replace the files the shop asked you to change"
                  : "Tap preview to check what you uploaded"}
              </span>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {order.files.map((f) => {
                  const replacing =
                    reuploadMutation.isPending && reuploadFile?.id === f.id;
                  return (
                    <li
                      key={f.id}
                      className="flex flex-col gap-3 rounded-md bg-muted/50 px-3 py-2.5 text-sm sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <FileText
                          className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <div className="min-w-0">
                          <p className="truncate font-medium">
                            {f.file_name}
                            {(f.current_version ?? 1) > 1 && (
                              <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                                v{f.current_version}
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {f.page_count} page{f.page_count === 1 ? "" : "s"} ·{" "}
                            {f.file_type}
                            {f.has_edits && " · edited"}
                            {(f.versions?.length ?? 0) > 0 && (
                              <> · {f.versions.length + 1} versions</>
                            )}
                          </p>
                          {(f.versions?.length ?? 0) > 0 && (
                            <p className="mt-0.5 flex items-start gap-1 text-xs text-muted-foreground">
                              <History
                                className="mt-0.5 h-3 w-3 shrink-0"
                                aria-hidden="true"
                              />
                              <span>
                                {[...f.versions]
                                  .reverse()
                                  .map((v) => v.version_label)
                                  .join(" → ")}
                                {" → "}v{f.current_version} (current)
                              </span>
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 pl-8 sm:pl-0">
                        {needsRevision && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={reuploadMutation.isPending}
                            aria-label={`Replace ${f.file_name}`}
                            onClick={() => {
                              setReuploadFile(f);
                              // One tick later so the target file is already in state
                              // when the picker resolves.
                              setTimeout(
                                () => reuploadInput.current?.click(),
                                0,
                              );
                            }}
                          >
                            {replacing ? (
                              <Loader2
                                className="mr-2 h-4 w-4 animate-spin"
                                aria-hidden="true"
                              />
                            ) : (
                              <FileUp
                                className="mr-2 h-4 w-4"
                                aria-hidden="true"
                              />
                            )}
                            {replacing ? "Uploading…" : "Replace"}
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          aria-label={`Preview ${f.file_name}`}
                          onClick={() => setPreviewFile(f)}
                        >
                          <Eye className="mr-2 h-4 w-4" aria-hidden="true" />{" "}
                          Preview
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
              {/* One shared picker: the Replace button records which file it targets,
                  then opens this input. Accepts what the create endpoint accepts
                  (PREVIEWABLE_EXTENSIONS) so nothing offered here is rejected. */}
              <input
                ref={reuploadInput}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.jpg,.jpeg,.png,.webp"
                onChange={(e) => {
                  const picked = e.target.files?.[0];
                  e.target.value = "";
                  if (picked && reuploadFile)
                    reuploadMutation.mutate({
                      file: reuploadFile,
                      upload: picked,
                    });
                  else setReuploadFile(null);
                }}
              />
            </CardContent>
          </Card>

          {/* When it's not the customer's move, the note is background, so it sits with the history. */}
          {!needsRevision && revisionCard}

          {order.payments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Payments</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {order.payments.map((p) => (
                    <li
                      key={p.id}
                      className="flex items-center justify-between gap-3 rounded-md bg-muted/50 px-3 py-2.5"
                    >
                      <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2">
                          <span className="font-medium capitalize">
                            {p.method === "qrph" ? "QR Ph" : p.method}
                          </span>
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                              paymentChipClass(p.status),
                            )}
                          >
                            {p.status}
                          </span>
                        </p>
                        {p.paid_at && (
                          <p className="text-xs text-muted-foreground">
                            Paid {dateTime(p.paid_at)}
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 font-medium">
                        {peso(p.amount / 100)}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Status history</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="relative space-y-5 border-l pl-6">
                {order.history.map((h) => (
                  <li key={h.id} className="relative">
                    <span
                      aria-hidden="true"
                      className="absolute -left-[1.85rem] top-1.5 h-3 w-3 rounded-full border-2 border-background bg-muted-foreground/50"
                    />
                    <StatusBadge
                      status={h.to_status}
                      display={h.to_status_display}
                    />
                    {h.note && <p className="mt-1.5 text-sm">{h.note}</p>}
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {dateTime(h.created_at)}
                    </p>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog
        open={showCheckout}
        onOpenChange={(open) => {
          setShowCheckout(open);
          if (!open) setQrResult(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {qrResult ? "Scan to pay with QR Ph" : "Choose how to pay"}
            </DialogTitle>
            <DialogDescription className={qrResult ? "sr-only" : undefined}>
              {qrResult
                ? "Scan the code with your bank or e-wallet app."
                : "Pay online now via QR Ph, or settle the balance when you pick up your printout."}
            </DialogDescription>
          </DialogHeader>

          {qrResult ? (
            <div className="space-y-4 text-center">
              {qrResult.qr_image_url ? (
                <img
                  src={qrResult.qr_image_url}
                  alt="QR Ph payment code"
                  className="mx-auto h-56 w-56 rounded-md border bg-white object-contain"
                />
              ) : (
                <div className="mx-auto flex h-56 w-56 items-center justify-center rounded-md border bg-muted">
                  <QrCode
                    className="h-16 w-16 text-muted-foreground"
                    aria-hidden="true"
                  />
                </div>
              )}
              <div>
                <p className="text-3xl font-bold">
                  {peso(qrResult.amount_peso ?? 0)}
                </p>
                {qrResult.expires_at && (
                  <p className="text-sm text-muted-foreground">
                    Expires{" "}
                    {new Date(qrResult.expires_at).toLocaleTimeString(
                      undefined,
                      { timeStyle: "short" },
                    )}
                  </p>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                Open your bank or e-wallet app, scan the code, and confirm the
                payment. This page refreshes automatically.
              </p>
              {!qrResult.mock_mode && (
                <p
                  className="flex items-center justify-center gap-2 text-sm text-muted-foreground"
                  role="status"
                >
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />{" "}
                  Waiting for your payment…
                </p>
              )}
              <Separator />
              {qrResult.mock_mode ? (
                <Button
                  className="w-full"
                  onClick={() =>
                    qrResult.payment_id &&
                    simulateMutation.mutate(qrResult.payment_id)
                  }
                  disabled={simulateMutation.isPending}
                >
                  {simulateMutation.isPending ? (
                    <Loader2
                      className="mr-2 h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                  ) : (
                    <Wallet className="mr-2 h-4 w-4" aria-hidden="true" />
                  )}
                  {simulateMutation.isPending
                    ? "Confirming…"
                    : "Simulate successful payment (mock mode)"}
                </Button>
              ) : (
                <Button
                  className="w-full"
                  variant="outline"
                  onClick={() => refetch()}
                >
                  I&apos;ve paid — check status
                </Button>
              )}
              <Button
                className="w-full"
                variant="ghost"
                onClick={() => setQrResult(null)}
                disabled={simulateMutation.isPending}
              >
                Back to payment options
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <Button
                className="h-auto w-full justify-between px-4 py-3"
                onClick={() =>
                  checkoutMutation.mutate({
                    method: "qrph",
                    payment_type: "full",
                  })
                }
                disabled={checkoutMutation.isPending}
              >
                <span className="flex items-center gap-2">
                  {checkoutMutation.isPending &&
                    checkoutMutation.variables?.payment_type === "full" && (
                      <Loader2
                        className="h-4 w-4 animate-spin"
                        aria-hidden="true"
                      />
                    )}
                  Pay in full
                </span>
                <span className="font-bold">{peso(order.subtotal_peso)}</span>
              </Button>
              <Button
                className="h-auto w-full justify-between px-4 py-3"
                variant="outline"
                onClick={() =>
                  checkoutMutation.mutate({
                    method: "qrph",
                    payment_type: "partial",
                  })
                }
                disabled={checkoutMutation.isPending}
              >
                <span className="flex items-center gap-2">
                  {checkoutMutation.isPending &&
                    checkoutMutation.variables?.payment_type === "partial" && (
                      <Loader2
                        className="h-4 w-4 animate-spin"
                        aria-hidden="true"
                      />
                    )}
                  Pay down payment
                </span>
                <span className="font-bold">
                  {peso(order.min_partial_peso)}
                </span>
              </Button>
              {allowPickup && (
                <>
                  <Separator />
                  <Button
                    className="h-auto w-full justify-between px-4 py-3"
                    variant="secondary"
                    onClick={() =>
                      checkoutMutation.mutate({ method: "pickup" })
                    }
                    disabled={checkoutMutation.isPending}
                  >
                    <span className="flex items-center gap-2">
                      {checkoutMutation.isPending &&
                      checkoutMutation.variables?.method === "pickup" ? (
                        <Loader2
                          className="h-4 w-4 animate-spin"
                          aria-hidden="true"
                        />
                      ) : (
                        <Wallet className="h-4 w-4" aria-hidden="true" />
                      )}
                      Pay upon pickup
                    </span>
                    <span className="font-bold">
                      {peso(order.balance_due_peso)}
                    </span>
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    No payment now. Pay cash or scan the shop&apos;s QR Ph when
                    you collect your order.
                  </p>
                </>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <FilePreviewDialog
        file={previewFile}
        orderId={Number(id)}
        trackingId={guestRef?.tracking_id}
        onClose={() => setPreviewFile(null)}
      />
    </div>
  );
}
