---
plan_id: layer3-gl-legal-mandate-search-engine
title: "GL - Legal/Mandate Search Engine"
type: slice-plan
status: active
created: 2026-06-08
revised: 2026-06-08
slice: GL
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/adr/0175-layer3-grounding-subordination-discipline.md
  - architecture/policy_design_case/layer3_g0_readiness_manifest.json
  - architecture/policy_design_case/layer3_discovery_search_discipline.json
  - architecture/policy_design_case/layer3_engineering_quality_check.json
  - architecture/policy_design_case/layer3_health_metric_ledgers.toml
  - production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb
  - src/polisyos/lex/knowledge/store.py
  - src/polisyos/lex/knowledge/search.py
  - src/polisyos/lex/knowledge/types.py
  - src/polisyos/lex/normpack/legal_authority.py
  - src/polisyos/lex/normpack/applicability_report.py
  - src/polisyos/legal_requirement/
  - src/polisyos/lex/intervention_artifacts.py
  - src/polisyos/runtime/quality/claim_registry.py
  - src/polisyos/runtime/quality/semantic_binding.py
  - src/polisyos/runtime/quality/argument_graph.py
  - src/polisyos/runtime/quality/public_export.py
  - src/polisyos/runtime/quality/invariants.py
  - src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py
  - src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py
  - src/polisyos/runtime/quality/design_axes/value_choice_provenance.py
  - src/polisyos/pdc/_impl/layer2_design_search.py
context_inputs:
  - docs/plans/active/layer3-slices/G1-data-grounding-existing-assets-acquisition.md
  - docs/plans/active/layer3-slices/G2-causal-forecast-search-engine.md
  - docs/plans/active/layer3-slices/G3-analytics-search-engine.md
  - architecture/policy_design_case/layer3_g1_readiness_manifest.json
  - architecture/policy_design_case/layer3_g2_readiness_manifest.json
  - architecture/policy_design_case/layer3_g3_readiness_manifest.json
cells_closed: []
layer_cells_advanced:
  - layer3.legal_mandate_search_adapter
  - layer3.gl_l3_legal_kg_search_route
  - layer3.gl_legal_search_frontier_ledger
  - layer3.gl_search_recall_freshness_gate
  - layer3.gl_l5_calibration_binding
  - layer3.gl_legal_requirement_binding
  - layer3.gl_authority_facet_binding
  - layer3.gl_norm_candidate_binding
  - layer3.gl_threshold_authority_record
  - layer3.gl_mandate_authority_record
  - layer3.gl_temporal_competence_record
  - layer3.gl_amendment_lineage_replay
  - layer3.gl_lex_intervention_map_binding
  - layer3.gl_claim_registry_consumer_gate
  - layer3.gl_argument_graph_readiness_consumer_gate
  - layer3.gl_s6_s7_mandate_consumer_gate
  - layer3.gl_s8_value_choice_consumer_gate
  - layer3.gl_design_constraint_consumer_gate
  - layer3.gl_g4_promotion_gate_consumer_gate
  - layer3.gl_legal_authority_surface
  - layer3.gl_public_export_projection_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_gl_legal_mandate_search_readiness_gate
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# GL - Legal/Mandate Search Engine

## For agentic workers

This is an executable slice spec, not strategy. Follow it red-first. GL lifts
the existing Lex legal knowledge graph, legal requirement compiler,
claim-level legal authority adapter, and provision-to-intervention mapping
artifacts into a replayable Layer 3 legal/mandate search path.

The goal is not to create a new legal reasoning engine. Search discovers legal
and mandate candidates; adapters discipline them; the existing legal authority
adapter decides whether any candidate can become claim-level legal authority.
Retrieved text, a search hit, a generic topic match, a threshold row, an
amendment row, or a `lex_intervention_map` entry is not authority by itself.

GL closes only when at least one legal threshold or mandate boundary is found
through the canonical L3 Legal KG route, replayed with temporal and amendment
lineage, evaluated through claim-level legal authority requirements, bound into
typed legal/mandate authority records, and consumed by runtime/PDC consumers
without laundering retrieval or mapping artifacts into recommendation,
closeout, publication, or agent authority.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.
`expected_open_cell_count: 0` refers to the existing Layer 2 cluster-map/open-cell
model that GL does not mutate. GL progress is measured by L3 Legal KG search
coverage, recall/freshness, legal requirement binding, temporal competence,
authority facet binding, amendment lineage, mandate authority records, consumer
gates, conformance negatives, and health ledgers.

## Intro

GL builds the legal/mandate search engine for Layer 3. Given a claim, legal
requirement, jurisdiction, policy domain, legal `as_of`, and intended
intervention family, GL searches the canonical L3 Legal KG for candidate norms,
rule thresholds, mandates, amendments, temporal windows, references, and
provision-to-intervention mappings. It persists the replayable search frontier,
then passes only temporally valid, source-grounded, claim-scoped candidates into
the existing legal authority adapter.

The primary existing substrates are:

- `production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb`
  - Canonical L3 Legal KG for this slice.
  - Current inspected tables include about 6M `lex_provisions`, 374k
    `lex_rule_thresholds`, 156k `lex_amendments`, 1.6M
    `lex_normative_ready_facts`, 1.6M `lex_normative_facts`, temporal audit,
    doc versions, doc temporal rows, references, and reference-resolution audit.
  - This is the GL search target. Smaller fixtures, Python API summaries, or
    inline candidate packs are tests/transition inputs, not closure authority.
- `src/polisyos/lex/knowledge/store.py`
  - Read-only DuckDB-backed `LegalKnowledgeStore`.
  - Existing structured routes include threshold search, applicable norms,
    constraints, source bundles, doc version chains, reference neighborhoods,
    jurisdiction/domain/as-of filters, confidence/quality-band filters, and lazy
    HNSW loading when vector indexes are present.
  - `search_facts_with_threshold(...)` is a useful discovery route, but inspected
    code returns `LegalFactResult` rows, not parsed threshold
    operator/value/unit/applies-to fields. GL threshold authority records must
    hydrate `lex_rule_thresholds` rows directly.
  - `text_search_facts(...)` is useful candidate retrieval, but it must not be
    the authority path by itself.
- `src/polisyos/lex/knowledge/search.py`
  - Higher-level `LegalKnowledgeGraph` hybrid search wrapper.
  - Its OpenAI embedding path is optional. GL readiness must remain
    deterministic/offline; live embedding calls cannot be required for closure.
- `src/polisyos/lex/knowledge/types.py`
  - Strict Lex DTOs for entities, facts, provisions, search results, trust
    tiers, grounding, canonicalization, reference resolution, and temporal
    fields.
- `src/polisyos/legal_requirement/**`
  - W7.B legal authority requirement compiler.
  - Emits strict claim-level requirements with authority types, jurisdiction,
    fallback policy, temporal competence window, required actors, required
    instruments, implementation/fiscal authority refs, scope predicates, rule
    versions, and authority boundary.
- `src/polisyos/lex/normpack/legal_authority.py`
  - Existing claim-level legal authority adapter.
  - It already treats retrieved legal material as candidate context until
    authority type, jurisdiction fallback, actor/instrument facets, source
    authority, hierarchy depth, legal time window, implementation/fiscal refs,
    conflict/supersession, and LLM provenance checks pass.
- `src/polisyos/lex/normpack/applicability_report.py`
  - Existing normative applicability report wrapper around legal authority.
  - It already produces query normalization traces, typed no-norm/retrieval
    blockers, legal corpus snapshot refs, candidate norms, applied norms,
    competence rows, and legal authority report fields.
  - GL may reuse this wrapper only after GL has already built canonical
    L3 Legal KG candidate bindings. Its internal fallback KG helper is a
    broad text/read-API candidate route, not a GL closure route.
- `src/polisyos/lex/intervention_artifacts.py`
  - Existing `LexProvisionMappingRegistry`, `LexInterventionMapEntry`,
    intervention knob dictionary, and provision-program crosswalk loaders.
  - These map validated provisions to executable intervention directives, but
    they do not create legal authority.
- `src/polisyos/lex/interventions.py`
  - Existing compiler from provision directives into IR intervention artifacts.
  - It imports heavier Foundry/Scientist dependencies at module load. GL should
    use `lex.intervention_artifacts` for readiness and lazy-load
    `lex.interventions` only in execution paths that actually compile an
    intervention.
- `src/polisyos/runtime/quality/claim_registry.py` and
  `src/polisyos/runtime/quality/semantic_binding.py`
  - Existing consumers for `selected_norm_refs`, `legal_authority_record_refs`,
    and `legal_authority_blocker_refs`.
  - Semantic binding already fails selected legal norms without claim-level
    legal authority records.
- `src/polisyos/runtime/quality/argument_graph.py`,
  `src/polisyos/runtime/quality/public_export.py`, and
  `src/polisyos/runtime/quality/invariants.py`
  - Existing diagnostic/readiness, public projection, and invariant-registration
    surfaces.
  - They are downstream visibility/governance consumers, not legal authority
    producers.
- `src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py`,
  `src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py`,
  `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py`, and
  `src/polisyos/pdc/_impl/layer2_design_search.py`
  - Existing S6 mandate-legitimacy, S7 mandate-bounded delegation, S8
    value-choice provenance, and PDC consumer surfaces.
  - They consume `mandate_record_ref`, `mandate_source_refs`,
    `s6_mandate_firewall_disposition`, delegation contract refs, and
    responsibility-integrity/value-choice posture. GL must feed these surfaces;
    it must not fork their governance decisions.

GL is an off-path sibling of G2/G3 in the master plan. G0 is the hard Layer 3
prerequisite. In this checkout, G1/G2/G3 readiness artifacts are useful context
for downstream integration and should be loaded when present, but GL closure
must not falsely depend on forecast/proof readiness unless a specific closure
case binds legal authority to a G2/G3 consumer.

## Closure Contract

