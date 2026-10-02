import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Eye, FileText, FileUp, ImageIcon,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import PageSelector from "@/components/PageSelector";
import { formatBytes, formatPageRange } from "@/lib/constants";
import { api, apiErrorMessage } from "@/lib/api";
import type { Order, OrderFile } from "@/lib/types";

interface FileReviewCardProps {
  order: Order;
  file: OrderFile;
  onPreview: (file: OrderFile) => void;
  /** Page selection is locked once the order has already gone to the printer. */
  locked?: boolean;
}

/**
 * One uploaded file as the admin sees it: what it is, which pages will be
 * printed, and — for a document the printer cannot accept — the control that
 * swaps in a converted PDF.
 */
export default function FileReviewCard({
  order, file, onPreview, locked,
}: FileReviewCardProps) {
  const queryClient = useQueryClient();
  const [pages, setPages] = useState<number[]>(file.selected_pages);
  const replaceInput = useRef<HTMLInputElement>(null);

  // Keep local state aligned when the server order is refetched.
  if (pages.join() !== file.selected_pages.join()) {
    setPages(file.selected_pages);
  }

  const pagesMutation = useMutation({
    mutationFn: async (next: number[]) => {
      const { data } = await api.patch<{ order: Order; label: string }>(
        `/admin/orders/${order.id}/files/${file.id}/pages/`, { pages: next });
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["admin-order", String(order.id)], data.order);
      toast.success(data.label);
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const replaceMutation = useMutation({
    mutationFn: async (upload: File) => {
      const body = new FormData();
      body.append("file", upload);
      const { data } = await api.post<Order>(
        `/admin/orders/${order.id}/files/${file.id}/replace/`, body);
      return data;
    },
    onSuccess: () => {
      toast.success(`${file.file_name} replaced with the converted file.`);
      queryClient.invalidateQueries({ queryKey: ["admin-order", String(order.id)] });
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const spec = file.specification;

return (
    <div className="rounded-lg border">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b bg-muted/40 p-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="mt-0.5 rounded-md bg-background p-1.5">
            {file.file_type === "image"
              ? <ImageIcon className="h-4 w-4" />
              : <FileText className="h-4 w-4" />}
          </div>
          <div className="min-w-0">
            <p className="truncate font-medium">{file.file_name}</p>
            <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
              <span>{formatBytes(file.size)}</span>
              <span>·</span>
              <span>{file.file_type === "document" ? "Office document" : `${file.page_count} page(s)`}</span>
              {file.page_selection_active && (
                <Badge variant="secondary" className="text-[10px]">
                  {formatPageRange(file.selected_pages)}
                </Badge>
              )}
            </p>
            {spec && (
              <p className="mt-1 text-xs text-muted-foreground">
                {spec.media_size.replace("ps_", "").toUpperCase()} · {spec.media_type.replace("pt_", "")} ·{" "}
                {spec.color_mode === "color" ? "Colour" : "B&W"} ·{" "}
                {spec.copies} cop{spec.copies === 1 ? "y" : "ies"} ·{" "}
                {spec.sides === "none" ? "single-sided" : "double-sided"}
              </p>
            )}
            {spec?.free_text_instructions && (
              <p className="mt-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
                “{spec.free_text_instructions}”
              </p>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => onPreview(file)}>
            <Eye className="mr-2 h-4 w-4" /> Preview
          </Button>
          {!file.print_ready && (
            <Button variant="outline" size="sm"
              onClick={() => replaceInput.current?.click()}
              disabled={replaceMutation.isPending}>
              <FileUp className="mr-2 h-4 w-4" /> Upload PDF
            </Button>
          )}
          <input ref={replaceInput} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden"
            onChange={(event) => {
              const chosen = event.target.files?.[0];
              if (chosen) replaceMutation.mutate(chosen);
              event.target.value = "";
            }} />
        </div>
      </div>

      <div className="space-y-3 p-3">
        {!file.print_ready && (
          <p className="flex items-start gap-2 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              The printer only accepts PDF and image files. Read it here to check the
              content, then upload the converted PDF before approving this order.
            </span>
          </p>
        )}

        {file.replaced_by_admin && (
          <p className="text-xs text-emerald-700">
            The shop replaced the original upload with this converted file.
          </p>
        )}

        {file.file_type === "pdf" && file.page_count > 1 && (
          <PageSelector
            pageCount={file.page_count}
            selected={pages}
            saving={pagesMutation.isPending}
            disabled={locked}
            disabledReason="This file has already gone to the printer. Reprint to change pages."
            onSave={(next) => pagesMutation.mutateAsync(next)}
          />
        )}

        {file.has_edits && (
          <details className="text-xs">
            <summary className="cursor-pointer text-muted-foreground">
              {file.edit_actions.length} edit(s) applied by the customer
            </summary>
            <ul className="mt-1 space-y-0.5 pl-4 text-muted-foreground">
              {file.edit_actions.map((edit, index) => (
                <li key={index}>
                  {edit.action}
                  {edit.pages ? `: ${String(edit.pages)}` : ""}
                  {edit.paper_size ? `: ${String(edit.paper_size)}` : ""}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}