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
| Surface count | 43 |
| `implemented` | 38 |
| `partial` | 2 |
| `missing` | 0 |
| `not_applicable` | 1 |
| `accepted_risk` | 1 |
| `blocked_by_research` | 1 |
| `source` plane surfaces | 16 |
| `evidence` plane surfaces | 4 |
| `semantics` plane surfaces | 6 |
| `world` plane surfaces | 5 |
| `trust` plane surfaces | 12 |

## Coverage Report

| Coverage Area | Status | Evidence |
| ------------- | ------ | -------- |
| `source_contracts` | `implemented` | status=`implemented`; fabric_registry_contracts=5; legacy_connector_contracts=5; source_contract_v2_contracts=20 |
| `source_platform` | `implemented` | status=`implemented`; source_contract_v2_count=20; source_scorecard_count=20; replay_fixture_count=0 |
| `source_profiles` | `implemented` | status=`implemented`; profile_count=38; profile_ids=38; tests=1 |
| `replay_fixtures` | `implemented` | status=`implemented`; record_replay_store=true; quarantine_module=true; production_entrypoint_count=11 |
| `quality_contracts` | `implemented` | status=`implemented`; quality_module=true; connector_quality_module_count=7; profile_count=38 |
| `lineage_nodes_edges` | `implemented` | status=`implemented`; lineage_module=true; openlineage_export=true; prov_export=true |
| `temporal_support` | `implemented` | status=`implemented`; world_query=true; snapshot_store=true; runtime_temporal_adapter=true |
| `access_classification` | `partial` | status=`partial`; access_control_module=true; column_mask_module=true; pii_stage_module=true |
| `observability_governance` | `implemented` | status=`implemented`; slo_contract=true; connector_governance_metadata=true; quality_evidence=true |
| `public_facade_exports` | `implemented` | status=`implemented`; export_count=24; exports=24; tests=3 |

## Tests By Plane

| Plane | Tests |
| ----- | ----- |
| Source | `tests/fabric/connectors/test_contract_system.py`, `tests/fabric/connectors/test_protocol_compliance.py`, `tests/fabric/connectors/test_registry.py`, `tests/fabric/connectors/test_source_contract_v2.py`, `tests/fabric/connectors/profiles/test_source_profiles.py`, `tests/tools/test_fabric_schema_governance.py`, `tests/tools/test_fabric_source_contracts.py` |
| Evidence | `tests/fabric/data_plane/test_record_replay.py`, `tests/fabric/data_plane/test_quarantine.py`, `tests/fabric/test_ingestion_quarantine.py`, `tests/fabric/test_provenance.py`, `tests/fabric/connectors/test_source_contract_v2.py`, `tests/tools/test_fabric_source_contracts.py` |
| Semantics | `tests/fabric/test_quality_indicators.py`, `tests/fabric/connectors/test_quality_system.py`, `tests/fabric/connectors/test_quality_statistics.py`, `tests/fabric/connectors/test_schema_system.py`, `tests/fabric/connectors/test_source_contract_v2.py`, `tests/tools/test_fabric_schema_governance.py`, `tests/tools/test_fabric_source_contracts.py` |
| World | `tests/fabric/test_world_time_travel.py`, `tests/fabric/test_world_materialization.py`, `tests/fabric/test_world_query_multibackend.py`, `tests/runtime/http/test_temporal_api.py`, `tests/runtime/http/test_temporal_routes.py` |
| Trust | `tests/fabric/test_lineage.py`, `tests/fabric/test_decision_data_envelope.py`, `tests/fabric/test_fabric_observability.py`, `tests/fabric/test_observability_governance_quality_phase4.py`, `tests/fabric/test_provenance.py`, `tests/fabric/test_access_control.py`, `tests/fabric/test_duckdb_storage_access_control.py`, `tests/fabric/test_world_query_column_masking.py`, +5 more |

