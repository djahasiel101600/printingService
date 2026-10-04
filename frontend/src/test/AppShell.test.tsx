import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AppShell from "@/components/AppShell";
import type { CurrentUser } from "@/lib/types";

/**
 * Locks in WHICH links each role sees. The navigation is restructured during
 * the app-shell work (data-driven + mobile drawer); these assertions must keep
 * passing so the refactor cannot leak admin-only pages to customers.
 */

const authState: { user: CurrentUser | null } = { user: null };

vi.mock("@/components/auth", () => ({
  useAuth: () => ({ user: authState.user, logout: vi.fn() }),
}));

function makeUser(overrides: Partial<CurrentUser>): CurrentUser {
  return {
    id: 1,
    email: "person@example.com",
    first_name: "Test",
    last_name: "Person",
    phone: "",
    role: "client",
    is_shop_admin: false,
    is_approver: false,
    can_review_orders: false,
    ...overrides,
  };
}

function renderShell() {
  return render(
    <MemoryRouter>
      <AppShell />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  authState.user = null;
});

describe("AppShell navigation by role", () => {
  it("shows only customer links to a signed-out visitor", () => {
    renderShell();

    expect(screen.getByRole("link", { name: /new order/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /track order/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /my orders/i })).toBeInTheDocument();

    expect(screen.queryByRole("link", { name: /^admin$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /pricing/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /staff/i })).not.toBeInTheDocument();
  });

  it("hides staff links from a plain customer account", () => {
    authState.user = makeUser({});
    renderShell();

    expect(screen.getByRole("link", { name: /new order/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^admin$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /pricing/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /staff/i })).not.toBeInTheDocument();
  });

  it("gives an approver the review queue but not pricing or staff management", () => {
    authState.user = makeUser({
      role: "approver",
      is_approver: true,
      can_review_orders: true,
    });
    renderShell();

    expect(screen.getByRole("link", { name: /review queue/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /pricing/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^staff$/i })).not.toBeInTheDocument();
  });

  it("gives a shop admin every staff destination", () => {
    authState.user = makeUser({
      role: "admin",
      is_shop_admin: true,
      is_approver: true,
      can_review_orders: true,
    });
    renderShell();

    expect(screen.getByRole("link", { name: /review queue/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /pricing/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^staff$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /api settings/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new order for customer/i })).toBeInTheDocument();
  });

  it("offers sign-in when logged out", () => {
    renderShell();
    expect(screen.getByRole("link", { name: /log in/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sign up/i })).toBeInTheDocument();
  });

  it("shows the signed-in account in a user menu instead of a bare logout button", () => {
    authState.user = makeUser({ first_name: "Ada" });
    renderShell();

    // The header no longer renders a lonely "Log out" button; the account and
    // its actions live behind one trigger so the bar stays readable on mobile.
    expect(screen.getByRole("button", { name: /ada/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^log out$/i })).not.toBeInTheDocument();
  });

  it("labels the main navigation landmark for screen readers", () => {
    renderShell();
    expect(screen.getByRole("navigation", { name: /main/i })).toBeInTheDocument();
  });
});

/**
 * The mobile drawer is the whole point of the shell work: before it existed,
 * every staff link was unreachable below the md breakpoint.
 */
describe("AppShell mobile navigation", () => {
  beforeEach(() => {
    authState.user = makeUser({ is_shop_admin: true, is_approver: true, can_review_orders: true });
  });

  it("keeps the drawer closed until the menu button is pressed", () => {
    renderShell();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open navigation menu/i })).toBeInTheDocument();
  });

  it("opens the drawer and exposes the same links on small screens", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /open navigation menu/i }));

    const drawer = await screen.findByRole("dialog");
    expect(drawer).toBeInTheDocument();
    // The drawer carries the same destinations as the desktop bar. Names are
    // anchored because "New Order" also prefixes "New Order for Customer".
    expect(within(drawer).getByRole("link", { name: /^new order$/i })).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /review queue/i })).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /pricing/i })).toBeInTheDocument();
  });

  it("closes the drawer on Escape", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: /open navigation menu/i }));
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});