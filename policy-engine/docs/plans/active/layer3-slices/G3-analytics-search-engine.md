---
plan_id: layer3-g3-analytics-search-engine
title: "G3 - Analytics Search Engine"
type: slice-plan
status: active
created: 2026-06-08
revised: 2026-06-08
slice: G3
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/plans/active/layer3-slices/G1-data-grounding-existing-assets-acquisition.md
  - docs/plans/active/layer3-slices/G2-causal-forecast-search-engine.md
  - docs/adr/0175-layer3-grounding-subordination-discipline.md
  - architecture/policy_design_case/layer3_g0_readiness_manifest.json
  - architecture/policy_design_case/layer3_discovery_search_discipline.json
  - architecture/policy_design_case/layer3_engineering_quality_check.json
  - architecture/policy_design_case/layer3_health_metric_ledgers.toml
  - architecture/policy_design_case/layer3_g1_readiness_manifest.json
  - architecture/policy_design_case/layer3_g1_grounded_source_contracts.json
  - architecture/policy_design_case/layer3_g1_search_recall_freshness.json
  - architecture/policy_design_case/layer3_g2_readiness_manifest.json
  - architecture/policy_design_case/layer3_g2_l2_skg_search_ledgers.json
  - architecture/policy_design_case/layer3_g2_l2_skg_query_traces.json
  - architecture/policy_design_case/layer3_g2_l2_skg_index_coverage.json
  - architecture/policy_design_case/layer3_g2_search_recall_freshness.json
  - architecture/policy_design_case/layer3_g2_forecast_support_bindings.json
  - architecture/policy_design_case/layer3_g2_method_requirement_bindings.json
  - architecture/policy_design_case/layer3_g2_semantic_spine_bindings.json
  - architecture/policy_design_case/layer3_g2_w12d_consumer_gate.json
  - architecture/policy_design_case/layer3_g2_grounded_forecast_handoffs.json
  - architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json
  - architecture/policy_design_case/layer2_floor_governance.toml
  - src/polisyos/runtime/quality/ir_analytics_bridge.py
  - src/polisyos/runtime/quality/layer2_predictive_knowledge.py
  - src/polisyos/ir/analytics/README.md
  - src/polisyos/ir/artifacts/README.md
cells_closed: []
layer_cells_advanced:
  - layer3.analytics_search_adapter
  - layer3.g3_l2_skg_proof_candidate_route
  - layer3.g3_ir_analytics_catalog_search
  - layer3.g3_ir_artifact_store_index
  - layer3.g3_certificate_resolution
  - layer3.g3_proof_carrying_bindings
  - layer3.g3_ir_analytics_bridge_generalization
  - layer3.g3_s11_predictive_posture_bridge
  - layer3.g3_claim_registry_consumer_gate
  - layer3.g3_baseline_comparison_consumer_gate
  - layer3.g3_proof_authority_surface
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g3_analytics_search_readiness_gate
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G3 - Analytics Search Engine

## For agentic workers

This is an executable slice spec, not strategy. Follow it red-first. G3
generalizes the existing `ir_analytics_bridge` exemplar into a real Layer 3
analytics search and adapter path. The goal is not to invent a new proof engine:
reuse existing IR analytics contracts, CAS helpers, Foundry/Scientist proof
producers, method requirements, claim-registry consumption, and S11 predictive
knowledge builders.

G3 closes only when at least one claim binds to a resolved, typed
proof/certificate artifact and that binding is consumed through S11,
`ir_analytics_bridge`, claim registry, baseline comparison, and W12D. A string
such as `certificate://...`, a search hit, a fixture row, or a bridge binding
without a resolved payload is not a certificate for G3 closure. Search discovers
candidates; adapters translate and downgrade; existing S11 and claim-registry
consumers decide what can be consumed. No G3 artifact may claim promotion,
recommendation, closeout, publication, useful-design credit, or agent authority.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.
`expected_open_cell_count: 0` refers to the existing Layer 2 cluster-map/open-cell
model that G3 does not mutate. Layer 3 G3 progress is measured by analytics
search readiness, proof/certificate resolution, `ProofCarryingAnalyticsRecord`
validity, S11 consumer binding, bridge/generalization compatibility, conformance
negatives, search recall/freshness, and health ledgers.

## Intro

G3 builds the proof-carrying analytics search engine. Given a claim, comparison
context, method requirement, and already-grounded G1/G2 substrate where
available, G3 searches the canonical L2/SKG proof-candidate substrate already
lifted by G2 plus existing IR analytics/proof surfaces and artifact stores,
resolves candidate certificates into typed payloads or CAS refs, validates
method and composability obligations, and translates only conformance-valid
candidates into existing S11 `ProofCarryingAnalyticsRecord` artifacts and
`ir_analytics_bridge` bindings.

The primary existing substrates are:

- `src/polisyos/runtime/quality/ir_analytics_bridge.py`
  - Claim-bound bridge from IR analytics refs to runtime claim registry.
  - Already fails when required IR analytics are missing, when a negative
    certificate blocks a claim, or when method requirements lack required
    certificate/uncertainty/limitation refs.
- `src/polisyos/runtime/quality/layer2_predictive_knowledge.py`
  - Existing S11 waist artifacts: `ProofCarryingAnalyticsRecord`,
    `PredictiveAxisCalibrationRecord`, `PredictiveAxisUpgradeRecord`,
    `S11PredictiveKnowledgeIntegrityReport`, and S11 authority envelope checks.
- `src/polisyos/ir/analytics/**`
  - Typed proof/certificate surfaces, including `ProofBundle`,
    `ProofComposabilityCertificate`, `NegativeCertificate`,
    `BoundsDualCertificateBundle` / `StratifiedLPDualCertificateBundle`
    certified-bounds bundles, abstraction certificates, transportability,
    uncertainty, strategic and recourse proof surfaces.
- `src/polisyos/ir/artifacts/**`
  - CAS-backed `ArtifactStore`, `put_json_artifact`, `get_json_artifact`, and
    typed persisted refs.
- `src/polisyos/ir/schemas/catalog.py`
  - Reflection catalog for IR types and exports. This is a catalog input, not a
    per-request linear search mechanism.
- G2 canonical L2/SKG route:
  - `layer3_g2_l2_skg_search_ledgers.json`,
    `layer3_g2_l2_skg_query_traces.json`,
    `layer3_g2_l2_skg_index_coverage.json`, and
    `layer3_g2_search_recall_freshness.json`.
  - These are the current G3 L2 substrate route in this checkout. G3 may consume
    them as proof-candidate context and must not replace them with an IR-only
    catalog surrogate when the master plan says "L2/IR".
- `src/polisyos/foundry/methods/catalog/causal/causal_engine/**`
  - Existing deterministic proof producers. Prefer public `CausalEngine.run(...)`
    or `audit(...)` with an `ArtifactStore`; they already persist proof bundles,
    proof traces, proof-composability certificates, bounds bundles, data-readiness
    reports, and negative certificates. Private materialization helpers are
    Foundry internals, not the long-term G3 closure API.
- `src/polisyos/scientist/methods/search/funnel/level2_causal.py`
  - Existing Scientist fast causal plausibility stage that persists proof,
    bounds, data-readiness, and negative-certificate refs when an artifact store
    is supplied. Treat it as an opportunistic transition producer: warnings or a
    missing artifact store cannot close G3 by themselves.
- `src/polisyos/method_requirement/**`
  - Claim-bound method validity requirement compiler and requirements consumed
    by `ir_analytics_bridge`.
- `src/polisyos/runtime/quality/claim_registry.py` and
  `src/polisyos/scientist/policy_design/baseline_compiler.py`
  - Downstream consumers of `ir_analytics_bridge` proof refs.
- `src/polisyos/runtime/quality/public_export.py` and
  `src/polisyos/runtime/quality/projection_semantics.py`
  - Existing public/projection path exposes S11 proof and bridge refs as
    projection-only audit semantics. It does not resolve those refs or expose
    G3 certificate-resolution/search-ledger status today; G3 must add that as
    G3 audit refs/status, not raw public proof payloads.
- G2 generated artifacts:
  - `layer3_g2_forecast_support_bindings.json`
  - `layer3_g2_method_requirement_bindings.json`
  - `layer3_g2_semantic_spine_bindings.json`
  - `layer3_g2_grounded_forecast_handoffs.json`
  - `layer3_g2_w12d_consumer_gate.json`

G3 must preserve the cost-shaped W12D route: one full first-case consumer proof
where needed and lightweight posture refs elsewhere. It must not turn W12D into
a full proof-search stress test for every corpus case unless a later plan
explicitly asks for that.

## Closure Contract

