import { useEffect, useState } from "react";
import { Dumbbell, FileText, LogOut, Menu, Settings, Tags, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  label: string;
  icon?: LucideIcon;
  /** Predicates keep role rules in one place instead of scattered JSX. */
  show: (user: ReturnType<typeof useAuth>["user"]) => boolean;
}

const CUSTOMER_NAV: NavItem[] = [
  { to: "/order", label: "New Order", show: () => true },
  { to: "/track", label: "Track Order", show: () => true },
  { to: "/orders", label: "My Orders", show: () => true },
];

const STAFF_NAV: NavItem[] = [
  { to: "/admin", label: "Review Queue", icon: Dumbbell, show: (u) => !!u?.can_review_orders },
  { to: "/admin/orders/new", label: "New Order for Customer", icon: FileText, show: (u) => !!u?.is_shop_admin },
  { to: "/admin/pricing", label: "Pricing", icon: Tags, show: (u) => !!u?.is_shop_admin },
  { to: "/admin/settings", label: "API Settings", icon: Settings, show: (u) => !!u?.is_shop_admin },
  { to: "/admin/users", label: "Staff", icon: Users, show: (u) => !!u?.is_shop_admin },
];

/** Active and inactive styling, shared by the desktop bar and the drawer. */
function navClass(isActive: boolean) {
  return cn(
    "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive
      ? "bg-accent font-medium text-accent-foreground"
      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
  );
}

/** Role chip. Approver used to be a hardcoded indigo, now a token. */
function UserBadge() {
  const { user } = useAuth();
  if (!user) return null;
  if (user.is_shop_admin) {
    return (
      <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary">staff</span>
    );
  }
  if (user.is_approver) {
    return (
      <span className="rounded bg-progress/15 px-1.5 py-0.5 text-xs font-semibold text-progress">
        approver
      </span>
    );
  }
  return null;
}

export default function AppShell() {
  const { user, logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  // A route change must not leave the drawer covering the page it navigated to.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const customerNav = CUSTOMER_NAV.filter((item) => item.show(user));
  const staffNav = STAFF_NAV.filter((item) => item.show(user));

  const renderLinks = (items: NavItem[]) =>
    items.map(({ to, label, icon: Icon }) => (
      <NavLink key={to} to={to} className={({ isActive }) => navClass(isActive)}>
        {Icon && <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />}
        {label}
      </NavLink>
    ));

  return (
    <div className="flex min-h-screen flex-col">
      {/* Keyboard users can jump past navigation on every page. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-4">
          {/* Below md the navigation lives in the drawer, so the trigger shows. */}
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation menu">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="overflow-y-auto">
              <SheetHeader>
                <SheetTitle>
                  <Link to="/" className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-primary" />
                    PrintEasy
                  </Link>
                </SheetTitle>
              </SheetHeader>
              <nav aria-label="Main" className="flex flex-col gap-1">
                {renderLinks(customerNav)}
              </nav>
              {staffNav.length > 0 && (
                <>
                  <p className="mb-1 mt-6 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Staff
                  </p>
                  <nav aria-label="Staff" className="flex flex-col gap-1">
                    {renderLinks(staffNav)}
                  </nav>
                </>
              )}
              <div className="mt-auto border-t pt-4">
                {user ? (
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate text-sm text-muted-foreground">
                      {user.first_name || user.email}
                    </span>
                    <Button variant="outline" size="sm" onClick={logout}>
                      <LogOut className="h-4 w-4" />
                      Log out
                    </Button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button asChild variant="outline" size="sm" className="flex-1">
                      <Link to="/login">Log in</Link>
                    </Button>
                    <Button asChild size="sm" className="flex-1">
                      <Link to="/register">Sign up</Link>
                    </Button>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>

          <Link to="/" className="flex items-center gap-2 font-bold">
            <FileText className="h-5 w-5 text-primary" />
            <span className="hidden sm:inline">PrintEasy</span>
          </Link>

          <nav aria-label="Main" className="ml-4 hidden items-center gap-1 md:flex">
            {renderLinks(customerNav)}
          </nav>
          {staffNav.length > 0 && (
            <nav aria-label="Staff" className="hidden items-center gap-1 border-l pl-3 md:flex">
              {renderLinks(staffNav)}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="max-w-[12rem]">
                    <span className="truncate">{user.first_name || user.email}</span>
                    <UserBadge />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel className="font-normal">
                    <span className="block truncate text-sm font-medium">
                      {user.first_name || user.email}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link to="/orders">
                      <FileText className="h-4 w-4" />
                      My Orders
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={logout}>
                    <LogOut className="h-4 w-4" />
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/login">Log in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/register">Sign up</Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t py-6 text-center text-xs text-muted-foreground">
        <p>PrintEasy — on-demand printing, reviewed by humans before it hits the printer.</p>
      </footer>
    </div>
  );
}
