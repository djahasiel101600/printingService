import { useEffect, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Copy, ExternalLink, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, apiErrorMessage } from "@/lib/api";

/**
 * OAuth redirect target for the Epson device authorization flow.
 *
 * Epson sends the admin here with either `?code=…&state=…` on success or
 * `?error=not_registered` when the printer isn't registered in Epson Connect.
 * The admin is signed in on this browser, so the code can be exchanged inline.
 */
export default function EpsonCallbackPage() {
  const [params] = useSearchParams();
  const { user } = useAuth();
  const code = params.get("code") ?? "";
  const state = params.get("state") ?? "";
  const error = params.get("error") ?? "";

  const exchangeMutation = useMutation({
    mutationFn: async () =>
      (await api.post<{ detail: string }>("/admin/epson/exchange-code/", { code, state })).data,
    onSuccess: (data) => toast.success(data.detail),
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  // Complete the flow automatically for a signed-in shop admin (the usual case).
  const attempted = useRef(false);
  useEffect(() => {
    if (attempted.current || error || !code || !user?.is_shop_admin) return;
    attempted.current = true;
    exchangeMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, error, user]);

  function copyCode() {
    navigator.clipboard.writeText(code);
    toast.success("Authorization code copied");
  }

  return (
    <div className="flex justify-center">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>Epson device authorization</CardTitle>
          <CardDescription>Connecting your printer to the Epson Connect API v2.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error === "not_registered" ? (
            <>
              <div className="flex items-start gap-2 rounded-md border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  That Epson account has no registered printer, so no device token can be issued.
                  Register the printer first, then retry.
                </span>
              </div>
              <Button asChild variant="outline">
                <a
                  href="https://www.epsonconnect.com/guide/en/html/p01.htm"
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  How to register a device
                </a>
              </Button>
            </>
          ) : error ? (
            <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>Epson returned an error: <code>{error}</code></span>
            </div>
          ) : !code ? (
            <p className="text-sm text-muted-foreground">
              No authorization code was returned. Start the flow again from API Settings.
            </p>
          ) : (
            <>
              {exchangeMutation.isSuccess ? (
                <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
                  <ShieldCheck className="h-4 w-4" />
                  Device connected. The refresh token is stored and renews automatically.
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="epson-code">Authorization code</Label>
                    <div className="flex gap-2">
                      <Input id="epson-code" readOnly value={code} className="font-mono text-xs" />
                      <Button variant="outline" size="sm" onClick={copyCode}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  {user?.is_shop_admin ? (
                    <Button
                      onClick={() => exchangeMutation.mutate()}
                      disabled={exchangeMutation.isPending}
                    >
                      {exchangeMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Complete connection
                    </Button>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Sign in as a shop admin, then paste this code in{" "}
                      <strong>Admin → API Settings</strong>.
                    </p>
                  )}
                </>
              )}
            </>
          )}

          <Button asChild variant="ghost" size="sm" className="px-0">
            <Link to="/admin/settings">Go to API Settings</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}