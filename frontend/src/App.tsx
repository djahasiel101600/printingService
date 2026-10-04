import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { AuthProvider } from "@/components/auth";
import AppShell from "@/components/AppShell";
import { RequireAuth } from "@/components/ProtectedRoute";

import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import SetupPage from "@/pages/SetupPage";
import EpsonCallbackPage from "@/pages/EpsonCallbackPage";
import NewOrderPage from "@/pages/NewOrderPage";
import TrackOrderPage from "@/pages/TrackOrderPage";
import MyOrdersPage from "@/pages/MyOrdersPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import AdminOrdersPage from "@/pages/AdminOrdersPage";
import AdminOrderDetailPage from "@/pages/AdminOrderDetailPage";
import AdminSettingsPage from "@/pages/AdminSettingsPage";
import AdminUsersPage from "@/pages/AdminUsersPage";
import AdminPricingPage from "@/pages/AdminPricingPage";
import QuickPrintPage from "@/pages/QuickPrintPage";
import HomePage from "@/pages/HomePage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/setup" element={<SetupPage />} />
              <Route path="/epson/callback" element={<EpsonCallbackPage />} />
              <Route path="/order" element={<NewOrderPage />} />
              <Route path="/track" element={<TrackOrderPage />} />
              {/* My Orders serves both signed-in users (their account orders)
                  and guests (orders saved on this device), so no RequireAuth. */}
              <Route path="/orders" element={<MyOrdersPage />} />
              {/* No RequireAuth: guests who just placed an order open their
                  confirmation page by proving ownership with the tracking ID. */}
              <Route path="/orders/:id" element={<OrderDetailPage />} />
              {/* The review queue: admins *and* approvers (staffOnly). */}
              <Route
                path="/admin"
                element={
                  <RequireAuth staffOnly>
                    <AdminOrdersPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/admin/settings"
                element={
                  <RequireAuth adminOnly>
                    <AdminSettingsPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/admin/pricing"
                element={
                  <RequireAuth adminOnly>
                    <AdminPricingPage />
                  </RequireAuth>
                }
              />
              {/* User management: owner-only (create approvers/admins). */}
              <Route
                path="/admin/users"
                element={
                  <RequireAuth adminOnly>
                    <AdminUsersPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/admin/orders/new"
                element={
                  <RequireAuth adminOnly>
                    <NewOrderPage adminMode />
                  </RequireAuth>
                }
              />
              <Route
                path="/admin/orders/:id"
                element={
                  <RequireAuth staffOnly>
                    <AdminOrderDetailPage />
                  </RequireAuth>
                }
              />
              {/* Kiosk / QR entry: scan-to-print wizard, open to guests. */}
              <Route path="/q" element={<QuickPrintPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </QueryClientProvider>
  );
}
