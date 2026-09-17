import { NextResponse } from "next/server";

import { DEV_BYPASS_ENV, devBypassEmail, isProductionEnv } from "@/lib/auth-bypass";

/**
 * Dev session probe (PBI-057). Returns the bypass identity when the dev
 * auth bypass is enabled, 401 when it is off, 404 in production (the
 * doorway does not exist there), 500 on a misconfigured value.
 *
 * The email lives server-side only — this route answers role + email to
 * the same-origin UI so the auth-client wrapper can synthesize a session.
 * NEVER read this flag from a NEXT_PUBLIC_ variable.
 */
export async function GET() {
  if (isProductionEnv(process.env.APP_ENV)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  let email: string | null;
  try {
    email = devBypassEmail(process.env[DEV_BYPASS_ENV]);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Invalid bypass" },
      { status: 500 },
    );
  }
  if (!email) {
    return NextResponse.json({ error: "Dev bypass disabled" }, { status: 401 });
  }
  return NextResponse.json({ email, role: "admin", devBypass: true });
}
