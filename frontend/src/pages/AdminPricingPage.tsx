import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Pencil, Plus, Tags, Trash2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, apiErrorMessage } from "@/lib/api";
import {
  PAPER_SIZE_LABELS, PAPER_TYPE_LABELS, QUALITY_LABELS,
  paperSizeLabel, paperTypeLabel, qualityLabel,
} from "@/lib/constants";
import type { Paginated, PriceRule, PricingSettings } from "@/lib/types";

const COLOR_OPTIONS = [
  { value: "mono", label: "Black & white" },
  { value: "color", label: "Color" },
  { value: "any", label: "Any color (wildcard)" },
];

const SIZE_OPTIONS = [
  { value: "any", label: "Any size (wildcard)" },
  ...Object.entries(PAPER_SIZE_LABELS).map(([value, label]) => ({ value, label })),
];

const TYPE_OPTIONS = [
  { value: "any", label: "Any paper type (wildcard)" },
  ...Object.entries(PAPER_TYPE_LABELS).map(([value, label]) => ({ value, label })),
];

const QUALITY_OPTIONS = [
  { value: "any", label: "Any quality (wildcard)" },
  ...Object.entries(QUALITY_LABELS).map(([value, label]) => ({ value, label })),
];

/** The list endpoint is paginated (PAGE_SIZE 50) — collect every page. */
async function fetchPriceRules(): Promise<PriceRule[]> {
  const rules: PriceRule[] = [];
  for (let page = 1; page <= 20; page += 1) {
    const { data } = await api.get<PriceRule[] | Paginated<PriceRule>>(
      "/admin/pricing-rules/", { params: { page } },
    );
    if (Array.isArray(data)) {
      rules.push(...data);
      break;
    }
    rules.push(...data.results);
    if (rules.length >= data.count) break;
  }
  return rules;
}

interface RuleForm {
  media_size: string;
  media_type: string;
  color_mode: string;
  print_quality: string;
  /** Price per side in pesos, as typed by the admin (sent as centavos). */
  price_peso: string;
  is_active: boolean;
}

const EMPTY_FORM: RuleForm = {
  media_size: "ps_a4",
  media_type: "pt_plainpaper",
  color_mode: "mono",
  print_quality: "normal",
  price_peso: "3.00",
  is_active: true,
};

