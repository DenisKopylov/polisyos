# Fabric Best-in-Class Inventory

Freshness: 2026-04-26.
Owner: `@fabric-owners`
Phase: 0 baseline inventory.

This page is generated from `tools/quality/validation/fabric_best_in_class_manifest.json` by `tools/quality/validation/fabric_best_in_class_inventory.py`.

Phase 0 is report-only: `--check` fails only when the committed manifest or report drift from the current repository inventory. It does not fail because a surface is `partial`, `missing`, `accepted_risk`, or `blocked_by_research`.

## Summary

| Metric | Value |
| ------ | ----- |
| Schema version | `fabric.best_in_class_manifest.v1` |
| Generated at | `2026-04-26T00:00:00Z` |
| Surface count | 59 |
| `implemented` | 55 |
| `partial` | 1 |
| `missing` | 0 |
| `not_applicable` | 2 |
| `accepted_risk` | 0 |
| `blocked_by_research` | 1 |
| `source` plane surfaces | 17 |
| `evidence` plane surfaces | 7 |
| `semantics` plane surfaces | 9 |
| `world` plane surfaces | 8 |
| `trust` plane surfaces | 18 |

## Coverage Report

| Coverage Area | Status | Evidence |
| ------------- | ------ | -------- |
| `source_contracts` | `implemented` | status=`implemented`; fabric_registry_contracts=5; legacy_connector_contracts=5; source_contract_v2_contracts=20 |
| `source_platform` | `implemented` | status=`implemented`; source_contract_v2_count=20; source_scorecard_count=20; replay_fixture_count=20 |
| `processing_guarantees` | `implemented` | status=`implemented`; processing_contract_count=20; dedupe_window_count=20; replay_retention_count=20 |
| `source_profiles` | `implemented` | status=`implemented`; profile_count=38; profile_ids=38; tests=1 |
| `replay_fixtures` | `implemented` | status=`implemented`; record_replay_store=true; quarantine_module=true; production_entrypoint_count=11 |
| `quality_contracts` | `implemented` | status=`implemented`; quality_module=true; connector_quality_module_count=7; profile_count=38 |
| `lineage_nodes_edges` | `implemented` | status=`implemented`; lineage_module=true; openlineage_export=true; prov_export=true |
| `temporal_support` | `implemented` | status=`implemented`; world_query=true; snapshot_store=true; runtime_temporal_adapter=true |
| `access_classification` | `implemented` | status=`implemented`; access_control_module=true; column_mask_module=true; pii_stage_module=true |
| `observability_governance` | `implemented` | status=`implemented`; slo_contract=true; connector_governance_metadata=true; quality_evidence=true |
| `decision_data_envelope` | `implemented` | status=`implemented`; decision_data_module=true; trust_envelope_schema=true; coverage_report=true |
| `discovery_intelligence` | `implemented` | status=`implemented`; semantic_catalog=true; source_contract_v2_count=20; eval_case_count=4 |
| `product_api_integration` | `implemented` | status=`implemented`; runtime_endpoints=5; frontend_fixture_count=12; required_frontend_fixture_count=12 |
| `public_facade_exports` | `implemented` | status=`implemented`; export_count=30; exports=30; tests=3 |

## Tests By Plane

| Plane | Tests |
| ----- | ----- |
| Source | `tests/unit/fabric/connectors/test_contract_system.py`, `tests/unit/fabric/connectors/test_protocol_compliance.py`, `tests/unit/fabric/connectors/test_registry.py`, `tests/unit/fabric/connectors/test_source_contract_v2.py`, `tests/unit/fabric/connectors/profiles/test_source_profiles.py`, `tests/unit/fabric/data_plane/test_processing_guarantees.py`, `tests/repo_quality/tools/test_fabric_schema_governance.py`, `tests/repo_quality/tools/test_fabric_source_contracts.py`, +1 more |
| Evidence | `tests/unit/fabric/data_plane/test_record_replay.py`, `tests/unit/fabric/data_plane/test_quarantine.py`, `tests/unit/fabric/data_plane/test_streaming_runtime.py`, `tests/unit/fabric/data_plane/test_processing_guarantees.py`, `tests/unit/fabric/data_plane/test_benchmarks.py`, `tests/unit/fabric/data_plane/test_orchestrator.py`, `tests/unit/fabric/test_ingestion_quarantine.py`, `tests/unit/fabric/test_provenance.py`, +3 more |
| Semantics | `tests/unit/fabric/test_quality_indicators.py`, `tests/unit/fabric/connectors/test_quality_system.py`, `tests/unit/fabric/connectors/test_quality_statistics.py`, `tests/unit/fabric/connectors/test_schema_system.py`, `tests/unit/fabric/connectors/test_source_contract_v2.py`, `tests/unit/fabric/test_discovery_intelligence.py`, `tests/unit/fabric/test_entity_resolution.py`, `tests/repo_quality/tools/test_fabric_schema_governance.py`, +2 more |
| World | `tests/unit/fabric/test_world_time_travel.py`, `tests/unit/fabric/test_world_materialization.py`, `tests/unit/fabric/test_world_branch_governance.py`, `tests/unit/fabric/test_world_temporal_capabilities.py`, `tests/unit/fabric/test_entity_resolution.py`, `tests/unit/fabric/test_world_query_multibackend.py`, `tests/unit/runtime/http/test_temporal_api.py`, `tests/unit/runtime/http/test_temporal_routes.py` |
| Trust | `tests/unit/fabric/test_lineage.py`, `tests/unit/fabric/test_decision_data_envelope.py`, `tests/unit/fabric/test_fabric_observability.py`, `tests/unit/fabric/test_observability_governance_quality_phase4.py`, `tests/unit/fabric/test_provenance.py`, `tests/unit/fabric/test_discovery_intelligence.py`, `tests/unit/fabric/test_entity_resolution.py`, `tests/unit/fabric/test_access_control.py`, +16 more |

