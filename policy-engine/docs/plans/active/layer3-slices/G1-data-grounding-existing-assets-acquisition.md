---
plan_id: layer3-g1-substrate-grounding-search-engine
title: "G1 - Substrate Grounding Search Engine"
type: slice-plan
status: active
created: 2026-06-06
revised: 2026-06-07
slice: G1
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md
  - docs/adr/0175-layer3-grounding-subordination-discipline.md
  - architecture/policy_design_case/layer3_g0_readiness_manifest.json
  - architecture/policy_design_case/layer3_discovery_search_discipline.json
  - architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json
  - architecture/policy_design_case/layer3_engineering_quality_check.json
  - architecture/policy_design_case/layer3_health_metric_ledgers.toml
  - architecture/policy_design_case/layer3_data_asset_ports.json
  - architecture/policy_design_case/layer3_first_vertical_case.json
cells_closed: []
layer_cells_advanced:
  - layer3.substrate_grounding_search_adapter
  - layer3.grounding_search_ledgers
  - layer3.grounded_source_contracts
  - layer3.lineage_contamination_ledger
  - layer3.hardcode_strangle_delta
  - layer3.g1_corpus_route
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g1_substrate_search_readiness_gate
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G1 - Substrate Grounding Search Engine

## For agentic workers

This is an executable slice spec, not strategy. Follow it red-first. Every
reuse claim below is grounded in current files and line references. G1 starts
from the accepted G0 v2 discovery/search freeze: consume the G0 dependency
requirements, `GroundingSearchLedger` semantics, recall/freshness records,
no-hardcode lint, hardcode strangle backlog, `DataAssetPort` records, and
engineering-quality bar. G1 adds its own wrapper records where G0's strict
models do not carry G1-only fields. Do not mutate G0's baseline counts to make G1
look green, do not promote any grounding output to claim authority, and do not
claim domain ceiling while search ceiling is unresolved.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.
`expected_open_cell_count: 0` refers to the existing Layer 2 cluster-map/open-cell
model that G1 does not mutate; Layer 3 progress is measured by substrate-search
readiness, adapter-admission delta, conformance, search-recall/freshness, and
health ledgers.

## Intro

G1 builds the first real Layer 3 substrate grounding search adapter. Given a
typed construct/metric/source request, the adapter searches the substrate route
defined by the master plan — the real L1 DCAT table
`production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb::ds_metric_bindings`
(56,846 metric bindings in the current snapshot), L5 calibration metadata, and
L6 routing — plus G0-discovered substrate indexes and production manifests. It
records a replayable G1 search-frontier ledger, ranks candidate data/source
paths by SourceContract readiness, calibration/freshness/rights/lineage/fitness,
and emits a typed search outcome: validated Fabric `SourceContract` binding,
`observed_but_uncertain` binding, fail-closed acquisition gap,
`grounded_abstention_domain_ceiling`, `search_ceiling_repair_required`, or
blocked dependency/incomplete result.

UA-MSME remains the narrow validation case, not the mechanism scope. The same
search mechanism must handle at least two distinct substrate request shapes and
must discover a correctly-added metric/source fixture without code changes. G1
does not estimate causal effects, does not claim policy impact, does not promote
any adapter to production authority, does not live-fetch new data, and does not
let raw `data_forge`, `fabric`, search hits, or corpus annotations fill construct
slots without the adapter and authority boundary.

## Closure Contract

Source of truth: roadmap G1 closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`,
especially the G1 "Substrate Grounding Search Engine" slice.

G1 must deliver:

1. **G0 dependency gate** proving G0 v2 readiness, discovery/search discipline,
   recall/freshness, no-hardcode lint, engineering-quality check, and
   G1 dependency requirements are green before G1 runs.
2. **Substrate grounding search adapter** over real production L1
   `ds_metric_bindings`, L5 calibration metadata, L6 routing, G0 `DataAssetPort`,
   `ResourceDiscoveryRecord`, discovery indexes, production manifests, Fabric
   discovery/SourceContract readiness, and capability-index transition/acquisition
   signals. Capability-index outputs are not an L1 search path.
3. **Replayable G1 search-ledger records** for every authority-relevant search
   hit, no-hit, abstention, selected candidate, rejected candidate, cutoff, and
   incompleteness reason. They must preserve G0 `GroundingSearchLedger` semantics
   and add G1-only freshness/seed refs through `Layer3G1GroundingSearchLedger` or
   the adjacent recall/freshness report, not by mutating G0 models.
4. **Validated grounded `SourceContract` binding records** and
   lineage/contamination ledgers for every `grounded_binding` or
   `observed_but_uncertain` result.
5. **Fail-closed acquisition/gap route** for constructs whose searched substrate
   cannot honestly validate a SourceContract.
6. **Admission records** for the substrate search/data binding and acquisition
   gap adapters at `fail_closed`/`predictive` only, with no promotion.
7. **Hardcode strangle delta** for G0 backlog entries
   `KNOWN_CONSTRUCTS` and `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`: G1 must
   consume search-backed discovery, run no-hardcode lint, and either delete/disable
   fallback use with no fallback or block G1 closure as incomplete.
8. **Bridge/consumer route** where W12D and S3 consume the G1 binding/gap
   envelope without treating it as claim authority or useful-design credit.
9. **EXPERT/MACHINE surface and all five health deltas** for envelope expansion,
   adapter-semantic-loss, governance throughput, demand-pull-vs-abstention, and
   search recall/freshness.
10. **Conformance and negative controls** proving fail-closed behavior on absent
    rights, contaminated lineage, semantic-loss projection, over-claimed coverage,
    raw output, no-ledger abstention, stale index, recall miss, hardcoded
    fallback, and local-path lineage.

Target done path: the same construct-agnostic search mechanism handles at least
two distinct validation request shapes, discovers a correctly-added synthetic
metric/source fixture through the real DCAT path without code changes, and grounds
or honestly observes at least one real UA-MSME substrate path through a validated
Fabric SourceContract snapshot, clean conformance battery, non-lossy preservation
report, and clean lineage/contamination check. It also proves the L1/L5/L6 route
is covered by real lifted artifacts; a bounded surrogate cannot stand in for L1
while the production `ds_metric_bindings` table is available. G1 must pass a
search-engineering quality/performance check.

Honesty escape path: if the search adapter runs with replayable ledgers, explicit
L1/L5/L6 coverage, fresh indexes, passing known-groundable recall, non-lossy
conformance, search-engineering quality, hardcode fallback deletion/disablement,
and clean negative controls, and current UA assets still cannot form a valid
Fabric SourceContract v2 snapshot for any pinned construct without laundering
local-path lineage, proxy-only validity, missing rights, or schema/replay
evidence, G1 may close as `grounded_abstention_domain_ceiling` with reason
`data_insufficiency_domain_ceiling`. If recall, freshness, ledger completeness,
L1/L5/L6 coverage, engineering quality, or hardcode-free discovery is unhealthy,
the outcome is `search_ceiling_repair_required`, not domain ceiling.

## Scope Boundaries

In scope:

- Implement the G1 substrate grounding search adapter and acquisition/gap route
  in `runtime/quality`.
- Consume G0 v2 readiness, real L1 metric-binding search over
  `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb::ds_metric_bindings`,
  L5 calibration metadata, L6 routing, `DataAssetPort`, discovery indexes,
  `ResourceDiscoveryRecord`, `GroundingSearchLedger` semantics, recall/freshness
  policy, hardcode backlog, engineering-quality check, first vertical case, Fabric
  `SourceContract`, Fabric discovery/source-contract readiness, capability-index
  compiler transition outputs, and S3 substrate acquisition as existing substrate.
- Produce and persist G1 adapter admission, grounded SourceContract binding,
  substrate search ledgers, L1/L5/L6 index-coverage evidence,
  lineage/contamination, hardcode strangle delta, conformance, all five
  health-delta readings, readiness, and EXPERT/MACHINE surface artifacts.
- Persist validated Fabric `SourceContract` snapshots, including content hash and
  contract payload, for every grounded or `observed_but_uncertain` data-asset
  binding. A binding ref without a SourceContract snapshot is not G1 closure.
- Persist G1 search-ledger evidence for every selected/no-hit/abstention route
  before it influences binding or ceiling diagnosis.
- Add G1 known-groundable recall/freshness checks for the substrate envelope and
  reuse the G0 recall/freshness gate as prerequisite evidence.
- Implement the first no-hardcode/free-growth closure over the G0 hardcode
  backlog: G1 may use existing compiler/resolver outputs as transition/acquisition
  substrate, but closure cannot depend on their hardcoded construct mappings or
  treat their derived capability-index as L1 search.
- Add a G1 search-engineering quality gate: named libraries/indexes, index-backed
  and lazy/streaming search, deterministic replay, no eager full-corpus scan, and
  no broad fail-open error handling.
- Add a G1-specific conformance registry delta for the two new adapter paths
  without mutating the G0 source-truth baseline.
- Route the UA-MSME W12D corpus case through a G1 grounding gate that can show
  grounded/uncertain/abstained construct status without giving useful-design or
  claim-authority credit.
- Add negative controls for raw output, missing rights, contamination,
  acquisition gap overclaim, manifest/runtime drift, semantic loss, stale index,
  recall miss, no-ledger abstention, hardcoded fallback, and search-hit authority
  laundering.

Out of scope:

- No causal estimates, forecasting, `ForecastSupport`, or claim impact closure;
  those belong to G2+.
- No promotion to production authority or universal design authority; G1 is
  `shadow`/`governed_for_binding` only and G4 handles promotion.
- No useful-design conversion credit; G5 is the first proving-ground conversion
  slice.
- No live network acquisition or mutation of `production_data` assets.
- No new parallel data catalog, scenario-family authority selector, or
  rewritten `data_forge`/`fabric` engine.
- No hand-maintained construct/dataset/source/method list as a G1 closure path.
  Existing `KNOWN_CONSTRUCTS` and scenario-family mappings are transition debt
  only and must not be the fallback that makes G1 pass.
- No claim that G1 has satisfied DCAT-scale substrate search unless the real L1
  `ds_metric_bindings` route is queried and replayably recorded. A capability-index
  or other construct-scoped derivative is an unjustified L1 surrogate when the
  production DCAT is available; bounded surrogates can only limit absent non-L1
  evidence and must not produce L1 coverage pass.
- No `pdc` imports from subordinate engines.
- No PUBLIC or REVIEWER-facing claim projection in G1. Those audiences are
  explicit `surface_out_of_scope` for this slice because the roadmap G1 surface
  is coverage/lineage/abstention in EXPERT/MACHINE only; G4/G5 decide promotion
  or public/reviewer disclosure.
- No blanket full backend verification on a local MacBook unless the user asks;
  use targeted tests for this slice.

## Pattern Pass

| Pattern | G1 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Adapter status and SourceContract records exist but no producer/consumer path proves grounding. | Add producer functions, persisted G1 artifacts, W12D/S3 consumer route, validator, and negative tests. |
| P02 thin orchestration | Existing S3 acquisition and capability-index compiler coexist but do not consume G1 bindings. | Wire G1 binding into the W12D G1 gate and S3 substrate context; test that raw output without binding is rejected. |
| P03 hidden internal richness | Lineage/contamination checks are internal JSON only. | Register EXPERT/MACHINE surface in inventory and docs/reference; validator checks artifact discoverability and records PUBLIC/REVIEWER as explicit `surface_out_of_scope`. |
| P04 status lattice gap | `grounded_binding`, `observed_but_uncertain`, and abstention could conflict with corpus useful-rate status. | Define local G1 statuses and cross-artifact tests proving `counts_as_useful_design=false` until G5. |
| P05 authority boundary leak | Real data binding is mistaken for claim or causal authority. | Every binding carries `authoritative_for` and `may_not_use_for`; W12D gate enforces no claim-authority promotion. |
| P07 rule replay gap | Grounding cannot be replayed after data/manifests change. | Store schema/rule versions, DCAT query/index refs, SourceContract hash, capability-index transition ref, data asset port ref, and manifest/runtime drift tests. |
| P08 time-role conflation | Data freshness, observed period, policy time, and replay time collapse into one field. | Require distinct `coverage_period_ref`, `freshness_ref`, `observed_through`, `rule_version`, and `generated_at` fields. |
| P09 warning lifecycle gap | Contamination or missing rights become soft warnings while grounding still succeeds. | Missing rights, contaminated lineage, and semantic loss are fail-closed blockers with issue codes. |
| P10 semantic adequacy gap | The validator only sees that a SourceContract object exists. | Add content-level negatives: raw-output echo, contaminated lineage, missing rights, lossy projection, and coverage overclaim. |
| P12 producer handshake gap | Substrate data-binding route and acquisition/gap route produce incompatible bindings. | Both routes emit the same `GroundedSourceContractBinding` or explicit gap envelope and the same status composition rules. |
| P13 governance gravity | G1 builds a new data engine or rewrites capability-index/data_forge. | Reuse G0 ports/search discipline, real DCAT DuckDB, Fabric SourceContract/discovery, capability-index transition signals, S3 loop, and data_forge manifests; only wrap/extend. |
| P14 evidence independence inflation | Multiple assets from shared Ukraine import lineage count as independent evidence. | Add contamination/effective-lineage collapse reasons; no independence-strength upgrade in G1. |
| P15 LLM speculation laundering | Candidate acquisition strategies or corpus annotations become data authority. | Acquisition adapter records gaps as candidate/fail-closed until SourceContract v2 validates. |
| P25 search-control laundering | Search hit, best-so-far, no-hit, or construct-scoped derivative index becomes authority, L1 coverage, or domain ceiling. | Persist G1 search frontier against the real DCAT path and keep it control-plane only; SourceContract binding/admission remains the authority gate. |
| T7 false abstention | Poor substrate recall or stale indexes cause fake data-insufficiency domain ceiling. | Known-groundable substrate seeds and index freshness must pass before `grounded_abstention_domain_ceiling`; otherwise emit `search_ceiling_repair_required`. |
| Rule 12 hardcode fallback | G1 passes because pinned constructs are still in `KNOWN_CONSTRUCTS`/scenario-family mappings, or because their construct-scoped capability-index is mistaken for L1 search. | Real DCAT `ds_metric_bindings` search path, no-hardcode lint, fallback deletion/disablement proof, free-growth fixture over DCAT, hardcode strangle delta, and no fallback closure rule. |
| C41 data contamination | Training, simulated, or fixture data is treated as real Ukraine evidence. | Contamination check blocks fixture/simulation-only lineage from grounding real constructs. |
| Import firewall | G1 adapters import engines through `pdc` or broad roots. | Keep adapter code in `runtime/quality`; validator scans G1 for non-waist `pdc` imports. |

## Capability Transition

| Capability | Start label after G0 | Pattern pressure | Target label after G1 |
| --- | --- | --- | --- |
| Substrate grounding search adapter | `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing` | P01/P02/P03/P10/P25/T7 | Implemented at `governed_for_binding`: search producer, replayable ledgers, validated SourceContract binding or honest ceiling, S3/W12D consumers, EXPERT/MACHINE surface, conformance, recall/freshness, and negatives. |
| Acquisition/gap grounding adapter | `producer_missing`, `bridge_missing`, `verification_missing`, `semantic_test_missing` | P12/P15/P10/P25 | Implemented as fail-closed gap adapter: candidate strategies are recorded, SourceContract v2 validation gates grounding, and no-hit/overclaim negatives fail. |
| Hardcode strangle delta | `consumer_missing`, `verification_missing` | P06/P13/Rule 12 | G1 consumes search-backed discovery for the G0 hardcode backlog, runs no-hardcode lint, and proves fallback deletion/disablement; remaining executable fallback debt blocks G1 closure. |
| Grounded SourceContract binding surface | `surface_missing`, `consumer_missing` | P03/P05 | Implemented EXPERT/MACHINE audit surface; PUBLIC/REVIEWER are explicit `surface_out_of_scope` and not claim authority. |
| Lineage/contamination ledger | `artifact_missing`, `verification_missing` | P08/P14/C41 | Implemented ledger with clean checks for grounded records and fail-closed contaminated negative. |
| UA-MSME W12D G1 route | `implemented_but_not_orchestrated`, `bridge_missing` | P02/P04/P05 | Implemented corpus route showing construct grounding/uncertainty while preserving no useful-design credit. |

## Code-Grounded Reality

### Existing Substrates

- G1 roadmap contract is at
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:283`.
- The Layer 3 master plan says stalled envelope expansion after adapters can be
  a first-class domain ceiling, not slice failure, at
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:72`.
- The plan-level done rule treats domain ceiling as a valid successful outcome at
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:499`
  and
  `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:506`,
  but G0 T7 makes that valid only after replayable search, recall, and freshness
  checks have passed.
