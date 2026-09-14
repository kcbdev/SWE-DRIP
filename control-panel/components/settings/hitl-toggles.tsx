"use client";

import { useEffect, useState } from "react";

import { isAdmin } from "@/lib/api";
import { type HitlFlags, fetchHitlFlags, toggleHitl } from "@/lib/settings";

/** Per-node HITL toggle with confirmation dialog. Admin-only write. */
export function HitlToggles({ role }: { role?: string }) {
  const [flags, setFlags] = useState<HitlFlags | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [confirmNode, setConfirmNode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const admin = isAdmin(role);

  useEffect(() => {
    void fetchHitlFlags()
      .then(setFlags)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleToggle(node: string, enabled: boolean) {
    setPending(node);
    setError(null);
    try {
      const updated = await toggleHitl(node, enabled);
      setFlags(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "toggle failed");
    } finally {
      setPending(null);
      setConfirmNode(null);
    }
  }

  if (error && !flags) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load HITL flags: {error}
      </p>
    );
  }

  if (!flags) {
    return <p className="font-mono text-xs text-muted-foreground">Loading HITL flags...</p>;
  }

  const nodes = Object.keys(flags);

  return (
    <section className="border border-border bg-card p-4" data-testid="hitl-toggles">
      <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
        HITL Toggles
      </h2>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        Per-node human-in-the-loop gates. Toggling requires confirmation and writes an audit row.
      </p>

      {error ? (
        <p className="mt-2 font-mono text-xs text-destructive">{error}</p>
      ) : null}

      <div className="mt-4 flex flex-col gap-2">
        {nodes.map((node) => (
          <div
            key={node}
            className="flex items-center justify-between border border-border px-3 py-2"
          >
            <span className="font-mono text-sm text-foreground">{node}</span>
            {admin ? (
              <div className="flex items-center gap-3">
                {confirmNode === node ? (
                  <>
                    <span className="font-mono text-xs text-muted-foreground">
                      Confirm {flags[node] ? "disable" : "enable"}?
                    </span>
                    <button
                      type="button"
                      disabled={pending === node}
                      onClick={() => void handleToggle(node, !flags[node])}
                      className="bg-primary px-3 py-1 font-mono text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
                    >
                      {pending === node ? "Saving..." : "Yes"}
                    </button>
                    <button
                      type="button"
                      disabled={pending === node}
                      onClick={() => setConfirmNode(null)}
                      className="font-mono text-xs text-muted-foreground hover:text-foreground disabled:opacity-40"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmNode(node)}
                    className={`font-mono text-xs px-3 py-1 border ${
                      flags[node]
                        ? "border-primary text-primary"
                        : "border-border text-muted-foreground"
                    }`}
                  >
                    {flags[node] ? "ON" : "OFF"}
                  </button>
                )}
              </div>
            ) : (
              <span
                className={`font-mono text-xs ${
                  flags[node] ? "text-primary" : "text-muted-foreground"
                }`}
              >
                {flags[node] ? "ON" : "OFF"}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
