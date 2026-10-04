import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/components/auth";

export function RequireAuth({
  children, adminOnly = false, staffOnly = false,
}: { children: ReactNode; adminOnly?: boolean; staffOnly?: boolean }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="py-20 text-center text-muted-foreground">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  // `staffOnly` covers admins *and* approvers (the review queue);
  // `adminOnly` is owner-level configuration only.
  if (adminOnly && !user.is_shop_admin) {
    return <div className="py-20 text-center text-destructive">Admin access required.</div>;
  }
  if (staffOnly && !(user.can_review_orders || user.is_shop_admin)) {
    return <div className="py-20 text-center text-destructive">Staff access required.</div>;
  }
  return <>{children}</>;
}
