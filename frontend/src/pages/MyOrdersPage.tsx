import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Order } from "@/lib/types";

export default function MyOrdersPage() {
  const { data: orders, isLoading } = useQuery({
    queryKey: ["my-orders"],
    queryFn: async () => {
      const { data } = await api.get<Order[]>("/orders/mine/");
      return data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">My Orders</h1>
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
            <p className="text-muted-foreground">You haven't placed any orders yet.</p>
            <Button asChild className="mt-4">
              <Link to="/order">Place your first order</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
