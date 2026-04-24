# P8 Foundry Data-Plane Input Bindings - Detailed Specification

- Status: Implemented
- Version: 1.0
- Effective phase: P8 (`2026-05-11` -> `2026-05-24`)
- Hard deadline for legacy `DataSnapshot -> foundry.state_snapshot` fallback removal: `2026-07-31`
- Scope: `policy-engine`
- Owners: `team-foundry` (primary), `team-scientist`, `team-fabric`, `team-core`
- Related docs:
  - `p7_connector_platform_hardening_spec.md`
  - `p6_plugin_unification_spec.md`
  - `p1_refactor_queue.md`
  - `docs/contracts/E1_5_FOUNDRY_PURE_COMPUTE_SPLIT_COMPILERS.md`
  - `src/polisyos/core/contracts/foundry.py`
  - `src/polisyos/core/contracts/fabric.py`
  - `src/polisyos/foundry/execute/api.py`
  - `src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py`
  - `src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py`
  - `src/polisyos/scientist/workflows/default.py`

## 1. Context and Problem Statement

After P7, connector runtime is hardened, but Foundry still consumes data through a compatibility path where `fabric.data_snapshot` usually wraps `foundry.state_snapshot`.

Current data-plane gaps:

| Area                        | Current state                                                                                                                                     | Impact                                                                              |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Foundry input contract      | `ExecuteRequest.data_snapshot_ref` exists, but execute path requires `DataSnapshot.data_ref.kind == foundry.state_snapshot`                       | Real connector data does not have a first-class binding contract into Foundry state |
| Scientist data binding      | `BuildDataSnapshotNode` mostly passes through existing snapshots; no deterministic tabular-to-state materialization contract                      | Data-plane is not explicit, hard to validate/replay as a separate phase             |
| Fabric port integration     | `FabricPort.snapshot(...)` protocol exists, but no default concrete adapter in `scientist/adapters`                                               | `data_view_request_ref` path is not production-ready                                |
| Pre-expensive quality gates | `QualityGatePass` exists in governance preflight utility, but default workflow path (`run_governance` node) does not execute it before simulation | Low-quality/stale data can reach expensive compile/execute stages                   |
| Replay completeness         | Replay relies on snapshot refs but has no dedicated `input_bindings` artifact role                                                                | Reproducibility metadata is incomplete at data-binding boundary                     |

Net effect: architecture boundaries are cleaner after P7, but the connector/fabric side and Foundry execution side are still coupled by a temporary snapshot compatibility bridge instead of a stable input-binding ABI.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Introduce a stable, typed `foundry.input_bindings` artifact contract as canonical data-plane handoff into Foundry execution.
2. Make `DataSnapshot -> Foundry state` materialization deterministic, auditable, and replay-safe.
3. Add explicit pre-simulation data quality gate behavior in default Scientist workflow.
4. Provide a concrete `FabricPort.snapshot(...)` adapter path for `data_view_request_ref` flows.
5. Keep one-release backward compatibility for legacy `state_snapshot_ref` and `DataSnapshot(data_ref=foundry.state_snapshot)` usage.
6. Extend replay/completeness evidence to include input-binding artifacts.

### 2.2 Non-Goals (P8)

1. Redesign of `GlobalState` economics/mechanism semantics.
2. Full rewrite of Fabric world-store materialization (`fabric.world.materialize.*`).
3. Immediate removal of direct `state_snapshot_ref` execute path.
4. Full convergence of all governance pass wiring (budget/legal/safety) into node-level workflow in this phase.

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Canonical P8 data-plane flow

After P8:

1. Connector/Fabric data is captured as `fabric.data_snapshot`.
2. Scientist builds deterministic `foundry.input_bindings` from snapshot + registry/slot contracts.
3. Binding materialization produces (or references) a deterministic `foundry.state_snapshot`.
4. Foundry execute resolves state through binding artifact (preferred) or legacy snapshot refs (compat).

### 4.2 New artifact contracts (P8)

Required additions in `core/contracts/foundry.py`:

1. `FoundryInputBindingsRef`:

   - `kind="foundry.input_bindings"`
   - `media_type="application/json"`.
2. `FoundryInputBindingReportRef`:

   - `kind="foundry.input_binding_report"`
   - `media_type="application/json"`.
3. `FoundryInputBindings` envelope (minimum fields):

   - `data_snapshot_ref`
   - `registry_bundle_ref`
   - `rules` (binding rules)
   - `bound_state_snapshot_ref`
   - optional `quality_report_ref`
   - `notes`.

Required updates in `core/contracts/fabric.py`:

1. `DataSnapshot` SHOULD support optional `quality_report_ref` (typed or `ArtifactRef`) for deterministic quality-gate input.
2. `DataSnapshot` MAY include optional `input_bindings_ref` link for downstream traceability.

