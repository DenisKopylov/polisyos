---
plan_id: layer3-g0-capability-data-inventory-triage-discipline-freeze
title: "G0 - Discovery/Search Discipline, Inventory & Triage Freeze"
type: slice-plan
status: active
created: 2026-06-06
revised: 2026-06-06
slice: G0
depends_on:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/reference/policy-design-case-failure-patterns.md
  - architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json
cells_closed: []
layer_cells_advanced:
  - layer3.discovery_search_discipline
  - layer3.capability_inventory
  - layer3.data_asset_ports
  - layer3.quarantine_registry
  - layer3.adapter_admission_gate
expected_open_cell_count: 0
floor_id: layer3_grounding_subordination
metric: layer3_g0_discovery_search_readiness_gate
source_roadmap: docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md
constitution: docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
---

# G0 - Discovery/Search Discipline, Inventory & Triage Freeze

## For Agentic Workers

This is an executable slice spec, not strategy. Follow it red-first. It
supersedes the earlier G0 interpretation that froze inventory, four health
metrics, and pre-admission records only. Existing G0 code and artifacts may be
reused as substrate, but they are **not protected as done**: anything that does
not satisfy Rule 12, T7, and the five-metric G0 closure must be migrated,
rewritten, or retired.

G0 does not implement G1+ adapters. G0 makes it impossible for G1+ to close by
hardcoded construct/dataset/method lists, stale indexes, unmeasured no-hit
abstention, or search output projected as authority.

Frontmatter note: `layer_cells_advanced` entries are Layer 3 plan-local progress
labels, not governed `cluster_ownership_map.toml` cells.
`expected_open_cell_count: 0` refers to the existing Layer 2 cluster-map/open-cell
model that G0 does not mutate. Layer 3 progress is measured by discovery/search
readiness, adapter-admission registry coverage, and the five health ledgers.

## Intro

G0 freezes the Layer 3 discipline that every later grounding slice must consume:

```text
search discovers -> adapters discipline -> authority gate admits
```

The old G0 shaped the pre-adapter inventory. The new G0 shapes the discovery
substrate itself. It inventories capability sources and data assets, triages
conceptual legacy, derives ports from the cluster map, freezes adapter admission
records, and also defines:

- discovery postures: `discoverable`, `executable`, `admitted_authority`;
- replayable search-frontier ledgers for authority-relevant search;
- known-groundable recall seeds and index-freshness gates;
- no-hardcode-enumeration lint and hardcode strangle backlog;
- free-growth fixtures that prove new resources become discoverable after index
  refresh without code changes;
- five governed health metrics, including search-recall@known-seeds +
  index-staleness.

G0 does not integrate engines into `pdc`, does not admit any adapter, does not
promote any adapter, does not claim grounded conversion, and does not rewrite
large legacy packages. It builds the gate that prevents later slices from
claiming universality through bespoke wiring.

## Closure Contract

Source of truth: roadmap G0 closure contract in
`docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER3_GROUNDING_SUBORDINATION_IMPLEMENTATION_PLAN.md`.

G0 must deliver thirteen closure artifact families:

1. **Capability & Data Inventory** for source packages, production/corpus assets,
   indexes, registries, and processing transforms.
2. **`CapabilityTriageRecord` + `QuarantineRegistry`** for conceptual legacy and
   wrap-then-strangle targets.
3. **`Port` contract** derived from the cluster-map `publishes`/`consumes` graph.
4. **`AdapterAdmissionRecord`** with zero admitted adapters at G0.
5. **`DataAssetPort`** for existing processed data, distinct from acquisition,
   with `SourceContract` readiness refs but no grounded G1 authority claim.
6. **Conformance-harness skeleton** extending `validate_adapter_preservation` and
   `AdapterLossBlocker`.
7. **Discovery/search discipline**: discovery posture contract,
   `GroundingSearchLedger` contract, absence/incompleteness semantics,
   known-groundable recall seeds, and index-freshness policy.
8. **Five health-metric ledgers**: envelope-expansion-rate,
   adapter-semantic-loss, governance-throughput, demand-pull-vs-abstention,
   search-recall@known-seeds + index-staleness.
9. **Import-firewall lint**: `pdc` cannot import subordinate capability sources;
   only `runtime/quality` adapters may touch them.
10. **Constitution -> ADR promotion** covering §5 organizing rules, §7
    ports/adapters/registry/conformance, Rule 12/T7, and the amendment impact
    notes required by the constitution, with human-principal acceptance or an
    explicit blocked status.
11. **Empty-port map** for proving-ground blockers, ranked by binding constraint.
12. **Adapter-cost map** sequencing near-typed vs raw vs conceptual-legacy sources.
13. **First validation case** pinned to UA-MSME for narrow validation only, never
    as mechanism scope.

Done when the thirteen artifact families are produced by a read-only builder,
persisted in architecture/docs artifacts, validated against runtime recomputation,
and surfaced for audit; all G1+ hardcoded-enumeration paths are either blocked or
registered in the strangle backlog; known-groundable seed recall and index
freshness are governed; the ADR status is accepted or explicitly human-blocked;
and no adapter is admitted before G1+.

## Scope Boundaries

In scope:

- Update the existing G0 contract/producer/validator to the new discovery-search
  discipline.
- Reuse current G0 code only where it satisfies the new Rule 12/T7 requirements.
- Derive ports from the existing cluster map instead of inventing a parallel
  ontology.
- Register source touchpoints and adapter candidates in `shadow`/pre-admission
  form only.
- Record data assets, indexes, method registries, agent/tool registries, and
  processing transforms as discoverable resources with freshness/replay metadata.
- Record `SourceContract` readiness refs for existing processed data assets
  without admitting those refs as grounded authority.
- Define known-groundable seed fixtures and free-growth fixtures for G1/G2/G3/GL.
- Enforce no-hardcode-enumeration lint for search/adapter paths.
- Produce an accepted ADR for the amended Layer 3 discipline. `Accepted` is a
  human-governance gate: the slice may draft the ADR and validator, but it may
  not self-certify acceptance without a human-principal acceptance ref.