- The capability reality bar requires the complete chain at
  `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:180`.
- The existing integration discipline says adapters live in `runtime/quality`,
  call engines, lower output to proved authority, and fail closed at
  `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:193`.
- Failure-pattern labels and missing capability states are canonical at
  `docs/reference/policy-design-case-failure-patterns.md:13`.
- G0 v2 is now the actual prerequisite, not a planned future state: the G0
  validator reports schema
  `policyos.policy_design_case.layer3_g0_discovery_search.v2`, rule
  `policyos.layer3.g0.discovery_search_free_growth.v2`, 16 persisted closure
  artifacts, 5 health ledgers, `grounding_search_ledger_contract_count: 1`,
  `search_recall_seed_status: pass`, `index_freshness_status: pass`,
  `no_hardcode_enumeration_lint_status: pass`, `engineering_quality_check_status:
  pass`, `g1_dependency_requirements_status: pass`, and zero admitted adapters in
  `architecture/policy_design_case/layer3_g0_readiness_manifest.json`.
- G0 v2 persists the discovery/search discipline in
  `architecture/policy_design_case/layer3_discovery_search_discipline.json`,
  including discovery indexes, resource discovery records, replayable
  `GroundingSearchLedger` records, recall seeds, index freshness records,
  free-growth fixtures, mechanism-generality fixtures, and targeted no-hardcode
  lint results.
- G0 v2 persists the hardcode strangle backlog in
  `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json`.
  The two load-bearing G1+ debts are
  `capability_index_compiler.KNOWN_CONSTRUCTS` and
  `capability_resolver.REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`; their
  deletion conditions require G1+ to consume `ResourceDiscoveryRecord`-backed
  discovery instead of hardcoded construct mappings.
- G0 v2 persists the engineering-quality check in
  `architecture/policy_design_case/layer3_engineering_quality_check.json`; G1
  must keep the same engineering posture: strict Pydantic, structured JSON/TOML
  parsers, manifest/index-backed scans, deterministic ordering, fail-closed
  errors, no eager full-corpus or full-Parquet scans.
- G0 models already define `DataAssetPort` with lineage, rights, freshness,
  fitness, contamination check, and port refs at
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py:468`.
- G0 models already define `ResourceDiscoveryRecord` and `GroundingSearchLedger`
  at `src/polisyos/runtime/quality/layer3_grounding_inventory.py:251` and
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py:263`; G1 must
  consume or extend these semantics rather than inventing a parallel search
  status system.
- The base G0 `GroundingSearchLedger` is intentionally narrow and does not carry
  G1-only index-freshness or known-seed refs; G0 stores those as separate
  `SearchRecallSeed` and `IndexFreshnessRecord` records. G1 must mirror that
  separation or wrap the base ledger, not validate extra G1 fields against the
  strict G0 model.
- G0 models already define `AdapterAdmissionRecord` at
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py:452`, and the G0
  bundle builder persists zero admitted adapters at
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py:1639`.
- The base G0 `AdapterAdmissionRecord` also does not carry G1-specific
  `admission_purpose`, `admitted_for_binding`, or `admitted_for_gap_routing`
  fields. Those belong in `Layer3G1AdapterAdmissionBundle`, with a nested or
  adjacent G0-compatible admission record.
- G0 validation already blocks manifest/runtime drift at
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py:1748` and validates
  adapter admission records at
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py:2142`.
- G0 data-asset validation already requires lineage, rights, freshness, fitness,
  contamination refs, and SourceContract/readiness classification through the G0
  data-asset readiness validators and persisted `layer3_data_asset_ports.json`.
- G0 first vertical case is fixed in
  `architecture/policy_design_case/layer3_first_vertical_case.json:2` as
  `ua-msme-affordable-loans-2022`, with construct bundle
  `ukrainian_msme_credit_constructs`.
- The construct bundle itself is grounded in the Layer 2 first proving case at
  `architecture/policy_design_case/layer2_first_proving_case.json:5`; it includes
  `credit_program_enrollment`, `firm_survival`, and
  `regional_displacement_pressure` at
  `architecture/policy_design_case/layer2_first_proving_case.json:8`.
- G0 data asset ports include `ukraine-ops-runner-root` over
  `tools/ops_runners/ukraine_data` at
  `architecture/policy_design_case/layer3_data_asset_ports.json:18`.
- G0 readiness manifest pins `source_truth_adapter_path_count: 9` and
  `source_truth_lattice_new_adapter_path_count: 0` at
  `architecture/policy_design_case/layer3_g0_readiness_manifest.json:41`.
- `AdapterContract`, `AdapterContractRegistry`, `AdapterLossBlocker`, and
  `validate_adapter_preservation` already exist at
  `src/polisyos/runtime/quality/adapter_contracts.py:29`,
  `src/polisyos/runtime/quality/adapter_contracts.py:43`,
  `src/polisyos/runtime/quality/adapter_contracts.py:71`, and
  `src/polisyos/runtime/quality/adapter_contracts.py:224`.
- The production source-truth registry currently starts `[[adapter_paths]]` at
  `architecture/production_quality/source_truth_lattice.toml:268`; G1 must not
  mutate this file just to create its slice-local conformance delta.
- Fabric SourceContract v2 has schema version
  `fabric.source_contract.v2` at
  `src/polisyos/fabric/connectors/contracts/source_contract.py:24`, and the
  strict active-contract model/validator are at
  `src/polisyos/fabric/connectors/contracts/source_contract.py:382` and
  `src/polisyos/fabric/connectors/contracts/source_contract.py:422`.
- Fabric active SourceContract field access policy validation requires policies
  for schema fields at
  `src/polisyos/fabric/connectors/contracts/source_contract.py:461`; Fabric
  `FieldSpec` requires snake-case field names and canonical data types at
  `src/polisyos/fabric/connectors/contracts/_schema_field.py:180`.
- Fabric source-contract production validator already builds reports and
  fail-closed summaries at
  `tools/quality/validation/fabric_source_contracts.py:119`,
  `tools/quality/validation/fabric_source_contracts.py:242`, and
  `tools/quality/validation/fabric_source_contracts.py:271`.
- Fabric already provides reusable SourceContract helpers:
  `default_source_field_access_policies` at
  `src/polisyos/fabric/connectors/contracts/source_contract.py:189`,
  `SourceContract.from_connector_schema_contract` at
  `src/polisyos/fabric/connectors/contracts/source_contract.py:510`, and
  `source_contracts_snapshot_payload` at
  `src/polisyos/fabric/connectors/contracts/source_contract.py:622`. G1 should
  reuse these patterns when possible instead of hand-writing every nested block.
- S3 substrate acquisition has `construct_not_observed` coverage snapshots at
  `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:173` and a
  closure state machine at
  `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:306`.
- S3 source contract validation fails on missing rights/legal use, missing data
  dictionary, missing rows, and unusable linkage at
  `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:511`.
- S3 converts validated source contracts into governed construct-binding
  capabilities at
  `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:546`.
- S3 already consumes an injected `RequirementToCapabilityResolver` through
  `resolve_expression(..., resolver=...)` at
  `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:691`; G1 should
  prove substrate consumption through that port rather than editing the S3 state
  machine.
- Capability resolution already maps `credit_program_registry` to
  `credit_program_enrollment` at
  `src/polisyos/core/contracts/capability_resolution.py:18`.
- The data-requirement compiler already treats `source_contract_ref`,
  `source_rights`, `lineage_refs`, and `construct_validity_refs` as mandatory
  facets at `src/polisyos/data_requirement/compiler.py:39`.
- The capability-index compiler knows the UA proving-ground constructs at
  `src/polisyos/runtime/quality/capability_index_compiler.py:112` and builds
  acquisition strategies for `credit_program_enrollment` at
  `src/polisyos/runtime/quality/capability_index_compiler.py:1612`.
- The capability-index compiler loads Ukraine panel capabilities from existing
  production assets at
  `src/polisyos/runtime/quality/capability_index_compiler.py:1093`.
- `load_ukraine_panel_capabilities` explicitly profiles Ukraine Parquet assets
  with metadata only, not full scans, at
  `src/polisyos/runtime/quality/capability_index_compiler.py:1099`; `_profile_ukraine_parquets`
  uses `pyarrow.ParquetFile` metadata at
  `src/polisyos/runtime/quality/capability_index_compiler.py:2473`.
- The existing firm-survival capability over UA panels already carries source
  assets, proxy-validation limitations, governed-pilot authority, production
  block, lineage refs, freshness, and rights at
  `src/polisyos/runtime/quality/capability_index_compiler.py:2332`.
- The real L1 DCAT target already exists at
  `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`
  table `ds_metric_bindings` with 56,846 rows in the current snapshot. G1 L1
  coverage, free-growth, mechanism-generality, and recall/freshness checks must
  query this path directly through DuckDB SQL and record the table/index version;
  a capability-index derived from `KNOWN_CONSTRUCTS` is not L1 coverage.
- `RequirementToCapabilityResolver` is already the W7-to-capability bridge; the
  module states this discipline at
  `src/polisyos/runtime/quality/capability_resolver.py:1`, and the class starts
  at `src/polisyos/runtime/quality/capability_resolver.py:100`. It
  treats HypothesisLedger as reviewer/acquisition signal rather than evidence
  authority.
- `RequirementToCapabilityResolver.default_fixture()` already includes
  `firm_survival` capability and `credit_program_enrollment` acquisition
  strategies at `src/polisyos/runtime/quality/capability_resolver.py:121`.
- `RequirementToCapabilityResolver.resolve()` returns selected or blocked typed
  bindings, rejected alternatives, acquisition strategies, reviewer queue, and
  capability-index refs at
  `src/polisyos/runtime/quality/capability_resolver.py:299`.
- `RequirementToCapabilityResolver.from_duckdb()` already loads the Phase 1
  capability-index DuckDB from `capabilities`, `conflicts`, `failure_modes`, and
  `acquisition_strategies` tables at
  `src/polisyos/runtime/quality/capability_resolver.py:255`; G1 may use this
  indexed resolver path only for transition binding/acquisition signals and S3/W12D
  consumption. It must not be the L1 metric-binding search route.
- `compose_capability_authority` already defines status composition,
  limitations, `satisfies_claim_evidence`, `authoritative_for`, and
  `may_not_use_for` at
  `src/polisyos/runtime/quality/capability_authority.py:200`; G1 must consume
  this instead of building a parallel authority scorer.
- `DataRequirementCompiler` accepts an injected `capability_resolver` at
  `src/polisyos/data_requirement/compiler.py:121`, compiles resolver bindings
  into data requirement specs at `src/polisyos/data_requirement/compiler.py:167`,
  and derives the pinned constructs from semantics at
  `src/polisyos/data_requirement/compiler.py:668`.
- Data Forge snapshot binding already blocks local-path substitution and missing
  durable provenance/lineage refs at
  `src/polisyos/runtime/quality/data_forge_binding.py:83` and
  `src/polisyos/runtime/quality/data_forge_binding.py:1149`.
- `ProductionDataContractIndex` is a useful scenario-binding/surface pattern at
  `src/polisyos/runtime/quality/production_data_contract_index.py:272`, but its
  `_validate_source_contract_ref` only checks active status/content hash shape at
  `src/polisyos/runtime/quality/production_data_contract_index.py:1025`; G1 must
  validate Fabric `SourceContract` v2 directly, not echo an active flag.
- The Ukraine ops runner explicitly points canonical domain logic to
  `src/polisyos/data_forge/domains/ukraine` at
  `tools/ops_runners/ukraine_data/README.md:1`.
- Ukraine data_forge source configs include `dps_financials` and other real
  observation families at
  `src/polisyos/data_forge/domains/ukraine/models.py:545`.
- Ukraine release/manifests use typed artifact and lineage models at
  `src/polisyos/data_forge/domains/ukraine/manifests.py:24`,
  `src/polisyos/data_forge/domains/ukraine/manifests.py:111`, and
  `src/polisyos/data_forge/domains/ukraine/manifests.py:150`.
- The imported Ukraine local manifest records normalized corpus and runtime
  calibration assets at
  `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/LOCAL_IMPORT_MANIFEST.json:1`.
- That Ukraine import manifest currently stores workstation-local absolute paths
  at
  `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/LOCAL_IMPORT_MANIFEST.json:2`;
  G1 must turn them into repo/artifact/source-snapshot refs before any lineage
  authority is recorded.
- The curated production `data_contracts.json` currently contains US macro/agent
  contracts, not UA-MSME construct grounding, at
  `production_data/canonical/local_data_20260501/policy_engine_data/curated/data_contracts.json:1`.
- The UA-MSME corpus case has authority-boundary annotations at
  `tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json:12`
  and expected adapter bindings at
  `tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json:443`.
- The W12D runner already imports G0 and adds G0 pre-adapter grounding gates at
  `tools/quality/validation/run_universal_outcome_corpus.py:185`,
  `tools/quality/validation/run_universal_outcome_corpus.py:569`, and
  `tools/quality/validation/run_universal_outcome_corpus.py:9071`.
- W12D computes G0 context and wraps cases inside
  `build_w12d_universal_outcome_corpus_report` at
  `tools/quality/validation/run_universal_outcome_corpus.py:569`, then calls
  `_summary(cases)` at
  `tools/quality/validation/run_universal_outcome_corpus.py:593`; `_summary`
  itself starts at
  `tools/quality/validation/run_universal_outcome_corpus.py:8959`. G1 must be
  injected before `_summary(cases)` and must not overwrite the G0
  `conversion_outcome` field set at
  `tools/quality/validation/run_universal_outcome_corpus.py:9154`.
- W12D G0 tests prove the first vertical is blocked without useful-design credit
  at `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py:190`.

### Strong Seams

- G0 v2 already provides the shared discovery/search discipline G1 must consume:
  discovery indexes, resource records, `GroundingSearchLedger` shape,
  recall/freshness gates, no-hardcode lint, free-growth fixtures, and G1
  dependency requirements. The useful reuse is semantic and compositional:
  base G0 ledger plus separate recall/freshness records, not direct extra-field
  extension of strict G0 models.
- `DataAssetPort` already has exactly the fields G1 must prove before grounding:
  lineage, rights, freshness, fitness, contamination, and ports.
