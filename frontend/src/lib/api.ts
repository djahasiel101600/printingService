import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

export const TOKEN_KEY = "printservice.token";

/**
 * Orders created without an account are remembered on this device so the
 * customer can reopen their confirmation page and view "My Orders" without
 * signing in. Each entry carries the tracking ID used as ownership proof.
 */
export interface GuestOrderRef {
  id: number;
  tracking_id: string;
  created_at: string;
}

const GUEST_ORDERS_KEY = "printservice.guest-orders";

export function loadGuestOrders(): GuestOrderRef[] {
  try {
    const raw = localStorage.getItem(GUEST_ORDERS_KEY);
    const parsed = raw ? (JSON.parse(raw) as GuestOrderRef[]) : [];
    return Array.isArray(parsed) ? parsed.filter((o) => o && typeof o.id === "number") : [];
  } catch {
    return [];
  }
}

export function saveGuestOrder(ref: GuestOrderRef): GuestOrderRef[] {
  const next = [ref, ...loadGuestOrders().filter((o) => o.id !== ref.id)].slice(0, 50);
  localStorage.setItem(GUEST_ORDERS_KEY, JSON.stringify(next));
  return next;
}

export function removeGuestOrder(id: number): GuestOrderRef[] {
  const next = loadGuestOrders().filter((o) => o.id !== id);
  localStorage.setItem(GUEST_ORDERS_KEY, JSON.stringify(next));
  return next;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (data) {
      if (typeof data.detail === "string") return data.detail;
      const first = Object.values(data)[0];
      if (typeof first === "string") return first;
      if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    }
    if (error.code === "ERR_NETWORK") return "Cannot reach the print server.";
  }
  return "Something went wrong. Please try again.";
}
