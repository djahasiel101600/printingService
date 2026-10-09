import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarRange,
  Coins,
  Loader2,
  Receipt,
  RefreshCw,
  TrendingDown,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, apiErrorMessage } from "@/lib/api";
import type { SalesDailyPoint, SalesDashboard } from "@/lib/types";
import { cn, formatDateTime, formatPeso } from "@/lib/utils";

/** Raw payment-method key (snapshotted on the ledger) -> the words a human reads. */
const METHOD_LABELS: Record<string, string> = {
  qrph: "QR Ph",
  pickup: "Pay upon pickup",
  cash: "Cash",
};

const methodLabel = (method: string) =>
  METHOD_LABELS[method] ?? (method ? method : "—");

/** Local (not UTC) YYYY-MM-DD, matching the server's date window. */
function isoDate(date: Date): string {
  const tzOffsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - tzOffsetMs).toISOString().slice(0, 10);
}

const DAY_MS = 86_400_000;

const PRESETS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
];

/** One headline metric. Tone tints the icon + value with a status token. */
function StatCard({
  icon: Icon,
  label,
  value,
  tone = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: "default" | "success" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "danger"
        ? "text-destructive"
        : "text-foreground";
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-5">
        <Icon className={cn("h-5 w-5 shrink-0", toneClass)} aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className={cn("text-xl font-bold", toneClass)}>{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminSalesPage() {
  const [from, setFrom] = useState(() => isoDate(new Date(Date.now() - 29 * DAY_MS)));
  const [to, setTo] = useState(() => isoDate(new Date()));
  const [error, setError] = useState("");

  const { data, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ["sales-dashboard", from, to],
    queryFn: async () =>
      (
        await api.get<SalesDashboard>("/admin/sales/dashboard/", {
          params: { from, to },
        })
      ).data,
    enabled: Boolean(from && to) && !error,
    retry: false,
  });

  // Peak magnitude drives the bar heights so the chart always fills its
  // track. abs() keeps it sign-safe: a window that is net-refunded (peak < 0)
  // still scales its bars by their largest magnitude.
  const peak = useMemo(
    () => (data?.daily ?? []).reduce((m, p) => Math.max(m, Math.abs(p.net)), 0),
    [data],
  );

  function applyPreset(days: number) {
    setError("");
    const end = new Date();
    setTo(isoDate(end));
    setFrom(isoDate(new Date(end.getTime() - (days - 1) * DAY_MS)));
  }

  function validateDates(nextFrom: string, nextTo: string) {
    if (!nextFrom || !nextTo) {
      setError("Pick both a start and an end date.");
      return;
    }
    if (nextFrom > nextTo) {
      setError("The start date must not be after the end date.");
      return;
    }
    if (
      (new Date(nextTo).getTime() - new Date(nextFrom).getTime()) / DAY_MS >
      366
    ) {
      setError("Keep the range within 366 days.");
      return;
    }
    setError("");
  }

  return (
    <div className="space-y-6">
      {/* Header + date range controls */}
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Sales</h1>
          <p className="text-sm text-muted-foreground">
            Revenue taken from the append-only sales ledger — the shop&apos;s
            book of record. Refunds net off automatically.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="sales-from" className="text-xs">
              From
            </Label>
            <Input
              id="sales-from"
              type="date"
              value={from}
              max={to}
              onChange={(e) => {
                setFrom(e.target.value);
                validateDates(e.target.value, to);
              }}
              className="w-40"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sales-to" className="text-xs">
              To
            </Label>
            <Input
              id="sales-to"
              type="date"
              value={to}
              min={from}
              onChange={(e) => {
                setTo(e.target.value);
                validateDates(from, e.target.value);
              }}
              className="w-40"
            />
          </div>
          <div className="flex items-center gap-1.5">
            {PRESETS.map((preset) => (
              <Button
                key={preset.label}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => applyPreset(preset.days)}
              >
                <CalendarRange className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                {preset.label}
              </Button>
            ))}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-9 w-9"
              aria-label="Refresh"
              disabled={isFetching}
              onClick={() => refetch()}
            >
              <RefreshCw
                className={cn("h-4 w-4", isFetching && "animate-spin")}
                aria-hidden="true"
              />
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-6" aria-busy="true" aria-label="Loading sales">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[76px] w-full" />
            ))}
          </div>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : isError ? (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            We couldn&apos;t load the sales dashboard. Try refreshing.
          </AlertDescription>
        </Alert>
      ) : data ? (
        <>
          {/* Headline totals for the window. */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Wallet}
              label="Net sales"
              value={formatPeso(data.net / 100)}
              tone={data.net >= 0 ? "success" : "danger"}
            />
            <StatCard
              icon={Coins}
              label="Gross payments"
              value={formatPeso(data.gross / 100)}
            />
            <StatCard
              icon={TrendingDown}
              label="Refunds"
              value={formatPeso(data.refunds / 100)}
              tone="danger"
            />
            <StatCard
              icon={Receipt}
              label="Paid orders"
              value={String(data.paid_orders)}
            />
          </div>

          {/* Daily net bar chart — plain CSS, since the project ships no chart lib. */}
          <Card>
            <CardHeader>
              <CardTitle>Daily net</CardTitle>
              <CardDescription>
                Payments minus refunds for each day in range. Hover a bar for
                the exact figure.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.daily.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No data for this range.
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="flex h-40 items-end gap-px overflow-hidden rounded-md border bg-muted/30 p-2">
                    {data.daily.map((point) => {
                      const pct =
                        peak > 0 ? (Math.abs(point.net) / peak) * 100 : 0;
                      const tone =
                        point.net > 0
                          ? "bg-success"
                          : point.net < 0
                            ? "bg-destructive"
                            : "bg-muted-foreground/30";
                      return (
                        <div
                          key={point.date}
                          className={cn("flex-1 rounded-sm", tone)}
                          style={{
                            height: `${Math.max(pct, point.net === 0 ? 0 : 2)}%`,
                          }}
                          title={`${point.date}: ${formatPeso(point.net / 100)}`}
                        />
                      );
                    })}
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{data.from}</span>
                    <span>{data.to}</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          {/* Net totals per payment method. */}
          <Card>
            <CardHeader>
              <CardTitle>By payment method</CardTitle>
            </CardHeader>
            <CardContent className="px-0">
              {data.methods.length === 0 ? (
                <p className="px-6 text-sm text-muted-foreground">
                  No payments in this range.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Method</TableHead>
                      <TableHead className="text-right">Payments</TableHead>
                      <TableHead className="text-right">Gross</TableHead>
                      <TableHead className="text-right">Refunds</TableHead>
                      <TableHead className="text-right">Net</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.methods.map((row) => (
                      <TableRow key={row.method}>
                        <TableCell className="font-medium">
                          {methodLabel(row.method)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.count}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatPeso(row.gross / 100)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {row.refunds ? formatPeso(row.refunds / 100) : "—"}
                        </TableCell>
                        <TableCell className="text-right font-medium tabular-nums">
                          {formatPeso(row.net / 100)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Latest ledger rows — the audit trail behind the totals. */}
          <Card>
            <CardHeader>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>
                The latest ledger entries in this window.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              {data.recent.length === 0 ? (
                <p className="px-6 text-sm text-muted-foreground">
                  Nothing recorded yet.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>When</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Tracking ID</TableHead>
                      <TableHead>Method</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.recent.map((entry) => {
                      const isRefund = entry.kind === "refund";
                      return (
                        <TableRow key={entry.id}>
                          <TableCell className="whitespace-nowrap text-muted-foreground">
                            {formatDateTime(entry.occurred_at)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={cn(
                                isRefund
                                  ? "border-destructive/40 text-destructive"
                                  : "border-success/40 text-success",
                              )}
                            >
                              {isRefund ? "Refund" : "Payment"}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {entry.tracking_id}
                          </TableCell>
                          <TableCell>{methodLabel(entry.method)}</TableCell>
                          <TableCell
                            className={cn(
                              "text-right font-medium tabular-nums",
                              isRefund ? "text-destructive" : "text-success",
                            )}
                          >
                            {isRefund ? "−" : "+"}
                            {formatPeso(entry.amount_peso)}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