Source of truth: roadmap G3 closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`,
especially the G3 "Analytics Search Engine" slice.

G3 must deliver:

1. **G0/G1/G2 dependency gate** proving Layer 3 discovery discipline,
   engineering quality, search recall/freshness, G1 grounded source contracts,
   and G2 S10/method/semantic-spine handoffs are healthy before G3 emits S11
   posture for the current sequential implementation path. G3 can support
   standalone proof binding with only G0, but W12D/S11 closure in this checkout
   consumes G1/G2.
2. **L2/SKG + IR analytics search route** over the canonical G2 L2/SKG search
   ledgers/query traces where they provide claim/effect/proof-candidate context,
   plus existing IR analytics contracts and proof-producing surfaces. G3 may use
   `get_ir_schema_catalog()` and the curated analytics facade as catalog inputs,
   but per-request search must query a materialized/indexed catalog view with
   module, type, field, ref, producer, certificate-kind, proof-status,
   composability, uncertainty, and persistence capability fields. Do not
   hardcode a list of proof modules or certificate class names as the closure
   mechanism, and do not let an IR-only catalog stand in for the L2 side of
   "L2/IR" when G2's canonical SKG route is available.
3. **Artifact-store and certificate-resolution route** that resolves candidate
   refs to typed certificate/proof payloads through existing CAS helpers or
   existing deterministic producers. A candidate is certificate-resolved only
   when it validates as one of the existing typed IR proof/certificate surfaces
   or as an S11 `ProofCarryingAnalyticsRecord` built from them. Unresolved refs
   are candidate context only.
4. **Replayable G3 search ledgers** for IR catalog search, CAS/artifact-store
   search, selected candidates, rejected candidates, no-hits, budget cutoffs,
   producer execution, certificate resolution, and abstention. Search ledgers
   are control-plane evidence, never proof authority.
5. **Search recall/freshness report** with known-groundable seeds for IR schema
   catalog entries, proof/certificate producers, and a resolved certificate
   fixture produced by existing code. False no-hit caused by stale catalog,
   stale CAS index, or poor recall is `search_ceiling_repair_required`, not a
   proof-domain ceiling.
6. **Generalized adapter path** that converts valid IR/Scientist/Foundry proof
   outputs into existing `ProofCarryingAnalyticsRecord` records through
   `build_proof_carrying_analytics_record`, then builds the existing
   `ir_analytics_bridge` through `build_ir_analytics_claim_bridge`.
7. **Proof/certificate integrity binding** proving that every G3 positive proof
   record has at least one resolved non-blocking proof/certificate source:
   `proof_bundle_ref`, `proof_trace_ref`, `ir_certificate_ref`,
   `proof_composability_ref`, `dual_certificate_ref`, or an accepted typed
   positive certificate payload. `negative_certificate_ref` and `uncertainty_ref`
   are resolved evidence too, but they are blocking/limiting evidence rather than
   positive-proof closure by themselves. Missing required certificate refs fail
   closed.
8. **Method-requirement binding** reusing G2/W7.C `MethodValidityRequirementSpec`
   and existing `ir_analytics_bridge` requirement validation. Point
   identification requires certificate refs; bounds require uncertainty/bounds
   refs; negative-certificate requirements must not be satisfied by positive
   method output.
9. **S11 prerequisite binding** proving S6 floor refs and S10 forecast refs are
   present before G3 emits any S11 predictive posture. G3 must not fabricate
   S6/S10 fields from a proof search hit.
10. **S11 posture bridge** using existing
    `build_predictive_axis_calibration_record`,
    `build_predictive_axis_upgrade_record`,
    `verify_s11_predictive_knowledge_authority_envelope`,
    `build_s11_predictive_knowledge_posture`, and
    `summarize_s11_predictive_knowledge_integrity`. G3 may wrap these records
    for audit, but the waist artifact remains S11.
11. **Claim-registry consumer gate** proving `build_runtime_claim_registry` or
    normalized claim-registry paths consume the G3 `ir_analytics_bridge` and
    block/limit claims correctly when proof status, composability, method
    requirements, uncertainty, or negative certificates demand it.
12. **Baseline-comparison consumer gate** proving
    `BaselineComparisonCompiler` preserves G3 IR analytics/certificate refs as
    comparison evidence without upgrading them to recommendation or closeout
    authority.
13. **W12D consumer gate** proving G3 can replace fixture-style S11 proof refs
    for at least the first full S2/S11 consumer case, while preserving the
    existing lightweight pattern for remaining cases. Fixture-generated
    `certificate://layer2/s11/...` refs can remain as regression anchors, but
    cannot count as G3 closure.
14. **Proof/certificate surface** across PUBLIC/REVIEWER/EXPERT/MACHINE.
    EXPERT/MACHINE must see proof/certificate refs, search frontier refs,
    certificate resolution status, method requirement refs, proof status,
    composability status, uncertainty refs, limitation/blocker refs, and
    authority boundary. PUBLIC/REVIEWER may use existing S11 projection/public
    export semantics: high-level limitation, denied uses, and projection-only
    G3 resolution/search audit refs/status are visible; raw proof payloads, raw
    CAS manifests, and raw search ledgers may be out of scope for those
    audiences.
15. **All five Layer 3 health deltas** updated from the G3 perspective:
    envelope expansion, adapter semantic loss, governance throughput,
    demand-pull versus abstention, and search recall/freshness. Primary G3
    readings are semantic loss, governance throughput, and certificate search
    recall/freshness.
16. **Conformance and negative controls** proving no search-hit laundering, no
    fixture-certificate laundering, no unresolved-certificate binding, no
    negative-certificate ignoring, no proof-composability bypass, no
    method-requirement bypass, no S11 predictive posture without S6/S10, no
    PUBLIC raw-proof leakage, no recommendation/claim/closeout authority leak,
    no hardcoded analytics-module closure, no stale-index proof-domain ceiling,
    and no raw engine output without adapter validation.
17. **Adapter admission and registry conformance** through the shared G0/G1/G2
    discipline: G3 must write a slice-local
    `layer3_g3_adapter_contract_registry.toml`, load it through
    `load_adapter_contract_registry(path=...)`, run `validate_adapter_preservation`
    for the G3 adapter paths, persist G0-compatible `AdapterAdmissionRecord`
    rows, and block readiness on missing registry paths, semantic-loss blockers,
    unknown adapter paths, or unregistered engine touch-points.

Target done path: the same construct-agnostic analytics search mechanism
handles at least two request shapes, discovers a correctly-added synthetic IR
analytics/proof producer or certificate catalog entry without code changes,
resolves at least one real typed certificate/proof payload through existing IR
builders/loaders, emits at least one valid `ProofCarryingAnalyticsRecord`, builds
an `ir_analytics_bridge`, and proves downstream claim-registry, baseline
comparison, S11, and W12D consumption. An uncertified negative control must fail
closed.

Honesty escape path: for an individual request or W12D case, if L2/SKG + IR
catalog search, artifact-store/certificate resolution, G3 search ledgers,
recall/freshness, method-requirement validation, engineering quality, and
conformance negatives all pass, but the current evidence cannot validly produce
any positive proof binding, that request/case may be recorded as
`analytics_proof_domain_ceiling` with explicit reasons. This is not slice
closure by itself: the G3 slice still requires at least one resolved typed
certificate/proof payload and end-to-end consumer chain. If recall, freshness,
certificate resolution, ledger completeness, method-requirement validation, or
engineering quality is unhealthy, the outcome is
`search_ceiling_repair_required`.

## Scope Boundaries

In scope:

- Implement the G3 analytics search and adapter layer in `runtime/quality`.
- Consume G0 search discipline, G1 grounded source contracts, and G2
  forecast/method/semantic-spine handoffs as prerequisites for S11/W12D closure.
- Consume G2 canonical L2/SKG coverage, ledgers, query traces, and
  recall/freshness as the current L2 side of the G3 "L2/IR" route.
- Search existing IR analytics contracts and proof-producing surfaces through a
  materialized/indexed catalog view.
- Search configured artifact stores or deterministic producer outputs for typed
  proof/certificate refs.
- Persist G3 search ledgers, catalog coverage, artifact-store index,
  certificate-resolution report, proof-carrying analytics records,
  `ir_analytics_bridge` output, S11 bindings, consumer gates, conformance
  report, health deltas, public-export projection refs, audit surface, adapter
  registry, and readiness manifest.
- Reuse existing S11 builders and existing `ir_analytics_bridge`; G3 may add a
  wrapper, not a second S11 or bridge contract.
- Add known-groundable seed recall/freshness and free-growth fixtures over the
  IR analytics catalog and certificate-resolution route.
- Add engineering-quality checks: indexed/materialized catalog query, bounded
  artifact-store indexing, lazy/streaming reads, strict Pydantic DTOs,
  deterministic replay, fail-closed exception handling, and no eager full-store
  scans per request.
- Add slice-local adapter contract registry/admission checks using the shared
  G0/G1/G2 adapter-preservation machinery.

Out of scope:

- No G4 promotion or production authority.
- No G5 proving-ground conversion or useful-design credit.
- No G6 agent/controller implementation.
- No GL legal mandate or temporal competence authority.
- No new causal/proof engine when existing Foundry/IR/Scientist producers can
  produce the required proof/certificate artifacts.
- No new parallel S11 contract or claim-registry contract.
- No direct PDC back-import from subordinate engines. G3 runtime code stays in
  `runtime/quality` and consumes PDC-facing DTOs through public/canonical
  boundaries.
- No claim that an IR catalog hit, search hit, bridge row, fixture ref, or raw
  engine output itself is proof support.
- No live network acquisition or mutation of `production_data` assets.
- No blanket full backend verification on a local MacBook unless explicitly
  requested; use targeted tests for this slice.

## Pattern Pass

