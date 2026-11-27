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
} from "@/lib/catalogue";
import type { QuoteLine } from "@/lib/types";
import { catalogueProduct, catalogueQuote } from "@/test/catalogue-fixtures";

const { createMock, updateMock } = vi.hoisted(() => ({
  createMock: vi.fn(),
  updateMock: vi.fn(),
}));

vi.mock("@/lib/catalogue", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/catalogue")>();
  return {
    ...actual,
    createCatalogueProduct: createMock,
    updateCatalogueProduct: updateMock,
  };
});
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