Source of truth: roadmap GL closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`,
especially the GL "Legal/Mandate Search Engine" slice.

GL must deliver:

1. **G0 dependency gate** proving Layer 3 discovery discipline, engineering
   quality, search recall/freshness health, and adapter admission discipline are
   healthy before GL emits legal/mandate authority. G1/G2/G3 are context inputs,
   not universal GL prerequisites.
2. **Canonical L3 Legal KG search route** over
   `production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb`.
   The route must query real Lex KG tables such as `lex_rule_thresholds`,
   `lex_normative_ready_facts`, `lex_normative_facts`, `lex_amendments`,
   `lex_doc_versions`, `lex_doc_temporal`, `lex_reference_edges`,
   `lex_reference_resolution_audit`, and `lex_temporal_audit`. It must not
   close over inline candidate packs, fixture rows, or a small Python facade
   when the canonical KG is available.
3. **Replayable legal search frontier ledger** for every GL search path:
   query terms, normalized terms, jurisdiction/domain/as-of filters, table
   routes, SQL/query shapes, row ids, budget limits, candidate rows, no-hit
   blockers, index/schema snapshot, source bundle refs, and freshness/recall
   signals.
4. **Search recall/freshness guard** that distinguishes true legal/domain
   ceilings from search ceilings. A no-hit legal abstention is honest only when
   known-groundable seeds and index freshness checks pass.
5. **Legal requirement binding** from claim/facet/obligation context into
   `LegalAuthorityRequirementSpec` artifacts. Mandatory legal claims must
   carry authority types, temporal competence window, jurisdiction/fallback
   policy, actor/instrument refs, and scope predicates.
6. **Norm/threshold/mandate candidate binding** from Lex KG rows to candidate
   norm payloads accepted by `build_legal_authority_report(...)`. Because the
   inspected production KG does not expose all legal-authority facets as native
   columns, this includes an explicit authority-facet binding layer. The binding
   must include source provenance, legal time, authority level, jurisdiction,
   trust tier, grounding/canonical/reference-resolution status, rule threshold
   metadata, amendment lineage refs, and the derivation/missingness status of
   authority type, competent actor, instrument, implementation, and fiscal
   authority facets.
7. **L5 calibration binding** for GL legal candidates and authority records,
   carrying trust tiers, trust caps/min coverage where available, schema regime
   or changepoint refs, and calibration/provenance refs. GL must not treat a
   Lex row's confidence as calibrated authority without this binding or an
   explicit blocker/limitation.
8. **Claim-level legal authority evaluation** using the existing legal authority
   adapter. GL may add wrapper DTOs and generated artifacts, but it must not
   fork a second legal authority evaluator.
9. **Threshold authority records** for at least one rule threshold discovered
   through `lex_rule_thresholds` and hydrated from that table, with parsed
   metric/operator/value/unit/applies-to, source norm/provision refs, legal time,
   authority grade, and downstream limitation/blocker refs. Threshold fields
   inferred only from `thresholds_json` or a search-result summary cannot close
   GL.
10. **Mandate authority records** for at least one legal mandate or mandate
    boundary, with authority type, competent actor, instrument, scope, legal
   time, source lineage, and S6/S7/S8-consumable refs. GL mandate outputs must
   map into existing S6 `MandateSourceRecord` / `MandateLegitimacyRecord`
   semantics when claiming a mandate disposition; GL cannot mint a parallel S6
   pass.
11. **Temporal competence and amendment replay** proving that selected legal
    authority is valid for the claim's legal `as_of` / implementation window and
    not stale under later amendments. Missing effective time, unresolved
    temporal status, or stale amendment lineage must fail closed.
12. **`lex_intervention_map` binding** from an admitted legal provision to an
    intervention directive or handoff candidate. The mapping is executable
    design context, not legal authority. If the mapping exists without a valid
    legal authority record, it must be downgraded or blocked.
13. **Consumer gates** proving GL refs are consumed by existing runtime/PDC
    surfaces:
    - claim registry / semantic binding consume `selected_norm_refs`,
      `legal_authority_record_refs`, and blockers;
    - argument graph/readiness rows connect GL legal authority refs to a passing
      readiness node for any major claim that uses GL evidence;
    - S6/S7 mandate/delegation consumers receive mandate record/source refs and
      firewall disposition without responsibility laundering;
    - S8 value-choice consumers receive the same mandate refs/disposition when
      legal mandate evidence is used to authorize ranked value choices;
    - design constraints consume the legal boundary as constraints/limitations,
      not as promotion authority;
    - the future G4 promotion gate can read GL refs and blockers without GL
      claiming promotion itself;
    - public/export/projection surfaces expose audit refs/status only, not raw
      legal retrieval payloads as public authority. The current public-export
      code has a G3-specific projection hook, not a GL hook, so GL must either
      implement a GL-specific projection hook or label
      `layer3_gl_public_export_projection_refs.json` as reference-only outside
      `build_public_export_bundle`.
14. **Adapter registry and generated artifacts** so GL paths are visible in
    `architecture/generated_artifacts.toml`, generated-artifact docs, reference
    docs, adapter contract registry, and readiness manifest.
15. **Conformance negatives** proving retrieval-only, text-only, read-API
    fallback, LLM-summary,
    generic-topic, stale-amendment, temporal-missing, fallback-missing,
    map-only, and selected-norm-without-authority cases fail closed.

GL is done when `tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py`
passes over persisted artifacts, and the runtime tests prove at least one legal
threshold or mandate boundary goes:

```text
claim/legal requirement
-> canonical L3 Legal KG search
-> replayable search frontier ledger
-> legal requirement, authority-facet, norm-candidate, and L5 calibration bindings
-> temporally valid Lex threshold/mandate candidate with amendment/reference lineage
-> legal authority report with explicit GL producer artifact ref
-> threshold/mandate/temporal competence records
-> claim registry / semantic binding / argument graph readiness / S6/S7/S8 consumer gate
-> audit/API/MACHINE/EXPERT + public projection surface
```

## Scope Boundaries

In scope:

- Add GL runtime-quality contracts and builders for search ledgers, query
  traces, KG coverage, recall/freshness, L5 calibration bindings, legal
  requirement bindings, authority facet bindings, norm candidate bindings,
  threshold authority records,
  mandate authority records,
  temporal competence records, amendment lineage records, intervention-map
  bindings, consumer gates, conformance report, and readiness manifest.
- Reuse `LegalKnowledgeStore`, `LegalKnowledgeGraph`, `LegalAuthorityRequirementCompiler`,
  `build_legal_authority_report`, `build_normative_applicability_report`,
  `LexProvisionMappingRegistry`, claim registry, semantic binding, S6 mandate
  legitimacy, S7 delegation, and S8 value-choice surfaces.
- Add a GL readiness CLI and repo-quality tests following the G1/G2/G3 pattern.
- Persist generated artifacts under `architecture/policy_design_case/`.
- Register artifacts in generated artifact TOML/docs and add a reference doc.
- Register any production-invariant/readiness-check usage so
  `layer3_gl_legal_mandate_search_readiness_gate` is not an unknown readiness
  check when GL is wired into invariant rows.
- Add focused fixtures under `tests/fixtures/layer3/gl/` for semantic negatives.

Out of scope:

- Rebuilding the Lex KG, legal batch pipeline, amendment detector, or reference
  resolver.
- Building a new legal authority evaluator parallel to
  `polisyos.lex.normpack.legal_authority`.
- Using `build_normative_applicability_report`'s internal Lex KG text/read-API
  fallback as GL closure. GL must supply its own canonical, structured
  `Layer3GLNormCandidateBinding` rows before calling the report wrapper.
- Making OpenAI embeddings or live network access a readiness dependency.
- Importing heavy `lex.interventions` / Foundry / Scientist modules at GL module
  import time.
- Exposing raw legal text or retrieved legal payloads as PUBLIC authority.
- Changing S6/S7/S8 governance semantics. GL feeds legal mandate source refs and
  authority records; S6 still owns mandate legitimacy disposition, S7 owns
  delegation/responsibility integrity, and S8 owns value-choice/ranking
  authorization.
- Running full-corpus stress tests in unit tests. Unit tests use tiny DuckDB
  fixtures; readiness may sample/check the production KG with bounded SQL.

## Pattern Pass

Relevant failure patterns and closure moves:

- `P01` contract-only capability: GL must show producer -> persisted artifact
  -> bridge -> consumer -> visible surface -> negative test. A legal search DTO
  alone is `contract_only`.
- `P02` thin orchestration: Lex KG search, legal requirements, legal authority,
  intervention mapping, claim registry, and S6/S7/S8 must exchange binding
  artifacts, not merely coexist.
- `P03` hidden internal richness: EXPERT/MACHINE audit surfaces must show
  search frontier, authority grade, temporal competence, amendment lineage,
  mandate refs, and blockers.
- `P04` status lattice gap: GL local statuses must compose with legal
  admissibility, projection status, readiness, freshness, temporal validity,
  mandate firewall disposition, and publication/closeout gates.
- `P05` authority dilution: search ledgers, retrieved text, intervention-map
  entries, and audit surfaces must declare `may_not_use_for`.
- `P07` rule replay gap: legal authority records must carry schema/rule
  versions, legal KG snapshot, query trace, temporal lineage, and amendment
  lineage so closed cases can replay or reissue.
- `P08` time-role fragmentation: legal `as_of`, effective-from/to,
  implementation window, amendment effective time, data time, forecast time, and
  replay time must not collapse into one date.
- `P10` structural-only validation: tests must include semantic legal negatives,
  not just JSON shape checks.
- `P12` producer handshake gap: GL must bind legal requirements to claim/facet
  scope before asking Lex candidates to satisfy authority.
- `P13` contract gravity well: GL readiness should be bounded and authority-level
  gated. Do not require exhaustive full-KG search for every corpus claim.
  GL must also reuse the G0 `AdapterAdmissionRecord` shape instead of minting a
  parallel admission DTO.
- `P15` LLM speculation laundering: legal summaries, query expansions, and
  drafted interpretations from LLMs remain candidates until deterministic Lex
  authority validates norm refs.
- `P22` mandate-legitimacy laundering: mandates/goals/social-weight authority
  need legal/participation/governance provenance before they can close. GL must
  reuse or feed existing S6 mandate-source/legitimacy records instead of
  inventing a parallel mandate pass.
- `P25` search-control laundering: search frontier/no-hit/frontier-best
  candidates are control-plane evidence only; persist budgets and
  incompleteness.
- `P26` responsibility-integrity laundering: GL mandate refs must support
  S6/S7/S8; they must not shift responsibility to a human or authorize ranked
  value choices without the existing mandate-bounded decision/value records.

Capability state at plan start:

- Lex KG search substrate: **producer exists**, **canonical artifact exists**,
  GL Layer 3 search ledger/consumer binding missing.
- L5 calibration substrate: **metadata exists in the corpus doctrine**, but GL
  binding into legal candidate/authority records is missing.
- Legal requirement compiler: **implemented**, but GL must bind it to L3 legal
  search and readiness artifacts.
- Authority facet extraction from production Lex KG: **bridge_missing**. The KG
  has threshold, temporal, reference, amendment, fact, and document fields, but
  inspected production tables do not expose native authority-type,
  competent-actor, instrument, implementation-authority, or fiscal-authority
  columns. GL must derive or block these facets explicitly instead of assuming
  them.
- Legal authority adapter: **implemented**, but GL must prove canonical KG
  candidate path and downstream consumer gates.
- `lex_intervention_map`: **producer/artifact exists for mappings**, but GL
  readiness/authority boundary and legal-authority precondition are missing.
- S6/S7/S8 consumers: **implemented**, but GL mandate record/source ref handoff
  is missing.
- GL as a complete capability: currently **bridge_missing**,
  **surface_missing**, and **semantic_test_missing**.

Target correct pattern:

```text
canonical L3 Legal KG row
+ replayable search frontier
+ legal requirement spec
+ authority facet binding
+ temporal/amendment/source lineage
+ legal authority adapter result
+ mandate/threshold authority record
+ consumer gate
+ audit surface
= admitted legal/mandate authority within declared purpose
```

## Code-Grounded Reality

The following inspection facts should shape implementation:

- The production L3 Legal KG is real and large. Do not materialize
  `lex_provisions` or `lex_normative_ready_facts` in Python. Use bounded DuckDB
  SQL, table predicates, projections, `LIMIT`, and lazy row hydration.
- The production Lex bundle also has companion freshness/evidence files:
  `finalize/qc_report.json`, `finalize/benchmark_report.json`,
  `amendment_only_summary.json`, and
  `finalize/claim_exports/normative_claims_summary.json`. Readiness should
  capture their identities when present.
- `LegalKnowledgeStore` already supports useful structured routes:
  `search_facts_with_threshold`, `find_constraints`, `get_applicable_norms`,
  source bundle loading, doc version chains, and reference neighborhoods.
- `search_facts_with_threshold(...)` joins threshold rows for discovery but
  returns fact-level DTOs. GL must hydrate `lex_rule_thresholds` directly for
  `metric`, `operator`, `value_decimal`, `value_text`, `unit`, and `applies_to`.
- The store's `as_of` filtering already hides rows whose temporal resolution is
  not resolved. GL should preserve this invariant and add explicit issue codes
  when candidates fail temporal resolution.
- Inspected corpus state includes many `partial` temporal rows. Passing
  authority seeds should use resolved/effective rows; partial/conflict rows are
  limitation or blocker cases, not evidence that the whole corpus is unusable.
- `LegalKnowledgeGraph` can call OpenAI embeddings. GL readiness must prefer
  deterministic DuckDB/HNSW/structured routes. Query embeddings may be used only
  when concrete vector/HNSW index artifacts and the query-vector producer/ref are
  persisted and replayable. QC text that says embeddings are optional is not a
  substitute for index files.
- The inspected production KG does not expose native columns named like
  `authority_type`, `competent_actor`, `instrument`, `implementation_authority`,
  `fiscal_authority`, or `budget_authority` in the search tables. GL must
  therefore add a deterministic authority-facet binding over existing fields
  such as doc metadata, fact/provision text, action/norm type, route class,
  threshold rows, source quote, and governed config. Any text-derived facet is
  context-only unless the binding declares a replayable rule and validation
  status.
- The legal requirement compiler currently defaults mandatory claims with no
  explicit authority type to `implementing`. GL may preserve that behavior, but
  the binding must mark the authority type as compiler-derived rather than
  Lex-discovered authority.
- `build_legal_authority_report(...)` internally compiles requirement specs when
  `legal_requirement_specs` is absent and emits a stable derived artifact ref
  when `producer_artifact_ref` is omitted. GL closure must pass explicit,
  persisted GL requirement specs plus a real producer artifact ref so the
  requirement/authority bridge remains replayable.
- `build_legal_authority_report(...)` already covers:
  authority type matching, jurisdiction fallback policy, actor/instrument
  facets, implementation/fiscal refs, hierarchy depth, source authority,
  legal windows, competence-window splits, LLM-provenance firewall, and
  blockers.
- `build_normative_applicability_report(...)` already handles query
  normalization traces, legal corpus snapshots, retrieval blockers, legal KG
  paths, candidate norms from packs/runtime payloads, and legal authority report
  fields.
  Its internal `_candidate_norms_from_lex_kg`/Data Forge read-API path is a
  broad text candidate helper; GL must not use it as the canonical L3 Legal KG
  closure route because it does not bind rule-threshold/amendment/reference/L5
  lineage with sufficient authority semantics.
- Applicability-report runtime payloads can also provide inline
  `runtime_candidate_norms`. For GL closeout, inline snapshots are fixtures or
  transition inputs only; closure needs the canonical KG snapshot, GL query trace,
  GL-built candidates, and a query-normalization report for no-hit cases.
- Existing tests already prove:
  generic legal topic matches remain context-only;
  jurisdiction fallback requires governed config;
  funding/implementing authority types are independent;
  competence-window changes split only affected legal windows;
  selected norms without claim-level legal authority fail semantic binding.
- Candidate norm dictionaries accepted by the legal authority adapter need exact
  fields, not just row ids and confidence: `norm_version_ref`,
  `source_provenance_ref`, jurisdiction/fallback, `authority_types`,
  `competent_actor_ref`, `instrument_types`, implementation/fiscal refs where
  relevant, legal effective window, `source_authority`, hierarchy data, and
  conflict/supersession/preemption state.
- `LexProvisionMappingRegistry` is the right map substrate for
  `lex_intervention_map`. Its `resolve(...)` path lazy-imports the heavier
  compiler. GL should test the registry/mapping boundary before compiling
  interventions. The inspected production intervention bundle may have zero map
  entries; that is mapping coverage status, not legal-corpus failure.
- `runtime/quality/claim_registry.py` already records `selected_norm_refs`,
  `legal_authority_record_refs`, and `legal_authority_blocker_refs`.
- `runtime/quality/semantic_binding.py` already extracts legal authority fields
  from Lex reports and blocks selected legal norms without legal authority
  record refs. Claim registry preservation alone is not enough for GL closure;
  semantic binding must also pass without
  `semantic_lex_legal_authority_record_missing`.
- `runtime/quality/argument_graph.py` only creates an
  `authority_feeds_readiness` edge when a major claim has evidence, a matched
  authority row, and a matched passing readiness row. GL must provide or validate
  that readiness row when legal authority evidence is used on a major claim; the
  argument graph remains diagnostic and does not mint authority.
- `runtime/quality/public_export.py` has an existing G3 analytics-search
  projection hook. It does not yet have an equivalent GL hook. GL public/export
  readiness must either add a GL-specific projection hook or keep the GL public
  projection artifact as reference-only and explicitly outside the runtime public
  export bundle.
- `runtime/quality/invariants.py` validates readiness-check ids against a fixed
  set for production invariant rows. If GL becomes a production invariant
  readiness check, the id must be registered instead of relying on free-form
  readiness names.
- `layer2_blind_spot_firewalls.py` already owns S6 mandate legitimacy through
  `MandateSourceRecord`, `MandateLegitimacyRecord`, and
  `evaluate_mandate_legitimacy(...)`. GL should produce S6-compatible source
  rows/refs or reference an evaluated S6 record when it claims a mandate
  disposition.
- `layer2_delegation.py`, `layer2_value_choice.py`, and
  `pdc/_impl/layer2_design_search.py` already consume `mandate_record_ref`,
  `mandate_source_refs`, and `s6_mandate_firewall_disposition`. S8 authorized
  value schedules fail closed unless the mandate firewall passes and mandate
  source dispositions are not candidate/limited.

## Target File Map

Runtime contracts and builders:

- Add `src/polisyos/runtime/quality/proving_ground/legal_mandate_search.py`.
  - Strict Pydantic DTOs with `extra="forbid"`.
  - No heavy Lex intervention/Foundry/Scientist imports at module load.
  - Public builder:
    `build_layer3_gl_bundle(repo_root: Path) -> Layer3GLBundle`.
  - Public validator:
    `validate_layer3_gl_bundle(repo_root: Path, bundle: Layer3GLBundle) -> Layer3GLValidationReport`.

Readiness CLI:

- Add `tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py`.
  - Match the G1/G2/G3 CLI shape: `--repo-root`, `--write`, `--output`,
    `--output-format`.
  - Use `tools.lib.fs.atomic_write_text`.
  - Validate runtime bundle, persisted artifacts, docs/TOML registration,
    manifest drift, issue-code dictionary, and write-path completeness.

Tests:

- Add `tests/unit/runtime/quality/test_layer3_gl_legal_mandate_search.py`.
- Add `tests/repo_quality/tools/test_policy_design_case_layer3_gl_readiness.py`.
- Add `tests/repo_quality/tools/test_policy_design_case_layer3_gl_readiness_cli.py`.
- Add fixtures under `tests/fixtures/layer3/gl/` for malformed and valid bundles.

Generated artifacts:

- Persist GL artifacts under `architecture/policy_design_case/`.
- Register them in `architecture/generated_artifacts.toml`.
- Register GL audit/projection surfaces in
  `architecture/policy_design_case/inventory.json`.
- Update `docs/reference/generated-artifacts.md`.
- Add `docs/reference/policy-design-case-layer3-legal-mandate-search.md`.
- Update `docs/reference/public-surface.md` if the local public-surface pattern
  requires a GL audit/projection entry.
- Update `docs/reference/documentation-inventory.md` and
  `docs/reference/index.md` if the local reference-doc pattern requires it.

## Persisted Artifacts

Expected generated artifacts:

- `architecture/policy_design_case/layer3_gl_adapter_admission_registry.json`
- `architecture/policy_design_case/layer3_gl_l3_legal_kg_index_coverage.json`
- `architecture/policy_design_case/layer3_gl_l3_legal_kg_search_ledgers.json`
- `architecture/policy_design_case/layer3_gl_l3_legal_kg_query_traces.json`
- `architecture/policy_design_case/layer3_gl_search_recall_freshness.json`
- `architecture/policy_design_case/layer3_gl_l5_calibration_bindings.json`
- `architecture/policy_design_case/layer3_gl_legal_requirement_bindings.json`
- `architecture/policy_design_case/layer3_gl_authority_facet_bindings.json`
- `architecture/policy_design_case/layer3_gl_norm_candidate_bindings.json`
- `architecture/policy_design_case/layer3_gl_threshold_authority_records.json`
- `architecture/policy_design_case/layer3_gl_mandate_authority_records.json`
- `architecture/policy_design_case/layer3_gl_temporal_competence_records.json`
- `architecture/policy_design_case/layer3_gl_amendment_lineage_records.json`
- `architecture/policy_design_case/layer3_gl_reference_resolution_records.json`
- `architecture/policy_design_case/layer3_gl_legal_authority_report.json`
- `architecture/policy_design_case/layer3_gl_lex_intervention_map_bindings.json`
- `architecture/policy_design_case/layer3_gl_claim_registry_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_semantic_binding_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_argument_graph_readiness_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_s6_mandate_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_s7_delegation_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_s8_value_choice_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_pdc_compiler_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_design_constraint_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_g4_promotion_gate_consumer_gate.json`
- `architecture/policy_design_case/layer3_gl_promotion_gate_handoff.json`
- `architecture/policy_design_case/layer3_gl_legal_mandate_audit_surface.json`
- `architecture/policy_design_case/layer3_gl_public_export_projection_refs.json`
- `architecture/policy_design_case/layer3_gl_conformance_report.json`
- `architecture/policy_design_case/layer3_gl_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_gl_adapter_contract_registry.toml`
- `architecture/policy_design_case/layer3_gl_readiness_manifest.json`

Minimum write-mode paths must include legal requirement, authority-facet,
norm-candidate, and L5 calibration bindings; the authority report;
threshold/mandate records; temporal/amendment/reference lineage; consumer gates;
audit/projection surfaces; health metric delta; adapter contract registry;
conformance report; and readiness manifest. Search ledgers/query traces/index
coverage must be written as well because GL cannot distinguish honest abstention
from search recall failure without them.

## Runtime Contract Sketch

Add strict DTOs in `layer3_legal_mandate_search.py`:

- `Layer3GLValidationIssue`
- `Layer3GLValidationReport`
- `Layer3GLLegalMandateRequest`
- `Layer3GLL3LegalKgCoverageReport`
- `Layer3GLLegalSearchLedger`
- `Layer3GLLegalQueryTrace`
- `Layer3GLSearchRecallFreshnessReport`
- `Layer3GLL5CalibrationBinding`
- `Layer3GLLegalRequirementBinding`
- `Layer3GLAuthorityFacetBinding`
- `Layer3GLNormCandidateBinding`
- `Layer3GLThresholdAuthorityRecord`
- `Layer3GLMandateAuthorityRecord`
- `Layer3GLTemporalCompetenceRecord`
- `Layer3GLAmendmentLineageRecord`
- `Layer3GLReferenceResolutionRecord`
- `Layer3GLLegalAuthorityReportBinding`
- `Layer3GLLexInterventionMapBinding`
- `Layer3GLClaimRegistryConsumerGate`
- `Layer3GLSemanticBindingConsumerGate`
- `Layer3GLArgumentGraphReadinessConsumerGate`
- `Layer3GLS6MandateConsumerGate`
- `Layer3GLS7DelegationConsumerGate`
- `Layer3GLS8ValueChoiceConsumerGate`
- `Layer3GLPdcCompilerConsumerGate`
- `Layer3GLDesignConstraintConsumerGate`
- `Layer3GLG4PromotionGateConsumerGate`
- `Layer3GLPromotionGateHandoff`
- `Layer3GLLegalMandateAuditSurface`
- `Layer3GLPublicExportProjectionRefSurface`
- `Layer3GLAdapterAdmissionBundle`
- `Layer3GLConformanceReport`
- `Layer3GLReadinessManifest`
- `Layer3GLBundle`

Do not define a new adapter-admission record schema for GL. Reuse/import the G0
`AdapterAdmissionRecord` shape from `layer3_grounding_inventory.py` inside a
GL-specific bundle/view that names the GL adapter id, source ids, cluster-derived
port ids, conformance refs, adapter-contract refs, and admission state.

Core constants:

- `LAYER3_GL_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gl_legal_mandate_search.v1"`
- `LAYER3_GL_RULE_VERSION = "policyos.layer3.gl.legal_mandate_search.v1"`
- `CANONICAL_L3_LEGAL_KG_PATH = Path("production_data/lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb")`
- `GL_SURFACE_ID = "layer3_gl_legal_mandate_audit_surface"`
- `GL_PUBLIC_PROJECTION_SURFACE_ID = "layer3_gl_public_export_projection_refs"`
- `GL_MAY_NOT_USE_FOR = ("recommendation_substance", "closeout_authority", "publication_authority", "agent_authority", "legal_authority_without_claim_level_adapter", "mandate_authority_without_temporal_competence", "s6_mandate_pass_without_s6_evaluation", "ranked_value_choice_without_s8_authorization")`

