"use client";

import { useEffect, useState } from "react";

import { isAdmin } from "@/lib/api";
import {
  type IntegrationsStatus,
  fetchIntegrations,
  saveIntegrations,
  testFourthwall,
} from "@/lib/settings";

/**
 * Integrations panel. Everyone sees connection status; admins also get forms
 * to set Fourthwall/OpenRouter credentials (stored server-side, never echoed).
 */
export function IntegrationsStatus({ role }: { role?: string }) {
  const admin = isAdmin(role);
  const [status, setStatus] = useState<IntegrationsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [fourthwallBaseUrl, setFourthwallBaseUrl] = useState("");
  const [fourthwallUsername, setFourthwallUsername] = useState("");
  const [fourthwallPassword, setFourthwallPassword] = useState("");
  const [openrouterKey, setOpenrouterKey] = useState("");
  const [openrouterBaseUrl, setOpenrouterBaseUrl] = useState("");

  useEffect(() => {
    void fetchIntegrations()
      .then((next) => {
        setStatus(next);
        setFourthwallBaseUrl(next.fourthwall_base_url ?? "");
        setFourthwallUsername(next.fourthwall_username ?? "");
        setOpenrouterBaseUrl(next.openrouter_base_url ?? "");
      })
      .catch((err: unknown) => setError(String(err)));
  }, []);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const patch: Record<string, string> = {};
      // Blank secrets mean "leave unchanged" — only send non-empty values.
      if (fourthwallBaseUrl) patch.fourthwall_api_base_url = fourthwallBaseUrl;
      if (fourthwallUsername) patch.fourthwall_api_username = fourthwallUsername;
      if (openrouterBaseUrl) patch.openrouter_base_url = openrouterBaseUrl;
      if (fourthwallPassword) patch.fourthwall_api_password = fourthwallPassword;
      if (openrouterKey) patch.openrouter_api_key = openrouterKey;
      if (Object.keys(patch).length === 0) {
        setNotice("Nothing to save — enter a credential first.");
        return;
      }
      const next = await saveIntegrations(patch);
      setStatus(next);
      setFourthwallPassword("");
      setOpenrouterKey("");
      setNotice("Credentials saved. Stored values override environment variables.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "failed to save credentials");
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await testFourthwall();
      if (result.ok) setNotice("Fourthwall API reachable.");
      else setError(`Fourthwall reads degraded: ${result.error ?? "unknown error"}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "test failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !status) {
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
    { key: "fourthwall" as const, label: "Fourthwall Open API" },
    { key: "openrouter" as const, label: "OpenRouter API Key" },
  ];

  const field =
    "mt-1 block w-full border border-border bg-background px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-primary";
  const fieldLabel = "font-mono text-xs uppercase tracking-widest text-muted-foreground";

  return (
    <section className="border border-border bg-card p-4" data-testid="integrations-status">
      <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
        Integrations
      </h2>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        Credentials are stored server-side and never returned by the API. A value set here
        overrides the deployment environment variable.
      </p>

      <div className="mt-4 flex flex-col gap-2">
        {items.map(({ key, label: name }) => (
          <div
            key={key}
            className="flex items-center justify-between border border-border px-3 py-2"
          >
            <span className="font-mono text-sm text-foreground">{name}</span>
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

      {error ? <p className="mt-3 font-mono text-xs text-destructive">{error}</p> : null}
      {notice ? <p className="mt-3 font-mono text-xs text-primary">{notice}</p> : null}

      {admin ? (
        <form onSubmit={save} className="mt-5 flex flex-col gap-3 border-t border-border pt-4">
          <h3 className="font-mono text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Set credentials
          </h3>
          <p className="font-mono text-[11px] text-muted-foreground">
            Fourthwall: create an API user under your shop&apos;s{" "}
            <span className="text-primary">Settings → For developers</span> and use its
            username + password (HTTP Basic).
          </p>
          <label className={fieldLabel}>
            Fourthwall API base URL
            <input
              type="url"
              value={fourthwallBaseUrl}
              onChange={(event) => setFourthwallBaseUrl(event.target.value)}
              placeholder="https://api.fourthwall.com"
              className={field}
            />
          </label>
          <label className={fieldLabel}>
            Fourthwall API username
            <input
              type="text"
              value={fourthwallUsername}
              onChange={(event) => setFourthwallUsername(event.target.value)}
              placeholder="fw_api_...@fourthwall.com"
              className={field}
            />
          </label>
          <label className={fieldLabel}>
            Fourthwall API password
            <input
              type="password"
              value={fourthwallPassword}
              onChange={(event) => setFourthwallPassword(event.target.value)}
              placeholder="leave blank to keep current"
              className={field}
            />
          </label>
          <label className={fieldLabel}>
            OpenRouter API key
            <input
              type="password"
              value={openrouterKey}
              onChange={(event) => setOpenrouterKey(event.target.value)}
              placeholder="leave blank to keep current"
              className={field}
            />
          </label>
          <label className={fieldLabel}>
            OpenRouter base URL
            <input
              type="url"
              value={openrouterBaseUrl}
              onChange={(event) => setOpenrouterBaseUrl(event.target.value)}
              placeholder="https://openrouter.ai/api/v1"
              className={field}
            />
          </label>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={busy}
              className="bg-primary px-4 py-2 font-mono text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {busy ? "Saving..." : "Save credentials"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void test()}
              className="border border-border px-4 py-2 font-mono text-sm text-foreground hover:bg-secondary disabled:opacity-50"
            >
              Test Fourthwall
            </button>
          </div>
          <p className="font-mono text-[11px] text-muted-foreground">
            Saving writes an audit row (presence only — values are never logged).
          </p>
        </form>
      ) : null}
    </section>
  );
}