Out of scope:

- No G1+ search adapter implementation and no grounded/admitted G1
  `SourceContract`, `ForecastSupport`, legal authority, or proof-carrying
  analytics binding. G0 may register `SourceContract` readiness refs for
  existing data assets, but those refs are candidate/readiness metadata only.
- No promoted adapter, no `governed_promoted` output, and no grounded conversion
  claim.
- No new non-waist `pdc` imports. For G0, the only external `polisyos.*` root
  currently allowed in `pdc` is `polisyos.core` because `core` is shared
  primitive/DTO infrastructure, not a capability-source package. Every other
  immediate `src/polisyos/*` root is blocked unless a later accepted ADR changes
  the waist.
- No mutation of production datasets or hidden sealed corpus fixtures.
- No deep full-data hashing or eager loading of heavy production data. G0 uses
  manifest-backed and index-backed checks.
- No cleanup refactor of large legacy packages.
- No fallback on hardcoded construct/method/data lists to preserve old G0
  behavior. Breakage after deleting a fallback is a search/discovery work item.

## Pattern Pass

| Pattern | G0 risk | Closure move |
| --- | --- | --- |
| P01 contract-only capability | Discovery/search contracts exist as docs but no producer, persisted artifacts, validator, or consumer gate. | One strict model module, read-only builders, persisted artifacts, readiness validator, audit surface, and negative tests. |
| P02 thin orchestration | Search/index artifacts coexist with G1+ but no later slice is forced to consume them. | G0 emits a reusable G1+ dependency contract and validator summary; later G1+ validators must consume that contract before claiming closure. |
| P03 hidden internal richness | Inventory, search-frontier, and recall results are internal JSON only. | Register EXPERT/MACHINE surfaces and docs/reference audit entries for all G0 artifact families. |
| P04 status lattice gap | `discoverable`, `executable`, and `admitted_authority` become a parallel status system. | Define composition with adapter maturity, grounding disposition, promotion state, and capability reality labels; test mixed states. |
| P05 authority boundary leak | Search hits, no-hits, tool choices, or projection statuses are treated as authority. | Every search ledger declares `authoritative_for=[]` and `may_not_use_for` until an adapter and admission gate validate a port. |
| P06 shim drift | Scenario-family and other compatibility paths remain untriaged. | Required quarantine/strangle entries for scenario-family authority and other known shims; blocked admission until disposition exists. |
| P07 rule replay gap | Search results cannot replay after index refresh or corpus growth. | Store rule version, corpus/index snapshot refs, ranking policy refs, and deterministic replay keys for every G0 search artifact. |
| P08 time-role conflation | Data freshness, index freshness, observation time, and replay time collapse. | Separate data coverage/freshness refs from index freshness, generated_at, rule_version, and replay snapshot refs. |
| P09 warning lifecycle gap | Stale index or low recall is a warning while abstention still succeeds. | Missing recall/freshness blocks no-hit abstention and domain-ceiling claims. |
| P10 semantic adequacy gap | Validator checks only schema/file presence, not content-level search adequacy. | Add negatives for no-ledger abstention, stale index, seed recall miss, hardcoded enumeration, and status-lattice bypass. |
| P12 producer handshake gap | Data, legal, scholar, Foundry, and agent registries use incompatible discovery semantics. | Shared `ResourceDiscoveryRecord` and `GroundingSearchLedger` shape across all search families. |
| P13 governance gravity | G0 tries to build a universal search engine or rewrite all registries. | Freeze contracts, ledgers, fixtures, and gates only; G1+ builds concrete engines. |
| P14 evidence independence inflation | Multiple data/index hits from the same lineage count as independent capability. | G0 records lineage/effective independence fields but grants no evidence-strength upgrade. |
| P15 LLM speculation laundering | Agent/tool search or LLM-generated acquisition ideas become authority. | Tool/agent discovery remains candidate-only; no admission without adapter conformance. |
| P25 search-control laundering | Search frontier, no-hit, or best-so-far result is projected as exhaustive or authoritative. | Persist replayable frontier, cutoff, selected/rejected candidates, incompleteness, and no-hit reason; keep frontier separate from producer evidence. |
| T7 false abstention | Bad recall or stale indexes produce "honest" abstention and fake domain ceiling. | Known-groundable seed recall and index-freshness gates; domain ceiling blocked while search ceiling is unresolved. |

## Capability Transition

| Capability | Start label | Pattern pressure | Target label after G0 |
| --- | --- | --- | --- |
| Layer 3 G0 readiness gate | `contract_only`, `artifact_missing`, `verification_missing`, `surface_missing`, `semantic_test_missing` | P01/P03/P10 | Implemented gate for G0 itself: typed contracts, producer, persisted artifacts, validator, audit surface, and negative tests. |
| Discovery/search discipline | `contract_only`, `producer_missing`, `verification_missing`, `semantic_test_missing` | P01/P10/P25/T7 | Implemented as a shared contract and validator gate: discovery posture, search ledger, recall/freshness policy, absence semantics, and fixtures. |
| Existing runtime/quality source touchpoints | `implemented_but_not_orchestrated`, `bridge_missing` | P02/P12 | Registered as source touchpoints with pre-admission status; quarantine always blocks admission, and any future admission requires adapter conformance. |
| Hardcoded capability enumerations | `verification_missing`, `consumer_missing` | P06/P10/P13/P25 | Marked in a strangle backlog with owner, target discovery path, deletion condition, and no fallback. |
| Scenario-family authority selector | `artifact_missing`, `verification_missing`, `consumer_missing` | P05/P06/P15 | Quarantined and enforced as adapter-admission and import-firewall blocker. |
| Foundry/manual method fallback lists | `implemented_but_not_orchestrated`, `verification_missing` | P06/P13/P25 | Registered as hardcode debt; G0 does not repair Foundry, but blocks treating fallback-resolved methods as free-growth evidence. |
| Data/corpus assets and processing transforms | `artifact_missing`, `verification_missing`, `surface_missing` | P08/P10/P14/T7 | Inventory entries plus `DataAssetPort` records, discovery-index refs, freshness refs, recall seed coverage, and validator coverage. |
| Search-recall and index-freshness health | `producer_missing`, `artifact_missing`, `verification_missing` | P10/P25/T7 | Implemented at gate level with known-groundable seeds, index refresh receipts, and stale-index/false-abstention negatives. |

