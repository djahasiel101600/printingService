import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  CreditCard,
  FileWarning,
  Hourglass,
  PauseCircle,
  Printer,
  RefreshCw,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ORDER_PHASES, statusMeta, type StatusTone } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * Status, explained. Previously a coloured pill was the ONLY signal, so
 * "on hold" and "rejected" looked alike and the badge fell back to printing the
 * raw database key. These components read STATUS_META so the same status always
 * tells the same story, and colour is reinforcement rather than the message.
 */

/** Icon per tone — shape carries meaning for colourblind users too. */
const TONE_ICONS: Record<StatusTone, LucideIcon> = {
  neutral: Clock,
  info: Hourglass,
  progress: Printer,
  attention: AlertTriangle,
  success: CheckCircle2,
  danger: Ban,
};

const TONE_BORDER: Record<StatusTone, string> = {
  neutral: "border-border bg-muted/50",
  info: "border-info/40 bg-info/5",
  progress: "border-progress/40 bg-progress/5",
  attention: "border-attention/50 bg-attention/10",
  success: "border-success/40 bg-success/5",
  danger: "border-danger/50 bg-danger/10",
};

const TONE_ICON: Record<StatusTone, string> = {
  neutral: "text-muted-foreground",
  info: "text-info",
  progress: "text-progress",
  attention: "text-attention",
  success: "text-success",
  danger: "text-danger",
};

export function OrderStatusBanner({
  status,
  trackingId,
  note,
  className,
}: {
  status: string;
  /** Shown so the customer can quote it at the counter. */
  trackingId?: string;
  /** Staff note / rejection reason, when one exists. */
  note?: string | null;
  className?: string;
}) {
  const meta = statusMeta(status);
  const Icon = TONE_ICONS[meta.tone];

  return (
    <section
      aria-label="Order status"
      className={cn("rounded-lg border p-4 sm:p-5", TONE_BORDER[meta.tone], className)}
    >
      <div className="flex items-start gap-3">
        <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", TONE_ICON[meta.tone])} aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="text-base font-semibold leading-tight sm:text-lg">{meta.customerLabel}</h2>
          <p className="text-sm text-foreground/80">{meta.customerHelp}</p>
          {note && (
            <p className="mt-2 border-l-2 border-current/20 pl-3 text-sm italic text-foreground/70">
              {note}
            </p>
          )}
          {trackingId && (
            <p className="pt-1 text-xs text-muted-foreground">
              Tracking ID <span className="font-mono font-medium">{trackingId}</span>
            </p>
          )}
        </div>
      </div>
      <OrderStepper status={status} className="mt-4 border-t border-current/10 pt-4" />
    </section>
  );
}

export function OrderStepper({ status, className }: { status: string; className?: string }) {
  const meta = statusMeta(status);
  const isTerminal = meta.phase === ORDER_PHASES.length - 1;
  const reached = isTerminal ? ORDER_PHASES.length - 1 : meta.phase;

  return (
    <ol className={cn("flex flex-wrap items-center gap-x-1 gap-y-2", className)}>
      {ORDER_PHASES.map((phase, index) => {
        const done = index < reached;
        const current = index === reached;
        const state = done ? "done" : current ? "current" : "upcoming";
        return (
          <li key={phase.label} className="flex items-center gap-1">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium",
                done && "bg-success/15 text-success",
                current && "bg-primary/10 text-primary",
                state === "upcoming" && "text-muted-foreground",
              )}
              // The current step is announced, not just coloured.
              aria-current={current ? "step" : undefined}
            >
              {done && <CheckCircle2 className="h-3 w-3" aria-hidden="true" />}
              {phase.label}
              {current && <span className="sr-only">(current step)</span>}
            </span>
            {index < ORDER_PHASES.length - 1 && (
              <span aria-hidden="true" className={cn("h-px w-3", done ? "bg-success/40" : "bg-border")} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Compact banner for queue rows: what it needs and from whom. */
export function StatusHint({ status, className }: { status: string; className?: string }) {
  const meta = statusMeta(status);
  if (meta.needsCustomer && meta.needsStaff) return <StatusPill tone="attention" icon={RefreshCw} className={className}>Needs customer + staff</StatusPill>;
  if (meta.needsCustomer) return <StatusPill tone="attention" icon={CreditCard} className={className}>Needs customer</StatusPill>;
  if (meta.needsStaff) return <StatusPill tone="info" icon={FileWarning} className={className}>Needs staff</StatusPill>;
  if (meta.tone === "progress") return <StatusPill tone="progress" icon={Printer} className={className}>In progress</StatusPill>;
  return <StatusPill tone="neutral" icon={PauseCircle} className={className}>Waiting</StatusPill>;
}

function StatusPill({
  tone,
  icon: Icon,
  className,
  children,
}: {
  tone: StatusTone;
  icon: LucideIcon;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs font-medium", TONE_ICON[tone], className)}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {children}
    </span>
  );
}