---
plan_id: layer3-g2-causal-forecast-search-engine
title: "G2 - Causal/Forecast Search Engine"
type: slice-plan
status: completed
created: 2026-06-07
revised: 2026-06-08
slice: G2
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/plans/active/layer3-slices/G1-data-grounding-existing-assets-acquisition.md
  - docs/adr/0175-layer3-grounding-subordination-discipline.md
  - architecture/policy_design_case/layer3_g0_readiness_manifest.json
  - architecture/policy_design_case/layer3_discovery_search_discipline.json
  - architecture/policy_design_case/layer3_engineering_quality_check.json
  - architecture/policy_design_case/layer3_health_metric_ledgers.toml
  - architecture/policy_design_case/layer3_g1_readiness_manifest.json
  - architecture/policy_design_case/layer3_g1_grounded_source_contracts.json
  - architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json
  - architecture/policy_design_case/layer3_g1_l1_l5_l6_index_coverage.json
  - architecture/policy_design_case/layer3_g1_search_recall_freshness.json
  - architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json
  - architecture/policy_design_case/layer2_floor_governance.toml
  - production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
  - production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/manifests/graph_index.json
  - production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/manifests/qc.json
  - production_data/policyos_academic_runtime_slim_20260411T112032Z/meta/source_lineage.json
cells_closed:
  - layer3.causal_forecast_search_adapter
  - layer3.g2_l2_skg_search_ledgers
  - layer3.g2_foundry_method_search
  - layer3.g2_method_validity_transport_limits
  - layer3.g2_s10_prerequisite_bindings
  - layer3.g2_forecast_support_bindings
  - layer3.g2_s10_consumer_bridge
  - layer3.g2_forecast_authority_surface
layer_cells_advanced:
  - layer3.causal_forecast_search_adapter
  - layer3.g2_l2_skg_search_ledgers
  - layer3.g2_foundry_method_search
  - layer3.g2_method_validity_transport_limits
  - layer3.g2_s10_prerequisite_bindings
  - layer3.g2_forecast_support_bindings
  - layer3.g2_s10_consumer_bridge
  - layer3.g2_forecast_authority_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g2_causal_forecast_readiness_gate
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G2 - Causal/Forecast Search Engine

## For agentic workers

This is an executable slice spec, not strategy. Follow it red-first. Every reuse
claim below is grounded in current files and production artifacts. G2 starts
after accepted G1: consume G1's grounded `SourceContract` bindings,
search-ledger discipline, real-L1 rule, recall/freshness bar, hardcode strangle
discipline, and engineering-quality gate. G2 adds a causal/forecast search
adapter over the real L2 academic SKG and Foundry method registry, then emits
bounded S10 `ForecastSupport` records. Do not create a second S10 contract, do
not treat search hits as causal authority, and do not call a no-hit a domain
ceiling while L2 recall/freshness is unresolved.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.
`expected_open_cell_count: 0` refers to the existing Layer 2 cluster-map/open-cell
model that G2 does not mutate. Layer 3 G2 progress is measured by causal/forecast
search readiness, SKG coverage, method-registry coverage, `ForecastSupport`
validity, S10 prerequisite binding, S10 bridge consumption, conformance
negatives, search recall/freshness, and health ledgers.

## Intro

G2 builds the first Layer 3 causal/forecast search engine. Given a G1-grounded
source-contract binding and a typed intervention/outcome request, G2 searches
the real L2 academic claim graph and the real Foundry method registry, records a
replayable search frontier, validates candidate claims/methods through adapter
contracts, proves the S10 prerequisite spine, and translates only
conformance-valid candidates into existing S10 `ForecastSupport`,
`ForecastCalibrationRecord`, and `PredictionAuthorityEnvelope` records.

The L2 search target is the production academic runtime snapshot:

- `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`
- `ac_causal_claims`: 7,868 curated causal claims.
- `ac_causal_claims_raw`: 137,589 raw causal claims, useful for recall and audit,
  not authority.
- `ac_skg_edges`: 7,607 canonical causal edges.
- `ac_skg_edge_evidence`: 7,868 edge-to-claim evidence links.
- `ac_skg_transport_scores`: 7,607 target-context transport scores.
- `ac_parameter_estimates`: 62,248 numeric estimates.
- `ac_skg_parameters`: 51,908 SKG parameter rows.
- `ac_skg_contested_edges`: 723 contested edge records.
- `academic/ac_work_index.hnsw` and `academic/ac_work_embeddings.npz`: search
  substrate for semantic retrieval where text/variable matching is insufficient.

G2 must hit that SKG path directly through the existing read-only SKG query API
where it preserves real table refs, or through index-backed DuckDB SQL where G2
needs additional replay fields. It can also use the existing HNSW/vector assets
for candidate discovery. A capability-index L2 view, pinned UA-MSME fixture,
manually curated claim list, or compiler output may be used as
transition/acquisition context, but cannot be the L2 search path or the basis for
L2 coverage pass. This is the G2 analogue of the G1 `ds_metric_bindings` fix:
the actual corpus is available, so a construct-scoped derivative is an
unjustified surrogate.

G2 does not promote policy recommendations, does not close useful-design credit,
does not provide legal mandate authority, does not produce proof-carrying
analytics authority, and does not grant large-scale equilibrium authority.
Contested, simulation-only, historical-prior, uncalibrated, or transported
evidence remains explicitly limited through S10 tiers and authority boundaries.

## Closure Contract

