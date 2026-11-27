import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2, RefreshCw, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, apiErrorMessage } from "@/lib/api";
import { colorModeLabel } from "@/lib/constants";
import type { Order, OrderFile, PageColorMode } from "@/lib/types";
import { cn } from "@/lib/utils";

interface PageColorReviewProps {
  order: Order;
  file: OrderFile;
  disabled?: boolean;
}

interface ColorUpdate {
  overrides?: Record<string, PageColorMode>;
  reanalyze?: boolean;
}

/** Staff review of Auto-mode analysis, effective page modes and quote-affecting overrides. */
export default function PageColorReview({ order, file, disabled }: PageColorReviewProps) {
  const queryClient = useQueryClient();
  const analysisPages = file.color_analysis?.pages ?? [];
  const detectedByPage = new Map(analysisPages.map((entry) => [entry.page, entry]));
  const effectiveModes = file.effective_page_modes?.length
    ? file.effective_page_modes
    : (file.selected_pages.length ? file.selected_pages : Array.from(
        { length: Math.max(1, file.page_count) },
        (_, index) => index + 1,
      )).map((page) => ({
        page,
        mode: file.color_page_overrides?.[String(page)] ?? detectedByPage.get(page)?.mode ?? "color",
      }));
  const overrides = file.color_page_overrides ?? {};
  const effectiveColor = effectiveModes.filter((entry) => entry.mode === "color").length;
  const effectiveMono = effectiveModes.filter((entry) => entry.mode === "mono").length;

  const colorMutation = useMutation({
    mutationFn: async (payload: ColorUpdate) => {
      const { data } = await api.patch<{ order: Order; file: OrderFile }>(
        `/admin/orders/${order.id}/files/${file.id}/color/`,
        payload,
      );
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-order", String(order.id)], data.order);
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
      toast.success("Page colors updated — the quote was recalculated.");
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const busy = colorMutation.isPending || disabled;

  function updateOverride(page: number, mode: PageColorMode) {
    const next = { ...overrides };
    const detected = detectedByPage.get(page)?.mode ?? "color";
    if (mode === detected) delete next[String(page)];
    else next[String(page)] = mode;
    colorMutation.mutate({ overrides: next });
  }

  function togglePage(page: number, current: PageColorMode) {
    updateOverride(page, current === "color" ? "mono" : "color");
  }

  return (
    <section
      className="space-y-3 rounded-md border bg-muted/20 p-3"
      aria-label="Automatic page color analysis"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">Auto page colors</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Detected {file.detected_color_pages ?? 0} color ·{" "}
            {file.detected_mono_pages ?? 0} black &amp; white ·{" "}
            {file.unanalyzed_pages ?? 0} unclear (charged as color).
          </p>
          <p className="mt-1 text-xs font-medium">
            Selected pages: {effectiveColor} color · {effectiveMono} black &amp; white
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => colorMutation.mutate({ reanalyze: true })}
          >
            {colorMutation.isPending ? (
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
            )}
            Reanalyze
          </Button>
          {Object.keys(overrides).length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => colorMutation.mutate({ overrides: {} })}
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
              Clear overrides
            </Button>
          )}
        </div>
      </div>

      {file.color_analysis?.warning && (
        <p className="flex items-start gap-2 rounded bg-amber-50 px-2 py-1.5 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {file.color_analysis.warning}
        </p>
      )}
      {file.color_analysis?.note && (
        <p className="text-xs text-muted-foreground">{file.color_analysis.note}</p>
      )}

      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-muted-foreground">
          Page-by-page overrides ({effectiveModes.length})
        </summary>
        <p className="mt-1 text-muted-foreground">
          Switch a page to override detection. Choose Auto on a manual page to return to detection.
          Duplex sheets use color whenever either side is color.
        </p>
        <div className="mt-2 grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
          {effectiveModes.map(({ page, mode }) => {
            const detected = detectedByPage.get(page);
            const manual = Boolean(overrides[String(page)]);
            const next = mode === "color" ? "mono" : "color";
            return (
              <div key={page} className="flex overflow-hidden rounded border bg-background">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => togglePage(page, mode)}
                  aria-label={`Page ${page}: ${colorModeLabel(mode)}. Switch to ${colorModeLabel(next)}`}
                  title={`Detected: ${detected?.analyzed ? colorModeLabel(detected.mode) : "unclear"}`}
                  className={cn(
                    "min-w-0 flex-1 px-2 py-1 text-left transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50",
                    manual && "bg-primary/5",
                  )}
                >
                  <span className="block font-medium">Page {page}</span>
                  <span className="block text-[10px] text-muted-foreground">
                    {mode === "color" ? "Color" : "B&W"}
                    {manual ? " · Manual" : ""}
                  </span>
                </button>
                {manual && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => updateOverride(page, detected?.mode ?? "color")}
                    aria-label={`Reset page ${page} to automatic detection`}
                    className="border-l px-1.5 text-[10px] text-muted-foreground hover:bg-accent disabled:opacity-50"
                  >
                    Auto
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </details>
    </section>
  );
}
