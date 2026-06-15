# Policy Design Case Layer 3 Grounding Inventory

Owner: `team-runtime-quality`
Source of truth: `src/polisyos/runtime/quality/layer3_grounding_inventory.py`, `tools/quality/validation/check_policy_design_case_layer3_g0_readiness.py`, and `architecture/policy_design_case/layer3_g0_readiness_manifest.json`
Review owner: `principal-governance`
Status: `active_pre_adapter_audit_surface`
Schema version: `policyos.policy_design_case.layer3_g0_discovery_search.v2`
Rule version: `policyos.layer3.g0.discovery_search_free_growth.v2`

This page is the public audit surface for the Layer 3 G0 grounding inventory.
The producer is `src/polisyos/runtime/quality/layer3_grounding_inventory.py`;
the runtime check is `validate_layer3_g0_bundle(repo_root, persisted)`.

G0 is a pre-adapter discipline. It may inventory current sources, derive ports,
register runtime-quality touchpoints, expose discovery/search posture, and fail
closed on adapter admission. It does not authorize grounded conversion,
publication, closeout, adapter promotion, no-hit/domain-ceiling summaries, or
LLM-derived authority.

## Authority Posture

| Field | G0 posture |
| --- | --- |
| Authoritative for | Pre-adapter inventory, quarantine, port derivation, manifest drift checks, discovery/search readiness, recall/freshness readiness, no-hardcode lint, engineering-quality check, and audit projection of current runtime counts. |
| May not use for | Adapter admission, publication authority, production claim evidence, policy recommendation authority, closeout authority, useful-design conversion, no-hit summary, or domain-ceiling claim. |
| LLM boundary | LLM output is candidate-only and never authority. G0 records this as `llm_output_candidate_never_authority`. |
| Capability reality | `implemented` for the G0 readiness gate: runtime producer, persisted artifacts, validator, audit surface, and negative semantic tests exist. G1+ still must consume the discipline before any adapter can claim authority. |
| Adapter admission | `admitted_adapter_count == 0` is load-bearing. Any admitted adapter before G1+ is a failure. |
| First vertical posture | `not_attempted_g0_pre_adapter`; no grounded conversion is attempted for `ua-msme-affordable-loans-2022`. |

## Closure Artifacts

The G0 closure family contains sixteen persisted artifacts. The readiness
manifest is counted as a closure artifact because reviewers must be able to
compare persisted counts against runtime recomputation.

| Artifact | Authority role |
| --- | --- |
| `architecture/policy_design_case/layer3_g0_capability_data_inventory.json` | Capability and data-source inventory snapshot. |
| `architecture/policy_design_case/layer3_g0_triage_registry.json` | Triage dispositions and missing capability labels. |
| `architecture/policy_design_case/layer3_g0_port_map.json` | Derived ports from `cluster_ownership_map.toml`; no new ports are invented. |
| `architecture/policy_design_case/layer3_adapter_admission_registry.json` | Candidate-only adapter records; G0 admits none. |
| `architecture/policy_design_case/layer3_data_asset_ports.json` | Data assets bound to ports with lineage, rights, freshness, fitness, and contamination refs. |
| `architecture/policy_design_case/layer3_conformance_harness.json` | Pre-adapter conformance skeleton and negative fixtures. |
| `architecture/policy_design_case/layer3_health_metric_ledgers.toml` | Five frozen health metric ledgers. |
| `architecture/policy_design_case/layer3_import_firewall_lint.json` | PDC narrow-waist import firewall report. |
| `architecture/policy_design_case/layer3_empty_port_map.json` | Explicit empty-port blockers for first vertical conversion. |
| `architecture/policy_design_case/layer3_adapter_cost_map.json` | Near-typed/raw adapter sequencing costs. |
| `architecture/policy_design_case/layer3_first_vertical_case.json` | Distinct corpus case and construct bundle identifiers. |
| `architecture/policy_design_case/layer3_discovery_search_discipline.json` | Discovery indexes, resource discovery, grounding search ledgers, recall/freshness policy, and no-hardcode lint summary. |
| `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json` | Registered hardcoded-enumeration debt with owners, replacement path, and deletion conditions. |
| `architecture/policy_design_case/layer3_engineering_quality_check.json` | Bounded scan, parser use, and replayability quality check. |
| `architecture/policy_design_case/layer3_g0_readiness_manifest.json` | Runtime/persisted count manifest and content hash. |
| `docs/adr/0175-layer3-grounding-subordination-discipline.md` | Human-governed ADR for the G0 subordination discipline. |