Source of truth: roadmap G2 closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`,
especially the G2 "Causal/Forecast Search Engine" slice.

G2 must deliver:

1. **G1 dependency gate** proving G1 readiness, real L1 DCAT coverage,
   SourceContract grounding, G1 search recall/freshness, hardcode strangle,
   conformance, and engineering quality are green before G2 emits support.
2. **Canonical L2 SKG search route** over
   `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`,
   reusing the public `polisyos.data_forge.read_api.academic.SKGQuery` facade
   for edge support, transport, parameter, prior, and variable-resolution paths
   where possible, and adding direct DuckDB queries only for missing G2 replay
   or coverage fields. Construct `SKGQuery` with
   `db_path=.../academic/graph/scholar_knowledge.duckdb` and
   `index_dir=.../academic`; the HNSW/NPZ assets live beside `graph/`, not in
   it. The route must cover `ac_skg_edges`,
   `ac_skg_edge_evidence`, `ac_causal_claims`, `ac_parameter_estimates`,
   `ac_skg_transport_scores`, `ac_skg_contested_edges`, `ac_skg_variables`,
   `ac_skg_variable_synonyms`, and SKG manifests. It must record table counts,
   selected indexes, snapshot hash, SKG version, query predicates, cutoff,
   result-set cardinality, and a query trace for every `SKGQuery` or direct-SQL
   call consumed by G2 authority.
3. **Optional semantic L2 retrieval** over the existing HNSW/work-embedding
   assets when lexical/canonical-variable search alone would under-recall. HNSW
   retrieval is candidate discovery only; DuckDB SKG rows and adapter validation
   remain the evidence authority path. Exact canonical DuckDB/SKG requests must
   not be blocked by HNSW freshness unless the request or recall seed invoked the
   semantic retrieval path. G2 must not build a new text-embedding generator or
   parallel vector retriever unless an existing repo producer is found and
   replayed; because `ScholarKnowledgeStore.search_works_by_vector(...)` accepts
   a precomputed query vector, any HNSW call without a replayed query-vector
   producer is pseudo-semantic retrieval and must fail or be recorded as
   `not_required_for_request`.
4. **Replayable G2 search-ledger records** for every authority-relevant L2 SKG
   search, HNSW search, Foundry method-registry search, selected candidate,
   rejected candidate, no-hit, budget cutoff, and abstention. Search ledgers are
   control-plane evidence, never `ForecastSupport`.
5. **L2 recall/freshness report** with known-groundable seeds against real SKG
   rows and manifest/index freshness checks. A false no-hit caused by stale index
   or poor recall is `search_ceiling_repair_required`, not domain ceiling.
   Vector/HNSW freshness is required only for seeds or requests that depend on
   semantic retrieval; canonical DuckDB freshness is always required.
6. **Foundry method-registry search route** over built-in catalog bootstrap,
   extension discovery, `MethodRegistry`, registry snapshots, and
   method-signature tags/slots/data modalities. G2 must bootstrap causal,
   forecasting, econometric, sensitivity, validation, and all installed method
   families through existing `ensure_*_methods_registered` /
   `ensure_all_methods_registered` paths, refresh entry-point/dev discovery
   where applicable, record coverage, search for method families compatible with
   the G1 data substrate and L2 causal request, then validate selected methods
   through the existing Foundry method-quality registry and reports. Do not
   hardcode a short list of causal method FQNs as the closure mechanism.
7. **Method validity and transport-limit declaration** reusing
   `MethodValidityRequirementSpec`, Foundry requirement selection,
   `build_foundry_method_report`, optional CAS persistence helpers where an
   artifact store is available, causal/statistical validity reports where
   available, identification requirements, transportability limits,
   sensitivity/uncertainty refs, and rejected-method reasons. Foundry reports
   are authoritative for method validity only; they are not academic support,
   legal authority, source-family satisfaction, or claim authority.
8. **Adapter admission records** for the L2 SKG search adapter, Foundry method
   search adapter, and S10 translation adapter. Default maturity is
   `fail_closed` or `predictive`; `calibrated` is allowed only when observable
   calibration passes and the S10 authority envelope remains bounded.
9. **Adapter translation into existing S10 records** through
   `build_forecast_support`, `build_forecast_calibration_record`,
   `verify_prediction_authority_envelope`, and
   `summarize_forecast_support_integrity`. G2 may wrap these records for Layer 3
   audit, but the waist artifact remains S10 `ForecastSupport`.
10. **Concept-alignment record** tying G1 `SourceContract` refs and target
    outcomes to SKG cause/effect variables, SKG parameter refs, Foundry method
    input/output slots, and S10 target-outcome refs through the existing
    concept-spine / semantic-binding substrate (`ProducerSpineReadContext`,
    `ProducerSpineBindingFields`, governed namespace refs, reconciled concepts,
    and producer handshakes) wherever applicable. G2 must not create a parallel
    concept/status lattice. Ambiguous, proxy-only, conflicting, or unmatched
    alignment must downgrade or block support rather than silently passing as
    causal grounding.
11. **S10 prerequisite binding** proving the S10 spine is present before G2 emits
    any posture: S5 forecast-support ref, S6 firewall refs, S8 value-provenance
    and tradeoff refs, design graph, prediction/policy contexts, candidate,
    baseline, alternative designs, horizon, uncertainty refs, and
    authority-boundary denials. G2 may propose a bounded tier, but existing S10
    derivation/validation remains authoritative; a mismatch is a G2 defect, not
    an override.
12. **Observable-subset calibration only where observable**. `observable_calibrated`
   requires a calibration denominator, observed outcome refs, credible evaluation
   evidence, counterfactual credibility, governed threshold, time-role semantics,
   and uncertainty interval refs. Non-observable, transported, contested,
   historical-prior, or simulation-only cases must be tiered honestly.
13. **S10 bridge/consumer route** producing `Layer2S10ForecastPostureInput` rows
    that the S2 shadow loop can consume without recommendation, claim,
    closeout, or publication authority. G2 should reuse the existing PDC S10
    injection path rather than rerunning S2 internals. Current W12D/S10 already
    proves one full first-case S2 posture plus lightweight forecast refs for the
    remaining cases; G2 should keep that cost-proportional pattern instead of
    forcing full S2 search for every corpus case.
14. **Grounded forecast handoff record** consumable by G4/G5 as a grounded
    forecast contract reference. This is not promotion, useful-design credit, or
    conversion authority; it preserves the forecast support, limitations,
    maturity, and `may_not_use_for` envelope for later promotion/conversion gates.
15. **Forecast tier and uncertainty surface** across PUBLIC/REVIEWER/EXPERT/MACHINE.
    PUBLIC/REVIEWER may use existing S10 projection semantics for tier,
    uncertainty, limitations, and `may_not_use_for`; only raw internal ledgers
    and low-level search diagnostics may be explicitly `surface_out_of_scope` for
    those audiences. The surface must expose search frontier refs,
    source-contract refs, SKG claim/edge/parameter refs, method validity refs,
    calibration status, transport limitations, uncertainty refs,
    contested/equilibrium caveats, and `may_not_use_for`.
16. **All five Layer 3 health deltas** updated from the G2 perspective:
    envelope expansion, adapter semantic loss, governance throughput,
    demand-pull versus abstention, and search recall/freshness.
17. **Conformance and negative controls** proving no search-hit laundering,
    no capability-index-as-L2 closure, no over-claimed forecast tier, no
    uncalibrated observable promotion, no transported estimate without
    limitation, no simulation/historical prior promotion, no hidden uncertainty,
    no large-scale equilibrium authority, no claim/recommendation/useful-design
    authority leak, no method-registry hardcode, no stale-index domain ceiling,
    and no raw SKG output without adapter validation.

Target done path: the same construct-agnostic causal/forecast mechanism handles
at least two request shapes, discovers a correctly-added synthetic SKG edge or
method fixture without code changes, and emits at least one real bounded
`ForecastSupport` or honest search/domain ceiling record from the current SKG
and G1-grounded substrate. If it emits `observable_calibrated`, observable
calibration must pass. If it emits `transported_limited`, every transported
claim must carry transport limitations and uncertainty refs. If current evidence
cannot support a governed tier, G2 closes with honest bounded tiers or
abstention, not a forced forecast.

Honesty escape path: if L2 SKG search, HNSW fallback where required, Foundry
method search, G2 search ledgers, recall/freshness, method validity checks,
engineering quality, and conformance negatives all pass, but the current
evidence cannot validly produce any `ForecastSupport` above
`simulation_only_advisory`, `historical_prior_context`, `transported_limited`, or
blocked/contested status, G2 may close as `causal_forecast_domain_ceiling` with
explicit reasons. If recall, freshness, canonical L2 coverage, method-registry
search, ledger completeness, or engineering quality is unhealthy, the outcome is
`search_ceiling_repair_required`.

## Scope Boundaries

In scope:

- Implement the G2 causal/forecast search and adapter layer in
  `runtime/quality`.
- Consume G1 grounded `SourceContract` bindings and G1 search-readiness artifacts
  as hard prerequisites.
- Search the real L2 SKG snapshot in DuckDB and, where needed, the existing
  academic HNSW/vector assets for candidate discovery.
- Search the real Foundry method registry through existing discovery/registry
  APIs and validate method choices through the existing method-quality registry.
- Persist G2 search ledgers, SKG coverage, method-registry coverage,
  method-validity/transport declarations, forecast-support bindings,
  S10 prerequisite bindings, calibration reports, authority envelopes,
  conformance report, health deltas, audit surface, and readiness manifest.
- Translate valid candidates into existing S10 records and a S10 posture input
  bridge consumed by the Layer 2 design-search path.
- Record search no-hits, candidate rejections, calibration failures, transport
  limits, contested edges, equilibrium caveats, and non-observable downgrades as
  first-class audit data.
- Add known-groundable seed recall/freshness and free-growth fixtures over the
  real SKG and Foundry method registry.
- Add engineering-quality checks: DuckDB/index-backed search, HNSW use where
  appropriate, lazy/streaming reads, strict Pydantic DTOs, deterministic replay,
  no broad fail-open exception handling, and no eager full-corpus scan.
- Add negative controls for authority boundaries, S10 tier constraints, SKG
  search control-plane boundaries, Foundry method validity, and W12D/S2 consumer
  behavior.

Out of scope:

- No G4 promotion or production authority.
- No G5 proving-ground conversion or useful-design credit.
- No GL legal mandate or temporal competence authority.
- No G3 proof-carrying analytics search path. G2 may preserve refs needed by
  S10/S11, but `ProofCarryingAnalyticsRecord` production belongs to G3.
- No large-scale equilibrium authority. Equilibrium-contested cases remain
  blocked or advisory until a future calibrated system-dynamics path exists.
- No live network acquisition or mutation of `production_data` assets.
- No new parallel academic graph, method registry, or S10 contract.
- No capability-index, fixture, compiler-derived claim view, or hand-curated
  list as a substitute for real L2 SKG search while
  `scholar_knowledge.duckdb` is available.
- No direct PDC back-import from subordinate engines. G2 runtime code stays in
  `runtime/quality` and consumes PDC-facing DTOs through public/canonical
  boundaries.
- No claim that an L2 search hit itself is causal support. Search hits become
  support only through adapter validation, method validity, calibration/transport
  checks, S10 construction, and authority-envelope verification.
- No blanket full backend verification on a local MacBook unless explicitly
  requested; use targeted tests for this slice.

## Pattern Pass

| Pattern | G2 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | New G2 schemas exist but no search producer, persisted artifacts, S10 bridge, or negative tests prove capability. | Add producer functions, persisted G2 artifacts, S10 posture consumer bridge, validator, and negative tests. |
| P02 thin orchestration | SKG search, Foundry methods, and S10 contracts coexist but do not exchange binding artifacts. | Create explicit G2 binding records from G1 SourceContract + SKG search + method validity into S10 `ForecastSupport`; test consumption by S10/S2 posture path. |
| P03 hidden internal richness | Calibration and transport diagnostics are internal JSON with no audit surface. | Register all-audience tier/uncertainty surface plus EXPERT/MACHINE audit details; expose tier, uncertainty, calibration status, limitations, denied uses, and replay refs at the right audience level. |
| P04 status lattice gap | Local G2 statuses conflict with S10 forecast tiers, G1 grounding status, or Layer 2 design-search status. | Define local G2 statuses as wrappers around existing S10 dispositions; test mixed outcomes and no useful-design credit. |
| P05 authority dilution | `ForecastSupport` is mistaken for recommendation, claim, closeout, or publication authority. | Every G2/S10 artifact carries purpose-scoped `authority_boundary` and full `may_not_use_for`; validator blocks leaks. |
| P07 rule replay gap | Forecast tier cannot be replayed after SKG, method, calibration, or rule changes. | Store schema/rule versions, SKG snapshot hash/version, query predicates, method registry refs, calibration threshold refs, and time roles. |
| P08 time-role conflation | Prediction time, observation time, policy effective time, data valid time, SKG build time, and replay time collapse. | Use S10 `ForecastCalibrationRecord` time roles and G2 search-ledger generated/index times; block mismatches. |
| P09 warning lifecycle gap | Missing uncertainty, weak transport, or contested evidence becomes a soft warning while forecast tier still passes. | Treat missing uncertainty, missing transport limits, contested equilibrium, and uncalibrated observable claims as blockers or tier downgrades. |
| P10 semantic adequacy gap | Validator only checks that `ForecastSupport` exists. | Add semantic negatives for search-hit laundering, uncalibrated observable promotion, simulated/historical prior promotion, hidden uncertainty, and unsupported method choice. |
| P12 producer handshake gap | G1 data substrate, SKG variables, and Foundry methods refer to incompatible concepts. | Add request binding fields and semantic-loss report tying G1 `SourceContract`, SKG cause/effect variables, method data affinity, and S10 target outcomes. |
| P13 governance gravity | G2 grows a new causal engine instead of wiring existing SKG, Foundry, and S10. | Reuse real SKG DuckDB/HNSW, Foundry registry/method-quality reports, S10 contracts, and G1 ledgers; add only Layer 3 wrapper records and gates. |
| P14 evidence independence inflation | Multiple SKG edges/parameters from shared articles, methods, or datasets count as independent causal evidence. | Record article/work refs, edge evidence refs, method/design family, and independence collapse reasons; no strength upgrade from raw count alone. |
| P15 LLM speculation laundering | LLM-generated intervention/outcome mapping or method choice becomes forecast authority. | Keep LLM output as candidate mapping only until SKG rows, method registry, and S10 validation support it. |
| P16 epistemic-regime laundering | Forecast tier implies precision under precautionary, contested, or ambiguous regimes. | Preserve regime refs and downgrade/block tier where regime and forecast evidence conflict; no regime-to-forecast shortcut. |
| P17 partial-equilibrium laundering | Local effects are composed into system-effect forecasts without coupling validity. | Use S5/S10 system-effect scope and dynamic/equilibrium caveats; block large-scale equilibrium authority. |
| P18 proxy/measurability laundering | Measurable SKG outcomes or parameter estimates stand in for policy value without disclosure. | Record target outcome refs, proxy/construct loss, S8 value refs, and limitation refs; no welfare claim without S8 provenance. |
| P19 aggregation laundering | Evidence at paper/sample/sector/jurisdiction level is applied to different target scope. | Require jurisdiction, subject granularity, sample/period metadata where available, and aggregation limitation refs. |
| P21 capacity-feasibility laundering | Forecast assumes implementability/capacity not grounded in G1 or later slices. | Preserve state-capacity boundary refs as missing/limited; do not let G2 alone satisfy feasibility. |
| P23 stakes/reversibility laundering | Low-evidence forecast supports high-stakes irreversible design. | Carry stakes/reversibility boundary refs as limitations; no promotion before G4/G5 floors. |
| P24 strategic-response laundering | Pre-policy causal evidence is transported into a changed incentive world. | Require strategic-response caveat refs or block/downgrade forecast tier. |
| P25 search-control laundering | Search frontier, best hit, no-hit, capability-index view, or pinned fixture is projected as exhaustive evidence. | Persist G2 search ledgers and keep them control-plane only; support must pass adapter/S10 validation over real SKG. |
| Spine parallelism | G2 concept labels create a second semantic lattice beside `concept_spine` / `semantic_binding`. | Reuse producer-spine read context, binding fields, governed namespace refs, and producer handshakes; local G2 labels are only candidate/context fields. |
| T7 false abstention | Poor L2 recall or stale SKG/HNSW index creates fake causal domain ceiling. | Known-groundable L2 seeds and index freshness must pass before domain ceiling; otherwise emit `search_ceiling_repair_required`. |
| Rule 12 hardcode fallback | G2 passes because a pinned UA-MSME claim or method list is hardcoded. | Free-growth fixtures over real SKG and Foundry registry; no hardcoded method/claim list as closure path. |
| Engineering quality | Naive O(n) scans or eager loads pass toy cases and fail at SKG scale. | DuckDB predicates/indexes, HNSW retrieval where useful, lazy/streaming reads, bounded result sets, deterministic replay, and perf checks are required. |

## Capability Transition

| Capability | Start label after G1 | Pattern pressure | Target label after G2 |
| --- | --- | --- | --- |
| Causal/forecast search adapter | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing` | P01/P02/P03/P10/P25/T7 | Implemented at `governed_for_forecast_support`: canonical L2/Foundry search producer, replayable ledgers and query traces, S10-valid support or honest ceiling, S10/S2 consumer bridge, G4/G5 handoff ref, all-audience tier/uncertainty surface, conformance, recall/freshness, and negatives. |
| L2 SKG search coverage | `producer_missing`, `verification_missing` | P13/P25/Rule 12 | Implemented coverage report over real `scholar_knowledge.duckdb` tables, manifests, counts, freshness, seeds, query traces, conditionally-required HNSW assets, and free-growth fixture. |
| Foundry method-registry search | `producer_missing`, `verification_missing` | P13/Rule 12 | Implemented search over refreshed registry/discovery metadata, discovery-source coverage, method-quality validation, rejected-method reasons, and no hardcoded FQN closure. |
| S10 prerequisite binding | `bridge_missing`, `consumer_missing`, `semantic_test_missing` | P02/P05/P10/P12 | Implemented prerequisite record proving S5/S6/S8 refs, design/prediction/policy contexts, candidate/baseline/horizon refs, uncertainty refs, and authority-boundary denials exist before G2 builds S10 posture. |
| Concept alignment and ForecastSupport binding | `bridge_missing`, `consumer_missing`, `semantic_test_missing` | P02/P05/P10/P12/P17/P24 | Implemented Layer 3 alignment and binding around existing S10 records with G1 outcome refs, SKG variable/parameter refs, Foundry slot refs, S10 prerequisite refs, authority envelopes, limitations, uncertainty, transport, calibration, S10 posture bridge, and G4/G5 handoff ref. |
| Semantic/concept spine binding | `bridge_missing`, `semantic_test_missing` | P12/P13/P15 | Implemented by reusing existing producer-spine read context, binding fields, concept-spine carrier semantics, and producer handshakes; no parallel G2 concept lattice. |
| Observable calibration and transport-limit report | `artifact_missing`, `verification_missing` | P07/P08/P09/P10/P14 | Implemented report proving observable calibration only where denominator/evidence/time roles pass, and transported evidence carries limitations. |
| Forecast tier audit surface | `surface_missing` | P03/P05 | Implemented PUBLIC/REVIEWER/EXPERT/MACHINE forecast tier and uncertainty surface. Raw search ledgers may be scoped out of PUBLIC/REVIEWER, but tier, uncertainty, limitations, and denied uses must remain visible through existing S10 projection semantics or G2 docs. |