- Fabric `SourceContract` v2 already has strict validation, replay evidence,
  lineage seed, quality refs, terms, field-policy helpers, processing guarantees,
  snapshot helpers, and content hash.
- `validate_adapter_preservation` already blocks unknown adapter paths, lost
  fields, and semantic value changes; G1 only needs two new path declarations and
  adapter-specific adversarial fixtures.
- The S3 substrate loop already distinguishes unobserved constructs from
  validated construct-binding capability, so G1 can wire binding instead of
  inventing a new state machine.
- The capability-index compiler already exposes Ukraine panel metadata and
  acquisition strategy refs; G1 can consume those outputs as transition evidence,
  but only behind search-backed discovery and with G0 hardcode backlog debt
  explicitly tracked.
- The resolver/authority pair already emits the binding status lattice,
  acquisition strategies, limitations, and authority boundaries G1 needs; G1 can
  be a binding-envelope and SourceContract producer, not a new scorer.
- `RequirementToCapabilityResolver.from_duckdb()` gives G1 a real indexed bridge
  into the checked-in/fixture capability-index DuckDB instead of forcing G1 to
  call compiler internals or recreate selection logic, but this is a consumer
  bridge, not DCAT search. G1 still must query the production
  `dataset_catalog.duckdb::ds_metric_bindings` table for L1 closure.
- The data-requirement compiler already consumes capability resolver output, so
  G1 can prove substrate consumption by injecting the existing resolver/binding
  path instead of patching compiler logic.
- Data Forge binding already has durable-ref/local-path firewalls that G1 can
  reuse as issue-vocabulary and fixture shape for raw-output negatives.
- Ukraine panel profiling is metadata-only in the capability-index compiler,
  which keeps G1 targeted tests feasible on a local machine.
- W12D already carries a G0 grounding gate; G1 can add a neighboring G1 gate
  without rewriting the corpus runner.
- The touched production modules are large enough that the low-risk path is a new
  small G1 runtime module plus validator and narrow W12D/S3/DataRequirement
  consumer hooks, not deep edits to the compiler, resolver, S3 loop, or W12D
  runner.

### Weak Or Expensive Seams

- G0 runtime counts derive from current source-truth adapter paths and persisted
  manifest metrics. Adding paths to the global
  `architecture/production_quality/source_truth_lattice.toml` would make G0
  drift. G1 must create `architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml`
  as a slice-local registry extension loaded through existing
  `load_adapter_contract_registry(path=...)`, and keep G0 baseline at 9. The
  TOML must include the full source-truth lattice metadata and field-family
  definitions required by the loader, not only two `[[adapter_paths]]` rows.
- `polisyos.runtime.quality.__init__` exports a local S3 `SourceContract` from
  `layer2_substrate_acquisition`; Fabric also has `SourceContract` v2. G1 must
  name its envelope `GroundedSourceContractBinding` and import Fabric's
  SourceContract explicitly to avoid contract-name collision.
- Existing curated `production_data/.../curated/data_contracts.json` is US
  macro/agent data, not UA-MSME grounding. G1 must use Ukraine
  `tools/ops_runners/ukraine_data` and data_forge Ukraine manifests or
  capability-index Ukraine panel capabilities, not the curated US contracts, for
  the real Ukraine grounding.
- The pinned corpus claim is about credit access/additionality, but the clearest
  existing real Ukraine asset support in code is firm-panel/survival-style
  capability. G1 may ground at least one construct in
  `ukrainian_msme_credit_constructs`, but must leave `credit_program_enrollment`
  as acquisition-required unless a real validated SourceContract proves it.
- W12D useful-design scoring must remain false in G1. Grounding a construct is
  not causal authority, policy impact, publishability, or universal-design
  conversion.
- Capability-index compiler may be heavier than a unit-level adapter test. Task
  1 fixtures should allow red tests to specify shape, while Task 2 can keep the
  producer lightweight and only invoke compiler helpers in targeted tests.
- G0's hardcode backlog means `KNOWN_CONSTRUCTS` and
  `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS` are no longer harmless
  conveniences. If G1 still needs them during transition, it must record a
  search-backed replacement path, no-fallback deletion/disablement result, and
  free-growth proof; a passing pinned-case test through those lists alone is a
  failure.
- The G0 discovery index set is currently small (`registry` and `structured`
  indexes over fixture/runtime/production manifests). Because the real production
  DCAT exists, G1 must extend the substrate search path to
  `dataset_catalog.duckdb::ds_metric_bindings` for L1. A bounded surrogate cannot
  justify L1 pass here; if it is used for any missing non-L1 route evidence, it
  must be explicitly limited and cannot be described as full DCAT-scale coverage.
- G0 `DataAssetPort` fields are correctly shaped, but the
  `ukraine-ops-runner-root` port currently cites README refs for lineage, rights,
  freshness, and fitness. That is acceptable for G0 inventory and insufficient
  for G1 grounding. G1 must bind the port to validated Fabric SourceContract
  snapshots and Ukraine manifest/Parquet metadata before recording a
  grounded/uncertain binding.
- Building a Fabric `SourceContract` v2 snapshot is materially more work than
  emitting a `source_contract_ref`: active contracts require schema evidence,
  quality contract refs, replay evidence, lineage seed, idempotency policy, and
  field access policies. Processing replay retention must cover source retention,
  and any exactly-once-narrow claim requires atomicity proof. Tests must validate
  `SourceContract.model_validate`, not just presence of a contract id.
- SourceContract construction from raw Parquet metadata is not already a public
  Ukraine helper. G1 should reuse Fabric helpers where the input can be represented
  as a connector/schema contract; otherwise it must build the same nested Fabric
  submodels explicitly from metadata, without reading row data.
- The existing production-data contract index does not provide the UA
  SourceContract snapshot G1 needs, and its active-flag validation is too weak
  for G1 closure. Treat it as a read/reuse pattern and negative-control reference,
  not as the primary grounding authority.
- The Ukraine local import manifest contains absolute local paths. Any G1
  lineage record that preserves `/Users/...` as authority must fail with
  `layer3_g1_local_path_lineage_ref`.
- W12D's current G0 gate writes `conversion_outcome`. G1 must write a separate
  `layer3_g1_grounding_outcome` or gate-local status and summary fields, because
  reusing `conversion_outcome` would corrupt G0/G5 scoring semantics.
- The corpus fixture `expected_adapter_bindings` is annotation-level evidence,
  not a runtime G1 envelope. G1 tests must prove those annotations cannot satisfy
  a construct slot without `GroundedSourceContractBinding`.
- Domain ceiling is expensive to prove after G0 T7. G1 cannot close with
  `data_insufficiency_domain_ceiling` unless G1 search ledgers, G0 recall seeds,
  G1 known-groundable substrate seeds, and freshness checks all pass. Otherwise
  it must close as `search_ceiling_repair_required` or stay incomplete.
- Adapter admission is similarly wrapper-shaped: direct G0-compatible
  `AdapterAdmissionRecord` rows prove shared admission vocabulary, while
  G1-specific purpose booleans live in `Layer3G1AdapterAdmissionBundle`.

### Overbuild Guard

- Do not build a new data catalog, new SourceContract model, new S3 loop, or new
  capability resolver.
- Do not mutate production datasets or rewrite data_forge builders.
- Do not satisfy G1 with hardcoded construct/dataset/source lists, even if those
  lists already exist in `capability_index_compiler` or `capability_resolver`.
- Do not treat G0 search ledgers, G1 search ledgers, or search hits as producer
  authority; they are replay/control-plane evidence only.
- Do not update `architecture/production_quality/source_truth_lattice.toml` in
  G1. The G1 adapter path delta is slice-local until a later governed promotion
  slice moves it into the production source-truth lattice.
- Do not call any G1 output `implemented` unless the red-first tests prove the
  full chain: adapter producer -> persisted binding -> W12D/S3 consumer ->
  EXPERT/MACHINE surface -> negative/conformance tests.

## Reuse Map

| Existing substrate | File:line | Responsibility in G1 |
| --- | --- | --- |
| G0 discovery/search discipline | `architecture/policy_design_case/layer3_discovery_search_discipline.json` | Required dependency contract for G1 substrate search ledgers, recall/freshness, free-growth, no-hit, and no-authority search boundaries. |
| G0 hardcode backlog | `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json` | Source of the G1 strangle delta for `KNOWN_CONSTRUCTS` and scenario-family mappings; no fallback closure. |
| G0 engineering-quality check | `architecture/policy_design_case/layer3_engineering_quality_check.json` | Engineering bar for manifest/index-backed, deterministic, fail-closed G1 search; no eager full scans. |
| G0 `ResourceDiscoveryRecord` / `GroundingSearchLedger` | `src/polisyos/runtime/quality/layer3_grounding_inventory.py:251` / `src/polisyos/runtime/quality/layer3_grounding_inventory.py:263` | Reuse discovery posture and ledger semantics; do not create parallel search status. |
| G0 `SearchRecallSeed` / `IndexFreshnessRecord` | `src/polisyos/runtime/quality/layer3_grounding_inventory.py:281` / `src/polisyos/runtime/quality/layer3_grounding_inventory.py:294` | Store G1 recall/freshness refs as sibling records or wrapper fields, not as extra keys on the base G0 ledger. |
| G0 `DataAssetPort` | `src/polisyos/runtime/quality/layer3_grounding_inventory.py:468` | Input contract for substrate data-binding; no duplicate port model. |
| G0 adapter admission vocabulary | `src/polisyos/runtime/quality/layer3_grounding_inventory.py:452` | Reuse admission posture and issue-code style inside two G1 admission bundles; G1 purpose booleans stay outside the strict G0 record. |
| G0 readiness validator pattern | `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py:117` | Template for G1 validator, write mode, issue-code allowlist, manifest/runtime drift checks. |
| Master L1/L5/L6 substrate route | `docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md:368` | Closure gate for real L1 metric-binding search, L5 calibration ranking, and L6 routing; bounded surrogate must be explicit and limited and cannot replace available L1. |
| Production L1 DCAT | `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb::ds_metric_bindings` | Required G1 L1 search target; direct DuckDB SQL path with row/resource count, query refs, freshness, free-growth, and recall evidence. |
| Adapter preservation harness | `src/polisyos/runtime/quality/adapter_contracts.py:224` | Conformance battery for G1 path delta and non-lossy binding projection. |
| Fabric SourceContract v2 | `src/polisyos/fabric/connectors/contracts/source_contract.py:382` | Canonical source contract; G1 wraps it instead of creating a parallel source schema. |
| Fabric SourceContract helpers | `src/polisyos/fabric/connectors/contracts/source_contract.py:189` / `src/polisyos/fabric/connectors/contracts/source_contract.py:510` / `src/polisyos/fabric/connectors/contracts/source_contract.py:622` | Reuse field-policy, connector-schema wrapping, and snapshot patterns where possible; otherwise build equivalent nested Fabric submodels from metadata. |
| Fabric source-contract report | `tools/quality/validation/fabric_source_contracts.py:271` | Reuse report semantics for acquisition adapter and fail-closed gaps. |
| S3 substrate acquisition loop | `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:306` | Consumer/bridge for construct-not-observed -> binding/gap route. |
| S3 resolver-injection port | `src/polisyos/runtime/quality/layer2_substrate_acquisition.py:691` | Prove substrate consumption by resolving an S3 construct through a G1-built resolver, without rewriting the S3 state machine. |
| Capability-index compiler | `src/polisyos/runtime/quality/capability_index_compiler.py:1093` | Source of Ukraine panel capability metadata and acquisition strategy refs; not a substitute for L1 DCAT search. |
| Requirement-to-capability resolver | `src/polisyos/runtime/quality/capability_resolver.py:255` / `src/polisyos/runtime/quality/capability_resolver.py:299` | Use `from_duckdb()` plus `resolve()` for indexed selected/blocked binding results, acquisition strategies, reviewer queue, and capability-index refs; G1 must not re-rank capabilities or count this as L1 search. |
| Capability authority composer | `src/polisyos/runtime/quality/capability_authority.py:200` | Status/authority/limitation composition for G1 binding envelopes; no parallel G1 authority scorer. |
| Data requirement facets | `src/polisyos/data_requirement/compiler.py:39` | Consumer-facing facets for `source_contract_ref`, rights, lineage, and construct validity. |
| Data requirement compiler resolver port | `src/polisyos/data_requirement/compiler.py:121` | Existing substrate-consumer route for G1 binding metadata; use injection tests instead of new compiler logic. |
| Data Forge snapshot binding firewall | `src/polisyos/runtime/quality/data_forge_binding.py:1149` | Reuse durable-ref/local-path/provenance issue vocabulary for raw-output and local-path negatives. |
| Production data contract index | `src/polisyos/runtime/quality/production_data_contract_index.py:272` | Reuse as scenario-binding and active-ref negative pattern only; not sufficient SourceContract v2 validation for G1. |
| Ukraine data_forge manifests | `src/polisyos/data_forge/domains/ukraine/manifests.py:111` | Lineage and artifact metadata for real Ukraine processed assets. |
| UA-MSME corpus case | `tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json:443` | Corpus route and authority-boundary fixture. |
| W12D G0 gate | `tools/quality/validation/run_universal_outcome_corpus.py:9071` / `tools/quality/validation/run_universal_outcome_corpus.py:9143` | Neighboring G1 gate preserving G0 no-useful-design discipline and `conversion_outcome` semantics. |

## Implementation Design

Create `src/polisyos/runtime/quality/layer3_substrate_grounding.py` as the G1
producer/validator module. It should import G0 contracts from
`polisyos.runtime.quality.layer3_grounding_inventory`, import Fabric
`SourceContract` explicitly from
`polisyos.fabric.connectors.contracts.source_contract`, and use existing adapter
preservation helpers from `adapter_contracts.py`. It should use the repo-standard
structured stack: strict Pydantic contracts, structured JSON/TOML parsers,
`duckdb` or existing catalog indexes for tabular/catalog search, `pyarrow` for
columnar metadata, and existing vector/HNSW indexes where similarity search is
already provided. Do not implement ad hoc full-corpus scans or eager dataframe
loads as the search engine.

Keep the module as a wrapper/bridge. The implementation should add G1 request,
result, binding, report, and bundle models around existing G0/Fabric/resolver
contracts. It should not edit `capability_index_compiler.py`,
`capability_resolver.py`, `layer2_substrate_acquisition.py`, or W12D except for
the narrow consumer hooks named in this plan.

The substrate grounding search adapter reads the G0 first vertical case, G0
data asset ports, G0 discovery/search discipline, G0 hardcode backlog, and G0
dependency requirements. Given typed `Layer3G1SubstrateSearchRequest` records, it
searches L1 metric-binding candidates, applies L5 calibration ranking, applies L6
routing, and then consults the available G0 structured/registry/manifest indexes.
It records a G1 search ledger, selects or rejects candidates with explicit
cutoff/incompleteness reasons, and emits `Layer3G1SubstrateSearchResult` records
containing `GroundedSourceContractBinding`, `observed_but_uncertain`,
acquisition-gap, abstention, blocked-dependency, or search-ceiling outcomes.

The preferred first validation construct is a real Ukraine panel construct such
as `firm_survival` when the search path discovers a Ukraine panel capability and
validates a Fabric SourceContract snapshot. If the only support is proxy-limited
or construct-validity-limited, the status must be `observed_but_uncertain`, not
`grounded_binding`. `credit_program_enrollment` remains acquisition-required
unless a real validated SourceContract proves direct registry coverage.

