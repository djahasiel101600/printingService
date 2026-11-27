import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Archive,
  AlertTriangle,
  ImagePlus,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Star,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import CatalogueProductForm from "@/components/CatalogueProductForm";
import { apiErrorMessage } from "@/lib/api";
import {
  archiveCatalogueProduct,
  fetchAllAdminCatalogueProducts,
  updateCatalogueProduct,
} from "@/lib/catalogue";
import {
  colorModeLabel,
  paperSizeLabel,
  paperTypeLabel,
  qualityLabel,
  sidesLabel,
} from "@/lib/constants";
import type { CatalogueProduct } from "@/lib/types";
import { formatPeso } from "@/lib/utils";

function useDebounced(value: string, delay = 250) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function specSummary(product: CatalogueProduct): string {
  const spec = product.default_spec;
  return [
    paperSizeLabel(spec.media_size ?? "ps_a4"),
    paperTypeLabel(spec.media_type ?? "pt_plainpaper"),
    colorModeLabel(spec.color_mode ?? "mono"),
    qualityLabel(spec.print_quality ?? "normal"),
    sidesLabel(spec.sides ?? "none"),
  ].join(" · ");
}

export default function AdminCataloguePage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<CatalogueProduct | null>(null);
  const [archiving, setArchiving] = useState<CatalogueProduct | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ["admin-catalogue-categories"],
    queryFn: () => fetchAllAdminCatalogueProducts(),
  });
  const categories = Array.from(
    new Set((categoriesQuery.data ?? []).map((product) => product.category)),
  ).sort((a, b) => a.localeCompare(b));

  const productsQuery = useQuery({
    queryKey: ["admin-catalogue-products", { search: debouncedSearch, category, status }],
    queryFn: () =>
      fetchAllAdminCatalogueProducts({
        search: debouncedSearch.trim() || undefined,
        category: category === "all" ? undefined : category,
        status: status === "all" ? undefined : status as "active" | "archived",
      }),
  });
  const products = productsQuery.data ?? [];

  const toggleMutation = useMutation({
    mutationFn: async ({
      product,
      field,
    }: {
      product: CatalogueProduct;
      field: "is_active" | "is_featured";
    }) => updateCatalogueProduct(product.id, { [field]: !product[field] }),
    onSuccess: (saved, variables) => {
      toast.success(
        variables.field === "is_active"
          ? saved.is_active
            ? "Product reactivated."
            : "Product archived."
          : saved.is_featured
            ? "Product featured on the home page."
            : "Product removed from featured products.",
      );
      queryClient.invalidateQueries({ queryKey: ["admin-catalogue-products"] });
      queryClient.invalidateQueries({ queryKey: ["admin-catalogue-categories"] });
      queryClient.invalidateQueries({ queryKey: ["catalogue-products"] });
    },
    onError: (error) => toast.error(apiErrorMessage(error)),
  });

  const archiveMutation = useMutation({
    mutationFn: (product: CatalogueProduct) => archiveCatalogueProduct(product.id),
    onSuccess: () => {
      toast.success("Product archived. Existing orders keep their original price.");
      setArchiving(null);
      queryClient.invalidateQueries({ queryKey: ["admin-catalogue-products"] });
      queryClient.invalidateQueries({ queryKey: ["admin-catalogue-categories"] });
      queryClient.invalidateQueries({ queryKey: ["catalogue-products"] });
    },
    onError: (error) => toast.error(apiErrorMessage(error)),
  });

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(product: CatalogueProduct) {
    setEditing(product);
    setFormOpen(true);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">Catalogue</h1>
          <p className="max-w-2xl text-muted-foreground">
            Manage fixed-price services, quantity limits, and the print defaults used for new orders.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          New product
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Products</CardTitle>
          <CardDescription>
            Archive products instead of deleting them so historical orders remain intact.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_10rem]">
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                type="search"
                aria-label="Search catalogue"
                placeholder="Search by name, description or category"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="pl-9"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="catalogue-category-filter" className="sr-only">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="catalogue-category-filter" aria-label="Filter by category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {categories.map((item) => (
                    <SelectItem key={item} value={item}>{item}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="catalogue-status-filter" className="sr-only">Status</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger id="catalogue-status-filter" aria-label="Filter by status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {productsQuery.isLoading ? (
            <div className="space-y-2" aria-label="Loading catalogue products">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-16 w-full" />
              ))}
            </div>
          ) : productsQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                <span>We couldn&apos;t load the catalogue.</span>
                <Button type="button" variant="outline" size="sm" onClick={() => productsQuery.refetch()}>
                  <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
                  Try again
                </Button>
              </AlertDescription>
            </Alert>
          ) : products.length === 0 ? (
            <div className="rounded-md border border-dashed px-4 py-10 text-center">
              <p className="font-medium">No products match these filters.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Clear the filters or create a new catalogue service.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Product</TableHead>
                    <TableHead>Fixed price</TableHead>
                    <TableHead>Quantity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Featured</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((product) => (
                    <TableRow key={product.id}>
                      <TableCell className="min-w-56 max-w-md">
                        <div className="flex items-start gap-3">
                          {product.cover_image_url ? (
                            <img
                              src={product.cover_image_url}
                              alt={`${product.name} cover photo`}
                              loading="lazy"
                              className="h-12 w-12 shrink-0 rounded-md object-cover"
                            />
                          ) : (
                            <div
                              aria-hidden="true"
                              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground"
                            >
                              <ImagePlus className="h-5 w-5" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="font-medium">{product.name}</p>
                            <p className="text-xs text-muted-foreground">{product.category}</p>
                            {product.description && (
                              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{product.description}</p>
                            )}
                            <p className="mt-1 text-[11px] text-muted-foreground">{specSummary(product)}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap font-medium tabular-nums">
                        {formatPeso(product.price_peso)}
                        <span className="block text-xs font-normal text-muted-foreground">per {product.unit_label}</span>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm">
                        {product.min_quantity}–{product.max_quantity ?? "∞"} {product.unit_label}s
                        <span className="block text-xs text-muted-foreground">Order: {product.display_order}</span>
                      </TableCell>
                      <TableCell>
                        <Badge variant={product.is_active ? "default" : "secondary"}>
                          {product.is_active ? "Active" : "Archived"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className={product.is_featured ? "text-amber-600" : "text-muted-foreground"}
                          disabled={toggleMutation.isPending || !product.is_active}
                          onClick={() => toggleMutation.mutate({ product, field: "is_featured" })}
                          aria-label={`${product.is_featured ? "Unfeature" : "Feature"} ${product.name}`}
                          aria-pressed={product.is_featured}
                        >
                          <Star className={`mr-2 h-4 w-4 ${product.is_featured ? "fill-current" : ""}`} aria-hidden="true" />
                          {product.is_featured ? "Featured" : "Not featured"}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <Button type="button" variant="ghost" size="sm" onClick={() => openEdit(product)}>
                            <Pencil className="mr-2 h-4 w-4" aria-hidden="true" />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="text-destructive"
                            disabled={!product.is_active || archiveMutation.isPending}
                            onClick={() => setArchiving(product)}
                          >
                            <Archive className="mr-2 h-4 w-4" aria-hidden="true" />
                            Archive
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <CatalogueProductForm
        open={formOpen}
        product={editing}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(null);
        }}
      />

      <Dialog open={!!archiving} onOpenChange={(open) => !open && setArchiving(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive {archiving?.name}?</DialogTitle>
            <DialogDescription>
              It will disappear from the public catalogue and cannot be selected for new orders.
              Existing orders keep their snapshotted name, price, quantity limits, and instructions.
              You can reactivate it later by editing the product.
            </DialogDescription>
          </DialogHeader>
          <Alert variant="warning">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>This does not cancel or reprice any existing order.</AlertDescription>
          </Alert>
          <DialogFooter>
            <Button variant="outline" onClick={() => setArchiving(null)} disabled={archiveMutation.isPending}>
              Keep active
            </Button>
            <Button
              variant="destructive"
              onClick={() => archiving && archiveMutation.mutate(archiving)}
              disabled={archiveMutation.isPending}
            >
              {archiveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
              Archive product
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