Public builder functions:

- `build_layer3_gl_bundle(repo_root: Path) -> Layer3GLBundle`
- `validate_layer3_gl_bundle(repo_root: Path, bundle: Layer3GLBundle) -> Layer3GLValidationReport`
- `build_gl_l3_legal_kg_index_coverage(repo_root: Path) -> Layer3GLL3LegalKgCoverageReport`
- `build_gl_legal_search_ledgers(repo_root: Path, requests: Sequence[Layer3GLLegalMandateRequest]) -> tuple[Layer3GLLegalSearchLedger, ...]`
- `build_gl_search_recall_freshness(repo_root: Path, ledgers: Sequence[Layer3GLLegalSearchLedger]) -> Layer3GLSearchRecallFreshnessReport`
- `build_gl_l5_calibration_bindings(...) -> tuple[Layer3GLL5CalibrationBinding, ...]`
- `build_gl_legal_requirement_bindings(...) -> tuple[Layer3GLLegalRequirementBinding, ...]`
- `build_gl_authority_facet_bindings(...) -> tuple[Layer3GLAuthorityFacetBinding, ...]`
- `build_gl_norm_candidate_bindings(...) -> tuple[Layer3GLNormCandidateBinding, ...]`
- `build_gl_legal_authority_report_binding(...) -> Layer3GLLegalAuthorityReportBinding`
- `build_gl_threshold_authority_records(...) -> tuple[Layer3GLThresholdAuthorityRecord, ...]`
- `build_gl_mandate_authority_records(...) -> tuple[Layer3GLMandateAuthorityRecord, ...]`
- `build_gl_temporal_competence_records(...) -> tuple[Layer3GLTemporalCompetenceRecord, ...]`
- `build_gl_lex_intervention_map_bindings(...) -> tuple[Layer3GLLexInterventionMapBinding, ...]`
- `build_gl_claim_registry_consumer_gate(...) -> Layer3GLClaimRegistryConsumerGate`
- `build_gl_semantic_binding_consumer_gate(...) -> Layer3GLSemanticBindingConsumerGate`
- `build_gl_argument_graph_readiness_consumer_gate(...) -> Layer3GLArgumentGraphReadinessConsumerGate`
- `build_gl_s6_mandate_consumer_gate(...) -> Layer3GLS6MandateConsumerGate`
- `build_gl_s7_delegation_consumer_gate(...) -> Layer3GLS7DelegationConsumerGate`
- `build_gl_s8_value_choice_consumer_gate(...) -> Layer3GLS8ValueChoiceConsumerGate`
- `build_gl_pdc_compiler_consumer_gate(...) -> Layer3GLPdcCompilerConsumerGate`
- `build_gl_design_constraint_consumer_gate(...) -> Layer3GLDesignConstraintConsumerGate`
- `build_gl_g4_promotion_gate_consumer_gate(...) -> Layer3GLG4PromotionGateConsumerGate`
- `build_gl_promotion_gate_handoff(...) -> Layer3GLPromotionGateHandoff`
- `build_gl_audit_surface(...) -> Layer3GLLegalMandateAuditSurface`
- `build_gl_public_export_projection_refs(...) -> Layer3GLPublicExportProjectionRefSurface`

