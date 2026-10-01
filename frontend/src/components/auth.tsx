import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api, getToken, setToken } from "@/lib/api";
import type { CurrentUser } from "@/lib/types";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  register: (payload: RegisterPayload) => Promise<CurrentUser>;
  setupAdmin: (payload: SetupPayload) => Promise<CurrentUser>;
  logout: () => void;
  refresh: () => Promise<void>;
}

export interface RegisterPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
}

export interface SetupPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<CurrentUser>("/auth/me/");
      setUser(data);
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post("/auth/token/", { email, password });
    setToken(data.access);
    setUser(data.user);
    return data.user as CurrentUser;
  }, []);

  const register = useCallback(async (payload: RegisterPayload) => {
    await api.post("/auth/register/", payload);
    return login(payload.email, payload.password);
  }, []);

  /** First-run only: creates the shop's first admin and logs them straight in. */
  const setupAdmin = useCallback(async (payload: SetupPayload) => {
    const { data } = await api.post("/auth/setup/", payload);
    setToken(data.access);
    setUser(data.user);
    return data.user as CurrentUser;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, setupAdmin, logout, refresh }),
    [user, loading, login, register, setupAdmin, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
