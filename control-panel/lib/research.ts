/** Collection-research UI types + pure helpers + API calls (PBI-052; data via the PBI-049/050/055/056 APIs). */

import { ApiError, apiFetch } from "./api";

export const RESEARCH_ORDER = [
  "inspiration_review",
  "style_synthesis",
  "mood_board",
  "contract_draft",
  "collection_gate",
] as const;

export type ResearchNodeName = (typeof RESEARCH_ORDER)[number];

export interface InspirationAsset {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  source_url: string;
  note: string;
  actor_user_id: string;
  created_at: string;
}

export interface InspirationRef {
  url: string;
  note: string;
}

export interface InspirationListing {
  assets: InspirationAsset[];
  refs: InspirationRef[];
}

export interface ResearchBoard {
  file_ref: string;
  model_used?: string;
  width?: number;
  height?: number;
  board_version: number;
}

export interface ResearchRunRow {
  id: string;
  collection_slug: string | null;
  status: string;
  current_stage: string;
  board_version: number | null;
  diversity_flags: string[];
  started_at: string | null;
  updated_at: string | null;
}

export interface ResearchNodePanel {
  node: string;
  reached: boolean;
  state: unknown;
  at: string | null;
}

export interface ResearchDetail extends ResearchRunRow {
  board: ResearchBoard | null;
  draft_contract: Record<string, unknown> | null;
  gate_decision: Record<string, unknown> | null;
  nodes: ResearchNodePanel[];
  errors: string[];
}

export interface ResearchGatePayload {
  draft: Record<string, unknown>;
  board: { file_ref?: string; board_version?: number };
  diversity_flags: string[];
}

export interface ResearchGateItem {
  id: number;
  run_id: string;
  node: string;
  status: string;
  payload: ResearchGatePayload;
  entity_ref: { type: string; id: string | null; label: string };
  waiting_since: string | null;
}

export interface StyleEntry {
  name: string;
  graphic_definition: string;
}

export interface StylesRepo {
  version: number;
  styles: StyleEntry[];
}

export interface RotationQueue {
  next_candidate: string | null;
  drafts: number;
  actives: number;
}

export interface ResearchLogRow {
  node: string;
  level: string;
  message: string;
  detail: Record<string, unknown>;
  ts: string;
}

/** Display stage labels (the API's vocabulary, humanized in one place). */
export function stageLabel(stage: string): string {
  const labels: Record<string, string> = {
    started: "Started",
    synthesizing: "Synthesizing",
    board_rendering: "Board rendering",
    drafting: "Drafting",
    awaiting_approval: "Awaiting approval",
    complete: "Complete",
    failed: "Failed",
  };
  return labels[stage] ?? stage;
}

/** Gate decisions reuse the lifecycle discipline: admin or operator. */
export function canDecideResearch(role: string | undefined): boolean {
  return role === "admin" || role === "operator";
}

/** Style repo writes are admin-only (audited founder gate). */
export function canEditStyles(role: string | undefined): boolean {
  return role === "admin";
}

/** Inspiration writes are admin-only (audited curator gate). */
export function canCurate(role: string | undefined): boolean {
  return role === "admin";
}