All public DTOs crossing generated artifacts must carry:

- `schema_version`
- `rule_version`
- `status`
- `authority_boundary`
- `authoritative_for`
- `may_not_use_for`
- `producer_component`
- `producer_artifact_ref`
- `provenance_refs`
- `legal_kg_snapshot_ref`
- `query_trace_refs`
- `search_ledger_refs`
- `l5_calibration_refs`
- `legal_requirement_artifact_ref`
- `authority_facet_binding_refs`
- `legal_as_of`
- `effective_from` / `effective_to` or explicit blocker
- `temporal_resolution_status`
- `amendment_lineage_refs`
- `reference_resolution_status`
- `source_authority`
- `authority_level`
- `jurisdiction`
- `claim_id` / `requirement_ref` where claim-scoped

## Adapter Semantics

GL has three distinct states:

1. `discoverable`
   - A legal candidate is visible through canonical KG search.
   - This is not authority.
2. `executable`
   - The candidate can be mapped to an intervention/provision or consumer
     handoff.
   - This is not authority unless claim-level legal authority also passes.
3. `admitted_authority`
   - The candidate passed legal requirement, temporal competence, amendment
     lineage, source authority, jurisdiction/fallback, actor/instrument, and
     consumer gate checks.

These states compose with the single authority/status lattice; they do not form
a parallel status system. Every GL artifact must preserve the distinction:

