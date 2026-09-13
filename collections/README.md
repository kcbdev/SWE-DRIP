# Collection contracts

Runtime collection-contract YAML lives here as `/collections/<slug>.yaml` — the
single source of truth for style, palette, colorways, placement, and KPI
thresholds (Vision doc §5, Data spec §1.1). The YAML store and CRUD API land in
PBI-019; the pipeline reads these files directly and the Control Panel reads them
through the API — no parallel copy (PRD NFR-1).

Empty at PBI-003; populated by the collections PBIs.
