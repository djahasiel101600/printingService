import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowLeft, Copy, Printer, Save, Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/components/auth";
import FilePreviewDialog from "@/components/FilePreviewDialog";
import FileReviewCard from "@/components/FileReviewCard";
import { Textarea } from "@/components/ui/textarea";
import { printJobStatusLabel, printJobStatusStyle } from "@/lib/constants";
import { api, apiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Order, OrderFile, PrintJob } from "@/lib/types";

type AdminAction =
  | "approve" | "reject" | "request_revision" | "hold" | "resolve_hold"
  | "ready" | "complete" | "cancel" | "record_payment" | "reprint";

const ACTION_LABELS: Record<AdminAction, string> = {
  approve: "Approve & Queue",
  reject: "Reject",
  request_revision: "Request Revision",
  hold: "Put On Hold",
  resolve_hold: "Resolve Hold",
  ready: "Mark Ready for Pickup",
  complete: "Mark Completed",
  cancel: "Cancel Order",
  record_payment: "Record Payment",
  reprint: "Reprint",
};

const DESTRUCTIVE: AdminAction[] = ["reject", "cancel"];

/** Actions the shop can take from each status (mirrors the API's ALLOWED map). */
function availableActions(status: Order["status"]): AdminAction[] {
  switch (status) {
    case "draft": return ["cancel"];
    case "awaiting_payment": return ["reject", "cancel"];
    case "pending_review": return ["approve", "reject", "request_revision"];
    case "approved_queued": return ["hold", "reprint", "cancel"];
    case "on_hold": return ["resolve_hold", "reprint", "cancel"];
    case "printing": return ["hold", "ready"];
    case "printed_ready": return ["complete", "reprint"];
    case "print_cancelled": return ["reprint", "ready", "reject"];
    case "revision_requested": return ["cancel"];
    case "completed": return ["reprint"];
    default: return [];
  }
}