### 4.3 Binding invariants

For each binding rule:

1. `target_slot_id` MUST exist in `SlotRegistry`.
2. If slot has `state_path`, binder MUST verify type/shape compatibility against target state tensor.
3. Transform chain MUST be deterministic and ordered.
4. Missing required source fields MUST fail binding unless explicit non-blocking policy is configured.
5. Rule application order MUST be stable (sorted by `binding_id`).

### 4.4 Execute invariants

`ExecuteRequest` MUST support canonical source resolution order:

1. `state_snapshot_ref` (legacy direct path).
2. `input_bindings_ref` (new canonical path).
3. `data_snapshot_ref` compatibility fallback.

Hard rules:

1. Exactly one effective state source MUST be resolved.
2. `input_bindings_ref` path MUST verify that referenced `data_snapshot_ref` and produced `bound_state_snapshot_ref` are present and readable.
3. `data_snapshot_ref` fallback MUST remain supported through one-release compatibility window and MUST emit compatibility notes.
4. Execute path MUST remain CAS-only (no DB/network).

### 4.5 Scientist workflow invariants

Default workflow (`scientist/workflows/default.py`) after P8 MUST include:

1. `build_data_snapshot` (existing).
2. New `bind_foundry_inputs` node after data snapshot build.
3. New `run_data_plane_gate` node before `compile_foundry` and before `run_simulation`.
4. `run_simulation` MUST consume `input_bindings_ref` (preferred) or legacy refs.

### 4.6 Quality-gate invariants

1. P8 MUST apply quality gate checks before expensive simulation execution.
2. `QualityGatePass` and `PIICheckPass` MUST be executable from node-level workflow state.
3. Strict profile MUST block simulation on quality/freshness blocker conditions.
4. Governance node MAY still run post-simulation for final decision logic.

### 4.7 Replay and decision packet invariants

1. Replay completeness MUST treat `input_bindings_ref` as critical for Foundry/Scientist strategies.
2. Decision packet inputs/artifact references SHOULD include binding artifacts (`input_bindings_ref`, optional `input_binding_report_ref`).
3. Replaying the same binding subgraph MUST produce the same binding artifact ID and same bound snapshot artifact ID.

## 5. Detailed Technical Design

### 5.1 Contract layer updates

Required changes:

1. `src/polisyos/core/contracts/foundry.py`

   - add `FoundryInputBindingsRef`, `FoundryInputBindingReportRef`,
   - add `FoundryInputBindings` (+ supporting models for rules/transforms).
2. `src/polisyos/core/contracts/fabric.py`

   - extend `DataSnapshot` with optional quality/binding refs.
3. `src/polisyos/core/contracts/README.md`

   - document P8 data-plane contract ownership and compatibility window.

Constraints:

1. Existing `ExecuteRequest` fields remain backward compatible.
2. Existing `DataSnapshot.data_ref` field remains supported.

### 5.2 Foundry data-plane module

Required new package:

- `src/polisyos/foundry/data_plane/`

Required responsibilities:

1. deterministic binding plan validation (`rule -> slot` checks),
2. payload extraction from `DataSnapshot.data_ref`,
3. deterministic materialization into `GlobalState`,
4. persistence of `foundry.input_bindings` + optional binding report.

Implementation constraints:

1. no randomization in binding transforms,
2. stable sort/group semantics for tabular data,
3. explicit float handling/canonicalization.

### 5.3 Scientist node changes

Required additions:

1. `src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py`

   - builds/persists `foundry.input_bindings`,
   - materializes `state_snapshot_ref`,
   - emits binding report.
2. `src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py`

   - runs `QualityGatePass`/`PIICheckPass` on snapshot+binding context before simulation.

Required updates:

1. `src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py`

   - prefer `input_bindings_ref` path,
   - keep legacy fallback behavior.
2. `src/polisyos/scientist/workflows/default.py`

   - include new P8 nodes and dependencies.
3. `src/polisyos/scientist/workflows/builder.py`

   - update required input checks/messages to include binding path.

### 5.4 Fabric adapter path for snapshot build

Required addition:

- `src/polisyos/scientist/adapters/fabric_bridge.py`

Responsibilities:

1. implement `FabricPort.snapshot(store, request_ref) -> DataSnapshotRef`,
2. resolve `DataViewRequestRef` via Fabric public APIs/entrypoints,
3. persist `DataSnapshot` with evidence/quality/warnings/PII metadata.

Compatibility requirement:

1. if fabric adapter is absent, node behavior remains deterministic and explicit (`ERROR_FOUNDATION_MISSING` or equivalent fail/skip path).

### 5.5 Foundry execute API integration

