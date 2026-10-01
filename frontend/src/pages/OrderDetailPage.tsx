import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { Copy, QrCode } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { api, apiErrorMessage } from "@/lib/api";
import type { Order } from "@/lib/types";
import { useState } from "react";

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [showCheckout, setShowCheckout] = useState(false);

  const { data: order, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: async () => {
      const { data } = await api.get<Order>(`/orders/${id}/`);
      return data;
    },
  });

  const checkoutMutation = useMutation({
    mutationFn: async (paymentType: "full" | "partial") => {
      const { data } = await api.post("/payments/checkout/", { order_id: id, payment_type: paymentType });
      return data;
    },
    onSuccess: () => {
      toast.success("Checkout created!");
      queryClient.invalidateQueries({ queryKey: ["order", id] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (!order) return <p>Order not found.</p>;

  const canPay = order.status === "draft" || order.status === "awaiting_payment";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{order.tracking_id}</h1>
          <p className="text-sm text-muted-foreground">Submitted {new Date(order.created_at).toLocaleString()}</p>
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

      <Card>
        <CardHeader><CardTitle>Files</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {order.files.map((f) => (
              <li key={f.id} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm">
                <div>
                  <p className="font-medium">{f.file_name}</p>
                  <p className="text-xs text-muted-foreground">{f.page_count} page(s) · {f.file_type}</p>
                </div>
                {f.has_edits && <span className="text-xs text-blue-600">edited</span>}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {order.revision_note && (
        <Card className="border-orange-200 bg-orange-50">
          <CardHeader><CardTitle className="text-orange-800">Revision requested</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-orange-700">{order.revision_note}</p></CardContent>
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

      {canPay && order.balance_due_peso > 0 && (
        <div className="flex gap-3">
          <Button onClick={() => setShowCheckout(true)}>
            <QrCode className="mr-2 h-4 w-4" /> Pay now
          </Button>
          <Button variant="outline" onClick={() => {
            navigator.clipboard.writeText(order.tracking_id);
            toast.success("Tracking ID copied!");
          }}>
            <Copy className="mr-2 h-4 w-4" /> Copy tracking ID
          </Button>
        </div>
      )}

      <Dialog open={showCheckout} onOpenChange={setShowCheckout}>
        <DialogContent>
          <DialogHeader><DialogTitle>Complete your payment</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Scan the QR Ph code with your bank or e-wallet app.</p>
            {order.payments.filter((p) => p.status === "pending").map((p) => (
              <div key={p.id} className="text-center">
                <div className="mx-auto mb-2 flex h-48 w-48 items-center justify-center rounded-md border bg-muted">
                  <QrCode className="h-16 w-16 text-muted-foreground" />
                </div>
                <p className="text-sm">Amount: ₱{(p.amount / 100).toFixed(2)}</p>
              </div>
            ))}
            <Separator />
            <div className="space-y-2">
              <p className="text-sm font-medium">Create checkout:</p>
              <div className="flex gap-2">
                <Button className="flex-1" onClick={() => checkoutMutation.mutate("full")} disabled={checkoutMutation.isPending}>
                  Pay full ₱{order.subtotal_peso.toFixed(2)}
                </Button>
                <Button variant="outline" className="flex-1" onClick={() => checkoutMutation.mutate("partial")} disabled={checkoutMutation.isPending}>
                  Pay partial
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