| Pattern | G3 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | G3 schemas exist but no search producer, resolved certificate, bridge, consumer, or semantic negative proves the capability. | Add producer functions, persisted artifacts, S11/claim-registry/baseline/W12D consumers, readiness CLI, and negative tests. |
| P02 thin orchestration | IR contracts, proof producers, method requirements, and S11 records coexist but do not exchange binding artifacts. | Create explicit G3 bindings from IR search plus certificate resolution into `ProofCarryingAnalyticsRecord`, `ir_analytics_bridge`, and S11 posture. |
| P03 hidden internal richness | Certificate resolution and proof status live only inside internal JSON. | Add EXPERT/MACHINE proof surface and PUBLIC/REVIEWER limitation/denied-use projection via existing S11 semantics. |
| P04 status lattice gap | Local G3 statuses conflict with proof status, composability status, claim registry status, or S11 maturity. | Define local G3 states as wrappers around existing proof/S11/bridge dispositions; test mixed outcomes. |
| P05 authority dilution | A proof/certificate is mistaken for recommendation, claim, closeout, or publication authority. | Every G3/S11 artifact carries purpose-scoped `authority_boundary` and `may_not_use_for`; validator blocks leaks. |
| P07 rule replay gap | Proof/certificate binding cannot be replayed after IR schema, CAS, method, or S11 rule changes. | Store schema/rule versions, catalog snapshot hash, CAS manifest refs, producer refs, query predicates, method requirement refs, and time roles. |
| P08 time-role conflation | Proof generation time, artifact valid time, data valid time, S10 prediction time, and replay time collapse. | Carry S11/S10 time roles plus G3 catalog/index/generated times; block stale or context-mismatched proof reuse. |
| P09 warning lifecycle gap | Missing uncertainty, negative certificate, or rederive composability becomes a warning while the claim binds. | Treat missing required uncertainty, negative certificates, and blocking composability as fail-closed or explicit limitation. |
| P10 semantic adequacy gap | Validator only checks that a `ProofCarryingAnalyticsRecord` exists. | Add negatives for unresolved certificate, fixture certificate, search-hit laundering, negative-certificate ignoring, and method-requirement bypass. |
| P12 producer handshake gap | G1/G2 claim concepts, IR analytics outputs, and method requirements refer to different claims/comparisons. | Bind claim id, comparison refs, baseline/alternative refs, concept-spine refs, source contracts, method requirements, and S11 proof refs in one record. |
| P13 governance gravity | G3 grows a new proof engine or absorbs IR analytics into the waist. | Reuse IR/Foundry/Scientist proof producers and S11 waist contracts; add only Layer 3 search, adapter, gate, and audit wrappers. |
| P14 evidence independence inflation | Multiple proof refs from one run/source count as independent support. | Record proof-bundle refs, input refs, method lineage, source lineage, independence/collapse refs, and no strength upgrade from raw counts. |
| P15 LLM speculation laundering | LLM-selected proof path becomes certificate authority. | LLM output remains candidate search input only; typed proof/certificate payloads and deterministic validators decide. |
| P16 epistemic-regime laundering | Proof status implies predictive or policy strength under incompatible regimes. | Preserve S10/S11 regime and forecast-quality disposition; no proof-to-recommendation shortcut. |
| P25 search-control laundering | Search frontier, no-hit, fixture ref, or bridge row is projected as proof authority. | Persist G3 search ledgers and keep them control-plane only; proof binding must resolve typed certificates and pass S11/bridge validation. |
| Spine parallelism | G3 invents a second claim/concept/status lattice beside existing claim registry and semantic spine. | Reuse G1/G2 semantic-spine refs, claim ids, comparison refs, `MethodValidityRequirementSpec`, proof status, and S11 status vocabulary. |
| T7 false abstention | Poor IR/CAS recall or stale catalog creates fake proof-domain ceiling. | Known-groundable seeds and index freshness must pass before domain ceiling; otherwise emit `search_ceiling_repair_required`. |
| Rule 12 hardcode fallback | G3 passes because a short list of IR modules/certificate classes is hardcoded. | Free-growth fixture over IR analytics catalog and producer discovery; no hardcoded module/class list as closure path. |
| Engineering quality | Naive O(n) scans or eager CAS walks pass toy cases and fail at scale. | Materialized/indexed catalog, bounded artifact-store indexing, lazy reads, deterministic replay, fail-closed validation, and perf checks are required. |
| L2/IR route collapse | G3 implements only IR catalog search and forgets the L2/SKG side named by the master plan. | Bind G3 request context to G2 canonical SKG ledgers/query traces or explicitly fail the L2 dependency gate; IR catalog search cannot substitute for L2/SKG candidate provenance. |
| Registry bypass | G3 writes artifacts but never proves adapter admission through the shared registry/conformance harness. | Use slice-local `layer3_g3_adapter_contract_registry.toml`, `load_adapter_contract_registry(path=...)`, `validate_adapter_preservation`, G0-compatible `AdapterAdmissionRecord`, and readiness drift keys. |

## Capability Transition

| Capability | Start label after G2 | Pattern pressure | Target label after G3 |
| --- | --- | --- | --- |
| Analytics search adapter | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing` | P01/P02/P03/P10/P25/T7 | Implemented as an admitted adapter with maturity from the shared vocabulary (`fail_closed`/`predictive`/`calibrated`) and authority purpose `proof_carrying_analytics_validity`: indexed L2/SKG + IR search producer, resolved certificate refs, S11-valid proof records, bridge consumers, surfaces, conformance, recall/freshness, and negatives. |
| L2/SKG proof-candidate route | Existing G2 canonical route implemented; G3 binding not yet proven | P02/P12/P25/Rule 12 | Implemented as G3 request-to-G2-ledger/query-trace bindings proving L2 candidate provenance before IR certificate resolution; missing/stale G2 SKG route blocks G3 closure or becomes search-ceiling repair. |
| IR analytics catalog search | `producer_missing`, `verification_missing` | P13/P25/Rule 12 | Implemented coverage report over actual IR analytics contracts, public facade, schema catalog, proof/certificate producers, persistence helpers, free-growth fixture, and query traces. |
| Certificate resolution | `artifact_missing`, `verification_missing` | P01/P07/P10/P25 | Implemented resolver proving refs map to typed proof/certificate payloads or CAS manifests; unresolved refs are blocked. |
| `ir_analytics_bridge` generalization | `implemented_but_not_orchestrated` for Layer 3 search | P02/P05/P10/P12 | Implemented as G3 bridge output built from resolved proof records and method requirements, preserving existing bridge behavior as regression anchor. |
| S11 predictive posture binding | Existing Layer 2 implemented, but G3 proof path is fixture-like | P02/P05/P10/P25 | Implemented G3-to-S11 binding with resolved proof refs, S6/S10 prerequisites, calibration/upgrades, authority envelope, and W12D consumer gate. |
| Claim-registry and comparison consumers | Existing consumers, no G3 producer route | P02/P03/P10 | Implemented gates proving `ir_analytics_bridge` is consumed by claim registry and baseline comparison without authority leakage. |
| Proof/certificate audit surface | `surface_missing` | P03/P05 | Implemented PUBLIC/REVIEWER limitation/denied-use surface plus EXPERT/MACHINE proof/certificate audit details. |

## Code-Grounded Reality

### Existing Strengths

- Roadmap G3 is defined in the master plan under "G3 - Analytics Search
  Engine": producer = search + adapter; persisted = search-frontier ledger +
  proof-carrying bindings; bridge/consumer = S11 analytics consumers; surface =
  certificate refs in EXPERT/MACHINE.
- The vision doc names `ProofCarryingAnalyticsRecord` as a narrow-waist artifact
  and identifies `ir_analytics_bridge.py` as an exemplar adapter.
- `runtime/quality/layer2_predictive_knowledge.py` already has strict S11
  contracts and builders. `ProofCarryingAnalyticsRecord` requires claim,
  comparison, bridge refs, proof/certificate refs, authority denials, and can
  block via negative certificates or blocking proof/composability statuses.
- `runtime/quality/ir_analytics_bridge.py` already normalizes claim-bound IR
  analytics bindings, applies method requirements, exposes runtime authority
  boundaries, projects into claim registry, and blocks negative certificates.
- `method_requirement` already compiles claim-bound method requirements and
  encodes point/partial/bounds/negative-certificate obligations.
- `ir.analytics` already contains typed proof/certificate surfaces and CAS
  persistence helpers: `ProofBundle`, `NegativeCertificate`,
  `ProofComposabilityCertificate`, certified-bounds dual certificate bundles
  (`BoundsDualCertificateBundle`, `StratifiedLPDualCertificateBundle`,
  `CertifiedBoundsCertificateBundle`), abstraction, transportability,
  uncertainty, and strategic certificate families.
- `ir.artifacts` and `core.artifacts.store.FileSystemCAS` already provide the
  artifact-store boundary needed to persist and load proof/certificate payloads.
- Foundry causal engine already has public producer paths that materialize proof
  bundles, proof traces, composability certificates, bounds bundles, data
  readiness reports, and negative certificates through an artifact store.
  Scientist Level 2 causal plausibility can persist a subset of those refs, but
  its caught warning paths must be recorded as limitations, not proof closure.
- G2 already materializes the canonical L2/SKG route over
  `scholar_knowledge.duckdb`, query traces, recall/freshness, method-requirement
  bindings, semantic-spine bindings, and S10 forecast handoffs. G3 should bind
  to those artifacts where it needs L2 claim/effect/proof-candidate provenance,
  not rebuild or bypass them.
- PDC S2 already consumes `Layer2S11PredictivePostureInput`, and projection
  semantics already separate PUBLIC limitation from EXPERT/MACHINE proof refs.
- PDC S2 does more than display S11 refs: S11 predictive posture affects the
  constraint store, refinement decision, design/search ledger refs,
  run/iteration status, axis-position declaration, firewall status, and
  audience projection. G3 W12D tests must check these downstream effects for
  the first full case.
- W12D already emits S11 blocks and tests S6/S10/S11 consumption. This is a
  regression anchor for G3, not proof that Layer 3 analytics search exists.
- G1 already demonstrates the correct adapter-admission pattern through
  `load_adapter_contract_registry(path=...)` and
  `validate_adapter_preservation(...)`; G3 should reuse that loader-compatible
  grammar instead of creating another summary-only registry format.

### Existing Weak Spots G3 Must Not Underestimate

- Current W12D S11 proof refs are generated fixture-style in
  `_s11_proof_record`: `ir://layer2/s11/...`,
  `method-output://layer2/s11/...`, `certificate://layer2/s11/...`, and
  `proof-composability://layer2/s11/...`. These satisfy the S11 type shape but
  are not resolved G3 certificates.