## Code-Grounded Reality

### Existing Substrates

- Roadmap G2 is defined in
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:426`.
- The master corpus table identifies L2 academic SKG as 7.9k curated causal
  claims, transport scores, CIs, contested edges, design-quality tiers,
  parameter estimates, and variable alignments at
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:241`.
- The vision doc defines `ForecastSupport` as a waist artifact and says
  adapters must preserve/loss-check it at
  `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:129`
  and
  `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:245`.
- G1 runtime already provides strict Layer 3 patterns in
  `src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py`: schema/rule
  constants, search requests, search ledgers, SourceContract bindings, coverage,
  recall/freshness, free-growth, engineering quality, conformance, readiness,
  bundle builder, and validator.
- G1 validator already persists and checks artifacts in
  `tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py`.
  G2 should follow the same CLI/write/manifest/runtime-drift pattern: runtime
  bundle, persisted JSON/TOML artifacts, G1 dependency checks,
  selected-key manifest/runtime drift checks, docs/inventory/generated-artifact
  sync, authority posture checks, search-health checks, and `--write` returning
  every expected artifact path.
- G1 generated-artifact documentation is driven from
  `architecture/generated_artifacts.toml` through architecture guardrails. G2
  must add a new TOML `[[family]]` and regenerate/sync the docs; hand-editing
  only `docs/reference/generated-artifacts.md` is not closure.
- S10 contracts already exist in
  `src/polisyos/runtime/quality/design_axes/outcome_prediction.py`:
  `ForecastSupport`, `ForecastCalibrationRecord`, `PredictionAuthorityEnvelope`,
  `ForecastSupportIntegrityReport`, `build_forecast_support`,
  `build_forecast_calibration_record`, `verify_prediction_authority_envelope`,
  and `summarize_forecast_support_integrity`. These validators already enforce
  observable calibration refs, governed uncertainty refs, transported-limit
  refs, validated-local-model refs, and purpose-scoped authority denials.
- PDC design search already accepts S10 posture through
  `Layer2S10ForecastPostureInput` in
  `src/polisyos/pdc/_impl/layer2_design_search.py:404`, exported through the
  public `polisyos.pdc` facade, and projects S10 fields without recommendation
  authority in the S2 path. Its `SearchLedger` records forecast support,
  calibration, posture, status, and authority boundary refs, but its
  deterministic replay key is intentionally narrow. G2 full replay must remain
  in G2 query/method/adapter ledgers, not be inferred from S2.
- Existing S2 tests prove that S2 consumes injected S10 posture without calling
  S10 runtime-quality producers, does not copy `source_contract_ref` or
  `method_validity_ref` into `DesignRecord.ledger_refs`, and exposes those refs
  through expert/machine projections. G2 must inject posture and preserve its
  own audit refs rather than expecting S2 design records to carry full G2
  replay.
- W12D already proves the cost-shaped S10 consumer route: one first-case full S2
  posture with a search ledger and lightweight forecast posture refs for the
  rest of the corpus. G2 should reuse that route shape where possible.
- S11 depends on S10 but is not G2's producer. `ProofCarryingAnalyticsRecord` and
  predictive-knowledge relaxation live in
  `src/polisyos/runtime/quality/design_axes/predictive_knowledge.py` and belong to
  G3/G11-style work, not G2 closure.
- Scholar search models in `src/polisyos/scholar/search/models.py` provide
  budget controls, query traces, claim support links, and evidence bundles. G2
  may reuse these semantics for search-ledger shape, but `WebEvidenceBundle`
  and `ClaimSupportLink` are web/deep-search models with source/snippet
  integrity rules. Do not force them onto local SKG rows unless the required
  source/snippet constraints are satisfied; authority remains the
  SKG/adapter/S10 chain.
- `polisyos.data_forge.read_api.academic.SKGQuery` is the public read API for
  the SKG implementation in
  `src/polisyos/data_forge/domains/academic/knowledge/skg_query.py`. It already
  provides read-only helpers for claim lookup, parameter lookup, exact/family/
  contested edge support, transport-score lookup, variable canonicalization,
  priors, latest SKG version, and SKG snapshot refs. G2 should reuse these
  helpers before writing new SQL, while still preserving replay fields in Layer
  3 ledgers.
- `SKGQuery` delegates vector lookup to `ScholarKnowledgeStore`, whose HNSW/NPZ
  loader expects `index_dir` to point at the academic root containing
  `ac_work_index.hnsw` and `ac_work_embeddings.npz`. Passing the `graph/`
  directory silently removes vector candidates, so G2 coverage must test this
  path explicitly. The vector API takes a precomputed `np.ndarray` query vector;
  without an existing replayed query-vector producer, HNSW is unavailable for
  semantic text retrieval and must be `not_required_for_request` or fail closed.
