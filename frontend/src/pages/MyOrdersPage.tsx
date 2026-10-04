import { useQueries, useQuery } from "@tanstack/react-query";
import { FileText, PackageOpen } from "lucide-react";
import { Link } from "react-router-dom";

import { AsyncBoundary } from "@/components/AsyncBoundary";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
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
      <PageHeader
        title="My Orders"
        description={!user && "Orders placed on this device without an account."}
        actions={
          <Button asChild>
            <Link to="/order">
              <FileText className="h-4 w-4" />
              New Order
            </Link>
          </Button>
        }
      />

      <AsyncBoundary
        isLoading={isLoading}
        error={user ? myOrdersQuery.error : null}
        isEmpty={(orders?.length ?? 0) === 0}
        onRetry={() => myOrdersQuery.refetch()}
        skeleton={
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        }
        empty={
          <EmptyState
            icon={PackageOpen}
            title={user ? "You haven't placed any orders yet" : "No orders on this device yet"}
            description={
              user
                ? "Upload a file, choose your settings, and we'll review it before printing."
                : "Orders placed without an account are saved on this device."
            }
            action={
              <div className="flex flex-wrap justify-center gap-3">
                <Button asChild>
                  <Link to="/order">Place your first order</Link>
                </Button>
                {!user && (
                  <Button asChild variant="outline">
                    <Link to="/login">Log in to see account orders</Link>
                  </Button>
                )}
              </div>
            }
          />
        }
      >
        <div className="space-y-3">
          {orders?.map((order) => (
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
                {/* No `display` override: the customer reads our wording, not
                    the backend's choice label. */}
                <StatusBadge status={order.status} />
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <div className="text-muted-foreground">
                  {order.files.length} file(s) · ₱{order.subtotal_peso.toFixed(2)}
                  {order.balance_due_peso > 0 && (
                    <span className="ml-2 text-attention">
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
      </AsyncBoundary>
    </div>
  );
}