- `ProofCarryingAnalyticsRecord` validates that refs exist, but it does not by
  itself prove those refs resolve to typed payloads. G3 must add a certificate
  resolution report and conformance gate.
- Existing S11 public/export code carries `proof_carrying_analytics_ref` and
  `ir_analytics_bridge_ref`, but it does not surface
  `certificate_resolution_report_ref`, `g3_search_ledger_ref`, resolved
  certificate counts, or resolution status. Without a G3 audit surface/public
  export ref binding, EXPERT/MACHINE see only string refs and replay remains
  hidden.
- `ir_analytics_bridge` is a bridge, not a search engine. G3 must not call a
  manually assembled bridge row "analytics search".
- G3 can accidentally collapse the master-plan "L2/IR" route into IR-only schema
  search. That is too narrow: when the current checkout has healthy G2 L2/SKG
  ledgers/query traces, G3 must bind request provenance to them or honestly fail
  the L2 dependency gate.
- `get_ir_schema_catalog()` reflects/imports modules. It is suitable for
  catalog construction, but not as a per-request O(n) closure path. G3 must
  materialize/cache/index the searchable catalog and record its snapshot.
- The analytics facade is curated and intentionally narrower than all modules.
  G3 catalog coverage must include defining modules and persistence helpers, not
  only root facade exports. `src/polisyos/ir/analytics/index.md` is a generated
  documentation/coverage sync marker; it must not be parsed as the authoritative
  search registry.
- There may not be a single global CAS/artifact store for all proof artifacts in
  local development. The resolver must handle configured stores, generated
  deterministic producer outputs, and explicit "unavailable" ceilings without
  pretending a no-hit is proof absence.
- CAS `iter_artifact_ids()` is a full manifest walk for filesystem stores and a
  remote object listing for remote/cached stores. The normal request/resolution
  path must not use full-store listing as search. G3 may use bounded index
  refresh jobs or selected refs, and must record backend/root/prefix and
  ownership/tenant mode in replay.
- Tenant-scoped CAS views enforce ownership. A manifest that exists but is not
  visible under the selected tenant/cell is a resolution denial/blocker, not a
  no-hit and not a proof-domain ceiling.
- A negative certificate is a real certificate. It should block or limit the
  claim, not disappear because it is inconvenient.
- A `BoundsBundleRef` with a `dual_certificate_ref` is only certified-bounds
  evidence if G3 follows and validates the nested dual-certificate payload via
  `load_dual_certificate_bundle(...)` and
  `validate_bounds_certificate_bundle(...)`. Bounds search must not overclaim
  sharpness from the bounds bundle alone.
- Proof composability status matters. `rederive` and blocking statuses cannot
  be replayed as reusable proof.
- Claim registry and baseline comparison already consume bridge refs, but they
  rely on the bridge being truthful. G3 must validate before consumer injection.
- W12D should not rerun heavyweight proof generation for every case. Keep one
  full first-case proof and lightweight refs elsewhere unless explicitly
  broadened later.
- Existing claim-registry, baseline-comparison, and S11 tests already cover much
  of the downstream blocking behavior. G3 should add integration tests proving a
  G3-produced resolved bridge reaches those consumers, instead of duplicating or
  rewriting their internal validation logic.
- Heavy producer paths (`CausalEngine`, DuckDB/HNSW/vector dependencies,
  Foundry/Scientist proof execution) should be imported lazily inside builder or
  producer functions. Importing `polisyos.runtime.quality.layer3_analytics_search`
  must stay cheap and must not build catalogs, scan CAS, open DuckDB, or import
  producer engines at module load.

## Target File Map

Create:

- `src/polisyos/runtime/quality/layer3_analytics_search.py`
  - Owns G3 DTOs, L2/SKG proof-candidate bindings, search ledgers, IR catalog
    coverage, artifact-store index, certificate resolution, proof bindings, S11
    bindings, consumer gates, audit surface, adapter admission bundle, readiness
    bundle builder, and validator.
- `tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py`
  - CLI/readiness wrapper mirroring G2: validates runtime bundle, validates
    persisted artifacts, writes artifacts in `--write` mode, and reports issue
    codes.
- `tests/unit/runtime/quality/test_layer3_g3_analytics_search.py`
  - Unit tests for DTO strictness, catalog search, certificate resolution,
    proof record construction, bridge behavior, S11 binding, negatives, and
    engineering quality.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness.py`
  - Repo-quality validator tests for persisted artifacts, manifest/runtime
    drift, generated-artifact registration, surfaces, authority leaks,
    canonical search, recall/freshness, and negative controls.
- `tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness_cli.py`
  - CLI tests for JSON/text output, write mode, issue-code reporting, and
    expected artifact paths.
- `docs/reference/policy-design-case-layer3-analytics-search.md`
  - All-audience proof/certificate reference, EXPERT/MACHINE audit details,
    validator command, artifacts, fields, and authority boundaries.

Modify:

- `architecture/generated_artifacts.toml`
  - Register a separate G3 generated-artifact family, source of truth,
    verifier, regeneration command, commit policy, freshness rule, drift gate,
    output paths, and workflow check command.
- `docs/reference/generated-artifacts.md`
  - Regenerate/update from `architecture/generated_artifacts.toml`; do not use
    this as the source of truth.
- `architecture/policy_design_case/inventory.json`
  - Register `layer3_g3_proof_carrying_audit_surface` and all persisted G3
    artifacts.
- `docs/reference/public-surface.md`
  - Modify only if the repo's public-surface policy or readiness validator
    requires this global index to mention the G3 surface. The primary G3 surface
    contract is the slice reference page, `inventory.json`, generated-artifact
    registration, and projection-only `public_export` audit refs/status. Do not
    expose private G3 DTOs through public facades or global public-surface docs
    just to satisfy a checklist.
- `src/polisyos/runtime/quality/public_export.py`
  - Add projection-only G3 resolution/search audit refs to public export
    semantics when a G3 proof-carrying audit surface is present. Keep raw proof
    payloads and raw search ledgers out of PUBLIC output.
- `tests/unit/runtime/quality/test_public_export.py`
  - Add regression tests proving G3 resolution report/search-ledger refs are
    visible as audit refs/status only, while raw proof payloads remain redacted.
- `docs/reference/documentation-inventory.md`
  - Add the G3 reference page and validator command.
- `docs/reference/index.md`
  - Add the G3 reference page to the reference index.
- `mkdocs.yml`
  - Modify only if the repo navigation requires explicit reference-page entries.
- `tools/quality/validation/run_universal_outcome_corpus.py`
  - Add a G3 W12D gate by mirroring the G2 gate pattern and wiring resolved
    G3 proof refs into the first full S11/S2 consumer path. Preserve existing
    fixture-style S11 behavior as regression/transition context, but do not let
    fixture refs count as G3 closure.
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
  - Add G3 route tests where W12D already exercises Layer 3 gates and S11
    posture consumption.

Persist generated artifacts:

- `architecture/policy_design_case/layer3_g3_adapter_admission_registry.json`
- `architecture/policy_design_case/layer3_g3_l2_skg_proof_candidate_bindings.json`
- `architecture/policy_design_case/layer3_g3_ir_analytics_search_ledgers.json`
- `architecture/policy_design_case/layer3_g3_ir_analytics_query_traces.json`
- `architecture/policy_design_case/layer3_g3_ir_catalog_coverage.json`
- `architecture/policy_design_case/layer3_g3_ir_artifact_store_index.json`
- `architecture/policy_design_case/layer3_g3_certificate_resolution_report.json`
- `architecture/policy_design_case/layer3_g3_search_recall_freshness.json`
- `architecture/policy_design_case/layer3_g3_method_requirement_bindings.json`
- `architecture/policy_design_case/layer3_g3_semantic_spine_bindings.json`
- `architecture/policy_design_case/layer3_g3_proof_carrying_analytics_records.json`
- `architecture/policy_design_case/layer3_g3_ir_analytics_claim_bridge.json`
- `architecture/policy_design_case/layer3_g3_s11_prerequisite_bindings.json`
- `architecture/policy_design_case/layer3_g3_s11_calibration_bindings.json`
- `architecture/policy_design_case/layer3_g3_s11_predictive_posture_bindings.json`
- `architecture/policy_design_case/layer3_g3_claim_registry_consumer_gate.json`
- `architecture/policy_design_case/layer3_g3_baseline_comparison_consumer_gate.json`
- `architecture/policy_design_case/layer3_g3_w12d_consumer_gate.json`
- `architecture/policy_design_case/layer3_g3_public_export_projection_refs.json`
- `architecture/policy_design_case/layer3_g3_proof_carrying_audit_surface.json`
- `architecture/policy_design_case/layer3_g3_conformance_report.json`
- `architecture/policy_design_case/layer3_g3_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_g3_adapter_contract_registry.toml`
- `architecture/policy_design_case/layer3_g3_readiness_manifest.json`

Readiness-selected manifest/runtime drift keys:

- `schema_version`
- `rule_version`
- `g0_dependency_status`
- `g1_dependency_status`
- `g2_dependency_status`
- `g3_l2_skg_dependency_status`
- `g3_l2_skg_proof_candidate_binding_count`
- `g3_ir_catalog_coverage_status`
- `g3_ir_artifact_store_index_status`
- `g3_search_ledger_count`
- `g3_query_trace_count`
- `g3_certificate_resolution_status`
- `g3_resolved_certificate_count`
- `g3_method_requirement_binding_count`
- `g3_proof_carrying_record_count`
- `g3_ir_analytics_bridge_status`
- `g3_s11_prerequisite_binding_status`
- `g3_s11_predictive_posture_binding_count`
- `g3_claim_registry_consumer_gate_status`
- `g3_baseline_comparison_consumer_gate_status`
- `g3_w12d_consumer_gate_status`
- `g3_public_export_projection_status`
- `g3_search_engineering_quality_status`
- `g3_conformance_status`
- `g3_adapter_contract_registry_status`
- `g3_adapter_contract_path_count`
- `g3_health_metric_ids`

Do not compare every summary count blindly. Follow G2's selected-key drift
pattern so the gate remains stable while still catching load-bearing mismatches.

## Runtime Contract Sketch

Use strict Pydantic DTOs (`extra="forbid"`) and stable schema/rule constants:

- `LAYER3_G3_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g3_analytics_search.v1"`
- `LAYER3_G3_RULE_VERSION = "policyos.layer3.g3.analytics_search.v1"`
- `LAYER3_G3_SURFACE_ID = "layer3_g3_proof_carrying_audit_surface"`