- `runtime/quality/concept_spine.py` and
  `runtime/quality/semantic_binding.py` already provide governed namespace refs,
  reconciled concepts, producer-spine read contexts, producer-spine binding
  fields, producer handshakes, and semantic binding ledgers across
  Lex/Fabric/Scholar/Foundry/Scientist/final compiler. G2 concept alignment
  should reuse this spine rather than inventing local cause/effect/status
  vocabulary.
- Foundry catalog bootstrap, extension discovery, and registry search are
  available in `src/polisyos/foundry/methods/catalog/__init__.py`,
  `src/polisyos/foundry/extensions/registry.py`,
  `src/polisyos/foundry/methods/discovery.py`, and
  `src/polisyos/foundry/methods/selection/registry.py`. `MethodRegistry` already
  supports deterministic query by namespace, tags, input/output slots, snapshot,
  stats, and registry audit; `MethodSignature` already carries family, variant,
  data modalities, complexity, fidelity, backend, and slot contracts.
- Foundry method-quality validation is available in
  `src/polisyos/foundry/validation/method_quality.py`, including the method
  validity registry, identification requirements, transportability limits, and
  `build_foundry_method_report`. It also exposes CAS persistence helpers and a
  runtime authority envelope: authoritative for method validity/selection,
  runtime assumption gates, method output refs, uncertainty refs, and
  limitations; explicitly not authoritative for legal authority, source-family
  satisfaction, academic support strength, claim support, participation, or
  closeout pass.
- `MethodValidityRequirementSpec` and
  `foundry.methods.selection.requirements.select_method_candidates_for_requirements`
  already encode method family expectations, identification class,
  transportability requirements, uncertainty class, fairness/strategic-response
  needs, runtime assumption gates, uncertainty envelope, limitation refs,
  method output refs, and negative-certificate requirements. G2 should build
  requirement specs and consume selection issues instead of validating methods
  only from loose tags.
- The academic SKG snapshot is local production data, not an external service:
  `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`
  is approximately 2.39GB in this checkout and exposes the tables listed in the
  intro.
- SKG stage manifests and lineage exist at
  `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/manifests/graph_index.json`,
  `production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/manifests/qc.json`,
  and
  `production_data/policyos_academic_runtime_slim_20260411T112032Z/meta/source_lineage.json`.
- W12D already has a Layer 3 gate pattern in
  `tools/quality/validation/run_universal_outcome_corpus.py`: build a
  per-slice context, inject a case-local gate, summarize the gate after cases
  are built, and preserve earlier conversion outcomes. G2 should mirror that
  pattern after G1 instead of inventing a separate corpus runner.

### Existing Weak Spots G2 Must Not Underestimate

- Capability-index currently has a L2 scholar extraction path, but it is a
  derivative transition substrate. G2 closure must query the real SKG directly
  and may use capability-index only for acquisition/consumer hints.
- S10 already has strong tier validators. Reimplementing a parallel forecast
  tier model would create drift and authority confusion.
- S10 derives effective forecast tier from S5/S6 support/origin semantics in
  `build_forecast_support`; a G2-supplied tier cannot be treated as authority if
  it disagrees with existing S10 derivation.
- `Layer2S10ForecastPostureInput` requires S5 forecast-support, S6 firewall,
  S8 value provenance/tradeoff, design graph, prediction/policy context,
  candidate/baseline/horizon, uncertainty, and authority-boundary fields. G2
  must bind or inherit these refs, not fabricate them from SKG hits.
- SKG has curated rows, raw rows, edges, evidence, parameters, transport scores,
  contested edges, variable synonyms, and HNSW assets. A plan that only searches
  `ac_causal_claims` underestimates the data shape.
- SKG rows contain candidate layers, publish blockers, edge support, contested
  support, transport scores, and query-helper annotations. G2 must preserve
  these as limitations/blockers, not strip them during adapter translation.
- Raw SKG count is much larger than curated support. G2 must not inflate causal
  strength by counting raw claims, repeated parameters, or shared works.
- Observable calibration is not guaranteed for most requests. G2 must expect
  limited/blocked tiers as healthy outcomes.
- Foundry method availability is not method validity. A registered method must
  still satisfy family expectations, identification requirements,
  transportability limits, and required surfaces.
- Foundry method discovery is not the same as built-in catalog bootstrap. G2
  should use existing catalog/bootstrap paths for installed methods, then record
  entry-point/dev discovery as coverage inputs where applicable.
- Foundry request filters are limited to real registry fields: namespace, tags,
  input slots, output slots, name patterns, method signature metadata, and
  method-quality requirements. Do not add a new data-affinity taxonomy in G2
  unless it is derived from existing signatures or explicitly scoped as future
  work.
- PDC S2 already consumes S10 posture. G2 should inject a posture input and
  verify consumer behavior, not refactor design-search internals.
- S2's existing forecast posture replay is deliberately consumer-facing and
  narrow. It is enough to prove S2 saw S10 posture; it is not enough to replay
  SKG predicates, Foundry requirement selection, method-report authority, source
  contracts, or G2 adapter decisions.
- W12D should not become a full-search stress test for every case by accident.
  Existing S10/S11 route tests use one full first-case S2 proof and lightweight
  posture refs elsewhere; G2 should preserve that shape unless a later W12D
  plan explicitly asks for corpus-wide full search.
- Foundry method reports must not be projected as evidence support. Their
  authority envelope is method-validity scoped, so G2 must bind them beside SKG
  evidence and S10 validation rather than treating method validity as causal
  effect support.
- A HNSW candidate without both a replayed query vector producer and matching
  DuckDB/SKG support rows is candidate-only at best. Treating it as evidence is
  search-hit laundering.
- Concept alignment must compose with the existing concept-spine/status lattice.
  A local G2 `cause_label == outcome_label` style match is only a candidate
  match until a spine/semantic-binding record says how the refs relate.
- Readiness `--write` must not silently omit TOML artifacts such as
  `layer3_g2_health_metric_delta.toml` or
  `layer3_g2_adapter_contract_registry.toml`; the written path list and
  expected artifact list must match.
- Generated artifact guardrails run family-level checks from
  `architecture/generated_artifacts.toml`, but committed-output existence is not
  enough to prove G2 readiness. The G2 readiness CLI must explicitly validate
  expected JSON/TOML artifact presence and selected manifest/runtime keys.

## Target File Map

Create:

- `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
  - Owns G2 DTOs, search records, SKG/method coverage reports, adapter
    bindings, calibration/transport summaries, S10 bridge records, readiness
    bundle builder, and runtime validator.
- `tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py`
  - CLI/readiness wrapper mirroring G1: validates runtime bundle, validates
    persisted artifacts, writes artifacts in `--write` mode, and reports issue
    codes.
- `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`
  - Unit tests for DTO strictness, bundle builder, validator, S10 translation,
    tier blockers, SKG coverage, search recall/freshness, method validity, and
    engineering quality.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness.py`
  - Repo-quality validator tests for persisted artifacts, manifest/runtime drift,
    surface sync, authority leaks, canonical SKG search, method-registry search,
    recall/freshness, and negative controls.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness_cli.py`
  - CLI tests for output format, write mode, issue-code reporting, and artifact
    list. Include a negative where `--write` omits a TOML artifact or reports a
    written path that is not in the expected artifact set.
- `docs/reference/policy-design-case-layer3-causal-forecast.md`
  - All-audience forecast tier/uncertainty reference, EXPERT/MACHINE audit
    details, validator command, artifacts, fields, and authority boundaries.

Modify:

- `architecture/generated_artifacts.toml`
  - Register a separate G2 generated-artifact family, source of truth,
    verifier, regeneration command, commit policy, freshness rule, drift gate,
    output paths, and workflow check command.
- `docs/reference/generated-artifacts.md`
  - Regenerate/update from `architecture/generated_artifacts.toml`; do not use
    this as the source of truth.
- `architecture/policy_design_case/inventory.json`
  - Register `layer3_g2_causal_forecast_audit_surface` and all persisted G2
    artifacts. The surface should expose PUBLIC/REVIEWER tier, uncertainty,
    limitations, and denied uses, while raw ledgers can be EXPERT/MACHINE
    details or explicit lower-level out-of-scope fields.
- `docs/reference/public-surface.md`
  - Add the G2 forecast tier/uncertainty surface or the existing S10 projection
    route used by PUBLIC/REVIEWER. Only raw search ledgers and low-level replay
    diagnostics may be explicitly `surface_out_of_scope` for those audiences.
- `docs/reference/documentation-inventory.md`
  - Add the G2 reference page and validator command.
- `docs/reference/index.md`
  - Add the G2 reference page to the reference index.
- `mkdocs.yml`
  - Modify only if the repo navigation requires explicit reference-page entries.
- `tools/quality/validation/run_universal_outcome_corpus.py`
  - Add the G2 W12D gate by mirroring the existing G1 context/gate/summary
    pattern: inject after G1 and before corpus summaries, preserve G0/G1
    conversion outcomes, and expose S10 forecast posture as forecast support
    only.
- `tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py`
  or existing W12D route, only if needed to expose the S10 consumer bridge in a
  tested way without broad design-search refactor.
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
  - Add G2 route tests only where W12D already exercises Layer 3 gates and S10
    posture consumption.

Persist generated artifacts:

- `architecture/policy_design_case/layer3_g2_adapter_admission_registry.json`
- `architecture/policy_design_case/layer3_g2_l2_skg_search_ledgers.json`
- `architecture/policy_design_case/layer3_g2_l2_skg_query_traces.json`
- `architecture/policy_design_case/layer3_g2_l2_skg_index_coverage.json`
- `architecture/policy_design_case/layer3_g2_search_recall_freshness.json`
- `architecture/policy_design_case/layer3_g2_foundry_method_registry_coverage.json`
- `architecture/policy_design_case/layer3_g2_foundry_method_registry_search.json`
- `architecture/policy_design_case/layer3_g2_method_requirement_bindings.json`
- `architecture/policy_design_case/layer3_g2_method_validity_transport.json`
- `architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json`
- `architecture/policy_design_case/layer3_g2_concept_alignment_records.json`
- `architecture/policy_design_case/layer3_g2_s10_prerequisite_bindings.json`
- `architecture/policy_design_case/layer3_g2_forecast_support_bindings.json`
- `architecture/policy_design_case/layer3_g2_grounded_forecast_handoffs.json`
- `architecture/policy_design_case/layer3_g2_observable_calibration_report.json`
- `architecture/policy_design_case/layer3_g2_transport_limit_declarations.json`
- `architecture/policy_design_case/layer3_g2_authority_envelopes.json`
- `architecture/policy_design_case/layer3_g2_conformance_report.json`
- `architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json`
- `architecture/policy_design_case/layer3_g2_causal_forecast_audit_surface.json`
- `architecture/policy_design_case/layer3_g2_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_g2_adapter_contract_registry.toml`
- `architecture/policy_design_case/layer3_g2_readiness_manifest.json`

Readiness-selected manifest/runtime drift keys:

- `schema_version`
- `rule_version`
- `g1_dependency_status`
- `g2_l2_skg_coverage_status`
- `g2_search_ledger_count`
- `g2_skg_query_trace_count`
- `g2_foundry_method_registry_coverage_status`
- `g2_method_requirement_binding_count`
- `g2_method_validity_report_status`
- `g2_semantic_spine_binding_count`
- `g2_s10_prerequisite_binding_status`
- `g2_forecast_support_binding_count`
- `g2_w12d_consumer_gate_status`
- `g2_search_engineering_quality_status`
- `g2_health_metric_ids`

Do not compare every summary count blindly; follow G1's selected-key drift
pattern so the gate is stable while still catching load-bearing mismatches.

## Runtime Contract Sketch

Use strict Pydantic DTOs (`extra="forbid"`) and stable schema/rule constants:

- `LAYER3_G2_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g2_causal_forecast.v1"`
- `LAYER3_G2_RULE_VERSION = "policyos.layer3.g2.causal_forecast_search.v1"`
- `LAYER3_G2_SURFACE_ID = "layer3_g2_causal_forecast_audit_surface"`