## Source Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `source.builtin_source_profiles` | `implemented` | `P1` | Built-in source profile catalog | profile_count=38; profile_ids=38 | - |
| `source.conformance_harness_v2` | `implemented` | `P1` | Connector conformance harness v2 | validator=`validate_source_conformance_v2`; harness=`ConnectorConformanceHarnessV2`; bounded_read_check=true; report_count=20 | - |
| `source.connector_entrypoints` | `implemented` | `P1` | Production connector entry points | entrypoint_group=`polisyos.fabric_connectors`; entrypoint_count=11; entrypoints=11 | - |
| `source.connector_public_exports` | `implemented` | `P1` | Concrete connector public exports | export_count=22; concrete_connector_count=20; concrete_connectors=20 | - |
| `source.connector_sdk_authoring_helpers` | `implemented` | `P1` | Connector SDK authoring helpers | sdk_package=`src/polisyos/fabric/connectors/sdk`; profile_matrix=`build_source_profile_matrix` | - |
| `source.connector_source_modules` | `implemented` | `P2` | Connector source module tree | source_tree=`src/polisyos/fabric/connectors/sources/**`; source_module_count=30; source_modules=30 | - |
| `source.entrypoint_coverage.direct_import_families` | `implemented` | `P2` | Governed production visibility for connector families | entrypoint_count=11; concrete_connector_count=20; governed_component_count=20; internal_support_only_count=9 | - |
| `source.http_runtime_base_contract` | `not_applicable` | `P3` | Shared HTTP runtime as production source | non_connector_exports=2 | - |
| `source.processing_guarantee_contracts` | `implemented` | `P1` | Processing guarantee, dedupe, and replay-retention contracts | processing_contract_count=20; dedupe_window_count=20; replay_retention_count=20; schema=`schemas/fabric/processing_guarantee.schema.json` | - |
| `source.source_contract_v2_platform` | `implemented` | `P1` | SourceContract v2 production source platform | schema=`schemas/fabric/source_contract.schema.json`; snapshot=`schemas/snapshots/fabric/source_contracts_v2.json`; source_contract_v2_count=20; source_contract_v2_ids=20 | - |
| `source_contracts.eurostat.data.generic` | `implemented` | `P1` | Source contract: eurostat.data.generic | contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json`; contract_id=`eurostat.data.generic`; connector_id=`eurostat.data`; dataset_id=`*` | - |
| `source_contracts.fabric_registry_snapshot` | `implemented` | `P1` | Fabric connector contract registry snapshot | contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json`; contract_count=5; contract_ids=5 | - |
| `source_contracts.legacy_connector_snapshot` | `implemented` | `P2` | Legacy connector contract snapshot | contract_snapshot=`schemas/snapshots/connectors/contracts.json`; contract_count=5; contract_ids=5 | - |
| `source_contracts.sdmx.generic` | `implemented` | `P1` | Source contract: sdmx.generic | contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json`; contract_id=`sdmx.generic`; connector_id=`sdmx.source`; dataset_id=`*` | - |
| `source_contracts.ukons.datasets.generic` | `implemented` | `P1` | Source contract: ukons.datasets.generic | contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json`; contract_id=`ukons.datasets.generic`; connector_id=`ukons.datasets`; dataset_id=`*` | - |
| `source_contracts.worldbank.wdi.generic` | `implemented` | `P1` | Source contract: worldbank.wdi.generic | contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json`; contract_id=`worldbank.wdi.generic`; connector_id=`worldbank.wdi`; dataset_id=`*` | - |
| `source_contracts.wvs.wave7.generic` | `implemented` | `P1` | Source contract: wvs.wave7.generic | contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json`; contract_id=`wvs.wave7.generic`; connector_id=`wvs.wave7`; dataset_id=`*` | - |

