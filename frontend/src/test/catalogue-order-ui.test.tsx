import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import FileReviewCard from "@/components/FileReviewCard";
import HomePage from "@/pages/HomePage";
import NewOrderPage from "@/pages/NewOrderPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import AdminOrderDetailPage from "@/pages/AdminOrderDetailPage";
import AdminOrdersPage from "@/pages/AdminOrdersPage";
import type { CurrentUser, Order, Quote } from "@/lib/types";
import {
  adminUser,
  approverUser,
  catalogueFile,
  catalogueOrder,
  catalogueProduct,
  catalogueQuote,
  preparedCatalogueFile,
} from "@/test/catalogue-fixtures";

const authState: { user: CurrentUser | null } = { user: null };
const { getMock, postMock, patchMock, fetchCatalogueMock, saveGuestOrderMock } =
  vi.hoisted(() => ({
    getMock: vi.fn(),
    postMock: vi.fn(),
    patchMock: vi.fn(),
    fetchCatalogueMock: vi.fn(),
    saveGuestOrderMock: vi.fn(),
  }));

vi.mock("@/components/auth", () => ({
  useAuth: () => authState,
}));
vi.mock("@/lib/api", () => ({
  api: { get: getMock, post: postMock, patch: patchMock },
  apiErrorMessage: (error: unknown) => {
    const detail = (error as { response?: { data?: { detail?: string } } })
      .response?.data?.detail;
    return detail ?? "Request failed";
  },
  loadGuestOrders: () => [],
  saveGuestOrder: saveGuestOrderMock,
}));
vi.mock("@/lib/catalogue", () => ({
  fetchAllCatalogueProducts: fetchCatalogueMock,
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("@/components/FilePreviewDialog", () => ({ default: () => null }));
vi.mock("@/components/OrderReceiptDialog", () => ({ default: () => null }));

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderAt(path: string, pattern: string, element: ReactNode) {
  return render(
    <QueryClientProvider client={makeClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={element} />
          <Route path="*" element={<p>Navigation destination</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function quoteForQuantity(quantity: number): Quote {
  return {
    ...catalogueQuote,
    lines: [{
      ...catalogueQuote.lines[0],
      quantity,
      amount: quantity * 3000,
      amount_peso: quantity * 30,
    }],
    subtotal: quantity * 3000,
    subtotal_peso: quantity * 30,
  };
}

async function chooseCatalogueProduct(user: ReturnType<typeof userEvent.setup>) {
  const select = await screen.findByRole("combobox", { name: "Service" });
  await user.click(select);
  await user.click(await screen.findByRole("option", { name: /2x2 ID Picture/ }));
}

beforeAll(() => {
  Object.defineProperty(window.HTMLElement.prototype, "hasPointerCapture", {
    configurable: true,
    value: () => false,
  });
  Object.defineProperty(window.HTMLElement.prototype, "setPointerCapture", {
    configurable: true,
    value: () => undefined,
  });
  Object.defineProperty(window.HTMLElement.prototype, "releasePointerCapture", {
    configurable: true,
    value: () => undefined,
  });
  Object.defineProperty(window.HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: () => undefined,
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

beforeEach(() => {
  authState.user = null;
  getMock.mockReset();
  postMock.mockReset();
  patchMock.mockReset();
  fetchCatalogueMock.mockReset();
  saveGuestOrderMock.mockReset();
  fetchCatalogueMock.mockResolvedValue([catalogueProduct]);
});

describe("homepage catalogue products", () => {
  it("shows all active products with distinct featured styling and product links", async () => {
    const regularProduct = {
      ...catalogueProduct,
      id: 2,
      slug: "photo-prints",
      name: "Photo Prints",
      category: "Photos",
      price: 1500,
      price_peso: 15,
      is_featured: false,
      display_order: 1,
      cover_image_url: null,
    };
    fetchCatalogueMock.mockResolvedValue([catalogueProduct, regularProduct]);
    renderAt("/", "/", <HomePage />);

    expect(await screen.findByRole("heading", { name: "Printing services" })).toBeInTheDocument();
    expect(await screen.findByText(catalogueProduct.name)).toBeInTheDocument();
    expect(await screen.findByText(regularProduct.name)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "2x2 ID Picture cover photo" })).toHaveAttribute(
      "src",
      catalogueProduct.cover_image_url,
    );
    expect(screen.getByText("Featured")).toBeInTheDocument();
    const serviceLinks = screen.getAllByRole("link", { name: /order this service/i });
    expect(serviceLinks).toHaveLength(2);
    expect(serviceLinks[0]).toHaveAttribute(
      "href",
      "/order?mode=catalogue&product=1",
    );
    expect(serviceLinks[1]).toHaveAttribute(
      "href",
      "/order?mode=catalogue&product=2",
    );
    expect(fetchCatalogueMock).toHaveBeenCalledWith();
  });

  it("hides the section when catalogue products fail to load", async () => {
    fetchCatalogueMock.mockRejectedValue(new Error("offline"));
    renderAt("/", "/", <HomePage />);

    expect(screen.getByRole("heading", { name: /Print anything/ })).toBeInTheDocument();
    await waitFor(() => expect(fetchCatalogueMock).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Printing services" })).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("heading", { name: "See it in action" })).toBeInTheDocument();
  });
});

describe("catalogue order creation", () => {
  it("preselects the product supplied by an Order this service link", async () => {
    postMock.mockResolvedValue({ data: catalogueQuote });
    renderAt("/order?mode=catalogue&product=1", "/order", <NewOrderPage />);

    const select = await screen.findByRole("combobox", { name: "Service" });
    await waitFor(() => expect(select).toHaveTextContent("2x2 ID Picture"));
    expect(screen.getByRole("img", { name: "2x2 ID Picture cover photo" })).toHaveAttribute(
      "src",
      catalogueProduct.cover_image_url,
    );
    expect(screen.getByLabelText("Quantity")).toHaveValue(1);
    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/orders/quote/", {
      order_mode: "catalogue",
      product_id: 1,
      product_quantity: 1,
    }));
  });

  it("quotes by quantity and submits one file with contact details", async () => {
    const user = userEvent.setup();
    postMock.mockImplementation(async (url: string, body: Record<string, unknown>) => {
      if (url === "/orders/quote/") {
        return { data: quoteForQuantity(Number(body.product_quantity)) };
      }
      if (url === "/orders/") {
        return { data: { order: catalogueOrder, quote: catalogueQuote } };
      }
      throw new Error(`Unexpected POST ${url}`);
    });
    renderAt("/order?mode=catalogue", "/order", <NewOrderPage />);

    await chooseCatalogueProduct(user);
    expect(screen.getByRole("img", { name: "2x2 ID Picture cover photo" })).toHaveAttribute(
      "src",
      catalogueProduct.cover_image_url,
    );
    const quantity = screen.getByLabelText("Quantity");
    await user.clear(quantity);
    await user.type(quantity, "2");
    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/orders/quote/", {
      order_mode: "catalogue",
      product_id: 1,
      product_quantity: 2,
    }));
    expect(await screen.findAllByText("₱60.00")).not.toHaveLength(0);
    expect(screen.queryByText("Print settings")).not.toBeInTheDocument();

    const upload = document.getElementById("file-upload") as HTMLInputElement;
    await user.upload(upload, new File(["photo"], "photo.jpg", { type: "image/jpeg" }));
    await user.type(screen.getByLabelText("Name"), "Ada Customer");
    await user.type(screen.getByLabelText("Email address"), "ada@example.com");
    await user.type(screen.getByLabelText(/Notes for the shop/), "Please keep the photo sharp.");
    await user.click(screen.getByRole("button", { name: "Place order" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      "/orders/",
      expect.any(FormData),
      expect.any(Object),
    ));
    const orderCall = postMock.mock.calls.find(([url]) => url === "/orders/");
    const formData = orderCall?.[1] as FormData;
    expect(formData.get("order_mode")).toBe("catalogue");
    expect(formData.get("product_id")).toBe("1");
    expect(formData.get("product_quantity")).toBe("2");
    expect(formData.get("guest_name")).toBe("Ada Customer");
    expect(formData.get("guest_contact_method")).toBe("email");
    expect(formData.get("guest_contact_value")).toBe("ada@example.com");
    expect(JSON.parse(String(formData.get("spec")))).toEqual({
      free_text_instructions: "Please keep the photo sharp.",
    });
    expect(formData.getAll("files")).toHaveLength(1);
    expect(saveGuestOrderMock).toHaveBeenCalledWith(expect.objectContaining({ id: 17 }));
  });

  it("supports admin-mode registered customer selection", async () => {
    const user = userEvent.setup();
    authState.user = adminUser;
    getMock.mockResolvedValue({ data: [{
      id: 9,
      email: "ada@example.com",
      first_name: "Ada",
      last_name: "Customer",
      phone: "",
    }] });
    postMock.mockImplementation(async (url: string, body: Record<string, unknown>) => {
      if (url === "/orders/quote/") {
        return { data: quoteForQuantity(Number(body.product_quantity)) };
      }
      if (url === "/orders/") {
        return { data: { order: catalogueOrder, quote: catalogueQuote } };
      }
      throw new Error(`Unexpected POST ${url}`);
    });
    renderAt(
      "/admin/orders/new?mode=catalogue",
      "/admin/orders/new",
      <NewOrderPage adminMode />,
    );

    await chooseCatalogueProduct(user);
    const upload = document.getElementById("file-upload") as HTMLInputElement;
    await user.upload(upload, new File(["photo"], "photo.jpg", { type: "image/jpeg" }));
    await user.type(screen.getByLabelText("Search customers"), "Ada");
    const customer = await screen.findByRole("button", { name: /Ada Customer/ });
    await user.click(customer);
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create order" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      "/orders/",
      expect.any(FormData),
      expect.any(Object),
    ));
    const formData = postMock.mock.calls.find(([url]) => url === "/orders/")?.[1] as FormData;
    expect(formData.get("customer_user_id")).toBe("9");
    expect(formData.get("guest_name")).toBeNull();
    expect(formData.get("order_mode")).toBe("catalogue");
  });
});

describe("catalogue order details", () => {
  it("shows the customer-facing product snapshot and instructions", async () => {
    authState.user = adminUser;
    getMock.mockImplementation(async (url: string) => ({
      data: url === "/payments/settings/" ? { allow_pay_on_pickup: false } : catalogueOrder,
    }));
    renderAt("/orders/17", "/orders/:id", <OrderDetailPage />);

    expect(await screen.findByRole("heading", { name: catalogueOrder.tracking_id })).toBeInTheDocument();
    expect(screen.getByText("Catalogue service")).toBeInTheDocument();
    expect(screen.getAllByText(catalogueProduct.name).length).toBeGreaterThan(0);
    expect(screen.getByText(/2 pieces at ₱30\.00\s*\/\s*piece/)).toBeInTheDocument();
    expect(screen.getByText(catalogueProduct.instructions)).toBeInTheDocument();
  });

  it("shows staff safeguards, validates bounds, and handles quantity update conflicts", async () => {
    const user = userEvent.setup();
    authState.user = adminUser;
    getMock.mockResolvedValue({ data: catalogueOrder });
    patchMock
      .mockRejectedValueOnce({
        response: { status: 409, data: { detail: "Quantity cannot change after payment." } },
      })
      .mockResolvedValueOnce({ data: {
        ...catalogueOrder,
        product_quantity: 3,
        subtotal: 9000,
        subtotal_peso: 90,
        balance_due: 9000,
        balance_due_peso: 90,
        quote_breakdown: quoteForQuantity(3).lines,
      } });
    renderAt("/admin/orders/17", "/admin/orders/:id", <AdminOrderDetailPage />);

    expect(await screen.findByRole("heading", { name: catalogueOrder.tracking_id })).toBeInTheDocument();
    expect(screen.getByText("Shop-prepared layout required before approval")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload prepared layout" })).toBeInTheDocument();
    expect(screen.getByText(/Fixed pricing uses the saved product price/)).toBeInTheDocument();
    expect(screen.getByText(catalogueProduct.instructions)).toBeInTheDocument();

    const quantity = screen.getByLabelText("Finished quantity");
    await user.clear(quantity);
    await user.type(quantity, "100");
    await user.click(screen.getByRole("button", { name: "Update" }));
    expect(await screen.findByText("Quantity cannot exceed 99.")).toBeInTheDocument();
    expect(patchMock).not.toHaveBeenCalled();

    await user.clear(quantity);
    await user.type(quantity, "3");
    await user.click(screen.getByRole("button", { name: "Update" }));
    expect(await screen.findByText("Quantity cannot change after payment.")).toBeInTheDocument();
    expect(patchMock).toHaveBeenCalledWith("/admin/orders/17/product/", { product_quantity: 3 });

    await user.click(screen.getByRole("button", { name: "Update" }));
    expect((await screen.findAllByText(/3 pieces × ₱30\.00\s*\/\s*piece/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText("₱90.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Shop-prepared layout required before approval")).toBeInTheDocument();
  });

  it("does not offer quantity editing to approvers", async () => {
    authState.user = approverUser;
    getMock.mockResolvedValue({ data: catalogueOrder });
    renderAt("/admin/orders/17", "/admin/orders/:id", <AdminOrderDetailPage />);

    expect(await screen.findByRole("heading", { name: catalogueOrder.tracking_id })).toBeInTheDocument();
    expect(screen.queryByLabelText("Finished quantity")).not.toBeInTheDocument();
    expect(screen.getByText(/Quantity can be changed only by a shop admin/)).toBeInTheDocument();
  });

  it("lets an admin complete a prepared catalogue order in-house", async () => {
    const user = userEvent.setup();
    authState.user = adminUser;
    const preparedOrder: Order = { ...catalogueOrder, files: [preparedCatalogueFile] };
    getMock.mockResolvedValue({ data: preparedOrder });
    postMock.mockResolvedValue({ data: {
      ...preparedOrder,
      status: "completed",
      status_display: "Completed",
      completed_at: "2026-01-02T08:00:00Z",
    } });
    renderAt("/admin/orders/17", "/admin/orders/:id", <AdminOrderDetailPage />);

    expect(await screen.findByRole("heading", { name: catalogueOrder.tracking_id })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Complete In-House" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/No Epson print job will be created/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Complete In-House" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      "/admin/orders/17/actions/complete_in_house/",
      { note: "" },
    ));
    expect(await screen.findByText("Completed", { selector: "span" })).toBeInTheDocument();
  });

  it("does not offer in-house completion to approvers or custom orders", async () => {
    authState.user = approverUser;
    getMock.mockResolvedValue({ data: { ...catalogueOrder, files: [preparedCatalogueFile] } });
    const first = renderAt("/admin/orders/17", "/admin/orders/:id", <AdminOrderDetailPage />);
    expect(await screen.findByRole("heading", { name: catalogueOrder.tracking_id })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete In-House" })).not.toBeInTheDocument();
    first.unmount();

    authState.user = adminUser;
    getMock.mockResolvedValue({ data: {
      ...catalogueOrder,
      order_mode: "custom",
      catalogue_product: null,
      files: [preparedCatalogueFile],
    } });
    renderAt("/admin/orders/17", "/admin/orders/:id", <AdminOrderDetailPage />);
    expect(await screen.findByRole("heading", { name: catalogueOrder.tracking_id })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete In-House" })).not.toBeInTheDocument();
  });
});

describe("review queue in-house completion", () => {
  it("lets a shop admin complete a prepared catalogue order directly from the queue", async () => {
    const user = userEvent.setup();
    authState.user = adminUser;
    const preparedOrder: Order = { ...catalogueOrder, files: [preparedCatalogueFile] };
    getMock.mockResolvedValue({ data: [preparedOrder] });
    postMock.mockResolvedValue({ data: {
      ...preparedOrder,
      status: "completed",
      status_display: "Completed",
      completed_at: "2026-01-02T08:00:00Z",
    } });
    renderAt("/admin", "/admin", <AdminOrdersPage />);

    await user.click(await screen.findByRole("button", { name: "Complete In-House" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/No Epson print job will be created/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Complete In-House" }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      "/admin/orders/17/actions/complete_in_house/",
      {},
    ));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("does not offer the queue shortcut to approvers", async () => {
    authState.user = approverUser;
    getMock.mockResolvedValue({ data: [{
      ...catalogueOrder,
      files: [preparedCatalogueFile],
    }] });
    renderAt("/admin", "/admin", <AdminOrdersPage />);

    expect(await screen.findByText(catalogueOrder.tracking_id)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete In-House" })).not.toBeInTheDocument();
  });

  it("disables unprepared catalogue orders and hides the shortcut for other orders", async () => {
    authState.user = adminUser;
    const preparedOrder: Order = { ...catalogueOrder, files: [preparedCatalogueFile] };
    getMock.mockResolvedValue({ data: [
      catalogueOrder,
      {
        ...preparedOrder,
        id: 18,
        tracking_id: "PSP-CUSTOM-002",
        order_mode: "custom",
        catalogue_product: null,
      },
      {
        ...preparedOrder,
        id: 19,
        tracking_id: "PSP-CAT-003",
        status: "completed",
        status_display: "Completed",
      },
    ] });
    renderAt("/admin", "/admin", <AdminOrdersPage />);

    expect(await screen.findByText(catalogueOrder.tracking_id)).toBeInTheDocument();
    const shortcut = screen.getByRole("button", { name: "Complete In-House" });
    expect(shortcut).toBeDisabled();
    expect(screen.getByText(/Open the order to upload the shop-prepared layout first/)).toBeInTheDocument();
  });
});

describe("prepared layout replacement", () => {
  it("always offers the prepared-layout control for catalogue files", async () => {
    const user = userEvent.setup();
    const preparedOrder = { ...catalogueOrder, files: [preparedCatalogueFile] };
    postMock.mockResolvedValue({ data: preparedOrder });
    render(
      <QueryClientProvider client={makeClient()}>
        <FileReviewCard
          order={catalogueOrder}
          file={catalogueFile}
          onPreview={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText(/Catalogue orders require a shop-prepared layout/)).toBeInTheDocument();
    const upload = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(upload, new File(["layout"], "layout.pdf", { type: "application/pdf" }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      "/admin/orders/17/files/23/replace/",
      expect.any(FormData),
    ));
  });

  it("recognizes a prepared layout and leaves custom printer-ready files unchanged", () => {
    const preparedOrder = { ...catalogueOrder, files: [preparedCatalogueFile] };
    const first = render(
      <QueryClientProvider client={makeClient()}>
        <FileReviewCard order={preparedOrder} file={preparedCatalogueFile} onPreview={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.queryByText(/Catalogue orders require a shop-prepared layout/)).not.toBeInTheDocument();
    expect(screen.getByText("Shop-prepared layout uploaded. This file can now be approved.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload prepared layout" })).toBeInTheDocument();
    first.unmount();

    const customOrder: Order = {
      ...catalogueOrder,
      order_mode: "custom",
      catalogue_product: null,
      files: [catalogueFile],
    };
    render(
      <QueryClientProvider client={makeClient()}>
        <FileReviewCard order={customOrder} file={catalogueFile} onPreview={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("button", { name: "Upload prepared layout" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Upload PDF" })).not.toBeInTheDocument();
  });
});