Core DTOs:

- `Layer3G2ValidationIssue`
- `Layer3G2ValidationReport`
- `Layer3G2CausalForecastRequest`
- `Layer3G2SearchLedger`
- `Layer3G2SkgQueryTrace`
- `Layer3G2L2SkgIndexCoverageReport`
- `Layer3G2SearchRecallSeed`
- `Layer3G2IndexFreshnessRecord`
- `Layer3G2SearchRecallFreshnessReport`
- `Layer3G2FoundryMethodRegistryCoverageReport`
- `Layer3G2FoundryMethodRegistrySearchReport`
- `Layer3G2MethodRequirementBinding`
- `Layer3G2MethodValidityTransportRecord`
- `Layer3G2SemanticSpineBinding`
- `Layer3G2ConceptAlignmentRecord`
- `Layer3G2S10PrerequisiteBinding`
- `Layer3G2ForecastSupportBinding`
- `Layer3G2GroundedForecastHandoffRecord`
- `Layer3G2ObservableCalibrationReport`
- `Layer3G2TransportLimitDeclaration`
- `Layer3G2AuthorityEnvelopeBinding`
- `Layer3G2SearchEngineeringQualityReport`
- `Layer3G2AdapterAdmissionBundle`
- `Layer3G2ConformanceReport`
- `Layer3G2CausalForecastAuditSurface`
- `Layer3G2GeneratedArtifactRegistrationStatus`
- `Layer3G2W12DConsumerGateRecord`
- `Layer3G2ReadinessManifest`
- `Layer3G2Bundle`

Core functions:

- `build_layer3_g2_bundle(repo_root: Path) -> Layer3G2Bundle`
- `validate_layer3_g2_bundle(repo_root: Path, persisted: Mapping[str, Any] | Layer3G2Bundle) -> Layer3G2ValidationReport`
- `build_g2_l2_skg_index_coverage(repo_root: Path) -> Layer3G2L2SkgIndexCoverageReport`
- `build_g2_search_recall_freshness(repo_root: Path) -> Layer3G2SearchRecallFreshnessReport`
- `search_l2_skg_for_forecast_candidates(request: Layer3G2CausalForecastRequest, repo_root: Path) -> tuple[Layer3G2SearchLedger, ...]`
  using public `polisyos.data_forge.read_api.academic.SKGQuery` first and direct
  read-only DuckDB for replay/coverage fields not exposed by `SKGQuery`; every
  consumed query result must carry a `Layer3G2SkgQueryTrace`.
- `build_g2_foundry_method_registry_coverage(repo_root: Path) -> Layer3G2FoundryMethodRegistryCoverageReport`
- `search_foundry_methods_for_forecast(request: Layer3G2CausalForecastRequest) -> Layer3G2FoundryMethodRegistrySearchReport`
- `build_g2_method_requirement_bindings(...) -> tuple[Layer3G2MethodRequirementBinding, ...]`
  using existing `MethodValidityRequirementSpec` fields and Foundry requirement
  selection, not loose local method tags only.
- `build_g2_method_validity_transport_record(...) -> Layer3G2MethodValidityTransportRecord`
- `build_g2_semantic_spine_bindings(...) -> tuple[Layer3G2SemanticSpineBinding, ...]`
  using existing producer-spine read contexts, binding fields, governed concept
  refs, and producer handshakes where available.
- `build_g2_concept_alignment_records(...) -> tuple[Layer3G2ConceptAlignmentRecord, ...]`
- `build_g2_s10_prerequisite_bindings(...) -> tuple[Layer3G2S10PrerequisiteBinding, ...]`
- `build_g2_forecast_support_bindings(...) -> tuple[Layer3G2ForecastSupportBinding, ...]`
- `build_g2_grounded_forecast_handoffs(...) -> tuple[Layer3G2GroundedForecastHandoffRecord, ...]`
- `validate_g2_adapter_conformance(repo_root: Path, bundle: Layer3G2Bundle) -> Layer3G2ConformanceReport`
- `build_g2_s10_forecast_posture(binding: Layer3G2ForecastSupportBinding) -> Layer2S10ForecastPostureInput`
- `build_g2_w12d_consumer_gate(...) -> Layer3G2W12DConsumerGateRecord`
  proving cost-proportional S10/S2 consumption: at least one full consumer proof
  and lightweight forecast refs elsewhere when routed through W12D.
- `build_g2_causal_forecast_audit_surface(bundle: Layer3G2Bundle) -> Layer3G2CausalForecastAuditSurface`
- `build_g2_generated_artifact_registration_status(repo_root: Path) -> Layer3G2GeneratedArtifactRegistrationStatus`
  verifying the TOML family, generated docs marker, inventory surface, public
  surface, documentation inventory, and reference index entries.

Do not expose private helper DTOs through public package facades unless the
package public-surface policy requires it. G2 runtime can remain an internal
quality module with documented audit artifacts.

## Adapter Semantics

G2 uses three-stage admission:

1. **Discoverable candidate**
   - SKG row, HNSW result, or method registry result exists.
   - It may inform the frontier and rejection set.
   - It is not support.
2. **Adapter-valid candidate**
   - G1 source-contract refs, SKG edge/claim/parameter/transport refs, Foundry
     method validity refs, concept-alignment/semantic-loss checks, and authority
     boundary are all present.
   - S5/S6/S8/design/prediction prerequisite refs are present or the candidate
     is downgraded/blocked before S10 posture.
   - It may be translated into S10 inputs.
   - It is still not claim authority.
3. **S10-valid forecast support**
   - Existing S10 builders and validators accept the record.
   - Authority envelope denies production/recommendation/claim/closeout/S11
     authority.
   - It may be consumed by S10/S2 as forecast posture only.
   - It may be referenced by a G4/G5 handoff record, but that handoff is not
     promotion, conversion, or useful-design credit.

Tier rules:

- `observable_calibrated` only when observable subset calibration passes and
  uncertainty intervals are visible.
- `transported_limited` when the support is transported from SKG/literature and
  carries transport limitations, source-contract refs, method-validity refs, and
  uncertainty intervals.
- `historical_prior_context` when evidence is a historical prior and remains
  context only.
- `simulation_only_advisory` when support is simulation-only.
- `equilibrium_contested_blocked` when a single/local effect would be laundered
  into system or equilibrium authority.
- `blocked` when required search, G1 grounding, method validity, calibration,
  transport, uncertainty, or authority-boundary checks fail.

## Implementation Tasks

### Task 0: G2 Red Baseline And Dependency Probe

**Files:**

- Create: `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness_cli.py`

Steps:

- [x] Add failing tests that import `polisyos.runtime.quality.proving_ground.causal_forecast_search`
  and assert the module exposes schema/rule constants, bundle builder, validator,
  DTOs, and issue-code surfaces listed in this plan.
- [x] Add a failing repo-quality test that `validate_layer3_g2_readiness(REPO_ROOT)`
  returns a pass summary only when persisted artifacts match the runtime bundle.
- [x] Include red assertions that method-requirement bindings, semantic-spine
  bindings, and the W12D consumer gate are persisted and included in the
  readiness manifest/write path.
- [x] Add a failing CLI test mirroring G1: `--output-format json` reports
  `schema_version`, `status`, `summary`, and `issues`; `--write` reports written
  G2 artifact paths.
- [x] Run:
  `uv run pytest tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness_cli.py -q`
  and confirm the failure is module/CLI absence, not unrelated environment drift.

### Task 1: Canonical L2 SKG Coverage And Search-Ledger DTOs

**Files:**

