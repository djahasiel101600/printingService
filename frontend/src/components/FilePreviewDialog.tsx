import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle, ChevronLeft, ChevronRight, Download, FileText, Loader2,
  RotateCw, Table2, ZoomIn, ZoomOut,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { API_URL, api } from "@/lib/api";
import { formatBytes, formatPageRange } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { DocumentPreview, FileVariant, OrderFile, PreviewBlock } from "@/lib/types";

interface FilePreviewDialogProps {
  file: OrderFile | null;
  orderId: number;
  /** Guest orders prove ownership with the tracking ID. */
  trackingId?: string;
  /** Staff can flip between the original, the customer edit and the shop file. */
  allowVariants?: boolean;
  onClose: () => void;
}

const VARIANT_LABELS: Record<FileVariant, string> = {
  original: "Original",
  edited: "Edited",
  final: "To print",
};

/** Which revision makes sense to show first for a given file. */
function defaultVariant(file: OrderFile): FileVariant {
  if (file.has_final_file) return "final";
  if (file.has_edits) return "edited";
  return "original";
}

/**
 * Path *relative to the axios `baseURL`*, which is how every other call in the
 * app is written (`/orders/...`, `/admin/orders/...`). The leading slash matters:
 * axios joins it onto `baseURL` exactly once, so `/api` + `/orders/1/...`
 * becomes `/api/orders/1/...`. Prepending `baseURL` here as well would produce
 * a doubled prefix (`/api/api/orders/...`) and a 404 from the proxy.
 */
export function buildFilePath(
  orderId: number,
  fileId: number,
  opts: { variant?: FileVariant; download?: boolean; trackingId?: string } = {},
): string {
  const params = new URLSearchParams();
  if (opts.variant) params.set("variant", opts.variant);
  if (opts.download) params.set("download", "1");
  if (opts.trackingId) params.set("tracking_id", opts.trackingId);
  const query = params.toString();
  return `/orders/${orderId}/files/${fileId}/preview/${query ? `?${query}` : ""}`;
}

/**
 * Fully-qualified URL for places where axios is *not* involved (a plain
 * `<a href>`, `window.open`, copying a link). When the API is same-origin the
 * result is an absolute path (`/api/orders/...`) that the browser resolves
 * against the current host, so it stays correct behind the tunnel and in dev.
 */
export function buildFileUrl(
  orderId: number,
  fileId: number,
  opts: { variant?: FileVariant; download?: boolean; trackingId?: string } = {},
): string {
  return `${API_URL.replace(/\/+$/, "")}${buildFilePath(orderId, fileId, opts)}`;
}

/**
 * Fetches a file through axios (so the JWT header rides along) and hands back an
 * object URL. A plain <img src> would be rejected, because the preview endpoint
 * authenticates via the Authorization header rather than a query token.
 */
async function fetchBlobUrl(url: string): Promise<string> {
  const response = await api.get<Blob>(url, { responseType: "blob" });
  return URL.createObjectURL(response.data);
}

/**
 * Download a file without leaking the Authorization header into the address
 * bar. `window.open(url)` cannot send bearer tokens, so signed-in staff would
 * get a 403; going through axios keeps the header on the request and the blob
 * never leaves the page. Guests still work because the tracking ID travels as
 * a query parameter.
 */
async function downloadFile(
  url: string,
  filename: string,
  onError: (message: string) => void,
): Promise<void> {
  try {
    const response = await api.get<Blob>(url, { responseType: "blob" });
    const href = URL.createObjectURL(response.data);
    const link = document.createElement("a");
    link.href = href;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Give the browser a moment to start the save before releasing the URL.
    setTimeout(() => URL.revokeObjectURL(href), 10_000);
  } catch {
    onError("The download could not be started. Please try again.");
  }
}