G1 must add a substrate search mechanism that handles at least two distinct
request shapes, such as `construct_to_metric_binding` and
`scenario_family_to_source_contract`. This mechanism may reuse the existing
capability-index compiler/resolver during transition, but not as L1 search or as a
hardcoded fallback. The G1 bundle must record a `Layer3G1HardcodeStrangleDelta` showing
which G0 backlog entries were consumed by search-backed discovery and which
fallbacks were deleted/disabled with no fallback. If fallback removal would break
G1, the honest result is incomplete/search-ceiling repair, not successful closure.

G1 must also persist a `Layer3G1L1L5L6IndexCoverageReport`. Successful closure
requires the real L1 `dataset_catalog.duckdb::ds_metric_bindings` query path plus
L5/L6 refs. Because that L1 table exists in production data, a capability-index
or bounded surrogate is `unjustified_l1_surrogate` and cannot yield
`g1_l1_l5_l6_index_coverage_status = pass`. A bounded surrogate may validate a
missing non-L1 route segment, but it must name represented schemas, row/resource
counts, omitted full-scale coverage, and replay limits.

The adapter must derive candidate construct bindings through
`RequirementToCapabilityResolver` and `compose_capability_authority` outputs.
G1 maps resolver statuses into its local audit statuses:

- `selected_exact` or `selected_derived` with clean SourceContract, clean
  lineage, no limitations that block governed-pilot use, and no semantic loss can
  become `grounded_binding`.
- `selected_derived` or `selected_proxy_with_limitation` with real observed
  Ukraine assets, clean SourceContract, and explicit construct-validity/proxy
  limits becomes `observed_but_uncertain`.
- `blocked_acquisition_required` or `blocked_construct_not_observed` becomes an
  acquisition gap or `grounded_abstention`, never a coverage claim.

This mapping is one-way. G1 must not create a parallel authority score, re-rank
capabilities, or turn `satisfies_claim_evidence` into policy/causal authority.

The SourceContract snapshot path is a first-class producer responsibility. For
each grounded or uncertain binding, build a Fabric `SourceContract` v2 payload
from selected capability source assets, Ukraine manifest/Parquet metadata, and
port evidence. Validate the persisted payload with
`SourceContract.model_validate`, store its `content_hash`, and reject any binding
whose lineage refs remain workstation-local paths. The G0 README-level
`DataAssetPort` refs can identify the port but cannot by themselves satisfy G1
lineage/rights/freshness/fitness.

Prefer Fabric helpers where the selected source can be expressed through existing
connector/schema contracts: `SourceContract.from_connector_schema_contract`,
`default_source_field_access_policies`, `default_processing_contract_for_connector`,
and `source_contracts_snapshot_payload`. For Ukraine panel metadata that does not
already have a connector-schema contract, build equivalent Fabric submodels from
Parquet metadata and manifest refs, then validate the final payload through
Fabric's strict model.

Minimum Fabric SourceContract snapshot recipe:

- `id`: deterministic `layer3.ua_msme.<construct>.<asset_family>` id matching
  Fabric's contract id pattern.
- `version`: semantic patch version such as `1.0.0`.
- `owner` and `reviewer`: runtime/data-acquisition owners, not an LLM actor.
- `source`: `connector_id`, `dataset_pattern`, `profile_id`, source name, and
  organization derived from Ukraine asset metadata.
- `schema`: `schema_id`, `schema_version`, and `fields` built from Parquet
  metadata. Normalize source column names to Fabric `FieldSpec` snake-case names
  and stable ids; do not read row data to infer schema.
- `semantics`: domain `msme_credit_support`, canonical construct refs, and any
  metric definitions used by the binding.
- `security`: source classification plus `field_policies` covering every schema
  field, or `*` only when no concrete fields exist.
- `quality`: non-empty `contract_ref`, required checks, and min quality score.
- `terms`: allowed/disallowed uses preserving aggregate-only/no-row-level-public
  restrictions from rights evidence.
- `replay`: fixture/artifact ref or explicit non-replayable reason.
- `lineage`: seed node kind, durable evidence ref, and seed fields.
- `source_trust`, `processing`, `retention`, `status`, and `content_hash`.
  Processing idempotency must be enabled, replay retention must cover source
  retention, and G1 must not claim `exactly_once_narrow` without atomicity proof.

The active-flag-only negative fixture must fail before a binding can become
grounded or uncertain.

The search-ledger path is also a first-class producer responsibility. Every G1
selected candidate, rejected candidate, no-hit, acquisition gap, abstention, and
ceiling diagnosis must be represented by a `Layer3G1GroundingSearchLedger` whose
core fields mirror G0 `GroundingSearchLedger` semantics. Because the G0 ledger
model is strict and does not contain recall/freshness refs, G1 must carry those
refs either in wrapper fields or in `Layer3G1SearchRecallFreshnessReport`, with
deterministic links back to the ledger. The ledger/report pair must carry:

- typed request ref and normalized query refs;
- searched index refs and index/rule versions;
- selected and rejected candidate refs;
- ranking policy ref;
- cutoff/budget refs;
- absence/incompleteness reason;
- deterministic replay key;
- index freshness refs and known-groundable seed refs;
- `authoritative_for=[]` and `may_not_use_for` covering adapter admission,
  claim authority, promotion, publication, and useful design credit.

The search ledger can support auditability and ceiling diagnosis, but it cannot
itself fill a SourceContract, adapter-admission, or construct authority slot.

For S3 consumption, implement a small resolver bridge rather than a second S3
engine. `build_g1_requirement_to_capability_resolver(repo_root, bundle=None)`
should expose grounded/uncertain G1 bindings as existing
`RequirementToCapabilityResolver` capabilities and preserve acquisition gap
strategy refs. The S3 test then calls `resolve_expression` with that resolver and
proves the returned `CapabilityBindingResult` carries the G1 capability-index
ref, lineage refs, and no claim/promotion authority.

The acquisition adapter reads capability-index failure/acquisition strategy
records for the pinned case and emits fail-closed acquisition records. It may
produce a grounded binding only when Fabric SourceContract v2 validates with
rights, replay, lineage, and schema evidence. Otherwise it records
`grounded_abstention` or `ungrounded_blocked` with strategy refs, never a
coverage claim.

Persist G1 artifacts under `architecture/policy_design_case/`:

- `layer3_g1_adapter_admission_registry.json`
- `layer3_g1_substrate_search_ledgers.json`
- `layer3_g1_l1_l5_l6_index_coverage.json`
- `layer3_g1_search_recall_freshness.json`
- `layer3_g1_hardcode_strangle_delta.json`
- `layer3_g1_free_growth_report.json`
- `layer3_g1_search_engineering_quality_report.json`
- `layer3_g1_grounded_source_contracts.json`, containing validated Fabric
  SourceContract snapshots plus G1 binding records.
- `layer3_g1_lineage_contamination_ledger.json`
- `layer3_g1_conformance_report.json`
- `layer3_g1_coverage_lineage_abstention_surface.json`
- `layer3_g1_health_metric_delta.toml`
- `layer3_g1_adapter_contract_registry.toml`
- `layer3_g1_readiness_manifest.json`

The slice-local `layer3_g1_adapter_contract_registry.toml` must use the same
semantic-preservation grammar as `source_truth_lattice.toml`, include the
top-level field-family/lattice metadata the loader requires, and declare exactly
two G1 adapter paths:

- `layer3_data_asset_port_to_source_contract`
- `layer3_fabric_acquisition_to_source_contract`

The G1 validator must verify those paths through the existing
`load_adapter_contract_registry(path=...)` and `validate_adapter_preservation`
helpers. It must not mutate G0 artifacts or the global production source-truth
lattice.

The G1 validator must also load G0's `layer3_discovery_search_discipline.json`,
`layer3_hardcode_enumeration_backlog.json`, and
`layer3_engineering_quality_check.json`. G1 closure fails if G0 v2 is stale,
missing, below v2 schema/rule versions, or reports degraded recall/freshness,
unless the G1 outcome is explicitly `blocked_g0_dependency`.

Add a W12D G1 gate beside the existing G0 gate inside
`build_w12d_universal_outcome_corpus_report` after the G0 gate wrap and before
typed blockers plus `_summary(cases)`. The G1 gate must not overwrite the case
`conversion_outcome` written by the G0 gate; use `layer3_g1_grounding_outcome`
and G1 summary keys instead. The G1 gate surfaces:

- `schema_version: policyos.policy_design_case.layer3_g1_grounding_gate.v1`
- `case_id`
- `construct_bundle_id`
- `grounding_closure_outcome`
- `grounding_status`
- `grounded_construct_refs`
- `observed_but_uncertain_construct_refs`
- `grounded_abstention_refs`
- `acquisition_required_construct_refs`
- `search_ledger_refs`
- `l1_l5_l6_index_coverage_status`
- `search_recall_status`
- `index_freshness_status`
- `search_engineering_quality_status`
- `hardcode_fallback_deletion_status`
- `lineage_record_refs`
- `source_contract_refs`
- `counts_as_useful_design: false`
- `authoritative_for: ["layer3_g1_construct_grounding_audit"]`
- `may_not_use_for: ["claim_authority", "causal_effect", "policy_recommendation", "publishability", "adapter_promotion", "useful_design_credit", "production_authority", "search_hit_as_authority"]`

## Closure Metrics

All metrics are checked by `validate_layer3_g1_bundle` and the readiness CLI.

| Metric | Required value |
| --- | --- |
| `g0_v2_dependency_status` | `pass`; G0 schema/rule are v2, persisted closure artifact count is `16`, and `g1_dependency_requirements_status == "pass"`. |
| `g1_l1_l5_l6_index_coverage_status` | `pass`; G1 search ledgers cite direct L1 `dataset_catalog.duckdb::ds_metric_bindings` query refs plus L5 calibration and L6 routing refs. Capability-index refs are transition evidence only and cannot satisfy L1 coverage. |
| `g1_substrate_search_ledger_count` | `>= 1`; every selected/no-hit/abstention/ceiling route has a replayable ledger. |
| `g1_search_ledger_authority_boundary_leak_count` | `0`; ledgers have `authoritative_for=[]` and explicit `may_not_use_for`. |
| `g1_search_recall_seed_count` | `>= 2`, covering production source-contract discovery and one UA-MSME substrate request shape. |
| `g1_search_recall_status` | `pass` before any domain-ceiling claim. |
| `g1_index_freshness_status` | `pass` before any domain-ceiling claim. |
| `g1_no_hit_without_ledger_count` | `0`. |
| `g1_search_ceiling_repair_required_count` | `0` for successful closure; `>= 1` blocks domain ceiling when recall/freshness/ledger integrity fails. |
| `g1_free_growth_fixture_count` | `>= 1`; a new synthetic metric/source binding becomes discoverable/executable after index refresh with no code change. |
| `g1_mechanism_generality_request_shape_count` | `>= 2` for the same substrate search mechanism. |
| `g1_hardcode_strangle_delta_count` | `>= 2`, covering `KNOWN_CONSTRUCTS` and `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`. |
| `g1_hardcode_fallback_closure_count` | `0`; hardcoded lists cannot make G1 pass. |
| `g1_hardcode_fallback_deletion_status` | `deleted_or_disabled_no_fallback`; otherwise G1 closure is incomplete/search-ceiling repair, not successful closure. |
| `g1_no_hardcode_enumeration_lint_status` | `pass` for G1 adapter/validator/runtime code. |
| `g1_search_engineering_quality_status` | `pass`; named libraries/indexes, index-backed/lazy search, deterministic replay, no eager full-corpus scans, no broad fail-open error handling. |
| `g1_search_scaling_fixture_status` | `pass`; search runs on a bounded corpus larger than the pinned case and proves index-backed behavior rather than O(n) construct enumeration. |
| `g1_adapter_admission_record_count` | `2` exactly: substrate data-binding/search record and acquisition/gap record. |
| `g1_admitted_for_binding_adapter_count` | `1` when `grounding_closure_outcome = grounded_or_uncertain`; `0` is allowed only when `grounding_closure_outcome = grounded_abstention_domain_ceiling`. |
| `g1_admitted_for_gap_routing_adapter_count` | `1` exactly for the acquisition adapter's fail-closed gap route. |
| `g1_adapter_contract_path_count` | `2` exactly in `layer3_g1_adapter_contract_registry.toml`. |
| `g0_source_truth_adapter_path_count` | Remains `9`; G1 must not mutate G0 baseline. |
| `g1_adapter_maturity_values` | Each adapter is `fail_closed` or `predictive`; no `calibrated`. |
| `g1_promoted_adapter_count` | `0`; promotion remains out of scope until G4. |
| `pinned_case_id` | `ua-msme-affordable-loans-2022`. |
| `pinned_construct_bundle_id` | `ukrainian_msme_credit_constructs`. |
| `selected_grounding_construct_in_bundle` | `true`; selected grounded/uncertain construct must be listed in `layer2_first_proving_case.json`. |
| `grounding_closure_outcome` | `grounded_or_uncertain`, `grounded_abstention_domain_ceiling`, or blocked `search_ceiling_repair_required`; the last one is not successful closure. |
| `firm_survival_source_contract_v2_spike_status` | `valid_source_contract`, `domain_ceiling_data_insufficiency`, or `not_selected`; `not_selected` requires another pinned construct to carry the spike. |
| `grounded_or_uncertain_construct_count` | `>= 1` when `grounding_closure_outcome = grounded_or_uncertain`; may be `0` only with `grounded_abstention_domain_ceiling`. |
| `grounded_abstention_domain_ceiling_count` | `>= 1` when `grounding_closure_outcome = grounded_abstention_domain_ceiling`; each abstention has reason `data_insufficiency_domain_ceiling` and evidence refs. |
| `source_contract_snapshot_count` | `>= grounded_or_uncertain_construct_count`; uncertainty limits authority but does not remove the SourceContract requirement. |
| `grounded_source_contract_binding_count` | `>= 1` only when `grounding_closure_outcome = grounded_or_uncertain`; a binding may have status `grounded_binding` or `observed_but_uncertain`, but it must carry a validated SourceContract snapshot. |
| `observed_but_uncertain_count` | `>= 0`; counts as G1 grounding audit only when paired with SourceContract snapshot and clean lineage. |
| `acquisition_gap_record_count` | `>= 1` for a construct not directly grounded, expected `credit_program_enrollment` unless real validated data exists. |
| `clean_lineage_contamination_check_count` | `>= grounded_or_uncertain_construct_count`. |
| `contaminated_grounding_count` | `0`. |
| `raw_output_grounding_count` | `0`. |
| `missing_rights_grounding_count` | `0`. |
| `adapter_semantic_loss_events` | `0`. |
| `manifest_runtime_drift_count` | `0`. |
| `production_claim_authority_count` | `0`. |
| `useful_design_credit_count` | `0`. |
| `w12d_first_vertical_g1_gate_count` | `1` for the pinned case. |
| `surface_out_of_scope_audience_count` | `2`: PUBLIC and REVIEWER. |
| `g1_health_metric_delta_ids` | Includes all five G0 health metrics: `envelope-expansion-rate`, `adapter-semantic-loss`, `governance-throughput`, `demand-pull-vs-abstention`, and `search-recall@known-seeds+index-staleness`. Metrics G1 does not move must be recorded as `no_change` or `not_authority_stage`, not omitted. |
| `capability_ratchet_delta_recorded` | `true`; substrate grounding path no longer has missing-state labels, acquisition path is implemented as fail-closed gap route. |
| `parallel_authority_scorer_count` | `0`; G1 consumes `CapabilityBindingResult` and `compose_capability_authority`. |
| `source_contract_validation_mode` | `fabric_pydantic_v2`; active-flag or contract-id echo is insufficient. |
| `fabric_source_contract_validation_count` | `>= source_contract_snapshot_count`; each persisted snapshot validates through Fabric `SourceContract.model_validate`. |
| `local_path_lineage_ref_count` | `0`; no `/Users/...`, home-directory, or workstation-local path is recorded as lineage authority. |
| `parquet_profile_mode` | `metadata_only`; no full Parquet data scan in G1 targeted tests. |
| `full_parquet_scan_count` | `0` for G1 producer and tests. |
| `data_requirement_compiler_bridge_test_count` | `>= 1`; substrate consumption is proven through the existing resolver port. |
| `s3_substrate_consumer_bridge_test_count` | `>= 1`; S3 consumes G1 binding through `resolve_expression(..., resolver=...)`. |
| `w12d_g1_gate_injection_order` | `after_g0_before_summary`. |
| `layer3_g1_w12d_conversion_outcome_overwrite_count` | `0`; G1 does not mutate G0/G5 conversion semantics. |