## Code-Grounded Reality

### Existing Substrates To Reuse

- Existing G0 module and validator:
  `src/polisyos/runtime/quality/layer3_grounding_inventory.py`,
  `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py`,
  and `tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py`.
  These are a green v1 readiness gate, not a stub. The current gate already
  recomputes and persists 12 closure artifacts, 25 source packages, 129 data
  assets, 10 processing transforms, 22 runtime-quality touchpoints, 23 adapter
  candidates, 0 admitted adapters, 27 cluster-derived ports, 9 source-truth
  adapter paths, 6 data-asset ports, 4 health ledgers, and 0 non-waist `pdc`
  imports. Treat this as preservation substrate: v2 must keep these guarantees
  while adding discovery/search, recall/freshness, source-contract readiness,
  free-growth, and engineering-quality gates.
- `adapter_contracts.py` already provides `AdapterContractRegistry`,
  `AdapterLossBlocker`, and `validate_adapter_preservation`. Reuse it as the
  conformance-preservation substrate, not as the raw discovery/source registry.
- `capability_ratchet.py` and its validator already provide capability reality
  labels, issue-code style, and report validation shape.
- `cluster_ownership_map.toml` already provides port names plus
  `publishes`/`consumes` edges.
- Fabric SourceContract v2 is already a strong production substrate:
  `source_contract.py` provides source identity, schema, semantics, access,
  security, quality, SLA, terms, replay, lineage, trust, retention, and
  deprecation fields. The existing fail-closed Fabric gate covers 20
  production-visible connectors, 20 SourceContracts, 20 replay fixtures, and 0
  conformance errors. G0 should reference this readiness rather than fork a
  parallel data-source contract.
- Fabric discovery intelligence is already explainable, reversible,
  stale-aware, SourceContract-bound, and benchmarked for dataset discovery. Use
  it as the pattern/substrate for data-source recall and index-freshness checks,
  while keeping the new Layer 3 `GroundingSearchLedger` as the cross-family
  control-plane contract.
- `production_data/manifest.json` plus nested production manifests provide the
  data inventory backbone. G0 must stay manifest/index backed and avoid loading
  heavy data files.
- Existing persisted v1 artifact names are load-bearing and validator-wired:
  `layer3_g0_readiness_manifest.json`,
  `layer3_g0_capability_data_inventory.json`, `layer3_g0_triage_registry.json`,
  `layer3_g0_port_map.json`, `layer3_adapter_admission_registry.json`,
  `layer3_data_asset_ports.json`, `layer3_conformance_harness.json`,
  `layer3_health_metric_ledgers.toml`, `layer3_import_firewall_lint.json`,
  `layer3_empty_port_map.json`, `layer3_adapter_cost_map.json`, and
  `layer3_first_vertical_case.json`. v2 should migrate these paths deliberately
  and add new discovery/search artifacts; do not silently introduce parallel
  names.
- `tests/fixtures/layer3/g0/` already contains malformed old-G0 fixtures. Keep
  useful fixtures, but add search-ledger, recall, freshness, free-growth, and
  no-hardcode negatives.
- `SearchLedger` exists in `polisyos.pdc` for Layer 2 design search. Reuse its
  replay discipline conceptually, but do not reuse it as authority grounding
  evidence without a Layer 3 `GroundingSearchLedger` contract.

### Code-Grounded Risks To Not Underestimate

- This is a v1 -> v2 schema migration, not a documentation-only change. Update
  the constants, bundle models, artifact path constants, artifact
  writer/loader, manifest summary, stable issue-code dictionary, fixture
  loaders, and repository validator together.
- Preserve the existing v1 regression value. Tests that prove strict Pydantic
  shape, quarantine dominance, zero adapter admission, exact port derivation,
  source-truth lattice non-mutation, manifest-backed data inventory, AST
  touchpoint scanning, status composition, ADR human acceptance, and first-case
  identity should remain as regression tests while v2 tests are added.
- `build_data_asset_inventory` is already production-manifest backed, but some
  fixture/docs roots are enumerated directly. That is acceptable only as bounded
  fixture/docs work; production/corpus growth must remain manifest- or
  index-backed with an explicit scaling/perf check.
- Hardcode strangle is not a one-line lint. Existing construct/scenario-family
  mappings are embedded in compiler/resolver behavior and tests; G0 should
  register backlog/deletion conditions first and avoid breaking governed
  vocabularies or compatibility tests without a replacement discovery path.
- ADR-0175 is already accepted for the v1 pre-adapter discipline. The v2
  Rule 12/T7/search-recall expansion needs an amendment, re-acceptance, or
  supplemental human-principal acceptance ref; it should not erase the v1 ADR
  history.

### Existing Substrates To Strangle

- `capability_index_compiler.KNOWN_CONSTRUCTS`,
  `capability_resolution.REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS`,
  `capability_resolver` pinned fixtures, and any manual Foundry-method or
  direct-import fallback list are not rescue paths. They are backlog entries with
  deletion conditions.
- The current old G0 constants for four health metrics, first-vertical construct
  bundles, and pinned-case-only closure are obsolete. UA-MSME remains only a
  validation case, not mechanism scope.
- Any path that says "no grounding found" without a replayable frontier,
  known-groundable recall signal, and fresh index is not honest abstention; it is
  search ceiling.

### Current Facts To Recompute, Not Hand Maintain

The old plan carried fixed counts for package roots, runtime touchpoints,
adapter paths, production bundles, and fixtures. New G0 must recompute those
counts from the repository and persisted manifests. A count may be asserted only
as a validator summary derived from the builder, not as hand-maintained plan
truth.

## Reuse Map