## Evidence Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `evidence.cas_evidence_bundle` | `implemented` | `P2` | CAS-backed evidence bundle persistence | evidence_module=true; provenance_bundle_tests=true | - |
| `evidence.distributed_execution_trust_gate` | `implemented` | `P1` | Distributed execution trust gate | trust_contract=true; fail_closed_gate=true | - |
| `evidence.fabric_scale_benchmark_suite` | `implemented` | `P2` | Scale benchmark reports for ingestion, streaming, materialization, and query | latency_quantiles=true; correctness_counters=true; query_benchmark=true | - |
| `evidence.production_source_replay_fixtures` | `implemented` | `P1` | Production source replay fixture matrix | production_entrypoint_count=11; contract_snapshot_count=5; source_contract_v2_count=20; replay_fixture_count=20 | - |
| `evidence.quarantine_replay_surface` | `implemented` | `P1` | Quarantine/DLQ replay surface | quarantine_module=true; quarantine_tests=true | - |
| `evidence.record_replay_store` | `implemented` | `P1` | Record/replay persistence surface | replay_store=true; record_replay_tests=true | - |
| `evidence.streaming_scale_semantics` | `implemented` | `P1` | Streaming, CDC, backpressure, and out-of-order semantics | processing_artifact_metadata=true; out_of_order_policy=true; cdc_compatibility=true; backpressure_contract=true | - |

