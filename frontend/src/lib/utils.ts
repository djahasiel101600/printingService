import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPeso(amountInPeso: number): string {
  return `₱${amountInPeso.toLocaleString("en-PH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatQuantityUnit(
  quantity: number | null | undefined,
  unitLabel?: string | null,
): string {
  const unit = unitLabel || "piece";
  return `${quantity ?? "—"} ${quantity === 1 ? unit : `${unit}s`}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
