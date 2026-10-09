import { useEffect, useState } from "react";
import {
  ChevronDown,
  ClipboardCheck,
  ClipboardList,
  FilePlus2,
  FileText,
  LogOut,
  Menu,
  PackageSearch,
  Settings,
  Tags,
  UserPlus,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

type AuthUser = ReturnType<typeof useAuth>["user"];

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Match the exact path only. Needed for parents like /admin, which would
   *  otherwise stay highlighted on every /admin/* page. */
  end?: boolean;
  /** Predicates keep role rules in one place instead of scattered JSX. */
  show: (user: AuthUser) => boolean;
}

const CUSTOMER_NAV: NavItem[] = [
  {
    to: "/order",
    label: "New order",
    icon: FilePlus2,
    show: (u) => !u?.is_shop_admin,
  },
  { to: "/track", label: "Track order", icon: PackageSearch, show: () => true },
  // Guests have no order history, so don't offer a page that can't work for them.
  { to: "/orders", label: "My orders", icon: ClipboardList, show: (u) => !!u },
];

const STAFF_NAV: NavItem[] = [
  {
    to: "/admin",
    label: "Review queue",
    icon: ClipboardCheck,
    end: true,
    show: (u) => !!u?.can_review_orders,
  },
  {
    to: "/admin/orders/new",
    label: "Create order for customer",
    icon: FilePlus2,
    show: (u) => !!u?.is_shop_admin,
  },
  {
    to: "/admin/pricing",
    label: "Pricing",
    icon: Tags,
    show: (u) => !!u?.is_shop_admin,
  },
  {
    to: "/admin/settings",
    label: "API settings",
    icon: Settings,
    show: (u) => !!u?.is_shop_admin,
  },
  {
    to: "/admin/users",
    label: "Staff",
    icon: Users,
    show: (u) => !!u?.is_shop_admin,
  },
];

function isPathActive(pathname: string, { to, end }: NavItem) {
  return end
    ? pathname === to
    : pathname === to || pathname.startsWith(`${to}/`);
}

/** One style for every nav link. The drawer gets taller touch targets. */
function navClass(isActive: boolean, size: "bar" | "drawer" = "bar") {
  return cn(
    "flex items-center gap-2 rounded-md px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    size === "drawer" ? "py-3" : "py-2",
    isActive
      ? "bg-accent font-medium text-accent-foreground"
      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
  );
}

function displayName(user: NonNullable<AuthUser>) {
  return user.first_name || user.email;
}

function initials(user: NonNullable<AuthUser>) {
  return displayName(user).trim().charAt(0).toUpperCase() || "?";
}

/** Role chip. */
function UserBadge({ className }: { className?: string }) {
  const { user } = useAuth();
  if (!user) return null;
  if (user.is_shop_admin) {
    return (
      <span
        className={cn(
          "rounded bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary",
          className,
        )}
      >
        Staff
      </span>
    );
  }
  if (user.is_approver) {
    return (
      <span
        className={cn(
          "rounded bg-progress/15 px-1.5 py-0.5 text-xs font-semibold text-progress",
          className,
        )}
      >
        Approver
      </span>
    );
  }
  return null;
}

function Avatar({ user }: { user: NonNullable<AuthUser> }) {
  return (
    <span
      aria-hidden="true"
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
    >
      {initials(user)}
    </span>
  );
}

function NavLinks({
  items,
  size = "bar",
  onNavigate,
}: {
  items: NavItem[];
  size?: "bar" | "drawer";
  onNavigate?: () => void;
}) {
  return (
    <>
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) => navClass(isActive, size)}
        >
          {/* In the top bar, icons only appear when there is room for them. */}
          <Icon
            className={cn(
              "h-4 w-4 shrink-0",
              size === "bar" && "hidden lg:block",
            )}
            aria-hidden="true"
          />
          {label}
        </NavLink>
      ))}
    </>
  );
}

/**
 * Staff tools on desktop. Five inline links plus three customer links don't
 * fit at md, so they collapse into one menu. A lone link stays inline.
 */
