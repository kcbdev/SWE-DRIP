"use client";

import { useEffect, useState } from "react";

import { isAdmin } from "@/lib/api";
import {
  type IssuedToken,
  type OperatorToken,
  type TokenScope,
  copyText,
  fetchTokens,
  issueToken,
  mcpEndpointUrl,
  revokeToken,
} from "@/lib/operator-tokens";

const SCOPES: { value: TokenScope; label: string; hint: string }[] = [
  { value: "read", label: "read", hint: "Observe: runs, logs, approvals, agents, catalog, audit, calibration." },
  { value: "operate", label: "operate", hint: "Read + run start, approval decisions, agent config, replay. Audited." },
];

/**
 * Operator tokens panel (admin-only; non-admins render nothing — the API is
 * the enforcement point). Values are shown exactly once at issuance and
 * never refetched: the list endpoint only carries metadata.
 */
export function OperatorTokens({ role }: { role?: string }) {
  const admin = isAdmin(role);
  const [tokens, setTokens] = useState<OperatorToken[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<TokenScope[]>(["read"]);
  const [issued, setIssued] = useState<IssuedToken | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedConfig, setCopiedConfig] = useState(false);
  const [revoking, setRevoking] = useState<number | null>(null);

  useEffect(() => {
    if (!admin) return;
    void fetchTokens()
      .then(setTokens)
      .catch((err: unknown) => setError(String(err)));
  }, [admin]);

  if (!admin) return null;

  async function reload() {
    try {
      setTokens(await fetchTokens());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "reload failed");
    }
  }

  async function handleIssue(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Token name is required");
      return;
    }
    if (scopes.length === 0) {
      setError("Pick at least one scope");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await issueToken(name.trim(), scopes);
      setIssued(created);
      setCopied(false);
      setName("");
      await reload();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "issue failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleCopy() {
    if (!issued) return;
    if (await copyText(issued.token)) {
      setCopied(true);
      setNotice("Copied. Vault it now — this value is never shown again.");
    } else {
      setError("Clipboard unavailable — select and copy the value manually.");
    }
  }

  async function handleRevoke(id: number) {
    setBusy(true);
    setError(null);
    try {
      await revokeToken(id);
      setRevoking(null);
      setNotice("Token revoked. In-flight uses fail on their next request.");
      await reload();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "revoke failed");
    } finally {
      setBusy(false);
    }
  }

  function toggleScope(scope: TokenScope) {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]));
  }

  const clientConfig = JSON.stringify(
    { mcpServers: { "swe-drip-operator": {
      type: "streamable-http",
      url: mcpEndpointUrl(),
      headers: { Authorization: "Bearer sdr_…" },
    } } },
    null,
    2,
  );

  if (error && !tokens) {
    return (
      <p className="border border-destructive p-4 font-mono text-xs text-destructive">
        Failed to load operator tokens: {error}
      </p>
    );
  }

  if (!tokens) {
    return <p className="font-mono text-xs text-muted-foreground">Loading operator tokens...</p>;
  }

  const field =
    "mt-1 block w-full border border-border bg-background px-3 py-2 font-mono text-sm text-foreground outline-none focus:border-primary";
  const fieldLabel = "font-mono text-xs uppercase tracking-widest text-muted-foreground";

  return (
    <section className="border border-border bg-card p-4" data-testid="operator-tokens">
      <h2 className="font-mono text-sm font-semibold uppercase tracking-widest text-primary">
        Operator tokens
      </h2>
      <p className="mt-1 font-mono text-xs text-muted-foreground">
        Machine credentials for the MCP doorway (`/mcp`). Issuance and
        revocation are audited (prefix only). Values are shown once and never
        stored where the UI can read them again.
      </p>

      {error ? <p className="mt-3 font-mono text-xs text-destructive">{error}</p> : null}
      {notice ? <p className="mt-3 font-mono text-xs text-primary">{notice}</p> : null}

      {issued ? (
        <div className="mt-4 border border-primary p-3" data-testid="issued-token">
          <p className="font-mono text-xs text-primary">
            Copy this value now — it will never be shown again.
          </p>
          <p className="mt-2 break-all border border-border bg-background p-2 font-mono text-sm text-foreground">
            {issued.token}
          </p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleCopy()}
              className="bg-primary px-4 py-1 font-mono text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={() => {
                setIssued(null);
                setCopied(false);
              }}
              className="border border-border px-4 py-1 font-mono text-xs text-foreground hover:bg-secondary"
            >
              I&apos;ve saved it — dismiss
            </button>
          </div>
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-2">
        {tokens.length === 0 ? (
          <p className="font-mono text-xs text-muted-foreground">No tokens issued yet.</p>
        ) : (
          tokens.map((t) => (
            <div
              key={t.id}
              className="flex flex-wrap items-center justify-between gap-2 border border-border px-3 py-2"
            >
              <div className="flex flex-col gap-1">
                <span className="font-mono text-sm text-foreground">
                  {t.name}{" "}
                  <span className="text-muted-foreground">{t.prefix}…</span>{" "}
                  {t.revoked ? (
                    <span className="border border-destructive px-1 text-xs text-destructive">revoked</span>
                  ) : null}
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  scopes: {t.scopes.join(", ")} · by {t.created_by || "unknown"}
                  {t.last_used_at ? ` · last used ${t.last_used_at}` : " · never used"}
                </span>
              </div>
              {!t.revoked ? (
                revoking === t.id ? (
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-xs">Revoke {t.prefix}…?</span>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void handleRevoke(t.id)}
                      className="border border-destructive px-3 py-1 font-mono text-xs text-destructive disabled:opacity-50"
                    >
                      Confirm revoke
                    </button>
                    <button
                      type="button"
                      onClick={() => setRevoking(null)}
                      className="border border-border px-3 py-1 font-mono text-xs"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setRevoking(t.id)}
                    className="border border-border px-3 py-1 font-mono text-xs text-muted-foreground hover:text-foreground"
                  >
                    Revoke
                  </button>
                )
              ) : null}
            </div>
          ))
        )}
      </div>

      <form onSubmit={handleIssue} className="mt-5 flex flex-col gap-3 border-t border-border pt-4">
        <h3 className="font-mono text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Issue a token
        </h3>
        <label className={fieldLabel}>
          Name
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. opencode-runner"
            className={field}
          />
        </label>
        <fieldset>
          <legend className={fieldLabel}>Scopes</legend>
          <div className="mt-1 flex flex-col gap-1">
            {SCOPES.map((s) => (
              <label key={s.value} className="flex items-start gap-2 font-mono text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={scopes.includes(s.value)}
                  onChange={() => toggleScope(s.value)}
                />
                <span>
                  <span className="text-foreground">{s.label}</span> — {s.hint}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div>
          <button
            type="submit"
            disabled={busy}
            className="bg-primary px-4 py-2 font-mono text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {busy ? "Issuing..." : "Issue token"}
          </button>
        </div>
      </form>

      <div className="mt-5 border-t border-border pt-4">
        <h3 className="font-mono text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Client config
        </h3>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">
          Paste into the MCP client config, replacing the value with an issued token.
        </p>
        <pre className="mt-2 overflow-auto border border-border bg-background p-3 font-mono text-xs text-foreground">
          {clientConfig}
        </pre>
        <div className="mt-2">
          <button
            type="button"
            onClick={() => void copyText(clientConfig).then((ok) => {
              if (ok) {
                setCopiedConfig(true);
                setNotice("Client config copied — replace the placeholder with an issued token.");
              } else {
                setError("Clipboard unavailable — select and copy the snippet manually.");
              }
            })}
            className="border border-border px-4 py-1 font-mono text-xs text-foreground hover:bg-secondary"
          >
            {copiedConfig ? "Copied" : "Copy client config"}
          </button>
        </div>
      </div>
    </section>
  );
}
