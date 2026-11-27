import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  COLOR_MODE_LABELS,
  ORIENTATION_LABELS,
  PAPER_SIZE_LABELS,
  PAPER_SOURCE_LABELS,
  PAPER_TYPE_LABELS,
  QUALITY_LABELS,
  SIDES_LABELS,
} from "@/lib/constants";
import { apiErrorMessage } from "@/lib/api";
import {
  centavosToPesoInput,
  createCatalogueProduct,
  pesoToCentavos,
  updateCatalogueProduct,
} from "@/lib/catalogue";
import type {
  CatalogueDefaultSpec,
  CatalogueProduct,
  CatalogueProductPayload,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const EMPTY_SPEC: CatalogueDefaultSpec = {
  media_size: "ps_a4",
  media_type: "pt_plainpaper",
  color_mode: "mono",
  sides: "none",
  print_quality: "normal",
  copies: 1,
  borderless: false,
  orientation: "portrait",
  source: "auto",
  reverse_order: false,
  collate: true,
};

interface ProductFormState {
  name: string;
  description: string;
  category: string;
  price_peso: string;
  unit_label: string;
  min_quantity: string;
  max_quantity: string;
  display_order: string;
  is_active: boolean;
  is_featured: boolean;
  default_spec: CatalogueDefaultSpec;
  instructions: string;
}

type FormErrors = Partial<Record<keyof ProductFormState | "default_spec", string>>;

function formFromProduct(product: CatalogueProduct | null): ProductFormState {
  return {
    name: product?.name ?? "",
    description: product?.description ?? "",
    category: product?.category ?? "",
    price_peso: product ? centavosToPesoInput(product.price) : "30.00",
    unit_label: product?.unit_label ?? "piece",
    min_quantity: String(product?.min_quantity ?? 1),
    max_quantity: product?.max_quantity === null ? "" : String(product?.max_quantity ?? 99),
    display_order: String(product?.display_order ?? 0),
    is_active: product?.is_active ?? true,
    is_featured: product?.is_featured ?? false,
    default_spec: { ...EMPTY_SPEC, ...product?.default_spec },
    instructions: product?.instructions ?? "",
  };
}

/** Validate locally and build the exact centavo-based admin API payload. */
export function catalogueProductPayload(
  form: ProductFormState,
): { payload: CatalogueProductPayload; errors: FormErrors } {
  const errors: FormErrors = {};
  if (!form.name.trim()) errors.name = "Enter a product name.";
  if (!form.category.trim()) errors.category = "Enter a category.";
  if (!form.unit_label.trim()) errors.unit_label = "Enter a unit label.";

  let price = 0;
  try {
    price = pesoToCentavos(form.price_peso);
    if (price < 1) errors.price_peso = "Price must be at least ₱0.01.";
  } catch (error) {
    errors.price_peso = error instanceof Error ? error.message : "Enter a valid price.";
  }

  const minimum = Number(form.min_quantity);
  if (!/^\d+$/.test(form.min_quantity) || !Number.isSafeInteger(minimum) || minimum < 1) {
    errors.min_quantity = "Minimum quantity must be a whole number of at least 1.";
  }
  let maximum: number | null = null;
  if (form.max_quantity.trim()) {
    maximum = Number(form.max_quantity);
    if (!/^\d+$/.test(form.max_quantity) || !Number.isSafeInteger(maximum) || maximum < 1) {
      errors.max_quantity = "Maximum quantity must be a positive whole number.";
    } else if (!errors.min_quantity && maximum < minimum) {
      errors.max_quantity = "Maximum quantity cannot be less than the minimum.";
    }
  }
  const displayOrder = Number(form.display_order);
  if (
    !/^\d+$/.test(form.display_order) ||
    !Number.isSafeInteger(displayOrder) ||
    displayOrder < 0
  ) {
    errors.display_order = "Display order must be a non-negative whole number.";
  }

  const payload: CatalogueProductPayload = {
    name: form.name.trim(),
    description: form.description.trim(),
    category: form.category.trim(),
    price,
    unit_label: form.unit_label.trim(),
    min_quantity: minimum,
    max_quantity: maximum,
    display_order: displayOrder,
    is_active: form.is_active,
    is_featured: form.is_featured,
    default_spec: { ...form.default_spec, copies: 1 },
    instructions: form.instructions.trim(),
  };
  return { payload, errors };
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return <p id={id} className="text-sm text-destructive">{message}</p>;
}

function SpecSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger aria-label={label}><SelectValue /></SelectTrigger>
        <SelectContent>
          {Object.entries(options).map(([code, text]) => (
            <SelectItem key={code} value={code}>{text}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

interface CatalogueProductFormProps {
  open: boolean;
  product: CatalogueProduct | null;
  onOpenChange: (open: boolean) => void;
  onSaved?: (product: CatalogueProduct) => void;
}

/** Create/edit dialog for fixed-price catalogue services. */
export default function CatalogueProductForm({
  open,
  product,
  onOpenChange,
  onSaved,
}: CatalogueProductFormProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ProductFormState>(() => formFromProduct(product));
  const [errors, setErrors] = useState<FormErrors>({});

  useEffect(() => {
    if (open) {
      setForm(formFromProduct(product));
      setErrors({});
    }
  }, [open, product]);

  function update<K extends keyof ProductFormState>(key: K, value: ProductFormState[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
    setErrors((previous) => ({ ...previous, [key]: undefined }));
  }

  function updateSpec<K extends keyof CatalogueDefaultSpec>(
    key: K,
    value: CatalogueDefaultSpec[K],
  ) {
    setForm((previous) => ({
      ...previous,
      default_spec: { ...previous.default_spec, [key]: value },
    }));
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const result = catalogueProductPayload(form);
      if (Object.keys(result.errors).length > 0) {
        setErrors(result.errors);
        throw new Error("Please fix the highlighted fields.");
      }
      return product
        ? updateCatalogueProduct(product.id, result.payload)
        : createCatalogueProduct(result.payload);
    },
    onSuccess: (saved) => {
      toast.success(product ? "Catalogue product updated." : "Catalogue product created.");
      queryClient.invalidateQueries({ queryKey: ["admin-catalogue-products"] });
      queryClient.invalidateQueries({ queryKey: ["catalogue-products"] });
      onOpenChange(false);
      onSaved?.(saved);
    },
    onError: (error) => {
      if (error.message !== "Please fix the highlighted fields.") {
        toast.error(apiErrorMessage(error));
      }
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{product ? "Edit catalogue product" : "New catalogue product"}</DialogTitle>
          <DialogDescription>
            The fixed unit price is snapshotted when an order is placed. Later edits never reprice existing orders.
          </DialogDescription>
        </DialogHeader>
        <form id="catalogue-product-form" onSubmit={onSubmit} className="space-y-5" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="product-name">Name</Label>
              <Input
                id="product-name"
                value={form.name}
                onChange={(event) => update("name", event.target.value)}
                aria-invalid={!!errors.name}
                placeholder="e.g. 2x2 ID Picture"
              />
              <FieldError id="product-name-error" message={errors.name} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-category">Category</Label>
              <Input
                id="product-category"
                value={form.category}
                onChange={(event) => update("category", event.target.value)}
                aria-invalid={!!errors.category}
                placeholder="e.g. ID photos"
              />
              <FieldError id="product-category-error" message={errors.category} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-price">Fixed price (pesos)</Label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">₱</span>
                <Input
                  id="product-price"
                  className={cn("pl-7", errors.price_peso && "border-destructive")}
                  inputMode="decimal"
                  value={form.price_peso}
                  onChange={(event) => update("price_peso", event.target.value)}
                  aria-invalid={!!errors.price_peso}
                  placeholder="30.00"
                />
              </div>
              <FieldError id="product-price-error" message={errors.price_peso} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-unit">Unit label</Label>
              <Input
                id="product-unit"
                value={form.unit_label}
                onChange={(event) => update("unit_label", event.target.value)}
                aria-invalid={!!errors.unit_label}
                placeholder="piece"
              />
              <FieldError id="product-unit-error" message={errors.unit_label} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-description">Description</Label>
              <Textarea
                id="product-description"
                value={form.description}
                onChange={(event) => update("description", event.target.value)}
                placeholder="What the customer receives"
                rows={3}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-instructions">Customer and staff instructions</Label>
              <Textarea
                id="product-instructions"
                value={form.instructions}
                onChange={(event) => update("instructions", event.target.value)}
                placeholder="Explain what to upload and how the shop prepares it"
                rows={4}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="product-min">Minimum quantity</Label>
              <Input
                id="product-min"
                type="number"
                min={1}
                step={1}
                value={form.min_quantity}
                onChange={(event) => update("min_quantity", event.target.value)}
                aria-invalid={!!errors.min_quantity}
              />
              <FieldError id="product-min-error" message={errors.min_quantity} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-max">Maximum quantity</Label>
              <Input
                id="product-max"
                type="number"
                min={1}
                step={1}
                value={form.max_quantity}
                onChange={(event) => update("max_quantity", event.target.value)}
                aria-invalid={!!errors.max_quantity}
                placeholder="No limit"
              />
              <FieldError id="product-max-error" message={errors.max_quantity} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="product-order">Display order</Label>
              <Input
                id="product-order"
                type="number"
                min={0}
                step={1}
                value={form.display_order}
                onChange={(event) => update("display_order", event.target.value)}
                aria-invalid={!!errors.display_order}
              />
              <FieldError id="product-order-error" message={errors.display_order} />
            </div>
          </div>

          <div className="flex flex-wrap gap-6 rounded-md border p-3">
            <div className="flex items-center gap-2">
              <Switch
                id="product-active"
                checked={form.is_active}
                onCheckedChange={(checked) => update("is_active", checked)}
              />
              <Label htmlFor="product-active">Active (available to order)</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="product-featured"
                checked={form.is_featured}
                onCheckedChange={(checked) => update("is_featured", checked)}
              />
              <Label htmlFor="product-featured">Featured on home page</Label>
            </div>
          </div>

          <fieldset className="space-y-4">
            <legend className="text-sm font-semibold">Default print settings</legend>
            <p className="text-xs text-muted-foreground">
              Catalogue quantity is separate from printer copies. Epson copies are always fixed at one.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <SpecSelect
                label="Paper size"
                value={form.default_spec.media_size ?? "ps_a4"}
                options={PAPER_SIZE_LABELS}
                onChange={(value) => updateSpec("media_size", value)}
              />
              <SpecSelect
                label="Paper type"
                value={form.default_spec.media_type ?? "pt_plainpaper"}
                options={PAPER_TYPE_LABELS}
                onChange={(value) => updateSpec("media_type", value)}
              />
              <SpecSelect
                label="Color mode"
                value={form.default_spec.color_mode ?? "mono"}
                options={COLOR_MODE_LABELS}
                onChange={(value) => updateSpec("color_mode", value as CatalogueDefaultSpec["color_mode"])}
              />
              <SpecSelect
                label="Sides"
                value={form.default_spec.sides ?? "none"}
                options={SIDES_LABELS}
                onChange={(value) => updateSpec("sides", value as CatalogueDefaultSpec["sides"])}
              />
              <SpecSelect
                label="Print quality"
                value={form.default_spec.print_quality ?? "normal"}
                options={QUALITY_LABELS}
                onChange={(value) => updateSpec("print_quality", value as CatalogueDefaultSpec["print_quality"])}
              />
              <SpecSelect
                label="Orientation"
                value={form.default_spec.orientation ?? "portrait"}
                options={ORIENTATION_LABELS}
                onChange={(value) => updateSpec("orientation", value as CatalogueDefaultSpec["orientation"])}
              />
              <SpecSelect
                label="Paper source"
                value={form.default_spec.source ?? "auto"}
                options={PAPER_SOURCE_LABELS}
                onChange={(value) => updateSpec("source", value)}
              />
            </div>
            <div className="flex flex-wrap gap-6">
              {([
                ["borderless", "Borderless"],
                ["reverse_order", "Reverse order"],
                ["collate", "Collate"],
              ] as const).map(([key, label]) => (
                <div key={key} className="flex items-center gap-2">
                  <Switch
                    id={`product-spec-${key}`}
                    checked={form.default_spec[key] ?? false}
                    onCheckedChange={(checked) => updateSpec(key, checked)}
                  />
                  <Label htmlFor={`product-spec-${key}`}>{label}</Label>
                </div>
              ))}
            </div>
          </fieldset>
        </form>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saveMutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="catalogue-product-form" disabled={saveMutation.isPending}>
            {saveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
            {product ? "Save changes" : "Create product"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