Core DTOs:

- `Layer3G3ValidationIssue`
- `Layer3G3ValidationReport`
- `Layer3G3AnalyticsRequest`
- `Layer3G3L2SkgProofCandidateBinding`
- `Layer3G3IRCatalogSearchLedger`
- `Layer3G3IRAnalyticsQueryTrace`
- `Layer3G3IRCatalogCoverageReport`
- `Layer3G3ArtifactStoreIndex`
- `Layer3G3CertificateCandidate`
- `Layer3G3CertificateResolutionRecord`
- `Layer3G3CertificateResolutionReport`
- `Layer3G3SearchRecallSeed`
- `Layer3G3IndexFreshnessRecord`
- `Layer3G3SearchRecallFreshnessReport`
- `Layer3G3MethodRequirementBinding`
- `Layer3G3SemanticSpineBinding`
- `Layer3G3ProofCarryingAnalyticsBinding`
- `Layer3G3IRAnalyticsBridgeBinding`
- `Layer3G3S11PrerequisiteBinding`
- `Layer3G3S11CalibrationBinding`
- `Layer3G3S11PredictivePostureBinding`
- `Layer3G3ClaimRegistryConsumerGateRecord`
- `Layer3G3BaselineComparisonConsumerGateRecord`
- `Layer3G3W12DConsumerGateRecord`
- `Layer3G3PublicExportProjectionRefSurface`
- `Layer3G3SearchEngineeringQualityReport`
- `Layer3G3AdapterContractRegistryStatus`
- `Layer3G3AdapterAdmissionBundle`
- `Layer3G3ConformanceReport`
- `Layer3G3ProofCarryingAuditSurface`
- `Layer3G3GeneratedArtifactRegistrationStatus`
- `Layer3G3ReadinessManifest`
- `Layer3G3Bundle`

Core functions:

- `build_layer3_g3_bundle(repo_root: Path) -> Layer3G3Bundle`
- `validate_layer3_g3_bundle(repo_root: Path, persisted: Mapping[str, Any] | Layer3G3Bundle) -> Layer3G3ValidationReport`
- `build_g3_l2_skg_proof_candidate_bindings(repo_root: Path, request: Layer3G3AnalyticsRequest) -> tuple[Layer3G3L2SkgProofCandidateBinding, ...]`
  binding the G3 request to G2 canonical L2/SKG ledgers, query traces, SKG
  coverage, and recall/freshness artifacts.
- `build_g3_ir_catalog_coverage(repo_root: Path) -> Layer3G3IRCatalogCoverageReport`
  using `get_ir_schema_catalog()` as catalog source and materializing an indexed
  search view for G3 query/replay.
- `search_ir_analytics_for_proof_candidates(request: Layer3G3AnalyticsRequest, repo_root: Path) -> tuple[Layer3G3IRCatalogSearchLedger, ...]`
  searching the materialized catalog, not a hardcoded module/class list.
- `build_g3_ir_artifact_store_index(repo_root: Path, store_config: Mapping[str, Any] | None = None) -> Layer3G3ArtifactStoreIndex`
  indexing configured CAS manifests and deterministic producer outputs with
  bounded/lazy reads.
- `run_g3_deterministic_proof_producer(...) -> Layer3G3CertificateResolutionRecord`
  using existing public producers, preferably `CausalEngine.run(...)` with a
  deterministic `FileSystemCAS`/configured `ArtifactStore`, to create the
  first-case resolved proof/certificate route when no suitable persisted ref is
  already present.
- `resolve_g3_certificate_candidates(...) -> Layer3G3CertificateResolutionReport`
  resolving refs/payloads through existing IR loaders/builders and recording
  typed validation status.
- `build_g3_method_requirement_bindings(...) -> tuple[Layer3G3MethodRequirementBinding, ...]`
  reusing existing `MethodValidityRequirementSpec` and G2 method bindings where
  available.
- `build_g3_proof_carrying_analytics_records(...) -> tuple[ProofCarryingAnalyticsRecord, ...]`
  using `build_proof_carrying_analytics_record`; search hits without resolved
  certificates are blocked.
- `build_g3_ir_analytics_claim_bridge(...) -> dict[str, Any]`
  using `build_ir_analytics_claim_bridge`, not a parallel bridge contract.
- `build_g3_s11_predictive_posture(...) -> Layer3G3S11PredictivePostureBinding`
  using existing S11 builders and S6/S10 prerequisites.
- `build_g3_claim_registry_consumer_gate(...) -> Layer3G3ClaimRegistryConsumerGateRecord`
  proving bridge consumption and negative-certificate blocking.
- `build_g3_baseline_comparison_consumer_gate(...) -> Layer3G3BaselineComparisonConsumerGateRecord`
  proving comparison evidence consumption without recommendation authority.
- `build_g3_w12d_consumer_gate(...) -> Layer3G3W12DConsumerGateRecord`
  proving first-case full consumer and lightweight refs elsewhere, including S2
  search-ledger refs, constraint-store entries, refinement/run status,
  axis-position/firewall status, and unchanged G0/G1/G2 outcomes.
- `build_g3_public_export_projection_refs(...) -> Layer3G3PublicExportProjectionRefSurface`
  binding the G3 certificate-resolution report/search-ledger refs into public
  export/projection audit semantics without raw proof payload leakage.
- `build_g3_adapter_admission_bundle(repo_root: Path, bundle: Layer3G3Bundle) -> Layer3G3AdapterAdmissionBundle`
  loading `layer3_g3_adapter_contract_registry.toml`, running
  `validate_adapter_preservation`, and emitting G0-compatible admission records.
- `validate_g3_adapter_conformance(repo_root: Path, bundle: Layer3G3Bundle) -> Layer3G3ConformanceReport`
- `build_g3_proof_carrying_audit_surface(bundle: Layer3G3Bundle) -> Layer3G3ProofCarryingAuditSurface`
- `build_g3_generated_artifact_registration_status(repo_root: Path) -> Layer3G3GeneratedArtifactRegistrationStatus`

Resolver matrix for the first implementation:

