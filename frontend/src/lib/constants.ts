import type { OrderStatus } from "./types";

/**
 * How loud a status is allowed to look. Tones are semantic tokens, so status
 * colour is never a hardcoded hex and never a shade of the brand colour —
 * a customer must never confuse "your order is printing" (progress) with
 * "pay now" (attention).
 */
export type StatusTone = "neutral" | "info" | "progress" | "attention" | "success" | "danger";

/** Badge styling per tone. Soft fill for most states, solid only for "done". */
export const TONE_STYLES: Record<StatusTone, string> = {
  neutral: "bg-muted text-muted-foreground",
  info: "bg-info/15 text-info",
  progress: "bg-progress/15 text-progress",
  attention: "bg-attention/15 text-attention",
  success: "bg-success/15 text-success",
  danger: "bg-danger/15 text-danger",
};

export interface StatusMeta {
  /** Plain-language label for customers. Never the raw database key. */
  customerLabel: string;
  /** One sentence telling the customer what happens next. */
  customerHelp: string;
  /** Staff-facing label — the shop's own vocabulary. */
  staffLabel: string;
  tone: StatusTone;
  /** Index into ORDER_PHASES. */
  phase: number;
  /** True when the customer has to do something before work continues. */
  needsCustomer: boolean;
  /** True when a human has to act before anything else can happen. */
  needsStaff: boolean;
  /** Render with a solid fill to mark a finished order. */
  filled?: boolean;
}

/** The customer journey, in order. The stepper renders exactly this. */
export const ORDER_PHASES: Array<{ label: string; blurb: string }> = [
  { label: "Placed", blurb: "We have your order." },
  { label: "Review", blurb: "A staff member checks your files and settings." },
  { label: "Printing", blurb: "Your pages are being printed." },
  { label: "Ready", blurb: "Collect your print at the counter." },
  { label: "Done", blurb: "Order closed." },
];

const PHASE = { placed: 0, review: 1, printing: 2, ready: 3, done: 4 } as const;

/**
 * The single source of truth for order status. The badge, the order banner,
 * the stepper and the admin queue all read this, so a customer sees the same
 * story everywhere and the shop can re-word it in one place.
 */
export const STATUS_META: Record<OrderStatus, StatusMeta> = {
  draft: {
    customerLabel: "Not sent yet",
    customerHelp: "This order has not been submitted to the shop yet.",
    staffLabel: "Draft",
    tone: "neutral",
    phase: PHASE.placed,
    needsCustomer: true,
    needsStaff: false,
  },
  awaiting_payment: {
    customerLabel: "Waiting for payment",
    customerHelp: "Pay online, or choose to pay when you collect, and we will start reviewing your files.",
    staffLabel: "Awaiting payment",
    tone: "attention",
    phase: PHASE.placed,
    needsCustomer: true,
    needsStaff: false,
  },
  pending_review: {
    customerLabel: "We are checking your files",
    customerHelp: "A staff member is checking your page range, paper and orientation before it goes to the printer.",
    staffLabel: "Pending review",
    tone: "info",
    phase: PHASE.review,
    needsCustomer: false,
    needsStaff: true,
  },
  revision_requested: {
    customerLabel: "We need a new file",
    customerHelp: "Read the note from staff below, then upload the corrected file. This same order continues — you will not start over.",
    staffLabel: "Revision requested",
    tone: "attention",
    phase: PHASE.review,
    needsCustomer: true,
    needsStaff: true,
  },
  approved_queued: {
    customerLabel: "Approved — waiting for the printer",
    customerHelp: "Your settings look good. Your order is in the print queue.",
    staffLabel: "Approved (queued)",
    tone: "progress",
    phase: PHASE.printing,
    needsCustomer: false,
    needsStaff: false,
  },
  printing: {
    customerLabel: "Printing now",
    customerHelp: "The printer is working through your pages.",
    staffLabel: "Printing",
    tone: "progress",
    phase: PHASE.printing,
    needsCustomer: false,
    needsStaff: false,
  },
  on_hold: {
    customerLabel: "On hold",
    customerHelp: "We have paused this order. The note below explains why.",
    staffLabel: "On hold",
    tone: "attention",
    phase: PHASE.review,
    needsCustomer: false,
    needsStaff: true,
  },
  printed_ready: {
    customerLabel: "Ready for pickup",
    customerHelp: "Your pages are printed and waiting at the counter.",
    staffLabel: "Ready for pickup",
    tone: "success",
    phase: PHASE.ready,
    needsCustomer: true,
    needsStaff: false,
  },
  // The printer dropped the job. The order is still alive, the shop just needs
  // to run it again — so it reads as "attention", never as a customer error.
  print_cancelled: {
    customerLabel: "Reprinting",
    customerHelp: "The printer stopped this job partway. We are running it again — nothing you need to do.",
    staffLabel: "Print cancelled (reprint needed)",
    tone: "attention",
    phase: PHASE.printing,
    needsCustomer: false,
    needsStaff: true,
  },
  rejected: {
    customerLabel: "We could not print this",
    customerHelp: "This order was declined. The note below has the details.",
    staffLabel: "Rejected",
    tone: "danger",
    phase: PHASE.done,
    needsCustomer: false,
    needsStaff: false,
  },
  cancelled: {
    customerLabel: "Cancelled",
    customerHelp: "This order was cancelled and will not be printed.",
    staffLabel: "Cancelled",
    tone: "neutral",
    phase: PHASE.done,
    needsCustomer: false,
    needsStaff: false,
  },
  completed: {
    customerLabel: "Completed",
    customerHelp: "Collected and closed. Thanks for printing with us.",
    staffLabel: "Completed",
    tone: "success",
    phase: PHASE.done,
    needsCustomer: false,
    needsStaff: false,
    filled: true,
  },
};

