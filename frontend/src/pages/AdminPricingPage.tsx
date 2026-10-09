import { useEffect, useMemo, useState } from "react";
import type { ComponentProps } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  Info,
  Loader2,
  Pencil,
  Plus,
  Tags,
  Trash2,
  X,
} from "lucide-react";

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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, apiErrorMessage } from "@/lib/api";
import {
  PAPER_SIZE_LABELS,
  PAPER_TYPE_LABELS,
  QUALITY_LABELS,
  paperSizeLabel,
  paperTypeLabel,
  qualityLabel,
} from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { Paginated, PriceRule, PricingSettings } from "@/lib/types";

const COLOR_OPTIONS = [
  { value: "mono", label: "Black & white" },
  { value: "color", label: "Color" },
  { value: "any", label: "Any color (wildcard)" },
];

const SIZE_OPTIONS = [
  { value: "any", label: "Any size (wildcard)" },
  ...Object.entries(PAPER_SIZE_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
];

const TYPE_OPTIONS = [
  { value: "any", label: "Any paper type (wildcard)" },
  ...Object.entries(PAPER_TYPE_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
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
      "/admin/pricing-rules/",
      { params: { page } },
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

interface Knobs {
  duplexPct: string;
  minPartial: string;
  fallbackPeso: string;
}

function knobsFromSettings(settings: PricingSettings): Knobs {
  return {
    duplexPct: String(Math.round(settings.duplex_discount_factor * 1000) / 10),
    minPartial: String(settings.min_partial_percent),
    fallbackPeso: String(settings.fallback_price_per_side_peso),
  };
}

/** Same rules the save request enforces, so problems show next to the field as you type. */
function validateKnobs(knobs: Knobs): Partial<Record<keyof Knobs, string>> {
  const errors: Partial<Record<keyof Knobs, string>> = {};
  const duplexPct = Number(knobs.duplexPct);
  const minPartial = Number(knobs.minPartial);
  const fallbackPeso = Number(knobs.fallbackPeso);
  if (
    knobs.duplexPct.trim() === "" ||
    !Number.isFinite(duplexPct) ||
    duplexPct < 0 ||
    duplexPct > 100
  ) {
    errors.duplexPct = "Double-sided factor must be between 0 and 100%.";
  }
  if (
    knobs.minPartial.trim() === "" ||
    !Number.isInteger(minPartial) ||
    minPartial < 0 ||
    minPartial > 100
  ) {
    errors.minPartial = "Minimum down payment must be a whole number 0–100.";
  }
  if (
    knobs.fallbackPeso.trim() === "" ||
    !Number.isFinite(fallbackPeso) ||
    fallbackPeso <= 0
  ) {
    errors.fallbackPeso = "Fallback price must be more than ₱0.";
  }
  return errors;
}

const colorLabel = (value: string) =>
  COLOR_OPTIONS.find((c) => c.value === value)?.label ?? value;
const sizeText = (rule: PriceRule) =>
  rule.media_size === "any" ? "Any size" : paperSizeLabel(rule.media_size);
const typeText = (rule: PriceRule) =>
  rule.media_type === "any" ? "Any type" : paperTypeLabel(rule.media_type);
const qualityText = (rule: PriceRule) =>
  rule.print_quality === "any"
    ? "Any quality"
    : qualityLabel(rule.print_quality);
const ruleSummary = (rule: PriceRule) =>
  `${sizeText(rule)} · ${typeText(rule)} · ${colorLabel(rule.color_mode)} · ${qualityText(rule)}`;
const peso = (n: number) => `₱${n.toFixed(2)}`;

/** Number input with a ₱ or % marker, so the unit is part of the field and not only the label. */
function UnitInput({
  prefix,
  suffix,
  className,
  ...props
}: ComponentProps<typeof Input> & { prefix?: string; suffix?: string }) {
  return (
    <div className="relative">
      {prefix && (
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
          {prefix}
        </span>
      )}
      <Input
        {...props}
        className={cn(prefix && "pl-7", suffix && "pr-8", className)}
      />
      {suffix && (
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
          {suffix}
        </span>
      )}
    </div>
  );
}

export default function AdminPricingPage() {
  const queryClient = useQueryClient();

  // ---------------------------------------------------- global pricing knobs
  const {
    data: settings,
    isLoading: settingsLoading,
    isError: settingsError,
    refetch: refetchSettings,
  } = useQuery({
    queryKey: ["pricing-settings"],
    queryFn: async () =>
      (await api.get<PricingSettings>("/pricing/settings/")).data,
  });

  const [knobs, setKnobs] = useState<Knobs>({
    duplexPct: "",
    minPartial: "",
    fallbackPeso: "",
  });
  useEffect(() => {
    if (settings) setKnobs(knobsFromSettings(settings));
  }, [settings]);

  const knobErrors = validateKnobs(knobs);
  const hasKnobErrors = Object.keys(knobErrors).length > 0;
  const savedKnobs = settings ? knobsFromSettings(settings) : null;
  const knobsDirty = Boolean(
    savedKnobs &&
    (savedKnobs.duplexPct !== knobs.duplexPct ||
      savedKnobs.minPartial !== knobs.minPartial ||
      savedKnobs.fallbackPeso !== knobs.fallbackPeso),
  );

  const saveKnobsMutation = useMutation({
    mutationFn: async () => {
      const firstError = Object.values(validateKnobs(knobs))[0];
      if (firstError) throw new Error(firstError);
      const duplexPct = Number(knobs.duplexPct);
      const minPartial = Number(knobs.minPartial);
      const fallbackPeso = Number(knobs.fallbackPeso);
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
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : apiErrorMessage(err)),
  });

  // ------------------------------------------------------------- price rules
  const {
    data: rules,
    isLoading: rulesLoading,
    isError: rulesError,
    refetch: refetchRules,
  } = useQuery({
    queryKey: ["pricing-rules"],
    queryFn: fetchPriceRules,
  });

  const [colorFilter, setColorFilter] = useState("all");
  const [qualityFilter, setQualityFilter] = useState("all");
  const [showInactive, setShowInactive] = useState(false);
  const filtersActive = colorFilter !== "all" || qualityFilter !== "all";

  const visibleRules = useMemo(() => {
    return (rules ?? []).filter((rule) => {
      if (!showInactive && !rule.is_active) return false;
      if (colorFilter !== "all" && rule.color_mode !== colorFilter)
        return false;
      if (qualityFilter !== "all" && rule.print_quality !== qualityFilter)
        return false;
      return true;
    });
  }, [rules, colorFilter, qualityFilter, showInactive]);

  /** A rule that matches everything is the safety net for jobs no other rule covers. */
  const hasCatchAll = (rules ?? []).some(
    (r) =>
      r.is_active &&
      r.media_size === "any" &&
      r.media_type === "any" &&
      r.color_mode === "any" &&
      r.print_quality === "any",
  );
  const hiddenInactiveCount = showInactive
    ? 0
    : (rules ?? []).filter((r) => !r.is_active).length;

  const invalidateRules = () =>
    queryClient.invalidateQueries({ queryKey: ["pricing-rules"] });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PriceRule | null>(null);
  const [form, setForm] = useState<RuleForm>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<PriceRule | null>(null);

  function openCreate(preset: Partial<RuleForm> = {}) {
    setEditing(null);
    setForm({ ...EMPTY_FORM, ...preset });
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

  const pricePeso = Number(form.price_peso);
  const priceValid =
    form.price_peso.trim() !== "" &&
    Number.isFinite(pricePeso) &&
    pricePeso >= 0.01;
  const duplexPrice =
    settings && priceValid ? pricePeso * settings.duplex_discount_factor : null;
  // The same combination twice is almost always a mistake, so say so before saving.
  const duplicateRule = dialogOpen
    ? (rules ?? []).find(
        (r) =>
          r.id !== editing?.id &&
          r.media_size === form.media_size &&
          r.media_type === form.media_type &&
          r.color_mode === form.color_mode &&
          r.print_quality === form.print_quality,
      )
    : undefined;

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
        return (
          await api.patch<PriceRule>(
            `/admin/pricing-rules/${editing.id}/`,
            payload,
          )
        ).data;
      }
      return (await api.post<PriceRule>("/admin/pricing-rules/", payload)).data;
    },
    onSuccess: () => {
      toast.success(editing ? "Price rule updated." : "Price rule added.");
      setDialogOpen(false);
      invalidateRules();
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : apiErrorMessage(err)),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, isActive }: { id: number; isActive: boolean }) =>
      (
        await api.patch<PriceRule>(`/admin/pricing-rules/${id}/`, {
          is_active: isActive,
        })
      ).data,
    onSuccess: (_data, variables) => {
      toast.success(
        variables.isActive
          ? "Price rule activated."
          : "Price rule deactivated.",
      );
      invalidateRules();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const deleteRuleMutation = useMutation({
    mutationFn: async (id: number) =>
      (await api.delete(`/admin/pricing-rules/${id}/`)).data,
    onSuccess: () => {
      toast.success("Price rule deleted.");
      setDeleteTarget(null);
      invalidateRules();
    },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });

  const renderToggle = (rule: PriceRule) => (
    <Switch
      checked={rule.is_active}
      aria-label={`${rule.is_active ? "Deactivate" : "Activate"} rule: ${ruleSummary(rule)}`}
      onCheckedChange={(isActive) =>
        toggleActiveMutation.mutate({ id: rule.id, isActive })
      }
      disabled={
        toggleActiveMutation.isPending &&
        toggleActiveMutation.variables?.id === rule.id
      }
    />
  );

  const renderActions = (rule: PriceRule) => (
    <div className="flex justify-end gap-1">
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Edit rule: ${ruleSummary(rule)}`}
        onClick={() => openEdit(rule)}
      >
        <Pencil className="h-4 w-4" aria-hidden="true" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Delete rule: ${ruleSummary(rule)}`}
        onClick={() => setDeleteTarget(rule)}
      >
        <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
      </Button>
    </div>
  );

  const duplexPctNumber = Number(knobs.duplexPct);
  const minPartialNumber = Number(knobs.minPartial);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Pricing</h1>
        <p className="max-w-2xl text-muted-foreground">
          Set the shop&apos;s price rules and the global pricing knobs used by
          every quotation.
        </p>
      </div>

      {/* ------------------------------------------------ global pricing knobs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tags className="h-5 w-5" aria-hidden="true" />
            Global pricing settings
          </CardTitle>
          <CardDescription>
            Applied to every quote and checkout. Changes take effect
            immediately.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {settingsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : settingsError || !settings ? (
            <Alert variant="destructive">
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                We couldn&apos;t load the pricing settings.
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => refetchSettings()}
                >
                  Try again
                </Button>
              </AlertDescription>
            </Alert>
          ) : (
            <form
              className="space-y-5"
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                if (!hasKnobErrors && knobsDirty) saveKnobsMutation.mutate();
              }}
            >
              <div className="grid gap-5 sm:grid-cols-3">
                <div className="space-y-1.5">
                  <Label htmlFor="duplex-factor">Double-sided factor</Label>
                  <UnitInput
                    id="duplex-factor"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    max={100}
                    step="1"
                    suffix="%"
                    value={knobs.duplexPct}
                    onChange={(e) =>
                      setKnobs((k) => ({ ...k, duplexPct: e.target.value }))
                    }
                    aria-invalid={!!knobErrors.duplexPct}
                    aria-describedby="duplex-factor-help"
                  />
                  <p
                    id="duplex-factor-help"
                    className={cn(
                      "text-xs",
                      knobErrors.duplexPct
                        ? "text-destructive"
                        : "text-muted-foreground",
                    )}
                  >
                    {knobErrors.duplexPct ??
                      `Per-side price × this % for duplex jobs (90 = 10% cheaper). Now: duplex pages cost ${duplexPctNumber}% per side.`}
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="min-partial">Minimum down payment</Label>
                  <UnitInput
                    id="min-partial"
                    type="number"
                    inputMode="numeric"
                    min={0}
                    max={100}
                    step="1"
                    suffix="%"
                    value={knobs.minPartial}
                    onChange={(e) =>
                      setKnobs((k) => ({ ...k, minPartial: e.target.value }))
                    }
                    aria-invalid={!!knobErrors.minPartial}
                    aria-describedby="min-partial-help"
                  />
                  <p
                    id="min-partial-help"
                    className={cn(
                      "text-xs",
                      knobErrors.minPartial
                        ? "text-destructive"
                        : "text-muted-foreground",
                    )}
                  >
                    {knobErrors.minPartial ??
                      `Smallest QR Ph partial payment, as % of the subtotal. On a ₱1,000 order: ₱${(minPartialNumber * 10).toLocaleString()}.`}
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="fallback-price">
                    Fallback price per side
                  </Label>
                  <UnitInput
                    id="fallback-price"
                    type="number"
                    inputMode="decimal"
                    min={0.01}
                    step="0.01"
                    prefix="₱"
                    value={knobs.fallbackPeso}
                    onChange={(e) =>
                      setKnobs((k) => ({ ...k, fallbackPeso: e.target.value }))
                    }
                    aria-invalid={!!knobErrors.fallbackPeso}
                    aria-describedby="fallback-price-help"
                  />
                  <p
                    id="fallback-price-help"
                    className={cn(
                      "text-xs",
                      knobErrors.fallbackPeso
                        ? "text-destructive"
                        : "text-muted-foreground",
                    )}
                  >
                    {knobErrors.fallbackPeso ??
                      "Charged when no price rule matches the job."}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3 border-t pt-4">
                <Button
                  type="submit"
                  disabled={
                    saveKnobsMutation.isPending || !knobsDirty || hasKnobErrors
                  }
                >
                  {saveKnobsMutation.isPending && (
                    <Loader2
                      className="mr-2 h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                  )}
                  Save settings
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setKnobs(knobsFromSettings(settings))}
                  disabled={saveKnobsMutation.isPending || !knobsDirty}
                >
                  Reset
                </Button>
                {knobsDirty && (
                  <span className="text-sm text-muted-foreground" role="status">
                    You have unsaved changes.
                  </span>
                )}
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {/* -------------------------------------------------------- price rules */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Price rules</CardTitle>
              <CardDescription className="max-w-2xl">
                Price per printed side for each paper / color / quality
                combination. Matched most-specific first; wildcards act as
                catch-alls.
              </CardDescription>
            </div>
            <Button onClick={() => openCreate()}>
              <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
              Add rule
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label
                htmlFor="filter-color"
                className="text-xs text-muted-foreground"
              >
                Color
              </Label>
              <Select value={colorFilter} onValueChange={setColorFilter}>
                <SelectTrigger id="filter-color" className="h-9 w-40 sm:w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All colors</SelectItem>
                  {COLOR_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label
                htmlFor="filter-quality"
                className="text-xs text-muted-foreground"
              >
                Quality
              </Label>
              <Select value={qualityFilter} onValueChange={setQualityFilter}>
                <SelectTrigger id="filter-quality" className="h-9 w-40 sm:w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All qualities</SelectItem>
                  {QUALITY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
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
              <Label
                htmlFor="show-inactive"
                className="text-sm text-muted-foreground"
              >
                Show inactive
              </Label>
            </div>
            {filtersActive && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="mb-0.5 text-muted-foreground"
                onClick={() => {
                  setColorFilter("all");
                  setQualityFilter("all");
                }}
              >
                <X className="mr-1 h-4 w-4" aria-hidden="true" />
                Clear filters
              </Button>
            )}
            {rules && rules.length > 0 && (
              <p
                className="ml-auto pb-2 text-xs text-muted-foreground"
                aria-live="polite"
              >
                Showing {visibleRules.length} of {rules.length}
                {hiddenInactiveCount > 0 &&
                  ` · ${hiddenInactiveCount} inactive hidden`}
              </p>
            )}
          </div>

          {rulesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : rulesError || !rules ? (
            <Alert variant="destructive">
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                We couldn&apos;t load the price rules.
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => refetchRules()}
                >
                  Try again
                </Button>
              </AlertDescription>
            </Alert>
          ) : rules.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-md border border-dashed p-8 text-center">
              <Tags
                className="h-8 w-8 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="font-medium">No price rules yet</p>
                <p className="text-sm text-muted-foreground">
                  Until you add one, every job is charged the fallback price.
                </p>
              </div>
              <Button onClick={() => openCreate()}>
                <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
                Add your first rule
              </Button>
            </div>
          ) : visibleRules.length === 0 ? (
            <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              <p>No price rules match these filters.</p>
              {filtersActive && (
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  onClick={() => {
                    setColorFilter("all");
                    setQualityFilter("all");
                  }}
                >
                  Clear filters
                </Button>
              )}
            </div>
          ) : (
            <>
              {/* Phones: one card per rule, because a 7-column table is a sideways scroll. */}
              <ul className="space-y-2 md:hidden">
                {visibleRules.map((rule) => (
                  <li
                    key={rule.id}
                    className={cn(
                      "rounded-md border p-3",
                      !rule.is_active && "opacity-60",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1.5">
                        <p className="font-medium">
                          {sizeText(rule)} · {typeText(rule)}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          <Badge
                            variant={
                              rule.color_mode === "any"
                                ? "outline"
                                : "secondary"
                            }
                          >
                            {colorLabel(rule.color_mode)}
                          </Badge>
                          <Badge
                            variant={
                              rule.print_quality === "any"
                                ? "outline"
                                : "secondary"
                            }
                          >
                            {qualityText(rule)}
                          </Badge>
                        </div>
                      </div>
                      <p className="shrink-0 text-right">
                        <span className="text-lg font-semibold tabular-nums">
                          {peso(rule.price_per_page_peso)}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          per side
                        </span>
                      </p>
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t pt-2">
                      <label className="flex items-center gap-2 text-sm text-muted-foreground">
                        {renderToggle(rule)}
                        {rule.is_active ? "Active" : "Inactive"}
                      </label>
                      {renderActions(rule)}
                    </div>
                  </li>
                ))}
              </ul>

              <div className="hidden overflow-x-auto rounded-md border md:block">
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
                      <TableRow
                        key={rule.id}
                        className={rule.is_active ? "" : "opacity-60"}
                      >
                        <TableCell>
                          {rule.media_size === "any" ? (
                            <Badge variant="outline">Any size</Badge>
                          ) : (
                            paperSizeLabel(rule.media_size)
                          )}
                        </TableCell>
                        <TableCell>
                          {rule.media_type === "any" ? (
                            <Badge variant="outline">Any type</Badge>
                          ) : (
                            paperTypeLabel(rule.media_type)
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              rule.color_mode === "any"
                                ? "outline"
                                : "secondary"
                            }
                          >
                            {colorLabel(rule.color_mode)}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {rule.print_quality === "any" ? (
                            <Badge variant="outline">Any</Badge>
                          ) : (
                            qualityLabel(rule.print_quality)
                          )}
                        </TableCell>
                        <TableCell className="text-right font-medium tabular-nums">
                          {peso(rule.price_per_page_peso)}
                        </TableCell>
                        <TableCell>{renderToggle(rule)}</TableCell>
                        <TableCell className="text-right">
                          {renderActions(rule)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}

          {rules &&
            rules.length > 0 &&
            (hasCatchAll ? (
              <Alert>
                <Info className="h-4 w-4" aria-hidden="true" />
                <AlertDescription>
                  Quotation matches the exact combination first, then relaxes
                  quality → type → size, so keeping a catch-all &quot;Any / Any
                  / Any / Any&quot; rule guarantees every job has a price.
                </AlertDescription>
              </Alert>
            ) : (
              <Alert className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                  <span>
                    There is no active catch-all rule. Jobs that match no rule
                    are charged the fallback price
                    {settings
                      ? ` (${peso(settings.fallback_price_per_side_peso)} per side)`
                      : ""}
                    .
                  </span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      openCreate({
                        media_size: "any",
                        media_type: "any",
                        color_mode: "any",
                        print_quality: "any",
                        price_peso: settings
                          ? settings.fallback_price_per_side_peso.toFixed(2)
                          : "3.00",
                      })
                    }
                  >
                    Add catch-all rule
                  </Button>
                </AlertDescription>
              </Alert>
            ))}
        </CardContent>
      </Card>

      {/* ------------------------------------------------------- rule dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <form
            noValidate
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              saveRuleMutation.mutate();
            }}
          >
            <DialogHeader>
              <DialogTitle>
                {editing ? "Edit price rule" : "Add price rule"}
              </DialogTitle>
              <DialogDescription>
                Choose which jobs this rule covers, then set the price for each
                printed side.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="rule-size">Paper size</Label>
                <Select
                  value={form.media_size}
                  onValueChange={(value) =>
                    setForm((f) => ({ ...f, media_size: value }))
                  }
                >
                  <SelectTrigger id="rule-size">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SIZE_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rule-type">Paper type</Label>
                <Select
                  value={form.media_type}
                  onValueChange={(value) =>
                    setForm((f) => ({ ...f, media_type: value }))
                  }
                >
                  <SelectTrigger id="rule-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TYPE_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rule-color">Color</Label>
                <Select
                  value={form.color_mode}
                  onValueChange={(value) =>
                    setForm((f) => ({ ...f, color_mode: value }))
                  }
                >
                  <SelectTrigger id="rule-color">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COLOR_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rule-quality">Print quality</Label>
                <Select
                  value={form.print_quality}
                  onValueChange={(value) =>
                    setForm((f) => ({ ...f, print_quality: value }))
                  }
                >
                  <SelectTrigger id="rule-quality">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {QUALITY_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rule-price">Price per side</Label>
                <UnitInput
                  id="rule-price"
                  type="number"
                  inputMode="decimal"
                  min={0.01}
                  step={0.01}
                  prefix="₱"
                  value={form.price_peso}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, price_peso: e.target.value }))
                  }
                  aria-invalid={!priceValid}
                  aria-describedby="rule-price-help"
                />
                <p
                  id="rule-price-help"
                  className={cn(
                    "text-xs",
                    priceValid ? "text-muted-foreground" : "text-destructive",
                  )}
                >
                  {!priceValid
                    ? "Price per side must be at least ₱0.01."
                    : duplexPrice !== null
                      ? `Double-sided jobs: about ${peso(duplexPrice)} per side.`
                      : ""}
                </p>
              </div>
              <div className="flex items-center justify-between gap-3 self-start rounded-md border p-3">
                <div>
                  <Label htmlFor="rule-active" className="text-base">
                    Active
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Inactive rules are ignored.
                  </p>
                </div>
                <Switch
                  id="rule-active"
                  checked={form.is_active}
                  onCheckedChange={(isActive) =>
                    setForm((f) => ({ ...f, is_active: isActive }))
                  }
                />
              </div>
            </div>

            {duplicateRule && (
              <Alert className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                <AlertDescription>
                  A rule for this exact combination already exists (
                  {peso(duplicateRule.price_per_page_peso)} per side). Edit that
                  one instead, or saving may be rejected.
                </AlertDescription>
              </Alert>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={saveRuleMutation.isPending || !priceValid}
              >
                {saveRuleMutation.isPending && (
                  <Loader2
                    className="mr-2 h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                )}
                {editing ? "Save changes" : "Add rule"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ----------------------------------------------- delete confirmation */}
      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete price rule?</DialogTitle>
            <DialogDescription className="sr-only">
              This permanently removes the selected price rule.
            </DialogDescription>
          </DialogHeader>
          {deleteTarget && (
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              <p className="font-medium">{ruleSummary(deleteTarget)}</p>
              <p className="text-muted-foreground">
                {peso(deleteTarget.price_per_page_peso)} per side
              </p>
            </div>
          )}
          <p className="text-sm text-muted-foreground">
            Jobs that relied on it will fall back to the next matching rule or
            the fallback price.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() =>
                deleteTarget && deleteRuleMutation.mutate(deleteTarget.id)
              }
              disabled={deleteRuleMutation.isPending}
            >
              {deleteRuleMutation.isPending && (
                <Loader2
                  className="mr-2 h-4 w-4 animate-spin"
                  aria-hidden="true"
                />
              )}
              Delete rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