- Search ledger authoritative for replay/provenance only.
- Query trace authoritative for search parameters only.
- KG coverage authoritative for route health only.
- Authority facet binding authoritative for derivation/missingness status only;
  it is not legal authority until the claim-level legal authority adapter passes.
- Candidate norm binding authoritative for candidate identity/provenance only.
- Legal authority report authoritative for claim-level legal admissibility only.
- Threshold authority record authoritative for the parsed legal threshold only
  within its claim/scope/time/authority boundary.
- Mandate authority record authoritative for mandate boundary only within its
  claim/scope/time/authority boundary, and only as S6-compatible mandate input
  unless an evaluated S6 mandate legitimacy record is referenced.
- Intervention-map binding authoritative for executable mapping only after a
  valid legal authority precondition; it is never legal authority.
- Audit/public projection authoritative for disclosure and reference visibility
  only. Public projection refs are not legal authority and are not proof of a
  runtime public-export bundle hook unless that hook is implemented and tested.

Local GL dispositions should include:

- `admissible`
- `proxy_with_limitation`
- `context_only`
- `contested`
- `blocked`
- `out_of_scope`
- `search_ceiling_repair_required`
- `temporal_reissue_required`
- `stale_amendment_lineage`

Composition rules:

- `selected_norm_refs` without `legal_authority_record_refs` -> fail.
- `lex_intervention_map` binding without legal authority record -> executable
  candidate only; fail for admitted authority.
- Missing `effective_from` or unresolved `temporal_resolution_status` for
  claim legal `as_of` -> blocked.
- Partial/conflict temporal rows may support limitations or negative tests, but
  must not be promoted to passing authority records.
- Stale index or missed known-groundable seed -> search ceiling, not domain
  ceiling.
- Generic topic/country/domain match without claim-level facets -> context only.
- Missing, unvalidated, or overclaimed authority facets -> context only or
  blocked; never admitted authority.
- Governed jurisdiction fallback missing -> blocked or context only, not
  admissible.
- `proxy_with_limitation` must carry limitation/fallback policy refs.
- LLM legal summary provenance -> candidate only until deterministic legal
  authority validates the norm ref.
- GL mandate source refs without an S6 mandate legitimacy record or compatible
  S6 source-row handoff -> compatibility-only, not mandate pass.
- S8 ranked value-choice authorization requires existing S8 checks; a GL legal
  mandate record alone cannot authorize ranking.

## Implementation Tasks

### Task 0 - Red Baseline and Dependency Audit

Create failing tests first.

Add tests that expect:

- GL readiness CLI/module exists.
- Expected artifact path set is complete.
- Missing persisted artifacts fail readiness.
- Manifest drift keys are enforced.
- Issue-code dictionary includes GL-specific failures.
- Runtime bundle cannot pass with search ledgers but no legal authority record.
- Runtime bundle cannot pass with legal authority report but no consumer gate.
- Runtime bundle cannot pass when `lex_intervention_map` is used as legal
  authority.
- Runtime bundle cannot pass when threshold authority is built from fact summary
  or `thresholds_json` without hydrated `lex_rule_thresholds` fields.
- Runtime bundle cannot pass when authority facets are assumed to exist in KG rows
  without a GL authority-facet binding.
- Runtime bundle cannot pass when the legal requirement compiler's default
  `implementing` authority type is treated as Lex-discovered authority.
- Runtime bundle cannot pass when legal authority report closure relies on the
  adapter's internal requirement compilation or derived producer artifact ref.
- Runtime bundle cannot pass when inline `runtime_candidate_norms` close GL.
- Runtime bundle cannot pass when GL claims S6 mandate pass without an
  S6-compatible mandate source/evaluation handoff.

Audit dependencies:

- Verify G0 readiness artifacts exist and pass.
- Load G1/G2/G3 manifests if present and record them as context, not hard GL
  prerequisites.
- Verify canonical Lex KG path exists and required tables are visible.
- Verify `LegalKnowledgeStore`, legal requirement compiler, legal authority
  adapter, `LexProvisionMappingRegistry`, claim registry, semantic binding, and
  S6/S7/S8 consumer imports are available.
- Verify importing GL runtime module does not import `polisyos.lex.interventions`
  or Foundry/Scientist heavy modules.

Acceptance:

- Red tests fail for missing GL module/CLI/artifacts.
- Dependency audit issue codes are present and precise.

### Task 1 - Canonical L3 Legal KG Search Route

Implement bounded canonical KG coverage and search ledger builders.

Coverage must check:

- canonical DuckDB file exists;
- required tables exist;
- required columns exist for:
  - `lex_rule_thresholds`;
  - `lex_normative_ready_facts` or `lex_normative_facts`;
  - `lex_amendments`;
  - `lex_doc_versions`;
  - `lex_doc_temporal`;
  - `lex_reference_edges` / reference audit;
  - `lex_temporal_audit`;
- table counts are nonzero where required;
- schema snapshot and DB file identity/freshness are captured;
- authority-facet source status is captured as
  `native`, `requires_gl_facet_binding`, `governed_config_only`, or `missing`;
- Lex QC/benchmark/summary companion file identities are captured when present;
- path is canonical L3 KG, not inline candidate pack or fixture route.

Search route must:

- Use DuckDB SQL / `LegalKnowledgeStore` structured methods.
- Prefer threshold/action/domain/jurisdiction/as-of queries over broad text
  search.
- Hydrate threshold authority fields from `lex_rule_thresholds` direct SQL or a
  typed row query, not from fact-result summaries.
- Keep text search as candidate expansion only, with downgrade metadata.
- Use HNSW/vector search only when existing index assets and query vector
  producer refs are present.
- Persist query trace refs and selected row ids.
- Never load all provisions/facts into Python.

Seeded canonical GL queries should cover at least:

- one resolved/effective `lex_rule_thresholds` metric/operator/value/unit path;
- one normative fact path with jurisdiction/domain/as-of;
- one amendment lineage path;
- one provision/source bundle path;
- one reference-resolution path;
- one intervention-map candidate path using fixture/mapping artifacts where
  production mapping is not available.

Acceptance:

- `layer3_gl_l3_legal_kg_index_coverage.json` reports `pass`.
  If the KG lacks native authority/actor/instrument/fiscal columns, this can
  still pass only with `authority_facet_source_status=requires_gl_facet_binding`
  and a mandatory downstream authority-facet binding check.
- `layer3_gl_l3_legal_kg_search_ledgers.json` contains at least one successful
  canonical KG ledger and at least one bounded no-hit/error ledger.
- `layer3_gl_l3_legal_kg_query_traces.json` records SQL/table route, filters,
  limits, row ids, candidate counts, and replay identifiers.
- Any noncanonical route is explicitly labeled `transition_input` and cannot
  close GL.

### Task 2 - Search Recall, Freshness, and False-Abstention Guard

Implement `Layer3GLSearchRecallFreshnessReport`.

Known-groundable seed classes:

- `known_threshold_seed`: a metric known to exist in `lex_rule_thresholds`.
- `known_norm_seed`: a normative fact known to satisfy jurisdiction/domain/as-of
  filters.
- `known_amendment_seed`: an amendment row with effective date/target refs.
- `known_temporal_seed`: a row with resolved temporal status.
- `known_reference_seed`: a reference edge or resolution-audit row.
- `known_mapping_seed`: a provision ref in a test mapping registry.

Freshness checks:

- canonical KG file identity and modification/fingerprint snapshot;
- Lex KG QC/benchmark/summary files where present:
  `finalize/qc_report.json`, `finalize/benchmark_report.json`,
  `amendment_only_summary.json`, and
  `finalize/claim_exports/normative_claims_summary.json`;
- generated ledger snapshot refers to same KG path/snapshot;
- no stale index or missing refresh can be called a legal/domain ceiling.

False-abstention rule:

- If no candidate is found and recall/freshness passes, GL may emit a typed
  legal no-ground blocker.
- If no candidate is found and recall/freshness fails, GL must emit
  `search_ceiling_repair_required`, not `domain_ceiling` or honest legal
  abstention.

Acceptance:

- Readiness exposes `search-recall@known-seeds+index-staleness` in GL health
  metric delta.
- Tests prove a missed known seed blocks domain-ceiling claims.
- Tests prove stale/missing KG snapshot blocks honest no-hit abstention.

### Task 3 - Legal Requirement, Authority Facet, and Norm Candidate Binding

Build GL bindings from claim/request context to legal requirements, from Lex KG
rows to legal-authority facets, and from those facets to candidate norms.

Legal requirement binding must:

- Reuse `compile_legal_authority_requirements(...)` or
  `compile_legal_authority_requirement_artifact(...)`.
- Preserve claim id/ref, mandatory/out-of-scope state, authority types,
  required hierarchy depth, temporal competence window, required instrument
  classes, actor refs, implementation/fiscal refs, fallback policy,
  jurisdiction, authority profile, facet refs, obligation refs, concept-spine
  refs, rule version, and authority boundary.
- Treat non-legal claims as out of scope with explicit no-authority rationale,
  not as silently satisfied.
