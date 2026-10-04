import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, Copy, Eye, FileUp, History, LogIn, QrCode, Wallet } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import FilePreviewDialog from "@/components/FilePreviewDialog";
import { useAuth } from "@/components/auth";
import { api, apiErrorMessage, loadGuestOrders } from "@/lib/api";
import type { CheckoutResponse, Order, OrderFile, ShopPaymentSettings } from "@/lib/types";

interface CreatedState {
  justCreated?: boolean;
  trackingId?: string;
}

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const location = useLocation();
  const queryClient = useQueryClient();
  const justCreated = Boolean((location.state as CreatedState | null)?.justCreated);

  const [showCheckout, setShowCheckout] = useState(false);
  const [qrResult, setQrResult] = useState<CheckoutResponse | null>(null);
  const [previewFile, setPreviewFile] = useState<OrderFile | null>(null);
  const [reuploadFile, setReuploadFile] = useState<OrderFile | null>(null);
  const reuploadInput = useRef<HTMLInputElement>(null);

  // Orders placed without an account are proven by their tracking ID, which
  // is stored on this device right after checkout (see NewOrderPage).
  const guestRef = !user ? loadGuestOrders().find((o) => String(o.id) === id) : undefined;
  const canView = Boolean(user || guestRef);

  const { data: order, isLoading, isError, refetch } = useQuery({
    queryKey: ["order", id, user ? "auth" : `guest:${guestRef?.tracking_id ?? ""}`],
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
    queryFn: async () => (await api.get<ShopPaymentSettings>("/payments/settings/")).data,
  });

  const checkoutMutation = useMutation({
    mutationFn: async (payload: { method: "qrph" | "pickup"; payment_type?: "full" | "partial" }) => {
      const { data } = await api.post<CheckoutResponse>("/payments/checkout/", {
        order_id: Number(id),
        method: payload.method,
        ...(payload.method === "qrph" ? { payment_type: payload.payment_type } : {}),
      });
      return data;
    },
    onSuccess: (data) => {
      if (data.method === "pickup") {
        toast.success("Pay upon pickup selected — settle the balance when you collect your order.");
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
      (await api.post("/payments/webhook/simulate/", { payment_id: paymentId })).data,
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
      if (guestRef?.tracking_id) body.append("tracking_id", guestRef.tracking_id);
      const { data } = await api.post<Order>(
        `/orders/${id}/files/${file.id}/reupload/`, body);
      return data;
    },
    // Read the target from the mutation variables (not state) so the toast
    // always names the file that was actually replaced.
    onSuccess: (data, variables) => {
      const updated = data.files.find((f) => f.id === variables.file.id);
      toast.success(updated
        ? `Uploaded v${updated.current_version} of ${updated.file_name}.`
        : "Revised file uploaded.");
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
      const { data } = await api.post<Order>(`/orders/${id}/resubmit/`,
        guestRef?.tracking_id ? { tracking_id: guestRef.tracking_id } : {});
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
  const payable = order?.status === "draft" || order?.status === "awaiting_payment";
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
            This order was not placed from this device, so we need to confirm it belongs to you.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Button asChild className="flex-1">
            <Link to="/login"><LogIn className="mr-2 h-4 w-4" /> Log in</Link>
          </Button>
          <Button asChild variant="outline" className="flex-1">
            <Link to="/track">Track with tracking ID</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError || !order) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader><CardTitle>Order not available</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            We couldn't load this order. It may belong to a different account.
          </p>
          <Button asChild variant="outline"><Link to="/track">Track an order</Link></Button>
        </CardContent>
      </Card>
    );
  }

  const canPay = payable && order.balance_due_peso > 0;
  const allowPickup = settingsQuery.data?.allow_pay_on_pickup ?? false;
  const needsRevision = order?.status === "revision_requested";
  // At least one file already replaced (v2+) — mirrors the server rule so
  // the customer cannot bounce an untouched order back into the queue.
  const hasRevisedFiles = Boolean(order?.files.some((f) => (f.current_version ?? 1) > 1));

  function copyTrackingId() {
    navigator.clipboard.writeText(order!.tracking_id);
    toast.success("Tracking ID copied!");
  }

  return (
    <div className="space-y-6">
      {justCreated && (
        <Card className="border-green-200 bg-green-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-800">
              <CheckCircle2 className="h-5 w-5" /> Order placed successfully!
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-green-700">
            <p>
              Your tracking ID is <strong className="tracking-wider">{order.tracking_id}</strong> —
              save it or copy it; you'll need it to follow your order.
            </p>
            <p>
              Next step: complete your payment (or choose pay upon pickup), then our staff reviews
              your job before it goes to the printer.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button size="sm" variant="outline" onClick={copyTrackingId}>
                <Copy className="mr-2 h-4 w-4" /> Copy tracking ID
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/orders">View My Orders</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/track">Track later</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{order.tracking_id}</h1>
          <p className="text-sm text-muted-foreground">
            {order.client_name} · Submitted {new Date(order.created_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={order.status} display={order.status_display} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Total</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">₱{order.subtotal_peso.toFixed(2)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Paid</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">₱{order.amount_paid_peso.toFixed(2)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Balance</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">₱{order.balance_due_peso.toFixed(2)}</p></CardContent>
        </Card>
      </div>

      {order.payment_method === "pickup" && order.balance_due_peso > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6 text-sm text-blue-800">
            You chose to <strong>pay upon pickup</strong> — bring ₱{order.balance_due_peso.toFixed(2)}{" "}
            when you collect your printout.
          </CardContent>
        </Card>
      )}

      {order.payments.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Payments</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {order.payments.map((p) => (
                <li key={p.id} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2">
                  <span className="capitalize">
                    {p.method === "qrph" ? "QR Ph" : p.method} · {p.status}
                    {p.paid_at && ` · paid ${new Date(p.paid_at).toLocaleString()}`}
                  </span>
                  <span className="font-medium">₱{(p.amount / 100).toFixed(2)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>Files</CardTitle>
          <span className="text-xs text-muted-foreground">
            Tap preview to check what you uploaded
          </span>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {order.files.map((f) => (
              <li key={f.id}
                className="flex items-center justify-between gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {f.file_name}
                    {(f.current_version ?? 1) > 1 && (
                      <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700">
                        v{f.current_version}
                      </span>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {f.page_count} page{f.page_count === 1 ? "" : "s"} · {f.file_type}
                    {f.has_edits && " · edited"}
                    {(f.versions?.length ?? 0) > 0 && (
                      <> · {f.versions.length + 1} versions</>
                    )}
                  </p>
                  {(f.versions?.length ?? 0) > 0 && (
                    <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                      <History className="h-3 w-3" />
                      {[...f.versions].reverse().map((v) => v.version_label).join(" → ")}
                      {" → "}v{f.current_version} (current)
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {needsRevision && (
                    <Button variant="outline" size="sm"
                      disabled={reuploadMutation.isPending}
                      onClick={() => {
                        setReuploadFile(f);
                        // One tick later so the target file is already in state
                        // when the picker resolves.
                        setTimeout(() => reuploadInput.current?.click(), 0);
                      }}>
                      <FileUp className="mr-2 h-4 w-4" /> Replace
                    </Button>
                  )}
                  <Button variant="outline" size="sm"
                    onClick={() => setPreviewFile(f)}>
                    <Eye className="mr-2 h-4 w-4" /> Preview
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          {/* One shared picker: the Replace button records which file it targets,
              then opens this input. Accepts what the create endpoint accepts
              (PREVIEWABLE_EXTENSIONS) so nothing offered here is rejected. */}
          <input ref={reuploadInput} type="file" className="hidden"
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv,.jpg,.jpeg,.png,.webp"
            onChange={(e) => {
              const picked = e.target.files?.[0];
              e.target.value = "";
              if (picked && reuploadFile) reuploadMutation.mutate({ file: reuploadFile, upload: picked });
              else setReuploadFile(null);
            }} />
        </CardContent>
      </Card>


      {order.revision_note && (
        <Card className="border-orange-200 bg-orange-50">
          <CardHeader><CardTitle className="text-orange-800">Revision requested</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-orange-700">{order.revision_note}</p>
            {needsRevision && (
              <div className="flex flex-col gap-2">
                <Button
                  onClick={() => resubmitMutation.mutate()}
                  disabled={!hasRevisedFiles || resubmitMutation.isPending}
                >
                  {resubmitMutation.isPending ? "Resubmitting…" : "Submit revised files for review"}
                </Button>
                {!hasRevisedFiles && (
                  <p className="text-xs text-orange-700">
                    Replace at least one file above (each upload is kept as a new version),
                    then send the order back for review.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Status history</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {order.history.map((h) => (
              <li key={h.id} className="flex items-start gap-3">
                <StatusBadge status={h.to_status} display={h.to_status_display} />
                <div>
                  <p className="text-sm">{h.note || "—"}</p>
                  <p className="text-xs text-muted-foreground">{new Date(h.created_at).toLocaleString()}</p>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-3">
        {canPay && (
          <Button onClick={() => setShowCheckout(true)}>
            <QrCode className="mr-2 h-4 w-4" /> Pay now — ₱{order.subtotal_peso.toFixed(2)}
          </Button>
        )}
        <Button variant="outline" onClick={copyTrackingId}>
          <Copy className="mr-2 h-4 w-4" /> Copy tracking ID
        </Button>
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
            <DialogTitle>{qrResult ? "Scan to pay with QR Ph" : "Choose how to pay"}</DialogTitle>
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
                  <QrCode className="h-16 w-16 text-muted-foreground" />
                </div>
              )}
              <p className="text-sm">
                Amount: <strong>₱{(qrResult.amount_peso ?? 0).toFixed(2)}</strong>
                {qrResult.expires_at && (
                  <span className="text-muted-foreground">
                    {" "}· expires {new Date(qrResult.expires_at).toLocaleTimeString()}
                  </span>
                )}
              </p>
              <p className="text-xs text-muted-foreground">
                Open your bank or e-wallet app, scan the code, and confirm the payment.
                This page refreshes automatically.
              </p>
              <Separator />
              {qrResult.mock_mode ? (
                <Button
                  className="w-full"
                  onClick={() => qrResult.payment_id && simulateMutation.mutate(qrResult.payment_id)}
                  disabled={simulateMutation.isPending}
                >
                  <Wallet className="mr-2 h-4 w-4" />
                  {simulateMutation.isPending ? "Confirming…" : "Simulate successful payment (mock mode)"}
                </Button>
              ) : (
                <Button className="w-full" variant="outline" onClick={() => refetch()}>
                  I've paid — check status
                </Button>
              )}
              <Button className="w-full" variant="ghost" onClick={() => setQrResult(null)}>
                Back to payment options
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Pay online now via QR Ph, or settle the balance when you pick up your printout.
              </p>
              <Button
                className="w-full"
                onClick={() => checkoutMutation.mutate({ method: "qrph", payment_type: "full" })}
                disabled={checkoutMutation.isPending}
              >
                Pay in full — ₱{order.subtotal_peso.toFixed(2)}
              </Button>
              <Button
                className="w-full"
                variant="outline"
                onClick={() => checkoutMutation.mutate({ method: "qrph", payment_type: "partial" })}
                disabled={checkoutMutation.isPending}
              >
                Pay down payment — ₱{order.min_partial_peso.toFixed(2)}
              </Button>
              {allowPickup && (
                <>
                  <Separator />
                  <Button
                    className="w-full"
                    variant="secondary"
                    onClick={() => checkoutMutation.mutate({ method: "pickup" })}
                    disabled={checkoutMutation.isPending}
                  >
                    <Wallet className="mr-2 h-4 w-4" /> Pay upon pickup — ₱{order.balance_due_peso.toFixed(2)}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    No payment now. Pay cash or scan the shop's QR Ph when you collect your order.
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

