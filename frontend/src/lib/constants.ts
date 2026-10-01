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
  rejected: "bg-red-100 text-red-900",
  cancelled: "bg-zinc-200 text-zinc-700",
  completed: "bg-green-600 text-white",
};

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
