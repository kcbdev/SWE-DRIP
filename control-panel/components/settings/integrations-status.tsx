"use client";

import { useEffect, useState } from "react";

import { type IntegrationsStatus, fetchIntegrations } from "@/lib/settings";

/** Integrations status display — configured/not-configured booleans only, never secret values. */
export function IntegrationsStatus() {
  const [status, setStatus] = useState<IntegrationsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchIntegrations()
      .then(setStatus)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  if (error) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load integrations status: {error}
      </p>
    );
  }

  if (!status) {
    return <p className="font-mono text-xs text-muted-foreground">Loading integrations...</p>;
  }

  const items = [
    { key: "fourthwall_mcp" as const, label: "Fourthwall MCP" },
    { key: "openrouter_key" as const, label: "OpenRouter API Key" },
  ];

  return (
    <section className="border border-border bg-card p-4" data-testid="integrations-status">
      <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
        Integrations
      </h2>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        Connection status only. Credentials are managed via environment variables.
      </p>

      <div className="mt-4 flex flex-col gap-2">
        {items.map(({ key, label }) => (
          <div
            key={key}
            className="flex items-center justify-between border border-border px-3 py-2"
          >
            <span className="font-mono text-sm text-foreground">{label}</span>
            <span
              className={`font-mono text-xs ${
                status[key] ? "text-primary" : "text-muted-foreground"
              }`}
            >
              {status[key] ? "Configured" : "Not configured"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
