import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { Textarea } from "@/components/ui/textarea";
import { api, apiErrorMessage } from "@/lib/api";
import type { Order } from "@/lib/types";

type AdminAction = "approve" | "reject" | "request_revision" | "hold" | "resolve_hold" | "ready" | "complete" | "cancel";

const ACTION_LABELS: Record<AdminAction, string> = {
  approve: "Approve & Queue",
  reject: "Reject",
  request_revision: "Request Revision",
  hold: "Put On Hold",
  resolve_hold: "Resolve Hold",
  ready: "Mark Ready for Pickup",
  complete: "Mark Completed",
  cancel: "Cancel Order",
};

export default function AdminOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [confirmAction, setConfirmAction] = useState<AdminAction | null>(null);

  const { data: order, isLoading } = useQuery({
    queryKey: ["admin-order", id],
    queryFn: async () => {
      const { data } = await api.get<Order>(`/admin/orders/${id}/`);
      return data;
    },
  });

  const actionMutation = useMutation({
    mutationFn: async (action: AdminAction) => {
      const { data } = await api.post<Order>(`/admin/orders/${id}/actions/${action}/`, { note });
      return data;
    },
    onSuccess: () => {
      toast.success("Order updated.");
      setNote("");
      setConfirmAction(null);
      queryClient.invalidateQueries({ queryKey: ["admin-order", id] });
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (isLoading || !order) return <Skeleton className="h-96 w-full" />;

  const availableActions: AdminAction[] = (() => {
    switch (order.status) {
      case "pending_review": return ["approve", "reject", "request_revision"];
      case "approved_queued": return ["hold", "cancel"];
      case "on_hold": return ["resolve_hold", "cancel"];
      case "printing": return ["hold", "ready"];
      case "printed_ready": return ["complete"];
      case "revision_requested": return ["cancel"];
      default: return [];
    }
  })();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{order.tracking_id}</h1>
          <p className="text-sm text-muted-foreground">
            {order.client_name} · {order.guest_contact_value || "—"} · {new Date(order.created_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={order.status} display={order.status_display} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Total</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">₱{order.subtotal_peso.toFixed(2)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Paid</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">₱{order.amount_paid_peso.toFixed(2)}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Balance</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-bold">₱{order.balance_due_peso.toFixed(2)}</p></CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Files ({order.files.length})</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {order.files.map((f) => (
              <li key={f.id} className="rounded-md bg-muted/50 px-3 py-2 text-sm">
                <p className="font-medium">{f.file_name} <span className="text-muted-foreground">({f.page_count} pg)</span></p>
                {f.specification && (
                  <p className="text-xs text-muted-foreground">
                    {f.specification.media_size}/{f.specification.media_type} · {f.specification.color_mode} · {f.specification.sides} · {f.specification.copies} copy
                  </p>
                )}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {order.revision_note && (
        <Card className="border-orange-200 bg-orange-50">
          <CardHeader><CardTitle className="text-sm text-orange-800">Revision note</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-orange-700">{order.revision_note}</p></CardContent>
        </Card>
      )}

      {order.admin_notes && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Internal notes</CardTitle></CardHeader>
          <CardContent><p className="text-sm text-muted-foreground">{order.admin_notes}</p></CardContent>
        </Card>
      )}

      {order.print_jobs && order.print_jobs.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Print jobs</CardTitle></CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {order.print_jobs.map((j) => (
                <li key={j.id} className="flex justify-between">
                  <span>{j.file_name || j.epson_job_id}</span>
                  <span className="text-muted-foreground">{j.epson_status || j.status}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">Status history</CardTitle></CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {order.history.map((h) => (
              <li key={h.id} className="flex items-start gap-2 text-sm">
                <StatusBadge status={h.to_status} display={h.to_status_display} />
                <div>
                  <p>{h.note || "—"}</p>
                  <p className="text-xs text-muted-foreground">{new Date(h.created_at).toLocaleString()}</p>
                </div>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {availableActions.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Actions</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="note">Note (optional)</Label>
                <Textarea
                  id="note"
                  placeholder="Internal note or message to the client (for revision requests)"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                {availableActions.map((action) => (
                  <Button
                    key={action}
                    variant={action === "reject" || action === "cancel" ? "destructive" : "default"}
                    onClick={() => setConfirmAction(action)}
                  >
                    {ACTION_LABELS[action]}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={!!confirmAction} onOpenChange={() => setConfirmAction(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Confirm: {confirmAction && ACTION_LABELS[confirmAction]}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              This will change the order status to "{confirmAction?.replace("_", " ")}".
              {note && <span className="mt-1 block">Note: {note}</span>}
            </p>
            <Separator />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmAction(null)}>Cancel</Button>
              <Button onClick={() => confirmAction && actionMutation.mutate(confirmAction)} disabled={actionMutation.isPending}>
                Confirm
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
