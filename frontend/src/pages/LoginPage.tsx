import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, apiErrorMessage } from "@/lib/api";
import type { SetupStatus } from "@/lib/types";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  // Surfaces a one-time "create the shop admin" link until setup is done.
  const { data: setupStatus } = useQuery({
    queryKey: ["setup-status"],
    queryFn: async () => (await api.get<SetupStatus>("/auth/setup/")).data,
  });

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("Welcome back!");
      navigate(from, { replace: true });
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex justify-center">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Enter your email and password to access your orders.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Logging in…" : "Log in"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              No account?{" "}
              <Link to="/register" className="text-primary underline-offset-4 hover:underline">
                Sign up
              </Link>
            </p>
            {setupStatus?.needs_setup && (
              <p className="text-center text-xs text-muted-foreground">
                First time here?{" "}
                <Link to="/setup" className="text-primary underline-offset-4 hover:underline">
                  Set up the shop admin
                </Link>
              </p>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