- Create: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`

Steps:

- [x] Implement strict DTOs for `Layer3G2CausalForecastRequest`,
  `Layer3G2SearchLedger`, `Layer3G2SkgQueryTrace`,
  `Layer3G2L2SkgIndexCoverageReport`, `Layer3G2SearchRecallFreshnessReport`,
  and validation issue/report.
- [x] Implement `build_g2_l2_skg_index_coverage(repo_root)` to read the real SKG
  DuckDB in read-only mode, check required tables, counts, manifest refs,
  `ac_skg_versions`, snapshot hash refs, and HNSW/embedding asset presence.
  Coverage must verify the exact construction path:
  `SKGQuery(db_path=academic/graph/scholar_knowledge.duckdb, index_dir=academic)`.
- [x] Implement `search_l2_skg_for_forecast_candidates(...)` by reusing
  public `polisyos.data_forge.read_api.academic.SKGQuery` for canonical
  cause/effect variables, edge support, contested support, transport, priors,
  and parameter paths, with bounded read-only DuckDB queries only for
  replay/coverage details not exposed by `SKGQuery`. Store
  query API path, SQL description where applicable, table refs, predicates,
  limits, result count, selected/rejected refs, row identifiers, and authority
  boundary in `Layer3G2SkgQueryTrace` and `Layer3G2SearchLedger`.
- [x] Reuse SKGQuery-provided `quality_flags`, transport notes, uncertainty
  source, matched moderators, normalization diagnostics, latest SKG version, and
  snapshot refs instead of reconstructing these semantics from raw SQL unless a
  replay field is missing.
- [x] Treat `src/polisyos/scholar/search/models.py` as a trace-shape reference,
  not as local SKG authority. Do not emit `WebEvidenceBundle` /
  `ClaimSupportLink` for SKG rows unless source/snippet integrity constraints
  are actually satisfied.
- [x] Add a conformance check that a consumed `SKGQuery` or direct-SQL result
  without a matching query trace fails readiness.
- [x] Add unit tests that reject payloads where the ledger uses
  `capability_index`, `fixture`, or `compiler_claim_view` as `canonical_l2_route`.
- [x] Add a test that deleting `ac_skg_transport_scores` from a temporary
  DuckDB fixture causes coverage failure rather than a false pass.
- [x] Add a test that a misconfigured `index_dir=academic/graph` fails the HNSW
  asset path check instead of silently reporting vector recall as healthy.
- [x] Add a test that semantic/HNSW retrieval without a replayed query-vector
  producer fails as `layer3_g2_semantic_retrieval_without_query_vector_producer`
  instead of becoming semantic evidence.
- [x] Add a test that a search hit without adapter/S10 validation cannot appear
  in `forecast_support_refs`.

### Task 2: L2 Recall, Freshness, Free-Growth, And Engineering Quality

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`

Steps:

- [x] Add known-groundable seed records that target real SKG rows, including at
  least one canonical SKG edge and one transport-score row.
- [x] Implement `build_g2_search_recall_freshness(repo_root)` with seed recall,
  SKG manifest freshness, conditionally-required HNSW/embedding freshness, and
  stale-index blockers. HNSW freshness is blocking only when semantic retrieval
  is invoked or the seed depends on vector search.
- [x] Keep exact/canonical SKG search independent from HNSW: if no existing
  query-vector producer is needed for the request, HNSW status is
  `not_required_for_request`, not `fail`.
- [x] If semantic retrieval is needed, record the existing query-vector producer,
  embedding/index versions, query-vector ref, HNSW `ef`/limit settings where
  available, candidate row refs, and post-HNSW DuckDB validation trace. If no
  existing query-vector producer is available, fail closed or mark the semantic
  path unavailable.
- [x] Implement G2 free-growth fixture logic: a correctly-added SKG edge/method
  in an isolated DuckDB/registry fixture is discovered without changing code.
- [x] Implement `Layer3G2SearchEngineeringQualityReport` or equivalent summary
  requiring DuckDB/HNSW/index-backed search, lazy/bounded reads, deterministic
  replay fields, named libraries/indexes, and no eager full-corpus scan.
- [x] Add tests for recall miss, stale manifest, HNSW asset mismatch, fixture
  free-growth failure, and O(n)/eager-search marker failure.
- [x] Add a test proving exact canonical DuckDB/SKG requests are not blocked by a
  missing HNSW asset when the semantic retrieval path is not required.

### Task 3: Foundry Method-Registry Search And Method Validity

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`

Steps:

- [x] Implement `Layer3G2FoundryMethodRegistryCoverageReport` with built-in
  catalog bootstrap refs, discovery source roots, entry-point groups, registered
  count, causal/forecast/econometric/sensitivity/validation method count,
  duplicates, errors, registry snapshot/version refs, registry stats, and
  freshness.
- [x] Implement `Layer3G2FoundryMethodRegistrySearchReport` with candidate
  methods, selected methods, rejected methods, registry/discovery refs, task/data
  affinity predicates, and search-ledger refs.
- [x] Bootstrap installed built-in families through existing
  `ensure_*_methods_registered` or `ensure_all_methods_registered` paths, then
  refresh entry-point/dev discovery where applicable before evaluating method
  search coverage.
- [x] Search Foundry registry/discovery metadata instead of using a hardcoded
  method FQN list. Accept request-shaped filters such as data modality,
  causal/forecast task tags, panel/cross-section/time-series affinity, treatment
  structure, outcome type, and required diagnostics only when those predicates
  are represented by existing `MethodSignature`, slot, tag, data-modality,
  namespace/name, or method-quality fields.
- [x] Build `MethodValidityRequirementSpec` records for the causal/forecast
  request, including identification class, transportability requirement,
  uncertainty class, fairness/strategic-response needs, required method
  families/expectations, runtime assumption gates, uncertainty envelope,
  limitation refs, method outputs, and negative-certificate needs where
  applicable.
- [x] Run existing Foundry requirement selection and preserve requirement
  status, candidate refs, selected refs, rejected refs, and selection issue
  codes in `Layer3G2MethodRequirementBinding` and
  `architecture/policy_design_case/layer3_g2_method_requirement_bindings.json`.
- [x] Reuse `build_foundry_method_report` and the method-quality registry to
  produce `Layer3G2MethodValidityTransportRecord` rows.
- [x] Preserve the Foundry method report authority envelope and fail if G2 uses a
  method report as academic support strength, legal authority, source-family
  satisfaction, claim support, closeout pass, or participation authority.
- [x] Use `persist_foundry_method_report` / `persist_foundry_method_report_for_state`
  when an artifact store is available; otherwise record why CAS persistence is
  out of scope for G2 readiness and persist the report ref in
  `architecture/policy_design_case/layer3_g2_method_validity_transport.json`.
- [x] Require identification requirements, transportability limits, sensitivity
  or uncertainty refs, selected/rejected reasons, and method lineage refs before
  a method can support governed S10 tiers.
- [x] Add negatives for registered-method-only support, generic simulation as
  causal evidence, missing `MethodValidityRequirementSpec`, failed requirement
  selection, missing identification requirements, missing transportability
  limits, method-report authority overclaim, missing discovery refresh, missing
  registry coverage, and hardcoded FQN closure.

### Task 4: S10 Prerequisite Spine, ForecastSupport Binding, And Builder Reuse

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`

Steps:

- [x] Implement `Layer3G2S10PrerequisiteBinding` that records or inherits S5
  forecast-support refs, S6 firewall refs, S8 value-provenance/tradeoff refs,
  design graph, prediction/policy context, candidate/baseline/alternative
  design refs, horizon refs, uncertainty refs, source-contract/method-validity
  refs, and authority-boundary denials.
- [x] Fail closed when the prerequisite binding is missing, incomplete, or
  inconsistent with S10-required refs. Do not fabricate S5/S6/S8 refs from SKG
  search hits or Foundry method selection.
- [x] Implement `Layer3G2ForecastSupportBinding` that wraps S10
  `ForecastSupport` plus G1 binding refs, SKG edge/claim/parameter/transport
  refs, method validity refs, S10 prerequisite refs, calibration refs,
  limitation refs, and G2 search-ledger refs.
- [x] Implement `Layer3G2ConceptAlignmentRecord` tying G1 source-contract target
  outcomes/metrics to SKG cause/effect variables, SKG parameter refs, Foundry
  input/output slots, and S10 target-outcome refs.
- [x] Implement `Layer3G2SemanticSpineBinding` or equivalent fields that reuse
  `build_producer_spine_read_context`, `producer_spine_read_context_for`,
  `build_producer_spine_binding_fields`, governed namespace refs, reconciled
  concept statuses, and producer handshakes where available. If a full spine
  carrier is unavailable for a fixture, the fixture must explicitly record the
  missing capability label and cannot pass as direct semantic grounding.
  Persist these rows in
  `architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json`.
- [x] Compose discovery/executable/admitted states with the existing status and
  authority lattice; do not add parallel G2 concept statuses that bypass
  `concept_spine` or `semantic_binding` closure semantics.
- [x] Downgrade or block support when concept alignment is ambiguous, proxy-only
  without disclosure, or unmatched.
- [x] Build support records only through `build_forecast_support`.
- [x] Compare G2's requested posture/tier with the tier derived by existing S10
  builders and treat any mismatch as `layer3_g2_s10_tier_derivation_mismatch`.
- [x] Build calibration records only through `build_forecast_calibration_record`.
- [x] Build authority envelopes only through `verify_prediction_authority_envelope`.
- [x] Build integrity summaries through `summarize_forecast_support_integrity`.
- [x] Add tests for S10-required failures: `observable_calibrated` without
  calibration refs, governed tier without uncertainty intervals,
  simulation-only promoted above advisory, historical prior promoted above
  context, transported estimate without limitation refs, ambiguous/proxy-only
  alignment overclaimed as direct grounding, parallel concept lattice,
  semantic-spine binding missing, missing S5/S6/S8 prerequisite refs,
  derived-tier mismatch, and missing denials in `may_not_use_for`.

