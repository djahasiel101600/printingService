import { useEffect, useState } from "react";
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
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api";
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

function OrderCard({ order }: { order: Order }) {
  const flags = attentionFor(order);
  const hasUrgent = flags.some((f) => f.tone === "urgent");
  const fileCount = order.files.length;
  const pageCount = order.files.reduce(
    (total, f) => total + f.selected_page_count,
    0,
  );

  return (
    <Card
      className={cn(
        "group relative overflow-hidden transition-colors hover:bg-muted/40",
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
              className="block truncate font-semibold leading-tight outline-none after:absolute after:inset-0 after:content-['']"
            >
              {order.tracking_id}
            </Link>
            <p className="truncate text-sm text-foreground/80">
              {order.client_name}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StatusBadge status={order.status} display={order.status_display} />
            <ChevronRight
              aria-hidden
              className="hidden h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 sm:block"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <p className="flex items-center gap-1.5">
            <FileText aria-hidden className="h-3.5 w-3.5" />
            <span>
              {fileCount} {fileCount === 1 ? "file" : "files"}, {pageCount}{" "}
              {pageCount === 1 ? "page" : "pages"}
            </span>
          </p>
          <p className="flex items-baseline gap-3">
            <time dateTime={order.created_at} className="text-xs">
              {formatDate(order.created_at)}
            </time>
            <span className="font-semibold tabular-nums text-foreground">
              {peso(order.subtotal_peso)}
            </span>
          </p>
        </div>

        {flags.length > 0 && (
          <ul
            aria-label="Needs attention"
            className="flex flex-wrap gap-1.5 border-t pt-3"
          >
            {flags.map((flag) => (
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

export default function AdminOrdersPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  // Debounced search so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const handle = setTimeout(() => setSearch(searchInput.trim()), 350);
    return () => clearTimeout(handle);
  }, [searchInput]);

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Orders</h1>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {orders
              ? `${orders.length} ${orders.length === 1 ? "order" : "orders"} · ${activeLabel}`
              : "Loading orders…"}
            {isRefreshing && (
              <Loader2
                aria-hidden
                className="ml-2 inline h-3 w-3 animate-spin"
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
          >
            <RefreshCw
              aria-hidden
              className={cn(
                "mr-2 h-4 w-4",
                syncMutation.isPending && "animate-spin",
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

      {/* Search */}
      <div className="relative w-full sm:max-w-md">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          aria-label="Search orders"
          placeholder="Search tracking ID, name, email or phone…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="pl-9 pr-9 [&::-webkit-search-cancel-button]:hidden"
        />
        {searchInput && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Clear search"
            onClick={() => setSearchInput("")}
            className="absolute right-1 top-1/2 h-7 w-7 -translate-y-1/2 text-muted-foreground"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Status filter: scrolls sideways on small screens instead of wrapping into a tall block */}
      <Tabs value={tab} onValueChange={setTab}>
        <div className="-mx-4 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
          <TabsList className="h-auto w-max justify-start">
            {ADMIN_STATUSES.map((s) => (
              <TabsTrigger
                key={s.value}
                value={s.value}
                className="whitespace-nowrap"
              >
                {s.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </Tabs>

      {/* Results */}
      {isLoading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading orders">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
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
            "space-y-3 transition-opacity",
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
            {search ? (
              <SearchX aria-hidden className="h-8 w-8 text-muted-foreground" />
            ) : (
              <Inbox aria-hidden className="h-8 w-8 text-muted-foreground" />
            )}
            <div className="space-y-1">
              <p className="font-medium">
                {search
                  ? `No orders match "${search}"`
                  : `No ${activeLabel.toLowerCase()} orders`}
              </p>
              <p className="text-sm text-muted-foreground">
                {search
                  ? "Try a different tracking ID, name, email or phone number."
                  : tab
                    ? "Nothing in this queue right now."
                    : "New orders will appear here."}
              </p>
            </div>
            {(search || tab) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchInput("");
                  setSearch("");
                  setTab("");
                }}
              >
                Clear search and filters
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
