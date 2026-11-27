import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CatalogueProductForm, {
  catalogueProductPayload,
} from "@/components/CatalogueProductForm";
import QuoteBreakdown from "@/components/QuoteBreakdown";
import {
  centavosToPesoInput,
  pesoToCentavos,
  validateCatalogueCoverImage,
} from "@/lib/catalogue";
import type { CatalogueProductPayload, QuoteLine } from "@/lib/types";
import { catalogueProduct, catalogueQuote } from "@/test/catalogue-fixtures";

const { createMock, updateMock, postMock, patchMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
}));

vi.mock("@/lib/catalogue", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/catalogue")>();
  return {
    ...actual,
    createCatalogueProduct: createMock,
    updateCatalogueProduct: updateMock,
  };
});
vi.mock("@/lib/api", () => ({
  api: { post: postMock, patch: patchMock },
  apiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const validForm = {
  name: "2x2 ID Picture",
  description: "Shop-prepared prints",
  category: "ID photos",
  price_peso: "30.25",
  unit_label: "piece",
  min_quantity: "2",
  max_quantity: "99",
  display_order: "0",
  is_active: true,
  is_featured: true,
  default_spec: { ...catalogueProduct.default_spec, copies: 7 },
  instructions: "Upload one photo.",
};

function renderForm(product: typeof catalogueProduct | null = null) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <CatalogueProductForm
        open
        product={product}
        onOpenChange={onOpenChange}
      />
    </QueryClientProvider>,
  );
  return { client, invalidate, onOpenChange };
}

beforeEach(() => {
  createMock.mockReset();
  updateMock.mockReset();
  postMock.mockReset();
  patchMock.mockReset();
  postMock.mockResolvedValue({ data: catalogueProduct });
  patchMock.mockResolvedValue({ data: catalogueProduct });
});

describe("catalogue currency and payload validation", () => {
  it("converts decimal peso strings to exact centavos", () => {
    expect(pesoToCentavos("0.01")).toBe(1);
    expect(pesoToCentavos("30")).toBe(3000);
    expect(pesoToCentavos("30.5")).toBe(3050);
    expect(pesoToCentavos("30.25")).toBe(3025);
    expect(centavosToPesoInput(3025)).toBe("30.25");
    expect(() => pesoToCentavos("30.001")).toThrow(/at most two decimal places/);
    expect(() => pesoToCentavos("3e1")).toThrow(/at most two decimal places/);
  });

  it("builds a centavo payload and forces Epson copies to one", () => {
    const result = catalogueProductPayload(validForm);

    expect(result.errors).toEqual({});
    expect(result.payload).toEqual({
      name: "2x2 ID Picture",
      description: "Shop-prepared prints",
      category: "ID photos",
      price: 3025,
      unit_label: "piece",
      min_quantity: 2,
      max_quantity: 99,
      display_order: 0,
      is_active: true,
      is_featured: true,
      default_spec: { ...catalogueProduct.default_spec, copies: 1 },
      instructions: "Upload one photo.",
    });
  });

  it("rejects zero prices and reversed quantity bounds", () => {
    const result = catalogueProductPayload({
      ...validForm,
      name: " ",
      price_peso: "0.00",
      min_quantity: "10",
      max_quantity: "2",
    });

    expect(result.errors.name).toBe("Enter a product name.");
    expect(result.errors.price_peso).toBe("Price must be at least ₱0.01.");
    expect(result.errors.max_quantity).toBe("Maximum quantity cannot be less than the minimum.");
  });
});

describe("catalogue cover image API", () => {
  it("serializes uploads as multipart while preserving nested specs and booleans", async () => {
    const actual = await vi.importActual<typeof import("@/lib/catalogue")>("@/lib/catalogue");
    const base = catalogueProductPayload(validForm).payload;
    const cover = new File([new Uint8Array([1, 2, 3])], "cover.png", { type: "image/png" });
    const payload: CatalogueProductPayload = { ...base, max_quantity: null, cover_image: cover };

    await actual.createCatalogueProduct(payload);

    expect(postMock).toHaveBeenCalledTimes(1);
    const [url, body] = postMock.mock.calls[0];
    expect(url).toBe("/admin/catalogue/products/");
    expect(body).toBeInstanceOf(FormData);
    const formData = body as FormData;
    expect(formData.get("cover_image")).toBe(cover);
    expect(formData.get("default_spec")).toBe(JSON.stringify({
      ...catalogueProduct.default_spec,
      copies: 1,
    }));
    expect(formData.get("is_active")).toBe("true");
    expect(formData.get("is_featured")).toBe("true");
    expect(formData.get("max_quantity")).toBe("");
  });

  it("preserves an explicit null when updating another field with a cover upload", async () => {
    const actual = await vi.importActual<typeof import("@/lib/catalogue")>("@/lib/catalogue");
    const cover = new File([new Uint8Array([1, 2, 3])], "cover.png", { type: "image/png" });

    await actual.updateCatalogueProduct(1, { max_quantity: null, cover_image: cover });

    const [url, body] = patchMock.mock.calls[0];
    expect(url).toBe("/admin/catalogue/products/1/");
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("max_quantity")).toBe("");
    expect((body as FormData).get("cover_image")).toBe(cover);
  });

  it("sends explicit cover removal as JSON null", async () => {
    const actual = await vi.importActual<typeof import("@/lib/catalogue")>("@/lib/catalogue");

    await actual.updateCatalogueProduct(1, { cover_image: null });

    expect(patchMock).toHaveBeenCalledWith("/admin/catalogue/products/1/", { cover_image: null });
  });

  it("rejects unsupported types, mismatched extensions, and oversized files", () => {
    expect(validateCatalogueCoverImage(new File(["png"], "cover.png", { type: "image/png" }))).toBeNull();
    expect(validateCatalogueCoverImage(new File(["webp"], "cover.webp", { type: "image/webp" }))).toBeNull();
    expect(validateCatalogueCoverImage(new File(["gif"], "cover.gif", { type: "image/gif" }))).toMatch(/JPEG, PNG, or WebP/);
    expect(validateCatalogueCoverImage(new File(["png"], "cover.jpg", { type: "image/png" }))).toMatch(/matching file extension/);
    const oversized = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "cover.png", { type: "image/png" });
    expect(validateCatalogueCoverImage(oversized)).toMatch(/5 MB or smaller/);
  });
});

