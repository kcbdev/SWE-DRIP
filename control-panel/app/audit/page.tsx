"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AuditTable } from "@/components/audit/audit-table";
import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import {
  buildAuditQuery,
  type AuditEntry,
  type AuditQueryParams,
} from "@/lib/audit-view";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const EMPTY: AuditQueryParams = {
  actor: "",
  action: "",
  entity_type: "",
  entity_id: "",
  start: "",
  end: "",
};

export default function AuditPage() {
  const [filters, setFilters] = useState<AuditQueryParams>(EMPTY);
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => buildAuditQuery(filters), [filters]);

  const load = useCallback(async () => {
    try {
      setEntries(await apiFetch<AuditEntry[]>(`/api/audit?${query}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load audit log");
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  const onChange = (key: keyof AuditQueryParams, value: string) =>
    setFilters((current) => ({ ...current, [key]: value }));

  return (
    <AppShell>
      <div className="flex flex-col gap-4">
        <h1 className="font-sans text-2xl font-semibold">Audit Log</h1>
        {error ? <p className="font-mono text-xs text-destructive">{error}</p> : null}
        <AuditTable
          entries={entries}
          filters={filters}
          onChange={onChange}
          exportBase={`${API_BASE}/api/audit?${query}`}
        />
      </div>
    </AppShell>
  );
}
