import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminCataloguePage from "@/pages/AdminCataloguePage";
import { catalogueProduct } from "@/test/catalogue-fixtures";

const { fetchMock, updateMock, archiveMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  updateMock: vi.fn(),
  archiveMock: vi.fn(),
}));

vi.mock("@/lib/catalogue", () => ({
  fetchAllAdminCatalogueProducts: fetchMock,
  updateCatalogueProduct: updateMock,
  archiveCatalogueProduct: archiveMock,
}));
vi.mock("@/lib/api", () => ({
  apiErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("@/components/CatalogueProductForm", () => ({
  default: ({
    open,
    product,
    onOpenChange,
  }: {
    open: boolean;
    product: { name: string } | null;
    onOpenChange: (open: boolean) => void;
  }) => open ? (
    <div role="dialog">
      <p>{product ? `Edit ${product.name}` : "New product form"}</p>
      <button type="button" onClick={() => onOpenChange(false)}>Close form</button>
    </div>
  ) : null,
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <AdminCataloguePage />
    </QueryClientProvider>,
  );
  return { client, invalidate };
}

beforeEach(() => {
  fetchMock.mockReset();
  updateMock.mockReset();
  archiveMock.mockReset();
  fetchMock.mockResolvedValue([catalogueProduct]);
});

describe("AdminCataloguePage", () => {
  it("opens distinct create and edit forms for a product", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText(catalogueProduct.name)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /new product/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent("New product form");
    await user.click(screen.getByRole("button", { name: "Close form" }));

    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent(`Edit ${catalogueProduct.name}`);
  });

  it("toggles featured state and archives with cache invalidation", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue([{ ...catalogueProduct, is_featured: false }]);
    updateMock.mockResolvedValue({ ...catalogueProduct, is_featured: true });
    archiveMock.mockResolvedValue(undefined);
    const { invalidate } = renderPage();

    await user.click(await screen.findByRole("button", { name: `Feature ${catalogueProduct.name}` }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledWith(1, { is_featured: true }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-catalogue-products"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-catalogue-categories"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["catalogue-products"] });

    await user.click(screen.getByRole("button", { name: /^archive$/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Existing orders keep their snapshotted");
    await user.click(screen.getByRole("button", { name: "Archive product" }));

    await waitFor(() => expect(archiveMock).toHaveBeenCalledWith(1));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["admin-catalogue-products"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["catalogue-products"] });
  });
});
