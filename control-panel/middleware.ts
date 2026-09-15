import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route gate: every PAGE requires a session cookie; everything else is public.
 *
 * This checks cookie PRESENCE only (Edge runtime has no Postgres access);
 * validity is resolved client-side (useSession) and API-side (401). A stale
 * cookie therefore lands on a signed-out shell with a working Sign in link
 * instead of a redirect loop — the login page never bounces away.
 */
const SESSION_COOKIES = [
  "__Secure-better-auth.session_token",
  "better-auth.session_token",
];

/** Paths that must never be gated (pure, unit-tested). */
export function isPublicPath(pathname: string): boolean {
  if (pathname.startsWith("/api/")) return true;
  if (pathname.startsWith("/_next/")) return true;
  if (pathname === "/login" || pathname.startsWith("/login/")) return true;
  // Any static file: /favicon.ico, /icon.svg, /images/x.png. Gating these
  // handed the browser a redirect-to-login as its icon/image.
  if (/\.[^/]*$/.test(pathname)) return true;
  return false;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }
  const hasSession = SESSION_COOKIES.some((name) => request.cookies.has(name));
  if (!hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Page routes only; static assets stay public (see isPublicPath).
  matcher: ["/((?!api/|_next/|.*\\..*).*)"],
};