| Candidate kind | Existing loader / validator | G3 closure semantics |
| --- | --- | --- |
| `ProofBundleRef` | `load_proof_bundle(...)` | Positive proof only when status/composability are non-blocking and required method/prerequisite refs are present. |
| `ProofComposabilityCertificateRef` | `load_proof_composability_certificate(...)` | `reusable` can support proof reuse; `rederive`/broken/invalidation statuses block reuse. |
| `NegativeCertificateRef` | `load_negative_certificate(...)` | Valid evidence, usually blocking or limiting; never satisfies positive-proof closure by itself. |
| `BoundsBundleRef` | `load_bounds_bundle(...)`; when `dual_certificate_ref` is present or sharp/certified bounds are claimed, follow `load_dual_certificate_bundle(...)` and `validate_bounds_certificate_bundle(...)` | Bounds/uncertainty evidence; can support bounded proof only with method requirement and uncertainty semantics preserved. It is certified-bounds evidence only when the nested dual certificate validates. |
| `DualCertificateRef` | `load_dual_certificate_bundle(...)` + `validate_bounds_certificate_bundle(...)` | Certified-bounds evidence; use precise `BoundsDualCertificateBundle` / `StratifiedLPDualCertificateBundle` names, not a generic `DualCertificate` class. |
| Other persisted IR certificate refs | Existing module `load_*_certificate(...)` helpers discovered in catalog build | Candidate-specific evidence only when typed validation succeeds and authority boundary is preserved. |
| S11 `ProofCarryingAnalyticsRecord` | `build_proof_carrying_analytics_record(...)` after resolver pass | Waist artifact for consumers; unresolved string refs cannot be laundered into S11 closure. |

The resolver must operate on selected candidates and configured stores, not by
full eager CAS walks. Missing store configuration, stale index state, or a
Scientist warning path is `search_ceiling_repair_required` / producer limitation,
not proof absence.

Minimum G3 issue-code families:

- Dependency/search: `layer3_g3_g0_dependency_not_ready`,
  `layer3_g3_g1_dependency_not_ready`, `layer3_g3_g2_dependency_not_ready`,
  `layer3_g3_l2_skg_dependency_missing`,
  `layer3_g3_l2_skg_route_not_bound`,
  `layer3_g3_ir_only_route_overclaimed_as_l2_ir`,
  `layer3_g3_search_recall_seed_miss_blocks_domain_ceiling`,
  `layer3_g3_stale_index_blocks_domain_ceiling`.
- Catalog/engineering: `layer3_g3_ir_catalog_not_materialized`,
  `layer3_g3_ir_catalog_doc_source_overclaimed`,
  `layer3_g3_manual_class_list_closure`,
  `layer3_g3_search_engineering_quality_failed`,
  `layer3_g3_artifact_store_full_scan_used_for_request`,
  `layer3_g3_heavy_producer_import_at_module_load`.
- Certificate/proof: `layer3_g3_certificate_ref_unresolved`,
  `layer3_g3_certificate_payload_type_invalid`,
  `layer3_g3_bounds_dual_certificate_missing`,
  `layer3_g3_bounds_sharpness_overclaimed`,
  `layer3_g3_tenant_scoped_manifest_denied`,
  `layer3_g3_negative_certificate_used_as_positive_proof`,
  `layer3_g3_proof_composability_rederive_blocks_reuse`,
  `layer3_g3_fixture_certificate_laundering`,
  `layer3_g3_scientist_warning_used_as_closure`.
- Consumers/authority: `layer3_g3_s11_prerequisite_missing`,
  `layer3_g3_ir_analytics_bridge_missing`,
  `layer3_g3_claim_registry_consumer_missing`,
  `layer3_g3_baseline_comparison_consumer_missing`,
  `layer3_g3_w12d_not_routed_closeout`,
  `layer3_g3_s2_consumer_effect_missing`,
  `layer3_g3_public_export_resolution_ref_missing`,
  `layer3_g3_claim_authority_leak`,
  `layer3_g3_recommendation_authority_leak`,
  `layer3_g3_closeout_authority_leak`.
- Adapter/registry: `layer3_g3_adapter_contract_registry_missing`,
  `layer3_g3_adapter_registry_summary_toml_not_loader_compatible`,
  `layer3_g3_adapter_contract_path_unknown`,
  `layer3_g3_adapter_semantic_loss`.

Do not expose private helper DTOs through public package facades unless the
package public-surface policy requires it. G3 runtime can remain an internal
quality module with documented audit artifacts.

## Adapter Semantics

G3 uses four-stage admission:

1. **Discoverable analytics candidate**
   - IR type, producer, artifact ref, proof bundle, certificate payload, or
     bridge-compatible row exists.
   - It may inform the frontier and rejection set.
   - It is not proof authority.
2. **Executable or resolvable candidate**
   - Existing producer can produce a proof/certificate payload, or an existing
     artifact ref resolves through an existing loader.
   - A failed producer or unresolved ref becomes a replayed rejection/no-hit.
   - It is still not a S11 proof record.
3. **Proof-bound candidate**
   - Claim id, comparison refs, method requirement refs, proof/certificate refs,
     proof status, composability status, uncertainty refs, limitation/blocker
     refs, source/method lineage, and authority boundary are present.
   - Existing S11 `ProofCarryingAnalyticsRecord` validates the payload.
   - It may be bridged through `ir_analytics_bridge`.
4. **S11/consumer-valid proof**
   - Existing `ir_analytics_bridge`, S11 builders, claim-registry gate,
     baseline-comparison gate, projection semantics, and W12D gate accept it.
   - It may be consumed as proof-carrying analytics validity only.
   - It remains shadow/governed for the declared proof purpose, not
     recommendation, claim, promotion, closeout, or publication authority.

Status rules:

- `identified`/`bounded` plus reusable or revalidate composability can bind only
  when method requirements and uncertainty/limitation refs are satisfied.
- `partial`, `limited`, and `contested` can bind only with explicit limitations
  and no strength upgrade.
- `not_identified`, `blocked`, `negative`, `refuted`, or negative-certificate
  refs block the claim/proof upgrade and must surface blocker refs.
- `rederive` composability blocks replay as reusable proof.
- Missing required certificate or uncertainty refs fail closed.
- Fixture refs may be retained as transition/regression context but never count
  as resolved G3 certificates.

## Implementation Tasks

### Task 0: G3 Red Baseline And Dependency Probe

**Files:**

- Create: `tests/unit/runtime/quality/test_layer3_g3_analytics_search.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness.py`
- Create: `tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness_cli.py`

Steps:

- [x] Add failing tests that import
  `polisyos.runtime.quality.layer3_analytics_search` and assert the module
  exposes schema/rule constants, bundle builder, validator, DTOs, and issue-code
  surfaces listed in this plan.
- [x] Add a failing repo-quality test that
  `validate_layer3_g3_readiness(REPO_ROOT)` returns pass only when persisted
  artifacts match the runtime bundle.
- [x] Include red assertions that certificate resolution, proof-carrying
  records, L2/SKG proof-candidate bindings, `ir_analytics_bridge`, S11 bindings,
  adapter admission, and consumer gates are persisted and included in the
  readiness manifest/write path.
- [x] Add a failing CLI test mirroring G2: `--output-format json` reports
  `schema_version`, `status`, `summary`, and `issues`; `--write` reports written
  G3 artifact paths including JSON and TOML artifacts.
- [x] Run:
  `uv run pytest tests/unit/runtime/quality/test_layer3_g3_analytics_search.py tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness_cli.py -q`
  and confirm the failure is module/CLI absence, not unrelated environment
  drift.

### Task 1: L2/SKG And IR Analytics Catalog Coverage And Search Ledgers

**Files:**

- Create: `src/polisyos/runtime/quality/layer3_analytics_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g3_analytics_search.py`

Steps:

- [x] Implement strict DTOs for `Layer3G3AnalyticsRequest`,
  `Layer3G3L2SkgProofCandidateBinding`,
  `Layer3G3IRCatalogSearchLedger`, `Layer3G3IRAnalyticsQueryTrace`,
  `Layer3G3IRCatalogCoverageReport`, and validation issue/report.
- [x] Load and validate G2 canonical L2/SKG dependency artifacts:
  `layer3_g2_l2_skg_search_ledgers.json`,
  `layer3_g2_l2_skg_query_traces.json`,
  `layer3_g2_l2_skg_index_coverage.json`, and
  `layer3_g2_search_recall_freshness.json`. Missing, stale, or unhealthy G2
  SKG route blocks G3 closure or emits `search_ceiling_repair_required`.
- [x] Build G3 L2/SKG proof-candidate bindings from G2 ledgers/query traces into
  claim id, concept/semantic-spine refs, SKG row refs, transport/parameter refs,
  method-requirement refs, and search-frontier refs. These bindings are
  candidate/control-plane provenance only; they are not certificates.
- [x] Build the IR catalog from `get_ir_schema_catalog()`,
  `polisyos.ir.analytics` facade exports, and known persistence helpers
  discovered by module metadata. Treat `src/polisyos/ir/analytics/index.md` as
  documentation/coverage sync only, not as the authoritative search registry.
  Materialize an indexed DuckDB catalog table before per-request search.
- [x] Record module refs, FQNs, exported status, schema versions, field refs,
  certificate/ref fields, proof status fields, composability fields,
  persistence helper refs, and producer refs.
- [x] Add search ledgers that store query predicates, catalog snapshot hash,
  index version, result cardinality, selected/rejected candidates, no-hit
  reasons, budget/cutoff, and authority boundary.
- [x] Use repo-standard index-backed search: DuckDB read-only/materialized
  tables for catalog predicates and exact lookup, optional existing HNSW/vector
  assets only when a replayed query-vector producer/ref exists, and bounded
  result sets with deterministic query traces.
- [x] Reject ledgers whose canonical route is `fixture`, `manual_class_list`,
  `curated_facade_only`, `docs_index_only`, or `compiler_bridge_view` when full
  IR analytics catalog coverage is required.
