"use client";

import { formatDiff, type AuditEntry, type AuditQueryParams } from "@/lib/audit-view";

export interface AuditTableProps {
  entries: AuditEntry[];
  filters: AuditQueryParams;
  onChange: (key: keyof AuditQueryParams, value: string) => void;
  exportBase: string;
}

const FILTER_FIELDS: { key: keyof AuditQueryParams; label: string; type?: string }[] = [
  { key: "actor", label: "Actor" },
  { key: "action", label: "Action" },
  { key: "entity_type", label: "Entity type" },
  { key: "entity_id", label: "Entity id" },
  { key: "start", label: "From", type: "date" },
  { key: "end", label: "To", type: "date" },
];

export function AuditTable({ entries, filters, onChange, exportBase }: AuditTableProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3 border border-border bg-card p-4">
        {FILTER_FIELDS.map((field) => (
          <label
            key={field.key}
            className="font-mono text-xs uppercase tracking-widest text-muted-foreground"
          >
            {field.label}
            <input
              type={field.type ?? "text"}
              value={filters[field.key] ?? ""}
              onChange={(event) => onChange(field.key, event.target.value)}
              className="mt-1 block border border-border bg-background px-2 py-1 font-mono text-sm text-foreground outline-none focus:border-primary"
            />
          </label>
        ))}
        <a
          href={`${exportBase}&format=csv`}
          download="audit-log.csv"
          className="border border-border px-3 py-2 font-mono text-xs text-primary"
        >
          Export CSV
        </a>
        <a
          href={`${exportBase}&format=json`}
          download="audit-log.json"
          className="border border-border px-3 py-2 font-mono text-xs text-primary"
        >
          Export JSON
        </a>
      </div>

      <table className="w-full border border-border text-left font-mono text-xs">
        <thead className="bg-secondary uppercase tracking-widest text-muted-foreground">
          <tr>
            <th className="px-3 py-2">Timestamp</th>
            <th className="px-3 py-2">Actor</th>
            <th className="px-3 py-2">Action</th>
            <th className="px-3 py-2">Entity</th>
            <th className="px-3 py-2">Before → After</th>
          </tr>
        </thead>
        <tbody>
          {entries.length === 0 ? (
            <tr className="border-t border-border">
              <td className="px-3 py-3 text-muted-foreground" colSpan={5}>
                No audit rows match the filters.
              </td>
            </tr>
          ) : (
            entries.map((entry) => (
              <tr key={entry.id} className="border-t border-border">
                <td className="px-3 py-2">{entry.created_at}</td>
                <td className="px-3 py-2">{entry.actor_user_id}</td>
                <td className="px-3 py-2 text-primary">{entry.action}</td>
                <td className="px-3 py-2">
                  {entry.entity_type}
                  {entry.entity_id ? `:${entry.entity_id}` : ""}
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {formatDiff(entry.before_json, entry.after_json)}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
