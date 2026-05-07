-- 003_rls_enable.sql
-- Phase 1 step 3: enforce tenant isolation with RLS.

-- 0) Safety defaults
DO $$
BEGIN
    IF current_setting('app.current_tenant', true) IS NULL THEN
        PERFORM set_config('app.current_tenant', '00000000-0000-0000-0000-000000000000', false);
    END IF;
END $$;

-- 1) NOT NULL enforcement
ALTER TABLE IF EXISTS world.world_facts ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.world_nodes ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.world_edges ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.world_events ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.claims ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.claim_citations ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.doc_sources ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.doc_versions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.doc_fragments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.conflict_sets ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.conflict_members ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.trust_assessments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS world.quality_reports ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS public.macro_history ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS public.agents_snapshot ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE IF EXISTS public.run_records ALTER COLUMN tenant_id SET NOT NULL;

-- 2) Tenant indexes
CREATE INDEX IF NOT EXISTS idx_world_facts_tenant ON world.world_facts (tenant_id);
CREATE INDEX IF NOT EXISTS idx_world_nodes_tenant ON world.world_nodes (tenant_id);
CREATE INDEX IF NOT EXISTS idx_world_edges_tenant ON world.world_edges (tenant_id);
CREATE INDEX IF NOT EXISTS idx_world_events_tenant ON world.world_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_claims_tenant ON world.claims (tenant_id);
CREATE INDEX IF NOT EXISTS idx_claim_citations_tenant ON world.claim_citations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_doc_sources_tenant ON world.doc_sources (tenant_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_tenant ON world.doc_versions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_doc_fragments_tenant ON world.doc_fragments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_conflict_sets_tenant ON world.conflict_sets (tenant_id);
CREATE INDEX IF NOT EXISTS idx_conflict_members_tenant ON world.conflict_members (tenant_id);
CREATE INDEX IF NOT EXISTS idx_trust_assessments_tenant ON world.trust_assessments (tenant_id);
CREATE INDEX IF NOT EXISTS idx_quality_reports_tenant ON world.quality_reports (tenant_id);
CREATE INDEX IF NOT EXISTS idx_macro_history_tenant ON public.macro_history (tenant_id);
CREATE INDEX IF NOT EXISTS idx_agents_snapshot_tenant ON public.agents_snapshot (tenant_id);
CREATE INDEX IF NOT EXISTS idx_run_records_tenant ON public.run_records (tenant_id);

-- 3) Enable RLS
ALTER TABLE world.world_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.world_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.world_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.world_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.claim_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.doc_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.doc_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.doc_fragments ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.conflict_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.conflict_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.trust_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE world.quality_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.macro_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.run_records ENABLE ROW LEVEL SECURITY;

ALTER TABLE world.world_facts FORCE ROW LEVEL SECURITY;
ALTER TABLE world.world_nodes FORCE ROW LEVEL SECURITY;
ALTER TABLE world.world_edges FORCE ROW LEVEL SECURITY;
ALTER TABLE world.world_events FORCE ROW LEVEL SECURITY;
ALTER TABLE world.claims FORCE ROW LEVEL SECURITY;
ALTER TABLE world.claim_citations FORCE ROW LEVEL SECURITY;
ALTER TABLE world.doc_sources FORCE ROW LEVEL SECURITY;
ALTER TABLE world.doc_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE world.doc_fragments FORCE ROW LEVEL SECURITY;
ALTER TABLE world.conflict_sets FORCE ROW LEVEL SECURITY;
ALTER TABLE world.conflict_members FORCE ROW LEVEL SECURITY;
ALTER TABLE world.trust_assessments FORCE ROW LEVEL SECURITY;
ALTER TABLE world.quality_reports FORCE ROW LEVEL SECURITY;
ALTER TABLE public.macro_history FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agents_snapshot FORCE ROW LEVEL SECURITY;
ALTER TABLE public.run_records FORCE ROW LEVEL SECURITY;

-- 4) Shared policy template
-- Keep policy names unique per table to avoid collisions.

CREATE POLICY tenant_access_world_facts ON world.world_facts
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_world_nodes ON world.world_nodes
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_world_edges ON world.world_edges
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_world_events ON world.world_events
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_claims ON world.claims
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_claim_citations ON world.claim_citations
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_doc_sources ON world.doc_sources
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_doc_versions ON world.doc_versions
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_doc_fragments ON world.doc_fragments
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_conflict_sets ON world.conflict_sets
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_conflict_members ON world.conflict_members
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_trust_assessments ON world.trust_assessments
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_quality_reports ON world.quality_reports
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_macro_history ON public.macro_history
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_agents_snapshot ON public.agents_snapshot
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
CREATE POLICY tenant_access_run_records ON public.run_records
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