Required updates:

1. `src/polisyos/foundry/execute/api.py`

   - support `input_bindings_ref`,
   - resolve bound snapshot through bindings artifact,
   - keep `state_snapshot_ref` and `data_snapshot_ref` fallback behavior.

2. `src/polisyos/core/contracts/foundry.py`

   - extend `ExecuteRequest` with optional `input_bindings_ref`.

### 5.6 ModelSpec consistency checks

Required P8 rule:

1. If `TrinityBundle.model_spec.data_snapshot_ref` is set to non-zero placeholder value, it MUST match the effective `data_snapshot_ref` used by Scientist execution.
2. Zero-hash placeholder (`sha256:000...000`) MAY remain accepted as compatibility default in generation/agent flows.
3. Consistency check SHOULD run in Scientist binding node before compile/execute expensive steps.

### 5.7 Replay/runtime integration

Required updates:

1. `src/polisyos/runtime/replay.py`

   - include `input_bindings_ref` in critical role detection/completeness checks.
2. `src/polisyos/scientist/replay_backend.py`

   - pass binding refs when available for Foundry replay.
3. `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py`

   - include binding refs in packet payload and manifest input refs.

### 5.8 Lint and regression prevention

Required new lint rule:

- `tools/lint/lint_foundry_data_plane.py`

Minimum checks:

1. no new hard-coded assumptions that `DataSnapshot.data_ref.kind == foundry.state_snapshot` outside compatibility boundary modules,
2. default workflow includes P8 binding + pre-simulation data gate nodes,
3. `FabricPort` has at least one concrete adapter implementation in Scientist adapters.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-05-11` -> `2026-05-13`):

   - contract additions (`input_bindings` refs/models),
   - execute API support for `input_bindings_ref`.
2. `M2` (`2026-05-13` -> `2026-05-17`):

   - implement binding node + deterministic materialization module.
3. `M3` (`2026-05-17` -> `2026-05-21`):

   - workflow rewiring + pre-simulation data-plane gate + replay integration.
4. `M4` (`2026-05-22` -> `2026-05-24`):

   - lint/tests/docs/governance closure and freeze evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: contracts + execute API compatibility extensions.
2. `PR-B`: binder module + Scientist binding node.
3. `PR-C`: workflow/data-plane gate + replay/decision-packet integration.
4. `PR-D`: lint/tests/docs and queue/governance updates.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `p1_refactor_queue.md`

   - add/track P8 work item (recommended `Q9`) and closure state.
2. `p8_foundry_data_plane_spec.md`

   - status progression (`Proposed` -> `Implemented`) with evidence section on close.
3. `import_exceptions.toml` / `import_exceptions_registry.md`

   - P8 SHOULD avoid new long-lived architecture exceptions.

### 7.2 Required verification commands

Architecture/freeze checks:

```bash
python3 tools/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p8_metrics \
  --summary-path .tmp/p8_metrics/summary.json \
  --print-summary

python3 tools/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p8_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p8_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

P8 lint checks:

```bash
python3 tools/lint/lint_connectors.py --src-root src/polisyos/fabric/connectors --strict
python3 tools/lint/lint_foundry.py
python3 tools/lint/lint_foundry_data_plane.py
```

Targeted tests (minimum):

```bash
python3 -m pytest \
  tests/contract/test_foundry_facade_contracts.py \
  tests/foundry/test_execute_facade_smoke.py \
  tests/scientist/test_engine_default_workflow_e1_7.py \
  tests/runtime/test_replay_runtime.py
```

Required new P8 tests:

```bash
python3 -m pytest \
  tests/contract/test_foundry_input_bindings_contract.py \
  tests/foundry/test_execute_input_bindings.py \
  tests/scientist/test_bind_foundry_inputs_node.py \
  tests/scientist/test_data_plane_gate_node.py \
  tests/scientist/test_engine_default_workflow_p8.py \
  tests/runtime/test_replay_input_bindings_completeness.py
```

## 8. Acceptance Criteria and DoD

P8 is complete only if all criteria are met:

1. Canonical `foundry.input_bindings` contract is implemented and used in default workflow.
2. For identical `data_snapshot_ref + registry_bundle_ref + rules`, binding artifact IDs are deterministic.
3. Pre-simulation quality gate blocks strict-profile runs on configured blocker conditions.
4. `run_simulation` supports binding-based state resolution while preserving legacy snapshot compatibility.
5. Replay completeness includes binding artifacts and can replay through binding path.
6. Architecture freeze blocking checks remain green with no regressions.

## 9. Risks and Mitigations

