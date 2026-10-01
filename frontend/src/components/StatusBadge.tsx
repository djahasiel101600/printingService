import { STATUS_STYLES } from "@/lib/constants";
import type { OrderStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, display, className }: { status: OrderStatus; display?: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold",
        STATUS_STYLES[status] ?? "bg-muted text-muted-foreground",
        className,
      )}
    >
      {display ?? status}
    </span>
  );
}
