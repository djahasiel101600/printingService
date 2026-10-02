import type { OrderStatus } from "./types";

export const STATUS_STYLES: Record<OrderStatus, string> = {
  draft: "bg-muted text-muted-foreground",
  awaiting_payment: "bg-amber-100 text-amber-800",
  pending_review: "bg-sky-100 text-sky-800",
  revision_requested: "bg-orange-100 text-orange-800",
  approved_queued: "bg-indigo-100 text-indigo-800",
  printing: "bg-blue-100 text-blue-800",
  on_hold: "bg-red-100 text-red-800",
  printed_ready: "bg-emerald-100 text-emerald-800",
  // The printer dropped the job. Amber rather than red: the order is still
  // alive, the shop just needs to reprint it.
  print_cancelled: "bg-amber-200 text-amber-900",
  rejected: "bg-red-100 text-red-900",
  cancelled: "bg-zinc-200 text-zinc-700",
  completed: "bg-green-600 text-white",
};

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