## Contract Dictionary

Constants:

- `LAYER3_G1_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g1_substrate_grounding.v1"`
- `LAYER3_G1_RULE_VERSION = "policyos.layer3.g1.substrate_grounding_search.v1"`
- `LAYER3_G1_GATE_SCHEMA_VERSION = "policyos.policy_design_case.layer3_g1_grounding_gate.v1"`
- `G1_SUBSTRATE_DATA_BINDING_ADAPTER_ID = "layer3-substrate-data-binding-to-source-contract"`
- `G1_ACQUISITION_ADAPTER_ID = "layer3-fabric-acquisition-to-source-contract"`
- `G1_SUBSTRATE_SEARCH_ADAPTER_ID = "layer3-substrate-grounding-search"`
- `G1_SUBSTRATE_DATA_BINDING_ADAPTER_PATH_ID = "layer3_data_asset_port_to_source_contract"`
- `G1_ACQUISITION_ADAPTER_PATH_ID = "layer3_fabric_acquisition_to_source_contract"`
- `G1_PINNED_CASE_ID = "ua-msme-affordable-loans-2022"`
- `G1_CONSTRUCT_BUNDLE_ID = "ukrainian_msme_credit_constructs"`
- `G1_PREFERRED_EXISTING_ASSET_CONSTRUCT_ID = "firm_survival"`
- `G1_EXPECTED_ACQUISITION_GAP_CONSTRUCT_ID = "credit_program_enrollment"`

Grounding statuses:

- `grounded_binding`: Direct validated SourceContract binding with clean lineage,
  rights, freshness, fitness, contamination, and non-lossy preservation.
- `observed_but_uncertain`: Real observed/proxy-limited data exists, but coverage,
  construct validity, or uncertainty prevents stronger binding.
- `grounded_abstention`: Adapter ran, found insufficient evidence, and abstained
  with explicit reason.
- `grounded_abstention_domain_ceiling`: Adapter and conformance ran, current UA
  assets cannot honestly validate a Fabric SourceContract v2 for pinned
  grounding, L1/L5/L6 route coverage is explicit, G0/G1 recall and index freshness
  are healthy, engineering quality passes, hardcode fallbacks are deleted/disabled,
  and the result is recorded as Layer-3 domain ceiling rather than failure.
- `search_ceiling_repair_required`: Search ledger, recall, freshness,
  L1/L5/L6 coverage, free-growth, hardcode-free discovery, or engineering quality
  failed; no domain ceiling may be claimed.
- `blocked_l1_l5_l6_index_coverage`: G1 cannot prove the L1 metric-binding, L5
  calibration, and L6 routing search route. L1 requires a direct
  `ds_metric_bindings` query; bounded surrogate cannot satisfy available L1.
- `blocked_engineering_quality`: G1 search is technically weak: non-indexed,
  eager, non-deterministic, fail-open, or missing named library/index evidence.
- `ungrounded_blocked`: Missing rights, contamination, missing lineage, semantic
  loss, or invalid SourceContract blocks grounding.

Adapter admission values:

These values live on `Layer3G1AdapterAdmissionBundle`. Each bundle should include
one nested or adjacent G0-compatible `AdapterAdmissionRecord` for shared admission
vocabulary plus G1-specific purpose fields. Do not pass G1-only fields directly
to the strict G0 `AdapterAdmissionRecord`.

- Substrate data-binding/search adapter:
  - `maturity`: `predictive` only after conformance, L1/L5/L6 coverage,
    recall/freshness, free-growth, no-hardcode lint, fallback deletion/disablement,
    and search-engineering quality pass, otherwise `fail_closed`.
  - `promotion_state`: `shadow`.
  - `admission_purpose`: `binding`.
  - `admission_state`: `admitted` only for the governed binding slot.
  - `admitted_for_binding`: `true` only when conformance status is `pass` and
    `grounding_closure_outcome = grounded_or_uncertain`.
  - `admitted_for_gap_routing`: `false`.
- Acquisition adapter:
  - `maturity`: `fail_closed` unless a validated SourceContract proves a gap can
    ground.
  - `promotion_state`: `shadow`.
  - `admission_purpose`: `gap_routing`.
  - `admission_state`: `admitted` for the fail-closed gap route, or `blocked` if
    conformance fails.
  - `admitted_for_binding`: `false`.
  - `admitted_for_gap_routing`: `true` means admitted to candidate/gap routing,
    never production authority.

Issue codes:

- `layer3_g1_raw_output_without_adapter`
- `layer3_g1_g0_dependency_not_ready`
- `layer3_g1_l1_l5_l6_index_coverage_missing`
- `layer3_g1_l1_l5_l6_bounded_surrogate_overclaimed`
- `layer3_g1_l1_dcat_not_queried`
- `layer3_g1_capability_index_used_as_l1_search`
- `layer3_g1_unjustified_l1_surrogate`
- `layer3_g1_search_ledger_missing`
- `layer3_g1_search_ledger_authority_boundary_leak`
- `layer3_g1_search_recall_seed_miss_blocks_domain_ceiling`
- `layer3_g1_stale_index_blocks_domain_ceiling`
- `layer3_g1_no_hit_without_replayable_frontier`
- `layer3_g1_search_ceiling_not_domain_ceiling`
- `layer3_g1_free_growth_fixture_failed`
- `layer3_g1_mechanism_generality_single_request`
- `layer3_g1_hardcode_fallback_used_for_closure`
- `layer3_g1_hardcode_strangle_delta_missing`
- `layer3_g1_hardcode_fallback_not_deleted`
- `layer3_g1_no_hardcode_lint_failed`
- `layer3_g1_search_engineering_quality_failed`
- `layer3_g1_search_scaling_fixture_failed`
- `layer3_g1_missing_data_asset_port`
- `layer3_g1_missing_source_contract`
- `layer3_g1_source_contract_invalid`
- `layer3_g1_source_contract_validation_echo`
- `layer3_g1_construct_bundle_mismatch`
- `layer3_g1_missing_rights`
- `layer3_g1_contaminated_lineage`
- `layer3_g1_local_path_lineage_ref`
- `layer3_g1_semantic_loss`
- `layer3_g1_coverage_overclaim`
- `layer3_g1_acquisition_gap_overclaimed`
- `layer3_g1_domain_ceiling_data_insufficiency`
- `layer3_g1_parallel_authority_scorer`
- `layer3_g1_full_parquet_scan_required`
- `layer3_g1_manifest_runtime_drift`
- `layer3_g1_surface_unsynced`
- `layer3_g1_import_firewall_violation`
- `layer3_g1_g0_baseline_drift`
- `layer3_g1_useful_design_credit_leak`
- `layer3_g1_claim_authority_leak`
- `layer3_g1_w12d_conversion_outcome_overwrite`

Models/helpers to implement in `layer3_substrate_grounding.py`:

- `Layer3G1ValidationIssue`
- `Layer3G1ValidationReport`
- `Layer3G1SubstrateSearchRequest`
- `Layer3G1SubstrateSearchResult`
- `Layer3G1GroundingSearchLedger`
- `Layer3G1L1L5L6IndexCoverageReport`
- `Layer3G1SearchRecallSeed`
- `Layer3G1IndexFreshnessRecord`
- `Layer3G1SearchRecallFreshnessReport`
- `Layer3G1FreeGrowthFixture`
- `Layer3G1FreeGrowthReport`
- `Layer3G1MechanismGeneralityFixture`
- `Layer3G1HardcodeStrangleDelta`
- `Layer3G1SearchEngineeringQualityReport`
- `LineageContaminationCheck`
- `GroundedSourceContractBinding`
- `AcquisitionGroundingRecord`
- `Layer3G1AdapterAdmissionBundle`
- `Layer3G1ConformanceReport`
- `Layer3G1CoverageLineageAbstentionSurface`
- `Layer3G1ReadinessManifest`
- `Layer3G1Bundle`
- `build_layer3_g1_bundle(repo_root: Path) -> Layer3G1Bundle`
- `validate_layer3_g1_bundle(repo_root: Path, persisted: Mapping[str, Any] | Layer3G1Bundle) -> Layer3G1ValidationReport`
- `build_substrate_grounding_search_adapter(repo_root: Path, requests: Sequence[Layer3G1SubstrateSearchRequest]) -> list[Layer3G1SubstrateSearchResult]`
- `build_g1_grounding_search_ledgers(repo_root: Path) -> list[Layer3G1GroundingSearchLedger]`
- `build_g1_l1_l5_l6_index_coverage_report(repo_root: Path, results: Sequence[Layer3G1SubstrateSearchResult]) -> Layer3G1L1L5L6IndexCoverageReport`
- `validate_g1_search_recall_freshness(repo_root: Path, bundle: Layer3G1Bundle) -> Layer3G1SearchRecallFreshnessReport`
- `build_g1_hardcode_strangle_delta(repo_root: Path) -> Layer3G1HardcodeStrangleDelta`
- `build_g1_free_growth_report(repo_root: Path) -> Layer3G1FreeGrowthReport`
- `build_g1_search_engineering_quality_report(repo_root: Path, bundle: Layer3G1Bundle) -> Layer3G1SearchEngineeringQualityReport`
- `build_acquisition_grounding_adapter(repo_root: Path) -> list[AcquisitionGroundingRecord]`
- `validate_g1_adapter_conformance(repo_root: Path, bundle: Layer3G1Bundle) -> Layer3G1ConformanceReport`
- `render_g1_expert_machine_surface(bundle: Layer3G1Bundle) -> Layer3G1CoverageLineageAbstentionSurface`
- `probe_firm_survival_source_contract_v2_groundability(repo_root: Path) -> Layer3G1GroundabilityProbe`
- `build_fabric_source_contract_snapshot_from_capability(repo_root: Path, binding: CapabilityBindingResult, source_assets: Sequence[Mapping[str, Any]]) -> SourceContract`
- `build_g1_requirement_to_capability_resolver(repo_root: Path, bundle: Layer3G1Bundle | None = None) -> RequirementToCapabilityResolver`

Authority posture:

- `authoritative_for`: `["layer3_g1_construct_grounding_audit", "layer3_g1_lineage_contamination_audit"]`
- `may_not_use_for`: `["claim_authority", "causal_effect", "policy_recommendation", "publishability", "adapter_promotion", "useful_design_credit", "production_authority", "search_hit_as_authority"]`
- `surface_out_of_scope`: `["PUBLIC", "REVIEWER"]` with rationale
  `G1 surfaces grounding audit only; public/reviewer claim projection waits for G4/G5 promotion.`

## File Map

Create:

- `src/polisyos/runtime/quality/layer3_substrate_grounding.py`
- `tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py`
- `tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py`
- `tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py`
- `tests/fixtures/layer3/g1/raw_data_forge_output_without_adapter.json`
- `tests/fixtures/layer3/g1/contaminated_data_asset_port.json`
- `tests/fixtures/layer3/g1/missing_rights_source_contract.json`
- `tests/fixtures/layer3/g1/active_flag_only_source_contract.json`
- `tests/fixtures/layer3/g1/lossy_source_contract_projection.json`
- `tests/fixtures/layer3/g1/fabric_acquisition_without_source_contract.json`
- `tests/fixtures/layer3/g1/search_no_ledger_abstention.json`
- `tests/fixtures/layer3/g1/search_recall_seed_miss_domain_ceiling.json`
- `tests/fixtures/layer3/g1/stale_index_domain_ceiling.json`
- `tests/fixtures/layer3/g1/hardcoded_construct_fallback_used_for_closure.json`
- `tests/fixtures/layer3/g1/hardcoded_fallback_not_deleted.json`
- `tests/fixtures/layer3/g1/l1_l5_l6_index_coverage_missing.json`
- `tests/fixtures/layer3/g1/l1_l5_l6_bounded_surrogate_overclaimed.json`
- `tests/fixtures/layer3/g1/capability_index_used_as_l1_search.json`
- `tests/fixtures/layer3/g1/unjustified_l1_surrogate.json`
- `tests/fixtures/layer3/g1/free_growth_metric_binding_fixture.json`
- `tests/fixtures/layer3/g1/mechanism_generality_single_request.json`
- `tests/fixtures/layer3/g1/search_engineering_quality_unindexed_scan.json`
- `tests/fixtures/layer3/g1/local_path_lineage_import_manifest.json`
- `tests/fixtures/layer3/g1/manifest_runtime_drift.json`
- `architecture/policy_design_case/layer3_g1_adapter_admission_registry.json`
- `architecture/policy_design_case/layer3_g1_substrate_search_ledgers.json`
- `architecture/policy_design_case/layer3_g1_l1_l5_l6_index_coverage.json`
- `architecture/policy_design_case/layer3_g1_search_recall_freshness.json`
- `architecture/policy_design_case/layer3_g1_hardcode_strangle_delta.json`
- `architecture/policy_design_case/layer3_g1_free_growth_report.json`
- `architecture/policy_design_case/layer3_g1_search_engineering_quality_report.json`
- `architecture/policy_design_case/layer3_g1_grounded_source_contracts.json`
- `architecture/policy_design_case/layer3_g1_lineage_contamination_ledger.json`
- `architecture/policy_design_case/layer3_g1_conformance_report.json`
- `architecture/policy_design_case/layer3_g1_coverage_lineage_abstention_surface.json`
- `architecture/policy_design_case/layer3_g1_health_metric_delta.toml`
- `architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml`
- `architecture/policy_design_case/layer3_g1_readiness_manifest.json`
- `docs/reference/policy-design-case-layer3-substrate-grounding.md`

Modify:

