import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowLeft,
  Copy,
  Loader2,
  Printer,
  Save,
  Trash2,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/components/auth";
import FilePreviewDialog from "@/components/FilePreviewDialog";
import FileReviewCard from "@/components/FileReviewCard";
import OrderReceiptDialog from "@/components/OrderReceiptDialog";
import { Textarea } from "@/components/ui/textarea";
import { printJobStatusLabel, printJobStatusStyle } from "@/lib/constants";
import { api, apiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Order, OrderFile, PrintJob } from "@/lib/types";

type AdminAction =
  | "approve"
  | "reject"
  | "request_revision"
  | "hold"
  | "resolve_hold"
  | "ready"
  | "complete"
  | "cancel"
  | "record_payment"
  | "reprint";

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
    case "draft":
      return ["cancel"];
    case "awaiting_payment":
      return ["reject", "cancel"];
    case "pending_review":
      return ["approve", "reject", "request_revision"];
    case "approved_queued":
      return ["hold", "reprint", "cancel"];
    case "on_hold":
      return ["resolve_hold", "reprint", "cancel"];
    case "printing":
      return ["hold", "ready"];
    case "printed_ready":
      return ["complete", "reprint"];
    case "print_cancelled":
      return ["reprint", "ready", "reject"];
    case "revision_requested":
      return ["cancel"];
    case "completed":
      return ["reprint"];
    default:
      return [];
  }
}

