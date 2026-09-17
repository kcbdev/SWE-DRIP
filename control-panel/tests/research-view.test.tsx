// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ResearchView } from "../components/collections/research-view";
import { StylesManager } from "../components/collections/styles-manager";
import type { CollectionContract } from "../lib/collections";
import type {
  InspirationListing,
  ResearchDetail,
  ResearchGateItem,
  ResearchRunRow,
  RotationQueue,
} from "../lib/research";

afterEach(cleanup);

function contract(overrides: Partial<CollectionContract> = {}): CollectionContract {
  return {
    collection_id: "vibe",
    theme: "Vibe",
    status: "draft",
    style_archetype: "mono-log",
    illustration_rules: { line_weight: null, palette: ["#0D0D0D"], no_mixed_styles: true },
    garment_colorways: [],
    placement_templates: [],
    product_count_target: null,
    lifecycle_days: null,
    kpi_thresholds: { min_units: null, min_conversion: null, eval_window_days: null },
    created_by: "u-9",
    created_at: "2026-09-16T00:00:00+00:00",
    approved_at: null,
    retired_at: null,
    style_descriptors: ["mono-line"],
    mood_board: ["board.png"],
    inspiration_refs: [],
    avoid: ["photorealism"],
    board_version: 1,
    ...overrides,
  };
}

const inspiration: InspirationListing = {
  assets: [
    {
      id: "a1", filename: "a1.png", content_type: "image/png", size_bytes: 10,
      source_url: "", note: "line quality", actor_user_id: "u-9",
      created_at: "2026-09-16T00:00:00+00:00",
    },
  ],
  refs: [{ url: "https://example.com/board", note: "ref note" }],
};

const rotation: RotationQueue = { next_candidate: "vibe", drafts: 1, actives: 0 };

const runs: ResearchRunRow[] = [
  {
    id: "rsch_1", collection_slug: "vibe", status: "awaiting_approval",
    current_stage: "awaiting_approval", board_version: 1, diversity_flags: ["near-duplicate"],
    started_at: null, updated_at: null,
  },
];

function selectedRun(overrides: Partial<ResearchDetail> = {}): ResearchDetail {
  return {
    ...runs[0],
    board: { file_ref: "board.png", board_version: 1 },
    draft_contract: { collection_id: "vibe" },
    gate_decision: null,
    nodes: [
      { node: "inspiration_review", reached: true, state: {}, at: null },
      { node: "style_synthesis", reached: true, state: {}, at: null },
      { node: "mood_board", reached: true, state: {}, at: null },
      { node: "contract_draft", reached: true, state: {}, at: null },
      { node: "collection_gate", reached: false, state: null, at: null },
    ],
    errors: [],
    ...overrides,
  };
}

function gate(): ResearchGateItem {
  return {
    id: 7,
    run_id: "rsch_1",
    node: "collection_gate",
    status: "pending",
    payload: {
      draft: { collection_id: "vibe", theme: "Vibe" },
      board: { file_ref: "board.png", board_version: 1 },
      diversity_flags: [],
    },
    entity_ref: { type: "research_gate", id: "vibe", label: "Vibe" },
    waiting_since: null,
  };
}

function baseProps(overrides: Record<string, unknown> = {}) {
  return {
    slug: "vibe",
    role: "admin",
    contract: contract(),
    inspiration,
    rotation,
    runs: [],
    selectedRun: null,
    logs: [],
    logTab: "state" as const,
    onLogTab: () => {},
    gate: null,
    error: null,
    acting: false,
    onStartRun: () => {},
    onSelectRun: () => {},
    onDecideGate: () => {},
    onUpload: () => {},
    onAddLink: () => {},
    onDeleteAsset: () => {},
    onApproveDraft: () => {},
    ...overrides,
  };
}

