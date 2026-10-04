import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api, apiErrorMessage } from "@/lib/api";
import type { StaffUser, StaffUserPayload } from "@/lib/types";

interface CreateForm {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  password: string;
  role: "approver" | "admin";
}

const EMPTY_FORM: CreateForm = {
  email: "", first_name: "", last_name: "", phone: "", password: "", role: "approver",
};

/**
 * User management (owner-only): the shop's admins and approvers.
 *
 * Approvers exist so the approval queue can be handed to a second person —
 * they review, revise and release print jobs, but cannot open pricing,
 * payment settings, printer credentials or this list.
 */
export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);

  const { data: staff, isLoading } = useQuery({
    queryKey: ["admin-staff"],
    queryFn: async () => (await api.get<StaffUser[]>("/admin/users/")).data,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-staff"] });

  const createMutation = useMutation({
    mutationFn: async (payload: StaffUserPayload) =>
      (await api.post<StaffUser>("/admin/users/", payload)).data,
    onSuccess: (created) => {
      toast.success(`${created.email} added as ${created.role_display}.`);
      setForm(EMPTY_FORM);
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: number; payload: Partial<StaffUserPayload> }) =>
      (await api.patch<StaffUser>(`/admin/users/${id}/`, payload)).data,
    onSuccess: (updated) => {
      toast.success(`${updated.email} updated.`);
      invalidate();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.email.trim()) return toast.error("Email is required.");
    if (form.password.length < 8) return toast.error("Password must be at least 8 characters.");
    createMutation.mutate({
      ...form,
      email: form.email.trim(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      phone: form.phone.trim(),
    });
  }

  function field(key: keyof CreateForm) {
    return {
      value: form[key] as string,
      onChange: (event: React.ChangeEvent<HTMLInputElement>) =>
        setForm({ ...form, [key]: event.target.value }),
    };
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Staff accounts</h1>
        <p className="text-muted-foreground">
          Approvers can review, revise and release print orders. Admins can also change
          pricing, payment and printer settings — and manage this list.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <UserPlus className="h-4 w-4" /> Add a staff account
          </CardTitle>
          <CardDescription>
            The new person signs in with their email and password right away.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="staff-email">Email</Label>
              <Input id="staff-email" type="email" placeholder="mara@shop.local"
                {...field("email")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="staff-first">First name</Label>
              <Input id="staff-first" {...field("first_name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="staff-last">Last name</Label>
              <Input id="staff-last" {...field("last_name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="staff-phone">Phone (optional)</Label>
              <Input id="staff-phone" {...field("phone")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="staff-password">Password</Label>
              <Input id="staff-password" type="password" placeholder="At least 8 characters"
                {...field("password")} />
            </div>
            <div className="space-y-1.5">
              <Label>Role</Label>
              <Select value={form.role}
                onValueChange={(value) => setForm({ ...form, role: value as CreateForm["role"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="approver">Approver — review &amp; print orders</SelectItem>
                  <SelectItem value="admin">Admin — full access</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-3">
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create account
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Current staff</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : !staff?.length ? (
            <p className="text-sm text-muted-foreground">No staff accounts yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Account</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last sign-in</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {staff.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell>
                      <p className="font-medium">
                        {[member.first_name, member.last_name].filter(Boolean).join(" ") || "—"}
                      </p>
                      <p className="text-xs text-muted-foreground">{member.email}</p>
                    </TableCell>
                    <TableCell>
                      <Select
                        value={member.role}
                        onValueChange={(role) => updateMutation.mutate({
                          id: member.id, payload: { role: role as StaffUser["role"] },
                        })}
                      >
                        <SelectTrigger className="h-8 w-36"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="approver">Approver</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      {member.is_active ? (
                        <Badge className="bg-emerald-100 text-emerald-800">Active</Badge>
                      ) : (
                        <Badge variant="secondary">Disabled</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {member.last_login ? new Date(member.last_login).toLocaleString() : "Never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={updateMutation.isPending}
                        onClick={() => updateMutation.mutate({
                          id: member.id, payload: { is_active: !member.is_active },
                        })}
                      >
                        {member.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            Approvers can work the review queue but cannot change pricing, payments,
            printer credentials or these accounts.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