## Semantics Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `semantics.connector_quality_validators` | `implemented` | `P1` | Connector-level quality validators | quality_module_count=7; quality_modules=7 | - |
| `semantics.fabric_quality_governance_evidence` | `implemented` | `P1` | Fabric quality evidence propagation | quality_evidence_builder=true; scientist_state_key=true | - |
| `semantics.nl_to_dataset_resolution_eval` | `implemented` | `P1` | Explainable NL-to-dataset resolution and eval pack | eval_case_count=4; maximum_false_positive_failures=0; llm_calls=0 | - |
| `semantics.quality_indicators` | `implemented` | `P1` | Metric-level quality indicators | quality_module=true; fitness_report_module=true; quality_tests=3 | - |
| `semantics.schema_governance_snapshot_gate` | `implemented` | `P1` | Schema governance snapshot gate | validator=`tools/quality/validation/fabric_schema_governance.py`; contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json` | - |
| `semantics.semantic_dataset_catalog` | `implemented` | `P1` | SourceContract-backed semantic dataset catalog | source_contract_v2_count=20; embedding_model=`hashing-bow-dataset-v1`; llm_calls=0; candidate_evidence=true | - |
| `semantics.source_quality_contract_coverage` | `implemented` | `P1` | Quality-contract coverage by source contract/profile | contract_count=5; source_contract_v2_count=20; profile_count=38; quality_validator_module_count=7 | Phase 6: propagate source quality states into decision-data envelopes. |
| `semantics.source_scorecards` | `implemented` | `P1` | Generated source scorecards | schema=`schemas/fabric/source_scorecard.schema.json`; snapshot=`schemas/snapshots/fabric/source_scorecards.json`; scorecard_count=20; required_dimensions=5 | - |
| `semantics.stale_embedding_invalidation` | `implemented` | `P1` | Stale semantic-vector invalidation | mark_stale=true; refresh=true; fingerprint=true; stale_filter=true | - |

## World Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `world.bitemporal_world_query` | `implemented` | `P1` | Bitemporal world-query support | as_of_tx_time=true; as_of_valid_time=true; temporal_tests=6 | - |
| `world.correction_revocation_mutations` | `implemented` | `P1` | Append-only correction and revocation metadata | mutation_enum=true; correction_required_fields=true; revocation_required_fields=true; emitter_support=true | - |
| `world.discovery_graph_reasoning` | `implemented` | `P1` | Discovery graph reasoning helpers | origin_trace=true; source_overlap=true; conflict_neighborhood=true; policy_impact=true | - |
| `world.future_table_snapshot_adapters` | `not_applicable` | `P2` | External table-format adapters excluded from Wave 2 production | adapter_registry_present=true; runtime_rejection_test=true; production_visible=false; strict_wave2_scope=`not_applicable` | - |
| `world.kuzu_temporal_scope_capability` | `partial` | `P2` | Kuzu temporal graph parity marker | temporal_capability=true; partial_scope=true; research_track=true | R3: prove full bitemporal Kuzu traversal semantics before marking implemented. |
| `world.snapshot_branch_surface` | `implemented` | `P1` | Snapshot, branch, merge, governance, and retention surface | create_world_branch=true; merge_world_branch=true; update_world_branch_head=true; delete_world_branch=true | - |
| `world.temporal_graph_reasoning` | `blocked_by_research` | `P2` | Temporal graph reasoning over world snapshots | research_wave=`Wave R / R3 temporal graph semantics` | Wave R R3: define acceptance semantics before implementation. |
| `world.temporal_runtime_adapter` | `implemented` | `P1` | Runtime temporal API adapter | route=true; service=true; supported_tables=true; slow_query_evidence=true | - |

## Trust Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `trust.access_classification` | `implemented` | `P1` | Field-level access classification and masking inventory | access_control_module=true; column_mask_module=true; pii_stage_module=true; source_contract_v2_count=20 | - |
| `trust.connector_governance_metadata` | `implemented` | `P1` | Production connector governance metadata | metadata_validator=true; schema_governance=true; quality_governance=true; sla=true | - |
| `trust.entity_resolution_override_governance` | `implemented` | `P1` | Entity override provenance and merge governance | override_audit_model=true; override_envelope=true; merge_governance_required=true; append_only_index=true | - |
| `trust.fabric_compatibility_bridges` | `implemented` | `P2` | Fabric compatibility bridge governance | bridge_registry=true; sunset_dates=true; migration_issues=true; root_facade_unchanged=true | - |
| `trust.fabric_decision_envelope` | `implemented` | `P1` | Fabric decision envelope | coverage_report=`tools/quality/validation/fabric_decision_data_coverage.json`; required_contracts=9 | - |
| `trust.fabric_decision_reason_codes` | `implemented` | `P2` | Reason codes for decision-bearing unknown states | typed_gap_states=5; naked_decision_values=0 | - |
| `trust.fabric_slo_error_budget_gate` | `implemented` | `P1` | Fabric SLI/SLO and error-budget gate | sli_enum=true; slo_targets=true; error_budget_gate=true; sli_metric=true | - |
| `trust.frontend_fabric_contract_fixtures` | `implemented` | `P1` | Frontend Fabric product contract fixtures | fixture_count=12; required_fixture_count=12; fixtures=12; fabric_decision_data_adapter=true | - |
| `trust.lineage_nodes_edges` | `implemented` | `P1` | Lineage graph nodes, edges, trace, and impact APIs | trace_value_origin=true; trace_column_lineage=true; impact_analysis=true | - |
| `trust.openlineage_export` | `implemented` | `P2` | OpenLineage export | export_openlineage_json=true | - |
| `trust.product_evidence_adapters` | `implemented` | `P2` | Scholar, Lex, and Foundry Fabric evidence adapters | fabric_evidence_path=true; scholar=true; lex=true; foundry_calibration=true | - |
| `trust.prov_export` | `implemented` | `P2` | W3C PROV export | prov_o_export=true; prov_json_export=true | - |
| `trust.public_facade_exports` | `implemented` | `P2` | Stable public facade exports | export_count=30; exports=30 | - |
| `trust.runtime_fabric_product_api` | `implemented` | `P1` | Runtime Fabric product API endpoints | operation_ids=5; route=true; service=true; openapi=true | - |
| `trust.runtime_lineage_adapter` | `implemented` | `P1` | Runtime lineage API adapter | route=true; service=true | - |
| `trust.scientist_fabric_trust_governance` | `implemented` | `P1` | Scientist readiness cap from Fabric trust metadata | pass=true; readiness_cap=true | - |
| `trust.source_contract_access_retention_slo` | `implemented` | `P1` | SourceContract access, retention, owner, reviewer, and SLO metadata | source_contract_v2_count=20; classification_count=20; owner_reviewer_count=20 | - |
| `trust.source_deprecation_sunset_policy` | `implemented` | `P2` | Source deprecation and sunset policy | deprecation_model=true; sunset_doc=true | - |

## Gaps By Phase And Priority

| Priority | Phase | Status | ID | Owner | Follow-up / Risk |
| -------- | ----- | ------ | -- | ----- | ---------------- |
| `P2` | 0 | `blocked_by_research` | `world.temporal_graph_reasoning` | `@fabric-owners` | Wave R R3: define acceptance semantics before implementation. |
| `P2` | 0 | `partial` | `world.kuzu_temporal_scope_capability` | `@fabric-owners` | R3: prove full bitemporal Kuzu traversal semantics before marking implemented. |

## Ratchet Mode

| Stage | Behavior |
| ----- | -------- |
| First PR | Report-only drift check for manifest/report freshness. |
| After Wave 1 hardening | P0/P1 `missing` entries fail CI unless they carry `accepted_risk`. |
| After Phase 6 | Decision-bearing `untraced`, `unknown_quality`, and `non_replayable` statuses require reason codes. |

## Validation

```bash
uv run python tools/quality/validation/fabric_wave2_strict_closure.py --check
uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check
uv run bash tools/quality/validation/run_fabric_best_in_class_inventory.sh
uv run pytest tests/repo_quality/tools/test_fabric_best_in_class_inventory.py -q
```