export default function AdminOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [confirmAction, setConfirmAction] = useState<AdminAction | null>(null);
  const [previewFile, setPreviewFile] = useState<OrderFile | null>(null);
  const [notes, setNotes] = useState("");
  const [reprintTarget, setReprintTarget] = useState<OrderFile | "all" | null>(null);

  const { data: order, isLoading } = useQuery({
    queryKey: ["admin-order", id],
    queryFn: async () => (await api.get<Order>(`/admin/orders/${id}/`)).data,
  });

  useEffect(() => {
    if (order) setNotes(order.admin_notes ?? "");
  }, [order?.id, order?.admin_notes]);

  const actionMutation = useMutation({
    mutationFn: async (payload: { action: AdminAction; extra?: Record<string, unknown> }) =>
      (await api.post<Order>(`/admin/orders/${id}/actions/${payload.action}/`,
        { note, ...(payload.extra ?? {}) })).data,
    onSuccess: (data, variables) => {
      toast.success(variables.action === "reprint"
        ? `Reprint #${data.reprint_count} sent to the printer.`
        : "Order updated.");
      setNote("");
      setConfirmAction(null);
      setReprintTarget(null);
      queryClient.setQueryData(["admin-order", id], data);
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const notesMutation = useMutation({
    mutationFn: async () =>
      (await api.patch<Order>(`/admin/orders/${id}/notes/`, { admin_notes: notes })).data,
    onSuccess: (data) => {
      toast.success("Internal notes saved.");
      queryClient.setQueryData(["admin-order", id], data);
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (isLoading || !order) return <Skeleton className="h-96 w-full" />;

const actions = availableActions(order.status);
  // Approvers work the print queue, but cancelling an order (which refunds)
  // and recording cash are owner-only — mirrors the API's guard.
  const visibleActions = user?.is_shop_admin
    ? actions
    : actions.filter((action) => action !== "cancel" && action !== "record_payment");
  const printerCancelled = order.status === "print_cancelled";
  const unprintable = order.files.filter((f) => !f.print_ready);
  const jobs = order.print_jobs ?? [];
  const printerCancelledJobs = jobs.filter((j) => j.is_printer_cancelled);
  const showRecordPayment =
    order.balance_due_peso > 0 && !["rejected", "cancelled"].includes(order.status);
  // Page selection stops being meaningful once the sheets are on the printer.
  const pagesLocked = ["printing", "printed_ready", "completed"].includes(order.status);

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1">
          <Link to="/admin"><ArrowLeft className="mr-2 h-4 w-4" /> All orders</Link>
        </Button>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">{order.tracking_id}</h1>
          <StatusBadge status={order.status} display={order.status_display} />
          {order.reprint_count > 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Copy className="h-3 w-3" /> reprinted {order.reprint_count}×
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {order.client_name} · {new Date(order.created_at).toLocaleString()}
        </p>
      </div>

      {printerCancelled && (
        <div className="flex items-start gap-3 rounded-md border-2 border-amber-400 bg-amber-50 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div className="space-y-1 text-sm text-amber-900">
            <p className="font-medium">The printer cancelled this job — nothing was printed.</p>
            {printerCancelledJobs.map((job) => (
              <p key={job.id} className="text-xs">
                {job.file_name}: {job.error_message || "cancelled at the printer"}
              </p>
            ))}
            <p className="text-xs">
              Use <strong>Reprint</strong> to send it again — the customer keeps their
              place in the queue either way.
            </p>
          </div>
        </div>
      )}

      {unprintable.length > 0 && (
        <div className="flex items-start gap-3 rounded-md border-2 border-amber-400 bg-amber-50 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div className="space-y-1 text-sm text-amber-900">
            <p className="font-medium">
              {unprintable.length} file(s) cannot be sent to the printer
            </p>
            <p className="text-xs">
              {unprintable.map((f) => f.file_name).join(", ")} — preview them below to check
              the content, then upload the converted PDF. Approval is blocked until then.
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        {/* ------------------------------------------------ review column */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="text-sm">Files to review ({order.files.length})</CardTitle>
              <p className="text-xs text-muted-foreground">
                Preview each file, then choose the pages to print
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {order.files.map((file) => (
                <FileReviewCard key={file.id} order={order} file={file}
                  onPreview={setPreviewFile} locked={pagesLocked} />
              ))}
            </CardContent>
          </Card>

{jobs.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-sm">Printer jobs</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {jobs.map((job) => (
                    <PrintJobRow key={job.id} job={job}
                      onReprint={() => setReprintTarget(
                        order.files.find((f) => f.id === job.order_file) ?? "all")} />
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
                    <StatusBadge status={h.to_status} display={h.to_status_display}
                      className="mt-0.5" />
                    <div>
                      <p>{h.note || "—"}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(h.created_at).toLocaleString()}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* ------------------------------------------------- side column */}
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="text-sm">Order summary</CardTitle></CardHeader>
            <CardContent className="space-y-1.5 text-sm">
              <Row label="Subtotal" value={`₱${order.subtotal_peso.toFixed(2)}`} />
              <Row label="Paid" value={`₱${order.amount_paid_peso.toFixed(2)}`} />
              <Row label="Balance" value={`₱${order.balance_due_peso.toFixed(2)}`}
                emphasis={order.balance_due_peso > 0} />
              <Separator className="my-2" />
              <Row label="Contact" value={order.guest_contact_value || "—"} />
              <Row label="Method" value={order.guest_contact_method || "—"} />
              <Row label="Payment" value={order.payment_method || "—"} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="text-sm">Internal notes</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => notesMutation.mutate()}
                disabled={notesMutation.isPending || notes === (order.admin_notes ?? "")}>
                <Save className="mr-2 h-4 w-4" /> Save
              </Button>
            </CardHeader>
            <CardContent>
              <Textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="Only the shop sees this." />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ------------------------------------------------------- actions */}
      <Card>
        <CardHeader><CardTitle className="text-sm">Actions</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="note">Note (optional)</Label>
            <Textarea id="note" rows={2} value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Internal note, or the message sent with a revision request" />
          </div>
          <div className="flex flex-wrap gap-2">
            {visibleActions.map((action) => (
              <Button key={action} size="sm"
                variant={DESTRUCTIVE.includes(action) ? "destructive"
                  : action === "reprint" ? "secondary" : "default"}
                onClick={() => (action === "reprint"
                  ? setReprintTarget("all")
                  : setConfirmAction(action))}>
                {action === "reprint" && <Printer className="mr-2 h-4 w-4" />}
                {action === "record_payment" && <Wallet className="mr-2 h-4 w-4" />}
                {ACTION_LABELS[action]}
              </Button>
            ))}
            {showRecordPayment && user?.is_shop_admin && !actions.includes("record_payment") && (
              <Button size="sm" variant="outline"
                onClick={() => setConfirmAction("record_payment")}>
                <Wallet className="mr-2 h-4 w-4" /> Record Payment
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <FilePreviewDialog file={previewFile} orderId={order.id} allowVariants
        onClose={() => setPreviewFile(null)} />

<Dialog open={!!confirmAction} onOpenChange={() => setConfirmAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Confirm: {confirmAction && ACTION_LABELS[confirmAction]}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {confirmAction === "approve"
                ? "This releases the job to the printer."
                : "This will change the order status."}
              {note && <span className="mt-1 block">Note: {note}</span>}
            </p>
            <Separator />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmAction(null)}>Cancel</Button>
              <Button
                variant={confirmAction && DESTRUCTIVE.includes(confirmAction) ? "destructive" : "default"}
                onClick={() => confirmAction &&
                  actionMutation.mutate({ action: confirmAction })}
                disabled={actionMutation.isPending}>
                Confirm
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reprint: whole order, or just the sheet that failed. */}
      <Dialog open={!!reprintTarget} onOpenChange={() => setReprintTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {reprintTarget === "all" ? "Reprint the whole order" : "Reprint this file"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {reprintTarget === "all"
                ? `All ${order.files.length} file(s) will be sent to the printer again. The previous run stays in the history.`
                : `Only “${reprintTarget?.file_name}” will be printed again. The pages you selected (${reprintTarget?.page_selection_label}) are kept.`}
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="reprint-note">Reason (optional)</Label>
              <Textarea id="reprint-note" rows={2} value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. printer cancelled the job, faded output, customer lost a copy" />
            </div>
            <Separator />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setReprintTarget(null)}>Cancel</Button>
              <Button
                onClick={() => actionMutation.mutate({
                  action: "reprint",
                  extra: reprintTarget !== "all" && reprintTarget
                    ? { file_id: reprintTarget.id } : {},
                })}
                disabled={actionMutation.isPending}>
                <Printer className="mr-2 h-4 w-4" /> Send to printer
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ label, value, emphasis }: {
  label: string; value: string; emphasis?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("tabular-nums", emphasis && "font-semibold")}>{value}</span>
    </div>
  );
}

function PrintJobRow({ job, onReprint }: { job: PrintJob; onReprint: () => void }) {
  return (
    <li className="rounded-md border p-2.5 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold",
            printJobStatusStyle(job.status))}>
            {printJobStatusLabel(job)}
          </span>
          <span className="truncate font-medium">{job.file_name || job.epson_job_id}</span>
          {job.is_reprint && (
            <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-800">
              reprint
            </span>
          )}
        </div>
        {job.is_printer_cancelled && (
          <Button variant="outline" size="sm" onClick={onReprint}>
            <Printer className="mr-2 h-3 w-4" /> Reprint
          </Button>
        )}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {job.pages_label} · {job.epson_status || job.status}
        {job.completed_at ? ` · finished ${new Date(job.completed_at).toLocaleString()}` : ""}
      </p>
      {job.error_message && (
        <p className="mt-1 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          {job.error_message}
        </p>
      )}
    </li>
  );
}