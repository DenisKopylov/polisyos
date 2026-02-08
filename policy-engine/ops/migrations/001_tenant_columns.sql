-- 001_tenant_columns.sql
-- Phase 1 step 1: add tenant columns as nullable to avoid downtime.

ALTER TABLE IF EXISTS world.world_facts ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.world_nodes ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.world_edges ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.world_events ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.claims ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.claim_citations ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.doc_sources ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.doc_versions ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.doc_fragments ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.conflict_sets ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.conflict_members ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.trust_assessments ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS world.quality_reports ADD COLUMN IF NOT EXISTS tenant_id UUID;

ALTER TABLE IF EXISTS public.macro_history ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS public.agents_snapshot ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE IF EXISTS public.run_records ADD COLUMN IF NOT EXISTS tenant_id UUID;
