"use client";

import Link from "next/link";

import { authClient } from "@/lib/auth-client";
import { isAdmin } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard", adminOnly: false },
  { href: "/audit", label: "Audit Log", adminOnly: false },
  { href: "/settings/users", label: "Users & Roles", adminOnly: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;
  const admin = isAdmin(role);

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-border bg-card p-4">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">SWE Drip</p>
        <nav className="mt-6 flex flex-col gap-1">
          {NAV.filter((item) => !item.adminOnly || admin).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="px-2 py-1 font-mono text-sm text-foreground hover:bg-secondary"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="flex-1">
        <header className="flex items-center justify-between border-b border-border px-6 py-3">
          <span className="font-mono text-xs text-muted-foreground">
            {session?.user?.email ?? "not signed in"}
          </span>
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs uppercase tracking-widest text-primary">
              {role ?? "viewer"}
            </span>
            {session ? (
              <button
                type="button"
                onClick={() => void authClient.signOut()}
                className="font-mono text-xs text-muted-foreground hover:text-foreground"
              >
                Logout
              </button>
            ) : (
              <Link href="/login" className="font-mono text-xs text-primary">
                Sign in
              </Link>
            )}
          </div>
        </header>
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
