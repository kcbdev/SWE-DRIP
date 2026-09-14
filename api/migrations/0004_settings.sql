-- 0004_settings.sql — key/value runtime config store (settings C1, C5).
--
-- The pipeline reads HITL flags from this table at run start (pipeline/settings.py).
-- Brand-lock constants are surfaced in the UI and consumed by generation nodes.
-- Integrations status reads env vars directly — no table row needed.

CREATE TABLE IF NOT EXISTS settings (
    key        VARCHAR(64) PRIMARY KEY,
    value_json JSONB        NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Seed default HITL flags (contract_approval, aesthetic_qc, publish_gate ON).
INSERT INTO settings (key, value_json) VALUES
    ('hitl', '{"trend_research":false,"contract_approval":true,"listing_copy":false,"design_spec":false,"art_render":false,"placement":false,"aesthetic_qc":true,"technical_qc":false,"fw_create":false,"publish_gate":true,"shelf":false}'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- Seed default brand-lock constants.
INSERT INTO settings (key, value_json) VALUES
    ('brand', '{"palette":{"void_black":"#0D0D0D","terminal_green":"#00FF41"},"typeface":"JetBrains Mono","forbidden":["gradients","shadows","rounded_pills","pastels"]}'::jsonb)
ON CONFLICT (key) DO NOTHING;