### Task 5: Calibration, Transport, Contested, And Equilibrium Downgrade Logic

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py`
- Reuse fixtures from: `tests/fixtures/layer2/s10/`

Steps:

- [x] Implement `Layer3G2ObservableCalibrationReport` with denominator,
  numerator, pass rate, threshold ref, credible evaluation evidence refs,
  observed-outcome refs, counterfactual credibility, and time-role refs.
- [x] Implement `Layer3G2TransportLimitDeclaration` using SKG
  `ac_skg_transport_scores`, method transportability limits, jurisdiction scope,
  aggregation scope, and uncertainty intervals.
- [x] Preserve contested-edge and publish-blocker signals from SKG as limitations
  or blockers.
- [x] Enforce adapter admission maturity: `calibrated` only when observable
  calibration passes and the forecast authority envelope remains bounded;
  otherwise adapter maturity is `predictive` or `fail_closed`.
- [x] Add dynamic/equilibrium caveat handling that keeps system-effect or
  large-scale equilibrium claims blocked unless a future calibrated dynamics
  producer exists.
- [x] Reuse existing S10 fixture negatives where possible:
  `uncalibrated_observable_promotion_probe.json`,
  `hidden_uncertainty_interval_probe.json`,
  `transported_estimate_without_limitation_probe.json`,
  `simulation_only_evidence_laundering_probe.json`,
  `equilibrium_contested_single_forecast_probe.json`, and
  `production_authority_from_forecast_probe.json`.

### Task 6: S10 Consumer Bridge, G4/G5 Handoff, And W12D Route

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify if needed: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

Steps:

- [x] Implement `build_g2_s10_forecast_posture(binding)` returning
  public `polisyos.pdc.Layer2S10ForecastPostureInput` without importing through
  non-canonical PDC internals.
- [x] Keep the S2 contract consumer-only: S2/W12D must not import or call G2/S10
  runtime-quality producers. G2 builds posture; PDC consumes posture.
- [x] Add a W12D/G2 gate record that consumes G2 forecast posture as forecast
  support only, preserving `layer3_g1_grounding_gate` and not overwriting G0/G1
  conversion outcomes. If G2 closes as `causal_forecast_domain_ceiling` or
  `search_ceiling_repair_required`, the W12D gate still routes after G1 and
  before summaries, records the ceiling/repair diagnosis, and does not pretend a
  posture was consumed.
- [x] Mirror the existing G1 W12D shape with `_layer3_g2_causal_forecast_context`,
  `_with_layer3_g2_forecast_gate`, `_layer3_g2_forecast_gate`, and
  `_layer3_g2_summary`; inject after G1 and before corpus summaries.
- [x] Preserve the existing W12D S10 cost shape: at least one full first-case S2
  consumer proof with forecast posture/search ledger, and lightweight forecast
  posture refs for other cases unless a later corpus-wide full-search plan
  explicitly requires more. `not_routed` is allowed only for local/dev probes or
  explicitly scoped-out experiments; it cannot satisfy G2 closeout readiness.
- [x] Implement `Layer3G2GroundedForecastHandoffRecord` as the stable
  promotion/conversion input for G4/G5. It must reference the S10-valid
  `ForecastSupport`, concept-alignment record, source contract, method validity,
  calibration/transport/uncertainty records, maturity, limitations, and
  `may_not_use_for`.
- [x] Add tests that S2/W12D sees forecast tier, support ref, calibration ref,
  source-contract ref, method-validity ref, uncertainty refs, and
  `may_not_use_for`.
- [x] Add tests that G2 does not rely on `DesignRecord.ledger_refs` or the S2
  deterministic replay key as the full G2 replay surface; source-contract,
  method-validity, SKG query, and method-requirement refs remain in G2
  handoff/audit artifacts and expert/machine projections.
- [x] Add tests that G2 forecast posture does not increase useful-design count,
  does not claim closeout, and does not become recommendation or claim authority.
- [x] Add tests that W12D does not run full S2 search for every G2 case by
  accident.
- [x] Add tests that `not_routed` cannot pass the G2 closeout readiness gate, and
  that a domain-ceiling run still emits a W12D gate summary after G1.
- [x] Add tests that G4/G5 can read the grounded forecast handoff ref without
  treating it as promotion, conversion, or useful-design credit.

### Task 7: Readiness CLI, Persisted Artifacts, Surface, And Docs

**Files:**

- Create: `tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py`
- Modify: `architecture/generated_artifacts.toml`
- Modify: `docs/reference/generated-artifacts.md`
- Modify: `architecture/policy_design_case/inventory.json`
- Create: `docs/reference/policy-design-case-layer3-causal-forecast.md`
- Modify: `docs/reference/documentation-inventory.md`
- Modify: `docs/reference/index.md`
- Modify if required by repo policy: `docs/reference/public-surface.md`
- Modify if required by repo navigation: `mkdocs.yml`

Steps:

- [x] Implement G2 readiness CLI mirroring G1: runtime bundle, persisted-artifact
  comparison, manifest/runtime drift, surface sync, artifact write mode, and
  compact text/json output.
- [x] Split readiness checks into explicit subchecks: G1 dependency, runtime
  bundle validation, persisted artifact presence, selected-key manifest/runtime
  drift, generated-artifact TOML family, docs/inventory/public-surface sync,
  authority posture, search health, method health, S10 consumer bridge, and
  W12D route when enabled.
- [x] Persist all G2 JSON and TOML artifacts listed in the file map through
  `--write`, including `layer3_g2_health_metric_delta.toml` and
  `layer3_g2_adapter_contract_registry.toml`; the CLI `written_artifact_paths`
  must match the expected artifact set.
- [x] Register a G2 family in `architecture/generated_artifacts.toml` and
  regenerate/update the generated-artifacts reference from that TOML source.
- [x] Register the G2 audit/tier surface in inventory, documentation inventory,
  reference index, and public-surface docs.
- [x] Write the G2 reference page with purpose, not-authority boundaries,
  all-audience forecast tier/uncertainty behavior, artifact list, validator
  command, failure modes, handoff refs, and replay fields.
- [x] Ensure PUBLIC/REVIEWER can see tier, uncertainty, limitations, and denied
  uses through existing S10 projection semantics or G2 reference docs. Raw query
  ledgers may remain expert/machine-only.
- [x] Add tests that docs/inventory/generated-artifacts entries are synced and
  that missing generated-artifact family, missing reference-index entry, missing
  public-surface visibility, missing adapter contract TOML, or missing surface
  registration fails readiness.

### Task 8: Conformance Battery And Final Gate

**Files:**

- Modify: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`
- Modify: `tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py`
- Test: all G2 tests

Steps:

- [x] Implement `validate_g2_adapter_conformance(repo_root, bundle)` with the
  issue codes below.
- [x] Add negative tests for every issue code that can be triggered with a small
  fixture.
- [x] Run targeted tests:
  `uv run pytest tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness_cli.py -q`
- [x] Run consumer tests:
  `uv run pytest tests/unit/pdc/test_layer2_s2_design_search.py tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q`
- [x] Run architecture/docs checks touched by G2:
  `uv run polisyos-tools architecture guardrails check`
- [x] Run the G2 CLI:
  `uv run python tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py --repo-root . --write --output-format json`
- [x] Confirm the readiness manifest reports `status=pass` or the honest
  `causal_forecast_domain_ceiling` path with all recall/freshness/search-quality
  prerequisites green.

## Required Issue Codes

The runtime validator and CLI must report stable issue codes. Use these names
unless implementation reveals an existing canonical code that should be reused.

- `layer3_g2_g1_dependency_not_ready`
- `layer3_g2_persisted_artifact_missing`
- `layer3_g2_manifest_runtime_drift`
- `layer3_g2_surface_unsynced`
- `layer3_g2_generated_artifacts_family_missing`
- `layer3_g2_inventory_surface_missing`
- `layer3_g2_reference_index_missing`
- `layer3_g2_public_surface_visibility_missing`
- `layer3_g2_adapter_contract_registry_missing`
- `layer3_g2_l2_skg_not_queried`
- `layer3_g2_l2_skg_bounded_surrogate_overclaimed`
- `layer3_g2_capability_index_used_as_l2_search`
- `layer3_g2_unjustified_l2_surrogate`
- `layer3_g2_l2_skg_index_coverage_missing`
- `layer3_g2_skg_index_dir_misconfigured`
- `layer3_g2_skg_query_trace_missing`
- `layer3_g2_hnsw_candidate_without_skg_row`
- `layer3_g2_semantic_retrieval_without_query_vector_producer`
- `layer3_g2_skg_web_evidence_bundle_laundering`
- `layer3_g2_search_ledger_missing`
- `layer3_g2_search_ledger_authority_boundary_leak`
- `layer3_g2_no_hit_without_replayable_frontier`
- `layer3_g2_search_recall_seed_miss_blocks_domain_ceiling`
- `layer3_g2_stale_index_blocks_domain_ceiling`
- `layer3_g2_search_ceiling_not_domain_ceiling`
- `layer3_g2_search_engineering_quality_failed`
- `layer3_g2_mechanism_generality_single_request`
- `layer3_g2_free_growth_fixture_failed`
- `layer3_g2_foundry_method_registry_not_queried`
- `layer3_g2_foundry_discovery_coverage_missing`
- `layer3_g2_foundry_builtin_catalog_bootstrap_missing`
- `layer3_g2_foundry_registry_snapshot_missing`
- `layer3_g2_method_registry_discovery_not_refreshed`
- `layer3_g2_method_registry_hardcode_closure`
- `layer3_g2_method_requirement_missing`
- `layer3_g2_method_requirement_selection_failed`
- `layer3_g2_method_validity_missing`
- `layer3_g2_foundry_method_report_authority_overclaim`
- `layer3_g2_foundry_method_report_persistence_missing`
- `layer3_g2_identification_requirement_missing`
- `layer3_g2_transportability_limit_missing`
- `layer3_g2_semantic_binding_spine_missing`
- `layer3_g2_parallel_concept_lattice`
- `layer3_g2_concept_alignment_missing`
- `layer3_g2_proxy_alignment_undisclosed`
- `layer3_g2_ambiguous_alignment_overclaimed`
- `layer3_g2_s10_prerequisite_binding_missing`
- `layer3_g2_s5_s6_s8_refs_missing`
- `layer3_g2_design_prediction_context_missing`
- `layer3_g2_s10_tier_derivation_mismatch`
- `layer3_g2_search_hit_used_as_forecast_support`
- `layer3_g2_raw_skg_output_without_adapter`
- `layer3_g2_forecast_support_missing`
- `layer3_g2_forecast_support_invalid`
- `layer3_g2_adapter_maturity_overclaim`
- `layer3_g2_forecast_tier_overclaimed`
- `layer3_g2_regime_forecast_tier_laundering`
- `layer3_g2_observable_calibration_required`
- `layer3_g2_observable_calibration_denominator_missing`
- `layer3_g2_credible_evaluation_evidence_missing`
- `layer3_g2_uncertainty_interval_missing`
- `layer3_g2_transport_limit_missing`
- `layer3_g2_simulation_only_laundered`
- `layer3_g2_historical_prior_laundered`
- `layer3_g2_equilibrium_authority_overclaim`
- `layer3_g2_contested_edge_overclaimed`
- `layer3_g2_effect_independence_inflated`
- `layer3_g2_aggregation_validity_missing`
- `layer3_g2_strategic_response_missing`
- `layer3_g2_semantic_loss`
- `layer3_g2_claim_authority_leak`
- `layer3_g2_recommendation_authority_leak`
- `layer3_g2_closeout_authority_leak`
- `layer3_g2_useful_design_credit_leak`
- `layer3_g2_s10_consumer_bridge_missing`
- `layer3_g2_s10_posture_not_consumed`
- `layer3_g2_s2_forecast_producer_import`
- `layer3_g2_s2_design_record_replay_overclaim`
- `layer3_g2_w12d_not_routed_closeout`
- `layer3_g2_w12d_domain_ceiling_gate_missing`
- `layer3_g2_w12d_full_s2_overreach`
- `layer3_g2_grounded_forecast_handoff_missing`
- `layer3_g2_grounded_forecast_handoff_promoted`
- `layer3_g2_w12d_conversion_outcome_overwrite`