describe("ResearchView", () => {
  it("renders board image rows from the contract refs", () => {
    render(<ResearchView {...baseProps()} />);
    expect(screen.getByAltText("Mood board board.png")).toBeTruthy();
    expect(screen.getByText(/board v1/)).toBeTruthy();
  });

  it("shows the empty-board hint when no refs exist", () => {
    render(<ResearchView {...baseProps({ contract: contract({ mood_board: [] }) })} />);
    expect(screen.getByText(/No board yet/)).toBeTruthy();
  });

  it("upload without a file is impossible via the UI", () => {
    const onUpload = vi.fn();
    render(<ResearchView {...baseProps({ onUpload })} />);
    const upload = screen.getByText("Upload") as HTMLButtonElement;
    expect(upload.disabled).toBe(true);
    fireEvent.click(upload);
    expect(onUpload).not.toHaveBeenCalled();
  });

  it("gate approve requires confirmation", () => {
    const onDecideGate = vi.fn();
    render(<ResearchView {...baseProps({ gate: gate(), onDecideGate })} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onDecideGate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm approve"));
    expect(onDecideGate).toHaveBeenCalledWith("approve", "");
  });

  it("diversity flags render their reasons", () => {
    render(<ResearchView {...baseProps({ runs, selectedRun: selectedRun() })} />);
    expect(screen.getByText("near-duplicate")).toBeTruthy();
  });

  it("viewer sees boards and flags but no edit controls", () => {
    render(
      <ResearchView
        {...baseProps({ role: "viewer", runs, selectedRun: selectedRun(), gate: gate() })}
      />,
    );
    expect(screen.getByAltText("Mood board board.png")).toBeTruthy();
    expect(screen.getByText("near-duplicate")).toBeTruthy();
    expect(screen.queryByText("Upload")).toBeNull();
    expect(screen.queryByText("Add link")).toBeNull();
    expect(screen.queryByText("Delete…")).toBeNull();
    expect(screen.queryByText("Start research run")).toBeNull();
    expect(screen.queryByText("Approve")).toBeNull();
    expect(screen.queryByText("Reject")).toBeNull();
  });

  it("operator sees gate buttons but no curation forms", () => {
    render(
      <ResearchView
        {...baseProps({ role: "operator", gate: gate() })}
      />,
    );
    expect(screen.getByText("Approve")).toBeTruthy();
    expect(screen.queryByText("Upload")).toBeNull();
    expect(screen.queryByText("Start research run")).toBeNull();
  });

  it("completed run on a draft offers activate-to-active with confirm", () => {
    const onApproveDraft = vi.fn();
    render(
      <ResearchView
        {...baseProps({
          selectedRun: selectedRun({ status: "complete", current_stage: "complete" }),
          onApproveDraft,
        })}
      />,
    );
    fireEvent.click(screen.getByText("Approve to active"));
    expect(onApproveDraft).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm activate"));
    expect(onApproveDraft).toHaveBeenCalledTimes(1);
  });

  it("no activate offer once the draft is active", () => {
    render(
      <ResearchView
        {...baseProps({
          contract: contract({ status: "active" }),
          selectedRun: selectedRun({ status: "complete", current_stage: "complete" }),
        })}
      />,
    );
    expect(screen.queryByText("Approve to active")).toBeNull();
  });
});

describe("StylesManager", () => {
  const repo = {
    version: 3,
    styles: [{ name: "mono-log", graphic_definition: "Lines." }],
  };
  const base = {
    repo,
    role: "admin",
    error: null,
    acting: false,
    lastAffected: null as string[] | null,
    onCreate: () => {},
    onUpdate: () => {},
  };

  it("lists styles with version", () => {
    render(<StylesManager {...base} />);
    expect(screen.getByText("mono-log")).toBeTruthy();
    expect(screen.getByText(/v3/)).toBeTruthy();
  });

  it("create requires confirmation and reports affected contracts", () => {
    const onCreate = vi.fn();
    const { rerender } = render(<StylesManager {...base} onCreate={onCreate} />);
    fireEvent.change(screen.getByLabelText("New style name"), { target: { value: "glitch" } });
    fireEvent.change(screen.getByLabelText("New style definition"), { target: { value: "Bars." } });
    fireEvent.click(screen.getByText("Create…"));
    expect(onCreate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm create"));
    expect(onCreate).toHaveBeenCalledWith("glitch", "Bars.");
    rerender(<StylesManager {...base} lastAffected={["vibe"]} />);
    expect(screen.getByText(/stranded contracts — vibe/)).toBeTruthy();
  });

  it("edit flow confirms before saving", () => {
    const onUpdate = vi.fn();
    render(<StylesManager {...base} onUpdate={onUpdate} />);
    fireEvent.click(screen.getByText("Edit…"));
    fireEvent.change(screen.getByLabelText("New definition for mono-log"), {
      target: { value: "New words." },
    });
    fireEvent.click(screen.getByText("Save…"));
    expect(onUpdate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm save"));
    expect(onUpdate).toHaveBeenCalledWith("mono-log", {
      name: "mono-log",
      graphic_definition: "New words.",
    });
  });

  it("viewer sees the list but no edit controls", () => {
    render(<StylesManager {...base} role="viewer" />);
    expect(screen.getByText("mono-log")).toBeTruthy();
    expect(screen.queryByText("Edit…")).toBeNull();
    expect(screen.queryByText("Create…")).toBeNull();
  });
});
