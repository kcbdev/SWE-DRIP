"""Collection lineage + diversity checks (spec C6, PBI-051).

A lineage is built from active/retired contracts (archetypes, palettes,
style descriptors as motif proxy) and serves two readers: synthesis
(negative context via :func:`format_avoid`) and the draft gate
(:func:`diversity_flags`, which flag near-duplicates with reasons instead
of approving silently). Pure functions over contract dicts — the caller
(listing, trigger, UI) supplies the contracts; no store access here.
"""

from __future__ import annotations

from typing import Any


def build_lineage(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize past collections into archetypes/palettes/motifs."""
    archetypes: list[str] = []
    palettes: list[str] = []
    motifs: list[str] = []
    seen: set[str] = set()
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        slug = str(contract.get("collection_id") or "")
        if slug:
            seen.add(slug)
        archetype = contract.get("style_archetype")
        if isinstance(archetype, str) and archetype and archetype not in archetypes:
            archetypes.append(archetype)
        rules = contract.get("illustration_rules") or {}
        palette = rules.get("palette") or []
        for color in palette:
            if isinstance(color, str) and color not in palettes:
                palettes.append(color)
        for descriptor in contract.get("style_descriptors") or []:
            if isinstance(descriptor, str) and descriptor and descriptor not in motifs:
                motifs.append(descriptor)
    return {
        "collections": sorted(seen),
        "archetypes": archetypes,
        "palettes": palettes,
        "motifs": motifs,
    }


def format_avoid(lineage: dict[str, Any]) -> list[str]:
    """Negative context lines for synthesis (what not to repeat)."""
    lines: list[str] = []
    for archetype in lineage.get("archetypes") or []:
        lines.append(f"style {archetype!r} is taken — differentiate, do not repeat")
    if lineage.get("palettes"):
        lines.append(f"palettes already in use: {', '.join(lineage['palettes'])}")
    for motif in lineage.get("motifs") or []:
        lines.append(f"motif {motif!r} is taken — differentiate, do not repeat")
    return lines


def build_research_inputs(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    """Seed dict for a research run's initial state (used by the run trigger).

    Bundles the lineage record (for the draft gate's diversity check) with
    the negative-context lines (for synthesis ``avoid``) so a trigger built
    from the collections store wires both readers in one call.
    """
    lineage = build_lineage(contracts)
    return {"lineage": lineage, "avoid": format_avoid(lineage)}


def diversity_flags(candidate: dict[str, Any], lineage: dict[str, Any]) -> list[str]:
    """Reasons a draft candidate looks like a duplicate (empty = distinct).

    A shared archetype alone is a flag only with overlapping palette or
    motifs: archetype reuse across seasons is legitimate when the expression
    differs.
    """
    flags: list[str] = []
    if not isinstance(candidate, dict):
        return ["candidate must be a mapping"]
    archetype = candidate.get("style_archetype")
    if archetype in (lineage.get("archetypes") or []):
        palette = set((candidate.get("illustration_rules") or {}).get("palette") or [])
        motifs = {m for m in (candidate.get("style_descriptors") or []) if isinstance(m, str)}
        shared_palette = palette & set(lineage.get("palettes") or [])
        shared_motifs = motifs & set(lineage.get("motifs") or [])
        if shared_palette or shared_motifs:
            reasons = []
            if shared_palette:
                reasons.append(f"palette overlap: {sorted(shared_palette)!r}")
            if shared_motifs:
                reasons.append(f"motif overlap: {sorted(shared_motifs)!r}")
            flags.append(f"near-duplicate of a past {archetype!r} collection ({'; '.join(reasons)})")
    return flags
