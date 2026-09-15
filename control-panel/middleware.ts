import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Route gate: every page except /login requires a session cookie.
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

export function middleware(request: NextRequest) {
  const hasSession = SESSION_COOKIES.some((name) => request.cookies.has(name));
  if (!hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api/|_next/|login|favicon.ico).*)"],
};
