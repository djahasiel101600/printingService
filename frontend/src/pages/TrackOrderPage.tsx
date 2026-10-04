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
  const [contact, setContact] = useState("");
  const [result, setResult] = useState<TrackResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function onTrack(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError("");
    try {
      // The API requires the contact used when the order was placed as proof
      // that this lookup belongs to the customer — a tracking ID alone is not
      // enough to read somebody else's order.
      const { data } = await api.get<TrackResult>(`/track/${trackingId.trim()}/`, {
        params: contact.trim() ? { contact: contact.trim() } : undefined,
      });
      setResult(data);
    } catch (err) {
      setError(apiErrorMessage(err));
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
          <form onSubmit={onTrack} className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="tracking">Tracking ID</Label>
              <Input
                id="tracking"
                placeholder="PSP-XXXX-XXXX"
                value={trackingId}
                onChange={(e) => setTrackingId(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contact">Email, phone or Facebook name</Label>
              <Input
                id="contact"
                placeholder="The contact you used when ordering"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Needed to confirm the order is yours. Skip it if you are signed in
                to the account that placed the order.
              </p>
            </div>
            {error && (
              <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" disabled={loading} className="w-full sm:w-auto">
              {loading ? "Looking up…" : "Track order"}
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
            <div className="grid gap-3 text-sm sm:grid-cols-4">
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
              <div>
                <p className="text-muted-foreground">Reprints</p>
                <p className="font-medium">{result.reprint_count ?? 0}</p>
              </div>
            </div>
            <div>
              <p className="text-sm font-medium">Files</p>
              <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
                {result.files.map((f) => (
                  <li key={f.id}>
                    {f.file_name} — {f.page_count} page(s)
                    {(f.current_version ?? 1) > 1 && ` · v${f.current_version}`}
                  </li>
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