- Persist the compiler output as the GL requirement artifact and pass those exact
  `legal_requirement_specs` into `build_legal_authority_report(...)` and
  `build_normative_applicability_report(...)`; do not rely on the legal-authority
  adapter's internal requirement compilation for GL closure.
- Pass a GL persisted `producer_artifact_ref` into the legal authority adapter.
  A stable derived ref emitted by the adapter is acceptable for non-GL callers,
  but is not the GL producer bridge.
- Mark compiler-derived defaults, especially the mandatory-claim default
  `authority_types=("implementing",)`, as `compiler_derived_default`; they are
  not Lex-discovered legal authority facets.

Authority facet binding must:

- Create `Layer3GLAuthorityFacetBinding` records between KG row refs and
  legal-authority candidate fields.
- For every authority-bearing candidate, record facet status for
  `authority_types`, `competent_actor_ref`, `instrument_types`,
  `implementation_authority_ref`, `fiscal_authority_ref`, `source_authority`,
  hierarchy, conflict/supersession/preemption, fallback, and legal effective
  window.
- Classify each facet source as `lex_explicit`, `derived_from_doc_metadata`,
  `derived_from_fact_or_source_quote`, `governed_config`, `compiler_default`,
  or `missing`.
- Carry `source_table`, `source_column_refs`, `source_row_refs`,
  `derivation_rule_ref`, `validation_status`, `semantic_loss_status`, and
  blocker/limitation refs.
- Treat text-derived authority type, actor, instrument, fiscal, or implementation
  facets as context-only unless the derivation rule is deterministic, replayable,
  validated, and allowed by the authority boundary.
- Fail closed when a candidate needs a facet that is `missing`, unvalidated,
  text-derived without validation, or only a compiler default incompatible with
  the claim requirement.

Norm candidate binding must:

- Convert Lex KG fact/provision/threshold rows into candidate norm dictionaries
  compatible with `build_legal_authority_report(...)`.
- Carry `norm_id`, `norm_version_ref`, `source_provenance_ref`, jurisdiction,
  policy domain/top domain, effective window, source authority, authority level,
  authority types, competent actor, instrument types, implementation/fiscal
  authority refs where available, legal `as_of`, trust tier, grounding status,
  canonical status, reference resolution status, temporal status, threshold ids,
  amendment lineage refs, and query trace refs.
- Preserve conflict, supersession, preemption, fallback, hierarchy-depth, and
  authority-position fields when present because the legal authority adapter
  treats them as load-bearing.
- Populate candidate norm authority fields only from
  `Layer3GLAuthorityFacetBinding` outputs or explicit governed configuration, not
  from ad hoc string guesses.
- Downgrade incomplete candidates to context-only/blocker rows instead of
  filling missing legal authority fields with guesses.
- Call `build_normative_applicability_report(...)` only with GL-built
  `candidate_norms` and `legal_requirement_specs`; do not let the wrapper's
  internal `_candidate_norms_from_lex_kg` / Data Forge read-API text search
  discover candidates for GL closure.

Acceptance:

- Candidate binding from real KG rows feeds the legal authority adapter.
- Authority facet bindings are present for passing candidates and preserve
  explicit/derived/missing facet status.
- Generic topic/domain/country matches stay context-only.
- Compiler-derived authority-type defaults are visible and cannot masquerade as
  Lex-discovered authority.
- Missing fallback policy, actor/instrument facets, or source authority fails
  closed.
- A test proves GL closure passes explicit persisted legal requirement specs and
  producer artifact refs into the legal authority adapter.
- A test proves the internal applicability-report KG fallback cannot satisfy GL
  closure and is labeled transition/text-candidate context when observed.

### Task 4 - Claim-Level Legal Authority, Threshold, Mandate, and Temporal Records

Reuse `build_legal_authority_report(...)` as the authority waist.

Implement:

- `Layer3GLL5CalibrationBinding`
  - Binds candidate norms, thresholds, mandates, trust tiers, trust caps,
    minimum coverage, schema-regime/changepoint refs, quality bands, confidence
    fields, and calibration provenance where available.
  - Marks missing L5 calibration as a limitation/blocker for calibrated legal
    authority claims rather than silently upgrading raw Lex confidence.
- `Layer3GLLegalAuthorityReportBinding`
  - Stores the raw report ref/payload summary, selected norm refs, rejected norm
    refs, legal authority record refs, blockers, requirement refs, candidate
    norm count, issue codes, and authority boundary.
  - Records that GL passed explicit persisted `legal_requirement_specs`,
    authority-facet binding refs, and a GL `producer_artifact_ref` into the
    adapter. If the adapter internally compiled requirements or emitted only a
    derived stable producer ref, the GL record must be blocked for closure.
- `Layer3GLThresholdAuthorityRecord`
  - Binds a `lex_rule_thresholds` row to the legal authority record that admits
    it.
  - Includes metric, operator, value decimal/text, unit, applies-to/scope,
    source fact/provision/norm refs, legal time, authority grade, limitation
    refs, blocker refs, and query trace refs.
  - Must prove the threshold fields came from `lex_rule_thresholds` hydration.
    `LegalFactResult.thresholds_json` or `search_facts_with_threshold(...)`
    output may be discovery context, not authority-row closure.
- `Layer3GLMandateAuthorityRecord`
  - Binds a mandate/legal boundary to claim/S6/S7/S8-consumable refs.
  - Includes mandate record ref, mandate source refs, authority type, competent
    actor, instrument/scope, jurisdiction, effective window, legal `as_of`,
    source authority, legal authority record refs, limitation/blocker refs, and
    S6 firewall disposition.
  - Must either reference an evaluated S6 `MandateLegitimacyRecord` or emit
    S6-compatible `MandateSourceRecord` payloads/refs with a clear
    compatibility-only status until S6 evaluates them.
- `Layer3GLTemporalCompetenceRecord`
  - Captures claim implementation window vs legal effective window vs legal
    `as_of` vs amendment effective time.
  - Marks stale/missing/unresolved temporal status as blocked or reissue
    required.
- `Layer3GLAmendmentLineageRecord`
  - Captures amended/amending doc ids, amendment id/type, effective from,
    target anchor, old/new text refs or hashes, confidence, lineage status, and
    query trace refs.
- `Layer3GLReferenceResolutionRecord`
  - Captures reference edge/resolution audit rows for selected norms/provisions.

Acceptance:

- At least one threshold or mandate boundary has a passing authority record.
- Threshold authority records show hydrated operator/value/unit fields from
  `lex_rule_thresholds`.
- Mandate records do not fork S6; they reference S6 evaluation or remain
  compatibility-only source handoff records.
- L5 calibration binding is present for passing records or a typed limitation
  explains why only fail-closed/context authority is available.
- At least one negative temporal/amendment case fails closed.
- Legal authority adapter issue codes are preserved rather than hidden behind a
  GL summary.
- The authority report binding proves no internal requirement compile, inline
  candidate snapshot, or missing producer artifact ref was used for GL closure.

### Task 5 - Lex Intervention Map Binding

Implement GL intervention-map binding without laundering mapping into authority.

Use:

- `LexProvisionMappingRegistry`
- `LexInterventionMapEntry`
- `InterventionKnobDictionaryEntry`
- `ProvisionProgramCrosswalkEntry`

Do:

- Bind selected/admitted provision refs to mapping entries.
- Record knob ids, intervention kind, target population/region/sector, strategic
  response expectations, measurement expectations, crosswalk refs, confidence,
  and mapping provenance.
- Validate that each mapping has an admitted legal authority precondition.
- Validate mapping registry shape with `load_lex_policy_bundle`,
  `LexProvisionMappingRegistry.get_mapping(...)` / `require_mapping(...)`, and
  dictionary/crosswalk checks before any executable compilation.
- Lazy-load `polisyos.lex.interventions` / call `resolve(...)` only if a task
  explicitly compiles a `LexProvisionDirective`; readiness may pass with a
  mapping handoff when compile is out of scope for the current closure case.

Do not:

- Treat a mapping row as proof of legal authority.
- Import heavy intervention compiler at GL module import time.
- Require production intervention mapping artifacts if the legal authority
  closure case does not need executable intervention compilation; use a
  fixture/synthetic mapping seed for readiness of the boundary and record it as
  mapping coverage, not legal corpus authority.

Acceptance:

- `lex_intervention_map` binding succeeds for an admitted provision.
- `lex_intervention_map` binding without a legal authority record fails
  admitted-authority checks.
- Import-laziness test proves GL module does not eagerly import heavy
  intervention compiler dependencies.
- A zero-row production intervention map reports bounded mapping coverage
  instead of failing legal authority closure.

### Task 6 - Consumer Gates and Surfaces

Implement consumer gates:

- Claim registry gate:
  - Builds/validates a runtime claim registry row with GL `selected_norm_refs`,
    `legal_authority_record_refs`, and blockers.
  - Preserves `legal_authority_record_refs` into producer/authority refs, but
    does not rely on claim registry alone to prove legal authority.
- Semantic binding gate:
  - Builds/evaluates semantic binding ledger and preserves legal authority
    grades, fallback refs, selected norm refs, and blocker refs.
  - Fails if selected norms are present without legal authority refs, including
    the existing `semantic_lex_legal_authority_record_missing` issue.
- Argument graph/readiness gate:
  - Builds or validates an argument-graph-compatible major-claim surface when GL
    legal evidence is used.
  - Ensures the claim has evidence, authority rows, and a passing readiness row
    with `readiness_check=layer3_gl_legal_mandate_search_readiness_gate` or a
    registered equivalent.
  - Ensures readiness `authority_refs` include the GL legal authority record,
    threshold/mandate record, and blocker refs where applicable.
  - Treats `argument_graph` as diagnostic/readiness path evidence only; it cannot
    mint claim, legal, projection, publication, or closeout authority.
