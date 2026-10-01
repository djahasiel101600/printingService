import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, apiErrorMessage } from "@/lib/api";
import type { SetupStatus } from "@/lib/types";

/**
 * First-run wizard: creates the shop's first administrator.
 *
 * The backend only accepts this once (it answers 403 as soon as an admin
 * exists), so the page doubles as a "setup finished" notice afterwards.
 */
export default function SetupPage() {
  const { setupAdmin } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: "", last_name: "", email: "", phone: "", password: "", confirm: "",
  });
  const [loading, setLoading] = useState(false);

  const { data: status, isLoading } = useQuery({
    queryKey: ["setup-status"],
    queryFn: async () => (await api.get<SetupStatus>("/auth/setup/")).data,
  });

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const user = await setupAdmin({
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        phone: form.phone,
      });
      toast.success(`Welcome, ${user.first_name || user.email}!`);
      navigate("/admin", { replace: true });
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  if (isLoading) return <Skeleton className="mx-auto h-96 w-full max-w-xl" />;

  if (status && !status.needs_setup) {
    return (
      <div className="flex justify-center">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Setup already completed</CardTitle>
            <CardDescription>An administrator account already exists for this shop.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full">
              <Link to="/login">Go to log in</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2 text-primary">
            <ShieldCheck className="h-5 w-5" />
            <span className="text-sm font-semibold uppercase tracking-wide">Initial setup</span>
          </div>
          <CardTitle>Create the shop administrator</CardTitle>
          <CardDescription>
            This is a one-time step. The account you create here manages orders, the
            printer, and API settings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="first_name">First name</Label>
                <Input id="first_name" value={form.first_name} onChange={(e) => update("first_name", e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Last name</Label>
                <Input id="last_name" value={form.last_name} onChange={(e) => update("last_name", e.target.value)} required />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={form.email} onChange={(e) => update("email", e.target.value)} required autoComplete="email" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone (optional)</Label>
              <Input id="phone" type="tel" value={form.phone} onChange={(e) => update("phone", e.target.value)} autoComplete="tel" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={form.password}
                  onChange={(e) => update("password", e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm">Confirm password</Label>
                <Input
                  id="confirm"
                  type="password"
                  value={form.confirm}
                  onChange={(e) => update("confirm", e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
              </div>
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating administrator…" : "Create administrator"}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Already set up?{" "}
              <Link to="/login" className="text-primary underline-offset-4 hover:underline">
                Log in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}