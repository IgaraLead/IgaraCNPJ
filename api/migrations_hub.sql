-- ============================================================
-- IgaraLead Entity - Hub Integration Migration
-- Adds hub_id and hub_synced_at to usuarios table
-- ============================================================

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS hub_id VARCHAR(36) UNIQUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS hub_synced_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_usuarios_hub_id ON usuarios (hub_id);
