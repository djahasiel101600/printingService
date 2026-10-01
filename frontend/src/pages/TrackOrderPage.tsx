import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/StatusBadge";
import { api, apiErrorMessage, saveGuestOrder } from "@/lib/api";
import type { TrackResult } from "@/lib/types";

export default function TrackOrderPage() {
  const [trackingId, setTrackingId] = useState("");
  const [result, setResult] = useState<TrackResult | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function onTrack(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const { data } = await api.get<TrackResult>(`/track/${trackingId.trim()}/`);
      setResult(data);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function openOrderDetails() {
    if (!result) return;
    // Remember the order on this device so the details page (and My Orders)
    // can be reopened without an account — the tracking ID is the proof.
    saveGuestOrder({ id: result.id, tracking_id: result.tracking_id, created_at: result.created_at });
    navigate(`/orders/${result.id}`);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Track your order</CardTitle>
          <CardDescription>Enter your tracking ID (e.g. PSP-XXXX-XXXX) to see the current status.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onTrack} className="flex gap-3">
            <div className="flex-1 space-y-2">
              <Label htmlFor="tracking" className="sr-only">Tracking ID</Label>
              <Input
                id="tracking"
                placeholder="PSP-XXXX-XXXX"
                value={trackingId}
                onChange={(e) => setTrackingId(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? "Looking up…" : "Track"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle>{result.tracking_id}</CardTitle>
              <CardDescription>Submitted {new Date(result.created_at).toLocaleString()}</CardDescription>
            </div>
            <StatusBadge status={result.status} display={result.status_display} />
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <p className="text-muted-foreground">Client</p>
                <p className="font-medium">{result.client_name}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Total</p>
                <p className="font-medium">₱{result.subtotal_peso.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Balance due</p>
                <p className="font-medium">₱{result.balance_due_peso.toFixed(2)}</p>
              </div>
            </div>
            <div>
              <p className="text-sm font-medium">Files</p>
              <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
                {result.files.map((f) => (
                  <li key={f.id}>{f.file_name} — {f.page_count} page(s)</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-sm font-medium">Status history</p>
              <ul className="mt-1 space-y-2">
                {result.history.map((h, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <StatusBadge status={h.to_status} display={h.to_status_display} className="mt-0.5" />
                    <div>
                      <p>{h.note || "—"}</p>
                      <p className="text-xs text-muted-foreground">{new Date(h.created_at).toLocaleString()}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <Separator />
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={openOrderDetails}>
                <ExternalLink className="mr-2 h-4 w-4" /> Open order details
              </Button>
              <span className="text-xs text-muted-foreground">
                Review files, pay, or manage the order from its details page.
              </span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
