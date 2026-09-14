"use client";

import { authClient } from "@/lib/auth-client";
import { AppShell } from "@/components/app-shell";
import { RosterTable } from "@/components/agents/roster-table";

export default function AgentsPage() {
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <header className="flex flex-col gap-1 border-b border-border pb-4">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">SWE Drip</p>
          <h1 className="font-sans text-3xl font-semibold">Agents</h1>
        </header>

        <RosterTable role={role} />
      </div>
    </AppShell>
  );
}
