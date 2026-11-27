import { colorModeLabel } from "@/lib/constants";
import type { QuoteLine } from "@/lib/types";
import { cn, formatPeso, formatQuantityUnit } from "@/lib/utils";

interface QuoteBreakdownProps {
  lines: QuoteLine[];
  className?: string;
  tone?: "default" | "receipt";
  title?: string;
}

/** Remove the suffix added by the API for mixed Auto quotes; the mode is shown separately. */
function baseLabel(label: string): string {
  return label.replace(/ — (Color|Black & white)$/, "");
}

/** Itemized centavo-to-peso quote lines shared by estimates, orders and receipts. */
export default function QuoteBreakdown({
  lines,
  className,
  tone = "default",
  title = "Price breakdown",
}: QuoteBreakdownProps) {
  if (lines.length === 0) return null;

  const muted = tone === "receipt" ? "text-black/60" : "text-muted-foreground";
  const border = tone === "receipt" ? "border-black/10" : "border-border/60";

  return (
    <div className={cn("space-y-2", className)}>
      <p className={cn("text-xs font-medium uppercase tracking-wide", muted)}>
        {title}
      </p>
      <ul className="space-y-2">
        {lines.map((line, index) => (
          <li
            key={`${line.label}-${index}`}
            className={cn("flex items-start justify-between gap-3 border-b pb-2 last:border-0", border)}
          >
            <div className="min-w-0">
              <p className="break-words text-xs font-medium">{baseLabel(line.label)}</p>
              <p className={cn("mt-0.5 text-[11px]", muted)}>
                {line.kind === "catalogue" ? (
                  <>
                    {formatQuantityUnit(line.quantity, line.unit_label)} × {formatPeso(line.unit_price_peso)}/
                    {line.unit_label || "piece"}
                  </>
                ) : (
                  <>
                    {line.color_mode ? colorModeLabel(line.color_mode) : "Print"} ·{" "}
                    {line.pages ?? 0} {line.pages === 1 ? "page" : "pages"} × {line.copies ?? 0}{" "}
                    {line.copies === 1 ? "copy" : "copies"} ·{" "}
                    {formatPeso(line.unit_price_peso)}/side
                  </>
                )}
              </p>
            </div>
            <span className="shrink-0 text-xs font-semibold tabular-nums">
              {formatPeso(line.amount_peso)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