- S6 mandate gate:
  - Emits `MandateSourceRecord`-compatible rows or references an evaluated
    `MandateLegitimacyRecord` for `Layer2S6BlindSpotPostureInput`-compatible
    consumers.
  - Does not assert S6 overall posture or `pass` unless S6 producer semantics are
    present.
- S7 delegation gate:
  - Feeds mandate record refs into S7 delegation surfaces when responsibility
    routing is needed.
  - Preserves P26 boundaries: human decision integrity remains S7 authority,
    not GL authority.
- S8 value-choice gate:
  - Shows GL mandate refs/disposition are compatible with
    `AuthorizedValueSchedule` / `Layer2S8ValuePostureInput` when legal mandate
    evidence is used for ranked value choices.
  - Fails when GL tries to authorize ranking without S6 mandate pass or when
    mandate source dispositions are candidate/limited.
- PDC compiler/Layer 2 design search gate:
  - Shows legal/mandate refs are compatible with existing PDC input fields and
    projection rows.
- Design constraint gate:
  - Emits legal threshold/mandate boundaries as constraints, limitations,
    blockers, or design-input refs for the design loop.
  - Fails if the legal boundary is consumed as recommendation substance or
    promotion authority.
- G4 promotion gate compatibility gate:
  - Emits the exact GL refs/blockers/statuses future G4 needs to evaluate
    shadow-to-governed promotion.
  - Does not claim promotion, `governed_promoted`, or closeout authority in GL.
- Promotion gate handoff:
  - Emits GL-readable refs for future G4/G5 promotion governance.
  - Does not claim promotion authority in GL.

Surfaces:

- Add `layer3_gl_legal_mandate_audit_surface.json`.
- Add `layer3_gl_public_export_projection_refs.json` with projection-only refs
  and safe disclosure status, produced through
  `Layer3GLPublicExportProjectionRefSurface`.
- Public export must either implement and test a GL-specific projection hook in
  `build_public_export_bundle(...)` or mark the GL public projection refs as
  reference-only and outside that runtime public bundle. The chosen mode must be
  explicit in the readiness manifest; a reference-only projection cannot register
  or claim a `public_export_bundle` adapter path. In both cases raw legal rows,
  source quotes, provision text, query ledgers, and unredacted authority payloads
  stay out of PUBLIC output.
- Add reference docs explaining:
  - search vs authority;
  - false-abstention recall guard;
  - legal time roles;
  - amendment lineage;
  - mandate/S6/S7 handoff;
  - mandate/S8 value-choice handoff;
  - `lex_intervention_map` authority boundary.

Acceptance:

- Consumer gate artifacts pass.
- Argument graph/readiness consumer gate passes for any major claim that uses GL
  evidence, or GL explicitly declares the claim outside the argument-graph
  closure surface.
- S8 value-choice gate passes or is explicitly out of scope for non-ranking GL
  closure cases.
- Design constraints and G4 promotion-gate compatibility artifacts pass.
- Public/projection artifacts do not include raw legal payloads as authority and
  do not overclaim a runtime public-export hook that has not been implemented.
- Projection refs have a typed DTO/builder and a manifest mode that matches the
  adapter registry path.
- MACHINE/EXPERT surfaces expose enough refs/status to audit GL decisions.

### Task 7 - Adapter Registry, Readiness CLI, and Generated Artifact Registration

Implement adapter and artifact registration.

Adapter contract registry must include paths such as:

- `layer3_gl_l3_legal_kg_to_search_ledger`
- `layer3_gl_search_ledger_to_norm_candidate_binding`
- `layer3_gl_l3_legal_kg_to_authority_facet_binding`
- `layer3_gl_legal_requirement_to_legal_authority_report`
- `layer3_gl_authority_facet_binding_to_legal_authority_report`
- `layer3_gl_legal_authority_report_to_threshold_authority_record`
- `layer3_gl_legal_authority_report_to_mandate_authority_record`
- `layer3_gl_temporal_lineage_to_competence_record`
- `layer3_gl_amendment_lineage_to_reissue_gate`
- `layer3_gl_authority_record_to_lex_intervention_map_binding`
- `layer3_gl_authority_record_to_claim_registry`
- `layer3_gl_authority_record_to_argument_graph_readiness`
- `layer3_gl_mandate_record_to_s6_s7_consumer_gate`
- `layer3_gl_mandate_record_to_s8_value_choice_consumer_gate`
- `layer3_gl_authority_record_to_design_constraints`
- `layer3_gl_authority_record_to_g4_promotion_gate_input`
- `layer3_gl_audit_surface_to_public_projection_refs`
- one of:
  - `layer3_gl_public_projection_refs_to_public_export_bundle` when a GL hook is
    implemented and tested in `build_public_export_bundle(...)`;
  - `layer3_gl_public_projection_refs_to_reference_only_surface` when GL public
    projection refs are outside the runtime public-export bundle.

The registry must include exactly one public projection route matching the chosen
manifest mode. A reference-only projection is an audit/reference surface, not a
runtime PUBLIC bundle capability.

Readiness manifest drift keys should include:

- `schema_version`
- `rule_version`
- `g0_dependency_status`
- `g1_context_status`
- `g2_context_status`
- `g3_context_status`
- `gl_l3_legal_kg_route_status`
- `gl_l3_legal_kg_table_count`
- `gl_l3_legal_kg_index_coverage_status`
- `gl_search_ledger_count`
- `gl_query_trace_count`
- `gl_search_recall_freshness_status`
- `gl_l5_calibration_binding_status`
- `gl_l5_calibration_binding_count`
- `gl_legal_requirement_binding_count`
- `gl_authority_facet_binding_status`
- `gl_authority_facet_binding_count`
- `gl_norm_candidate_binding_count`
- `gl_legal_authority_report_status`
- `gl_selected_norm_ref_count`
- `gl_legal_authority_record_count`
- `gl_threshold_authority_record_count`
- `gl_mandate_authority_record_count`
- `gl_temporal_competence_status`
- `gl_amendment_lineage_status`
- `gl_reference_resolution_status`
- `gl_lex_intervention_map_binding_status`
- `gl_claim_registry_consumer_gate_status`
- `gl_semantic_binding_consumer_gate_status`
- `gl_argument_graph_readiness_consumer_gate_status`
- `gl_s6_mandate_consumer_gate_status`
- `gl_s7_delegation_consumer_gate_status`
- `gl_s8_value_choice_consumer_gate_status`
- `gl_design_constraint_consumer_gate_status`
- `gl_g4_promotion_gate_consumer_gate_status`
- `gl_public_export_projection_status`
- `gl_public_export_projection_hook_status`
- `gl_public_export_projection_mode`
- `gl_public_export_projection_ref_surface_status`
- `gl_inventory_surface_status`
- `gl_reference_docs_status`
- `gl_invariant_readiness_check_registration_status`
- `gl_adapter_semantic_loss_status`
- `gl_governance_throughput_status`
- `gl_conformance_status`
- `gl_adapter_contract_registry_status`
- `gl_adapter_contract_path_count`
- `gl_health_metric_ids`

Acceptance:

- CLI `--write` persists all expected JSON/TOML artifacts.
- CLI without `--write` validates persisted artifacts and reports missing paths.
- Repo-quality tests enforce expected artifact set, required write paths,
  manifest keys, issue-code dictionary, generated-artifact registration,
  inventory registration, reference/public-surface docs, and runtime drift.
- Adapter registry tests enforce that the GL public projection mode and adapter
  path agree; `reference_only` mode must not register a public-export-bundle
  route.
- If GL is referenced by production invariant rows, tests prove its readiness
  check id is registered in the invariant validator instead of appearing as an
  unknown readiness check.

### Task 8 - Conformance, Performance, and Closeout Verification

Add conformance negatives:

- `retrieved_legal_text_without_temporal_authority`
- `text_search_hit_used_as_authority`
- `applicability_report_internal_lex_kg_fallback_used_for_closure`
- `inline_runtime_candidate_norms_used_for_gl_closure`
- `internal_legal_requirement_compile_used_for_gl_closure`
- `legal_authority_report_missing_gl_producer_artifact_ref`
- `compiler_default_authority_type_treated_as_lex_authority`
- `authority_facet_binding_missing`
- `text_derived_authority_facet_overclaimed`
- `llm_legal_summary_used_as_authority`
- `generic_topic_match_laundered_as_authority`
- `selected_norm_without_claim_level_legal_authority`
- `jurisdiction_fallback_without_governed_config`
- `threshold_row_without_source_norm`
- `threshold_authority_without_hydrated_lex_rule_thresholds_row`
- `threshold_unit_or_operator_unparsed`
- `missing_effective_time`
- `unresolved_temporal_status`
- `partial_temporal_row_promoted_to_authority`
- `stale_amendment_lineage`
- `reference_resolution_unresolved`
- `missing_l5_calibration_binding`
- `lex_intervention_map_used_as_authority`
- `mandate_record_without_source_refs`
- `mandate_pass_forked_without_s6_evaluation`
- `s6_s7_consumer_missing`
- `argument_graph_readiness_consumer_missing`
- `argument_graph_readiness_ref_missing`
- `s8_value_choice_consumer_missing_when_ranking_claimed`
- `design_constraint_consumer_missing`
- `g4_promotion_gate_consumer_missing`
- `search_no_hit_with_recall_seed_miss`
- `stale_legal_index_claimed_as_domain_ceiling`
- `heavy_intervention_import_at_module_load`
- `intervention_registry_resolve_used_in_readiness_import_path`
- `vector_route_assumed_without_index_artifact`
- `public_export_hook_overclaimed`
- `public_projection_raw_legal_payload_leak`
- `public_projection_mode_mismatch`
- `public_projection_ref_surface_missing`
- `generated_artifact_family_missing`
- `inventory_surface_missing`
- `reference_index_missing`
- `public_surface_visibility_missing`

Performance/scaling checks:

- No full `lex_provisions` or `lex_normative_ready_facts` eager load in GL
  request path.
