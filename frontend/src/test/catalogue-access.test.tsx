import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RequireAuth } from "@/components/ProtectedRoute";
import { adminUser, approverUser } from "@/test/catalogue-fixtures";
import type { CurrentUser } from "@/lib/types";

const authState: { user: CurrentUser | null; loading: boolean } = {
  user: null,
  loading: false,
};

vi.mock("@/components/auth", () => ({
  useAuth: () => authState,
}));

function renderProtectedCatalogue() {
  render(
    <MemoryRouter initialEntries={["/admin/catalogue"]}>
      <Routes>
        <Route path="/login" element={<p>Login page</p>} />
        <Route
          path="/admin/catalogue"
          element={
            <RequireAuth adminOnly>
              <p>Catalogue administration</p>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  authState.user = null;
  authState.loading = false;
});

describe("catalogue administration access", () => {
  it("redirects signed-out visitors to login", () => {
    renderProtectedCatalogue();
    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Catalogue administration")).not.toBeInTheDocument();
  });

  it("denies approvers even though they can review orders", () => {
    authState.user = approverUser;
    renderProtectedCatalogue();
    expect(screen.getByText("Admin access required.")).toBeInTheDocument();
    expect(screen.queryByText("Catalogue administration")).not.toBeInTheDocument();
  });

  it("allows shop admins", () => {
    authState.user = adminUser;
    renderProtectedCatalogue();
    expect(screen.getByText("Catalogue administration")).toBeInTheDocument();
  });
});