export const ALL_ORDER_STATUSES = Object.keys(STATUS_META) as OrderStatus[];

/** Never throws: an unknown status from a newer backend degrades gracefully. */
export function statusMeta(status: string): StatusMeta {
  return (
    STATUS_META[status as OrderStatus] ?? {
      customerLabel: status.replace(/_/g, " "),
      customerHelp: "Contact the shop if this looks wrong.",
      staffLabel: status,
      tone: "neutral" as StatusTone,
      phase: PHASE.placed,
      needsCustomer: false,
      needsStaff: false,
    }
  );
}

export function statusLabel(status: string, audience: "customer" | "staff" = "customer"): string {
  const meta = statusMeta(status);
  return audience === "staff" ? meta.staffLabel : meta.customerLabel;
}

/** Terminal states never show a "next step" — there isn't one. */
export function isTerminalStatus(status: string): boolean {
  return statusMeta(status).phase === PHASE.done;
}

export function statusBadgeClass(status: string): string {
  const meta = statusMeta(status);
  return meta.filled ? "bg-success text-success-foreground" : TONE_STYLES[meta.tone];
}

/**
 * @deprecated Prefer `statusBadgeClass`. Kept so the existing call sites keep
 * working while pages are migrated one at a time — now derived from
 * STATUS_META, so adding a status updates the badge automatically.
 */
export const STATUS_STYLES: Record<OrderStatus, string> = Object.fromEntries(
  ALL_ORDER_STATUSES.map((status) => [status, statusBadgeClass(status)]),
) as Record<OrderStatus, string>;

/** Statuses that need a human decision before anything else can happen. */
export const ATTENTION_STATUSES: OrderStatus[] = [
  "pending_review",
  "revision_requested",
  "on_hold",
  "print_cancelled",
];

export const PRINT_JOB_STATUS_STYLES: Record<string, string> = {
  created: "bg-muted text-muted-foreground",
  submitted: "bg-muted text-muted-foreground",
  executed: "bg-indigo-100 text-indigo-800",
  printing: "bg-blue-100 text-blue-800",
  completed: "bg-emerald-100 text-emerald-800",
  on_hold: "bg-red-100 text-red-800",
  // Distinct from "failed": the printer itself cancelled this job.
  canceled: "bg-amber-200 text-amber-900",
  failed: "bg-red-100 text-red-900",
};

export function printJobStatusStyle(status: string): string {
  return PRINT_JOB_STATUS_STYLES[status] ?? "bg-muted text-muted-foreground";
}

/** Human label for an Epson print job state. */
export const PRINT_JOB_STATUS_LABELS: Record<string, string> = {
  created: "Queued",
  submitted: "Submitted",
  executed: "Sent to printer",
  printing: "Printing",
  completed: "Printed",
  on_hold: "Printer issue",
  canceled: "Cancelled at printer",
  failed: "Failed to send",
};