- Bounded SQL and `LIMIT` in readiness/search probes.
- Query trace records row counts and budgets.
- Unit tests use tiny DuckDB fixtures; production KG coverage uses bounded
  introspection/sampling.
- Search route uses DuckDB/HNSW/structured APIs, not Python O(n) scans.
- Health metric delta records `adapter-semantic-loss` and
  `governance-throughput` for GL, in addition to the cross-slice
  recall/freshness metric.

Closeout commands:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_gl_legal_mandate_search.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_gl_readiness.py
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_gl_readiness_cli.py
uv run python tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py --write --output-format json
uv run python tools/quality/validation/check_policy_design_case_layer3_gl_readiness.py --output-format json
uv run polisyos-tools architecture guardrails check
python3 -m tools.cli workspace verify --backend-only
```

Acceptance:

- All targeted GL tests pass.
- Readiness CLI returns pass after `--write`.
- Architecture guardrails pass.
- Backend verification passes or any failure is unrelated and explicitly
  documented.

## Issue Codes

The runtime and CLI should expose at least these issue codes:

- `layer3_gl_g0_dependency_not_ready`
- `layer3_gl_l3_legal_kg_missing`
- `layer3_gl_l3_legal_kg_route_not_bound`
- `layer3_gl_l3_legal_kg_index_coverage_failed`
- `layer3_gl_noncanonical_legal_route_used_for_closure`
- `layer3_gl_search_ledger_missing`
- `layer3_gl_query_trace_missing`
- `layer3_gl_search_recall_seed_miss_blocks_domain_ceiling`
- `layer3_gl_stale_legal_index_blocks_domain_ceiling`
- `layer3_gl_false_abstention_recall_unmeasured`
- `layer3_gl_text_search_used_as_authority`
- `layer3_gl_read_api_text_search_used_for_closure`
- `layer3_gl_applicability_report_internal_lex_kg_fallback_used_for_closure`
- `layer3_gl_runtime_candidate_norm_snapshot_used_for_closure`
- `layer3_gl_internal_requirement_compile_used_for_closure`
- `layer3_gl_legal_requirement_producer_artifact_ref_missing`
- `layer3_gl_retrieved_legal_text_used_as_authority`
- `layer3_gl_llm_legal_summary_used_as_authority`
- `layer3_gl_legal_requirement_binding_missing`
- `layer3_gl_legal_requirement_missing_authority_types`
- `layer3_gl_compiler_default_authority_type_unmarked`
- `layer3_gl_compiler_default_authority_type_laundered`
- `layer3_gl_jurisdiction_fallback_policy_missing`
- `layer3_gl_authority_facet_binding_missing`
- `layer3_gl_kg_authority_facets_assumed_present`
- `layer3_gl_text_derived_authority_facet_overclaimed`
- `layer3_gl_authority_facet_binding_semantic_loss`
- `layer3_gl_norm_candidate_binding_missing`
- `layer3_gl_l5_calibration_binding_missing`
- `layer3_gl_norm_temporal_window_missing`
- `layer3_gl_norm_source_authority_missing`
- `layer3_gl_reference_resolution_unresolved`
- `layer3_gl_amendment_lineage_missing`
- `layer3_gl_stale_amendment_lineage`
- `layer3_gl_threshold_authority_record_missing`
- `layer3_gl_threshold_row_not_hydrated`
- `layer3_gl_thresholds_json_used_as_authority`
- `layer3_gl_threshold_unit_or_operator_unparsed`
- `layer3_gl_partial_temporal_row_promoted_to_authority`
- `layer3_gl_mandate_authority_record_missing`
- `layer3_gl_mandate_source_refs_missing`
- `layer3_gl_s6_mandate_semantics_forked`
- `layer3_gl_temporal_competence_record_missing`
- `layer3_gl_legal_authority_report_missing`
- `layer3_gl_selected_norm_without_legal_authority_record`
- `layer3_gl_lex_intervention_map_missing`
- `layer3_gl_lex_intervention_map_used_as_authority`
- `layer3_gl_claim_registry_consumer_gate_missing`
- `layer3_gl_semantic_binding_consumer_gate_missing`
- `layer3_gl_argument_graph_readiness_consumer_gate_missing`
- `layer3_gl_argument_graph_readiness_ref_missing`
- `layer3_gl_s6_mandate_consumer_gate_missing`
- `layer3_gl_s7_delegation_consumer_gate_missing`
- `layer3_gl_s8_value_choice_consumer_gate_missing`
- `layer3_gl_s8_ranking_authorized_without_mandate_pass`
- `layer3_gl_pdc_compiler_consumer_gate_missing`
- `layer3_gl_design_constraint_consumer_gate_missing`
- `layer3_gl_g4_promotion_gate_consumer_gate_missing`
- `layer3_gl_public_raw_legal_payload_leak`
- `layer3_gl_public_export_hook_overclaimed`
- `layer3_gl_public_projection_ref_without_projection_policy`
- `layer3_gl_public_export_projection_mode_mismatch`
- `layer3_gl_public_export_projection_ref_surface_missing`
- `layer3_gl_invariant_readiness_check_unknown`
- `layer3_gl_promotion_authority_leak`
- `layer3_gl_closeout_authority_leak`
- `layer3_gl_adapter_contract_registry_missing`
- `layer3_gl_adapter_registry_summary_only`
- `layer3_gl_adapter_unknown_path`
- `layer3_gl_adapter_semantic_loss`
- `layer3_gl_manifest_runtime_drift`
- `layer3_gl_persisted_artifact_missing`
- `layer3_gl_generated_artifacts_family_missing`
- `layer3_gl_inventory_surface_missing`
- `layer3_gl_reference_index_missing`
- `layer3_gl_public_surface_visibility_missing`
- `layer3_gl_import_laziness_violation`
- `layer3_gl_intervention_resolve_used_in_readiness_import_path`
- `layer3_gl_vector_index_assumed_without_artifact`

## Acceptance Checklist

Implementation is ready to claim GL complete only when:

- [ ] GL runtime module exists with strict DTOs and no eager heavy imports.
- [ ] GL readiness CLI exists and follows G1/G2/G3 write/validate conventions.
- [ ] Canonical L3 Legal KG route is bound and checked.
- [ ] Search ledgers/query traces persist replayable frontier and no-hit
      evidence.
- [ ] Search recall/freshness prevents false-abstention/domain-ceiling
      laundering.
- [ ] Internal applicability-report KG fallback and read-API text search cannot
      close GL.
- [ ] L5 calibration bindings are present or explicitly limit authority.
- [ ] Legal requirements are compiled and persisted as claim-level bindings.
- [ ] Legal authority reports receive explicit GL requirement specs and GL
      producer artifact refs; internal adapter compilation cannot close GL.
- [ ] Authority facet bindings exist for passing candidates and distinguish
      explicit, derived, governed, compiler-default, and missing facets.
- [ ] Lex KG rows become candidate norms only through typed bindings.
- [ ] Legal authority report is reused as the authority waist.
- [ ] Threshold records hydrate parsed fields from `lex_rule_thresholds`, not
      search-result summaries.
- [ ] At least one threshold or mandate authority record passes.
- [ ] Mandate records either reference S6 evaluation or remain S6-compatible
      source handoffs.
- [ ] Temporal competence and amendment lineage are explicit and replayable.
- [ ] `lex_intervention_map` binding is present when an executable
      intervention handoff is claimed, and it cannot mint legal authority.
- [ ] Claim registry and semantic binding consume selected/legal authority refs.
- [ ] Argument graph/readiness consumes GL legal authority refs for major claims
      using GL evidence.
- [ ] S6/S7/S8 mandate consumer gates receive mandate refs without taking over
      GL.
- [ ] Design-constraint and G4 promotion-gate compatibility consumers receive
      legal boundary refs without promotion/closeout authority leakage.
- [ ] Public/export/projection surfaces expose audit refs only, include a typed
      projection-ref surface, and do not claim a runtime public-export hook
      unless one is implemented and tested.
- [ ] Public projection mode matches adapter registry: public-export-bundle hook
      or reference-only surface, never both.
- [ ] Generated artifacts are persisted and registered in generated-artifact
      TOML/docs, policy-design-case inventory, and reference/public-surface docs
      where required by local patterns.
- [ ] Any production-invariant GL readiness check id is registered before use.
- [ ] Conformance negatives fail closed.
- [ ] Targeted tests, readiness CLI, architecture guardrails, and backend verify
      pass or failures are explicitly unrelated.

## Non-Negotiables

- Use canonical L3 Legal KG for closure; no fixture/inline candidate substitute.
- Do not close GL through `build_normative_applicability_report`'s internal
  read-API/text KG fallback.
- Do not close GL through inline `runtime_candidate_norms`.
- Search is discovery, not authority.
- Legal authority is claim-level, time-scoped, source-scoped, and
  purpose-scoped.
- No lowering of evidence or mandate floors.
- No threshold authority from fact summaries, `thresholds_json`, or helper search
  output without hydrated `lex_rule_thresholds` rows.
- No authority type, actor, instrument, implementation-authority, or
  fiscal-authority assumption from KG rows without a replayable
  authority-facet binding.
- No compiler-default authority type masquerading as Lex-discovered authority.
- Missing effective time, missing source authority, unresolved reference,
  stale amendment lineage, partial/conflict temporal status for a passing
  authority row, or unmeasured recall fails closed.
- No live embedding/network dependency for readiness.
- No Python full-corpus scans or eager loading of millions of Lex rows.
- No `lex_intervention_map` authority laundering.
- No generic legal topic/country/domain match authority laundering.
- No LLM legal reading authority laundering.
- No PUBLIC raw legal payload authority leak.
- No public-export-bundle adapter path unless the GL-specific hook is implemented
  and tested; otherwise GL projection refs stay explicitly reference-only.
- No S6/S7 responsibility laundering or S8 ranked-value authorization without
  existing S8 mandate/value-choice checks.