| Existing substrate | New G0 responsibility |
| --- | --- |
| `layer3_grounding_inventory.py` | Rewrite/extend strict models and builders for discovery posture, search ledgers, recall/freshness, no-hardcode lint, and five health metrics. |
| `check_policy_design_case_layer3_g0_readiness.py` | Validate persisted artifacts against runtime recomputation and new Rule 12/T7 gates. |
| `test_layer3_g0_grounding_inventory.py` | Preserve v1 regression tests and add v2 search-discipline, source-contract-readiness, free-growth, and false-abstention negatives; replace only obsolete four-metric/pinned-only expectations. |
| `adapter_contracts.py` | Reference conformance/loss-blocking substrate; do not use it as a discovery registry. |
| `capability_ratchet.py` | Reuse missing-state labels and validation/report idioms. |
| `cluster_ownership_map.toml` | Derive ports and portless open questions. |
| `production_data/**` manifests | Build data/index inventory and freshness receipts without deep eager scans. |
| `foundry` method registry and agent/tool registries | Register as discovery sources; no manual fallback list may count as free-growth. |
| `tests/fixtures/layer3/g0/` | Add malformed and positive fixtures for search ledger, recall seeds, stale indexes, hardcode lint, and free-growth. |
| ADR tooling | Promote the amended constitution/G0 discipline through ADR-0175 or the next available ADR. |

## Implementation Design

Update `src/polisyos/runtime/quality/layer3_grounding_inventory.py` as the single
G0 contract/producer module. Keep it read-only. It may import public
narrow-waist DTOs such as `polisyos.pdc.Layer2ReadinessModel` and standard
library/TOML/JSON readers, but it must not import private `pdc._impl` modules or
subordinate engine packages. It should inspect files, manifests, registries, and
architecture artifacts as data.

Keep the module internal to the validator by default. Export public symbols only
if the public-surface contract and generated references are updated in the same
slice.

### Engineering Bar

G0 is a read-only inventory/search-discipline gate, but it still obeys the
master-plan engineering doctrine. Use structured parsers and the repo's standard
stack rather than ad-hoc text parsing: strict Pydantic contracts
(`extra="forbid"`), TOML/JSON readers, manifest-backed data access, existing
index metadata, deterministic ordering, and fail-closed validation. Heavy
production payloads must stay referenced through manifests, snapshots, or index
refs; no eager full-corpus loads and no unbounded O(n) payload scans.

The task implementation must name the libraries/parsers/indexes it uses and add
a bounded scaling/perf check proving the builder and validator stay manifest- or
index-backed as corpus size grows.

### Required Model Families

- `CapabilityInventoryEntry`: package/root id, kind, path, owner evidence,
  source refs, current capability label, and current imports.
- `DataAssetInventoryEntry`: asset id, data kind, path, manifest refs, lineage
  refs, rights refs, freshness refs, fitness refs, contamination refs, and index
  participation.
- `ProcessingTransformInventoryEntry`: transform id, source root, output refs,
  transform script refs, replay command refs, and contamination risk refs.
- `DiscoveryIndexInventoryEntry`: index id, source family, index kind
  (`structured`, `text`, `vector`, `graph`, `registry`), backing path/service,
  corpus snapshot ref, schema version, index version, freshness ref, owner, and
  rebuild command.
- `ResourceDiscoveryRecord`: resource id, resource kind (`dataset`, `claim`,
  `legal_norm`, `method`, `agent`, `tool`, `adapter`, `case`, `probe`),
  discovery posture (`discoverable`, `executable`, `admitted_authority`),
  index refs, executable interface refs, authority boundary, and missing labels.
- `GroundingSearchLedger`: ledger id, typed request ref, normalized query refs,
  searched index refs and versions, ranking policy ref, selected candidate refs,
  rejected candidate refs, cutoff/budget refs, absence or incompleteness reason,
  deterministic replay key, and explicit `authoritative_for=[]` until adapter
  admission.
- `SearchRecallSeed`: seed id, target resource ref, expected query shape,
  required index refs, expected minimum discovery posture, refresh requirement,
  and failure issue code.
- `IndexFreshnessRecord`: index id, corpus snapshot ref, last refresh ref,
  expected freshness window, staleness status, and blocked authority effects.
- `HardcodeEnumerationBacklogEntry`: file/path/pattern, enumeration kind
  (`construct`, `dataset`, `variable`, `method`, `agent`, `tool`, `source`),
  governed-vocabulary exception flag, target discovery path, owner, deletion
  condition, and fallback-forbidden flag.
- `NoHardcodeEnumerationLintReport`: scanned paths, violations, governed
  vocabulary exceptions, and fail/pass status.
- `FreeGrowthFixture`: resource kind, fixture mutation, index refresh command,
  expected discovery query, expected posture, expected executable/use path, and
  no-code-change assertion. G0 may validate the use path with tiny fixtures or a
  later-slice contract stub; it must not grant authority.
- `MechanismGeneralityFixture`: fixture id, search mechanism id, at least two
  distinct request shapes, expected resources, expected postures, expected
  executable/use paths, and no-code-change assertion proving the mechanism is not
  a pinned-case route.
- `CapabilityTriageRecord`: capability id, disposition, rationale, evidence refs,
  missing capability labels, quarantine ref, and adapter admissibility.
- `QuarantineRegistryEntry`: target id, target kind, reason, pattern ids,
  blocker codes, enforcement surface, release condition.
- `Port`: id, cluster, facet, publishes, consumes, source refs.
- `PortlessCapabilityOpenQuestion`: capability id, missing-port rationale,
  why existing ports cannot express it, proposed waist-change question, owner,
  evidence refs, and status.
- `SourceTouchpointRegistration`: touchpoint id, file, line, import root,
  source module, registration status, optional existing source-truth adapter path,
  quarantine check result, and `admission_allowed`.
- `AdapterAdmissionRecord`: adapter id, source ids, port ids, maturity, promotion
  state, conformance status, quarantine check, admitted flag, adapter contract path
  refs, and source touchpoint refs.