The readiness validator must report `closure_artifact_count=16`,
`persisted_closure_artifact_count=16`, equal runtime/persisted content hashes,
and zero admitted adapters.

## Task 5 Review Surface

Reviewers can inspect the G0 freeze through these named surfaces:

| Review topic | Artifact |
| --- | --- |
| discovery/search posture | `architecture/policy_design_case/layer3_discovery_search_discipline.json` |
| known-groundable recall seeds | `architecture/policy_design_case/layer3_discovery_search_discipline.json` |
| index freshness policy | `architecture/policy_design_case/layer3_discovery_search_discipline.json` |
| no-hardcode lint | `architecture/policy_design_case/layer3_discovery_search_discipline.json` and `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json` |
| strangle backlog | `architecture/policy_design_case/layer3_hardcode_enumeration_backlog.json` |
| five health metrics | `architecture/policy_design_case/layer3_health_metric_ledgers.toml` |
| SourceContract readiness | `architecture/policy_design_case/layer3_data_asset_ports.json` and readiness manifest counts. |
| engineering-quality check | `architecture/policy_design_case/layer3_engineering_quality_check.json` |
| zero-admission adapter registry | `architecture/policy_design_case/layer3_adapter_admission_registry.json` |
| quarantine and portless open questions | `architecture/policy_design_case/layer3_g0_triage_registry.json` and `architecture/policy_design_case/layer3_empty_port_map.json` |

## Touchpoints And Adapter Paths

Raw `SourceTouchpointRegistration` records are shadow registrations discovered
by AST scanning of `src/polisyos/runtime/quality`. They record that runtime
quality imports subordinate source roots such as `lex`, `foundry`, `fabric`,
`scholar`, or `scientist`. A registration is not an adapter contract and cannot
make the imported source authoritative.

Existing source-truth adapter paths come from
`architecture/production_quality/source_truth_lattice.toml`. They are
preservation registry paths, not Layer 3 adapter-admission records. G0 must
observe the existing nine source-truth adapter paths and must not add a new path
to that lattice. The Layer 3 admission registry remains separate and has
`admitted_adapter_count == 0`.

## Health Metrics

| Metric | Freeze value | Trend vocabulary | Owner | Per-slice delta rule |
| --- | --- | --- | --- | --- |
| `envelope-expansion-rate` | `{"g0_admitted_adapter_count": 0}` | `expanding`, `flat`, `shrinking` | `team-runtime-quality` | Later slices may change only after admitted adapter evidence. |
| `adapter-semantic-loss` | `{"semantic_loss_events": 0}` | `clean`, `lossy` | `team-runtime-quality` | Any AdapterLossBlocker event increments lossy evidence. |
| `governance-throughput` | `{"accepted_adr_count": 0, "open_human_gate_count": 1}` | `flowing`, `stalled` | `principal-governance` | Human acceptance gates move throughput only with acceptance refs. |
| `demand-pull-vs-abstention` | `{"grounded_conversion_count": 0}` | `responding`, `abstention_inertia` | `team-runtime-quality` | Demand pull cannot count until a grounded adapter admits evidence. |
| `search-recall@known-seeds+index-staleness` | `{"known_groundable_seed_miss_count": 0, "stale_required_index_count": 0}` | `fresh_recall_ok`, `search_ceiling` | `team-runtime-quality` | Recall misses or stale required indexes block domain-ceiling and no-hit claims. |

## Discovery/Search Discipline

`layer3_discovery_search_discipline.json` records replayable search ledgers,
selected/rejected candidates, cutoff refs, absence semantics, discovery indexes,
known-groundable recall seeds, and index freshness receipts. Search hit, no-hit,
or best-so-far frontier output is candidate/control-plane evidence only:
`authoritative_for=[]` until G1+ wires a semantic-preserving adapter and the
admission gate accepts it for a purpose.

A no-hit cannot support grounded abstention, search ceiling, or domain ceiling
unless the search ledger exists, the known-groundable recall seeds pass, and the
required indexes are fresh. Even with G0 recall/freshness ready, W12D must not
emit a no-hit/domain-ceiling summary before G1+ search adapter execution because
G0 is not a grounded conversion slice.

