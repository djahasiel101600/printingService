import { useEffect, useRef, useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  AlertTriangle,
  ChevronRight,
  FileText,
  Info,
  Inbox,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  SearchX,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, apiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Order } from "@/lib/types";

const ADMIN_STATUSES = [
  { value: "", label: "All" },
  { value: "pending_review", label: "Pending review" },
  { value: "revision_requested", label: "Revision" },
  { value: "print_cancelled", label: "Cancelled at printer" },
  { value: "approved_queued", label: "Approved / Queued" },
  { value: "printing", label: "Printing" },
  { value: "on_hold", label: "On hold" },
  { value: "printed_ready", label: "Ready for pickup" },
  { value: "completed", label: "Completed" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled" },
];

// Queues that usually need an admin to act; shown with a small dot in the filter bar.
const NEEDS_ACTION = new Set([
  "pending_review",
  "revision_requested",
  "print_cancelled",
]);

type Flag = { text: string; tone: "urgent" | "info" };

/** Things an admin should notice before opening an order. */
function attentionFor(order: Order): Flag[] {
  const flags: Flag[] = [];
  if (order.status === "print_cancelled")
    flags.push({ text: "Printer cancelled — reprint needed", tone: "urgent" });
  const blocked = order.files.filter((f) => !f.print_ready);
  if (blocked.length)
    flags.push({
      text: `${blocked.length} file(s) need converting to PDF`,
      tone: "urgent",
    });
  if (order.files.some((f) => f.page_selection_active))
    flags.push({ text: "Page selection applied", tone: "info" });
  // Files the client swapped out after a revision request — the shop should
  // re-inspect the new bytes before approving.
  const revised = order.files.filter((f) => (f.current_version ?? 1) > 1);
  if (revised.length)
    flags.push({
      text: `${revised.length} file(s) revised by client`,
      tone: "info",
    });
  if (order.reprint_count > 0)
    flags.push({ text: `Reprinted ${order.reprint_count}×`, tone: "info" });
  return flags;
}

const peso = (n: number) =>
  `₱${n.toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

/** "5 minutes ago", "yesterday" — falls back to a short date after a week. */
function formatRelative(iso: string) {
  const diffSec = (new Date(iso).getTime() - Date.now()) / 1000;
  const abs = Math.abs(diffSec);
  if (abs < 60) return "just now";
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
  if (abs < 7 * 86400) return rtf.format(Math.round(diffSec / 86400), "day");
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function OrderCard({ order }: { order: Order }) {
  const flags = attentionFor(order);
  const hasUrgent = flags.some((f) => f.tone === "urgent");
  // Urgent items first so they're the first thing scanned.
  const sortedFlags = [...flags].sort(
    (a, b) => Number(b.tone === "urgent") - Number(a.tone === "urgent"),
  );
  const fileCount = order.files.length;
  const pageCount = order.files.reduce(
    (total, f) => total + f.selected_page_count,
    0,
  );

  return (
    <Card
      className={cn(
        "group relative overflow-hidden transition-all motion-reduce:transition-none",
        "hover:-translate-y-px hover:border-foreground/20 hover:bg-muted/40 hover:shadow-sm motion-reduce:hover:translate-y-0",
        "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
        hasUrgent && "border-l-4 border-l-amber-500",
      )}
    >
      <CardContent className="space-y-3 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-0.5">
            {/* Stretched link: the whole card is clickable, one tab stop per order. */}
            <Link
              to={`/admin/orders/${order.id}`}
              className="block truncate font-mono text-[0.95rem] font-semibold leading-tight tracking-tight outline-none group-hover:underline group-hover:underline-offset-4 after:absolute after:inset-0 after:content-['']"
            >
              {order.tracking_id}
              <span className="sr-only">, order for {order.client_name}</span>
            </Link>
            <p className="truncate text-sm text-foreground/80">
              {order.client_name}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StatusBadge status={order.status} display={order.status_display} />
            <ChevronRight
              aria-hidden
              className="hidden h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none sm:block"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <FileText aria-hidden className="h-3.5 w-3.5" />
            <span>
              {fileCount} {fileCount === 1 ? "file" : "files"} · {pageCount}{" "}
              {pageCount === 1 ? "page" : "pages"}
            </span>
          </p>
          <p className="flex items-baseline gap-3">
            <time
              dateTime={order.created_at}
              title={formatDate(order.created_at)}
              className="text-xs"
            >
              {formatRelative(order.created_at)}
            </time>
            <span className="text-base font-semibold tabular-nums text-foreground">
              {peso(order.subtotal_peso)}
            </span>
          </p>
        </div>

        {sortedFlags.length > 0 && (
          <ul
            aria-label="Needs attention"
            className="flex flex-wrap gap-1.5 border-t pt-3"
          >
            {sortedFlags.map((flag) => (
              <li
                key={flag.text}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
                  flag.tone === "urgent"
                    ? "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {flag.tone === "urgent" ? (
                  <AlertTriangle aria-hidden className="h-3 w-3" />
                ) : (
                  <Info aria-hidden className="h-3 w-3" />
                )}
                {flag.text}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function OrderCardSkeleton() {
  return (
    <Card>
      <CardContent className="space-y-3 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-3.5 w-24" />
          </div>
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-3.5 w-28" />
          <Skeleton className="h-4 w-20" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminOrdersPage() {
  const queryClient = useQueryClient();
  const searchRef = useRef<HTMLInputElement>(null);
  const tabsScrollRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  // Debounced search so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const handle = setTimeout(() => setSearch(searchInput.trim()), 350);
    return () => clearTimeout(handle);
  }, [searchInput]);

  // Press "/" anywhere (outside a text field) to jump to search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (
        el &&
        (el.tagName === "INPUT" ||
          el.tagName === "TEXTAREA" ||
          el.isContentEditable)
      )
        return;
      e.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Keep the selected status visible when the tab strip scrolls sideways.
  useEffect(() => {
    const active = tabsScrollRef.current?.querySelector<HTMLElement>(
      '[data-state="active"]',
    );
    active?.scrollIntoView({
      inline: "center",
      block: "nearest",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
    });
  }, [tab]);

  const {
    data: orders,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["admin-orders", tab, search],
    // Keep showing the previous list while a new tab/search loads, so the page doesn't flash.
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tab) params.set("status", tab);
      if (search) params.set("search", search);
      const qs = params.toString();
      const { data } = await api.get<Order[]>(
        `/admin/orders/${qs ? `?${qs}` : ""}`,
      );
      return data;
    },
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      await api.post("/admin/print-jobs/");
    },
    onSuccess: () => {
      toast.success("Print job statuses synced.");
      queryClient.invalidateQueries({ queryKey: ["admin-orders"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const activeLabel =
    ADMIN_STATUSES.find((s) => s.value === tab)?.label ?? "All";
  const isRefreshing = isFetching && !isLoading;
  const isTyping = searchInput.trim() !== search;
  const hasFilters = Boolean(search || tab);

  const clearAll = () => {
    setSearchInput("");
    setSearch("");
    setTab("");
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">Orders</h1>
          <p
            className="flex items-center text-sm text-muted-foreground"
            aria-live="polite"
          >
            {orders ? (
              <>
                <span className="font-medium tabular-nums text-foreground">
                  {orders.length}
                </span>
                &nbsp;{orders.length === 1 ? "order" : "orders"}
                <span aria-hidden className="mx-1.5">
                  ·
                </span>
                {activeLabel}
                {search && (
                  <>
                    <span aria-hidden className="mx-1.5">
                      ·
                    </span>
                    matching “{search}”
                  </>
                )}
              </>
            ) : (
              "Loading orders…"
            )}
            {(isRefreshing || isTyping) && (
              <Loader2
                aria-hidden
                className="ml-2 h-3 w-3 animate-spin motion-reduce:animate-none"
              />
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            title="Fetch the latest status from the printers"
          >
            <RefreshCw
              aria-hidden
              className={cn(
                "mr-2 h-4 w-4",
                syncMutation.isPending &&
                  "animate-spin motion-reduce:animate-none",
              )}
            />
            {syncMutation.isPending ? "Syncing…" : "Sync printers"}
          </Button>
          <Button asChild size="sm">
            <Link to="/admin/orders/new">
              <Plus aria-hidden className="mr-2 h-4 w-4" /> New order
            </Link>
          </Button>
        </div>
      </div>

      {/* Filters stay visible while scrolling a long list */}
      <div className="sticky top-0 z-10 -mx-4 space-y-2.5 border-b bg-background/90 px-4 py-3 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/70 sm:mx-0 sm:rounded-lg sm:border sm:px-3">
        <div className="relative w-full sm:max-w-md">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            ref={searchRef}
            type="search"
            aria-label="Search orders"
            aria-keyshortcuts="/"
            placeholder="Search tracking ID, name, email or phone…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape" && searchInput) {
                e.preventDefault();
                setSearchInput("");
              }
            }}
            className="pl-9 pr-16 [&::-webkit-search-cancel-button]:hidden"
          />
          {searchInput ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Clear search"
              onClick={() => {
                setSearchInput("");
                searchRef.current?.focus();
              }}
              className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 text-muted-foreground"
            >
              <X className="h-4 w-4" />
            </Button>
          ) : (
            <kbd
              aria-hidden
              className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:block"
            >
              /
            </kbd>
          )}
        </div>

        {/* Status filter: pill tabs that scroll sideways (with faded edges) instead of wrapping */}
        <Tabs value={tab} onValueChange={setTab}>
          <div
            ref={tabsScrollRef}
            className={cn(
              "-mx-4 overflow-x-auto px-4 py-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
              "[mask-image:linear-gradient(to_right,transparent,black_16px,black_calc(100%-16px),transparent)]",
              "sm:mx-0 sm:px-0 sm:[mask-image:none]",
            )}
          >
            <TabsList className="h-auto w-max justify-start gap-1.5 bg-transparent p-0">
              {ADMIN_STATUSES.map((s) => (
                <TabsTrigger
                  key={s.value}
                  value={s.value}
                  className={cn(
                    "gap-1.5 whitespace-nowrap rounded-full border border-transparent bg-muted/60 px-3 py-1 text-[13px] text-muted-foreground transition-colors motion-reduce:transition-none",
                    "hover:bg-muted hover:text-foreground",
                    "data-[state=active]:border-primary data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-none",
                  )}
                >
                  {NEEDS_ACTION.has(s.value) && (
                    <span
                      aria-hidden
                      className="h-1.5 w-1.5 rounded-full bg-amber-500"
                    />
                  )}
                  {s.label}
                  {NEEDS_ACTION.has(s.value) && (
                    <span className="sr-only"> (needs action)</span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
        </Tabs>

        {/* Active filters, each removable on its own */}
        {hasFilters && (
          <div
            role="group"
            aria-label="Active filters"
            className="flex flex-wrap items-center gap-1.5 text-xs"
          >
            <span className="text-muted-foreground">Filtering by</span>
            {tab && (
              <span className="inline-flex items-center gap-1 rounded-full border bg-background py-0.5 pl-2.5 pr-1 font-medium">
                Status: {activeLabel}
                <button
                  type="button"
                  aria-label={`Remove status filter: ${activeLabel}`}
                  onClick={() => setTab("")}
                  className="rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X aria-hidden className="h-3 w-3" />
                </button>
              </span>
            )}
            {search && (
              <span className="inline-flex max-w-[16rem] items-center gap-1 rounded-full border bg-background py-0.5 pl-2.5 pr-1 font-medium">
                <span className="truncate">“{search}”</span>
                <button
                  type="button"
                  aria-label={`Remove search filter: ${search}`}
                  onClick={() => {
                    setSearchInput("");
                    setSearch("");
                  }}
                  className="shrink-0 rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X aria-hidden className="h-3 w-3" />
                </button>
              </span>
            )}
            {tab && search && (
              <Button
                type="button"
                variant="link"
                size="sm"
                onClick={clearAll}
                className="h-auto px-1 py-0 text-xs"
              >
                Clear all
              </Button>
            )}
          </div>
        )}
      </div>

      {/* A refresh failed but we still have a list to show */}
      {isError && orders && (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm"
        >
          <span className="flex items-center gap-2 text-destructive">
            <AlertTriangle aria-hidden className="h-4 w-4" />
            Couldn't refresh — showing the last loaded results.
          </span>
          <Button variant="ghost" size="sm" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {/* Results */}
      {isLoading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading orders">
          {Array.from({ length: 5 }).map((_, i) => (
            <OrderCardSkeleton key={i} />
          ))}
        </div>
      ) : isError && !orders ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <AlertTriangle aria-hidden className="h-8 w-8 text-destructive" />
            <div className="space-y-1">
              <p className="font-medium">Couldn't load orders</p>
              <p className="text-sm text-muted-foreground">
                Check your connection and try again.
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Try again
            </Button>
          </CardContent>
        </Card>
      ) : orders && orders.length > 0 ? (
        <ul
          className={cn(
            "space-y-3 transition-opacity motion-reduce:transition-none",
            isRefreshing && "opacity-60",
          )}
        >
          {orders.map((order) => (
            <li key={order.id}>
              <OrderCard order={order} />
            </li>
          ))}
        </ul>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <div className="rounded-full bg-muted p-3">
              {search ? (
                <SearchX
                  aria-hidden
                  className="h-6 w-6 text-muted-foreground"
                />
              ) : (
                <Inbox aria-hidden className="h-6 w-6 text-muted-foreground" />
              )}
            </div>
            <div className="space-y-1">
              <p className="font-medium">
                {search
                  ? `No orders match "${search}"`
                  : tab
                    ? `No ${activeLabel.toLowerCase()} orders`
                    : "No orders yet"}
              </p>
              <p className="text-sm text-muted-foreground">
                {search
                  ? "Try a different tracking ID, name, email or phone number."
                  : tab
                    ? "Nothing in this queue right now."
                    : "New orders will appear here."}
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {hasFilters && (
                <Button variant="outline" size="sm" onClick={clearAll}>
                  Clear search and filters
                </Button>
              )}
              {!hasFilters && (
                <Button asChild size="sm">
                  <Link to="/admin/orders/new">
                    <Plus aria-hidden className="mr-2 h-4 w-4" /> Create an
                    order
                  </Link>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
