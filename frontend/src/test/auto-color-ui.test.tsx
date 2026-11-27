import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PageColorReview from "@/components/PageColorReview";
import QuoteBreakdown from "@/components/QuoteBreakdown";
import SpecFields, { DEFAULT_SPEC } from "@/components/SpecFields";
import type { Order, OrderFile, QuoteLine } from "@/lib/types";

const { patchMock } = vi.hoisted(() => ({ patchMock: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: { patch: patchMock },
  apiErrorMessage: () => "Request failed",
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const order = { id: 17 } as Order;
const file = {
  id: 23,
  page_count: 2,
  selected_pages: [1, 2],
  color_analysis: {
    version: 1,
    pages: [
      { page: 1, mode: "mono", analyzed: true, color_ratio: 0, max_chroma: 0, confidence: "high" },
      { page: 2, mode: "color", analyzed: true, color_ratio: 0.2, max_chroma: 180, confidence: "high" },
    ],
    complete: true,
    warning: "",
  },
  color_page_overrides: {},
  effective_page_modes: [
    { page: 1, mode: "mono" },
    { page: 2, mode: "color" },
  ],
  detected_color_pages: 1,
  detected_mono_pages: 1,
  unanalyzed_pages: 0,
} as OrderFile;

function renderReview(reviewFile = file, disabled = false) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PageColorReview order={order} file={reviewFile} disabled={disabled} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  patchMock.mockReset();
});

describe("Auto color mode controls", () => {
  it("offers Auto in the shared print specification editor", async () => {
    const onChange = vi.fn();
    render(
      <SpecFields
        capabilities={null}
        value={{ ...DEFAULT_SPEC, color_mode: "mono" }}
        onChange={onChange}
      />,
    );

    await userEvent.setup().click(screen.getByRole("radio", { name: /Auto \(per page\)/ }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ color_mode: "auto" }));
  });

  it("summarizes detected and effective page modes", () => {
    renderReview();

    expect(screen.getByText(/Detected 1 color · 1 black & white · 0 unclear/)).toBeInTheDocument();
    expect(screen.getByText("Selected pages: 1 color · 1 black & white")).toBeInTheDocument();
  });

  it("sends a complete override map when a page is switched", async () => {
    patchMock.mockResolvedValue({ data: { order, file } });
    renderReview();

    await userEvent.setup().click(screen.getByText("Page-by-page overrides (2)"));
    await userEvent.setup().click(
      screen.getByRole("button", { name: "Page 1: Black & white. Switch to Color" }),
    );

    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(
      "/admin/orders/17/files/23/color/",
      { overrides: { "1": "color" } },
    ));
  });

  it("can force reanalysis and respects the review lock", async () => {
    patchMock.mockResolvedValue({ data: { order, file } });
    const first = renderReview();
    await userEvent.setup().click(screen.getByRole("button", { name: "Reanalyze" }));
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(
      "/admin/orders/17/files/23/color/",
      { reanalyze: true },
    ));
    first.unmount();

    renderReview(file, true);
    expect(screen.getByRole("button", { name: "Reanalyze" })).toBeDisabled();
  });
});

describe("QuoteBreakdown", () => {
  it("itemizes concrete color modes and amounts without repeating the API suffix", () => {
    const lines: QuoteLine[] = [
      {
        label: "mixed.pdf — Black & white",
        color_mode: "mono",
        pages: 1,
        copies: 2,
        unit_price: 300,
        unit_price_peso: 3,
        sides: 2,
        amount: 600,
        amount_peso: 6,
      },
      {
        label: "mixed.pdf — Color",
        color_mode: "color",
        pages: 1,
        copies: 2,
        unit_price: 600,
        unit_price_peso: 6,
        sides: 2,
        amount: 1200,
        amount_peso: 12,
      },
    ];

    render(<QuoteBreakdown lines={lines} />);

    expect(screen.getAllByText("mixed.pdf")).toHaveLength(2);
    expect(screen.getByText(/Black & white · 1 page × 2 copies · ₱3.00\/side/)).toBeInTheDocument();
    expect(screen.getByText(/Color · 1 page × 2 copies · ₱6.00\/side/)).toBeInTheDocument();
    expect(screen.getByText("₱6.00")).toBeInTheDocument();
    expect(screen.getByText("₱12.00")).toBeInTheDocument();
  });
});
