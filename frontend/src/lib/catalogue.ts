import { api } from "@/lib/api";
import type {
  CatalogueProduct,
  CatalogueProductPayload,
  Paginated,
} from "@/lib/types";

export const CATALOGUE_COVER_IMAGE_MAX_BYTES = 5 * 1024 * 1024;

const COVER_IMAGE_TYPES: Record<string, string[]> = {
  "image/jpeg": ["jpg", "jpeg"],
  "image/png": ["png"],
  "image/webp": ["webp"],
};

export function validateCatalogueCoverImage(file: File): string | null {
  if (file.size > CATALOGUE_COVER_IMAGE_MAX_BYTES) {
    return "Cover photo must be 5 MB or smaller.";
  }
  const extensions = COVER_IMAGE_TYPES[file.type];
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!extensions || !extensions.includes(extension)) {
    return "Use a JPEG, PNG, or WebP cover photo with a matching file extension.";
  }
  return null;
}

export interface CatalogueProductQuery {
  search?: string;
  category?: string;
  featured?: boolean;
  status?: "active" | "archived";
  page?: number;
}

/**
 * Convert an admin-entered decimal peso string to centavos without going
 * through floating-point arithmetic. Exponents and extra precision are
 * rejected rather than silently rounded.
 */
export function pesoToCentavos(value: string): number {
  const trimmed = value.trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(trimmed)) {
    throw new Error("Enter a price in pesos with at most two decimal places.");
  }
  const [whole, fraction = ""] = trimmed.split(".");
  const centavos = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(centavos)) {
    throw new Error("The price is too large.");
  }
  return centavos;
}

/** Format stored centavos for an editable peso input, also without floats. */
export function centavosToPesoInput(centavos: number): string {
  if (!Number.isSafeInteger(centavos) || centavos < 0) {
    throw new Error("Price must be a non-negative whole number of centavos.");
  }
  return `${Math.floor(centavos / 100)}.${String(centavos % 100).padStart(2, "0")}`;
}

function asPaginated<T>(data: T[] | Paginated<T>): Paginated<T> {
  if (Array.isArray(data)) {
    return { count: data.length, next: null, previous: null, results: data };
  }
  return data;
}

export async function fetchCatalogueProducts(
  params: CatalogueProductQuery = {},
): Promise<Paginated<CatalogueProduct>> {
  const { data } = await api.get<CatalogueProduct[] | Paginated<CatalogueProduct>>(
    "/catalogue/products/",
    { params },
  );
  return asPaginated(data);
}

export async function fetchAllCatalogueProducts(
  params: Omit<CatalogueProductQuery, "page"> = {},
): Promise<CatalogueProduct[]> {
  const products: CatalogueProduct[] = [];
  for (let page = 1; page <= 20; page += 1) {
    const result = await fetchCatalogueProducts({ ...params, page });
    products.push(...result.results);
    if (products.length >= result.count || !result.next) break;
  }
  return products;
}

export async function fetchAdminCatalogueProducts(
  params: CatalogueProductQuery = {},
): Promise<Paginated<CatalogueProduct>> {
  const { data } = await api.get<CatalogueProduct[] | Paginated<CatalogueProduct>>(
    "/admin/catalogue/products/",
    { params },
  );
  return asPaginated(data);
}

export async function fetchAllAdminCatalogueProducts(
  params: Omit<CatalogueProductQuery, "page"> = {},
): Promise<CatalogueProduct[]> {
  const products: CatalogueProduct[] = [];
  for (let page = 1; page <= 20; page += 1) {
    const result = await fetchAdminCatalogueProducts({ ...params, page });
    products.push(...result.results);
    if (products.length >= result.count || !result.next) break;
  }
  return products;
}

function catalogueRequestData(payload: Partial<CatalogueProductPayload>) {
  const coverImage = payload.cover_image;
  if (typeof File === "undefined" || !(coverImage instanceof File)) {
    return payload;
  }

  const data = new FormData();
  for (const [key, value] of Object.entries(payload)) {
    if (key === "cover_image") {
      data.append(key, value as File);
    } else if (value !== undefined) {
      // DRF interprets an empty multipart value as null for nullable fields.
      // Preserve explicit nulls so PATCH can clear limits during a cover upload.
      data.append(
        key,
        value === null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value),
      );
    }
  }
  return data;
}

export function createCatalogueProduct(
  payload: CatalogueProductPayload,
): Promise<CatalogueProduct> {
  return api
    .post<CatalogueProduct>("/admin/catalogue/products/", catalogueRequestData(payload))
    .then(({ data }) => data);
}

export function updateCatalogueProduct(
  id: number,
  payload: Partial<CatalogueProductPayload>,
): Promise<CatalogueProduct> {
  return api
    .patch<CatalogueProduct>(`/admin/catalogue/products/${id}/`, catalogueRequestData(payload))
    .then(({ data }) => data);
}

export function archiveCatalogueProduct(id: number): Promise<void> {
  return api.delete(`/admin/catalogue/products/${id}/`).then(() => undefined);
}