function StaffMenu({ items }: { items: NavItem[] }) {
  const { pathname } = useLocation();

  if (items.length === 1) {
    return (
      <div className="hidden items-center border-l pl-3 md:flex">
        <NavLinks items={items} />
      </div>
    );
  }

  const activeItem = items.find((item) => isPathActive(pathname, item));

  return (
    <div className="hidden items-center border-l pl-3 md:flex">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "gap-1.5",
              activeItem && "bg-accent font-medium text-accent-foreground",
            )}
          >
            {activeItem ? activeItem.label : "Staff tools"}
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-60">
          <DropdownMenuLabel className="text-xs text-muted-foreground">
            Staff tools
          </DropdownMenuLabel>
          {items.map((item) => {
            const active = isPathActive(pathname, item);
            return (
              <DropdownMenuItem
                key={item.to}
                asChild
                className={cn(active && "bg-accent font-medium")}
              >
                <Link to={item.to} aria-current={active ? "page" : undefined}>
                  <item.icon className="h-4 w-4" aria-hidden="true" />
                  {item.label}
                </Link>
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function UserMenu({
  user,
  logout,
}: {
  user: NonNullable<AuthUser>;
  logout: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="max-w-[14rem] gap-2 px-2"
          aria-label={`Account menu for ${displayName(user)}`}
        >
          <Avatar user={user} />
          <span className="hidden truncate sm:inline">{displayName(user)}</span>
          <UserBadge className="hidden lg:inline" />
          <ChevronDown className="h-4 w-4 shrink-0" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <div className="flex items-center gap-2">
            <span className="block min-w-0 truncate text-sm font-medium">
              {displayName(user)}
            </span>
            <UserBadge />
          </div>
          <span className="block truncate text-xs text-muted-foreground">
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/orders">
            <ClipboardList className="h-4 w-4" aria-hidden="true" />
            My orders
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout}>
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function AuthButtons({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Button asChild variant="ghost" size="sm">
        <Link to="/login">Log in</Link>
      </Button>
      <Button asChild size="sm">
        <Link to="/register">Sign up</Link>
      </Button>
    </div>
  );
}

export default function AppShell() {
  const { user, logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();

  // A route change must not leave the drawer covering the page it navigated to.
  // It also shouldn't leave the new page scrolled to where the last one ended.
  useEffect(() => {
    setDrawerOpen(false);
    if (!location.hash) window.scrollTo({ top: 0 });
  }, [location.pathname, location.hash]);

  const customerNav = CUSTOMER_NAV.filter((item) => item.show(user));
  const staffNav = STAFF_NAV.filter((item) => item.show(user));
  const closeDrawer = () => setDrawerOpen(false);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Keyboard users can jump past navigation on every page. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-2 px-4">
          {/* Below md the navigation lives in the drawer, so the trigger shows. */}
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="-ml-2 md:hidden"
                aria-label="Open navigation menu"
              >
                <Menu className="h-5 w-5" aria-hidden="true" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="flex w-72 flex-col gap-0">
              <SheetHeader className="text-left">
                <SheetTitle>
                  <Link
                    to="/"
                    onClick={closeDrawer}
                    className="flex items-center gap-2"
                  >
                    <FileText
                      className="h-5 w-5 text-primary"
                      aria-hidden="true"
                    />
                    PrintEasy
                  </Link>
                </SheetTitle>
                <SheetDescription className="sr-only">
                  Site navigation
                </SheetDescription>
              </SheetHeader>

              {/* Only the nav scrolls, so the account section stays in reach. */}
              <div className="mt-4 flex-1 overflow-y-auto">
                <nav aria-label="Main" className="flex flex-col gap-1">
                  <NavLinks
                    items={customerNav}
                    size="drawer"
                    onNavigate={closeDrawer}
                  />
                </nav>
                {staffNav.length > 0 && (
                  <>
                    <p className="mb-1 mt-6 px-3 text-xs font-semibold text-muted-foreground">
                      Staff tools
                    </p>
                    <nav aria-label="Staff" className="flex flex-col gap-1">
                      <NavLinks
                        items={staffNav}
                        size="drawer"
                        onNavigate={closeDrawer}
                      />
                    </nav>
                  </>
                )}
              </div>

              <div className="border-t pt-4">
                {user ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <Avatar user={user} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium">
                            {displayName(user)}
                          </span>
                          <UserBadge />
                        </div>
                        <span className="block truncate text-xs text-muted-foreground">
                          {user.email}
                        </span>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        closeDrawer();
                        logout();
                      }}
                    >
                      <LogOut className="h-4 w-4" aria-hidden="true" />
                      Log out
                    </Button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button asChild variant="outline" className="flex-1">
                      <Link to="/login" onClick={closeDrawer}>
                        Log in
                      </Link>
                    </Button>
                    <Button asChild className="flex-1">
                      <Link to="/register" onClick={closeDrawer}>
                        <UserPlus className="h-4 w-4" aria-hidden="true" />
                        Sign up
                      </Link>
                    </Button>
                  </div>
                )}
              </div>
            </SheetContent>
          </Sheet>

          {/* The wordmark stays visible on phones so the brand is never lost. */}
          <Link to="/" className="flex items-center gap-2 font-bold">
            <FileText className="h-5 w-5 text-primary" aria-hidden="true" />
            PrintEasy
          </Link>

          <nav
            aria-label="Main"
            className="ml-4 hidden items-center gap-1 md:flex"
          >
            <NavLinks items={customerNav} />
          </nav>
          {staffNav.length > 0 && <StaffMenu items={staffNav} />}

          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <UserMenu user={user} logout={logout} />
            ) : (
              // On phones, auth lives in the drawer; the bar stays uncluttered.
              <AuthButtons className="hidden md:flex" />
            )}
          </div>
        </div>
      </header>

      <main
        id="main-content"
        className="mx-auto w-full max-w-6xl flex-1 scroll-mt-16 px-4 py-6 sm:py-8"
      >
        <Outlet />
      </main>

      <footer className="border-t py-6 text-center text-xs text-muted-foreground">
        <p>PrintEasy. Every order is checked by a person before it prints.</p>
      </footer>
    </div>
  );
}
