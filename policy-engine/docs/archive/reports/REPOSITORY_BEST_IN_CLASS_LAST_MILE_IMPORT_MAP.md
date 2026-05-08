# Repository Best-In-Class Last-Mile Import Map

Generated: 2026-05-07

## Purpose

Phase 0.3 freezes the public import compatibility decision before any Wave 2-4 source move starts. Every planned source path has exactly one decision: remove it, move it with a re-export shim, or retain it as a dated exception.

The machine-readable source of truth is `architecture/shims.toml#last_mile_import_compatibility_map`. The caller evidence is `_build/.tmp/last-mile/shim_callers.json`.

## Removal Rule

A shim may be removed only when caller_count is zero or all remaining callers are examples/tests intentionally exercising compatibility.

No package source move in Waves 2-4 starts without this map.

## Summary

- Planned compatibility paths: 60
- Caller observations: 2890
- Zero-caller shims: 0
- Shims with first-party source callers: 37

## Scientist Root Modules

| Source import | Decision | Migration target | Owner | Sunset | Caller count | Test |
|---|---|---|---|---|---:|---|
| `polisyos.scientist.decision_validity` | `moved_with_reexport_shim` | `polisyos.scientist.validation.decision_validity` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.error_semantics` | `moved_with_reexport_shim` | `polisyos.scientist.orchestration.engine.error_semantics` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.evidence_sources` | `moved_with_reexport_shim` | `polisyos.scientist.evidence.sources` | `team-scientist` | `2026-11-30` | 7 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.feedback_utils` | `moved_with_reexport_shim` | `polisyos.scientist.feedback.utils` | `team-scientist` | `2026-11-30` | 6 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.frontier_runtime` | `moved_with_reexport_shim` | `polisyos.scientist.orchestration.engine.frontier_runtime` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.latent_separation` | `moved_with_reexport_shim` | `polisyos.scientist.methods.causal.latent_separation` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.llm_cycle` | `moved_with_reexport_shim` | `polisyos.scientist.orchestration.llm.cycle` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.publisher` | `moved_with_reexport_shim` | `polisyos.scientist.publishing.publisher` | `team-scientist` | `2026-12-31` | 4 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.reliability_scorecard` | `moved_with_reexport_shim` | `polisyos.scientist.validation.reliability_scorecard` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.remediation_status` | `moved_with_reexport_shim` | `polisyos.scientist.governance.remediation_status` | `team-scientist` | `2026-12-31` | 3 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |
| `polisyos.scientist.replay_backend` | `moved_with_reexport_shim` | `polisyos.scientist.replay.backend` | `team-scientist` | `2026-11-30` | 6 | `tests/unit/scientist/methods/test_import_shims.py::test_phase_0_3_planned_scientist_root_module_shims_import` |

## Fabric Shell Packages

| Source import | Decision | Migration target | Owner | Sunset | Caller count | Test |
|---|---|---|---|---|---:|---|
| `polisyos.fabric._connector_bridge` | `moved_with_reexport_shim` | `polisyos.fabric` | `team-fabric` | `2026-12-31` | 7 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric._numeric_parsing` | `moved_with_reexport_shim` | `polisyos.fabric._internal.numeric_parsing` | `team-fabric` | `2026-12-31` | 2 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.compatibility` | `moved_with_reexport_shim` | `polisyos.fabric._internal.compatibility` | `team-fabric` | `2026-12-31` | 7 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.config` | `retained_with_dated_exception` | `polisyos.fabric._internal.config` | `team-fabric` | `2026-12-31` | 2 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.connectors.sdk` | `moved_with_reexport_shim` | `polisyos.fabric.connectors.sdk.scaffold` | `team-fabric` | `2026-12-31` | 24 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.connectors_ingestion` | `moved_with_reexport_shim` | `polisyos.fabric.ingestion.connectors` | `team-fabric` | `2026-12-31` | 2 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.decision_data` | `moved_with_reexport_shim` | `polisyos.fabric.evidence.decision_data` | `team-fabric` | `2026-12-31` | 60 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.evidence` | `retained_with_dated_exception` | `polisyos.fabric.evidence.evidence` | `team-fabric` | `2026-12-31` | 35 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.extensions` | `moved_with_reexport_shim` | `polisyos.fabric.extensions.api` | `team-fabric` | `2026-12-31` | 3 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.fact_writer` | `moved_with_reexport_shim` | `polisyos.fabric.evidence.fact_writer` | `team-fabric` | `2026-12-31` | 6 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.finite` | `moved_with_reexport_shim` | `polisyos.fabric.quality.finite` | `team-fabric` | `2026-12-31` | 2 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.fitness_report` | `moved_with_reexport_shim` | `polisyos.fabric.quality.fitness_report` | `team-fabric` | `2026-12-31` | 8 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.ingestion_providers` | `moved_with_reexport_shim` | `polisyos.fabric.ingestion.providers` | `team-fabric` | `2026-12-31` | 8 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.manifest` | `moved_with_reexport_shim` | `polisyos.fabric.identity.manifest` | `team-fabric` | `2026-12-31` | 4 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.observability` | `retained_with_dated_exception` | `polisyos.fabric.observability` | `team-fabric` | `2026-12-31` | 35 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.processing_guarantees` | `moved_with_reexport_shim` | `polisyos.fabric.quality.processing_guarantees` | `team-fabric` | `2026-12-31` | 43 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.product_integration` | `retained_with_dated_exception` | `polisyos.fabric.product_integration` | `team-fabric` | `2026-12-31` | 19 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.registry` | `moved_with_reexport_shim` | `polisyos.fabric._internal.registry` | `team-fabric` | `2026-12-31` | 2 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.safety` | `moved_with_reexport_shim` | `polisyos.fabric.quality.safety` | `team-fabric` | `2026-12-31` | 27 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.segment_manifest` | `moved_with_reexport_shim` | `polisyos.fabric.identity.segment_manifest` | `team-fabric` | `2026-12-31` | 4 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.tabular` | `moved_with_reexport_shim` | `polisyos.fabric.data_plane.tabular` | `team-fabric` | `2026-12-31` | 12 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.temporal` | `moved_with_reexport_shim` | `polisyos.fabric.data_plane.temporal` | `team-fabric` | `2026-12-31` | 57 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.trust` | `retained_with_dated_exception` | `polisyos.fabric.trust` | `team-fabric` | `2026-12-31` | 11 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.trust_adapter` | `moved_with_reexport_shim` | `polisyos.fabric.trust.adapter` | `team-fabric` | `2026-12-31` | 4 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.fabric.world_query` | `moved_with_reexport_shim` | `polisyos.fabric.world.query` | `team-fabric` | `2026-12-31` | 21 | `tests/unit/fabric/test_root_facade.py::test_fabric_phase_0_3_import_map_declares_shell_group_targets` |

## IR Shell Packages

| Source import | Decision | Migration target | Owner | Sunset | Caller count | Test |
|---|---|---|---|---|---:|---|
| `polisyos.ir._internal` | `retained_with_dated_exception` | `polisyos.ir._internal` | `team-ir` | `2026-12-31` | 87 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir._lazy_facade` | `moved_with_reexport_shim` | `polisyos.ir.api` | `team-ir` | `2026-12-31` | 2 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.canon` | `moved_with_reexport_shim` | `polisyos.ir.model_layer.canon` | `team-ir` | `2026-12-31` | 244 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.citations` | `moved_with_reexport_shim` | `polisyos.ir.loading.citations` | `team-ir` | `2026-12-31` | 49 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.connectors` | `retained_with_dated_exception` | `polisyos.ir.connectors` | `team-ir` | `2026-12-31` | 464 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.fact_log` | `moved_with_reexport_shim` | `polisyos.ir.loading.fact_log` | `team-ir` | `2026-12-31` | 54 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.loaders` | `moved_with_reexport_shim` | `polisyos.ir.loading.loaders` | `team-ir` | `2026-12-31` | 12 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.migration_report` | `moved_with_reexport_shim` | `polisyos.ir.loading.migration_report` | `team-ir` | `2026-12-31` | 2 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.model_spec` | `moved_with_reexport_shim` | `polisyos.ir.model_layer.model_spec` | `team-ir` | `2026-12-31` | 135 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.norm_pack` | `moved_with_reexport_shim` | `polisyos.ir.loading.norm_pack` | `team-ir` | `2026-12-31` | 101 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.portfolio` | `moved_with_reexport_shim` | `polisyos.ir.loading.portfolio` | `team-ir` | `2026-12-31` | 15 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.predicate` | `moved_with_reexport_shim` | `polisyos.ir.model_layer.predicate` | `team-ir` | `2026-12-31` | 7 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.public_surface` | `moved_with_reexport_shim` | `polisyos.ir.registry.public_surface` | `team-ir` | `2026-12-31` | 2 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.queries` | `moved_with_reexport_shim` | `polisyos.ir.model_layer.queries` | `team-ir` | `2026-12-31` | 11 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.references` | `moved_with_reexport_shim` | `polisyos.ir.api` | `team-ir` | `2026-12-31` | 316 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.refs` | `moved_with_reexport_shim` | `polisyos.ir.registry.refs` | `team-ir` | `2026-12-31` | 490 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.registry_fragments` | `moved_with_reexport_shim` | `polisyos.ir.registry.registry_fragments` | `team-ir` | `2026-12-31` | 57 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.schema_catalog` | `moved_with_reexport_shim` | `polisyos.ir.loading.schema_catalog` | `team-ir` | `2026-12-31` | 19 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.schemas` | `moved_with_reexport_shim` | `polisyos.ir.schemas.catalog` | `team-ir` | `2026-12-31` | 20 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.trinity` | `retained_with_dated_exception` | `polisyos.ir.trinity` | `team-ir` | `2026-12-31` | 176 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.types` | `moved_with_reexport_shim` | `polisyos.ir.model_layer.types` | `team-ir` | `2026-12-31` | 164 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |
| `polisyos.ir.units` | `moved_with_reexport_shim` | `polisyos.ir.model_layer.units` | `team-ir` | `2026-12-31` | 4 | `tests/unit/ir/test_root_facade_closeout.py::test_ir_phase_0_3_import_map_declares_shell_group_targets` |

## DDM And Synthetic World

| Source import | Decision | Migration target | Owner | Sunset | Caller count | Test |
|---|---|---|---|---|---:|---|
| `polisyos.ddm_15_7` | `retained_with_dated_exception` | `polisyos.ddm` | `team-architecture` | `2026-07-31` | 2 | `tests/unit/ddm/test_ddm_15_7_shim.py::test_ddm_15_7_root_shim_reexports_canonical_facade_until_july_2026` |
| `polisyos.synthetic_world` | `retained_with_dated_exception` | `polisyos.foundry.agent_sim.world` | `team-foundry` | `2026-07-31` | 2 | `tests/unit/foundry/agent_sim/test_synthetic_world_shim.py::test_synthetic_world_root_shim_reexports_canonical_world_until_july_2026` |

Phase 2.3 keeps both root compatibility imports through the tightened
2026-07-31 sunset. The refreshed caller report shows no first-party source
callers; the remaining callers are repo-quality contract checks and canonical
unit smoke tests that intentionally exercise compatibility.

## Caller Report Contract

Each `_build/.tmp/last-mile/shim_callers.json` row records `importer_path`, `import_kind`, `import_name`, `migration_target`, `caller_role`, and whether the caller is an intentional compatibility exercise. The scanner uses AST import parsing first and a string-literal fallback for dynamic import strings.

Phase 2.3 may remove a shim only when the caller count is zero or all remaining callers are examples/tests intentionally exercising compatibility.

## Contract Touchpoints

- `architecture/shims.toml`: source-of-truth decisions and shim metadata.
- `architecture/name_registry.toml`: Fabric and IR shell-package rename backlog.
- `architecture/public_surface/contract.toml`: compatibility package metadata for `polisyos.ddm_15_7` and `polisyos.synthetic_world`.
- `architecture/imports/contracts.toml`: Wave 2-4 source-move precondition pointer.
