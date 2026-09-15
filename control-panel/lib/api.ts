const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** An HTTP error carrying the API's own `detail`/`message` so the UI can show it. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

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
    throw new ApiError(response.status, await _errorMessage(response));
  }
  return (await response.json()) as T;
}

/**
 * Prefer the server's own wording (FastAPI `detail`, or `message`) over a bare
 * status code — a 409 that explains *why* is the difference between a working
 * control and a silently dead one.
 */
async function _errorMessage(response: Response): Promise<string> {
  const fallback = `API ${response.status}`;
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object") {
      const detail = (body as { detail?: unknown }).detail;
      if (typeof detail === "string" && detail) return detail;
      const message = (body as { message?: unknown }).message;
      if (typeof message === "string" && message) return message;
    }
  } catch {
    // Non-JSON body — keep the status-code fallback.
  }
  return fallback;
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
