# Policy Design Case Layer 3 Grounding Inventory

Owner: `team-runtime-quality`
Review owner: `principal-governance`
Status: `active_pre_adapter_audit_surface`
Schema version: `policyos.policy_design_case.layer3_g0_grounding_inventory.v1`
Rule version: `policyos.layer3.g0.grounding_subordination.v1`

This page is the public audit surface for the Layer 3 G0 grounding inventory.
The producer is `src/polisyos/runtime/quality/layer3_grounding_inventory.py`;
the runtime check is `validate_layer3_g0_bundle(repo_root, persisted)`.

G0 is a pre-adapter discipline. It may inventory current sources, derive ports,
register runtime-quality touchpoints, and fail closed on adapter admission. It
does not authorize grounded conversion, publication, closeout, adapter
promotion, or LLM-derived authority.

## Authority Posture

| Field | G0 posture |
| --- | --- |
| Authoritative for | Pre-adapter inventory, quarantine, port derivation, manifest drift checks, and audit projection of current runtime counts. |
| May not use for | Adapter admission, publication authority, production claim evidence, policy recommendation authority, closeout authority, or useful-design conversion. |
| LLM boundary | LLM output is candidate-only and never authority. G0 records this as `llm_output_candidate_never_authority`. |
| Capability reality | `artifact_missing` until Task 5 persists all closure artifacts and ADR-0175 receives human-principal acceptance. |
| Adapter admission | `admitted_adapter_count == 0` is load-bearing. Any admitted adapter before G1+ is a failure. |
| First vertical posture | `not_attempted_g0_pre_adapter`; no grounded conversion is attempted for `ua-msme-affordable-loans-2022`. |

## Closure Artifacts

The G0 closure family contains twelve artifacts. Task 3 exposes the family and
documents the contract; Task 5 persists the artifacts and the readiness
manifest.

| Artifact | Authority role |
| --- | --- |
| `architecture/policy_design_case/layer3_g0_capability_data_inventory.json` | Capability and data-source inventory snapshot. |
| `architecture/policy_design_case/layer3_g0_triage_registry.json` | Triage dispositions and missing capability labels. |
| `architecture/policy_design_case/layer3_g0_port_map.json` | Derived ports from `cluster_ownership_map.toml`; no new ports are invented. |
| `architecture/policy_design_case/layer3_adapter_admission_registry.json` | Candidate-only adapter records; G0 admits none. |
| `architecture/policy_design_case/layer3_data_asset_ports.json` | Data assets bound to ports with lineage, rights, freshness, fitness, and contamination refs. |
| `architecture/policy_design_case/layer3_conformance_harness.json` | Pre-adapter conformance skeleton and negative fixtures. |
| `architecture/policy_design_case/layer3_health_metric_ledgers.toml` | Four frozen health metric ledgers. |
| `architecture/policy_design_case/layer3_import_firewall_lint.json` | PDC narrow-waist import firewall report. |
| `architecture/policy_design_case/layer3_empty_port_map.json` | Explicit empty-port blockers for first vertical conversion. |
| `architecture/policy_design_case/layer3_adapter_cost_map.json` | Near-typed/raw adapter sequencing costs. |
| `architecture/policy_design_case/layer3_first_vertical_case.json` | Distinct corpus case and construct bundle identifiers. |
| `docs/adr/0175-layer3-grounding-subordination-discipline.md` | Human-governed ADR for the G0 subordination discipline. |

`architecture/policy_design_case/layer3_g0_readiness_manifest.json` is the
readiness manifest. It is generated from the same runtime builder counts but is
not counted as one of the twelve closure artifacts.

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

Live API and dashboard projection are outside Task 3. They are not required for
G0 because the reference page, architecture inventory, runtime validator, and
future persisted artifacts provide the audit surface. If a later slice adds API
or dashboard projection, it must carry the same `authoritative_for` and
`may_not_use_for` boundaries.

## ADR Gate

ADR-0175 is cross-linked at
`docs/adr/0175-layer3-grounding-subordination-discipline.md`. Task 3 must not
mark it accepted. Task 5 must stop for human-principal review and record
`accepted_by`, `accepted_at`, and `acceptance_ref` before the readiness gate can
pass.

ADR-0175 must keep constitution open questions as `tracked_empirically_open`,
record the `policy.toml` versus constitution import-policy conflict, name a
follow-up to narrow the `pdc` allowlist in `policy.toml`, and distinguish the
source-truth preservation registry from the Layer 3 admission registry.

## Pattern Pass

Relevant failure-pattern checks:

| Pattern | G0 closure move |
| --- | --- |
| P01 | Do not call G0 implemented until producer output is persisted and validated. |
| P03 | Expose PUBLIC, REVIEWER, EXPERT, and MACHINE audit surfaces here and in the architecture inventory. |
| P05 | Keep projection, diagnostic, and adapter-admission authority separate. |
| P10 | Require negative semantic tests for portless capability, data evidence, firewall, ADR, and status composition failures. |
| P15 | Keep LLM output candidate-only until producer authority validates it. |