export default function FilePreviewDialog({
  file, orderId, trackingId, allowVariants = false, onClose,
}: FilePreviewDialogProps) {
  const [variant, setVariant] = useState<FileVariant>("original");
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [downloading, setDownloading] = useState(false);

  const open = Boolean(file);

  // Reset the controls whenever a different file is opened.
  useEffect(() => {
    if (!file) return;
    setVariant(defaultVariant(file));
    setPage(1);
    setZoom(1);
    setRotation(0);
  }, [file]);

  const fileId = file?.id;
  const isDocument = file?.file_type === "document";
  const isPdf = file?.file_type === "pdf";
  const totalPages = file?.page_count ?? 1;

  const variantPath = useMemo(
    () => (fileId ? buildFilePath(orderId, fileId, { variant, trackingId }) : ""),
    [orderId, fileId, variant, trackingId],
  );

  const blobQuery = useQuery({
    queryKey: ["file-blob", orderId, fileId, variant],
    enabled: open && Boolean(fileId) && !isDocument,
    queryFn: () => fetchBlobUrl(variantPath),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const contentsQuery = useQuery({
    queryKey: ["file-contents", orderId, fileId],
    enabled: open && Boolean(fileId) && Boolean(isDocument),
    queryFn: async () => {
      const { data } = await api.get<DocumentPreview>(
        `/orders/${orderId}/files/${fileId}/contents/`,
        { params: trackingId ? { tracking_id: trackingId } : undefined });
      return data;
    },
    retry: false,
  });

  // Object URLs are a leak until revoked — release the previous one on change.
  useEffect(() => () => {
    if (blobQuery.data) URL.revokeObjectURL(blobQuery.data);
  }, [blobQuery.data]);

  const download = useCallback(() => {
    if (!fileId || !file) return;
    setDownloading(true);
    void downloadFile(
      buildFilePath(orderId, fileId, { variant, trackingId }),
      file.file_name,
      (message) => toast.error(message),
    ).finally(() => setDownloading(false));
  }, [file, fileId, orderId, variant, trackingId]);

  const variants: FileVariant[] = useMemo(() => {
    if (!file || !allowVariants) return [];
    const list: FileVariant[] = ["original"];
    if (file.has_edits) list.push("edited");
    if (file.has_final_file) list.push("final");
    return list;
  }, [file, allowVariants]);

  if (!file) return null;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex max-h-[92vh] w-[95vw] max-w-6xl flex-col gap-3 overflow-hidden p-4">
        <DialogHeader className="pr-8">
          <DialogTitle className="truncate text-base">{file.file_name}</DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            <span>{formatBytes(file.size)}</span>
            <span>{isPdf ? `${totalPages} page${totalPages === 1 ? "" : "s"}` : file.file_type}</span>
            {file.page_selection_active && (
              <span className="font-medium text-indigo-700">
                Printing pages {formatPageRange(file.selected_pages)}
              </span>
            )}
            {file.replaced_by_admin && (
              <span className="inline-flex items-center gap-1 text-emerald-700">
                <FileText className="h-3 w-3" /> converted by the shop
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2 border-y py-2">
          {variants.length > 1 && (
            <div className="flex overflow-hidden rounded-md border">
              {variants.map((option) => (
                <button key={option} type="button"
                  onClick={() => { setVariant(option); setPage(1); }}
                  className={cn("px-3 py-1.5 text-xs font-medium transition-colors",
                    option === variant ? "bg-primary text-primary-foreground" : "hover:bg-accent")}>
                  {VARIANT_LABELS[option]}
                </button>
              ))}
            </div>
          )}
          {isPdf && totalPages > 1 && (
            <PageStepper page={page} total={totalPages} onChange={setPage} />
          )}
          {!isDocument && (
            <ZoomControls zoom={zoom} setZoom={setZoom}
              rotation={rotation} setRotation={setRotation} />
          )}
          <div className="ml-auto flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={download} disabled={downloading}>
              {downloading
                ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                : <Download className="mr-2 h-4 w-4" />}
              Download
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
          </div>
        </div>

        <PreviewBody
          isDocument={Boolean(isDocument)} isPdf={Boolean(isPdf)}
          page={page} zoom={zoom} rotation={rotation} fileName={file.file_name}
          objectUrl={blobQuery.data} blobQuery={blobQuery} contentsQuery={contentsQuery}
        />
      </DialogContent>
    </Dialog>
  );
}

function PageStepper({ page, total, onChange }: {
  page: number; total: number; onChange: (page: number) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <Button variant="outline" size="icon" className="h-8 w-8" disabled={page <= 1}
        onClick={() => onChange(Math.max(1, page - 1))} aria-label="Previous page">
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <span className="min-w-[5rem] text-center text-xs tabular-nums">
        Page {page} of {total}
      </span>
      <Button variant="outline" size="icon" className="h-8 w-8" disabled={page >= total}
        onClick={() => onChange(Math.min(total, page + 1))} aria-label="Next page">
        <ChevronRight className="h-4 w-4" />
      </Button>
      <input type="range" min={1} max={total} value={page} className="w-28"
        onChange={(event) => onChange(Number(event.target.value))} aria-label="Page" />
    </div>
  );
}

function ZoomControls({ zoom, setZoom, rotation, setRotation }: {
  zoom: number; setZoom: (value: number) => void;
  rotation: number; setRotation: (value: number) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <Button variant="outline" size="icon" className="h-8 w-8"
        onClick={() => setZoom(Math.max(0.25, +(zoom - 0.25).toFixed(2)))} aria-label="Zoom out">
        <ZoomOut className="h-4 w-4" />
      </Button>
      <span className="min-w-[3.5rem] text-center text-xs tabular-nums">
        {Math.round(zoom * 100)}%
      </span>
      <Button variant="outline" size="icon" className="h-8 w-8"
        onClick={() => setZoom(Math.min(4, +(zoom + 0.25).toFixed(2)))} aria-label="Zoom in">
        <ZoomIn className="h-4 w-4" />
      </Button>
      <Button variant="outline" size="icon" className="h-8 w-8"
        onClick={() => setRotation((rotation + 90) % 360)} aria-label="Rotate">
        <RotateCw className="h-4 w-4" />
      </Button>
    </div>
  );
}

interface PreviewBodyProps {
  isDocument: boolean;
  isPdf: boolean;
  page: number;
  zoom: number;
  rotation: number;
  fileName: string;
  objectUrl?: string;
  blobQuery: UseQueryResult<string, Error>;
  contentsQuery: UseQueryResult<DocumentPreview, Error>;
}

function PreviewBody(props: PreviewBodyProps) {
  const { isDocument, isPdf, page, zoom, rotation, fileName, objectUrl, blobQuery, contentsQuery } = props;
  return (
    <div className="min-h-0 flex-1 overflow-auto rounded-md bg-muted/40">
      {isDocument ? (
        <DocumentBody query={contentsQuery} />
      ) : blobQuery.isError ? (
        <PreviewError message="We could not open this file." onRetry={() => blobQuery.refetch()} />
      ) : !objectUrl ? (
        <div className="flex h-full min-h-[24rem] items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isPdf ? (
        // The browser's built-in viewer gives real zoom and text selection; we
        // only drive the page cursor through the #page fragment.
        <iframe key={`${objectUrl}-${page}-${zoom}`}
          src={`${objectUrl}#page=${page}&zoom=${Math.round(zoom * 100)}&toolbar=1`}
          title={`Preview of ${fileName}`}
          className="h-full min-h-[24rem] w-full" />
      ) : (
        <div className="flex min-h-[24rem] items-center justify-center p-4">
          <img src={objectUrl} alt={fileName}
            style={{ transform: `rotate(${rotation}deg) scale(${zoom})` }}
            className="max-h-[70vh] max-w-full object-contain transition-transform" />
        </div>
      )}
    </div>
  );
}

function PreviewError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex h-full min-h-[24rem] flex-col items-center justify-center gap-3 p-6 text-center">
      <AlertTriangle className="h-8 w-8 text-amber-500" />
      <p className="text-sm text-muted-foreground">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>
    </div>
  );
}

function DocumentBody({ query }: { query: UseQueryResult<DocumentPreview, Error> }) {
  if (query.isError) {
    const error = query.error as {
      response?: { status?: number; data?: { detail?: string } };
    };
    if (error?.response?.status === 404) {
      // The endpoint was added with document previews; an older backend image
      // has no such route. Say so instead of showing a bare "not found".
      return <PreviewError
        message="This server does not have document preview yet. Rebuild and restart the backend image (docker compose up -d --build), or open the file directly."
        onRetry={() => query.refetch()} />;
    }
    return <PreviewError message={error?.response?.data?.detail ?? "We could not read this document."}
      onRetry={() => query.refetch()} />;
  }
  if (!query.data) {
    return (
      <div className="flex h-full min-h-[24rem] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const { blocks, truncated, kind } = query.data;
  if (!blocks.length) {
    return (
      <div className="flex h-full min-h-[24rem] items-center justify-center p-6 text-sm text-muted-foreground">
        This document appears to be empty.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 bg-background p-5">
      {truncated && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Showing the beginning of this document only.
        </p>
      )}
      {kind === "spreadsheet" && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Table2 className="h-3.5 w-3.5" /> Spreadsheet preview — cell contents only.
        </p>
      )}
      {blocks.map((block, index) => <PreviewBlockView key={index} block={block} />)}
    </div>
  );
}

const HEADING_CLASSES = [
  "text-lg", "text-xl", "text-lg", "text-base", "text-base", "text-sm", "text-sm",
];

function PreviewBlockView({ block }: { block: PreviewBlock }) {
  switch (block.type) {
    case "heading": {
      const index = Math.min(HEADING_CLASSES.length - 1, Math.max(0, (block.level ?? 2) - 1));
      return <p className={cn("mt-4 font-semibold first:mt-0", HEADING_CLASSES[index])}>
        {block.text}</p>;
    }
    case "spacer":
      return <div className="h-3" />;
    case "table":
      return (
        <div className="overflow-x-auto rounded-md border">
          {block.label && (
            <p className="border-b bg-muted/50 px-3 py-1.5 text-xs font-medium">{block.label}</p>
          )}
          <table className="w-full border-collapse text-xs">
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex} className={rowIndex === 0 ? "bg-muted/30" : ""}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="border-t px-3 py-1.5 align-top">
                      {cell || "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "slide":
      return (
        <div className="rounded-md border p-3">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {block.label}
          </p>
          <p className="font-medium">{block.title}</p>
          {block.items.length > 1 && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
              {block.items.slice(1).map((item, index) => <li key={index}>{item}</li>)}
            </ul>
          )}
        </div>
      );
    default:
      return <p className="whitespace-pre-wrap text-sm leading-relaxed">{block.text}</p>;
  }
}