const peso = (n: number) =>
  `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

const humanize = (s?: string | null) => (s ? s.replace(/_/g, " ") : "—");

export default function AdminOrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [confirmAction, setConfirmAction] = useState<AdminAction | null>(null);
  const [previewFile, setPreviewFile] = useState<OrderFile | null>(null);
  const [notes, setNotes] = useState("");
  const [reprintTarget, setReprintTarget] = useState<OrderFile | "all" | null>(
    null,
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showReceipt, setShowReceipt] = useState(false);

  const {
    data: order,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["admin-order", id],
    queryFn: async () => (await api.get<Order>(`/admin/orders/${id}/`)).data,
  });

  useEffect(() => {
    if (order) setNotes(order.admin_notes ?? "");
  }, [order?.id, order?.admin_notes]);

  const actionMutation = useMutation({
    mutationFn: async (payload: {
      action: AdminAction;
      extra?: Record<string, unknown>;
    }) =>
      (
        await api.post<Order>(
          `/admin/orders/${id}/actions/${payload.action}/`,
          { note, ...(payload.extra ?? {}) },
        )
      ).data,
    onSuccess: (data, variables) => {
      toast.success(
        variables.action === "reprint"
          ? `Reprint #${data.reprint_count} sent to the printer.`
          : "Order updated.",
      );
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
      (
        await api.patch<Order>(`/admin/orders/${id}/notes/`, {
          admin_notes: notes,
        })
      ).data,
    onSuccess: (data) => {
      toast.success("Internal notes saved.");
      queryClient.setQueryData(["admin-order", id], data);
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  // D of CRUD. The API restricts deletion to shop admins (mirrors cancel),
  // so the button only renders for them too.
  const deleteMutation = useMutation({
    mutationFn: async () => (await api.delete(`/admin/orders/${id}/`)).status,
    onSuccess: () => {
      toast.success("Order deleted.");
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
      navigate("/admin");
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  if (isLoading) return <DetailSkeleton />;

  if (isError || !order) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
          <AlertTriangle aria-hidden className="h-8 w-8 text-destructive" />
          <div className="space-y-1">
            <p className="font-medium">Couldn't load this order</p>
            <p className="text-sm text-muted-foreground">
              It may have been removed, or the connection dropped.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Try again
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link to="/admin">Back to orders</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const actions = availableActions(order.status);
  // Approvers work the print queue, but cancelling an order (which refunds)
  // and recording cash are owner-only — mirrors the API's guard.
  const visibleActions = user?.is_shop_admin
    ? actions
    : actions.filter(
        (action) => action !== "cancel" && action !== "record_payment",
      );
  const printerCancelled = order.status === "print_cancelled";
  const unprintable = order.files.filter((f) => !f.print_ready);
  const jobs = order.print_jobs ?? [];
  const printerCancelledJobs = jobs.filter((j) => j.is_printer_cancelled);
  const showRecordPayment =
    order.balance_due_peso > 0 &&
    !["rejected", "cancelled"].includes(order.status);
  // Page selection stops being meaningful once the sheets are on the printer.
  const pagesLocked = ["printing", "printed_ready", "completed"].includes(
    order.status,
  );

  // Group actions: safe ones first, destructive ones separated at the bottom.
  const mainActions: AdminAction[] = visibleActions.filter(
    (a) => !DESTRUCTIVE.includes(a),
  );
  if (
    showRecordPayment &&
    user?.is_shop_admin &&
    !actions.includes("record_payment")
  ) {
    mainActions.push("record_payment");
  }
  const destructiveActions = visibleActions.filter((a) =>
    DESTRUCTIVE.includes(a),
  );
  const primaryAction =
    mainActions.find((a) => a !== "reprint" && a !== "record_payment") ??
    mainActions[0];

  const reprintFile =
    reprintTarget && reprintTarget !== "all" ? reprintTarget : null;
  const notesDirty = notes !== (order.admin_notes ?? "");

  const runAction = (action: AdminAction) =>
    action === "reprint" ? setReprintTarget("all") : setConfirmAction(action);

  return (
    <div className="space-y-6">
      {/* ------------------------------------------------------ header */}
      <div className="space-y-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/admin">
            <ArrowLeft aria-hidden className="mr-2 h-4 w-4" /> All orders
          </Link>
        </Button>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-2xl font-bold tracking-tight">
            {order.tracking_id}
          </h1>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground"
            aria-label="Copy tracking ID"
            onClick={() => {
              navigator.clipboard
                ?.writeText(order.tracking_id)
                .then(() => toast.success("Tracking ID copied."))
                .catch(() => toast.error("Couldn't copy the tracking ID."));
            }}
          >
            <Copy className="h-4 w-4" />
          </Button>
          <StatusBadge status={order.status} display={order.status_display} />
          {order.reprint_count > 0 && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Printer aria-hidden className="h-3 w-3" /> Reprinted{" "}
              {order.reprint_count}×
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">
            {order.client_name}
          </span>
          {" · "}Placed{" "}
          <time dateTime={order.created_at}>
            {formatDate(order.created_at)}
          </time>
        </p>
      </div>

      {/* ------------------------------------------------------ alerts */}
      {printerCancelled && (
        <AlertBanner title="The printer cancelled this job — nothing was printed.">
          {printerCancelledJobs.map((job) => (
            <p key={job.id}>
              <span className="font-medium">{job.file_name}:</span>{" "}
              {job.error_message || "cancelled at the printer"}
            </p>
          ))}
          <p>
            Use <strong>Reprint</strong> to send it again. The customer keeps
            their place in the queue either way.
          </p>
        </AlertBanner>
      )}

      {unprintable.length > 0 && (
        <AlertBanner
          title={`${unprintable.length} file(s) cannot be sent to the printer`}
        >
          <p>
            {unprintable.map((f) => f.file_name).join(", ")}. Preview them below
            to check the content, then upload the converted PDF. Approval is
            blocked until then.
          </p>
        </AlertBanner>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        {/* ---------------------------------------------- review column */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="space-y-1">
              <CardTitle className="text-base">
                Files to review ({order.files.length})
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Preview each file, then choose the pages to print.
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {order.files.map((file) => (
                <FileReviewCard
                  key={file.id}
                  order={order}
                  file={file}
                  onPreview={setPreviewFile}
                  locked={pagesLocked}
                />
              ))}
            </CardContent>
          </Card>

          {jobs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Printer jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {jobs.map((job) => (
                    <PrintJobRow
                      key={job.id}
                      job={job}
                      onReprint={() =>
                        setReprintTarget(
                          order.files.find((f) => f.id === job.order_file) ??
                            "all",
                        )
                      }
                    />
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* ------------------------------------------------- side column
            Actions come first so the decision is next to the review, and on
            mobile they appear right after the files instead of at the very end. */}
        <div className="space-y-6 lg:sticky lg:top-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="note">Note (optional)</Label>
                <Textarea
                  id="note"
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Internal note, or the message sent with a revision request"
                />
              </div>

              {mainActions.length === 0 && destructiveActions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No actions are available while the order is{" "}
                  {order.status_display.toLowerCase()}.
                </p>
              ) : (
                <div className="space-y-2">
                  {mainActions.map((action) => (
                    <Button
                      key={action}
                      className="w-full justify-start"
                      variant={
                        action === primaryAction
                          ? "default"
                          : action === "reprint"
                            ? "secondary"
                            : "outline"
                      }
                      onClick={() => runAction(action)}
                    >
                      {action === "reprint" && (
                        <Printer aria-hidden className="mr-2 h-4 w-4" />
                      )}
                      {action === "record_payment" && (
                        <Wallet aria-hidden className="mr-2 h-4 w-4" />
                      )}
                      {ACTION_LABELS[action]}
                    </Button>
                  ))}
                  {destructiveActions.length > 0 && mainActions.length > 0 && (
                    <Separator className="my-3" />
                  )}
                  {destructiveActions.map((action) => (
                    <Button
                      key={action}
                      variant="outline"
                      className="w-full justify-start border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => runAction(action)}
                    >
                      {ACTION_LABELS[action]}
                    </Button>
                  ))}
                </div>
              )}

              {user?.is_shop_admin && (
                <>
                  <Separator className="my-3" />
                  <Button
                    variant="destructive"
                    className="w-full justify-start"
                    onClick={() => setConfirmDelete(true)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
                    Delete order
                  </Button>
                </>
              )}

              <Separator className="my-3" />
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => setShowReceipt(true)}
              >
                <Printer className="mr-2 h-4 w-4" aria-hidden="true" />
                View receipt
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Order summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <Row label="Subtotal" value={peso(order.subtotal_peso)} />
              <Row label="Paid" value={peso(order.amount_paid_peso)} />
              <Row
                label="Balance due"
                value={peso(order.balance_due_peso)}
                emphasis={order.balance_due_peso > 0}
              />
              <Separator className="my-2" />
              <Row label="Contact" value={order.guest_contact_value || "—"} />
              <Row
                label="Contact method"
                value={humanize(order.guest_contact_method)}
                capitalize
              />
              <Row
                label="Payment"
                value={humanize(order.payment_method)}
                capitalize
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle className="text-base">Internal notes</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Only the shop sees this.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => notesMutation.mutate()}
                disabled={notesMutation.isPending || !notesDirty}
              >
                {notesMutation.isPending ? (
                  <Loader2 aria-hidden className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save aria-hidden className="mr-2 h-4 w-4" />
                )}
                {notesMutation.isPending ? "Saving…" : "Save"}
              </Button>
            </CardHeader>
            <CardContent className="space-y-1.5">
              <Textarea
                rows={4}
                aria-label="Internal notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add a note for the team…"
              />
              {notesDirty && (
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  Unsaved changes
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Status history</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="relative space-y-5 border-l pl-5">
                {order.history.map((h) => (
                  <li key={h.id} className="relative">
                    <span
                      aria-hidden
                      className="absolute -left-[25px] top-1.5 h-2 w-2 rounded-full bg-border ring-4 ring-card"
                    />
                    <StatusBadge
                      status={h.to_status}
                      display={h.to_status_display}
                    />
                    <p
                      className={cn(
                        "mt-1.5 text-sm",
                        !h.note && "italic text-muted-foreground",
                      )}
                    >
                      {h.note || "No note"}
                    </p>
                    <time
                      dateTime={h.created_at}
                      className="text-xs text-muted-foreground"
                    >
                      {formatDate(h.created_at)}
                    </time>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
        </div>
      </div>

      <FilePreviewDialog
        file={previewFile}
        orderId={order.id}
        allowVariants
        onClose={() => setPreviewFile(null)}
      />

      <OrderReceiptDialog
        order={order}
        open={showReceipt}
        onClose={() => setShowReceipt(false)}
      />

      {/* ------------------------------------------------ confirm dialog */}
      <Dialog
        open={!!confirmAction}
        onOpenChange={(open) => !open && setConfirmAction(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmAction && ACTION_LABELS[confirmAction]}?
            </DialogTitle>
            <DialogDescription>
              Order {order.tracking_id} ·{" "}
              {confirmAction === "approve"
                ? "This releases the job to the printer."
                : "This will change the order status."}
              {confirmAction &&
                DESTRUCTIVE.includes(confirmAction) &&
                " This can't be undone."}
            </DialogDescription>
          </DialogHeader>
          {confirmAction === "request_revision" && !note.trim() ? (
            <p className="text-sm text-destructive">
              A message is required — the customer sees it with the
              revision request and needs it to know what to fix.
            </p>
          ) : note ? (
            <blockquote className="rounded-md border-l-4 bg-muted/50 px-3 py-2 text-sm">
              <span className="text-xs text-muted-foreground">Your note</span>
              <p className="whitespace-pre-wrap">{note}</p>
            </blockquote>
          ) : (
            <p className="text-sm text-muted-foreground">No note attached.</p>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setConfirmAction(null)}>
              Go back
            </Button>
            <Button
              variant={
                confirmAction && DESTRUCTIVE.includes(confirmAction)
                  ? "destructive"
                  : "default"
              }
              onClick={() =>
                confirmAction &&
                actionMutation.mutate({ action: confirmAction })
              }
              disabled={
                actionMutation.isPending ||
                (confirmAction === "request_revision" && !note.trim())
              }
            >
              {actionMutation.isPending && (
                <Loader2 aria-hidden className="mr-2 h-4 w-4 animate-spin" />
              )}
              {confirmAction && ACTION_LABELS[confirmAction]}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reprint: whole order, or just the sheet that failed. */}
      <Dialog
        open={!!reprintTarget}
        onOpenChange={(open) => !open && setReprintTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {reprintTarget === "all"
                ? "Reprint the whole order"
                : "Reprint this file"}
            </DialogTitle>
            <DialogDescription>
              {reprintTarget === "all"
                ? `All ${order.files.length} file(s) will be sent to the printer again. The previous run stays in the history.`
                : `Only “${reprintFile?.file_name}” will be printed again. The pages you selected (${reprintFile?.page_selection_label}) are kept.`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="reprint-note">Reason (optional)</Label>
            <Textarea
              id="reprint-note"
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. printer cancelled the job, faded output, customer lost a copy"
            />
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setReprintTarget(null)}>
              Go back
            </Button>
            <Button
              onClick={() =>
                actionMutation.mutate({
                  action: "reprint",
                  extra: reprintFile ? { file_id: reprintFile.id } : {},
                })
              }
              disabled={actionMutation.isPending}
            >
              {actionMutation.isPending ? (
                <Loader2 aria-hidden className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Printer aria-hidden className="mr-2 h-4 w-4" />
              )}
              Send to printer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------------ delete dialog */}
      <Dialog
        open={confirmDelete}
        onOpenChange={(open) => !open && setConfirmDelete(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this order permanently?</DialogTitle>
            <DialogDescription>
              Order {order.tracking_id}, its files and versions, print jobs,
              payment records and history will be removed for good. Any paid
              payments are refunded first. This can&apos;t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              Go back
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <Loader2 aria-hidden className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 aria-hidden className="mr-2 h-4 w-4" />
              )}
              Delete forever
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ----------------------------------------------------------- helpers */

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading order">
      <div className="space-y-2">
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Skeleton className="h-96 w-full rounded-lg" />
        <div className="space-y-6">
          <Skeleton className="h-64 w-full rounded-lg" />
          <Skeleton className="h-40 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
}

function AlertBanner({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-amber-300 border-l-4 border-l-amber-500 bg-amber-50 p-4 dark:border-amber-800 dark:border-l-amber-500 dark:bg-amber-950/40"
    >
      <AlertTriangle
        aria-hidden
        className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400"
      />
      <div className="space-y-1 text-sm text-amber-900 dark:text-amber-100">
        <p className="font-medium">{title}</p>
        <div className="space-y-1 text-xs text-amber-900/90 dark:text-amber-100/90">
          {children}
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  emphasis,
  capitalize,
}: {
  label: string;
  value: string;
  emphasis?: boolean;
  capitalize?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          "min-w-0 break-words text-right tabular-nums",
          emphasis && "font-semibold text-amber-700 dark:text-amber-400",
          capitalize && "capitalize",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function PrintJobRow({
  job,
  onReprint,
}: {
  job: PrintJob;
  onReprint: () => void;
}) {
  return (
    <li className="rounded-md border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={cn(
              "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
              printJobStatusStyle(job.status),
            )}
          >
            {printJobStatusLabel(job)}
          </span>
          <span className="truncate font-medium">
            {job.file_name || job.epson_job_id}
          </span>
          {job.is_reprint && (
            <span className="shrink-0 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200">
              Reprint
            </span>
          )}
        </div>
        {job.is_printer_cancelled && (
          <Button variant="outline" size="sm" onClick={onReprint}>
            <Printer aria-hidden className="mr-2 h-4 w-4" /> Reprint
          </Button>
        )}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {job.pages_label} · {job.epson_status || job.status}
        {job.completed_at ? ` · finished ${formatDate(job.completed_at)}` : ""}
      </p>
      {job.error_message && (
        <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {job.error_message}
        </p>
      )}
    </li>
  );
}
