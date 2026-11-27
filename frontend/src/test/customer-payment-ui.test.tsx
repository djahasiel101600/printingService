import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import AdminCustomersPage from "@/pages/AdminCustomersPage";
import AdminSettingsPage from "@/pages/AdminSettingsPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import QuickPrintPage from "@/pages/QuickPrintPage";
import type {
  CurrentUser,
  CustomerDirectoryPage,
  CustomerRecord,
  EstimateResponse,
  Order,
} from "@/lib/types";
import {
  adminUser,
  catalogueOrder,
  catalogueQuote,
} from "@/test/catalogue-fixtures";

const authState: { user: CurrentUser | null } = { user: null };
const { getMock, postMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock("@/components/auth", () => ({
  useAuth: () => authState,
}));
vi.mock("@/lib/api", () => ({
  api: { get: getMock, post: postMock, put: putMock, patch: vi.fn() },
  apiErrorMessage: (error: unknown) => {
    const detail = (error as { response?: { data?: { detail?: string } } })
      .response?.data?.detail;
    return detail ?? (error instanceof Error ? error.message : "Request failed");
  },
  loadGuestOrders: () => [],
  saveGuestOrder: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("@/components/FilePreviewDialog", () => ({ default: () => null }));
vi.mock("@/components/OrderReceiptDialog", () => ({ default: () => null }));

const customer: CustomerRecord = {
  id: 9,
  email: "ada@example.com",
  first_name: "Ada",
  last_name: "Customer",
  phone: "09171234567",
  facebook_handle: "@ada.customer",
  is_active: true,
  date_joined: "2026-01-01T08:00:00Z",
  last_login: "2026-01-03T09:00:00Z",
  order_count: 3,
  last_order_at: "2026-01-03T10:00:00Z",
};

function directoryPage(
  results: CustomerRecord[],
  overrides: Partial<CustomerDirectoryPage> = {},
): CustomerDirectoryPage {
  return {
    page: 1,
    page_size: 25,
    count: results.length,
    num_pages: 1,
    has_next: false,
    has_previous: false,
    results,
    ...overrides,
  };
}

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderAt(path: string, pattern: string, element: ReactNode) {
  const client = makeClient();
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={pattern} element={element} />
          <Route path="*" element={<p>Navigation destination</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { client, ...view };
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
  authState.user = adminUser;
  getMock.mockReset();
  postMock.mockReset();
  putMock.mockReset();
});

describe("admin customer directory", () => {
  it("shows signup details, contact information, and order counts", async () => {
    getMock.mockResolvedValue({ data: directoryPage([customer]) });
    renderAt("/admin/customers", "/admin/customers", <AdminCustomersPage />);

    expect(screen.getByRole("heading", { name: "Customers" })).toBeInTheDocument();
    expect(await screen.findByText("Ada Customer")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("09171234567")).toBeInTheDocument();
    expect(screen.getByText("@ada.customer")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "3" })).toBeInTheDocument();
    expect(screen.getByText("1 customer")).toBeInTheDocument();
    expect(getMock).toHaveBeenCalledWith("/admin/customers/", {
      params: { search: "", page: 1 },
    });
  });

  it("searches customers and moves between result pages", async () => {
    const second = { ...customer, id: 10, email: "grace@example.com", first_name: "Grace" };
    getMock.mockImplementation(async (_url: string, config: { params: { search: string; page: number } }) => {
      const { search, page } = config.params;
      if (search === "Grace") return { data: directoryPage([second]) };
      return {
        data: directoryPage(page === 1 ? [customer] : [second], {
          page,
          count: 26,
          num_pages: 2,
          has_next: page === 1,
          has_previous: page === 2,
        }),
      };
    });
    const user = userEvent.setup();
    renderAt("/admin/customers", "/admin/customers", <AdminCustomersPage />);

    await screen.findByText("Ada Customer");
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("grace@example.com")).toBeInTheDocument();
    expect(getMock).toHaveBeenCalledWith("/admin/customers/", {
      params: { search: "", page: 2 },
    });

    await user.type(screen.getByRole("searchbox", { name: "Search registered customers" }), "Grace");
    await waitFor(() => expect(getMock).toHaveBeenCalledWith("/admin/customers/", {
      params: { search: "Grace", page: 1 },
    }));
    expect(await screen.findByText("1 customer")).toBeInTheDocument();
  });
});

describe("pay upon pickup settings", () => {
  it("persists OFF and ON from the admin API Settings switch", async () => {
    let allowPickup = true;
    getMock.mockImplementation(async (url: string) => {
      if (url === "/payments/settings/") {
        return { data: { allow_pay_on_pickup: allowPickup, updated_at: "2026-01-01T08:00:00Z" } };
      }
      return { data: {} };
    });
    putMock.mockImplementation(async (_url: string, body: { allow_pay_on_pickup: boolean }) => {
      allowPickup = body.allow_pay_on_pickup;
      return { data: { allow_pay_on_pickup: allowPickup, updated_at: "2026-01-01T08:00:00Z" } };
    });
    const user = userEvent.setup();
    renderAt("/admin/settings", "/admin/settings", <AdminSettingsPage />);

    const toggle = await screen.findByRole("switch", { name: /Allow "Pay upon pickup"/i });
    await waitFor(() => expect(toggle).toBeChecked());
    await waitFor(() => expect(toggle).toBeEnabled());
    await user.click(toggle);
    await waitFor(() => expect(putMock).toHaveBeenCalledWith("/payments/settings/", {
      allow_pay_on_pickup: false,
    }));
    await waitFor(() => expect(toggle).not.toBeChecked());

    await user.click(toggle);
    await waitFor(() => expect(putMock).toHaveBeenLastCalledWith("/payments/settings/", {
      allow_pay_on_pickup: true,
    }));
    await waitFor(() => expect(toggle).toBeChecked());
  });

  it("hides pickup at checkout when disabled and submits it when enabled", async () => {
    const user = userEvent.setup();
    let allowPickup = false;
    const payableOrder: Order = { ...catalogueOrder, status: "awaiting_payment" };
    getMock.mockImplementation(async (url: string) => ({
      data: url === "/payments/settings/"
        ? { allow_pay_on_pickup: allowPickup }
        : payableOrder,
    }));
    postMock.mockResolvedValue({ data: { method: "pickup", order: payableOrder } });
    const { unmount } = renderAt("/orders/17", "/orders/:id", <OrderDetailPage />);

    await screen.findByRole("heading", { name: payableOrder.tracking_id });
    await user.click(screen.getByRole("button", { name: /pay now/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("button", { name: /pay in full/i })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /pay upon pickup/i })).not.toBeInTheDocument();
    unmount();

    allowPickup = true;
    renderAt("/orders/17", "/orders/:id", <OrderDetailPage />);
    await screen.findByRole("heading", { name: payableOrder.tracking_id });
    await user.click(screen.getByRole("button", { name: /pay now/i }));
    const enabledDialog = await screen.findByRole("dialog");
    await user.click(within(enabledDialog).getByRole("button", { name: /pay upon pickup/i }));
    await waitFor(() => expect(postMock).toHaveBeenCalledWith("/payments/checkout/", {
      order_id: 17,
      method: "pickup",
    }));
  });

  it("clears a stale quick-print pickup choice when settings turn it off", async () => {
    let allowPickup = true;
    const estimate: EstimateResponse = {
      total_pages: 1,
      files: [{
        name: "notes.pdf",
        file_type: "pdf",
        page_count: 1,
        size: 1024,
        print_ready: true,
        color_analysis: {
          pages: [{ page: 1, mode: "mono", analyzed: true, color_ratio: 0, max_chroma: 0, confidence: "high" }],
          complete: true,
          warning: "",
        },
      }],
    };
    getMock.mockImplementation(async (url: string) => {
      if (url === "/payments/settings/") return { data: { allow_pay_on_pickup: allowPickup } };
      if (url === "/printing/capabilities/") {
        return { data: {
          printMode: "normal",
          colorModes: ["mono", "color"],
          resolutions: [],
          paperSizes: [{
            paperSize: "ps_a4",
            paperTypes: [{
              paperType: "pt_plainpaper",
              borderless: false,
              paperSources: [],
              printQualities: ["normal", "high"],
              doubleSided: false,
            }],
          }],
        } };
      }
      return { data: {} };
    });
    postMock.mockImplementation(async (url: string) => {
      if (url === "/orders/estimate/") return { data: estimate };
      if (url === "/orders/quote/") return { data: catalogueQuote };
      return { data: {} };
    });
    const user = userEvent.setup();
    const { client, container } = renderAt("/q", "/q", <QuickPrintPage />);

    const upload = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(upload, new File(["pdf"], "notes.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(await screen.findByText("Print settings", { exact: true })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(await screen.findByText("Notes for the shop", { exact: true })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await user.click(await screen.findByRole("button", { name: /pay when you collect/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(await screen.findByText("Review your order", { exact: true })).toBeInTheDocument();

    allowPickup = false;
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["payment-settings"] });
    });
    expect(await screen.findByText("How do you want to pay?", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("Pay upon pickup is currently disabled by the shop.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
    expect(postMock.mock.calls.some(([url]) => url === "/orders/")).toBe(false);
  });
});