- `DataAssetPort`: asset id, data kind, path, optional `source_contract_ref`,
  required `source_contract_readiness`, lineage ref, rights ref, freshness ref,
  fitness ref, contamination check ref, index refs, and port ids. Readiness is
  an explicit state, not an authority claim: production data should point to a
  Fabric SourceContract/readiness report where available; fixture/docs assets
  may use an explicit `fixture_or_docs_readiness_ref`; missing classification is
  a failure.
- `ConformanceHarnessRecord`: harness id, existing source-truth adapter path refs,
  `AdapterLossBlocker` refs, status, and negative fixtures.
- `HealthMetricLedger`: metric id, owner, freeze value, trend vocabulary,
  denominator/numerator or event fields, update rule, and per-slice delta rule.
  Must include all five metrics.
- `StatusCompositionRule`: rule id, inputs, composed result, issue code, and
  negative fixture ref for quarantine, conformance, maturity, discovery posture,
  search ceiling, and promotion composition.
- `EmptyPortMapEntry`: port id, proving-ground case id, blocker cause,
  binding-constraint rank (`substrate`, `causal_support`, `calibration`),
  search-ceiling status, and next adapter dependency.
- `AdapterCostMapEntry`: source id, port id, near-typed/raw/conceptual-legacy
  classification, existing contract refs, adapter effort tier, semantic-loss
  risk, discovery-readiness risk, and sequencing priority.
- `EngineeringQualityCheck`: named libraries/parsers/indexes, scan strategy,
  bounded-work proof, scaling/perf check ref, deterministic ordering ref, and
  fail-closed error-handling policy.
- `Layer3G0ReadinessManifest`: paths to all artifact families, counts, rule
  version, schema version, ADR ref, first validation case id, runtime builder
  hash, engineering-quality check summary, downstream G1+ dependency
  requirements, and validator summary.

### Producer Functions

- `build_capability_inventory(repo_root: Path) -> CapabilityDataInventory`
  scans immediate `src/polisyos/*` packages and required data/corpus roots.
- `build_discovery_index_inventory(repo_root: Path) -> DiscoveryIndexInventory`
  discovers structured/text/vector/graph/registry indexes and records snapshot,
  version, freshness, owner, and rebuild refs.
- `build_data_asset_inventory(repo_root: Path) -> DataAssetInventory` enumerates
  discovered data assets and processing transforms under required roots. It must
  read production manifests first and perform only lightweight drift checks.
- `build_resource_discovery_records(repo_root: Path) -> ResourceDiscoveryInventory`
  emits `discoverable`/`executable` candidate records for datasets, claims, legal
  facts, methods, agents/tools, probes, and adapters without granting authority.
- `build_grounding_search_contracts(repo_root: Path) -> GroundingSearchDiscipline`
  emits ledger schema, absence semantics, recall seed set, index freshness policy,
  and free-growth fixtures.
- `build_engineering_quality_check(repo_root: Path) -> EngineeringQualityCheck`
  records the structured parsers, indexes, bounded scan strategy, deterministic
  ordering, fail-closed policy, and scaling/perf probe used by the G0 builder and
  validator.
- `build_hardcode_enumeration_backlog(repo_root: Path) -> HardcodeEnumerationBacklog`
  scans search/adapter routes for capability-gating enumerations and separates
  governed vocabularies from defects.
- `build_no_hardcode_lint_report(repo_root: Path) -> NoHardcodeEnumerationLintReport`
  fails on unregistered capability-gating lists in adapter/search code.
- `build_port_map_from_cluster_map(cluster_map_path: Path) -> PortMap` derives
  ports from the cluster map and records portless capability open questions.
- `build_runtime_quality_touchpoint_inventory(repo_root: Path) -> list[SourceTouchpointRegistration]`
  AST-scans top-level and local `runtime/quality` imports from subordinate
  packages and attaches pre-admission registration.
- `build_adapter_admission_records(repo_root: Path) -> AdapterAdmissionRegistry`
  emits zero admitted adapters at G0 and blocks all quarantined or unregistered
  touchpoints.
- `build_health_metric_ledgers(repo_root: Path) -> HealthMetricLedgerBundle`
  freezes all five metrics, including recall/freshness.
- `build_layer3_g0_bundle(repo_root: Path) -> Layer3G0Bundle` composes the above.
- `validate_layer3_g0_bundle(repo_root: Path, persisted: Layer3G0Bundle) -> ValidationReport`
  recomputes runtime output, compares it to persisted artifacts, and emits stable
  issue codes.

### Content Validation Rules

Validation must be content-based, not file-presence-based:

- A search no-hit cannot support `grounded_abstention`, search-ceiling, or
  domain-ceiling claims unless a `GroundingSearchLedger` exists and recall/freshness
  gates are satisfied for the declared envelope.
- A domain-ceiling claim fails if any required known-groundable seed is missed or
  any required index is stale.
- A discovered resource at `discoverable` or `executable` cannot fill an authority
  slot or adapter admission record.
- `admitted_authority` is invalid at G0 because no adapter conformance has run.
- A hardcoded capability enumeration outside governed vocabulary exceptions fails.
- A free-growth fixture fails if a correctly-added resource requires a code change
  to become discoverable, executable, or usable through the declared path after
  index refresh.
- A mechanism-generality fixture fails if the same search mechanism cannot handle
  at least two distinct request shapes without pinned-case code.
- Data asset records fail if lineage, rights, freshness, fitness, contamination,
  `SourceContract`/readiness classification, index participation, or replay refs
  are missing. Production data without a SourceContract readiness ref is a
  blocker; fixture/docs data without an explicit fixture/docs readiness ref is a
  blocker.
- Status composition must prove discovery posture, adapter maturity, promotion
  state, quarantine, and capability reality labels do not drift into parallel
  systems.
- The readiness manifest must expose downstream G1+ dependency requirements:
  required G0 artifact refs, validator command, rule version, and
  blocked-if-missing issue codes. G0 does not execute G1+ closure, but it must
  leave the dependency contract machine-readable.
- Quarantine dominates adapter admission.
- Search frontier evidence is control-plane evidence and must carry
  `may_not_use_for` authority limitations.
