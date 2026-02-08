-- 003_rls_disable_rollback.sql
-- Emergency rollback for 003_rls_enable.sql.

DROP POLICY IF EXISTS tenant_access_world_facts ON world.world_facts;
DROP POLICY IF EXISTS tenant_access_world_nodes ON world.world_nodes;
DROP POLICY IF EXISTS tenant_access_world_edges ON world.world_edges;
DROP POLICY IF EXISTS tenant_access_world_events ON world.world_events;
DROP POLICY IF EXISTS tenant_access_claims ON world.claims;
DROP POLICY IF EXISTS tenant_access_claim_citations ON world.claim_citations;
DROP POLICY IF EXISTS tenant_access_doc_sources ON world.doc_sources;
DROP POLICY IF EXISTS tenant_access_doc_versions ON world.doc_versions;
DROP POLICY IF EXISTS tenant_access_doc_fragments ON world.doc_fragments;
DROP POLICY IF EXISTS tenant_access_conflict_sets ON world.conflict_sets;
DROP POLICY IF EXISTS tenant_access_conflict_members ON world.conflict_members;
DROP POLICY IF EXISTS tenant_access_trust_assessments ON world.trust_assessments;
DROP POLICY IF EXISTS tenant_access_quality_reports ON world.quality_reports;
DROP POLICY IF EXISTS tenant_access_macro_history ON public.macro_history;
DROP POLICY IF EXISTS tenant_access_agents_snapshot ON public.agents_snapshot;
DROP POLICY IF EXISTS tenant_access_run_records ON public.run_records;

ALTER TABLE world.world_facts DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.world_nodes DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.world_edges DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.world_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.claims DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.claim_citations DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.doc_sources DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.doc_versions DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.doc_fragments DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.conflict_sets DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.conflict_members DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.trust_assessments DISABLE ROW LEVEL SECURITY;
ALTER TABLE world.quality_reports DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.macro_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents_snapshot DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.run_records DISABLE ROW LEVEL SECURITY;