- [x] Add a free-growth fixture that introduces a new synthetic IR analytics
  contract/producer entry in the catalog input and proves discovery without code
  changes.
- [x] Add a perf/engineering check that per-request search does not import/walk
  every analytics module and does not scan G2 SKG/IR/CAS JSON files linearly.

### Task 2: Artifact Store Index And Certificate Resolution

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_analytics_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g3_analytics_search.py`

Steps:

- [x] Implement `Layer3G3ArtifactStoreIndex`,
  `Layer3G3CertificateCandidate`, `Layer3G3CertificateResolutionRecord`, and
  `Layer3G3CertificateResolutionReport`.
- [x] Reuse existing IR loaders/builders for `ProofBundle`,
  `ProofComposabilityCertificate`, `NegativeCertificate`, `BoundsBundle`,
  `BoundsDualCertificateBundle` / `StratifiedLPDualCertificateBundle`,
  uncertainty/bounds refs, and other typed certificate surfaces where relevant.
  Follow the resolver matrix above instead of inventing a generic untyped
  certificate loader.
- [x] Use existing `ArtifactStoreConfig`/`FileSystemCAS` helpers when a store is
  configured. If no stable store is configured for local readiness, use a
  deterministic test producer path and record the store/index limitation
  honestly.
- [x] Build the artifact index from configured CAS manifests, deterministic
  producer output manifests, and selected refs only. Do not eager-walk arbitrary
  artifact directories or treat missing store configuration as proof absence.
- [x] Do not call `iter_artifact_ids()` in the normal selected-candidate
  resolver path. If a bounded index-refresh job uses listing, record the listing
  budget, backend/root/prefix, snapshot hash, tenant/cell ownership mode, and
  cutoff in `Layer3G3ArtifactStoreIndex`.
- [x] Treat tenant-scoped CAS denial as a typed resolution denial/blocker with
  `layer3_g3_tenant_scoped_manifest_denied`; do not downgrade it into a no-hit.
- [x] Add a deterministic first-case producer path using existing public
  IR/Foundry code, preferably `CausalEngine.run(...)` with an artifact store. It
  must emit a typed proof/certificate payload or CAS ref, not a bare string.
  Scientist Level 2 can be an additional transition producer, but a caught
  warning path or missing store cannot close G3.
- [x] For `BoundsBundleRef`, validate nested `dual_certificate_ref` whenever
  sharp/certified bounds are claimed. Missing or invalid nested dual
  certificate blocks certified-bounds proof and emits the bounds-specific issue
  code.
- [x] Persist selected certificate resolution results and payload fingerprints.
  Payloads may be out of scope for PUBLIC, but must be replayable by
  EXPERT/MACHINE readiness.
- [x] Distinguish positive proof/certificate resolution from blocking or limiting
  certificate resolution. A resolved `NegativeCertificate` is valid evidence but
  cannot satisfy positive-proof closure by itself.
- [x] Add negatives:
  - unresolved `certificate://...` string fails G3 resolution;
  - negative certificate resolves and blocks;
  - proof-composability `rederive` blocks reusable proof;
  - stale artifact index cannot produce proof-domain ceiling;
  - per-request resolver path that calls full CAS listing fails engineering
    quality;
  - tenant-scoped manifest denial blocks resolution;
  - bounds bundle overclaims sharp/certified bounds without nested dual
    certificate;
  - Scientist warning/ref-less path cannot count as resolved proof;
  - broad exception handling cannot silently mark resolution as pass.

### Task 3: Method Requirements, Proof Records, And Bridge Generalization

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_analytics_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g3_analytics_search.py`
- Test: `tests/unit/runtime/quality/test_ir_analytics_bridge_method_requirements.py`
- Test: `tests/unit/runtime/quality/test_claim_registry.py`

Steps:

- [x] Implement `Layer3G3MethodRequirementBinding`,
  `Layer3G3SemanticSpineBinding`, `Layer3G3ProofCarryingAnalyticsBinding`, and
  `Layer3G3IRAnalyticsBridgeBinding`.
- [x] Consume G2 method-requirement bindings where available and fall back to
  W7.C `MethodValidityRequirementSpec` compilation only for requests that do
  not have a G2 binding.
- [x] Build `ProofCarryingAnalyticsRecord` through the existing
  `build_proof_carrying_analytics_record` function. Do not instantiate a
  parallel G3 proof DTO as the waist artifact.
- [x] Build the bridge through existing `build_ir_analytics_claim_bridge`.
  Preserve current bridge issue codes and behavior as regression anchors.
- [x] Ensure proof records carry claim id, design comparison ref, baseline ref,
  alternative refs, method output refs, certificate refs, proof status,
  composability status, uncertainty refs, method requirement refs, bridge ref,
  claim-registry entry ref, comparison consumer ref, source/method lineage, and
  authority denials.
- [x] Add negatives:
  - search hit without resolved certificate cannot build proof record;
  - S11/string fixture ref without resolver payload cannot build G3 proof record;
  - point requirement without certificate fails;
  - bounds requirement without uncertainty/bounds refs fails;
  - negative-certificate requirement is not satisfied by method output;
  - bridge row without claim id fails;
  - bridge row with blocking proof status fails claim readiness.

### Task 4: S11 Prerequisites, Calibration, And Predictive Posture Binding

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_analytics_search.py`
- Test: `tests/unit/runtime/quality/test_layer3_g3_analytics_search.py`
- Test: `tests/unit/runtime/quality/test_layer2_s11_predictive_knowledge.py`
- Test: `tests/unit/pdc/test_layer2_s2_design_search.py`

Steps:

- [x] Implement `Layer3G3S11PrerequisiteBinding`,
  `Layer3G3S11CalibrationBinding`, and
  `Layer3G3S11PredictivePostureBinding`.
- [x] Prove S6 floor refs and G2/S10 forecast support refs exist before any S11
  posture is emitted.
- [x] Use existing S11 builders for calibration, upgrades, authority envelope,
  posture, and integrity summary.
- [x] Keep S11 maturity rules intact: only S11 predictive axes can relax;
  mandate legitimacy cannot become predictive; fail-closed axes require
  `reverted_fail_closed`.
- [x] Preserve G2/S10 forecast-quality disposition and weakest-boundary
  semantics. G3 proof does not override S10 tier or S6 floor.
- [x] Add negatives:
  - missing S6 floor ref blocks;
  - missing S10 forecast support ref blocks;
  - stale/out-of-scope calibration cannot pass;
  - predictive upgrade without proof ref blocks;
  - production/recommendation/claim/closeout authority in S11 boundary blocks.

### Task 5: Consumer Gates And W12D Route

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_analytics_search.py`
- Modify: `tools/quality/validation/run_universal_outcome_corpus.py`
- Test: `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Test: `tests/unit/runtime/quality/test_claim_registry.py`
- Test: `tests/unit/scientist/policy_design/test_baseline_compiler.py`

Steps:

- [x] Implement `Layer3G3ClaimRegistryConsumerGateRecord` proving the G3 bridge
  is consumed by runtime claim registry and blocks/limits claims correctly. Reuse
  existing claim-registry logic; the new proof is that a G3-produced resolved
  bridge reaches it.
- [x] Implement `Layer3G3BaselineComparisonConsumerGateRecord` proving the G3
  bridge is consumed by `BaselineComparisonCompiler` as comparison evidence
  without recommendation or closeout authority. Do not fork baseline compiler
  semantics.
- [x] Implement `Layer3G3W12DConsumerGateRecord` proving the first full W12D
  S11/S2 route consumes a G3-resolved proof record. Remaining cases may use
  lightweight refs, preserving the existing cost pattern.
- [x] Assert the first full S2/S11 route reflects G3 proof consumption in
  `search_ledger.predictive_knowledge_refs`, S11 constraint-store entries,
  refinement decision/run status, axis-position declaration, firewall status,
  and projection fields. A posture ref present only as a string is not enough.
- [x] Add W12D summary fields for G3 gate count, full consumer case count,
  lightweight posture ref count, fixture-certificate closure count,
  negative-certificate block count, and useful-design delta count.
- [x] Add tests that fixture-style S11 proof refs remain regression context but
  do not count as G3 closure.
- [x] Add tests that G3 gate injection does not overwrite G0/G1/G2 conversion
  outcomes and does not mutate useful-design credit.

### Task 6: Surfaces, Generated Artifacts, Health, And Readiness CLI

**Files:**

- Create: `tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py`
- Create: `docs/reference/policy-design-case-layer3-analytics-search.md`
- Modify: `src/polisyos/runtime/quality/public_export.py`
- Modify: `architecture/generated_artifacts.toml`
- Modify: `docs/reference/generated-artifacts.md`
- Modify: `architecture/policy_design_case/inventory.json`
- Modify if required by repo policy: `docs/reference/public-surface.md`
- Modify: `docs/reference/documentation-inventory.md`
- Modify: `docs/reference/index.md`
- Modify: `mkdocs.yml` if needed
- Test: `tests/unit/runtime/quality/test_public_export.py`

Steps:

- [x] Implement readiness CLI with `--write`, `--output`, and
  `--output-format json|text`, matching G2 conventions.
- [x] Write every expected JSON/TOML artifact in `--write` mode and reject
  omitted TOML artifacts or written paths not in the expected set.
  Mirror G2's readiness shape: explicit expected artifact list, selected-key
  manifest/runtime drift, `issue_code_dictionary`, registration/docs checks, and
  stable text/json output.
