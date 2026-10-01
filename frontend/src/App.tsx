import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { AuthProvider } from "@/components/auth";
import AppShell from "@/components/AppShell";
import { RequireAuth } from "@/components/ProtectedRoute";

import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import SetupPage from "@/pages/SetupPage";
import NewOrderPage from "@/pages/NewOrderPage";
import TrackOrderPage from "@/pages/TrackOrderPage";
import MyOrdersPage from "@/pages/MyOrdersPage";
import OrderDetailPage from "@/pages/OrderDetailPage";
import AdminOrdersPage from "@/pages/AdminOrdersPage";
import AdminOrderDetailPage from "@/pages/AdminOrderDetailPage";
import AdminSettingsPage from "@/pages/AdminSettingsPage";
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
              <Route path="/order" element={<NewOrderPage />} />
              <Route path="/track" element={<TrackOrderPage />} />
              <Route
                path="/orders"
                element={
                  <RequireAuth>
                    <MyOrdersPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/orders/:id"
                element={
                  <RequireAuth>
                    <OrderDetailPage />
                  </RequireAuth>
                }
              />
              <Route
                path="/admin"
                element={
                  <RequireAuth adminOnly>
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
                path="/admin/orders/:id"
                element={
                  <RequireAuth adminOnly>
                    <AdminOrderDetailPage />
                  </RequireAuth>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </QueryClientProvider>
  );
}
