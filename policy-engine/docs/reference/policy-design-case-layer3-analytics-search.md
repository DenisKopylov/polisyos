# Policy Design Case Layer 3 Analytics Search

Owner: `team-runtime-quality`
Source of truth: `src/polisyos/runtime/quality/proving_ground/proof_carrying_analytics_search.py`, `tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py`, and `architecture/policy_design_case/layer3_g3_readiness_manifest.json`

Evidence basis: source and selected test files cited here were inspected at repository pin
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; this page was read at documentation HEAD
`c35222b3dcf103338175cf300c5fe9487e6416f3`. Tests were inspected as source evidence and not run for
this documentation update. Commands below are procedures, not verification receipts.

Layer 3 G3 is the proof-carrying analytics search readiness surface for Policy
Design Case. It turns the canonical G2 L2/SKG proof-candidate route, indexed IR
analytics catalog search, selected-ref artifact-store indexing, typed
certificate resolution, existing S11 `ProofCarryingAnalyticsRecord` output,
`ir_analytics_bridge` consumption, and W12D routing into persisted audit
artifacts.

G3 is not recommendation, claim, closeout, publication, or useful-design-credit
authority. Search ledgers discover candidates. Certificate resolution validates
typed proof/certificate payloads. Existing S11, claim registry, baseline
comparison, and W12D consumers decide what can be consumed.

## Public And Reviewer View

`layer3_g3_proof_carrying_audit_surface` is registered for `PUBLIC`,
`REVIEWER`, `EXPERT`, and `MACHINE`.

`PUBLIC/REVIEWER` may see:

- proof posture and resolution status;
- limitation refs and blocker summaries;
- `may_not_use_for` denied uses;
- projection-only `certificate_resolution_report_ref`, redacted search frontier
  refs, resolved/blocked counts, and consumer-gate status.

Raw proof payloads, raw CAS manifests, raw query ledgers, and raw IR catalog
rows remain out of PUBLIC and REVIEWER projections. EXPERT and MACHINE surfaces
may consume proof refs, certificate-resolution refs, bridge refs, method
requirement refs, S11 refs, replay/search frontier refs, blocker refs,
limitation refs, and authority boundaries.

## Authority Boundary

The G3 surface carries these denied uses through runtime artifacts and docs:

- `claim_authority`
- `causal_effect_authority_without_adapter_validation`
- `policy_recommendation`
- `closeout_authority`
- `publication_authority`
- `useful_design_credit`
- `production_authority`
- `search_hit_as_certificate`
- `search_frontier_as_proof_authority`

`ProofCarryingAnalyticsRecord` remains the waist artifact. G3 wraps and audits
that existing S11 artifact; it does not create a parallel proof waist.

A readiness result is scoped to G3's declared runtime, persisted-artifact,
consumer, and projection checks. A passing registration or generated artifact
does not establish a functional end-to-end policy design or recommendation/design
authority; read the downstream consumer verdict and missing capability state.

## Persisted Artifacts

The G3 generated family is
`policy-design-case-layer3-g3-analytics-search-artifacts`. The readiness CLI
writes:

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

## Validator

Run the readiness validator from the product root:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g3_readiness.py --repo-root . --write --output-format json
```

Without `--write`, the same validator checks runtime validation, persisted
artifacts, manifest/runtime drift, generated-artifact registration, inventory
and docs sync, adapter registry loader compatibility, health metrics, authority
posture, and public raw-payload redaction.

## Failure Modes

Stable failure codes include:

- `layer3_g3_l2_skg_proof_candidate_binding_missing`
- `layer3_g3_certificate_resolution_missing`
- `layer3_g3_search_hit_laundered_as_certificate`
- `layer3_g3_fixture_certificate_laundered`
- `layer3_g3_unresolved_certificate_binding`
- `layer3_g3_negative_certificate_ignored`
- `layer3_g3_method_requirement_bypass`
- `layer3_g3_proof_carrying_record_missing`
- `layer3_g3_ir_analytics_bridge_missing`
- `layer3_g3_s11_posture_without_s6_s10`
- `layer3_g3_claim_registry_consumer_gate_missing`
- `layer3_g3_baseline_comparison_consumer_gate_missing`
- `layer3_g3_w12d_consumer_gate_missing`
- `layer3_g3_public_raw_proof_leak`
- `layer3_g3_adapter_registry_summary_only`
- `layer3_g3_manifest_runtime_drift`

## Handoff And Replay

G3 handoff refs are readable by later Layer 3 slices as audit inputs only. They
do not promote, convert, or grant useful-design credit.

Replay fields carried across artifacts include:

- `certificate_resolution_report_ref`
- `proof_carrying_analytics_refs`
- `ir_analytics_bridge_refs`
- `method_requirement_refs`
- `s11_predictive_posture_refs`
- `search_ledger_refs`
- `redacted_search_frontier_refs`
- `limitation_refs`
- `may_not_use_for`

The pinned W12D consumer-gate artifact records one full consumer case and no
lightweight posture references: `full_consumer_case_count=1`,
`lightweight_posture_ref_count=0`, `lightweight_case_refs=[]`, and
`lightweight_posture_ref=null`. It therefore does not establish lightweight
S11 posture refs for the remaining corpus cases. The record also has
`predictive_knowledge_ref=null` and
`search_ledger_predictive_knowledge_ref_consumed=false`; this missing
predictive-knowledge consumer input is part of the reported full-route failure.

At the pinned artifact snapshot, `g3_w12d_consumer_gate_status` is `fail`,
`g3_s11_prerequisite_binding_status` is `blocked`, and `g3_conformance_status`
is `fail`. The exact persisted record is
`architecture/policy_design_case/layer3_g3_w12d_consumer_gate.json`; it carries
`layer3_g3_w12d_consumer_gate_missing` and records the missing predictive-
knowledge reference as not consumed. The readiness-test source identifies
the missing W12D consumer gate as the reported failure. Tests and validators
were inspected, not run. This docs update did not regenerate the artifacts;
the persisted status remains historical evidence.
