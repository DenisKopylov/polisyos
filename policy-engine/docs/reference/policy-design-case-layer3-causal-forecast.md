# Policy Design Case Layer 3 Causal Forecast

Owner: `team-runtime-quality`
Source of truth: `src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py`, `tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py`, and `architecture/policy_design_case/layer3_g2_readiness_manifest.json`

Layer 3 G2 is the causal/forecast search readiness surface for Policy Design Case. It turns canonical L2 SKG search, Foundry method validity, semantic-spine binding, existing S10 `ForecastSupport`, and W12D consumer routing into persisted audit artifacts.

G2 is not recommendation authority. It can expose a bounded forecast tier, uncertainty refs, limitations, denied uses, and handoff refs. It cannot close policy design, grant useful-design credit, publish claims, or turn a raw SKG hit into forecast support without adapter validation and S10 binding.

## Public And Reviewer View

`layer3_g2_causal_forecast_audit_surface` is registered for `PUBLIC`, `REVIEWER`, `EXPERT`, and `MACHINE`.

`PUBLIC/REVIEWER` may see:

- forecast tier, such as `observable_calibrated`;
- `uncertainty_interval_refs`;
- limitation refs and transport caveats;
- `may_not_use_for` denied uses;
- support-only disposition and W12D posture-consumption status.

Raw SKG query ledgers and query traces remain `EXPERT`/`MACHINE` surfaces. They are replay frontiers, not public authority.

## Authority Boundary

The G2 surface carries these denied uses through runtime artifacts and docs:

- `claim_authority`
- `causal_effect_authority_without_adapter_validation`
- `policy_recommendation`
- `closeout_authority`
- `publication_authority`
- `useful_design_credit`
- `production_authority`
- `search_hit_as_authority`

The S10 `ForecastSupport` binding is the only route from G2 search into a visible forecast posture. Search ledgers, Foundry method reports, and transport declarations are supporting evidence until consumed by the S10/W12D bridge.

## Persisted Artifacts

The G2 generated family is `policy-design-case-layer3-g2-causal-forecast-artifacts`. The readiness CLI writes:

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

## Validator

Run the readiness validator from the product root:

```bash
uv run python tools/quality/validation/check_policy_design_case_layer3_g2_readiness.py --repo-root . --write --output-format json
```

Without `--write`, the same validator checks runtime validation, persisted artifacts, manifest/runtime drift, G1 dependency readiness, generated-artifact registration, inventory/docs/public-surface sync, search health, method health, S10 bridge, and W12D route.

## Failure Modes

Stable failure codes include:

- `layer3_g2_g1_dependency_not_ready`
- `layer3_g2_persisted_artifact_missing`
- `layer3_g2_manifest_runtime_drift`
- `layer3_g2_generated_artifacts_family_missing`
- `layer3_g2_inventory_surface_missing`
- `layer3_g2_reference_index_missing`
- `layer3_g2_public_surface_visibility_missing`
- `layer3_g2_adapter_contract_registry_missing`
- `layer3_g2_search_ledger_missing`
- `layer3_g2_skg_query_trace_missing`
- `layer3_g2_method_requirement_missing`
- `layer3_g2_method_validity_missing`
- `layer3_g2_semantic_binding_spine_missing`
- `layer3_g2_s10_consumer_bridge_missing`
- `layer3_g2_w12d_not_routed_closeout`

## Handoff And Replay

G2 handoff refs are readable by G4/G5 as inputs only. They do not promote, convert, or grant useful-design credit.

Replay fields carried across artifacts include:

- `source_contract_ref`
- `method_validity_refs`
- `method_requirement_refs`
- `search_ledger_refs`
- `skg_query_trace_refs`
- `calibration_record_refs`
- `uncertainty_interval_refs`
- `limitation_refs`

The W12D route injects the G2 forecast gate after G1 and before the outcome-corpus summary. A `not_routed` gate cannot pass G2 readiness unless the run is explicitly in a domain-ceiling repair path.
