"use client";

import { useEffect, useState } from "react";

import { isAdmin } from "@/lib/api";
import {
  type AgentInfo,
  fetchAgents,
  patchAgentCap,
} from "@/lib/agents";

const GLOBAL_MONTHLY_CAP = 130;

export function RosterTable({ role }: { role?: string }) {
  const [agents, setAgents] = useState<AgentInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [capValue, setCapValue] = useState("");
  const [noteValue, setNoteValue] = useState("");
  const [pending, setPending] = useState(false);
  const admin = isAdmin(role);

  useEffect(() => {
    void fetchAgents()
      .then(setAgents)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  async function handleSave(node: string) {
    setPending(true);
    setError(null);
    try {
      const cap = parseFloat(capValue);
      if (isNaN(cap) || cap < 0) {
        setError("Cap must be a non-negative number");
        return;
      }
      if (cap > GLOBAL_MONTHLY_CAP) {
        setError(`Cap cannot exceed global monthly cap of $${GLOBAL_MONTHLY_CAP}`);
        return;
      }
      if (!noteValue.trim()) {
        setError("Cost-impact note is required");
        return;
      }
      const updated = await patchAgentCap(node, cap, noteValue);
      setAgents((prev) =>
        prev ? prev.map((a) => (a.node === node ? updated : a)) : prev,
      );
      setEditing(null);
      setCapValue("");
      setNoteValue("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "update failed");
    } finally {
      setPending(false);
    }
  }

  if (error && !agents) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load agents: {error}
      </p>
    );
  }

  if (!agents) {
    return <p className="font-mono text-xs text-muted-foreground">Loading agents...</p>;
  }

  return (
    <section className="border border-border bg-card p-4" data-testid="roster-table">
      <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
        Agent Roster
      </h2>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        Per-node model assignments and budget caps. Routing is immutable here — edit in pipeline/routing.py.
      </p>

      {error ? (
        <p className="mt-2 font-mono text-xs text-destructive">{error}</p>
      ) : null}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse font-mono text-xs">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="px-2 py-1">Node</th>
              <th className="px-2 py-1">Role</th>
              <th className="px-2 py-1">Model</th>
              <th className="px-2 py-1">Cap</th>
              <th className="px-2 py-1">Spend</th>
              {admin ? <th className="px-2 py-1">Edit</th> : null}
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.node} className="border-b border-border">
                <td className="px-2 py-1 text-foreground">{a.node}</td>
                <td className="px-2 py-1 text-foreground">{a.role}</td>
                <td className="px-2 py-1 text-muted-foreground">
                  {a.model ?? <span className="italic">deterministic</span>}
                </td>
                <td className="px-2 py-1 text-foreground">${a.cap_usd.toFixed(2)}</td>
                <td className="px-2 py-1 text-foreground">${a.spend_usd.toFixed(2)}</td>
                {admin ? (
                  <td className="px-2 py-1">
                    {editing === a.node ? (
                      <div className="flex flex-col gap-1">
                        <div className="flex gap-1">
                          <input
                            type="number"
                            value={capValue}
                            onChange={(e) => setCapValue(e.target.value)}
                            className="w-20 border border-border bg-background px-1 py-0.5 text-foreground"
                            placeholder="Cap $"
                          />
                          <input
                            type="text"
                            value={noteValue}
                            onChange={(e) => setNoteValue(e.target.value)}
                            className="w-40 border border-border bg-background px-1 py-0.5 text-foreground"
                            placeholder="Cost-impact note"
                          />
                        </div>
                        <div className="flex gap-1">
                          <button
                            type="button"
                            disabled={pending}
                            onClick={() => void handleSave(a.node)}
                            className="bg-primary px-2 py-0.5 text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
                          >
                            {pending ? "Saving..." : "Save"}
                          </button>
                          <button
                            type="button"
                            disabled={pending}
                            onClick={() => {
                              setEditing(null);
                              setCapValue("");
                              setNoteValue("");
                            }}
                            className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(a.node);
                          setCapValue(String(a.cap_usd));
                          setNoteValue("");
                        }}
                        className="border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground"
                      >
                        Edit
                      </button>
                    )}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