| Risk                                                           | Impact | Mitigation                                                                          |
| -------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------- |
| Non-deterministic tabular transforms (ordering/grouping drift) | High   | Stable sort keys, explicit aggregation semantics, deterministic serialization tests |
| Data-schema drift breaks slot mappings                         | High   | Binding validation against slot registry + contract hash checks + blocker mode      |
| Memory pressure during tabular-to-state materialization        | Medium | Chunked materialization strategy and explicit shape limits in binder                |
| Breaking existing snapshot-based tests/flows                   | Medium | Keep one-release fallback path and add compatibility regression suite               |
| Governance gate ambiguity across preflight/node runtime        | Medium | Define P8 node-level gate as canonical pre-simulation blocker for default workflow  |

## 10. Post-P8 Follow-Ups (Out of Scope)

1. Remove legacy `data_snapshot_ref -> foundry.state_snapshot` fallback after compatibility deadline.
2. Expand binding engine to direct world-store projections without intermediate tabular payloads.
3. Unify governance preflight and node-level governance pass execution into one canonical pipeline.
4. Add performance benchmark suite for large-scale binding materialization paths.

## 11. Baseline Snapshot for P8 Planning (`2026-02-10`)

Reference snapshot (fresh local scan):

- `package_cycles_count = 0`
- `import_violations_count = 0`
- `test_collect_errors_count = 42`
- `ruff_total_issues = 1270`
- `stale_sources_missing_paths_count = 40`
- `compare_baseline.py --mode blocking`: `[OK] Architecture freeze checks passed.`

P8-specific baseline observations:

1. `foundry/execute/api.py` resolves `data_snapshot_ref` only through `DataSnapshot.data_ref.kind == "foundry.state_snapshot"` compatibility path.
2. `foundry.state_snapshot` kind assumptions are present in active execution/analysis paths:

   - `src/polisyos/foundry/execute/api.py`
   - `src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py`
   - `src/polisyos/scientist/agent/feasibility.py`
3. Scientist protocol defines `FabricPort.snapshot(...)`, but no concrete adapter implementation exists in `src/polisyos/scientist/adapters`.
4. Default workflow runs simulation after compile + snapshot build, while quality pass wiring is not part of `run_governance` node pre-simulation path.
5. Test suite still encodes compatibility usage broadly (multiple tests construct `DataSnapshot(data_ref=StateSnapshotRef(...))`).

## 12. Implementation Evidence (`2026-02-10`)

Implemented artifacts (P8 scope):

1. Contract layer:

   - `src/polisyos/core/contracts/foundry.py`: added `FoundryInputBindingsRef`, `FoundryInputBindingReportRef`, `FoundryInputBindings`, binding rule/transform models, and `ExecuteRequest.input_bindings_ref`.
   - `src/polisyos/core/contracts/fabric.py`: `DataSnapshot` extended with `quality_report_ref` and `input_bindings_ref`.
   - `src/polisyos/core/contracts/__init__.py` and `src/polisyos/core/contracts/README.md`: exports/docs updated for P8 ownership and compatibility window.
2. Foundry data-plane module:

   - Added `src/polisyos/foundry/data_plane/` with deterministic binding/materialization flow and binding report persistence.
3. Execute API:

   - `src/polisyos/foundry/execute/api.py`: canonical state-source resolution order (`state_snapshot_ref` -> `input_bindings_ref` -> `data_snapshot_ref` fallback), compatibility notes, and input provenance roles.
4. Scientist nodes/workflow:

   - Added `src/polisyos/scientist/nodes/builtins/data/bind_foundry_inputs.py`.
   - Added `src/polisyos/scientist/nodes/builtins/governance/data_plane_gate.py`.
   - Updated default DAG in `src/polisyos/scientist/workflows/default.py` to include `bind_foundry_inputs` and `run_data_plane_gate` before simulation.
   - Updated `run_simulation` to prefer `input_bindings_ref`.
5. Fabric adapter path:

   - Added `src/polisyos/scientist/adapters/fabric_bridge.py` with concrete `FabricPort.snapshot(...)`.
6. Replay/decision packet integration:

   - `src/polisyos/runtime/replay.py`, `src/polisyos/scientist/replay_backend.py`, and `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py` updated for `input_bindings_ref` completeness and manifest propagation.
7. Regression prevention:

   - Added `tools/lint/lint_foundry_data_plane.py`.
   - Updated queue tracking in `p1_refactor_queue.md` (`Q9` closed).
8. P8 tests:

   - Added:
     - `tests/contract/test_foundry_input_bindings_contract.py`
     - `tests/foundry/test_execute_input_bindings.py`
     - `tests/scientist/test_bind_foundry_inputs_node.py`
     - `tests/scientist/test_data_plane_gate_node.py`
     - `tests/scientist/test_engine_default_workflow_p8.py`
     - `tests/runtime/test_replay_input_bindings_completeness.py`