- `tools/quality/validation/run_universal_outcome_corpus.py`
- `tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py`
- `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- `architecture/policy_design_case/inventory.json`
- `docs/reference/generated-artifacts.md`
- `docs/reference/documentation-inventory.md`
- `src/polisyos/runtime/quality/README.md` only if G1 public runtime entrypoint is exported.
- `src/polisyos/runtime/quality/__init__.py` only if the repo requires explicit public export; avoid exporting ambiguous `SourceContract`.
- `architecture/production_quality/ci_tiers.toml` only if adding the new tests to tier metadata is required by existing validator expectations.

Read/reuse-first:

- `src/polisyos/runtime/quality/layer3_grounding_inventory.py`
- `architecture/policy_design_case/layer3_discovery_search_discipline.json`
- `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json`
- `architecture/policy_design_case/layer3_engineering_quality_check.json`
- `architecture/policy_design_case/layer3_health_metric_ledgers.toml`
- `architecture/policy_design_case/layer3_data_asset_ports.json`
- `architecture/policy_design_case/layer3_first_vertical_case.json`
- `architecture/policy_design_case/layer3_g0_readiness_manifest.json`
- `src/polisyos/runtime/quality/adapter_contracts.py`
- `src/polisyos/runtime/quality/source_truth.py`
- `src/polisyos/runtime/quality/capability_resolver.py`
- `src/polisyos/runtime/quality/capability_authority.py`
- `src/polisyos/runtime/quality/data_forge_binding.py`
- `src/polisyos/runtime/quality/production_data_contract_index.py`
- `src/polisyos/fabric/connectors/contracts/source_contract.py`
- `src/polisyos/fabric/connectors/contracts/_schema_field.py`
- `tools/quality/validation/fabric_source_contracts.py`
- `src/polisyos/runtime/quality/layer2_substrate_acquisition.py`
- `src/polisyos/runtime/quality/capability_index_compiler.py`
- `src/polisyos/data_requirement/compiler.py`
- `src/polisyos/data_forge/domains/ukraine/models.py`
- `src/polisyos/data_forge/domains/ukraine/manifests.py`
- `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/LOCAL_IMPORT_MANIFEST.json`
- `tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json`

Do not modify:

- `architecture/production_quality/source_truth_lattice.toml` in G1.
- `production_data/**` raw/imported/curated data.
- `src/polisyos/pdc/**` for subordinate-engine imports.
- `src/polisyos/data_forge/domains/ukraine/**` production builders unless a
  red test proves an existing public helper cannot expose manifest metadata.
- `src/polisyos/fabric/connectors/contracts/source_contract.py` unless existing
  strict validators make a real SourceContract impossible to instantiate; prefer
  wrapping existing semantics.

## Task 1 - Red Tests and Fixtures

Intent: specify G1 behavior before implementation and prove the red failure is
missing capability, not a typo.

Files:

- Create `tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py`
- Create `tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py`
- Create `tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py`
- Modify `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`
- Create fixtures under `tests/fixtures/layer3/g1/`

Steps:

- [x] Add unit tests:
  - `test_g1_requires_g0_v2_dependency_contract_before_grounding`
  - `test_substrate_search_adapter_builds_replayable_ledger_for_pinned_ukraine_construct`
  - `test_substrate_search_no_hit_abstention_requires_replayable_frontier`
  - `test_search_hit_cannot_satisfy_grounding_without_source_contract_binding`
  - `test_selected_grounding_construct_must_belong_to_pinned_construct_bundle`
  - `test_raw_data_forge_output_cannot_satisfy_construct_slot_without_adapter`
  - `test_contaminated_or_missing_rights_asset_fails_closed`
  - `test_acquisition_adapter_records_gap_without_overclaiming_coverage`
  - `test_g1_adapter_preservation_blocks_lossy_projection`
  - `test_g1_adapter_contract_registry_loads_with_existing_loader_and_two_paths`
  - `test_g1_manifest_counts_match_runtime_builder`
  - `test_g1_does_not_mutate_g0_source_truth_baseline`
  - `test_g1_uses_requirement_to_capability_resolver_outputs_not_parallel_status_ranker`
  - `test_g1_source_contract_snapshot_is_fabric_v2_not_active_flag_echo`
  - `test_firm_survival_source_contract_v2_spike_reports_groundable_or_domain_ceiling`
  - `test_domain_ceiling_abstention_requires_healthy_search_recall_and_freshness`
  - `test_search_recall_seed_miss_blocks_domain_ceiling`
  - `test_stale_index_blocks_domain_ceiling`
  - `test_g1_free_growth_metric_binding_requires_no_code_change`
  - `test_g1_mechanism_generality_requires_two_request_shapes`
  - `test_hardcoded_construct_fallback_cannot_close_g1`
  - `test_hardcoded_fallback_must_be_deleted_or_disabled_for_closure`
  - `test_l1_l5_l6_index_coverage_required_for_g1_search_closure`
  - `test_l1_l5_l6_bounded_surrogate_cannot_be_overclaimed_as_full_dcat`
  - `test_capability_index_cannot_satisfy_l1_dcat_search`
  - `test_l1_surrogate_is_unjustified_when_production_dcat_exists`
  - `test_g1_search_engineering_quality_rejects_unindexed_scan`
  - `test_g1_canonicalizes_ukraine_import_manifest_local_paths_before_lineage`
  - `test_g1_data_requirement_compiler_consumes_binding_via_existing_resolver_port`
  - `test_g1_parquet_profile_uses_metadata_only_and_never_full_scans`
- [x] Add S3 consumer test in
  `tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py`:
  - `test_s3_substrate_consumes_g1_grounded_binding_through_existing_resolver_port`
- [x] Add repo-quality validator tests:
  - `test_layer3_g1_readiness_passes_with_persisted_runtime_bundle`
  - `test_layer3_g1_validator_fails_manifest_runtime_drift`
  - `test_layer3_g1_surface_registered_for_expert_and_machine`
  - `test_layer3_g1_validator_blocks_claim_authority_or_useful_design_leak`
  - `test_layer3_g1_validator_requires_g0_v2_dependency_artifacts`
  - `test_layer3_g1_validator_fails_search_ledger_authority_leak`
  - `test_layer3_g1_validator_blocks_domain_ceiling_on_recall_or_freshness_failure`
  - `test_layer3_g1_validator_blocks_hardcoded_fallback_closure`
  - `test_layer3_g1_validator_blocks_hardcoded_fallback_not_deleted`
  - `test_layer3_g1_validator_requires_free_growth_and_mechanism_generality`
  - `test_layer3_g1_validator_requires_l1_l5_l6_index_coverage`
  - `test_layer3_g1_validator_rejects_capability_index_as_l1_search`
  - `test_layer3_g1_validator_rejects_unjustified_l1_surrogate`
  - `test_layer3_g1_validator_requires_all_five_health_metric_deltas`
  - `test_layer3_g1_validator_requires_search_engineering_quality`
- [x] Add CLI tests:
  - `test_layer3_g1_readiness_cli_delegates_to_runtime_validator_and_reports_issue_codes`
  - `test_layer3_g1_readiness_cli_write_mode_reports_artifacts`
- [x] Add W12D tests:
  - `test_w12d_layer3_g1_records_first_vertical_grounding_without_claim_authority`
  - `test_w12d_layer3_g1_raw_fixture_binding_does_not_count_as_grounded`
  - `test_w12d_layer3_g1_gate_is_inserted_before_summary_without_overwriting_g0_conversion_outcome`
  - `test_w12d_layer3_g1_search_ceiling_does_not_count_as_domain_ceiling`
- [x] Add fixtures:
  - stale/missing G0 v2 dependency artifact.
  - search no-hit abstention without replayable frontier.
  - search recall seed miss that would otherwise look like domain ceiling.
  - stale index domain-ceiling fixture.
  - hardcoded construct fallback used for closure.
  - hardcoded fallback not deleted/disabled after search replacement.
  - missing L1/L5/L6 index coverage.
  - bounded L1/L5/L6 surrogate overclaimed as full DCAT-scale coverage.
  - capability-index search result incorrectly reported as L1 DCAT coverage.
  - bounded surrogate used for L1 despite available production `ds_metric_bindings`.
  - free-growth metric/source fixture requiring index refresh with no code change.
  - mechanism-generality fixture with only one request shape.
  - search-engineering quality fixture with unindexed scan/eager load.
  - raw data_forge/fabric payload with no adapter envelope.
  - contaminated data asset port.
  - SourceContract-like payload with missing rights.
  - SourceContract-like payload that only has `status: active` and no Fabric v2
    evidence.
  - firm-survival SourceContract v2 spike fixture with either valid metadata or
    explicit `data_insufficiency_domain_ceiling`.
  - lossy projection fixture dropping lineage/source fields.
  - acquisition strategy fixture with no validated SourceContract.
  - manifest drift fixture changing one metric.
  - Ukraine import manifest fixture containing `/Users/...` local path lineage.
- [x] Do not implement `layer3_substrate_grounding.py` or the G1 readiness CLI in this
  commit.

Command:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py \
  tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py::test_s3_substrate_consumes_g1_grounded_binding_through_existing_resolver_port \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_records_first_vertical_grounding_without_claim_authority \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_raw_fixture_binding_does_not_count_as_grounded \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_gate_is_inserted_before_summary_without_overwriting_g0_conversion_outcome \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_search_ceiling_does_not_count_as_domain_ceiling \
  -q
```

Expected red output:

- Tests fail because `polisyos.runtime.quality.layer3_substrate_grounding` does not
  exist.
- CLI tests fail because
  `tools.quality.validation.check_policy_design_case_layer3_g1_readiness` does
  not exist.
- W12D tests fail because `layer3_g1_grounding_gate` is not present.
- Search-ledger, recall/freshness, free-growth, hardcode-strangle,
  resolver/SourceContract/local-path/compiler-bridge tests fail because no G1
  runtime module maps existing discovery/capability bindings into a G1 envelope
  yet.
- S3 bridge test fails because no G1 resolver bridge exists for
  `resolve_expression(..., resolver=...)` yet.
- No failure is due to JSON syntax, fixture path typo, or misspelled test import.

Commit:

```text
test: add layer3 g1 red tests and fixtures
```

## Task 2 - Contracts, Producer, and Firewalls

Intent: implement strict G1 contracts, the substrate grounding search producer,
the acquisition/gap route, slice-local adapter preservation registry, and
fail-closed search/authority firewalls.

Files:

- Create `src/polisyos/runtime/quality/layer3_substrate_grounding.py`
- Create `architecture/policy_design_case/layer3_g1_adapter_contract_registry.toml`
- Create/update `tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py`
- Modify `tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py`

Steps:

- [x] Implement strict Pydantic models listed in Contract Dictionary with
  `extra="forbid"` and Google-style docstrings for public classes/functions.
- [x] Load and validate G0 v2 dependency artifacts before producing any G1
  result:
  - `layer3_g0_readiness_manifest.json`.
  - `layer3_discovery_search_discipline.json`.
  - `layer3_hardcode_enumeration_backlog.json`.
  - `layer3_engineering_quality_check.json`.
  - `layer3_health_metric_ledgers.toml`.
  - fail with `layer3_g1_g0_dependency_not_ready` if any required artifact is
    missing, below the accepted v2 schema/rule, or reports degraded recall,
    freshness, no-hardcode, free-growth, or engineering-quality status.
- [x] Import G0 `DataAssetPort`, `ResourceDiscoveryRecord`,
  `GroundingSearchLedger`, `SearchRecallSeed`, `IndexFreshnessRecord`, and
  admission vocabulary from `layer3_grounding_inventory.py`; do not duplicate G0
  contracts or invent a parallel search-state lattice. Wrap or link to these
  strict models for G1-only fields instead of validating extra keys through them.
- [x] Import Fabric `SourceContract` v2 explicitly from
  `polisyos.fabric.connectors.contracts.source_contract`; do not use the S3 local
  `SourceContract` export.
- [x] Implement the real L1 search path with DuckDB SQL against
  `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb::ds_metric_bindings`;
  record query refs, row/resource count, and index/freshness refs. Keep
  `RequirementToCapabilityResolver.from_duckdb()` as a transition resolver,
  consumer bridge, and acquisition-signal source only; it cannot satisfy L1
  coverage.
- [x] Implement `build_substrate_grounding_search_adapter(repo_root, requests)`:
  - accept typed `Layer3G1SubstrateSearchRequest` records and support at least
    `construct_to_metric_binding` and `scenario_family_to_source_contract`
    request shapes through the same search mechanism.
  - read G0 first vertical, G0 data asset ports, G0 discovery/search discipline,
    G0 hardcode backlog, `architecture/policy_design_case/layer2_first_proving_case.json`,
    and production/import manifest evidence.
  - search structured/registry/manifest indexes represented by G0
    `ResourceDiscoveryRecord` and `GroundingSearchLedger` semantics; transition
    use of the capability-index DuckDB through
    `RequirementToCapabilityResolver.from_duckdb()` is allowed only as an indexed
    resolver/acquisition bridge, while direct compiler internals are used only in
    targeted fixture tests. Neither path may become the L1 search route or a
    hardcoded closure fallback.
  - search L1 metric-binding refs by querying
    `dataset_catalog.duckdb::ds_metric_bindings`, then cite L5 calibration refs and
    L6 routing refs before producing a grounding outcome. If the direct L1 query
    does not run, emit `layer3_g1_l1_dcat_not_queried`. If capability-index output
    is reported as L1 coverage, emit
    `layer3_g1_capability_index_used_as_l1_search`. Because production L1 exists,
    an L1 surrogate is unjustified and emits `layer3_g1_unjustified_l1_surrogate`.
  - record one `Layer3G1GroundingSearchLedger` for every selected candidate,
    rejected candidate set, no-hit route, abstention route, and ceiling
    diagnosis. Each ledger must include query refs, searched index refs/versions,
    ranking policy, cutoff/budget, incompleteness evidence, replay key,
    `authoritative_for=[]`, and explicit `may_not_use_for`; freshness refs and
    known-seed refs must be present either on the G1 wrapper or in the linked
    recall/freshness report.
  - require selected grounding constructs to belong to the pinned construct
    bundle, but do not hardcode the selected construct as the only executable
    path.
  - require real production/import manifest evidence, not corpus fixture only.
  - rank candidates by Fabric SourceContract readiness, rights, lineage,
    freshness, fitness, calibration/coverage, and contamination; search rank is
    control-plane evidence only.
  - run `probe_firm_survival_source_contract_v2_groundability(repo_root)` or the
    selected-construct equivalent. It must return `valid_source_contract` with a
    validated Fabric v2 snapshot, or `domain_ceiling_data_insufficiency` with
    blocker evidence; it must not silently proceed on unvalidated proxy/local-path
    evidence.
  - profile Ukraine Parquet assets through the existing metadata-only helper path
    or equivalent `pyarrow.ParquetFile` metadata calls; do not read full data
    frames in the producer or tests.
  - resolve construct candidates through `RequirementToCapabilityResolver`
    output and `CapabilityBindingResult`; do not implement a second authority
    scorer or status ranker.
  - create and validate a Fabric SourceContract v2 snapshot for each
    grounded/uncertain substrate binding.
  - build that snapshot through
    `build_fabric_source_contract_snapshot_from_capability`; reuse
    `default_source_field_access_policies`,
    `default_processing_contract_for_connector`,
    `SourceContract.from_connector_schema_contract`, and
    `source_contracts_snapshot_payload` when the source shape allows it. Active
    SourceContract payloads must include schema fields, matching field policies,
    quality contract ref, replay evidence or non-replayable reason, lineage seed,
    terms, source trust, processing, retention, and content hash.
  - canonicalize Ukraine import-manifest absolute paths into repo/artifact/source
    snapshot refs before lineage authority is recorded.
  - emit `grounded_binding` only when rights, lineage, freshness, fitness,
    contamination, non-lossy SourceContract projection, and G1 adapter
    conformance pass.
  - emit `observed_but_uncertain` when real data exists but construct validity
    or proxy coverage is limited; this still requires a validated SourceContract
    snapshot and clean lineage.
  - emit `search_ceiling_repair_required` when a no-hit/abstention path depends
    on missing ledger, missing/overclaimed L1/L5/L6 coverage, absent direct L1 DCAT
    query, capability-index-as-L1 surrogate, stale index, failed known-seed recall,
    failed free-growth, failed search-engineering quality, or hardcoded fallback.
  - emit `grounded_abstention_domain_ceiling` only when no pinned construct can
    validate a Fabric SourceContract v2 snapshot and G0/G1 recall, freshness,
    L1/L5/L6 coverage, replay, no-hardcode, fallback deletion/disablement,
    engineering-quality, and free-growth checks all pass; use reason
    `data_insufficiency_domain_ceiling`, evidence refs, and no binding/source
    authority.
- [x] Implement `build_g1_l1_l5_l6_index_coverage_report`:
  - require every successful/abstention/search-ceiling result to cite a direct L1
    `ds_metric_bindings` query ref, L5 refs, and L6 refs. Capability-index refs do
    not count as L1 refs.
  - reject missing route coverage with
    `layer3_g1_l1_l5_l6_index_coverage_missing`.
  - reject surrogate overclaim with
    `layer3_g1_l1_l5_l6_bounded_surrogate_overclaimed`.
  - reject no direct production DCAT query with `layer3_g1_l1_dcat_not_queried`.
  - reject capability-index masquerading as L1 with
    `layer3_g1_capability_index_used_as_l1_search`.
  - reject an L1 surrogate while production L1 exists with
    `layer3_g1_unjustified_l1_surrogate`.
- [x] Implement `validate_g1_search_recall_freshness`:
  - at least two known-groundable seeds, covering production SourceContract
    discovery and one UA-MSME substrate request shape.
  - index freshness records for every index used by a selected/no-hit/abstention
    ledger.
  - failed recall or stale indexes block domain ceiling and produce the dedicated
    issue codes.
- [x] Implement `build_g1_free_growth_report`:
  - add a synthetic metric/source fixture to the real DCAT-style
    `ds_metric_bindings` search corpus/index, not only the capability-index.
  - refresh the index through the same direct L1 path used by normal discovery.
  - prove the new binding becomes discoverable/executable through that L1 path with
    no code change.
- [x] Implement `build_g1_hardcode_strangle_delta`:
  - consume both G0 backlog entries for `KNOWN_CONSTRUCTS` and
    `REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`.
  - record the search-backed replacement path, deletion/disablement result, no
    fallback proof, and remaining non-executable debt owner.
  - fail closure if a hardcoded construct/scenario mapping is used as the reason
    G1 passes.
  - fail closure if a replaced fallback remains executable through the G1 adapter
    path.
- [x] Implement `build_g1_search_engineering_quality_report`:
  - name every search library/index used (`duckdb`/existing catalog index,
    `pyarrow`, existing vector/HNSW where applicable).
  - prove search is index-backed, bounded/lazy, deterministic, replayable, and
    backed by the canonical L1 DCAT path for L1 claims.
  - prove the scaling fixture searches a bounded corpus larger than the pinned case
    without O(n) construct enumeration or eager full-corpus load.
  - reject broad fail-open exceptions and missing library/index evidence.
- [x] Implement `build_acquisition_grounding_adapter(repo_root)`:
  - consume capability-index acquisition strategy refs for missing constructs.
  - fail closed without validated Fabric SourceContract v2.
  - record `credit_program_enrollment` as acquisition-required unless validated
    real registry coverage exists.
- [x] Populate two `Layer3G1AdapterAdmissionBundle` records:
  - each bundle carries a strict G0-compatible `AdapterAdmissionRecord` for shared
    admission posture plus G1-specific `admission_purpose`,
    `admitted_for_binding`, and `admitted_for_gap_routing` fields outside the G0
    record.
  - substrate search/data-binding adapter: `maturity` is `predictive` only after
    conformance plus L1/L5/L6 coverage, recall/freshness, free-growth,
    no-hardcode/fallback deletion, and search-engineering quality pass,
    `promotion_state` is `shadow`, `admission_purpose` is `binding`,
    `admission_state` is `admitted` only for the governed binding slot, and
    `admitted_for_binding` is false for domain-ceiling abstention.
  - acquisition/gap adapter: `maturity` is `fail_closed`, `promotion_state` is
    `shadow`, `admission_purpose` is `gap_routing`, and `admission_state` is
    `admitted` only for fail-closed gap routing.
- [x] Implement raw-output and search-control firewalls:
  - raw data_forge/fabric payload without adapter envelope yields
    `layer3_g1_raw_output_without_adapter`.
  - missing rights yields `layer3_g1_missing_rights`.
  - contaminated lineage yields `layer3_g1_contaminated_lineage`.
  - workstation-local lineage refs yield `layer3_g1_local_path_lineage_ref`.
  - active-flag-only SourceContract-like payload yields
    `layer3_g1_source_contract_validation_echo`.
  - coverage overclaim yields `layer3_g1_coverage_overclaim`.
  - missing replayable search frontier yields `layer3_g1_search_ledger_missing`.
  - search-ledger authority leakage yields
    `layer3_g1_search_ledger_authority_boundary_leak`.
  - recall seed miss blocks domain ceiling with
    `layer3_g1_search_recall_seed_miss_blocks_domain_ceiling`.
  - stale index blocks domain ceiling with
    `layer3_g1_stale_index_blocks_domain_ceiling`.
  - a failed free-growth fixture yields `layer3_g1_free_growth_fixture_failed`.
  - hardcoded fallback used for closure yields
    `layer3_g1_hardcode_fallback_used_for_closure`.
- [x] Implement `layer3_g1_adapter_contract_registry.toml` with exactly two
  adapter paths, the top-level lattice/field-family definitions required by
  `load_source_truth_lattice`, and semantic field requirements for source
  surface, target surface, lineage, authority boundary, schema/rule version,
  rights, freshness, and contamination.
- [x] Implement `validate_g1_adapter_conformance` using
  `load_adapter_contract_registry(path=...)` and
  `validate_adapter_preservation`; unknown path or semantic loss must block.
- [x] Add `validate_layer3_g1_bundle` checks for G0 baseline drift:
  - persisted G0 `source_truth_adapter_path_count` remains `9`.
  - G1 adapter path count is `2`.
  - G1 artifacts never require mutating global source truth lattice.
- [x] Add `validate_layer3_g1_bundle` checks for health metrics:
  - all five G0 health metrics are present, even when recorded as `no_change` or
    `not_authority_stage`.
  - `adapter-semantic-loss` delta exists and has zero loss events.
  - `governance-throughput` delta exists and records no promotion attempt.
  - `search-recall@known-seeds+index-staleness` exists and blocks domain ceiling
    when degraded.
- [x] Add a bridge test that injects the existing resolver into
  `DataRequirementCompiler` and proves G1 binding metadata is consumed without
  patching compiler semantics.
- [x] Add `build_g1_requirement_to_capability_resolver` and the S3 bridge test
  proving `resolve_expression(..., resolver=g1_resolver)` consumes G1 binding
  metadata without editing `SubstrateAcquisitionLoop`.

Command:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py \
  tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py::test_s3_substrate_consumes_g1_grounded_binding_through_existing_resolver_port \
  -q
```

Expected output:

- Unit G1 tests pass.
- Negative tests report the exact `layer3_g1_*` issue codes.
- No test requires network access or mutation of production data.

Commit:

```text
feat: add layer3 g1 substrate grounding contracts and adapters
```

## Task 3 - Wiring, Projection, and Audit Surface

Intent: wire the G1 runtime bundle into validator, inventory, and EXPERT/MACHINE
audit surface.

Files:

- Create `tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py`
- Create `docs/reference/policy-design-case-layer3-substrate-grounding.md`
- Modify `architecture/policy_design_case/inventory.json`
- Modify `docs/reference/generated-artifacts.md`
- Modify `docs/reference/documentation-inventory.md`
- Modify `src/polisyos/runtime/quality/README.md` only if public export is added.
- Modify `src/polisyos/runtime/quality/__init__.py` only if needed.
- Create/update repo-quality tests for G1 validator/CLI.

Steps:

- [x] Implement G1 readiness CLI following the G0 validator pattern:
  - `validate_layer3_g1_readiness(repo_root: Path, *, write: bool = False) -> dict[str, Any]`.
  - `--repo-root`, `--write`, and `--output-format json|text`.
  - issue-code allowlist for all Contract Dictionary issue codes.
  - artifact write mode for all G1 persisted files.
- [x] Validator must load and validate G0 v2 dependency artifacts before any G1
  pass result:
  - discovery/search discipline.
  - hardcode backlog.
  - engineering-quality check.
  - health metric ledgers.
  - readiness manifest schema/rule/status.
- [x] Validator must recompute runtime bundle and compare persisted manifest
  metrics. Hard-coded pass is forbidden.
- [x] Validator must check inventory registration and docs/reference surface.
- [x] Validator must check G1 output authority posture:
  - authoritative only for G1 grounding/lineage audit.
  - search ledgers, search hits, no-hit routes, and hardcode-strangle reports are
    never authority for grounding, claim support, publication, or design quality.
  - may not be used for claim authority, causal effects, promotion, publication,
    or useful design credit.
  - PUBLIC and REVIEWER audiences are recorded as explicit
    `surface_out_of_scope` with G4/G5 rationale.
- [x] Validator must check G1 search-health posture:
  - L1/L5/L6 index coverage is present, with direct L1
    `ds_metric_bindings` query refs; capability-index refs do not satisfy L1.
  - any L1 surrogate while production DCAT exists is blocked as
    `layer3_g1_unjustified_l1_surrogate`.
  - every selected/no-hit/abstention/ceiling route has a replayable ledger.
  - `g1_search_recall_status == pass` before domain ceiling.
  - `g1_index_freshness_status == pass` before domain ceiling.
  - `g1_free_growth_fixture_count >= 1`.
  - `g1_mechanism_generality_request_shape_count >= 2`.
  - no-hardcode lint status is pass.
  - fallback deletion/disablement status is `deleted_or_disabled_no_fallback`.
  - capability-index-as-L1 search count is zero.
  - search-engineering quality/scaling status is pass.
  - all five health metric deltas are present.
  - hardcode fallback closure count is zero.
- [x] Add `layer3_g1_substrate_grounding_audit_surface` entry to
  `architecture/policy_design_case/inventory.json` with EXPERT and MACHINE
  audiences.
- [x] Add generated-artifact references for all G1 artifacts, including search
  ledgers, L1/L5/L6 index coverage, recall/freshness report, free-growth report,
  hardcode strangle delta, search-engineering quality report, and readiness
  manifest.
- [x] Add docs reference page that lists schema version, rule version, artifacts,
  validator command, surfaces, authority posture, search-health gates, G0
  dependency gate, and negative controls.

Command:

```bash
uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_fails_manifest_runtime_drift \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_surface_registered_for_expert_and_machine \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_blocks_claim_authority_or_useful_design_leak \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_requires_g0_v2_dependency_artifacts \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_fails_search_ledger_authority_leak \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_blocks_domain_ceiling_on_recall_or_freshness_failure \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_blocks_hardcoded_fallback_closure \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_blocks_hardcoded_fallback_not_deleted \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_requires_free_growth_and_mechanism_generality \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_requires_l1_l5_l6_index_coverage \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_requires_all_five_health_metric_deltas \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py::test_layer3_g1_validator_requires_search_engineering_quality \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py \
  -q

# Diagnostic only before Task 5: this may exit non-zero if the only remaining
# issues are missing persisted layer3_g1_* artifacts.
uv run python tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py \
  --repo-root . \
  --output-format json
```

Expected output:

- Runtime/surface/authority repo-quality tests and CLI tests pass.
- Before Task 5 write mode, `test_layer3_g1_readiness_passes_with_persisted_runtime_bundle`
  is intentionally not run here; if run, it should fail with missing
  `architecture/policy_design_case/layer3_g1_*` persisted artifacts rather than
  a code error.
- CLI JSON in non-write mode is diagnostic before Task 5: it may return non-zero
  and report missing persisted artifacts, but it must still recompute runtime
  metrics, list expected artifact refs, and expose issue codes instead of
  hard-coded pass.
- CLI JSON includes G1 metrics and no `layer3_g1_surface_unsynced`,
  `layer3_g1_claim_authority_leak`, or `layer3_g1_useful_design_credit_leak`.
- CLI JSON includes L1/L5/L6 coverage, all five health metric deltas,
  no-hardcode/fallback deletion status, and search-engineering quality/scaling
  status.

Commit:

```text
feat: surface layer3 g1 grounding audit and readiness validator
```

## Task 4 - Corpus Route

Intent: route the pinned UA-MSME W12D case through the G1 gate while preserving
G0/G5 authority boundaries.

Files:

- Modify `tools/quality/validation/run_universal_outcome_corpus.py`
- Modify `tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py`

Steps:

- [x] Import `build_layer3_g1_bundle` from
  `polisyos.runtime.quality.layer3_substrate_grounding`.
- [x] Add `_layer3_g1_grounding_context(repo_root)` mirroring the G0 context
  shape but reading G1 readiness/bundle metrics.
- [x] Add `_with_layer3_g1_grounding_gate(case, g1_context=...)` beside the G0
  gate.
- [x] In `build_w12d_universal_outcome_corpus_report`, compute `g1_context` and
  wrap cases with `_with_layer3_g1_grounding_gate` after the existing G0 wrap and
  before typed blockers plus `_summary(cases)`.
- [x] Do not assign `case["conversion_outcome"]` in G1 code. Store G1's result
  in `layer3_g1_grounding_gate["layer3_g1_grounding_outcome"]` and summary
  fields only.
- [x] G1 gate must only affect the pinned case; other corpus cases stay
  ungrounded or out-of-envelope for G1.
- [x] G1 gate must surface coverage/lineage/abstention, not useful design.
- [x] G1 gate must surface search-ledger refs and search-health status whenever
  the route is no-hit, abstention, or ceiling diagnosis.
- [x] G1 gate must show `counts_as_useful_design: false`.
- [x] Raw fixture binding must not count as grounded and must produce
  `layer3_g1_raw_output_without_adapter`.
- [x] Corpus fixture `expected_adapter_bindings` must remain annotation-only; it
  cannot satisfy G1 without `GroundedSourceContractBinding`.
- [x] Search ceiling must remain a repair-required G1 state; it cannot increment
  domain-ceiling or grounded counts.
- [x] Update summary fields without breaking G0 summary semantics:
  - `layer3_g1_grounding_closure_outcome`
  - `layer3_g1_grounded_or_uncertain_construct_count`
  - `layer3_g1_grounded_abstention_domain_ceiling_count`
  - `layer3_g1_search_ceiling_repair_required_count`
  - `layer3_g1_search_ledger_count`
  - `layer3_g1_l1_l5_l6_index_coverage_status`
  - `layer3_g1_search_recall_status`
  - `layer3_g1_index_freshness_status`
  - `layer3_g1_search_engineering_quality_status`
  - `layer3_g1_acquisition_gap_record_count`
  - `layer3_g1_useful_design_credit_count`
  - `layer3_g1_claim_authority_leak_count`
  - `layer3_g1_hardcode_fallback_deletion_status`
  - `layer3_g1_hardcode_fallback_closure_count`
  - `layer3_g1_w12d_conversion_outcome_overwrite_count`

Command:

```bash
uv run pytest \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_records_first_vertical_grounding_without_claim_authority \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_raw_fixture_binding_does_not_count_as_grounded \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_gate_is_inserted_before_summary_without_overwriting_g0_conversion_outcome \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_search_ceiling_does_not_count_as_domain_ceiling \
  -q
```

Expected output:

- Pinned case has `layer3_g1_grounding_gate`.
- `counts_as_useful_design` remains `false`.
- Existing G0 `conversion_outcome` remains unchanged.
- `layer3_g1_grounding_closure_outcome` is either `grounded_or_uncertain` with
  `layer3_g1_grounded_or_uncertain_construct_count >= 1`, or
  `grounded_abstention_domain_ceiling` with
  `layer3_g1_grounded_abstention_domain_ceiling_count >= 1` and reason
  `data_insufficiency_domain_ceiling` plus passing L1/L5/L6 coverage, search
  recall/freshness, hardcode-free, and engineering-quality gates.
- `search_ceiling_repair_required` does not count as domain ceiling or grounded
  closure.
- Raw fixture negative fails closed with `layer3_g1_raw_output_without_adapter`.

Commit:

```text
feat: route layer3 g1 grounding through universal outcome corpus
```

## Task 5 - Manifest, Validator, and Registration

Intent: persist G1 artifacts, register traceability, and prove manifest/runtime
drift detection.

Files:

- Create/update all `architecture/policy_design_case/layer3_g1_*` artifacts.
- Modify `architecture/policy_design_case/inventory.json`.
- Modify `docs/reference/generated-artifacts.md`.
- Modify `docs/reference/documentation-inventory.md`.
- Use `tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py`.
- Use repo-quality tests from Task 3.

Steps:

- [x] Run G1 readiness CLI with `--write`.
- [x] Inspect persisted artifacts for:
  - schema/rule versions.
  - G0 v2 dependency status `pass`.
  - L1/L5/L6 index coverage status `pass`, with direct L1
    `dataset_catalog.duckdb::ds_metric_bindings` query refs and no capability-index
    or bounded surrogate standing in for L1.
  - pinned case and construct bundle ids.
  - substrate search ledger count `>= 1`.
  - every selected/no-hit/abstention/ceiling route has a ledger ref.
  - every search ledger has `authoritative_for=[]` and explicit
    `may_not_use_for`.
  - known-groundable G1 search recall seed count `>= 2`.
  - `g1_search_recall_status == pass` before domain ceiling.
  - `g1_index_freshness_status == pass` before domain ceiling.
  - `g1_search_ceiling_repair_required_count == 0` for successful closure.
  - free-growth fixture count `>= 1` and free-growth status `pass`.
  - mechanism-generality request shape count `>= 2`.
  - free-growth and mechanism-generality fixtures exercise the real DCAT path, not
    only the capability-index.
  - hardcode strangle delta count `>= 2`.
  - hardcoded fallback closure count `0`.
  - hardcoded fallback deletion/disablement status
    `deleted_or_disabled_no_fallback`.
  - no-hardcode lint status `pass`.
  - search-engineering quality status `pass`.
  - search scaling fixture status `pass`.
  - adapter admission record count `2`.
  - admitted-for-binding count matches `grounding_closure_outcome`.
  - admitted-for-gap-routing count `1`.
  - adapter contract path count `2`.
  - SourceContract snapshot count `>= grounded_or_uncertain_construct_count`.
  - every SourceContract snapshot validates through Fabric
    `SourceContract.model_validate` and carries a content hash.
  - grounded/uncertain construct count `>= 1` when closure outcome is
    `grounded_or_uncertain`.
  - grounded abstention domain ceiling count `>= 1` when closure outcome is
    `grounded_abstention_domain_ceiling`, with reason
    `data_insufficiency_domain_ceiling`.
  - acquisition gap count `>= 1`.
  - all five health metric deltas, including no-change/not-authority-stage
    readings for metrics not moved by G1.
  - local path lineage ref count `0`.
  - parallel authority scorer count `0`.
  - full Parquet scan count `0`.
  - data requirement compiler bridge test count `>= 1`.
  - S3 substrate consumer bridge test count `>= 1`.
  - PUBLIC/REVIEWER explicit `surface_out_of_scope` entries.
  - no authority/useful-design leak.
  - no W12D conversion-outcome overwrite.
  - G0 baseline unchanged.
- [x] Ensure `layer3_g1_readiness_manifest.json` lists every persisted artifact.
- [x] Ensure the readiness manifest includes the G1 search ledgers, L1/L5/L6
  coverage report, recall/freshness report, hardcode strangle delta, free-growth
  report, and search-engineering quality report.
- [x] Ensure manifest counts match `build_layer3_g1_bundle(repo_root)`.
- [x] Ensure docs/reference and inventory entries point to the G1 validator and
  artifacts.
- [x] Add/update tests that mutate persisted metrics and expect
  `layer3_g1_manifest_runtime_drift`.

Command:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py \
  --repo-root . \
  --write \
  --output-format json

uv run pytest \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py \
  -q
```

Expected output:

- CLI write mode emits/persists all G1 artifacts.
- Validator tests pass, including
  `test_layer3_g1_readiness_passes_with_persisted_runtime_bundle`, which was
  intentionally held until Task 5 because persisted artifacts did not exist in
  Task 3.
- Drift detection is proven by fixture mutation.
- `architecture/policy_design_case/inventory.json` has one G1 audit-surface
  entry with EXPERT/MACHINE audiences.

Commit:

```text
feat: persist layer3 g1 manifest and audit registration
```

## Task 6 - Regression Snapshots

Intent: stabilize focused regression coverage without running the full heavy
backend suite locally.

Files:

- Update test snapshots/expected JSON only where G1 runtime output requires it.
- Update docs generated references only where validator artifacts require it.
- Do not update unrelated W12D snapshots or broad corpus baselines.

Steps:

- [x] Run the targeted runtime and validator tests.
- [x] Run the targeted W12D G1 tests.
- [x] If snapshot text changes, inspect every changed line for authority posture:
  no claim authority, no promotion, no useful design credit, and no search hit
  projected as grounding authority.
- [x] Confirm search-health snapshots distinguish `search_ceiling_repair_required`
  from `grounded_abstention_domain_ceiling`.
- [x] Confirm L1/L5/L6 coverage and search-engineering quality snapshots are
  visible and cannot be overclaimed.
- [x] Confirm hardcode-strangle/free-growth snapshots show no closure fallback to
  `KNOWN_CONSTRUCTS` or scenario-family mappings.
- [x] Confirm G0 tests still pass where they protect freeze semantics:
  G0 source-truth baseline remains 9, and G0 zero-admission semantics remain
  historical.
- [x] Do not run full `workspace verify --backend-only` locally unless the user
  asks; it is documented as optional/remote in Task 7.

Command:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py \
  tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py \
  tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py::test_s3_substrate_consumes_g1_grounded_binding_through_existing_resolver_port \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_records_first_vertical_grounding_without_claim_authority \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_raw_fixture_binding_does_not_count_as_grounded \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_gate_is_inserted_before_summary_without_overwriting_g0_conversion_outcome \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_search_ceiling_does_not_count_as_domain_ceiling \
  -q
```

Expected output:

- Focused regression tests pass.
- G0 freeze tests still pass.
- No broad corpus useful-design score changes.
- Search ceiling, recall miss, stale index, free-growth failure, and hardcoded
  fallback negatives remain fail-closed.

Commit:

```text
test: add layer3 g1 regression snapshots
```

## Task 7 - Full Gate Done When

Intent: prove G1 closure with a targeted local gate and leave only heavy CI
parity as optional/remote.

Files:

- No planned file edits. If this gate reveals a defect, fix in the smallest
  relevant file and commit with a precise message.

Steps:

- [x] Run all targeted G1 and nearby G0/S3 tests.
- [x] Run G1 readiness validator without write mode.
- [x] Run architecture guardrails.
- [x] Inspect G1 persisted artifacts and W12D summary for authority leaks.
- [x] Re-open the failure-pattern register and confirm
  P01/P02/P03/P04/P05/P07/P08/P09/P10/P12/P13/P14/P15/P25/C41/T7/Rule12
  closures are represented.
- [x] Confirm no G1 output is used for claim authority, causal effect,
  publishability, adapter promotion, or useful design credit.
- [x] Confirm no search hit/no-hit/search ledger is used as grounding authority
  and no failed recall/freshness path is reported as domain ceiling.
- [x] Confirm G1 free-growth and mechanism-generality fixtures pass with no code
  change for the new synthetic metric/source binding through real
  `ds_metric_bindings`.
- [x] Confirm L1/L5/L6 coverage includes direct L1 DCAT query refs and that
  capability-index or bounded surrogate output is not counted as L1 coverage.
- [x] Confirm hardcoded fallbacks are deleted/disabled with no fallback and G1
  adapter code passes no-hardcode-enumeration lint.
- [x] Confirm search-engineering quality/scaling status passes with named
  libraries/indexes and no unindexed/eager full-corpus search.

Command:

```bash
uv run pytest \
  tests/unit/runtime/quality/test_layer3_g1_substrate_grounding.py \
  tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py \
  tests/unit/runtime/quality/test_layer2_s3_substrate_acquisition.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness.py \
  tests/repo_quality/tools/test_policy_design_case_layer3_g1_readiness_cli.py \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_records_first_vertical_grounding_without_claim_authority \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_raw_fixture_binding_does_not_count_as_grounded \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_gate_is_inserted_before_summary_without_overwriting_g0_conversion_outcome \
  tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py::test_w12d_layer3_g1_search_ceiling_does_not_count_as_domain_ceiling \
  -q

uv run python tools/quality/validation/check_policy_design_case_layer3_g1_readiness.py \
  --repo-root . \
  --output-format json

uv run polisyos-tools architecture guardrails check
```

Expected output:

- All targeted tests pass.
- G1 readiness JSON has `"status": "pass"` following the G0 readiness CLI
  contract.
- G1 metrics satisfy Closure Metrics exactly.
- G1 L1/L5/L6 coverage, search recall/freshness, free-growth,
  hardcode-strangle, no-hardcode lint, search-engineering quality/scaling, and
  mechanism generality gates pass; L1 coverage and free-growth are proven through
  the real `ds_metric_bindings` path, not the capability-index.
- Fabric SourceContract snapshots validate through Fabric v2, not active-flag
  echo.
- W12D G1 gate is present before summary and does not overwrite G0
  `conversion_outcome`.
- Architecture guardrails pass.
- No full backend verify is required locally for G1 closeout.

Optional remote/heavy parity command:

```bash
python3 -m tools.cli workspace verify --backend-only
```

Commit:

```text
No commit expected unless Task 7 reveals and fixes a defect.
```

## Commit Sequence

1. `test: add layer3 g1 red tests and fixtures`
2. `feat: add layer3 g1 substrate grounding contracts and adapters`
3. `feat: surface layer3 g1 grounding audit and readiness validator`
4. `feat: route layer3 g1 grounding through universal outcome corpus`
5. `feat: persist layer3 g1 manifest and audit registration`
6. `test: add layer3 g1 regression snapshots`

## Closeout Pattern Check

Before closing G1, re-read
`docs/reference/policy-design-case-failure-patterns.md:13` and record the result
in the final implementation summary.

| Pattern | Closeout question | Required acceptance signal |
| --- | --- | --- |
| P01 | Does the substrate grounding chain flow from typed search request to replayable frontier to validated SourceContract binding or honest ceiling to W12D/S3 consumer to surface? | `validate_layer3_g1_bundle` passes and W12D pinned-case G1 gate exists with `grounded_or_uncertain` or healthy `grounded_abstention_domain_ceiling`. |
| P02/P12 | Do adapters and consumers exchange one typed binding envelope, not parallel ad hoc payloads? | S3/W12D tests consume `GroundedSourceContractBinding` or explicit acquisition record. |
| P03 | Can EXPERT/MACHINE inspect coverage, lineage, and abstention, and are PUBLIC/REVIEWER explicitly scoped out? | Inventory/docs reference and readiness validator surface checks pass; PUBLIC/REVIEWER have `surface_out_of_scope` rationale. |
| P04/P09 | Are statuses composed and are blockers hard, not warnings? | Missing rights, contamination, semantic loss, and raw output produce fail-closed issue codes. |
| P05/P15 | Can G1 outputs launder into claim authority, publication, promotion, or useful design? | W12D and validator assert `may_not_use_for` and leak counts are zero. |
| P07/P08 | Are rule, replay, and time roles preserved? | Binding records include schema/rule version, persisted SourceContract snapshot/hash, coverage/freshness refs, and generated time. |
| P10 | Do negatives prove content detection, not fixture echo? | Raw-output, contamination, missing-rights, lossy-projection, and overclaim tests fail for content reasons. |
| P25/T7 | Can bad recall, stale indexes, no-hit search, or capability-index pseudo-search masquerade as honest domain ceiling? | Search ledgers are replayable; L1/L5/L6 coverage includes direct `ds_metric_bindings` refs; recall/freshness checks pass before domain ceiling; failed checks emit `search_ceiling_repair_required`. |
| P13 | Did G1 reuse existing substrate instead of building a new engine? | File diff shows wrapper module/validator/artifacts only; no data_forge/fabric rewrite. |
| Rule 12 | Did G1 avoid hardcoded construct/source/method enumeration as closure logic? | Hardcode strangle delta covers G0 backlog entries, hardcoded fallback count is zero, fallback deletion/disablement is proven, no-hardcode lint passes, and free-growth fixture passes through real DCAT after index refresh with no code change. |
| Engineering quality | Is the search engine technically strong enough to free-grow? | Named libraries/indexes are recorded; search is index-backed/lazy against the canonical L1 path, deterministic, and scaling-tested; unindexed/eager scan and capability-index-as-L1 fixtures fail. |
| P14/C41 | Does lineage collapse/contamination prevent independence inflation? | Contamination ledger clean count matches grounded/uncertain records; contaminated fixture cannot ground. |
| Resolver/authority reuse | Did G1 consume existing capability status and authority posture instead of adding a scorer? | Tests prove G1 uses `CapabilityBindingResult`; `parallel_authority_scorer_count == 0`. |
| SourceContract v2 | Did G1 validate real Fabric SourceContract snapshots rather than echo active refs? | Active-flag-only fixture fails with `layer3_g1_source_contract_validation_echo`; snapshots pass `SourceContract.model_validate`. |
| Local lineage | Did G1 turn local import paths into durable lineage refs? | `/Users/...` fixture fails with `layer3_g1_local_path_lineage_ref`; persisted local path count is zero. |
| W12D order | Did G1 surface before summary without hijacking G0/G5 conversion semantics? | W12D test proves `layer3_g1_grounding_gate` exists and `conversion_outcome` is unchanged. |
| G0 freeze | Did G1 avoid rewriting G0 baseline? | G0 readiness manifest remains `source_truth_adapter_path_count: 9`; G1 path delta is in slice-local registry. |

G1 is complete only when the target capability transition is no longer
`producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, `surface_missing`, or `semantic_test_missing` for the
pinned substrate grounding-or-domain-ceiling path. If real UA assets validate,
the path closes as `grounded_or_uncertain`; if the spike proves current assets
cannot honestly form Fabric SourceContract v2 grounding and recall/freshness,
L1/L5/L6 coverage, free-growth, replay, engineering-quality, and hardcode-free
checks pass, the path closes as
`grounded_abstention_domain_ceiling`. If search health is degraded, the only
honest outcome is `search_ceiling_repair_required` or incomplete. The
acquisition adapter may remain fail-closed for direct grounding, but it must be
implemented as a consumer-visible gap route with negative controls and no
coverage overclaim.
