"use client";

import { Fragment, useEffect, useState } from "react";

import { isAdmin } from "@/lib/api";
import {
  type AgentConfigPatch,
  type AgentInfo,
  type CatalogList,
  type PromptMeta,
  fetchAgents,
  fetchModels,
  fetchPromptMeta,
  patchAgentConfig,
} from "@/lib/agents";

const GLOBAL_MONTHLY_CAP = 130;

// ---------------------------------------------------------------------------
// Formatting helpers (pure)
// ---------------------------------------------------------------------------

function formatParams(params?: Record<string, number>): string {
  if (!params || Object.keys(params).length === 0) return "defaults";
  const parts: string[] = [];
  if (params.temperature !== undefined) parts.push(`t=${params.temperature}`);
  if (params.max_tokens !== undefined) parts.push(`max ${params.max_tokens}`);
  for (const [k, v] of Object.entries(params)) {
    if (k !== "temperature" && k !== "max_tokens") parts.push(`${k}=${v}`);
  }
  return parts.join(" · ");
}

/** Human-readable before → after summary shown on a successful save. */
export function diffSummary(before: AgentInfo, after: AgentInfo): string {
  const parts: string[] = [];
  if (before.model !== after.model) {
    parts.push(`model ${before.model ?? "none"} → ${after.model ?? "none"}`);
  }
  const bTemp = before.params?.temperature;
  const aTemp = after.params?.temperature;
  if (bTemp !== aTemp) {
    parts.push(`temperature ${bTemp ?? "default"} → ${aTemp ?? "default"}`);
  }
  const bMax = before.params?.max_tokens;
  const aMax = after.params?.max_tokens;
  if (bMax !== aMax) {
    parts.push(`max_tokens ${bMax ?? "default"} → ${aMax ?? "default"}`);
  }
  if ((before.enabled ?? true) !== (after.enabled ?? true)) {
    parts.push(`enabled ${String(before.enabled ?? true)} → ${String(after.enabled ?? true)}`);
  }
  if ((before.prompt_version ?? null) !== (after.prompt_version ?? null)) {
    parts.push(`prompt ${before.prompt_version ?? "none"} → ${after.prompt_version ?? "none"}`);
  }
  if (before.cap_usd !== after.cap_usd) {
    parts.push(`cap $${before.cap_usd.toFixed(2)} → $${after.cap_usd.toFixed(2)}`);
  }
  return parts.length > 0 ? parts.join(" · ") : "no changes";
}

function formatPricePerM(value: number | null): string {
  if (value === null || value === undefined) return "?";
  return `$${value.toFixed(2)}`;
}

/** Defensive shape check — a non-catalog payload disables the picker loudly. */
function normalizeCatalog(list: unknown): CatalogList {
  if (list && typeof list === "object" && Array.isArray((list as CatalogList).models)) {
    const l = list as CatalogList;
    return { models: l.models, stale: !!l.stale, unavailable: !!l.unavailable };
  }
  return { models: [], stale: false, unavailable: true };
}

// ---------------------------------------------------------------------------
// Roster table
// ---------------------------------------------------------------------------

interface EditorState {
  capValue: string;
  noteValue: string;
  modelQuery: string;
  modelOptions: CatalogList | null;
  modelsLoading: boolean;
  /** "unchanged" until the operator picks a catalog row or clears the override. */
  selectedModel: string | null;
  modelChanged: boolean;
  temperature: string;
  maxTokens: string;
  enabled: boolean;
  /** Prompt override editor: toggle reveals the textarea (write-only text). */
  promptToggle: boolean;
  promptText: string;
  promptMeta: PromptMeta | null;
  promptClear: boolean;
}

function editorFor(agent: AgentInfo): EditorState {
  return {
    capValue: String(agent.cap_usd),
    noteValue: "",
    modelQuery: "",
    modelOptions: null,
    modelsLoading: false,
    selectedModel: agent.model,
    modelChanged: false,
    temperature: agent.params?.temperature !== undefined ? String(agent.params.temperature) : "",
    maxTokens: agent.params?.max_tokens !== undefined ? String(agent.params.max_tokens) : "",
    enabled: agent.enabled ?? true,
    promptToggle: agent.has_prompt_override ?? false,
    promptText: "",
    promptMeta: null,
    promptClear: false,
  };
}

