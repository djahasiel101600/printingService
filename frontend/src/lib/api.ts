import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

export const TOKEN_KEY = "printservice.token";

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
