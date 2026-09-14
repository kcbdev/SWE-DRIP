"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiFetch } from "@/lib/api";
import { creationErrors } from "@/lib/collections";

/** Minimal 1:1 create form: id + theme + style; the rest edits via PATCH later. */
export default function NewCollectionPage() {
  const router = useRouter();
  const [collectionId, setCollectionId] = useState("");
  const [theme, setTheme] = useState("");
  const [style, setStyle] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [serverError, setServerError] = useState<string | null>(null);

  const submit = async () => {
    const local = creationErrors({ collection_id: collectionId, theme });
    if (!style.trim()) local.push("style_archetype is required");
    setErrors(local);
    if (local.length > 0) return;
    setServerError(null);
    try {
      const created = await apiFetch<{ id: string }>("/api/collections", {
        method: "POST",
        body: JSON.stringify({
          collection_id: collectionId,
          theme,
          style_archetype: style,
          illustration_rules: { line_weight: null, palette: [], no_mixed_styles: true },
          garment_colorways: [],
          placement_templates: [],
          kpi_thresholds: {},
          created_by: "ui",
          created_at: new Date().toISOString(),
        }),
      });
      router.push(`/collections/${created.id}`);
    } catch (err) {
      setServerError(err instanceof Error ? err.message : "create failed");
    }
  };

  return (
    <AppShell>
      <div className="flex max-w-md flex-col gap-3">
        <h1 className="font-sans text-2xl font-semibold">New collection</h1>
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          collection_id (kebab-case)
          <input
            value={collectionId}
            onChange={(e) => setCollectionId(e.target.value)}
            className="mt-1 block w-full border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          theme
          <input
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            className="mt-1 block w-full border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
        <label className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          style_archetype
          <input
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className="mt-1 block w-full border border-border bg-background px-2 py-1 text-foreground outline-none focus:border-primary"
          />
        </label>
        {errors.map((e) => (
          <p key={e} className="font-mono text-xs text-destructive">
            {e}
          </p>
        ))}
        {serverError ? <p className="font-mono text-xs text-destructive">{serverError}</p> : null}
        <button
          type="button"
          onClick={() => void submit()}
          className="border border-primary px-3 py-2 font-mono text-xs text-primary"
        >
          Create draft
        </button>
      </div>
    </AppShell>
  );
}
