import { statusBadgeClass, statusLabel } from "@/lib/constants";
import { cn } from "@/lib/utils";

/**
 * Now speaks the customer vocabulary by default instead of showing the raw
 * database key (`display ?? status` used to leak `revision_requested` straight
 * onto the page). Staff views pass `audience="staff"` to keep shop jargon.
 */
export function StatusBadge({
  status,
  /** Overrides the computed label — only for foreign states (print jobs). */
  display,
  audience = "customer",
  className,
}: {
  status: string;
  display?: string;
  audience?: "customer" | "staff";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold",
        statusBadgeClass(status),
        className,
      )}
    >
      {display ?? statusLabel(status, audience)}
    </span>
  );
}