export function printJobStatusLabel(job: {
  status: string;
  status_display?: string;
  epson_status?: string;
}): string {
  if (job.status === "canceled") return PRINT_JOB_STATUS_LABELS.canceled;
  return job.status_display || PRINT_JOB_STATUS_LABELS[job.status] || job.status;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const value = bytes / 1024 ** index;
  return `${value >= 10 || index === 0 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

/** [1,2,3,7] -> "1-3, 7" — mirrors the server's page-selection label. */
export function formatPageRange(pages: number[]): string {
  if (!pages.length) return "";
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  const groups: Array<[number, number]> = [];
  let start = sorted[0];
  let previous = sorted[0];
  for (const page of sorted.slice(1)) {
    if (page === previous + 1) {
      previous = page;
      continue;
    }
    groups.push([start, previous]);
    start = page;
    previous = page;
  }
  groups.push([start, previous]);
  return groups.map(([a, b]) => (a === b ? `${a}` : `${a}-${b}`)).join(", ");
}

/**
 * Parse a human page range ("1-3, 5, 8-10") into page numbers.
 * Returns null when the input is malformed so the caller can show an error.
 */
export function parsePageRange(input: string, maxPage: number): number[] | null {
  const text = input.trim();
  if (!text) return [];
  const pages = new Set<number>();
  for (const chunk of text.split(",")) {
    const part = chunk.trim();
    if (!part) return null;
    const match = part.match(/^(\d+)\s*(?:-\s*(\d+))?$/);
    if (!match) return null;
    const from = Number(match[1]);
    const to = match[2] ? Number(match[2]) : from;
    if (from < 1 || to < from) return null;
    if (to > maxPage) return null;
    // Guard against someone pasting an enormous range by accident.
    if (to - from > 2000) return null;
    for (let page = from; page <= to; page += 1) pages.add(page);
  }
  return [...pages].sort((a, b) => a - b);
}

export const PAPER_SIZE_LABELS: Record<string, string> = {
  ps_a3: "A3",
  ps_a4: "A4",
  ps_a5: "A5",
  ps_a6: "A6",
  ps_b5: "B5",
  ps_tabloid: "Tabloid",
  ps_letter: "Letter",
  ps_legal: "Legal",
  ps_halfletter: "Half Letter",
  ps_kg: "King (8.5×13\")",
  ps_l: "L (3.5×5\")",
  ps_2l: "2L (5×7\")",
  ps_10x12: '10×12"',
  ps_8x10: '8×10"',
  ps_hivision: "Hi-Vision",
  ps_5x8: '5×8"',
  ps_postcard: "Postcard",
};

export const PAPER_TYPE_LABELS: Record<string, string> = {
  pt_plainpaper: "Plain paper",
  pt_photopaper: "Photo paper",
  pt_hagaki: "Hagaki",
  pt_hagakiphoto: "Hagaki photo",
  pt_hagakiinkjet: "Hagaki inkjet",
  pt_roll: "Roll",
};

export const PAPER_SOURCE_LABELS: Record<string, string> = {
  auto: "Auto",
  rear: "Rear tray",
  front1: "Cassette 1",
  front2: "Cassette 2",
  front3: "Cassette 3",
  front4: "Cassette 4",
  roll: "Roll",
};

export const QUALITY_LABELS: Record<string, string> = {
  draft: "Draft (fastest)",
  normal: "Normal",
  high: "High (best quality)",
};

export const SIDES_LABELS: Record<string, string> = {
  none: "Single-sided",
  long: "Double-sided (flip long edge)",
  short: "Double-sided (flip short edge)",
};

/**
 * Sheet orientation for picture files. PDFs and Word documents keep their own
 * page layout — the shop applies this to the picture before printing.
 */
export const ORIENTATION_LABELS: Record<string, string> = {
  portrait: "Portrait",
  landscape: "Landscape",
};

export function orientationLabel(value: string): string {
  return ORIENTATION_LABELS[value] ?? value;
}

export function paperSizeLabel(code: string): string {
  return PAPER_SIZE_LABELS[code] ?? code;
}

export function paperTypeLabel(code: string): string {
  return PAPER_TYPE_LABELS[code] ?? code;
}

export function paperSourceLabel(code: string): string {
  return PAPER_SOURCE_LABELS[code] ?? code;
}

export function qualityLabel(code: string): string {
  return QUALITY_LABELS[code] ?? code;
}

export function sidesLabel(code: string): string {
  return SIDES_LABELS[code] ?? code;
}