describe("CatalogueProductForm", () => {
  it("creates a product with an exact centavo payload and invalidates caches", async () => {
    const user = userEvent.setup();
    createMock.mockResolvedValue(catalogueProduct);
    const { invalidate, onOpenChange } = renderForm();

    await user.type(screen.getByLabelText("Name"), validForm.name);
    await user.type(screen.getByLabelText("Category"), validForm.category);
    const price = screen.getByLabelText("Fixed price (pesos)");
    await user.clear(price);
    await user.type(price, "30.25");
    await user.click(screen.getByRole("button", { name: "Create product" }));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({
      name: validForm.name,
      category: validForm.category,
      price: 3025,
      default_spec: expect.objectContaining({ copies: 1 }),
    }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-catalogue-products"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["catalogue-products"] });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("loads an existing product and sends edits to its id", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue({ ...catalogueProduct, price: 3505, price_peso: 35.05 });
    renderForm(catalogueProduct);

    const price = screen.getByLabelText("Fixed price (pesos)");
    expect(price).toHaveValue("30.00");
    await user.clear(price);
    await user.type(price, "35.05");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
    expect(updateMock).toHaveBeenCalledWith(1, expect.objectContaining({ price: 3505 }));
  });

  it("uploads a selected cover photo with the product payload", async () => {
    const user = userEvent.setup();
    createMock.mockResolvedValue(catalogueProduct);
    renderForm();
    const cover = new File([new Uint8Array([1, 2, 3])], "cover.png", { type: "image/png" });

    await user.type(screen.getByLabelText("Name"), validForm.name);
    await user.type(screen.getByLabelText("Category"), validForm.category);
    await user.upload(screen.getByLabelText("Cover photo"), cover);
    await user.click(screen.getByRole("button", { name: "Create product" }));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ cover_image: cover }));
  });

  it("previews and removes an existing cover photo", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue(catalogueProduct);
    renderForm(catalogueProduct);

    expect(screen.getByRole("img", { name: "2x2 ID Picture cover preview" })).toHaveAttribute(
      "src",
      catalogueProduct.cover_image_url,
    );
    await user.click(screen.getByRole("button", { name: "Remove cover photo" }));
    expect(screen.queryByRole("img", { name: "2x2 ID Picture cover preview" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
    expect(updateMock).toHaveBeenCalledWith(1, expect.objectContaining({ cover_image: null }));
  });

  it("blocks invalid cover files without calling the API", async () => {
    const user = userEvent.setup();
    renderForm(catalogueProduct);
    const invalid = new File(["png"], "cover.jpg", { type: "image/png" });

    await user.upload(screen.getByLabelText("Cover photo"), invalid);
    expect(await screen.findByText(/matching file extension/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(updateMock).not.toHaveBeenCalled();
  });

  it("shows precision errors without calling the API", async () => {
    const user = userEvent.setup();
    renderForm();

    const price = screen.getByLabelText("Fixed price (pesos)");
    await user.clear(price);
    await user.type(price, "30.001");
    await user.click(screen.getByRole("button", { name: "Create product" }));

    expect(await screen.findByText(/at most two decimal places/)).toBeInTheDocument();
    expect(createMock).not.toHaveBeenCalled();
  });
});

describe("catalogue quote rendering", () => {
  it("renders fixed quantity pricing while preserving custom per-side lines", () => {
    const custom: QuoteLine = {
      label: "notes.pdf — Black & white",
      kind: "custom",
      color_mode: "mono",
      pages: 2,
      copies: 1,
      unit_price: 300,
      unit_price_peso: 3,
      sides: 1,
      amount: 600,
      amount_peso: 6,
    };

    render(<QuoteBreakdown lines={[catalogueQuote.lines[0], custom]} />);

    expect(screen.getByText(/2 pieces × ₱30\.00\s*\/\s*piece/)).toBeInTheDocument();
    expect(screen.getByText(/Black & white · 2 pages × 1 copy · ₱3\.00\s*\/\s*side/)).toBeInTheDocument();
  });
});
