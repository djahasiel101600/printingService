import { Loader2, RefreshCw } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";
import QuoteBreakdown from "@/components/QuoteBreakdown";
import { apiErrorMessage } from "@/lib/api";
import type { CatalogueProduct, Quote } from "@/lib/types";
import { cn } from "@/lib/utils";
import { formatPeso } from "@/lib/utils";

export interface CatalogueOrderErrors {
  product?: string;
  quantity?: string;
  quote?: string;
}

interface CatalogueOrderFieldsProps {
  products: CatalogueProduct[];
  isLoading: boolean;
  loadError: unknown;
  onRetryProducts: () => void;
  productId: string;
  quantity: string;
  instructions: string;
  errors?: CatalogueOrderErrors;
  quote: Quote | null;
  quoteLoading: boolean;
  quoteError: unknown;
  onRetryQuote: () => void;
  onProductChange: (id: string) => void;
  onQuantityChange: (quantity: string) => void;
  onInstructionsChange: (instructions: string) => void;
}

/** Fixed-price service selection used by both guest and admin order creation. */
export default function CatalogueOrderFields({
  products,
  isLoading,
  loadError,
  onRetryProducts,
  productId,
  quantity,
  instructions,
  errors,
  quote,
  quoteLoading,
  quoteError,
  onRetryQuote,
  onProductChange,
  onQuantityChange,
  onInstructionsChange,
}: CatalogueOrderFieldsProps) {
  const product = products.find((item) => String(item.id) === productId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2.5">
          <span
            aria-hidden="true"
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
          >
            1
          </span>
          Choose a catalogue service
        </CardTitle>
        <CardDescription>
          Pick a fixed-price service and the number of finished pieces you need.
          The shop prepares the final layout from your source file.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {isLoading ? (
          <div className="space-y-3" aria-label="Loading catalogue services">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : loadError ? (
          <Alert variant="destructive">
            <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
              <span>We couldn&apos;t load the catalogue. Please try again.</span>
              <Button type="button" variant="outline" size="sm" onClick={onRetryProducts}>
                <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
                Try again
              </Button>
            </AlertDescription>
          </Alert>
        ) : products.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No catalogue services are available right now. You can still place a custom print order.
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="catalogue-product">Service</Label>
              <Select
                value={productId}
                onValueChange={onProductChange}
                disabled={isLoading}
              >
                <SelectTrigger
                  id="catalogue-product"
                  aria-invalid={!!errors?.product}
                  aria-describedby={errors?.product ? "catalogue-product-error" : undefined}
                  className={cn(errors?.product && "border-destructive")}
                >
                  <SelectValue placeholder="Choose a service" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.name} — {formatPeso(item.price_peso)}/{item.unit_label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors?.product && (
                <p id="catalogue-product-error" role="alert" className="text-sm text-destructive">
                  {errors.product}
                </p>
              )}
            </div>

            {product && (
              <div className="rounded-md border bg-muted/40 p-3 text-sm">
                <div className="flex flex-col gap-3 sm:flex-row">
                  {product.cover_image_url && (
                    <img
                      src={product.cover_image_url}
                      alt={`${product.name} cover photo`}
                      loading="lazy"
                      decoding="async"
                      className="h-32 w-full rounded-md object-cover sm:h-24 sm:w-32 sm:shrink-0"
                    />
                  )}
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium">{product.name}</p>
                      <span className="text-xs text-muted-foreground">{product.category}</span>
                    </div>
                    {product.description && (
                      <p className="text-muted-foreground">{product.description}</p>
                    )}
                    <p className="font-medium">
                      {formatPeso(product.price_peso)} per {product.unit_label}
                    </p>
                    {product.instructions && (
                      <Alert>
                        <AlertDescription className="whitespace-pre-line">
                          {product.instructions}
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="catalogue-quantity">Quantity</Label>
              <Input
                id="catalogue-quantity"
                type="number"
                inputMode="numeric"
                min={product?.min_quantity ?? 1}
                max={product?.max_quantity ?? undefined}
                step={1}
                value={quantity}
                onChange={(event) => onQuantityChange(event.target.value)}
                disabled={!product}
                aria-invalid={!!errors?.quantity}
                aria-describedby={errors?.quantity ? "catalogue-quantity-error" : undefined}
                className={cn("max-w-40", errors?.quantity && "border-destructive")}
              />
              <p className="text-xs text-muted-foreground">
                {product
                  ? product.max_quantity === null
                    ? `At least ${product.min_quantity} ${product.unit_label}${product.min_quantity === 1 ? "" : "s"}.`
                    : `${product.min_quantity}–${product.max_quantity} ${product.unit_label}s.`
                  : "Choose a service to set the quantity."}
              </p>
              {errors?.quantity && (
                <p id="catalogue-quantity-error" role="alert" className="text-sm text-destructive">
                  {errors.quantity}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="catalogue-instructions">Notes for the shop (optional)</Label>
              <Textarea
                id="catalogue-instructions"
                value={instructions}
                onChange={(event) => onInstructionsChange(event.target.value)}
                placeholder="Anything the shop should know about your source file"
                rows={3}
              />
            </div>

            <div className="rounded-md border bg-muted/40 p-3" aria-live="polite">
              {quoteLoading ? (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Calculating the fixed price…
                </p>
              ) : quoteError ? (
                <div className="space-y-2">
                  <p role="alert" className="text-sm text-destructive">
                    {apiErrorMessage(quoteError)}
                  </p>
                  <Button type="button" variant="outline" size="sm" onClick={onRetryQuote}>
                    <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
                    Try again
                  </Button>
                </div>
              ) : quote ? (
                <div className="space-y-3">
                  <QuoteBreakdown lines={quote.lines} title="Fixed price" />
                  <div className="flex items-center justify-between gap-3 border-t pt-3">
                    <span className="text-sm font-medium">Fixed total</span>
                    <span className="text-lg font-bold tabular-nums">
                      {formatPeso(quote.subtotal_peso)}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Choose a service and enter a valid quantity to see the fixed price.
                </p>
              )}
              {errors?.quote && (
                <p role="alert" className="mt-2 text-sm text-destructive">
                  {errors.quote}
                </p>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