## Source Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `source.builtin_source_profiles` | `implemented` | `P1` | Built-in source profile catalog | profile_count=38; profile_ids=38 | - |
| `source.conformance_harness_v2` | `implemented` | `P1` | Connector conformance harness v2 | validator=`validate_source_conformance_v2`; harness=`ConnectorConformanceHarnessV2`; bounded_read_check=true; report_count=20 | - |
| `source.connector_entrypoints` | `implemented` | `P1` | Production connector entry points | entrypoint_group=`polisyos.fabric_connectors`; entrypoint_count=11; entrypoints=11 | - |
| `source.connector_public_exports` | `implemented` | `P1` | Concrete connector public exports | export_count=22; concrete_connector_count=20; concrete_connectors=20 | - |
| `source.connector_sdk_authoring_helpers` | `implemented` | `P1` | Connector SDK authoring helpers | sdk_package=`src/polisyos/fabric/connectors/sdk`; profile_matrix=`build_source_profile_matrix` | - |
| `source.connector_source_modules` | `implemented` | `P2` | Connector source module tree | source_tree=`src/polisyos/fabric/connectors/sources/**`; source_module_count=30; source_modules=30 | - |
| `source.entrypoint_coverage.direct_import_families` | `partial` | `P2` | Entry-point coverage for direct-import connector families | entrypoint_count=11; concrete_connector_count=20; direct_import_family_count=9 | Phase 5: decide which direct-import families require entry-point registration. |
| `source.http_runtime_base_contract` | `not_applicable` | `P3` | Shared HTTP runtime as production source | non_connector_exports=2 | - |
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
| `evidence.production_source_replay_fixtures` | `implemented` | `P1` | Replay fixture or explicit non-replayable matrix | production_entrypoint_count=11; contract_snapshot_count=5; source_contract_v2_count=20; replay_fixture_count=0 | Phase 5: add replay fixtures for sources currently carrying explicit non-replayable reasons. |
| `evidence.quarantine_replay_surface` | `implemented` | `P1` | Quarantine/DLQ replay surface | quarantine_module=true; quarantine_tests=true | - |
| `evidence.record_replay_store` | `implemented` | `P1` | Record/replay persistence surface | replay_store=true; record_replay_tests=true | - |

## Semantics Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `semantics.connector_quality_validators` | `implemented` | `P1` | Connector-level quality validators | quality_module_count=7; quality_modules=7 | - |
| `semantics.fabric_quality_governance_evidence` | `implemented` | `P1` | Fabric quality evidence propagation | quality_evidence_builder=true; scientist_state_key=true | - |
| `semantics.quality_indicators` | `implemented` | `P1` | Metric-level quality indicators | quality_module=true; fitness_report_module=true; quality_tests=3 | - |
| `semantics.schema_governance_snapshot_gate` | `implemented` | `P1` | Schema governance snapshot gate | validator=`tools/quality/validation/fabric_schema_governance.py`; contract_snapshot=`schemas/snapshots/fabric/connector_contract_registry.json` | - |
| `semantics.source_quality_contract_coverage` | `implemented` | `P1` | Quality-contract coverage by source contract/profile | contract_count=5; source_contract_v2_count=20; profile_count=38; quality_validator_module_count=7 | Phase 6: propagate source quality states into decision-data envelopes. |
| `semantics.source_scorecards` | `implemented` | `P1` | Generated source scorecards | schema=`schemas/fabric/source_scorecard.schema.json`; snapshot=`schemas/snapshots/fabric/source_scorecards.json`; scorecard_count=20; required_dimensions=5 | - |

## World Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `world.bitemporal_world_query` | `implemented` | `P1` | Bitemporal world-query support | as_of_tx_time=true; as_of_valid_time=true; temporal_tests=4 | - |
| `world.future_table_snapshot_adapters` | `accepted_risk` | `P2` | Future table-format snapshot adapters | adapter_registry_present=true; runtime_rejection_test=true | accepted risk: External table-format adapters are discoverable for planning, while runtime query/create paths reject unsupported adapters.; review 2026-05-31; expires 2026-07-31 |
| `world.snapshot_branch_surface` | `implemented` | `P1` | Snapshot, branch, merge, and retention surface | create_world_branch=true; merge_world_branch=true; gc_world_snapshots=true | - |
| `world.temporal_graph_reasoning` | `blocked_by_research` | `P2` | Temporal graph reasoning over world snapshots | research_wave=`Wave R / R3 temporal graph semantics` | Wave R R3: define acceptance semantics before implementation. |
| `world.temporal_runtime_adapter` | `implemented` | `P1` | Runtime temporal API adapter | route=true; service=true | - |