- G0 builder and validator fail if they depend on eager heavy-corpus loads,
  unbounded O(n) scans over production payloads, hand-rolled parsing where a
  structured parser exists, nondeterministic output ordering, or silent broad
  exception handling.

## Closure Metrics

The validator must emit these derived metrics. Exact counts are recomputed from
the tree and manifests during execution, not trusted from the plan:

- `capability_inventory_entry_count >= 1`.
- `data_asset_inventory_entry_count >= 1`.
- `discovery_index_inventory_entry_count >= 1`.
- `resource_discovery_record_count >= 1`.
- `grounding_search_ledger_contract_count == 1`.
- `search_recall_seed_count >= 1`.
- `index_freshness_policy_count == 1`.
- `free_growth_fixture_count >= 4` covering metric-binding, claim, method, and
  agent/tool or legal threshold.
- `mechanism_generality_fixture_count >= 1`, with one mechanism covering at least
  two distinct request shapes.
- `data_asset_source_contract_readiness_coverage == 1.0`, meaning every
  `DataAssetPort` has an explicit readiness classification; this does not mean
  every fixture/docs asset must have a production Fabric SourceContract.
- `hardcode_enumeration_backlog_count >= 1` until the strangle backlog is empty.
- `no_hardcode_lint_status == "pass"`.
- `engineering_quality_check_status == "pass"`.
- `g1_dependency_requirements_status == "pass"`.
- `health_metric_ledger_count == 5`.
- `admitted_adapter_count == 0`.
- `source_truth_adapter_path_count` equals the current source-truth lattice count.
- `pdc_non_waist_import_count == 0`.
- `port_count` equals the current cluster-map port count.
- `search_ceiling_blocks_domain_ceiling == true`.
- `first_validation_case_id == "ua-msme-affordable-loans-2022"`.
- `first_validation_case_role == "validation_only_not_mechanism_scope"`.

## Contract Dictionary

- `LAYER3_G0_SCHEMA_VERSION =
  "policyos.policy_design_case.layer3_g0_discovery_search.v2"`.
- `LAYER3_G0_RULE_VERSION =
  "policyos.layer3.g0.discovery_search_free_growth.v2"`.
- `LAYER3_G0_MANIFEST_ID = "layer3.g0.discovery_search_readiness"`.
- `DiscoveryPosture = Literal["discoverable", "executable", "admitted_authority"]`.
- `SearchCompletenessStatus = Literal["complete_with_candidates",
  "complete_no_candidate", "incomplete_budget_cutoff",
  "incomplete_index_unavailable", "incomplete_alias_gap",
  "incomplete_schema_mismatch", "stale_index", "recall_failed"]`.
- `CeilingDiagnosis = Literal["none", "domain_ceiling", "search_ceiling",
  "adapter_missing", "governance_blocked"]`.
- `HealthMetricId = Literal["envelope-expansion-rate",
  "adapter-semantic-loss", "governance-throughput",
  "demand-pull-vs-abstention", "search-recall@known-seeds+index-staleness"]`.
- `CapabilityDisposition = Literal["integrate_as_is",
  "integrate_after_refactor", "wrap_then_strangle", "quarantine"]`.
- `HardcodeEnumerationKind = Literal["construct", "dataset", "variable",
  "method", "agent", "tool", "source", "governed_vocabulary_exception"]`.
- `NO_ADAPTER_ADMISSION_IN_G0 = true`.
- `NO_HARDCODE_FALLBACKS = true`.
- `SEARCH_FRONTIER_REQUIRED_FOR_ABSTENTION = true`.
- `RECALL_FRESHNESS_REQUIRED_FOR_DOMAIN_CEILING = true`.

## File Map

Modify:

- `policy-engine/docs/plans/active/layer3-slices/G0-capability-data-inventory-triage-discipline-freeze.md`
- `src/polisyos/runtime/quality/layer3_grounding_inventory.py`
- `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py`
- `tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py`
- `tests/repo_quality/tools/test_policy_design_case_layer3_g0_readiness.py`
- `tests/repo_quality/tools/test_policy_design_case_layer3_g0_readiness_cli.py`
- `tests/fixtures/layer3/g0/*.json`
- `docs/reference/policy-design-case-layer3-grounding-inventory.md`
- `architecture/policy_design_case/inventory.json`
- `docs/adr/0175-layer3-grounding-subordination-discipline.md`

Persist or update architecture artifacts:

- `architecture/policy_design_case/layer3_g0_readiness_manifest.json`
- `architecture/policy_design_case/layer3_g0_capability_data_inventory.json`
- `architecture/policy_design_case/layer3_g0_triage_registry.json`
- `architecture/policy_design_case/layer3_g0_port_map.json`
- `architecture/policy_design_case/layer3_adapter_admission_registry.json`
- `architecture/policy_design_case/layer3_data_asset_ports.json`
- `architecture/policy_design_case/layer3_conformance_harness.json`
- `architecture/policy_design_case/layer3_health_metric_ledgers.toml`
- `architecture/policy_design_case/layer3_import_firewall_lint.json`
- `architecture/policy_design_case/layer3_empty_port_map.json`
- `architecture/policy_design_case/layer3_adapter_cost_map.json`
- `architecture/policy_design_case/layer3_first_vertical_case.json`

Add v2 discovery/search artifacts:

- `architecture/policy_design_case/layer3_discovery_search_discipline.json`
- `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json`
- `architecture/policy_design_case/layer3_engineering_quality_check.json`

Modify only if stable public exports are deliberately added:

- `src/polisyos/runtime/quality/__init__.py`
- `docs/reference/public-surface.md`
- `architecture/public_surface/inventory.json`

Do not modify:

- `src/polisyos/pdc/**` unless a failing firewall test proves a narrow-waist
  contract must change and an accepted ADR authorizes it.
- `architecture/production_quality/source_truth_lattice.toml`; G0 references
  existing preservation paths and does not add adapter paths.
- `production_data/**` payload files.
- hidden sealed fixtures.

## Task 1 - Red Tests and Fixtures

Intent: prove the old G0 is insufficient before implementation.