export default function AdminPricingPage() {
  const queryClient = useQueryClient();

  // ---------------------------------------------------- global pricing knobs
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ["pricing-settings"],
    queryFn: async () => (await api.get<PricingSettings>("/pricing/settings/")).data,
  });

  const [knobs, setKnobs] = useState({ duplexPct: "", minPartial: "", fallbackPeso: "" });
  useEffect(() => {
    if (settings) {
      setKnobs({
        duplexPct: String(Math.round(settings.duplex_discount_factor * 1000) / 10),
        minPartial: String(settings.min_partial_percent),
        fallbackPeso: String(settings.fallback_price_per_side_peso),
      });
    }
  }, [settings]);

  const saveKnobsMutation = useMutation({
    mutationFn: async () => {
      const duplexPct = Number(knobs.duplexPct);
      const minPartial = Number(knobs.minPartial);
      const fallbackPeso = Number(knobs.fallbackPeso);
      if (!Number.isFinite(duplexPct) || duplexPct < 0 || duplexPct > 100) {
        throw new Error("Double-sided factor must be between 0 and 100%.");
      }
      if (!Number.isInteger(minPartial) || minPartial < 0 || minPartial > 100) {
        throw new Error("Minimum down payment must be a whole number 0–100.");
      }
      if (!Number.isFinite(fallbackPeso) || fallbackPeso <= 0) {
        throw new Error("Fallback price must be more than ₱0.");
      }
      const { data } = await api.put<PricingSettings>("/pricing/settings/", {
        duplex_discount_factor: duplexPct / 100,
        min_partial_percent: minPartial,
        fallback_price_per_side: Math.round(fallbackPeso * 100),
      });
      return data;
    },
    onSuccess: () => {
      toast.success("Pricing settings saved.");
      queryClient.invalidateQueries({ queryKey: ["pricing-settings"] });
      queryClient.invalidateQueries({ queryKey: ["quote"] });
      queryClient.invalidateQueries({ queryKey: ["quick-quote"] });
      queryClient.invalidateQueries({ queryKey: ["order"] });
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : apiErrorMessage(err)),
  });

  // ------------------------------------------------------------- price rules
  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ["pricing-rules"],
    queryFn: fetchPriceRules,
  });

  const [colorFilter, setColorFilter] = useState("all");
  const [qualityFilter, setQualityFilter] = useState("all");
  const [showInactive, setShowInactive] = useState(false);

  const visibleRules = useMemo(() => {
    return (rules ?? []).filter((rule) => {
      if (!showInactive && !rule.is_active) return false;
      if (colorFilter !== "all" && rule.color_mode !== colorFilter) return false;
      if (qualityFilter !== "all" && rule.print_quality !== qualityFilter) return false;
      return true;
    });
  }, [rules, colorFilter, qualityFilter, showInactive]);

  const invalidateRules = () => queryClient.invalidateQueries({ queryKey: ["pricing-rules"] });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PriceRule | null>(null);
  const [form, setForm] = useState<RuleForm>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<PriceRule | null>(null);

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEdit(rule: PriceRule) {
    setEditing(rule);
    setForm({
      media_size: rule.media_size,
      media_type: rule.media_type,
      color_mode: rule.color_mode,
      print_quality: rule.print_quality,
      price_peso: (rule.price_per_page / 100).toFixed(2),
      is_active: rule.is_active,
    });
    setDialogOpen(true);
  }

  const saveRuleMutation = useMutation({
    mutationFn: async () => {
      const pricePeso = Number(form.price_peso);
      if (!Number.isFinite(pricePeso) || pricePeso < 0.01) {
        throw new Error("Price per side must be at least ₱0.01.");
      }
      const payload = {
        media_size: form.media_size,
        media_type: form.media_type,
        color_mode: form.color_mode,
        print_quality: form.print_quality,
        price_per_page: Math.round(pricePeso * 100),
        is_active: form.is_active,
      };
      if (editing) {
        return (await api.patch<PriceRule>(`/admin/pricing-rules/${editing.id}/`, payload)).data;
      }
      return (await api.post<PriceRule>("/admin/pricing-rules/", payload)).data;
    },
    onSuccess: () => {
      toast.success(editing ? "Price rule updated." : "Price rule added.");
      setDialogOpen(false);
      invalidateRules();
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : apiErrorMessage(err)),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, isActive }: { id: number; isActive: boolean }) =>
      (await api.patch<PriceRule>(`/admin/pricing-rules/${id}/`, { is_active: isActive })).data,
    onSuccess: () => invalidateRules(),
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const deleteRuleMutation = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/admin/pricing-rules/${id}/`)).data,
    onSuccess: () => {
      toast.success("Price rule deleted.");
      setDeleteTarget(null);
      invalidateRules();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Pricing</h1>
        <p className="text-muted-foreground">
          Set the shop's price rules and the global pricing knobs used by every quotation.
        </p>
      </div>

      {/* ------------------------------------------------ global pricing knobs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tags className="h-5 w-5" />
            Global pricing settings
          </CardTitle>
          <CardDescription>
            Applied to every quote and checkout. Changes take effect immediately.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {settingsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <Label htmlFor="duplex-factor">Double-sided factor (%)</Label>
                  <Input
                    id="duplex-factor"
                    type="number"
                    min={0}
                    max={100}
                    step="1"
                    value={knobs.duplexPct}
                    onChange={(e) => setKnobs((k) => ({ ...k, duplexPct: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Per-side price × this % for duplex jobs (90 = 10% cheaper).
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="min-partial">Minimum down payment (%)</Label>
                  <Input
                    id="min-partial"
                    type="number"
                    min={0}
                    max={100}
                    step="1"
                    value={knobs.minPartial}
                    onChange={(e) => setKnobs((k) => ({ ...k, minPartial: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Smallest QR Ph partial payment, as % of the subtotal.
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="fallback-price">Fallback price per side (₱)</Label>
                  <Input
                    id="fallback-price"
                    type="number"
                    min={0.01}
                    step="0.01"
                    value={knobs.fallbackPeso}
                    onChange={(e) => setKnobs((k) => ({ ...k, fallbackPeso: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Charged when no price rule matches the job.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button
                  onClick={() => saveKnobsMutation.mutate()}
                  disabled={saveKnobsMutation.isPending}
                >
                  {saveKnobsMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save settings
                </Button>
                <Button
                  variant="outline"
                  onClick={() => settings && setKnobs({
                    duplexPct: String(Math.round(settings.duplex_discount_factor * 1000) / 10),
                    minPartial: String(settings.min_partial_percent),
                    fallbackPeso: String(settings.fallback_price_per_side_peso),
                  })}
                  disabled={saveKnobsMutation.isPending}
                >
                  Reset
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* -------------------------------------------------------- price rules */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Price rules</CardTitle>
              <CardDescription>
                Price per printed side for each paper / color / quality combination.
                Matched most-specific first; wildcards act as catch-alls.
              </CardDescription>
            </div>
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Add rule
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Color</Label>
              <Select value={colorFilter} onValueChange={setColorFilter}>
                <SelectTrigger className="h-9 w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All colors</SelectItem>
                  {COLOR_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Quality</Label>
              <Select value={qualityFilter} onValueChange={setQualityFilter}>
                <SelectTrigger className="h-9 w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All qualities</SelectItem>
                  {QUALITY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2 pb-2">
              <Switch
                id="show-inactive"
                checked={showInactive}
                onCheckedChange={setShowInactive}
              />
              <Label htmlFor="show-inactive" className="text-sm text-muted-foreground">
                Show inactive
              </Label>
            </div>
          </div>

          {rulesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : visibleRules.length === 0 ? (
            <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              No price rules match these filters.{" "}
              {rules?.length === 0 && "Add your first rule to start pricing jobs."}
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Paper size</TableHead>
                    <TableHead>Paper type</TableHead>
                    <TableHead>Color</TableHead>
                    <TableHead>Quality</TableHead>
                    <TableHead className="text-right">Price / side</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead className="w-24 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleRules.map((rule) => (
                    <TableRow key={rule.id} className={rule.is_active ? "" : "opacity-60"}>
                      <TableCell>
                        {rule.media_size === "any"
                          ? <Badge variant="outline">Any size</Badge>
                          : paperSizeLabel(rule.media_size)}
                      </TableCell>
                      <TableCell>
                        {rule.media_type === "any"
                          ? <Badge variant="outline">Any type</Badge>
                          : paperTypeLabel(rule.media_type)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={rule.color_mode === "any" ? "outline" : "secondary"}>
                          {COLOR_OPTIONS.find((c) => c.value === rule.color_mode)?.label ?? rule.color_mode}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {rule.print_quality === "any"
                          ? <Badge variant="outline">Any</Badge>
                          : qualityLabel(rule.print_quality)}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        ₱{rule.price_per_page_peso.toFixed(2)}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={rule.is_active}
                          onCheckedChange={(isActive) =>
                            toggleActiveMutation.mutate({ id: rule.id, isActive })}
                          disabled={
                            toggleActiveMutation.isPending &&
                            toggleActiveMutation.variables?.id === rule.id
                          }
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Edit rule"
                            onClick={() => openEdit(rule)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Delete rule"
                            onClick={() => setDeleteTarget(rule)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <Alert>
            <AlertDescription>
              Quotation matches the exact combination first, then relaxes quality → type → size,
              so keeping a catch-all "Any / Any / Any / Any" rule guarantees every job has a price.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* ------------------------------------------------------- rule dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit price rule" : "Add price rule"}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="rule-size">Paper size</Label>
              <Select
                value={form.media_size}
                onValueChange={(value) => setForm((f) => ({ ...f, media_size: value }))}
              >
                <SelectTrigger id="rule-size"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SIZE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-type">Paper type</Label>
              <Select
                value={form.media_type}
                onValueChange={(value) => setForm((f) => ({ ...f, media_type: value }))}
              >
                <SelectTrigger id="rule-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-color">Color</Label>
              <Select
                value={form.color_mode}
                onValueChange={(value) => setForm((f) => ({ ...f, color_mode: value }))}
              >
                <SelectTrigger id="rule-color"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {COLOR_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-quality">Print quality</Label>
              <Select
                value={form.print_quality}
                onValueChange={(value) => setForm((f) => ({ ...f, print_quality: value }))}
              >
                <SelectTrigger id="rule-quality"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {QUALITY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rule-price">Price per side (₱)</Label>
              <Input
                id="rule-price"
                type="number"
                min={0.01}
                step={0.01}
                value={form.price_peso}
                onChange={(e) => setForm((f) => ({ ...f, price_peso: e.target.value }))}
              />
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div>
                <Label className="text-base">Active</Label>
                <p className="text-sm text-muted-foreground">Inactive rules are ignored.</p>
              </div>
              <Switch
                checked={form.is_active}
                onCheckedChange={(isActive) => setForm((f) => ({ ...f, is_active: isActive }))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={() => saveRuleMutation.mutate()}
              disabled={saveRuleMutation.isPending}
            >
              {saveRuleMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Save changes" : "Add rule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ----------------------------------------------- delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete price rule?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {deleteTarget
              ? `${paperSizeLabel(deleteTarget.media_size)} · ${paperTypeLabel(deleteTarget.media_type)} · ` +
                `${COLOR_OPTIONS.find((c) => c.value === deleteTarget.color_mode)?.label ?? deleteTarget.color_mode} · ` +
                `${qualityLabel(deleteTarget.print_quality)} — `
              : ""}
            jobs that relied on it will fall back to the next matching rule or the fallback price.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteRuleMutation.mutate(deleteTarget.id)}
              disabled={deleteRuleMutation.isPending}
            >
              {deleteRuleMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}