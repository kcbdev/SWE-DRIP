const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** Same-origin API fetch carrying the Better Auth session cookie. */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}`);
  }
  return (await response.json()) as T;
}

export type Role = "admin" | "operator" | "viewer";

export interface ApiUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
}

export const isAdmin = (role: string | undefined): boolean => role === "admin";