Create or update failing tests:

- `tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py`
  - preserve the existing v1 regression coverage for strict models, quarantine,
    zero admission, exact port derivation, source-truth lattice non-mutation,
    manifest-backed data inventory, AST touchpoint scanning, status composition,
    ADR acceptance, and first-case identity
  - `test_g0_requires_five_health_metrics_including_search_recall`
  - `test_discovery_postures_compose_with_status_lattice`
  - `test_grounding_search_ledger_required_for_no_hit_abstention`
  - `test_known_groundable_seed_miss_blocks_domain_ceiling`
  - `test_stale_index_blocks_abstention_and_free_growth`
  - `test_free_growth_fixture_requires_index_refresh_executable_use_and_no_code_change`
  - `test_mechanism_generality_fixture_requires_two_distinct_requests`
  - `test_data_asset_port_requires_source_contract_readiness`
  - `test_engineering_quality_check_blocks_eager_or_unbounded_scans`
  - `test_no_hardcode_enumeration_lint_rejects_capability_lists`
  - `test_governed_vocabulary_exception_does_not_fail_lint`
  - `test_discoverable_or_executable_resource_cannot_be_admitted_authority`
  - `test_g0_admits_zero_adapters`
- `tests/fixtures/layer3/g0/`
  - `malformed_search_no_ledger_abstention.json`
  - `malformed_search_seed_recall_miss_domain_ceiling.json`
  - `malformed_index_stale_free_growth.json`
  - `malformed_free_growth_discoverable_but_not_executable.json`
  - `malformed_mechanism_generality_single_request.json`
  - `malformed_data_asset_missing_source_contract_readiness.json`
  - `malformed_engineering_quality_unbounded_scan.json`
  - `malformed_discoverable_resource_admitted_authority.json`
  - `malformed_hardcoded_construct_list_unregistered.json`
  - `valid_discovery_search_minimal_bundle.json`
  - `valid_free_growth_metric_binding_fixture.json`

Expected red state before Task 2:

```text
layer3_g0_schema_version expected ...v2
health_metric_ledger_count expected=5 actual=4
grounding_search_ledger_contract_missing
search_recall_seed_set_missing
index_freshness_policy_missing
no_hardcode_enumeration_lint_missing
free_growth_fixture_missing
mechanism_generality_fixture_missing
data_asset_source_contract_readiness_missing
engineering_quality_check_missing
```

Do not weaken expectations to match the old implementation.

## Task 2 - Contracts, Builder, and Status Composition

Intent: update the G0 module to produce the new artifact families without
building G1+ search engines.

Implementation requirements:

- Update schema/rule constants to v2.
- Add the required model families from the Implementation Design section.
- Add strict Pydantic models with `extra="forbid"` and deterministic ordering.
- Preserve old inventory/triage/data-asset builders only where they still satisfy
  the new model shape.
- Add `GroundingSearchLedger` contract shape; do not execute external retrieval.
- Add `SearchRecallSeed` and `IndexFreshnessRecord` contracts.
- Add `MechanismGeneralityFixture` and `EngineeringQualityCheck` contracts.
- Add `HardcodeEnumerationBacklogEntry` and `NoHardcodeEnumerationLintReport`.
- Add five health metric ledgers.
- Add status-composition rules for:
  - `discoverable` + no adapter -> candidate only;
  - `executable` + no conformance -> candidate only;
  - `admitted_authority` at G0 -> invalid;
  - stale index + no-hit -> search ceiling;
  - recall miss + domain ceiling -> invalid;
  - quarantine + adapter candidate -> blocked.

Expected result:

```text
uv run pytest tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py -q
```

passes unit tests for contracts/builders, except repository-level artifact
comparison tests that require Task 4 persistence.

## Task 3 - No-Hardcode, Free-Growth, Recall, and Freshness Gates

Intent: make Rule 12 executable at G0.

Implement read-only gates:

- No-hardcode enumeration lint:
  - uses a declared scan profile, not an unbounded whole-repo grep;
  - scans search/adapter-relevant paths first:
    `src/polisyos/runtime/quality/*capability*`,
    `src/polisyos/runtime/quality/*resolver*`,
    `src/polisyos/runtime/quality/*registry*`,
    `src/polisyos/runtime/quality/layer3_grounding_inventory.py`,
    `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py`,
    and known Foundry/agent/tool registry fallback paths discovered by the G0
    builder;
  - detects capability-gating lists of constructs, datasets, variables, methods,
    agents/tools, and sources;
  - separates governed vocabularies/status enums/schema versions from capability
    enumerations;
  - requires every violation to appear in the hardcode strangle backlog.
- Free-growth fixture gate:
  - inserts or references synthetic resource fixtures;
  - requires index refresh receipt;
  - proves the resource becomes discoverable, executable, and usable through the
    declared path without code changes;
  - does not grant authority.
- Mechanism-generality fixture gate:
  - uses the same search mechanism for at least two distinct request shapes;
  - fails pinned-case routes that only work for UA-MSME or one known construct;
  - does not require a full G1+ engine implementation.
- Known-groundable recall/freshness gate:
  - defines seed resources known to be groundable in fixture/index scope;
  - reuses existing Fabric discovery benchmark/staleness mechanics for
    SourceContract-bound data-source seeds where applicable;
  - fails if a seed is not returned by the expected search contract;
  - fails if the relevant index freshness record is stale;
  - blocks domain-ceiling claims when recall/freshness is unhealthy.

This task may use tiny fixtures and manifest/index metadata. It must not deep-scan
the full production corpus.

## Task 4 - Persisted Artifacts, Validator, and CLI

Intent: persist the thirteen artifact families and make runtime-vs-manifest drift
fail closed.

Update `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py`
to:

- migrate the existing v1 path constants, artifact writer/loader, artifact
  summary, missing-artifact handling, and `ALL_ISSUE_CODES` dictionary to the
  v2 bundle shape;
- load persisted G0 architecture artifacts using the real current names from the
  File Map plus the new v2 discovery/search artifacts;
