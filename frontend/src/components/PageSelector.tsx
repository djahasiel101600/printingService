import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatPageRange, parsePageRange } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface PageSelectorProps {
  /** Total pages in the document. */
  pageCount: number;
  /** Pages currently marked for printing (empty array = all pages). */
  selected: number[];
  onSave: (pages: number[]) => Promise<unknown> | void;
  saving?: boolean;
  disabled?: boolean;
  disabledReason?: string;
}

/**
 * "Which pages should be printed?" — the admin's page picker.
 *
 * Two ways to work, because admins think in both modes: type a range
 * ("1-3, 5") for a long document, or tick page chips for a short one.
 * Selecting every page is stored as "no selection", which lets the original
 * file flow to the printer untouched.
 */
export default function PageSelector({
  pageCount, selected, onSave, saving, disabled, disabledReason,
}: PageSelectorProps) {
  const [range, setRange] = useState("");
  const [touched, setTouched] = useState(false);

  // Keep the field in sync when the selection changes elsewhere (reset, save).
  useEffect(() => {
    setRange(formatPageRange(selected));
  }, [selected]);

  const allPages = useMemo(
    () => Array.from({ length: pageCount }, (_, index) => index + 1),
    [pageCount],
  );
  const active = useMemo(() => new Set(selected), [selected]);
  const parsed = useMemo(() => parsePageRange(range, pageCount), [range, pageCount]);
  const rangeError = touched && parsed === null;
  const dirty = JSON.stringify(parsed ?? []) !== JSON.stringify(selected);

  // Nothing ticked (or everything ticked) means "print it all".
  const effective = parsed ?? [];
  const isAllPages = effective.length === 0 || effective.length === pageCount;

  function toggle(page: number) {
    const next = new Set(active.has(page) ? selected.filter((p) => p !== page) : [...selected, page]);
    setRange(formatPageRange(allPages.filter((p) => next.has(p))));
    setTouched(true);
  }

  function setAll(pages: number[]) {
    setRange(formatPageRange(pages));
    setTouched(true);
  }

  if (disabled) {
    return (
      <p className="rounded-md bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
        {disabledReason ?? "Page selection is not available for this file."}
      </p>
    );
  }

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor="page-range" className="text-xs">Pages to print</Label>
        <span className="text-xs text-muted-foreground">
          {isAllPages
            ? `All ${pageCount} page${pageCount === 1 ? "" : "s"}`
            : `${effective.length} of ${pageCount} pages`}
        </span>
      </div>

      <Input
        id="page-range"
        value={range}
        onChange={(event) => { setRange(event.target.value); setTouched(true); }}
        onBlur={() => setTouched(true)}
        placeholder="e.g. 1-3, 5, 8-10  (leave empty for every page)"
        className={cn("h-9 text-sm", rangeError && "border-destructive")}
        aria-invalid={rangeError}
      />
      {rangeError && (
        <p className="text-xs text-destructive">
          Use page numbers and ranges up to {pageCount}, separated by commas — for example 1-3, 5.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Button type="button" variant="outline" size="sm" className="h-7 px-2 text-xs"
          onClick={() => setAll(allPages)}>
          <Check className="mr-1 h-3 w-3" /> All
        </Button>
        <Button type="button" variant="outline" size="sm" className="h-7 px-2 text-xs"
          onClick={() => setAll([])}>
          <X className="mr-1 h-3 w-3" /> None
        </Button>
        <Button type="button" variant="outline" size="sm" className="h-7 px-2 text-xs"
          onClick={() => setAll(allPages.filter((page) => !active.has(page)))}>
          Invert
        </Button>
        {effective.length > 0 && (
          <span className="ml-auto font-medium tabular-nums text-indigo-700">
            {formatPageRange(effective)}
          </span>
        )}
      </div>

      {/* Page chips — capped so a 500-page scan does not render 500 buttons. */}
      {pageCount <= 100 ? (
        <div className="flex flex-wrap gap-1">
          {allPages.map((page) => {
            const isSelected = isAllPages || active.has(page);
            return (
              <button key={page} type="button" onClick={() => toggle(page)}
                aria-pressed={isSelected}
                className={cn(
                  "h-7 w-7 rounded border text-xs font-medium tabular-nums transition-colors",
                  isSelected
                    ? "border-primary bg-primary text-primary-foreground"
                    : "bg-background hover:bg-accent",
                )}>
                {page}
              </button>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Long document — use the range field above to choose pages.
        </p>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="outline" size="sm"
          onClick={() => { setRange(formatPageRange(selected)); setTouched(false); }}
          disabled={!dirty || saving}>
          Reset
        </Button>
        <Button type="button" size="sm" onClick={() => onSave(parsed ?? [])}
          disabled={saving || rangeError || !dirty}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Save page selection
        </Button>
      </div>
    </div>
  );
}