## Data Inventory Rules

The data inventory is manifest-backed and lightweight. G0 reads committed
manifests and fixture directories as governance inputs; it does not deep-hash
or recursively classify raw heavy data as authority.

Required roots are:

| Root | G0 treatment |
| --- | --- |
| `production_data` | Manifest-backed production-data bundles and split manifests. |
| `tools/ops_runners/ukraine_data` | Runner scripts treated as processing transforms with replay refs. |
| `tests/fixtures/universal-corpus/cases` | Semantic expectations for corpus testing only. |
| `tests/fixtures/universal-corpus/producer_stubs` | Producer-stub fixtures, not production evidence. |
| `tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/layer2-sealed-universality-battery` | Hidden semantic evaluation fixtures, not training or authority data. |
| `docs/research/universal-policy-design/outcome-corpus` | Research corpus material used for governance traceability. |

The universal corpus fixtures are semantic expectations. They may test whether
G0 blocks conversion, but they may not be treated as runtime evidence authority.

## Audience Projection

| Audience | Surface | Scope |
| --- | --- | --- |
| PUBLIC | This reference page and `architecture/policy_design_case/inventory.json`. | Explain G0 posture, artifact family, zero-admission rule, and authority limits. |
| REVIEWER | This page, runtime tests, and repo-quality readiness tests. | Audit issue codes, negative fixtures, and Task 5 gates. |
| EXPERT | Runtime bundle contracts and derived inventories. | Inspect counts, source touchpoints, data roots, port derivation, and firewall semantics. |
| MACHINE | Strict Pydantic DTOs and JSON/TOML closure artifacts. | Replay builder counts, detect drift, and consume machine-readable inventories. |

Live API and dashboard projection are outside G0. They are not required because
the reference page, architecture inventory, runtime validator, persisted
artifacts, ADR, and W12D corpus route provide the audit surface. If a later
slice adds API or dashboard projection, it must carry the same
`authoritative_for` and `may_not_use_for` boundaries.

## ADR Gate

ADR-0175 is cross-linked at
`docs/adr/0175-layer3-grounding-subordination-discipline.md`. ADR-0175 remains
the accepted v1 pre-adapter discipline and now records a v2 discovery/search
amendment with supplemental human-principal acceptance metadata.

ADR-0175 must keep constitution open questions as `tracked_empirically_open`,
record the `policy.toml` versus constitution import-policy conflict, name a
follow-up to narrow the `pdc` allowlist in `policy.toml`, and distinguish the
source-truth preservation registry from the Layer 3 admission registry.
It must also record §5 organizing rules, §7 ports/adapters/registry/conformance,
Rule 12/T7, rule-version refs, and an impact note covering status lattice,
authority boundaries, replay behavior, affected slice plans, health signals, and
enforcement surfaces.

## Corpus Route

W12D useful-design semantics are unchanged. W12D still counts only `pass` and
`publish-with-limitation` outcomes as useful design, and typed blockers,
accepted deficits, corpus stubs, and Layer 3 G0 pre-adapter blocks do not count.

W12D now emits a G0 pre-adapter/readiness block so corpus reports can state that
G0 is not a grounded conversion slice. The route records
`not_attempted_g0_pre_adapter`, `grounded_conversion_count=0`, and
`no_hit_domain_ceiling_summary_allowed_before_g1=false`; no no-hit/domain-ceiling
summary can appear before G1+ search adapter execution and G0 recall/freshness
readiness.

## Pattern Pass

Relevant failure-pattern checks:

| Pattern | G0 closure move |
| --- | --- |
| P01 | Do not call G0 implemented until producer output is persisted and validated. |
| P03 | Expose PUBLIC, REVIEWER, EXPERT, and MACHINE audit surfaces here and in the architecture inventory. |
| P05 | Keep projection, diagnostic, and adapter-admission authority separate. |
| P10 | Require negative semantic tests for portless capability, data evidence, firewall, ADR, and status composition failures. |
| P15 | Keep LLM output candidate-only until producer authority validates it. |
| P25 | Keep replayable search frontier separate from producer evidence and adapter authority. |
| T7 | Distinguish false abstention from domain ceiling with recall/freshness gates. |