- recompute the G0 bundle from the repository;
- compare schema/rule versions, counts, and content hashes;
- enforce all content validation rules;
- emit stable issue codes;
- fail when old v1/four-metric artifacts are present without v2 migration.

Persist architecture artifacts listed in the File Map. Keep artifact contents
bounded; large data stays referenced by manifest/index refs.

Expected command:

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py
```

Expected summary:

```text
layer3_g0_readiness_status=pass
schema_version=policyos.policy_design_case.layer3_g0_discovery_search.v2
health_metric_ledger_count=5
admitted_adapter_count=0
no_hardcode_enumeration_lint_status=pass
search_recall_seed_status=pass
index_freshness_status=pass
free_growth_fixture_status=pass
data_asset_source_contract_readiness_status=pass
mechanism_generality_fixture_status=pass
engineering_quality_check_status=pass
```

## Task 5 - Audit Surface, ADR, and Corpus Route

Intent: make G0 externally inspectable and governance-owned.

Update docs/reference and `architecture/policy_design_case/inventory.json` so
reviewers can inspect:

- discovery/search posture;
- known-groundable recall seeds;
- index freshness policy;
- no-hardcode lint and strangle backlog;
- five health metrics;
- data-asset `SourceContract` readiness;
- engineering-quality check summary;
- zero-admission adapter registry;
- quarantine and portless open questions.

ADR requirements:

- Treat ADR-0175 as the accepted v1 pre-adapter discipline. Record the v2
  discovery/search expansion as an amendment, re-acceptance, or supplemental
  acceptance with its own human-principal acceptance ref.
- Record §5 organizing rules and §7 ports/adapters/registry/conformance as the
  governed Layer 3 discipline.
- Record the amended Rule 12/T7 discovery-search discipline.
- Clarify that `AdapterContractRegistry` is semantic-preservation substrate, not
  the raw discovery/source registry.
- Resolve constitution §8.4 open questions as owned empirical questions, not as
  silent assumptions.
- Include the constitution-required impact note on the status lattice, authority
  boundaries, replay behavior, affected slice plans, health signals, and
  enforcement surfaces.
- Include rule-version refs for replay and migration.
- Record any import-policy mismatch follow-up for `architecture/imports/policy.toml`.
- Include human-principal acceptance ref or keep G0 blocked.

Corpus route:

- Keep W12D useful-design semantics unchanged.
- Add or update a G0 pre-adapter/readiness block that says G0 is not a grounded
  conversion slice.
- Ensure no no-hit/domain-ceiling summary can appear before G1+ search adapter
  execution and G0 recall/freshness readiness.

## Task 6 - Regression Snapshots and Public Surface

Intent: refresh generated surfaces only where G0 changed the public/audit contract.

Run targeted docs/surface checks after Task 5. Update public-surface snapshots
only if stable runtime exports are added. Otherwise keep G0 internals consumed
through the validator and architecture artifacts.

Suggested commands:

```bash
cd policy-engine
uv run python tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py
uv run pytest tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_layer3_g0_readiness.py tests/repo_quality/tools/test_policy_design_case_layer3_g0_readiness_cli.py -q
```

Extend the existing repo-quality G0 readiness and CLI tests rather than adding a
parallel test family with a different name.

## Task 7 - Full Gate Done When

Intent: prove G0 closure end-to-end and leave G1 with no ambiguity.

Run:

```bash
cd policy-engine
uv run pytest tests/unit/runtime/quality/test_layer3_g0_grounding_inventory.py -q
uv run python tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py
```

Optional broader check if the local environment is already bootstrapped:

```bash
cd policy-engine
python3 -m tools.cli workspace verify --backend-only
```

Done when:

- G0 builder produces all thirteen artifact families.
- Validator recomputes the bundle and exits 0.
- Five health ledgers exist and are governed.
- Search-frontier ledger contract exists and blocks no-ledger abstention.
- Known-groundable recall/freshness gates pass.
- Free-growth fixtures pass after index refresh and without code changes.
- No-hardcode lint passes, with remaining debt only in the registered strangle
  backlog.
- Hardcode fallback deletion conditions are explicit and no fallback is allowed
  as G1+ closure path.
- `admitted_adapter_count == 0`.
- `pdc_non_waist_import_count == 0`.
- `discoverable` and `executable` resources remain candidate-only.
- Domain-ceiling claims are blocked unless search ceiling is ruled out.
- ADR is accepted or G0 stays blocked with a human-principal acceptance issue.
- G1 can start only by consuming this discovery/search discipline.

## Commit Sequence

1. `test: add layer3 g0 discovery-search red fixtures`
2. `feat: update layer3 g0 discovery-search contracts`
3. `feat: add layer3 g0 hardcode and recall gates`
4. `feat: persist layer3 g0 readiness artifacts`
5. `docs: update layer3 g0 audit surface and adr`
6. `test: close layer3 g0 discovery-search readiness`

Split commits by task if implementation is large. Do not mix G1 adapter work into
G0 commits.

## Closeout Pattern Check

Before closing G0, re-open
`docs/reference/policy-design-case-failure-patterns.md` and record:

- P01 is closed for the G0 gate itself: contract, producer, persisted artifacts,
  validator, surface, and negative tests exist.
- P02 is partially closed for future G1+ slices: G0 defines the bridge contract,
  but G1+ still must consume it.
- P03 is closed for G0 audit surfaces.
- P04 is closed for discovery posture/status composition.
- P05/P15 are closed at G0 scope: search/LLM/tool outputs cannot grant authority.
- P07/P08 are closed for G0 replay/index/data freshness metadata.
- P09 is closed for stale-index/recall warnings because they block abstention and
  domain-ceiling claims.
- P10 is closed for G0 skeleton level through semantic negatives.
- P13 is watched: G0 must not build a full search engine or parallel capability
  graph.
- P25 is closed at G0 scope: search frontier is replayable and separate from
  producer evidence.
- T7 is explicitly covered: false abstention is distinguished from domain ceiling
  by recall/freshness gates.

If any item is missing, mark the precise missing-state label and do not call G0
implemented.
