import { Printer } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatDateTime, formatPeso } from "@/lib/utils";
import type { Order } from "@/lib/types";

/** Raw payment-method key -> the words a customer expects to read. */
const METHOD_LABELS: Record<string, string> = {
  qrph: "QR Ph",
  pickup: "Pay upon pickup",
  cash: "Cash",
  card: "Card",
};

const methodLabel = (method: string) =>
  METHOD_LABELS[method] ?? (method ? method : "—");

/** Payment status chip tone. Mirrors the chip styling on the order page. */
function paymentChipClass(status: string) {
  const s = status.toLowerCase();
  if (s.includes("paid") || s.includes("success")) {
    return "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300";
  }
  if (s.includes("refund")) {
    return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300";
  }
  if (s.includes("fail") || s.includes("expire") || s.includes("cancel")) {
    return "bg-destructive/10 text-destructive";
  }
  return "bg-muted text-muted-foreground";
}

interface Props {
  order: Order | null;
  open: boolean;
  onClose: () => void;
}

/**
 * Printable receipt for a single order.
 *
 * The whole card carries `print-receipt`, so the global print stylesheet shows
 * only this region and hides the app chrome (see index.css). The on-screen
 * Print button lives *outside* that region, so it disappears from the printout.
 */
export default function OrderReceiptDialog({ order, open, onClose }: Props) {
  if (!order) return null;

  const payments = order.payments ?? [];
  const paidInFull = order.balance_due_peso <= 0 && order.amount_paid_peso > 0;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Receipt</DialogTitle>
          <DialogDescription>
            A printable summary for order {order.tracking_id}.
          </DialogDescription>
        </DialogHeader>

        {/* Everything inside .print-receipt is what the printer sees. */}
        <div className="print-receipt rounded-lg border bg-white p-6 text-black">
          <div className="flex items-start justify-between border-b border-black/15 pb-4">
            <div>
              <p className="text-lg font-bold tracking-wide">PrintEasy</p>
              <p className="text-xs text-black/60">Order receipt</p>
            </div>
            <div className="text-right">
              <p className="font-mono text-sm font-bold tracking-widest">
                {order.tracking_id}
              </p>
              <p className="text-xs text-black/60">
                {formatDateTime(order.created_at)}
              </p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 py-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-black/60">Customer</dt>
              <dd className="font-medium">{order.client_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-black/60">Status</dt>
              <dd className="font-medium">{order.status_display}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-black/60">Payment method</dt>
              <dd className="font-medium">{methodLabel(order.payment_method)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-black/60">Files</dt>
              <dd className="font-medium">{order.files.length}</dd>
            </div>
          </dl>

          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-black/15 text-left text-xs uppercase tracking-wide text-black/60">
                <th className="py-1.5">File</th>
                <th className="py-1.5 text-right">Pages</th>
              </tr>
            </thead>
            <tbody>
              {order.files.map((file) => (
                <tr key={file.id} className="border-b border-black/10">
                  <td className="py-1.5 pr-2">
                    <span className="break-all">{file.file_name}</span>
                    {(file.current_version ?? 1) > 1 && (
                      <span className="ml-1 text-xs text-black/50">
                        (v{file.current_version})
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {file.page_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <dl className="space-y-1 py-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-black/60">Subtotal</dt>
              <dd className="tabular-nums">{formatPeso(order.subtotal_peso)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-black/60">Paid</dt>
              <dd className="tabular-nums">
                {formatPeso(order.amount_paid_peso)}
              </dd>
            </div>
            <div className="flex justify-between border-t border-black/15 pt-1 text-base font-bold">
              <dt>{paidInFull ? "Paid in full" : "Balance due"}</dt>
              <dd className="tabular-nums">
                {paidInFull
                  ? formatPeso(order.subtotal_peso)
                  : formatPeso(order.balance_due_peso)}
              </dd>
            </div>
          </dl>

          {payments.length > 0 && (
            <div className="border-t border-black/15 pt-3">
              <p className="mb-1.5 text-xs uppercase tracking-wide text-black/60">
                Payment history
              </p>
              <ul className="space-y-1 text-xs">
                {payments.map((payment) => (
                  <li
                    key={payment.id}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[0.65rem] font-semibold ${paymentChipClass(
                          payment.status,
                        )}`}
                      >
                        {payment.status}
                      </span>
                      <span className="text-black/70">
                        {methodLabel(payment.method)}
                      </span>
                      <span className="text-black/50">
                        {payment.paid_at
                          ? formatDateTime(payment.paid_at)
                          : "not paid"}
                      </span>
                    </span>
                    <span className="tabular-nums">
                      {formatPeso(payment.amount / 100)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="mt-4 border-t border-black/15 pt-3 text-center text-[0.7rem] text-black/50">
            Thank you! Every order is checked by a person before it prints.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button onClick={() => window.print()}>
            <Printer className="mr-2 h-4 w-4" aria-hidden="true" /> Print
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

