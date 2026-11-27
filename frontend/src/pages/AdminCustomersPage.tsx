import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Search, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import type { CustomerDirectoryPage } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

function useDebounced(value: string, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

const fullName = (customer: CustomerDirectoryPage["results"][number]) =>
  [customer.first_name, customer.last_name].filter(Boolean).join(" ");

/** Owner-only directory of everyone who registered through /register. */
export default function AdminCustomersPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const { data, isLoading, isFetching, isError } = useQuery({
    queryKey: ["admin-customer-directory", debouncedSearch, page],
    queryFn: async () => (await api.get<CustomerDirectoryPage>("/admin/customers/", {
      params: { search: debouncedSearch.trim(), page },
    })).data,
  });

  function updateSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  const customers = data?.results ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Customers</h1>
        <p className="text-muted-foreground">
          Registered accounts appear here automatically after sign-up. Guest checkout
          details remain on their orders and are not customer accounts.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Users className="h-4 w-4" /> Registered customers
          </CardTitle>
          <CardDescription>
            Search by name, email, phone number, or Facebook handle.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              type="search"
              aria-label="Search registered customers"
              placeholder="Search customers…"
              value={search}
              onChange={(event) => updateSearch(event.target.value)}
              className="pl-9"
            />
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading customers…
            </div>
          ) : isError ? (
            <p role="alert" className="py-8 text-sm text-destructive">
              Could not load customers. Please try again.
            </p>
          ) : customers.length === 0 ? (
            <p className="py-8 text-sm text-muted-foreground">
              {debouncedSearch ? "No customers match your search." : "No customers have signed up yet."}
            </p>
          ) : (
            <div className={isFetching ? "opacity-60" : undefined}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer</TableHead>
                    <TableHead>Contact</TableHead>
                    <TableHead>Signed up</TableHead>
                    <TableHead>Last sign-in</TableHead>
                    <TableHead>Last order</TableHead>
                    <TableHead className="text-right">Orders</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {customers.map((customer) => (
                    <TableRow key={customer.id}>
                      <TableCell>
                        <p className="font-medium">{fullName(customer) || "—"}</p>
                        <p className="text-xs text-muted-foreground">{customer.email}</p>
                      </TableCell>
                      <TableCell className="text-sm">
                        <p>{customer.phone || "—"}</p>
                        {customer.facebook_handle && (
                          <p className="text-xs text-muted-foreground">{customer.facebook_handle}</p>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDateTime(customer.date_joined)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {customer.last_login ? formatDateTime(customer.last_login) : "Never"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {customer.last_order_at ? formatDateTime(customer.last_order_at) : "Never"}
                      </TableCell>
                      <TableCell className="text-right font-medium">{customer.order_count}</TableCell>
                      <TableCell>
                        {customer.is_active ? (
                          <Badge className="bg-emerald-100 text-emerald-800">Active</Badge>
                        ) : (
                          <Badge variant="secondary">Disabled</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground" aria-live="polite">
              {data ? `${data.count} customer${data.count === 1 ? "" : "s"}` : "Customer directory"}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!data?.has_previous || isFetching}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {data?.page ?? page} of {data?.num_pages ?? 1}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={!data?.has_next || isFetching}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
