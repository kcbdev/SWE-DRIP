"use client";

import { useState } from "react";

import {
  detailHrefFor,
  filterByTab,
  rejectNoteValid,
  waitingAge,
  TABS,
  type ApprovalItem,
  type ApprovalTab,
  type DecisionAction,
} from "@/lib/approvals";

export interface ApprovalsViewProps {
  items: ApprovalItem[];
  canDecide: boolean;
  deciding: Record<number, DecisionAction>;
  error: string | null;
  streamLive: boolean;
  onDecide: (item: ApprovalItem, action: DecisionAction, note: string) => void;
  onRefresh: () => void;
}

export function ApprovalsView({
  items,
  canDecide,
  deciding,
  error,
  streamLive,
  onDecide,
  onRefresh,
}: ApprovalsViewProps) {
  const [tab, setTab] = useState<ApprovalTab>("all");
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [noteError, setNoteError] = useState<string | null>(null);
  const visible = filterByTab(items, tab);

  const decide = (item: ApprovalItem, action: DecisionAction) => {
    const note = notes[item.id] ?? "";
    if (action === "reject" && !rejectNoteValid(note)) {
      setNoteError(`Row ${item.id}: reject needs a note (feeds regeneration).`);
      return;
    }
    setNoteError(null);
    onDecide(item, action, note);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            aria-pressed={tab === t.key}
            className={`border px-3 py-1 font-mono text-xs uppercase tracking-widest ${
              tab === t.key
                ? "border-primary text-primary"
                : "border-border text-muted-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
        <span className="ml-auto flex items-center gap-3">
          <span className="font-mono text-xs text-muted-foreground">
            {streamLive ? "stream: live" : "stream: unavailable — manual refresh"}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="border border-border px-3 py-1 font-mono text-xs text-foreground"
          >
            Refresh
          </button>
        </span>
      </div>

      {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
      {noteError ? <p className="font-mono text-xs text-destructive">{noteError}</p> : null}

      {visible.length === 0 ? (
        <p className="border border-border p-4 font-mono text-xs text-muted-foreground">
          No open approvals{ initializedTabSuffix(tab) }.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((item) => {
            const pending = deciding[item.id];
            const href = detailHrefFor(item);
            return (
              <li
                key={item.id}
                className="flex flex-wrap items-center gap-3 border border-border bg-card p-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-sm text-foreground">
                    {item.entity_ref.label}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {item.node} · run {item.run_id} · waiting {waitingAge(item.waiting_since)}
                    </span>
                  </p>
                  {href ? (
                    <a href={href} className="font-mono text-xs text-primary">
                      Full detail
                    </a>
                  ) : null}
                </div>
                {canDecide ? (
                  <div className="flex items-center gap-2">
                    <input
                      aria-label={`Note for approval ${item.id}`}
                      placeholder="note (required to reject)"
                      value={notes[item.id] ?? ""}
                      disabled={pending !== undefined}
                      onChange={(event) =>
                        setNotes((current) => ({ ...current, [item.id]: event.target.value }))
                      }
                      className="border border-border bg-background px-2 py-1 font-mono text-xs text-foreground outline-none focus:border-primary"
                    />
                    <button
                      type="button"
                      disabled={pending !== undefined}
                      onClick={() => decide(item, "approve")}
                      className="border border-primary px-3 py-1 font-mono text-xs text-primary disabled:opacity-50"
                    >
                      {pending === "approve" ? "resuming pipeline…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      disabled={pending !== undefined}
                      onClick={() => decide(item, "reject")}
                      className="border border-border px-3 py-1 font-mono text-xs text-foreground disabled:opacity-50"
                    >
                      {pending === "reject" ? "resuming pipeline…" : "Reject"}
                    </button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function initializedTabSuffix(tab: ApprovalTab): string {
  return tab === "all" ? "" : ` in ${tab}`;
}