- [x] Register the G3 generated-artifact family in
  `architecture/generated_artifacts.toml`; include the full family contract
  used by G1/G2: `id`, `label`, `owner`, `approval_owner`, `lifecycle`,
  `generator`, `verifier`, `promotion_target`, `stale_output_behavior`,
  `source_of_truth`, exact `outputs`, `regenerate_commands`, `commit_policy`,
  `freshness_rule`, `drift_gate`, `workflow`, `check_cwd`, and
  `check_command`. Regenerate generated-artifacts docs from that source of
  truth.
- [x] Register the G3 audit surface in `inventory.json`, the slice reference
  page, generated-artifact docs, and public-export projection refs. Update
  `docs/reference/public-surface.md` only if the repo policy/validator requires
  the global index to mention this internal audit surface; do not widen public
  facades or expose private DTOs for documentation symmetry.
- [x] Create and register `layer3_g3_adapter_contract_registry.toml` with the G3
  adapter paths for L2/SKG proof-candidate binding, IR analytics catalog search,
  certificate resolution, proof-record binding, bridge consumption, and W12D
  consumer gating.
- [x] Use the G1-style loader-compatible registry grammar with
  `[[field_families]]` and `[[adapter_paths]]`. Do not copy G2's
  summary-only TOML literally unless the implementation first creates a shared
  writer that emits a loader-compatible contract registry.
- [x] Validate the registry with `load_adapter_contract_registry(path=...)` and
  `validate_adapter_preservation`; write `Layer3G3AdapterContractRegistryStatus`
  and G0-compatible `AdapterAdmissionRecord` rows into the G3 readiness bundle.
- [x] Add a negative repo-quality test proving a summary-only
  `[adapter_contract_registry] adapter_contract_refs = [...]` TOML fails the
  G3 registry loader/conformance check.
- [x] Build `Layer3G3ProofCarryingAuditSurface`:
  - PUBLIC/REVIEWER: limitation, denied uses, proof posture, no raw payloads.
  - EXPERT/MACHINE: proof refs, certificate resolution, bridge refs, search
    frontier refs, method requirement refs, S11 refs, blocker/limitation refs,
    authority boundary.
- [x] Build `Layer3G3PublicExportProjectionRefSurface` and update public export
  tests so PUBLIC receives projection-only G3 audit refs/status
  (`certificate_resolution_report_ref`, search-ledger refs or redacted frontier
  refs, resolved/blocked counts, authority denials) but never raw proof payloads,
  raw CAS manifests, or raw query ledgers.
- [x] Build `layer3_g3_health_metric_delta.toml` with all five metric ids and
  G3 readings.
- [x] Add selected-key manifest/runtime drift checks.

### Task 7: Final Conformance, Performance, And Verification

**Files:**

- Modify: `src/polisyos/runtime/quality/layer3_analytics_search.py`
- Test all G3 files above.

Steps:

- [x] Implement `Layer3G3ConformanceReport` with issue codes for every
  conformance negative named in this plan.
- [x] Add performance checks for DuckDB materialized/indexed catalog search,
  bounded L2/SKG ledger use, optional replay-backed HNSW/vector use, and bounded
  artifact-store indexing. A toy-case O(n) implementation is a defect.
- [x] Add import/performance checks proving importing
  `polisyos.runtime.quality.layer3_analytics_search` does not build catalogs,
  open DuckDB, scan CAS, or import heavy Foundry/Scientist producer engines at
  module load. Heavy producer paths must be lazy and request-scoped.
- [x] Add replay checks: every selected proof/certificate has a query trace,
  certificate resolution record, producer/ref source, method requirement ref,
  and authority boundary.
- [x] Add adapter-admission checks: missing `layer3_g3_adapter_contract_registry.toml`,
  unknown adapter paths, semantic-loss blockers, or engine touch-points outside a
  registered adapter path fail readiness.
- [x] Add CAS/search engineering negatives for full-store listing in the
  request path, tenant-scoped manifest denial, stale artifact index, and missing
  store configuration misreported as proof absence.
- [x] Run targeted tests:
  `uv run pytest tests/unit/runtime/quality/test_layer3_g3_analytics_search.py tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g3_readiness_cli.py -q`
- [x] Run consumer tests:
  `uv run pytest tests/unit/runtime/quality/test_claim_registry.py tests/unit/runtime/quality/test_public_export.py tests/unit/scientist/policy_design/test_baseline_compiler.py tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py -q`
- [x] Run architecture/generated-artifact guardrails:
  `uv run polisyos-tools architecture guardrails check`
- [x] Run the G3 readiness CLI in write and read modes:
  `uv run python tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py --write --output-format json`
  and
  `uv run python tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py --output-format json`

## Acceptance Checklist

- [x] G3 runtime module exists with strict DTOs, schema/rule constants, bundle
  builder, validator, and issue-code dictionary.
- [x] G3 binds request provenance to the canonical G2 L2/SKG route or honestly
  blocks as missing/stale L2 dependency; IR-only catalog search cannot satisfy
  the master-plan "L2/IR" route.
- [x] IR analytics catalog search is materialized/indexed and free-growth tested.
- [x] Artifact-store/certificate resolver validates at least one real typed
  proof/certificate payload or CAS ref.
- [x] Resolver does not use full CAS listing in the normal request path;
  bounded index refresh is replayed with backend/root/prefix, snapshot, budget,
  cutoff, and tenant/cell ownership mode.
- [x] Tenant-scoped CAS manifest denial is recorded as a blocker, not as a
  no-hit or proof-domain ceiling.
- [x] Positive proof closure requires non-blocking proof/certificate evidence;
  negative certificates and uncertainty refs are resolved and surfaced as
  blocking/limiting evidence, not positive proof.
- [x] Bounds/certified-bounds claims follow and validate nested dual
  certificates when `dual_certificate_ref` is present or sharp/certified bounds
  are claimed.
- [x] `ProofCarryingAnalyticsRecord` is built only from resolved proof/certificate
  candidates.
- [x] `ir_analytics_bridge` is built through the existing bridge and preserves
  existing failure behavior.
- [x] Method requirements are consumed and tested for point, bounds, and
  negative-certificate obligations.
- [x] S11 prerequisites, calibration, upgrades, posture, and authority envelope
  are built through existing S11 functions.
- [x] Claim registry, baseline comparison, and W12D consumers prove the G3
  bridge is consumed without authority leakage.
- [x] First full W12D/S2 case proves S11 downstream effects in search ledger,
  constraint store, refinement/run status, axis/firewall records, and projection
  fields; lightweight cases remain lightweight.
- [x] Fixture-style S11 proof refs do not count as G3 closure.
- [x] PUBLIC/REVIEWER surfaces expose limitations and denied uses; EXPERT/MACHINE
  surfaces expose proof/certificate refs and replay details.
- [x] Public export exposes G3 resolution/search status as projection-only audit
  refs/status, and tests prove raw proof payloads, raw CAS manifests, and raw
  search ledgers do not leak to PUBLIC.
- [x] All five health metrics are updated.
- [x] Slice-local adapter contract registry loads through the existing loader,
  passes adapter preservation checks, persists G0-compatible admission rows, and
  appears in readiness selected-key drift checks.
- [x] G3 adapter registry uses loader-compatible `[[field_families]]` and
  `[[adapter_paths]]`; a summary-only TOML fails conformance.
- [x] Readiness CLI validates persisted artifacts, generated-artifact
  registration, inventory/docs/public surface, drift keys, conformance, and
  authority posture.
- [x] Search recall/freshness passes before any proof-domain ceiling claim.
- [x] Engineering quality report proves no hand-rolled hardcoded module list,
  no per-request O(n) full catalog scan, no eager full-store scan, no broad
  fail-open exception handling, no heavy producer imports at module load, and
  deterministic replay.

## Non-Negotiables

- A search hit is not a certificate.
- A bridge row is not a certificate.
- A fixture `certificate://...` string is not a G3-resolved certificate.
- A negative certificate is evidence, and usually blocking evidence.
- A request/case `analytics_proof_domain_ceiling` is not G3 slice closure unless
  at least one real resolved certificate/proof route and consumer chain also
  passed.
- IR catalog search alone is not the master-plan L2/IR route when healthy G2
  L2/SKG ledgers are available.
- `ProofCarryingAnalyticsRecord` is the waist artifact; do not create a parallel
  G3 proof waist.
- `ir_analytics_bridge` is the bridge; generalize it by wrapping/searching
  around it, not by replacing it.
- S11 depends on S6 and S10. G3 proof cannot fabricate those prerequisites.
- PUBLIC must not receive raw proof payloads by accident.
- EXPERT/MACHINE must receive resolution/search replay refs and status; raw
  payload disclosure remains audience-gated.
- G3's public documentation surface is the slice reference + registered audit
  artifacts + projection-only export refs. Global `public-surface.md` and
  package facades are updated only when repo policy requires them, never to
  expose private helper DTOs for symmetry.
- G3 adapter admission must use the shared loader-compatible registry grammar;
  summary-only registry presence is not enough.
- Full CAS listing is not the normal request resolver. Selected refs and bounded
  indexed snapshots are the normal route.
- G3 cannot promote, recommend, close out, publish, or award useful-design
  credit.