export function RosterTable({ role }: { role?: string }) {
  const [agents, setAgents] = useState<AgentInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [pending, setPending] = useState(false);
  const [success, setSuccess] = useState<{ node: string; summary: string } | null>(null);
  const admin = isAdmin(role);

  useEffect(() => {
    void fetchAgents()
      .then(setAgents)
      .catch((err: unknown) => setError(String(err)));
  }, []);

  // Load the catalog when the editor opens, and debounce search queries.
  useEffect(() => {
    if (!editing || !editor) return;
    setEditor((prev) => (prev ? { ...prev, modelsLoading: true } : prev));
    const timer = setTimeout(() => {
      void fetchModels(editor.modelQuery)
        .then((list) => setEditor((prev) => (prev ? { ...prev, modelOptions: normalizeCatalog(list), modelsLoading: false } : prev)))
        .catch(() =>
          setEditor((prev) =>
            prev ? { ...prev, modelOptions: { models: [], stale: false, unavailable: true }, modelsLoading: false } : prev,
          ),
        );
    }, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing, editor?.modelQuery]);

  // Prompt key/version for the node under edit (text never travels).
  useEffect(() => {
    if (!editing || !editor || !agents) return;
    const agent = agents.find((a) => a.node === editing);
    if (!agent?.prompt_key) return;
    let cancelled = false;
    void fetchPromptMeta(editing)
      .then((meta) => {
        if (!cancelled) setEditor((prev) => (prev ? { ...prev, promptMeta: meta } : prev));
      })
      .catch(() => {
        if (!cancelled) setEditor((prev) => (prev ? { ...prev, promptMeta: null } : prev));
      });
    return () => {
      cancelled = true;
    };
  }, [editing, agents]);

  function openEditor(agent: AgentInfo) {
    setEditing(agent.node);
    setEditor(editorFor(agent));
    setError(null);
    setSuccess(null);
  }

  function closeEditor() {
    setEditing(null);
    setEditor(null);
  }

  function setEditorField<K extends keyof EditorState>(key: K, value: EditorState[K]) {
    setEditor((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleSave(agent: AgentInfo) {
    if (!editor) return;
    setPending(true);
    setError(null);
    try {
      if (!editor.noteValue.trim()) {
        setError("Cost-impact note is required");
        return;
      }
      const patch: AgentConfigPatch = { cost_impact_note: editor.noteValue.trim() };

      const cap = parseFloat(editor.capValue);
      if (isNaN(cap) || cap < 0) {
        setError("Cap must be a non-negative number");
        return;
      }
      if (cap > GLOBAL_MONTHLY_CAP) {
        setError(`Cap cannot exceed global monthly cap of $${GLOBAL_MONTHLY_CAP}`);
        return;
      }
      if (cap !== agent.cap_usd) patch.cap_usd = cap;

      const hasModelCall = agent.model !== null || (agent.overridden ?? []).includes("model");
      if (hasModelCall && editor.modelChanged) {
        // null clears the override back to the routing.py default.
        patch.model = editor.selectedModel;
      }

      const params: Record<string, number> = {};
      let paramsTouched = false;
      if (editor.temperature.trim()) {
        paramsTouched = true;
        const t = parseFloat(editor.temperature);
        if (isNaN(t) || t < 0 || t > 2) {
          setError("Temperature must be a number between 0 and 2");
          return;
        }
        params.temperature = t;
      }
      if (editor.maxTokens.trim()) {
        paramsTouched = true;
        const m = Number(editor.maxTokens);
        if (!Number.isInteger(m) || m <= 0) {
          setError("Max tokens must be a positive integer");
          return;
        }
        params.max_tokens = m;
      }
      const hadParams = Object.keys(agent.params ?? {}).length > 0;
      if (paramsTouched) {
        patch.params = params;
      } else if (hadParams && editor.temperature === "" && editor.maxTokens === "") {
        // Both emptied while an override existed → fall back to defaults.
        patch.params = null;
      }

      if (editor.enabled !== (agent.enabled ?? true)) patch.enabled = editor.enabled;

      const hadPromptOverride =
        editor.promptMeta?.has_override ?? agent.has_prompt_override ?? false;
      if (agent.prompt_key) {
        if (editor.promptClear && hadPromptOverride) {
          patch.prompt_override = null;
        } else if (editor.promptToggle && editor.promptText.trim()) {
          patch.prompt_override = editor.promptText;
        } else if (!editor.promptToggle && hadPromptOverride && !editor.promptClear) {
          // Toggled off with an override present → fall back to built-in.
          patch.prompt_override = null;
        }
      }

      const keys = (Object.keys(patch) as string[]).filter((k) => k !== "cost_impact_note");
      if (keys.length === 0) {
        setError("No changes to save");
        return;
      }
      const updated = await patchAgentConfig(agent.node, patch);
      setAgents((prev) => (prev ? prev.map((a) => (a.node === agent.node ? updated : a)) : prev));
      setSuccess({ node: agent.node, summary: diffSummary(agent, updated) });
      closeEditor();
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
        Per-node runtime config. Overrides save to the settings store; defaults live in pipeline/routing.py.
      </p>

      {success ? (
        <p className="mt-2 font-mono text-xs text-primary" data-testid="save-diff">
          {success.node}: {success.summary}
        </p>
      ) : null}
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
              <th className="px-2 py-1">Params</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Cap</th>
              <th className="px-2 py-1">Spend</th>
              {admin ? <th className="px-2 py-1">Edit</th> : null}
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <Fragment key={a.node}>
                <tr className="border-b border-border">
                  <td className="px-2 py-1 text-foreground">{a.node}</td>
                  <td className="px-2 py-1 text-foreground">{a.role}</td>
                  <td className="px-2 py-1 text-muted-foreground">
                    {a.model ?? <span className="italic">deterministic</span>}{" "}
                    {a.model && a.model_source === "store" ? (
                      <span className="border border-primary px-1 text-primary">overridden</span>
                    ) : null}
                    {a.model && a.model_source !== "store" ? (
                      <span className="border border-border px-1">default</span>
                    ) : null}
                  </td>
                  <td className="px-2 py-1 text-muted-foreground">{formatParams(a.params)}</td>
                  <td className="px-2 py-1 text-muted-foreground">
                    {(a.enabled ?? true) ? "enabled" : "disabled"}
                  </td>
                  <td className="px-2 py-1 text-foreground">${a.cap_usd.toFixed(2)}</td>
                  <td className="px-2 py-1 text-foreground">${a.spend_usd.toFixed(2)}</td>
                  {admin ? (
                    <td className="px-2 py-1">
                      {editing === a.node ? (
                        <button
                          type="button"
                          disabled={pending}
                          onClick={closeEditor}
                          className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                        >
                          Close
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => openEditor(a)}
                          className="border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground"
                        >
                          Edit
                        </button>
                      )}
                    </td>
                  ) : null}
                </tr>
                {admin && editing === a.node && editor ? (
                  <tr key={`${a.node}-editor`} className="border-b border-border">
                    <td colSpan={8} className="px-2 py-2">
                      <div className="flex flex-col gap-3 border border-border p-3">
                        {a.model !== null || (a.overridden ?? []).includes("model") ? (
                          <div className="flex flex-col gap-1">
                            <label className="text-muted-foreground">
                              Model — catalog-backed (no free text; unknown IDs are rejected by the API)
                            </label>
                            {editor.modelOptions?.unavailable ? (
                              <p className="text-destructive">
                                Model catalog unavailable — model editing is disabled until the catalog can be
                                verified. Cap, params and status can still be saved.
                              </p>
                            ) : (
                              <>
                                <input
                                  type="text"
                                  value={editor.modelQuery}
                                  onChange={(e) => setEditorField("modelQuery", e.target.value)}
                                  disabled={editor.modelOptions?.unavailable}
                                  className="w-64 border border-border bg-background px-1 py-0.5 text-foreground"
                                  placeholder="Search models…"
                                  aria-label="Search models"
                                />
                                {editor.modelOptions?.stale ? (
                                  <p className="text-muted-foreground">
                                    Catalog may be stale — saves re-verify before accepting.
                                  </p>
                                ) : null}
                                <div className="flex max-h-48 flex-col gap-1 overflow-y-auto" role="listbox" aria-label="Model options">
                                  {editor.modelsLoading && !editor.modelOptions ? (
                                    <p className="text-muted-foreground">Loading models…</p>
                                  ) : null}
                                  {(editor.modelOptions?.models ?? []).map((m) => (
                                    <button
                                      key={m.id}
                                      type="button"
                                      role="option"
                                      aria-selected={editor.selectedModel === m.id}
                                      onClick={() => {
                                        setEditorField("selectedModel", m.id);
                                        setEditorField("modelChanged", true);
                                      }}
                                      className={
                                        editor.selectedModel === m.id
                                          ? "border border-primary px-2 py-1 text-left text-foreground"
                                          : "border border-border px-2 py-1 text-left text-muted-foreground hover:text-foreground"
                                      }
                                    >
                                      <span className="text-foreground">{m.id}</span>
                                      <span> — {m.name}</span>
                                      <span>
                                        {" "}
                                        ({formatPricePerM(m.prompt_price_per_m)} /{" "}
                                        {formatPricePerM(m.completion_price_per_m)} per M ·{" "}
                                        {(m.input_modalities ?? []).join(", ") || "text"})
                                      </span>
                                    </button>
                                  ))}
                                  {editor.modelOptions && (editor.modelOptions.models ?? []).length === 0 && !editor.modelOptions.unavailable ? (
                                    <p className="text-muted-foreground">No matching models — refine the search.</p>
                                  ) : null}
                                </div>
                                <div className="flex items-center gap-2">
                                  <p>
                                    Selected:{" "}
                                    <span className="text-foreground">{editor.selectedModel ?? "none"}</span>
                                  </p>
                                  {(a.overridden ?? []).includes("model") ? (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setEditorField("selectedModel", null);
                                        setEditorField("modelChanged", true);
                                      }}
                                      className="border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground"
                                    >
                                      Use default (clear override)
                                    </button>
                                  ) : null}
                                </div>
                              </>
                            )}
                          </div>
                        ) : (
                          <p className="text-muted-foreground">
                            Deterministic node — no model call, so no model picker.
                          </p>
                        )}

                        {a.prompt_key ? (
                          <div className="flex flex-col gap-1 border border-border p-2">
                            <p className="text-muted-foreground">
                              Prompt: {a.prompt_key} · version {editor.promptMeta?.prompt_version ?? a.prompt_version ?? "…"}
                              {editor.promptMeta?.has_override ?? a.has_prompt_override ? (
                                <span className="ml-1 border border-primary px-1 text-primary">overridden</span>
                              ) : (
                                <span className="ml-1 border border-border px-1">built-in</span>
                              )}
                            </p>
                            <p className="text-muted-foreground">
                              An override changes the effective prompt version — calibration compares like with
                              like, so an overridden verdict flags as uncalibrated until re-pinned.
                            </p>
                            <label className="flex items-start gap-2 text-muted-foreground">
                              <input
                                type="checkbox"
                                checked={editor.promptToggle}
                                onChange={(e) => setEditorField("promptToggle", e.target.checked)}
                              />
                              <span>Override the built-in prompt</span>
                            </label>
                            {editor.promptToggle ? (
                              <textarea
                                value={editor.promptText}
                                onChange={(e) => setEditorField("promptText", e.target.value)}
                                rows={4}
                                className="w-full border border-border bg-background px-1 py-0.5 text-foreground"
                                placeholder="Replacement prompt (plain text — sent as-is, never executed)"
                                aria-label="Prompt override"
                              />
                            ) : null}
                            {(editor.promptMeta?.has_override ?? a.has_prompt_override) ? (
                              <div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditorField("promptClear", true);
                                    setEditorField("promptToggle", false);
                                    setEditorField("promptText", "");
                                  }}
                                  className="border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground"
                                >
                                  Use built-in (clear override)
                                </button>
                              </div>
                            ) : null}
                          </div>
                        ) : null}

                        <div className="flex flex-wrap gap-2">
                          <label className="flex flex-col gap-1 text-muted-foreground">
                            Temperature (default)
                            <input
                              type="number"
                              step="0.1"
                              min="0"
                              max="2"
                              value={editor.temperature}
                              onChange={(e) => setEditorField("temperature", e.target.value)}
                              className="w-28 border border-border bg-background px-1 py-0.5 text-foreground"
                              placeholder="default"
                            />
                          </label>
                          <label className="flex flex-col gap-1 text-muted-foreground">
                            Max tokens (default)
                            <input
                              type="number"
                              step="1"
                              min="1"
                              value={editor.maxTokens}
                              onChange={(e) => setEditorField("maxTokens", e.target.value)}
                              className="w-28 border border-border bg-background px-1 py-0.5 text-foreground"
                              placeholder="default"
                            />
                          </label>
                          <label className="flex flex-col gap-1 text-muted-foreground">
                            Cap $
                            <input
                              type="number"
                              value={editor.capValue}
                              onChange={(e) => setEditorField("capValue", e.target.value)}
                              className="w-28 border border-border bg-background px-1 py-0.5 text-foreground"
                              placeholder="Cap $"
                            />
                          </label>
                        </div>

                        <label className="flex items-start gap-2 text-muted-foreground">
                          <input
                            type="checkbox"
                            checked={editor.enabled}
                            onChange={(e) => setEditorField("enabled", e.target.checked)}
                          />
                          <span>
                            Enabled — when off, skips this node&apos;s model call. The node still records that it
                            was skipped (never a silent skip).
                          </span>
                        </label>

                        <label className="flex flex-col gap-1 text-muted-foreground">
                          Cost-impact note (required)
                          <input
                            type="text"
                            value={editor.noteValue}
                            onChange={(e) => setEditorField("noteValue", e.target.value)}
                            className="w-full border border-border bg-background px-1 py-0.5 text-foreground"
                            placeholder="Cost-impact note"
                          />
                        </label>

                        <div className="flex gap-2">
                          <button
                            type="button"
                            disabled={pending}
                            onClick={() => void handleSave(a)}
                            className="bg-primary px-2 py-0.5 text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
                          >
                            {pending ? "Saving..." : "Save"}
                          </button>
                          <button
                            type="button"
                            disabled={pending}
                            onClick={closeEditor}
                            className="text-muted-foreground hover:text-foreground disabled:opacity-40"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
