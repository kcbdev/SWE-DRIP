"use client";

import { useState } from "react";

import { canEditStyles, type StylesRepo } from "@/lib/research";

export interface StylesManagerProps {
  repo: StylesRepo | null;
  role: string | undefined;
  error: string | null;
  acting: boolean;
  lastAffected: string[] | null;
  onCreate: (name: string, graphic_definition: string) => void;
  onUpdate: (oldName: string, patch: { name?: string; graphic_definition?: string }) => void;
}

export function StylesManager({ repo, role, error, acting, lastAffected, onCreate, onUpdate }: StylesManagerProps) {
  const editable = canEditStyles(role);
  const [name, setName] = useState("");
  const [definition, setDefinition] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDefinition, setEditDefinition] = useState("");
  const [confirmKey, setConfirmKey] = useState<string | null>(null);

  const startEdit = (styleName: string, styleDefinition: string) => {
    setEditing(styleName);
    setEditName(styleName);
    setEditDefinition(styleDefinition);
    setConfirmKey(null);
  };

  return (
    <div className="border border-border p-4">
      <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
        Style repository{repo ? ` · v${repo.version}` : ""}
      </p>
      {error ? <p className="mt-2 font-mono text-xs text-destructive">{error}</p> : null}
      {lastAffected !== null ? (
        <p className="mt-2 font-mono text-xs text-muted-foreground">
          {lastAffected.length === 0
            ? "Revalidation: no contracts stranded."
            : `Revalidation: stranded contracts — ${lastAffected.join(", ")}`}
        </p>
      ) : null}
      {!repo ? (
        <p className="mt-2 font-mono text-xs text-muted-foreground">Style repository unavailable.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {repo.styles.map((style) => (
            <li key={style.name} className="border border-border p-2">
              <p className="font-mono text-xs">
                <span className="text-primary">{style.name}</span>
                <span className="text-muted-foreground"> — {style.graphic_definition}</span>
              </p>
              {editable ? (
                editing === style.name ? (
                  <div className="mt-2 flex flex-col gap-2">
                    <input
                      aria-label={`New name for ${style.name}`}
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
                    />
                    <input
                      aria-label={`New definition for ${style.name}`}
                      value={editDefinition}
                      onChange={(e) => setEditDefinition(e.target.value)}
                      className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
                    />
                    {confirmKey === style.name ? (
                      <span className="flex items-center gap-2">
                        <span className="font-mono text-xs">Save these edits?</span>
                        <button
                          type="button"
                          disabled={acting}
                          onClick={() => {
                            setConfirmKey(null);
                            setEditing(null);
                            onUpdate(style.name, { name: editName, graphic_definition: editDefinition });
                          }}
                          className="border border-primary px-2 py-0.5 font-mono text-xs text-primary"
                        >
                          Confirm save
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmKey(null)}
                          className="border border-border px-2 py-0.5 font-mono text-xs"
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      <span className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setConfirmKey(style.name)}
                          className="border border-primary px-2 py-0.5 font-mono text-xs text-primary"
                        >
                          Save…
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditing(null)}
                          className="border border-border px-2 py-0.5 font-mono text-xs"
                        >
                          Cancel
                        </button>
                      </span>
                    )}
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => startEdit(style.name, style.graphic_definition)}
                    className="mt-1 border border-border px-2 py-0.5 font-mono text-xs"
                  >
                    Edit…
                  </button>
                )
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {editable && repo ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <input
            aria-label="New style name"
            placeholder="style name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
          />
          <input
            aria-label="New style definition"
            placeholder="graphic definition"
            value={definition}
            onChange={(e) => setDefinition(e.target.value)}
            className="border border-border bg-background px-2 py-1 font-mono text-xs outline-none focus:border-primary"
          />
          {confirmKey === "__create" ? (
            <span className="flex items-center gap-2">
              <span className="font-mono text-xs">Create this style?</span>
              <button
                type="button"
                disabled={acting}
                onClick={() => {
                  setConfirmKey(null);
                  onCreate(name.trim(), definition);
                  setName("");
                  setDefinition("");
                }}
                className="border border-primary px-2 py-0.5 font-mono text-xs text-primary"
              >
                Confirm create
              </button>
              <button
                type="button"
                onClick={() => setConfirmKey(null)}
                className="border border-border px-2 py-0.5 font-mono text-xs"
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              type="button"
              disabled={acting || !name.trim() || !definition.trim()}
              onClick={() => setConfirmKey("__create")}
              className="border border-primary px-3 py-1 font-mono text-xs text-primary disabled:opacity-40"
            >
              Create…
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}
