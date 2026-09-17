import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { DEV_BYPASS_ENV, devBypassEmail, isProductionEnv, shouldRedirectToLogin } from "./lib/auth-bypass";

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
  // Dev bypass (PBI-057): a valid email lets pages render without a session
  // cookie. Garbage values fail closed (warn + behave as off); production
  // ignores the flag entirely (the API hard-refuses to boot with it set).
  let bypass: string | null = null;
  try {
    bypass = isProductionEnv(process.env.APP_ENV)
      ? null
      : devBypassEmail(process.env.SWE_DRIP_DEV_AUTH_BYPASS);
  } catch (err) {
    console.warn(`[auth-bypass] ignoring invalid ${DEV_BYPASS_ENV}:`, err);
    bypass = null;
  }
  const hasSession = SESSION_COOKIES.some((name) => request.cookies.has(name));
  if (shouldRedirectToLogin(pathname, hasSession, false, bypass)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Page routes only; static assets stay public (see isPublicPath).
  matcher: ["/((?!api/|_next/|.*\\..*).*)"],
};
