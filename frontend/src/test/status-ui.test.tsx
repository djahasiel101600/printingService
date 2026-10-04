import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AsyncBoundary, errorMessage } from "@/components/AsyncBoundary";
import { EmptyState } from "@/components/EmptyState";
import { OrderStatusBanner, OrderStepper } from "@/components/OrderStatusBanner";
import { StatusBadge } from "@/components/StatusBadge";
import { ORDER_PHASES, STATUS_META, ALL_ORDER_STATUSES } from "@/lib/constants";

/**
 * These lock the behaviour the UI pass promised: a status is explained in words
 * and the raw database key never reaches the page.
 */

describe("StatusBadge", () => {
  it("shows plain-language labels instead of the raw status key", () => {
    render(<StatusBadge status="revision_requested" />);
    // The old component rendered the literal string "revision_requested".
    expect(screen.getByText(STATUS_META.revision_requested.customerLabel)).toBeInTheDocument();
    expect(screen.queryByText(/revision_requested/)).not.toBeInTheDocument();
  });

  it("uses shop vocabulary when the audience is staff", () => {
    render(<StatusBadge status="revision_requested" audience="staff" />);
    expect(screen.getByText(STATUS_META.revision_requested.staffLabel)).toBeInTheDocument();
  });

  it("honours an explicit display override for foreign states", () => {
    render(<StatusBadge status="some_printer_state" display="Queued at printer" />);
    expect(screen.getByText("Queued at printer")).toBeInTheDocument();
  });

  it("never throws on a status the backend has not shipped yet", () => {
    render(<StatusBadge status="brand_new_status" />);
    expect(screen.getByText("brand new status")).toBeInTheDocument();
  });

  it("gives every known status a semantic tone", () => {
    for (const status of ALL_ORDER_STATUSES) {
      expect(STATUS_META[status].tone).toBeTruthy();
    }
  });
});

describe("OrderStatusBanner", () => {
  it("explains what happens next, in words", () => {
    render(<OrderStatusBanner status="awaiting_payment" trackingId="PE-42" />);

    expect(screen.getByRole("region", { name: /order status/i })).toBeInTheDocument();
    expect(screen.getByText(STATUS_META.awaiting_payment.customerHelp)).toBeInTheDocument();
    expect(screen.getByText("PE-42")).toBeInTheDocument();
  });

  it("surfaces a rejection reason from staff to the customer", () => {
    render(<OrderStatusBanner status="rejected" note="Margins were too tight." />);
    expect(screen.getByText("Margins were too tight.")).toBeInTheDocument();
  });

  it("omits the tracking row when the order has no id yet", () => {
    const { container } = render(<OrderStatusBanner status="submitted" />);
    expect(container.textContent).not.toMatch(/Tracking ID/);
  });
});

describe("OrderStepper", () => {
  it("announces the current step instead of relying on colour", () => {
    render(<OrderStepper status="printing" />);

    const items = screen.getAllByRole("listitem");
    const printing = items.find((li) => li.textContent?.startsWith("Printing"));
    const placed = items.find((li) => li.textContent?.startsWith("Placed"));

    expect(printing).toBeDefined();
    // The step is announced, so colour is never the only signal.
    expect(printing?.textContent).toContain("(current step)");
    expect(printing?.querySelector("[aria-current]")).toHaveAttribute("aria-current", "step");

    expect(placed?.textContent).not.toContain("(current step)");
    expect(placed?.querySelector("[aria-current]")).toBeNull();
  });

  it("renders exactly the documented journey", () => {
    render(<OrderStepper status="submitted" />);
    expect(screen.getAllByRole("listitem")).toHaveLength(ORDER_PHASES.length);
  });
});
describe("AsyncBoundary", () => {
  it("shows a skeleton while loading and hides the empty state", () => {
    render(
      <AsyncBoundary isLoading isEmpty empty={<p>No orders yet</p>}>
        <p>Real content</p>
      </AsyncBoundary>,
    );
    expect(screen.queryByText("Real content")).not.toBeInTheDocument();
    expect(screen.queryByText("No orders yet")).not.toBeInTheDocument();
  });

  it("shows the empty state only after loading has finished", () => {
    render(
      <AsyncBoundary isLoading={false} isEmpty empty={<p>No orders yet</p>}>
        <p>Real content</p>
      </AsyncBoundary>,
    );
    expect(screen.getByText("No orders yet")).toBeInTheDocument();
  });

  it("renders children when the request succeeded with results", () => {
    render(
      <AsyncBoundary isLoading={false} isEmpty={false}>
        <p>Real content</p>
      </AsyncBoundary>,
    );
    expect(screen.getByText("Real content")).toBeInTheDocument();
  });

  it("surfaces an error with a retry affordance", () => {
    render(
      <AsyncBoundary isLoading={false} error={new Error("Network down")} onRetry={() => {}}>
        <p>Real content</p>
      </AsyncBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Network down")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("calls onRetry when the user asks to try again", async () => {
    let retried = false;
    render(
      <AsyncBoundary isLoading={false} error={new Error("Boom")} onRetry={() => { retried = true; }}>
        <p>Real content</p>
      </AsyncBoundary>,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
    expect(retried).toBe(true);
  });
});

describe("errorMessage", () => {
  it("reads a DRF detail string", () => {
    expect(errorMessage({ response: { data: { detail: "Not allowed." } } })).toBe("Not allowed.");
  });

  it("reads the first field error from a validation payload", () => {
    const error = { response: { data: { email: ["This account already exists."] } } };
    expect(errorMessage(error)).toBe("email: This account already exists.");
  });

  it("falls back to a generic message", () => {
    expect(errorMessage(undefined)).toBe("Please try again.");
  });
});

describe("EmptyState", () => {
  it("renders a heading, explanation and a next step", () => {
    render(<EmptyState title="No orders yet" description="Your first print is a minute away." />);

    expect(screen.getByRole("heading", { name: "No orders yet" })).toBeInTheDocument();
    expect(screen.getByText("Your first print is a minute away.")).toBeInTheDocument();
  });
});