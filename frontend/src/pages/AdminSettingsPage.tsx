import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  CheckCircle2,
  Copy,
  ExternalLink,
  KeyRound,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Wallet,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api, apiErrorMessage } from "@/lib/api";
import type { EpsonAuthUrl, EpsonStatus, ShopPaymentSettings } from "@/lib/types";

interface TestResult {
  mock_mode?: boolean;
  overall?: string;
  tests?: Record<string, { status: string; error?: string; data?: any }>;
}

function StatusIcon({ status }: { status: string }) {
  if (status === "success") return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  if (status === "failed") return <XCircle className="h-4 w-4 text-red-600" />;
  return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
}

export default function AdminSettingsPage() {
  const [epsonMockMode, setEpsonMockMode] = useState(true);
  const [paymongoMockMode, setPaymongoMockMode] = useState(true);
  const [code, setCode] = useState("");
  const queryClient = useQueryClient();

  const { data: epsonStatus } = useQuery({
    queryKey: ["epson-status"],
    queryFn: async () => (await api.get<EpsonStatus>("/admin/epson/status/")).data,
  });

  const authUrlMutation = useMutation({
    mutationFn: async () => (await api.get<EpsonAuthUrl>("/admin/epson/auth-url/")).data,
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const exchangeMutation = useMutation({
    mutationFn: async () =>
      (await api.post<{ detail: string }>("/admin/epson/exchange-code/", {
        code,
        state: authUrlMutation.data?.state ?? "",
      })).data,
    onSuccess: (data) => {
      toast.success(data.detail);
      setCode("");
      queryClient.invalidateQueries({ queryKey: ["epson-status"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  function copy(text: string) {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  }

  const epsonTestMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TestResult>("/admin/epson/test-connection/", { mock_mode: epsonMockMode });
      return data;
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const paymongoTestMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<TestResult>("/admin/paymongo/test-connection/", { mock_mode: paymongoMockMode });
      return data;
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const { data: paymentSettings, isLoading: paymentSettingsLoading } = useQuery({
    queryKey: ["payment-settings"],
    queryFn: async () => (await api.get<ShopPaymentSettings>("/payments/settings/")).data,
  });

  const paymentSettingsMutation = useMutation({
    mutationFn: async (allowPayOnPickup: boolean) =>
      (await api.put<ShopPaymentSettings>("/payments/settings/", { allow_pay_on_pickup: allowPayOnPickup })).data,
    onSuccess: () => {
      toast.success("Payment option updated.");
      queryClient.invalidateQueries({ queryKey: ["payment-settings"] });
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">API Settings</h1>
        <p className="text-muted-foreground">Configure and test your Epson Connect and PayMongo integrations.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            Epson Connect API
          </CardTitle>
          <CardDescription>Configure your Epson printer connection.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <Label className="text-base">Mock Mode</Label>
              <p className="text-sm text-muted-foreground">Simulate printer responses without a real device.</p>
            </div>
            <Switch checked={epsonMockMode} onCheckedChange={setEpsonMockMode} />
          </div>
          <Alert variant={epsonMockMode ? "default" : "warning"}>
            <AlertDescription>
              {epsonMockMode ? "Mock mode is ON. No real printer connection." : "Mock mode is OFF. Real credentials from .env will be used."}
            </AlertDescription>
          </Alert>
          <Button onClick={() => epsonTestMutation.mutate()} disabled={epsonTestMutation.isPending}>
            {epsonTestMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Test Epson Connection
          </Button>
          {epsonTestMutation.data && (
            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-center gap-2 font-medium">
                <StatusIcon status={epsonTestMutation.data.overall ?? ""} />
                Overall: {epsonTestMutation.data.overall === "success" ? "All tests passed!" : "Some tests failed"}
              </div>
              {epsonTestMutation.data.tests && Object.entries(epsonTestMutation.data.tests).map(([key, test]) => (
                <div key={key} className="flex items-start gap-2 text-sm">
                  <StatusIcon status={test.status} />
                  <div>
                    <span className="font-medium">{key.replace(/_/g, " ")}</span>
                    {test.status === "success" && test.data && (
                      <span className="ml-2 text-muted-foreground">{test.data.productName} ({test.data.serialNumber})</span>
                    )}
                    {test.status === "failed" && <p className="text-xs text-red-600">{test.error}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="h-5 w-5" />
            Epson device authorization
          </CardTitle>
          <CardDescription>
            Epson Connect v2 has no password login. The printer is connected once via an
            authorization code; the refresh token then renews automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 text-sm">
            <StatusIcon status={epsonStatus?.device_connected ? "success" : "failed"} />
            {epsonStatus?.device_connected ? (
              <>
                Connected
                <span className="text-muted-foreground">
                  (refresh token from: {epsonStatus.refresh_token_source})
                </span>
              </>
            ) : (
              "Not connected — real printing fails until this is completed."
            )}
          </div>
          {epsonStatus && (
            <p className="text-xs text-muted-foreground">
              Redirect URI:{" "}
              <code className="rounded bg-muted px-1 py-0.5">{epsonStatus.redirect_uri}</code> — it must be
              reachable on the hostname the tunnel serves.
            </p>
          )}

          <Separator />

          <div className="space-y-2">
            <Label>Step 1 — sign in to Epson as the printer's account</Label>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => authUrlMutation.mutate()}
                disabled={authUrlMutation.isPending}
              >
                {authUrlMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <KeyRound className="mr-2 h-4 w-4" />
                )}
                Get authorization URL
              </Button>
              {authUrlMutation.data && (
                <Button asChild>
                  <a href={authUrlMutation.data.authorization_url} target="_blank" rel="noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    Open Epson sign-in
                  </a>
                </Button>
              )}
            </div>
            {authUrlMutation.data && (
              <div className="flex items-center gap-2">
                <Input readOnly value={authUrlMutation.data.authorization_url} className="text-xs" />
                <Button variant="ghost" size="sm" onClick={() => copy(authUrlMutation.data!.authorization_url)}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>

          <Separator />

          <div className="space-y-2">
            <Label htmlFor="epson-code">Step 2 — paste the code Epson returned</Label>
            <div className="flex gap-2">
              <Input
                id="epson-code"
                placeholder="Code from the callback URL"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
              <Button
                onClick={() => exchangeMutation.mutate()}
                disabled={!code || exchangeMutation.isPending}
              >
                {exchangeMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="mr-2 h-4 w-4" />
                )}
                Connect device
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              After signing in, Epson redirects to the callback page, which shows the code.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5" />
            PayMongo (QR Ph)
          </CardTitle>
          <CardDescription>Configure your payment gateway.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <Label className="text-base">Mock Mode</Label>
              <p className="text-sm text-muted-foreground">Simulate payments without real transactions.</p>
            </div>
            <Switch checked={paymongoMockMode} onCheckedChange={setPaymongoMockMode} />
          </div>
          <Alert variant={paymongoMockMode ? "default" : "warning"}>
            <AlertDescription>
              {paymongoMockMode ? "Mock mode is ON. No real payments." : "Mock mode is OFF. Real credentials from .env will be used."}
            </AlertDescription>
          </Alert>
          <Button onClick={() => paymongoTestMutation.mutate()} disabled={paymongoTestMutation.isPending}>
            {paymongoTestMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Test PayMongo Connection
          </Button>
          {paymongoTestMutation.data && (
            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-center gap-2 font-medium">
                <StatusIcon status={paymongoTestMutation.data.overall ?? ""} />
                Overall: {paymongoTestMutation.data.overall === "success" ? "All tests passed!" : "Some tests failed"}
              </div>
              {paymongoTestMutation.data.tests && Object.entries(paymongoTestMutation.data.tests).map(([key, test]) => (
                <div key={key} className="flex items-start gap-2 text-sm">
                  <StatusIcon status={test.status} />
                  <div>
                    <span className="font-medium">{key.replace(/_/g, " ")}</span>
                    {test.status === "failed" && <p className="text-xs text-red-600">{test.error}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            Checkout options
          </CardTitle>
          <CardDescription>Choose how customers can settle their orders.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <Label className="text-base">Allow "Pay upon pickup"</Label>
              <p className="text-sm text-muted-foreground">
                Let customers skip online payment and pay the balance when they collect their printout.
                QR Ph remains available either way.
              </p>
            </div>
            <Switch
              checked={paymentSettings?.allow_pay_on_pickup ?? false}
              onCheckedChange={(checked) => paymentSettingsMutation.mutate(checked)}
              disabled={paymentSettingsLoading || paymentSettingsMutation.isPending || !paymentSettings}
            />
          </div>
          <Alert>
            <AlertDescription>
              When enabled, customers choosing pay upon pickup go straight to your review queue, and
              you can record their payment from the order page when they collect.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    </div>
  );
}