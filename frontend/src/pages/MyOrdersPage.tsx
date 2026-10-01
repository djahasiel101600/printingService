import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/components/auth";
import { api, loadGuestOrders } from "@/lib/api";
import type { Order } from "@/lib/types";

export default function MyOrdersPage() {
  const { user } = useAuth();
  const guestRefs = loadGuestOrders();

  // Signed in: one request for the account's orders.
  const myOrdersQuery = useQuery({
    queryKey: ["my-orders"],
    enabled: !!user,
    queryFn: async () => {
      const { data } = await api.get<Order[]>("/orders/mine/");
      return data;
    },
  });

  // Guest: fetch each order saved on this device, proving ownership with its
  // tracking ID. Orders that can no longer be read are dropped from the list.
  const guestQueries = useQueries({
    queries: guestRefs.map((ref) => ({
      queryKey: ["order", String(ref.id), `guest:${ref.tracking_id}`],
      retry: false,
      queryFn: async () => {
        const { data } = await api.get<Order>(`/orders/${ref.id}/`, {
          params: { tracking_id: ref.tracking_id },
        });
        return data;
      },
    })),
  });

  const guestOrders = guestQueries
    .map((q, i) => ({ q, ref: guestRefs[i] }))
    .filter((e) => e.q.isSuccess && e.q.data)
    .map((e) => e.q.data as Order)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  const orders = user ? myOrdersQuery.data : guestOrders;
  const isLoading = user
    ? myOrdersQuery.isLoading
    : guestQueries.some((q) => q.isPending && q.isFetching);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">My Orders</h1>
          {!user && (
            <p className="text-sm text-muted-foreground">
              Orders placed on this device without an account.
            </p>
          )}
        </div>
        <Button asChild>
          <Link to="/order">New Order</Link>
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : orders && orders.length > 0 ? (
        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id} className="transition-shadow hover:shadow-md">
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="text-base">
                    <Link to={`/orders/${order.id}`} className="hover:underline">
                      {order.tracking_id}
                    </Link>
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">
                    {new Date(order.created_at).toLocaleString()}
                  </p>
                </div>
                <StatusBadge status={order.status} display={order.status_display} />
              </CardHeader>
              <CardContent className="flex items-center justify-between text-sm">
                <div className="text-muted-foreground">
                  {order.files.length} file(s) · ₱{order.subtotal_peso.toFixed(2)}
                  {order.balance_due_peso > 0 && (
                    <span className="ml-2 text-amber-600">
                      (balance: ₱{order.balance_due_peso.toFixed(2)})
                    </span>
                  )}
                </div>
                <Button asChild variant="outline" size="sm">
                  <Link to={`/orders/${order.id}`}>View</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              {user
                ? "You haven't placed any orders yet."
                : "No orders found on this device yet."}
            </p>
            <div className="mt-4 flex justify-center gap-3">
              <Button asChild>
                <Link to="/order">Place your first order</Link>
              </Button>
              {!user && (
                <Button asChild variant="outline">
                  <Link to="/login">Log in to see account orders</Link>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
