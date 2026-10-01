import { Dumbbell, FileText, Settings } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/components/auth";
import { Button } from "@/components/ui/button";

export default function AppShell() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4">
          <Link to="/" className="flex items-center gap-2 font-bold">
            <FileText className="h-5 w-5 text-primary" />
            PrintEasy
          </Link>
          <nav className="ml-4 hidden items-center gap-1 text-sm md:flex">
            <NavLink
              to="/order"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${isActive ? "bg-accent font-medium" : "text-muted-foreground hover:text-foreground"}`
              }
            >
              New Order
            </NavLink>
            <NavLink
              to="/track"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 ${isActive ? "bg-accent font-medium" : "text-muted-foreground hover:text-foreground"}`
              }
            >
              Track Order
            </NavLink>
            {user && (
              <NavLink
                to="/orders"
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 ${isActive ? "bg-accent font-medium" : "text-muted-foreground hover:text-foreground"}`
                }
              >
                My Orders
              </NavLink>
            )}
            {user?.is_shop_admin && (
              <NavLink
                to="/admin/settings"
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 ${isActive ? "bg-accent font-medium" : "text-muted-foreground hover:text-foreground"}`
                }
              >
                <Settings className="mr-1 inline h-3.5 w-3.5" />
                API Settings
              </NavLink>
            )}
            {user?.is_shop_admin && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 ${isActive ? "bg-accent font-medium" : "text-muted-foreground hover:text-foreground"}`
                }
              >
                <Dumbbell className="mr-1 inline h-3.5 w-3.5" />
                Admin
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <>
                <span className="hidden text-sm text-muted-foreground sm:inline">
                  {user.first_name || user.email}
                  {user.is_shop_admin && (
                    <span className="ml-1 rounded bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary">
                      staff
                    </span>
                  )}
                </span>
                <Button variant="outline" size="sm" onClick={logout}>
                  Log out
                </Button>
              </>
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
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t py-4 text-center text-xs text-muted-foreground">
        PrintEasy — on-demand printing, reviewed by humans before it hits the printer.
      </footer>
    </div>
  );
}