## Completion Audit

Completed on 2026-06-08 with the G2 closure path implemented as bounded
`ForecastSupport` plus explicit authority denials, not recommendation or
closeout authority.

Verification run:

- `uv run pytest tests/unit/runtime/quality/test_layer3_g2_causal_forecast.py -q`
- `uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g2_readiness_cli.py tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q`
- `uv run python tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py --write --output-format json`
- `uv run python tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py --output-format json`
- `uv run polisyos-tools architecture guardrails check`

Final readiness signal: `status=pass`, `issue_count=0`,
`g2_conformance_status=pass`, `g2_manifest_runtime_drift_key_count=0`,
`persisted_g2_artifact_count=23`, and
`g2_w12d_consumer_gate_status=pass`.

Pattern closeout: the remaining gaps were `contract_only` /
`semantic_test_missing` issue codes. They now have negative tests and concrete
runtime or readiness/W12D producers, closing the relevant P01/P10/P16/P19/P24/P25
risks without changing G2's authority boundary.

## Acceptance Gates

G2 is ready for implementation closeout only when all of the following are true:

For method-requirement, method-validity, semantic-spine, and concept-alignment
status gates, `pass` means the evaluation ran against canonical inputs, persisted
its binding record, and produced either selected refs or typed
blockers/limitations. It does not mean strong causal support was found. A skipped,
unpersisted, or unreplayable evaluation is `fail`, even on the honest domain
ceiling path.

- `g1_dependency_status == "pass"`.
- `g2_l2_skg_coverage_status == "pass"`.
- `g2_l2_skg_canonical_route == "scholar_knowledge.duckdb"`.
- `g2_skg_query_api_route == "polisyos.data_forge.read_api.academic.SKGQuery"`.
- `g2_skg_query_index_dir_status == "pass"`.
- `g2_l2_skg_required_tables_present == true`.
- `g2_l2_skg_hnsw_assets_status in {"pass", "not_required_for_request"}`.
- `g2_hnsw_query_vector_producer_status in {"pass", "not_required_for_request"}`.
- `g2_hnsw_candidate_without_skg_row_count == 0`.
- `g2_semantic_retrieval_without_query_vector_producer_count == 0`.
- `g2_skg_web_evidence_bundle_laundering_count == 0`.
- `g2_skg_query_trace_count >= g2_consumed_skg_query_result_count`.
- `g2_search_ledger_count >= g2_authority_relevant_search_count`.
- `g2_search_recall_status == "pass"`.
- `g2_index_freshness_status == "pass"`.
- `g2_hnsw_freshness_status in {"pass", "not_required_for_request"}`.
- `g2_foundry_method_registry_coverage_status == "pass"`.
- `g2_foundry_method_registry_search_status == "pass"`.
- `g2_foundry_builtin_catalog_bootstrap_status == "pass"`.
- `g2_foundry_registry_snapshot_status == "pass"`.
- `g2_foundry_method_registry_discovery_refreshed == true`.
- `g2_method_requirement_status == "pass"`.
- `g2_method_requirement_binding_count >= 1`.
- `g2_method_requirement_selection_status == "pass"`.
- `g2_method_validity_report_status == "pass"`.
- `g2_foundry_method_report_authority_status == "bounded"`.
- `g2_foundry_method_report_persistence_status in {"pass", "recorded_out_of_scope"}`.
- `g2_semantic_binding_spine_status == "pass"`.
- `g2_semantic_spine_binding_count >= 1`.
- `g2_parallel_concept_lattice_count == 0`.
- `g2_concept_alignment_status == "pass"`.
- `g2_s10_prerequisite_binding_status == "pass"` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with healthy search.
- `g2_s5_s6_s8_refs_status == "pass"` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with healthy search.
- `g2_design_prediction_context_status == "pass"` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with healthy search.
- `g2_s10_derived_tier_mismatch_count == 0`.
- `g2_proxy_alignment_undisclosed_count == 0`.
- `g2_ambiguous_alignment_overclaim_count == 0`.
- `g2_adapter_maturity_overclaim_count == 0`.
- `g2_mechanism_generality_request_shape_count >= 2`.
- `g2_free_growth_fixture_status == "pass"`.
- `g2_forecast_support_binding_count >= 1` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with healthy search.
- `g2_observable_calibrated_count == 0` unless observable calibration denominator,
  credible evaluation evidence, threshold, time roles, and uncertainty intervals
  pass.
- `g2_transport_limit_count >= g2_transported_support_count`.
- `g2_uncertainty_interval_ref_count >= g2_governed_forecast_tier_count`.
- `g2_search_hit_used_as_support_count == 0`.
- `g2_claim_authority_leak_count == 0`.
- `g2_recommendation_authority_leak_count == 0`.
- `g2_closeout_authority_leak_count == 0`.
- `g2_useful_design_credit_count == 0`.
- `g2_grounded_forecast_handoff_status == "synced"` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with healthy search.
- `g2_grounded_forecast_handoff_promotion_count == 0`.
- `g2_generated_artifacts_family_status == "registered"`.
- `g2_inventory_surface_status == "registered"`.
- `g2_reference_index_status == "synced"`.
- `g2_adapter_contract_registry_status == "synced"`.
- `g2_manifest_runtime_drift_key_count == 0`.
- `g2_surface_status == "synced"`.
- `g2_public_reviewer_tier_uncertainty_surface_status == "synced"`.
- `g2_w12d_gate_injection_order == "after_g1_before_summary"`.
- `g2_w12d_consumer_gate_status == "pass"`.
- `g2_s2_forecast_producer_import_count == 0`.
- `g2_s2_design_record_replay_overclaim_count == 0`.
- `g2_w12d_full_s2_consumer_case_count >= 1` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with
  `g2_w12d_domain_ceiling_gate_status == "pass"`.
- `g2_w12d_lightweight_forecast_ref_status == "pass"` or
  `g2_closure_outcome == "causal_forecast_domain_ceiling"` with
  `g2_w12d_domain_ceiling_gate_status == "pass"`.
- `g2_w12d_full_s2_overreach_count == 0`.
- `g2_w12d_not_routed_closeout_count == 0`.
- `g2_w12d_conversion_outcome_overwrite_count == 0`.
- `g2_engineering_quality_status == "pass"`.
- `g2_conformance_status == "pass"`.

## Done Definition

G2 is done when a fresh checkout can run the targeted G2 tests and readiness CLI,
persist the G2 artifact set, inspect PUBLIC/REVIEWER forecast tier and
uncertainty behavior, and inspect EXPERT/MACHINE forecast audit details showing:

- which G1 grounded data substrate was used;
- which real SKG tables, rows, query predicates, transport scores, parameters,
  contested edges, query traces, and manifests were searched;
- whether HNSW/vector retrieval was unnecessary, or which existing query-vector
  producer and index versions made it replayable;
- which Foundry discovery sources were refreshed and which methods were found,
  selected, rejected, validated, and bounded by method-report authority;
- which `MethodValidityRequirementSpec` requirements were selected or failed;
- how G1 source contracts, SKG variables, Foundry slots, S10 outcomes, and
  concept-spine/semantic-binding refs were aligned or downgraded;
- which S5/S6/S8/design/prediction prerequisite refs allowed or blocked S10
  posture;
- which candidates became S10 `ForecastSupport` and which were rejected;
- how S2/W12D consumed posture without becoming the full G2 replay surface or
  rerunning full S2 search for every case;
- which generated-artifact TOML family, inventory surface, reference index,
  public surface, and adapter contract registry entries are synced;
- which grounded forecast handoff refs exist for later G4/G5 use, without
  promotion or useful-design credit;
- which forecast tier was emitted and why;
- what uncertainty, calibration, transport, semantic-loss, aggregation,
  strategic-response, and equilibrium limitations remain;
- which authority uses are denied;
- whether the outcome is a bounded `ForecastSupport`, honest limited tier,
  blocked/contested result, `causal_forecast_domain_ceiling`, or
  `search_ceiling_repair_required`.

The success condition is not "G2 makes a strong forecast". The success condition
is that G2 can search the real causal/forecast substrate, reuse the best existing
libraries and PolicyOS contracts, and tell the truth about how far the resulting
forecast support can go.