## Trust Plane

| ID | Status | Priority | Title | Evidence | Follow-up |
| -- | ------ | -------- | ----- | -------- | --------- |
| `trust.access_classification` | `partial` | `P1` | Access classification and masking inventory | access_control_module=true; column_mask_module=true; pii_stage_module=true; access_tests=3 | Phase 5/6: require contract/profile-level classification coverage for decision-bearing fields. |
| `trust.connector_governance_metadata` | `implemented` | `P1` | Production connector governance metadata | metadata_validator=true; schema_governance=true; quality_governance=true; sla=true | - |
| `trust.fabric_decision_envelope` | `implemented` | `P1` | Fabric decision envelope | coverage_report=`tools/quality/validation/fabric_decision_data_coverage.json`; required_contracts=7 | - |
| `trust.fabric_decision_reason_codes` | `implemented` | `P2` | Reason codes for decision-bearing unknown states | typed_gap_states=5; naked_decision_values=0 | - |
| `trust.fabric_slo_error_budget_gate` | `implemented` | `P1` | Fabric SLI/SLO and error-budget gate | sli_enum=true; slo_targets=true; error_budget_gate=true; sli_metric=true | - |
| `trust.lineage_nodes_edges` | `implemented` | `P1` | Lineage graph nodes, edges, trace, and impact APIs | trace_value_origin=true; trace_column_lineage=true; impact_analysis=true | - |
| `trust.openlineage_export` | `implemented` | `P2` | OpenLineage export | export_openlineage_json=true | - |
| `trust.prov_export` | `implemented` | `P2` | W3C PROV export | prov_o_export=true; prov_json_export=true | - |
| `trust.public_facade_exports` | `implemented` | `P2` | Stable public facade exports | export_count=24; exports=24 | - |
| `trust.runtime_lineage_adapter` | `implemented` | `P1` | Runtime lineage API adapter | route=true; service=true | - |
| `trust.source_contract_access_retention_slo` | `implemented` | `P1` | SourceContract access, retention, owner, reviewer, and SLO metadata | source_contract_v2_count=20; classification_count=20; owner_reviewer_count=20 | - |
| `trust.source_deprecation_sunset_policy` | `implemented` | `P2` | Source deprecation and sunset policy | deprecation_model=true; sunset_doc=true | - |

## Gaps By Phase And Priority

| Priority | Phase | Status | ID | Owner | Follow-up / Risk |
| -------- | ----- | ------ | -- | ----- | ---------------- |
| `P1` | 0 | `partial` | `trust.access_classification` | `@fabric-owners` | Phase 5/6: require contract/profile-level classification coverage for decision-bearing fields. |
| `P2` | 0 | `accepted_risk` | `world.future_table_snapshot_adapters` | `@fabric-owners` | External table-format adapters are discoverable for planning, while runtime query/create paths reject unsupported adapters.; review 2026-05-31; expires 2026-07-31 |
| `P2` | 0 | `blocked_by_research` | `world.temporal_graph_reasoning` | `@fabric-owners` | Wave R R3: define acceptance semantics before implementation. |
| `P2` | 0 | `partial` | `source.entrypoint_coverage.direct_import_families` | `@fabric-owners` | Phase 5: decide which direct-import families require entry-point registration. |

## Ratchet Mode

| Stage | Behavior |
| ----- | -------- |
| First PR | Report-only drift check for manifest/report freshness. |
| After Wave 1 hardening | P0/P1 `missing` entries fail CI unless they carry `accepted_risk`. |
| After Phase 6 | Decision-bearing `untraced`, `unknown_quality`, and `non_replayable` statuses require reason codes. |

## Validation

```bash
uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check
uv run bash tools/quality/validation/run_fabric_best_in_class_inventory.sh
uv run pytest tests/tools/test_fabric_best_in_class_inventory.py -q
```