/** Textarea (one value per line) → clean string list for descriptors/avoid. */
export function parseLines(raw: string): string[] {
  return raw
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

/**
 * Board image URL: absolute API origin (PBI-059 fix).
 *
 * Relative `/api/…` URLs resolve against the *panel* host, which serves no
 * API routes in production (no Traefik path routing) — images 404 while
 * JSON (fetched via API_BASE) works. Absolute URLs ride the same
 * cross-subdomain session cookie the API calls already use.
 */
export function boardImageUrl(apiBase: string, slug: string, ref: string): string {
  return `${apiBase}/api/collections/${slug}/board/${ref}`;
}

/** Same-origin inspiration asset URL (absolute API origin, see above). */
export function inspirationFileUrl(apiBase: string, slug: string, assetId: string): string {
  return `${apiBase}/api/collections/${slug}/inspiration/${assetId}/file`;
}

/**
 * Servable board ref from a run board's file_ref (mirrors the pipeline
 * board_display_ref: basename across separators, null when absent).
 */
export function boardDisplayRef(fileRef: unknown): string | null {
  if (typeof fileRef !== "string" || !fileRef.trim()) return null;
  const name = fileRef.replace(/\\/g, "/").split("/").pop()?.trim();
  return name || null;
}

// ------------------------------------------------------------------ API

export async function getInspiration(slug: string): Promise<InspirationListing> {
  return apiFetch<InspirationListing>(`/api/collections/${slug}/inspiration`);
}

export async function getRotation(): Promise<RotationQueue> {
  return apiFetch<RotationQueue>(`/api/collections/rotation`);
}

export async function listResearchRuns(): Promise<{ items: ResearchRunRow[] }> {
  return apiFetch<{ items: ResearchRunRow[] }>(`/api/research/runs`);
}

export async function getResearchRun(runId: string): Promise<ResearchDetail> {
  return apiFetch<ResearchDetail>(`/api/research/runs/${runId}`);
}

export async function getResearchLogs(runId: string): Promise<{ items: ResearchLogRow[] }> {
  return apiFetch<{ items: ResearchLogRow[] }>(`/api/research/runs/${runId}/logs?limit=500`);
}

export async function startResearchRun(slug: string): Promise<ResearchRunRow> {
  return apiFetch<ResearchRunRow>(`/api/research/runs`, {
    method: "POST",
    body: JSON.stringify({ collection_slug: slug }),
  });
}

export async function listResearchApprovals(): Promise<{ items: ResearchGateItem[] }> {
  return apiFetch<{ items: ResearchGateItem[] }>(`/api/research/approvals`);
}

export async function decideResearchApproval(
  itemId: number,
  action: "approve" | "reject" | "regenerate",
  note?: string,
  contract?: Record<string, unknown>,
): Promise<unknown> {
  return apiFetch<unknown>(`/api/research/approvals/${itemId}/decision`, {
    method: "POST",
    body: JSON.stringify({
      action,
      note: note || null,
      selection: contract ? { contract } : null,
    }),
  });
}

export async function getStyles(): Promise<StylesRepo> {
  return apiFetch<StylesRepo>(`/api/styles`);
}

export async function createStyle(
  name: string,
  graphic_definition: string,
  expected_version: number,
): Promise<StylesRepo & { affected_contracts: string[] }> {
  return apiFetch(`/api/styles`, {
    method: "POST",
    body: JSON.stringify({ name, graphic_definition, expected_version }),
  });
}

export async function updateStyle(
  name: string,
  expected_version: number,
  patch: { name?: string; graphic_definition?: string },
): Promise<StylesRepo & { affected_contracts: string[] }> {
  return apiFetch(`/api/styles/${name}`, {
    method: "PATCH",
    body: JSON.stringify({ ...patch, expected_version }),
  });
}

/**
 * Multipart asset upload (raw fetch — apiFetch forces a JSON content type,
 * which would corrupt the multipart body). The file input gates this call:
 * the UI never invokes it without a File (server would 400 regardless).
 */
export async function uploadInspirationAsset(
  apiBase: string,
  slug: string,
  file: File,
  note: string,
  sourceUrl: string,
): Promise<InspirationAsset> {
  const form = new FormData();
  form.append("file", file);
  if (note) form.append("note", note);
  if (sourceUrl) form.append("source_url", sourceUrl);
  const response = await fetch(`${apiBase}/api/collections/${slug}/inspiration`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return (await response.json()) as InspirationAsset;
}

export async function addInspirationLink(slug: string, url: string, note: string): Promise<InspirationRef> {
  return apiFetch<InspirationRef>(`/api/collections/${slug}/inspiration`, {
    method: "POST",
    body: JSON.stringify({ url, note }),
  });
}

export async function deleteInspirationAsset(slug: string, assetId: string): Promise<unknown> {
  return apiFetch<unknown>(`/api/collections/${slug}/inspiration/${assetId}`, {
    method: "DELETE",
  });
}
