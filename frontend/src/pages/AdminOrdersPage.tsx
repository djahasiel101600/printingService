import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Plus, RefreshCw, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api";
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

/** Things an admin should notice before opening an order. */
function attentionFor(order: Order): string[] {
  const flags: string[] = [];
  if (order.status === "print_cancelled") flags.push("printer cancelled — reprint needed");
  const blocked = order.files.filter((f) => !f.print_ready);
  if (blocked.length) flags.push(`${blocked.length} file(s) need converting to PDF`);
  if (order.files.some((f) => f.page_selection_active)) flags.push("page selection applied");
  if (order.reprint_count > 0) flags.push(`reprinted ${order.reprint_count}×`);
  return flags;
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

  const { data: orders, isLoading } = useQuery({
    queryKey: ["admin-orders", tab, search],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (tab) params.set("status", tab);
      if (search) params.set("search", search);
      const qs = params.toString();
      const { data } = await api.get<Order[]>(`/admin/orders/${qs ? `?${qs}` : ""}`);
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Admin — Orders</h1>
        <div className="flex items-center gap-2">
          <Button asChild size="sm">
            <Link to="/admin/orders/new">
              <Plus className="mr-2 h-4 w-4" /> New order for customer
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
            <RefreshCw className="mr-2 h-4 w-4" /> Sync printers
          </Button>
        </div>
      </div>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search tracking ID, name, email or phone…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="pl-9"
        />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex-wrap">
          {ADMIN_STATUSES.map((s) => (
            <TabsTrigger key={s.value} value={s.value}>{s.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      ) : orders && orders.length > 0 ? (
        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id} className="transition-shadow hover:shadow-md">
              <CardHeader className="flex-row items-start justify-between space-y-0 pb-2">
                <div className="min-w-0">
                  <CardTitle className="text-base">
                    <Link to={`/admin/orders/${order.id}`} className="hover:underline">
                      {order.tracking_id}
                    </Link>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {order.client_name} · {new Date(order.created_at).toLocaleString()}
                  </p>
                </div>
                <StatusBadge status={order.status} display={order.status_display} />
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <p className="text-muted-foreground">
                    {order.files.length} file(s) · {order.files.reduce(
                      (total, f) => total + f.selected_page_count, 0)} page(s) ·{" "}
                    <span className="font-medium text-foreground">
                      ₱{order.subtotal_peso.toFixed(2)}
                    </span>
                  </p>
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/admin/orders/${order.id}`}>Review</Link>
                  </Button>
                </div>
                {attentionFor(order).length > 0 && (
                  <ul className="flex flex-wrap gap-1.5">
                    {attentionFor(order).map((flag) => (
                      <li key={flag}
                        className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-800">
                        {flag}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {search ? `No orders match "${search}".` : "No orders in this queue."}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
