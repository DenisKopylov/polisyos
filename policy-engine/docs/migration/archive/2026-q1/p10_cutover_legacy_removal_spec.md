# P10 Cutover & Legacy Removal - Detailed Specification

- Status: Implemented
- Version: 1.0
- Effective phase: P10 (`2026-09-01` -> `2026-09-14`)
- Hard deadline for irreversible legacy removal completion: `2026-09-30`
- Scope: `policy-engine`
- Owners: `team-runtime` (primary), `team-foundry`, `team-scientist`, `team-core`, `team-fabric`, `team-platform-ui`
- Related docs:
  - `p9_runtime_api_frontend_foundation_spec.md`
  - `p8_foundry_data_plane_spec.md`
  - `p7_connector_platform_hardening_spec.md`
  - `p6_plugin_unification_spec.md`
  - `p5_foundry_domain_decoupling_spec.md`
  - `p1_refactor_queue.md`
  - `src/polisyos/runtime/README.md`
  - `src/polisyos/runtime/http/app.py`
  - `src/polisyos/runtime/http/services/run_index.py`
  - `src/polisyos/foundry/execute/api.py`
  - `src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py`
  - `pyproject.toml`

## 1. Context and Problem Statement

P5-P9 delivered architecture decoupling and API-first foundations, but multiple compatibility paths remained intentionally deferred.

Those compatibility windows now have explicit target closure dates:

1. P5 compatibility facades removal target: `2026-06-30`.
2. P6 legacy adapter paths removal target: `2026-06-30`.
3. P7 temporary compatibility wrappers removal target: `2026-06-30`.
4. P8 `data_snapshot_ref -> foundry.state_snapshot` fallback removal deadline: `2026-07-31`.
5. P9 legacy dashboard cutover deadline: `2026-08-31`.

P10 is the consolidation phase that must close these deferred removals and enforce a single canonical runtime path.

Current hard gaps (baseline scan, `2026-02-10`):

| Area                            | Current state                                                                                           | Impact                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Runtime run model               | Runtime API still indexes both core runs and legacy manifests (`legacy_runtime` source)                 | Dual semantics in security, contracts, and client code              |
| Runtime lifecycle API           | `src/polisyos/runtime/api.py` + `src/polisyos/runtime/manifest.py` still exposed via `runtime.__init__` | Legacy write-path remains importable and test fixtures depend on it |
| Runtime API auth policy         | `allow_unscoped_legacy_runs=True` path still present                                                    | Unscoped run access branch remains in tenant enforcement logic      |
| Foundry state-source resolution | `ExecuteRequest` still supports `state_snapshot_ref` and `data_snapshot_ref` compatibility fallback     | Canonical input-binding contract from P8 is not strictly enforced   |
| Foundry compat facades          | `foundry.base`, `foundry.types`, `foundry.domain.*` deprecation facades still active                    | Deprecated imports continue to compile and hide ownership drift     |
| Plugin bootstrap compatibility  | Legacy entry-point bridges for `polisyos.connectors` / `polisyos.methods` are still loaded              | Discovery complexity and deprecation debt remain in runtime paths   |
| Dashboard cutover               | `dashboard.py` is still in tree and documented as demo utility                                          | Direct DB/script path remains an attractive bypass to API contracts |

Observed baseline (`2026-02-10`, local code scan):

1. Legacy usage counters:

   - `legacy_runtime` references in `src/` + `tests/`: `22`
   - `runtime.api` references in `src/` + `tests/`: `10`
   - legacy run adapter references (`load_legacy_run`, `LegacyRunManifest`, adapter module): `12`
   - `allow_unscoped_legacy_runs` references: `10`
   - `dashboard.py` references in key docs/specs: `9`
   - explicit P8 legacy fallback markers in code: `3`
2. Repository runtime artifacts:

   - `runs/*/manifest.json` checked into repo: `26` files (legacy runtime shape)
3. Compatibility surfaces still present:

   - Foundry compat facade files (`foundry.base/types/domain`): `7`
   - legacy entry-point bridge/group references (`polisyos.connectors`, `polisyos.methods`, legacy group flags): `26`
4. Architecture freeze snapshot (`tools/quality/lint/collect_arch_metrics.py`):

   - `package_cycles_count = 0`
   - `import_violations_count = 0`
   - `test_collect_errors_count = 46`
   - `ruff_total_issues = 1281`
   - `stale_sources_missing_paths_count = 40`
5. Freeze compare status against `summary.json`:

   - blocking status: `FAIL`
   - blocking reason: `delta_test_collect_errors = +4` (historical regression)
   - additional non-blocking delta: `delta_ruff_total_issues = +87`

Net effect: the architecture DAG is clean, but canonical runtime behavior is still diluted by compatibility code paths that should have been removed after P5-P9 windows.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Complete runtime cutover to CAS-native core runs only; remove legacy runtime run ingestion from Runtime API.
2. Remove legacy lifecycle runtime surface (`runtime.api` / legacy `RunManifest`) from public runtime package APIs.
3. Enforce `input_bindings_ref` as the only canonical Foundry execute state source in production paths.
4. Remove P5 compatibility facades (`foundry.base`, `foundry.types`, `foundry.domain` mechanism/state re-export shims).
5. Remove P6/P7 legacy entry-point bridges and deprecation adapters (`polisyos.connectors`, `polisyos.methods`, legacy component group path).
6. Finalize P9 dashboard cutover by removing legacy dashboard from runtime critical path and docs.
7. Provide deterministic migration/archive tooling for historical legacy run manifests before removal.
8. Close governance work item(s) for P10 with objective evidence.

### 2.2 Non-Goals (P10)

1. Designing new Runtime write APIs (`POST /runs`, replay execution controls).
2. Product UI SSO/role-based frontend expansion beyond reference shell hardening.
3. Redesigning Foundry simulation economics or mechanism semantics.
4. Large-scale replay/performance optimization stream beyond legacy-path removal.
5. Removing unrelated domain deprecations not tied to P5-P9 closure commitments.

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Runtime run model after P10

1. Runtime API MUST index only CAS-native core runs.
2. `legacy_runs_root` scanning MUST be removed from runtime API services.
3. `legacy_runtime` source kind MUST NOT appear in API responses after cutover.
4. Tenant enforcement MUST deny unscoped runs by design (no compatibility bypass).

### 4.2 Runtime lifecycle contract after P10

1. Public runtime package API MUST NOT expose legacy lifecycle helpers:

   - `start_run`
   - `log_artifact`
   - `append_audit`
   - `update_budget_usage`
   - `finalize_run`
   - `resolve_artifact_path`
2. Legacy manifest model (`runtime.manifest.RunManifest`) MUST NOT be a runtime package dependency for active production flows.
3. Audit assembler MUST operate on core run manifests and trace-derived fallback only.

### 4.3 Foundry execute contract after P10

1. `input_bindings_ref` MUST be the only accepted state source in canonical execute path.
2. Compatibility fallback (`data_snapshot_ref -> foundry.state_snapshot`) MUST be removed.
3. Direct `state_snapshot_ref` bypass path MUST be removed from standard workflow execution path.
4. Scientist `run_simulation` MUST fail fast if `input_bindings_ref` is missing in default workflow.

### 4.4 Discovery/bootstrap contract after P10

1. Canonical entry-point groups MUST be used:

   - `polisyos.fabric_connectors`
   - `polisyos.foundry_methods`
   - other P6 component groups already standardized.
2. Legacy groups MUST be removed from runtime bootstrap:

   - `polisyos.connectors`
   - `polisyos.methods`
   - compatibility `polisyos.components` path where still wired.
3. Runtime bootstrap helpers MUST NOT set `include_legacy_entry_points=True`.

### 4.5 Foundry import-path contract after P10

1. Legacy compatibility facades from P5 MUST be removed or converted to hard errors:

   - `polisyos.foundry.base`
   - `polisyos.foundry.types`
   - `polisyos.foundry.domain.state`
   - `polisyos.foundry.domain.mechanisms.*`
2. Canonical imports MUST target:

   - `polisyos.foundry.contracts.*`
   - `polisyos.foundry.mechanisms.*`

### 4.6 Dashboard contract after P10

1. `dashboard.py` MUST NOT be part of runtime operational guidance.
2. Runtime debugging guidance MUST reference only Runtime API v1 + API-driven UI surfaces.
3. If demo scripts are retained, they MUST live under explicit demo tooling paths and MUST consume Runtime API rather than direct DB reads.

## 5. Detailed Technical Design

### 5.1 Runtime legacy surface removal

Required changes:

1. Remove legacy lifecycle module usage:

   - remove `src/polisyos/runtime/api.py` from package exports and runtime-critical tests.
2. Remove legacy manifest model usage:

   - remove `src/polisyos/runtime/manifest.py` dependencies from runtime HTTP adapters/tests.
3. Update runtime package export map:

   - `src/polisyos/runtime/__init__.py` MUST stop lazy-loading symbols from `runtime.api` and `runtime.manifest`.
4. Remove legacy manifest compatibility detector path where no longer needed:

   - `src/polisyos/core/audit/_manifest_compat.py`
   - corresponding compatibility branch in `src/polisyos/core/audit/_assembler_core.py`.

### 5.2 Runtime HTTP core-only cutover

Required service changes:

1. `src/polisyos/runtime/http/app.py`:

   - remove `legacy_runs_root` and `allow_unscoped_legacy_runs` app configuration knobs.
2. `src/polisyos/runtime/http/dependencies.py`:

   - remove `allow_unscoped_legacy_runs` context flag and compatibility allow-branch.
3. `src/polisyos/runtime/http/services/run_index.py`:

   - remove legacy run indexing and adapter integration.
4. Remove legacy adapter module:

   - `src/polisyos/runtime/http/services/adapters/legacy_runtime.py`.
5. `src/polisyos/core/contracts/runtime.py`:

   - remove `legacy_runtime` from `SourceKind`.
   - remove `legacy_artifact_paths` from canonical run details contracts (or mark non-emitted and deprecated for one patch release at most).

### 5.3 Legacy run data migration/archive

P10 MUST provide a deterministic pre-removal path for existing `runs/<id>/manifest.json` repositories:

1. Add migration inventory CLI (recommended):

   - `tools/ops/runtime/inventory_legacy_runs.py`
2. Inventory output MUST include:

   - `run_id`
   - manifest status
   - artifact count
   - start/finish timestamps
   - parse/shape validity
3. Optional archive CLI (recommended):

   - `tools/ops/runtime/archive_legacy_runs.py`
4. Archive policy:

   - create immutable archive artifact/report before deleting or ignoring legacy run roots.
5. Runtime API MUST NOT depend on archive output for online serving.

### 5.4 Foundry P8 compatibility fallback removal

Required changes:

1. `src/polisyos/foundry/execute/api.py`:

   - remove `data_snapshot_ref` compatibility fallback branch.
   - remove legacy compatibility notes for fallback.
2. `src/polisyos/core/contracts/foundry.py`:

   - tighten `ExecuteRequest` requirements toward binding-driven execution in production.
3. `src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py`:

   - remove state-source fallback order that allows `state_snapshot_ref` or `data_snapshot_ref` without bindings.
4. `src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py`:

   - remove/contain wrapping fallback from `state_snapshot_ref` where incompatible with canonical binding pipeline.

### 5.5 P5/P6/P7 compatibility removals

Required changes:

1. Remove P5 facade modules:

   - `src/polisyos/foundry/base.py`
   - `src/polisyos/foundry/types.py`
   - `src/polisyos/foundry/domain/state.py`
   - `src/polisyos/foundry/domain/mechanisms/__init__.py`
   - `src/polisyos/foundry/domain/mechanisms/fiscal.py`
   - `src/polisyos/foundry/domain/mechanisms/labor.py`
   - `src/polisyos/foundry/domain/mechanisms/treasury.py`
2. Remove legacy connector bootstrap bridge loading:

   - `include_legacy_entry_points=True` paths in connector bootstrap.
3. Remove legacy method bootstrap fallback path:

   - compatibility `bootstrap_registry(...)` fallback usage in runtime execution flow.
4. Remove legacy entry-point declarations from `pyproject.toml`:

   - `[project.entry-points."polisyos.methods"]`
   - `[project.entry-points."polisyos.connectors"]`
5. Keep only canonical component entry-point groups in production bootstrap.

### 5.6 Frontend and OpenAPI contract updates

Required updates:

1. Regenerate OpenAPI schema and typed client after contract narrowing.
2. Update reference shell logic to remove legacy source badges/assumptions.
3. Ensure UI handles core-only runs without legacy fallback states.

### 5.7 Regression-prevention lint gate

Required new lint tool (recommended):

- `tools/quality/lint/lint_legacy_cutover.py`

Minimum checks:

1. No imports from `polisyos.runtime.api` in `src/`.
2. No `legacy_runtime` source kind in `src/polisyos/runtime/http` and core runtime contracts.
3. No `allow_unscoped_legacy_runs` code path in runtime HTTP.
4. No legacy entry-point groups (`polisyos.connectors`, `polisyos.methods`) in `pyproject.toml`.
5. No `foundry.domain` compatibility facade imports in active modules outside explicit migration tooling.
6. No legacy execute fallback markers in Foundry execute path.

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-09-01` -> `2026-09-03`):

   - inventory/archive tooling for legacy runs,
   - contract-impact map and breakage report.
2. `M2` (`2026-09-03` -> `2026-09-07`):

   - runtime core-only cutover (`runtime.http`, contracts, package exports),
   - remove runtime legacy adapters/manifests from runtime path.
3. `M3` (`2026-09-07` -> `2026-09-11`):

   - Foundry execute/source hardening to bindings-only,
   - remove P5/P6/P7 compat facades and legacy bootstrap groups.
4. `M4` (`2026-09-12` -> `2026-09-14`):

   - OpenAPI/client/docs refresh,
   - lint/CI stabilization,
   - governance closure evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: runtime contracts + runtime HTTP core-only indexing + legacy run inventory tooling.
2. `PR-B`: Foundry execute + Scientist simulation path hard cutover to input bindings.
3. `PR-C`: remove Foundry/domain facades + remove legacy entry-point bridges/groups.
4. `PR-D`: docs/OpenAPI/client updates + lint gate + governance/queue closure.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `p1_refactor_queue.md`

   - add and track `Q11` for P10.
   - mark `Q11` as `Done` only after all P10 DoD criteria pass.
2. `p10_cutover_legacy_removal_spec.md`

   - status progression (`Proposed` -> `Implemented`) with implementation evidence section at closure.
3. `README.md`

   - remove references to legacy dashboard/runtime legacy paths in runtime critical-path guidance.
4. `src/polisyos/runtime/README.md`

   - remove lifecycle API as active surface and document core-only runtime path.
5. `pyproject.toml`

   - remove legacy connector/method entry-point groups.

### 7.2 Required verification commands

Architecture/freeze checks:

```bash
python3 tools/quality/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p10_metrics \
  --summary-path .tmp/p10_metrics/summary.json \
  --print-summary

python3 tools/quality/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p10_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p10_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Lint gates:

```bash
python3 tools/quality/lint/lint_imports.py
python3 tools/quality/lint/lint_foundry.py
python3 tools/quality/lint/lint_connectors.py --src-root src/polisyos/fabric/connectors --strict
python3 tools/quality/lint/lint_foundry_data_plane.py
python3 tools/quality/lint/lint_legacy_cutover.py
```

Targeted tests (minimum):

```bash
python3 -m pytest \
  tests/unit/runtime/http/test_runs_api.py \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/runtime/http/test_timeline_api.py \
  tests/unit/runtime/http/test_debug_api.py \
  tests/unit/runtime/http/test_artifact_inspector_api.py \
  tests/unit/foundry/test_execute_input_bindings.py \
  tests/unit/scientist/test_engine_default_workflow_p8.py \
  tests/unit/runtime/test_replay_input_bindings_completeness.py
```

Required new P10 tests (recommended):

```bash
python3 -m pytest \
  tests/unit/runtime/http/test_core_only_runs_api.py \
  tests/unit/runtime/http/test_runtime_api_no_legacy_sources.py \
  tests/unit/foundry/test_execute_requires_input_bindings_ref.py \
  tests/unit/foundry/test_no_compat_facade_imports.py \
  tests/unit/core/components/test_no_legacy_entrypoint_groups.py \
  tests/lint/test_legacy_cutover_lint.py
```

## 8. Acceptance Criteria and DoD

P10 is complete only if all criteria are met:

1. Runtime API serves only core runs; `legacy_runtime` is no longer emitted.
2. Runtime HTTP no longer scans `legacy_runs_root` and has no unscoped-legacy access bypass.
3. Runtime package no longer exports legacy lifecycle helpers from `runtime.api`.
4. Legacy run adapter module and related runtime compatibility code are removed.
5. Foundry execute path rejects missing `input_bindings_ref` in canonical workflow path.
6. `data_snapshot_ref -> foundry.state_snapshot` compatibility fallback is removed.
7. P5 compatibility facades (`foundry.base/types/domain` legacy shims) are removed from active import surface.
8. Legacy plugin entry-point groups (`polisyos.connectors`, `polisyos.methods`) are removed from packaging/bootstrap.
9. Runtime docs and root README no longer reference legacy dashboard as a supported path.
10. Required P10 tests and lint gates pass; freeze checks show no new regressions.

## 9. Risks and Mitigations

| Risk                                                                  | Impact | Mitigation                                                                                        |
| --------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------- |
| Downstream import breakage from hard facade removal                   | High   | Pre-cutover inventory, migration guide, explicit changelog mapping old imports to canonical paths |
| Historical run observability loss after dropping legacy run ingestion | High   | Mandatory inventory/archive tooling and signed archive reports before removal                     |
| Workflow breakage from strict input-bindings requirement              | High   | Stage-gated rollout with dedicated tests for default DAG and replay paths                         |
| Plugin ecosystem breakage from legacy entry-point group removal       | Medium | Provide one release note cycle with explicit canonical group migration examples                   |
| CI instability due broad test fixture rewrites                        | Medium | PR slicing with early fixture migration and temporary compatibility test isolation branch         |

## 10. Post-P10 Follow-Ups (Out of Scope)

1. Add Runtime API write surfaces for controlled replay and orchestration (security-reviewed scope).
2. Promote reference shell into full product UI with identity/session UX.
3. Add schema-aware artifact diff and replay comparison UX in artifact inspector.
4. Expand archival tooling into a dedicated offline legacy-run explorer CLI.

## 11. Baseline Snapshot for P10 Planning (`2026-02-10`)

Reference snapshot captured during P10 planning:

- `package_cycles_count = 0`
- `import_violations_count = 0`
- `test_collect_errors_count = 46`
- `ruff_total_issues = 1281`
- `stale_sources_missing_paths_count = 40`

Freeze compare against historical `summary.json`:

- blocking status: `FAIL`
- reason: `delta_test_collect_errors = +4`
- additional delta: `delta_ruff_total_issues = +87`

Legacy-cutover-specific planning signals:

1. Runtime still contains dual-source run indexing (`core_run` + `legacy_runtime`) and unscoped compatibility logic.
2. Legacy runtime lifecycle API remains importable in tests and package exports.
3. Foundry execute still contains explicit compatibility branch from `data_snapshot_ref` to `foundry.state_snapshot`.
4. Foundry compatibility facades introduced in P5 are still present as deprecation wrappers.
5. Packaging still declares legacy plugin groups (`polisyos.methods`, `polisyos.connectors`) alongside canonical component groups.

## 12. Implementation Evidence (`2026-02-10`)

P10 implementation completed with the following evidence:

1. Runtime API cutover to core-only:

   - `src/polisyos/runtime/http/app.py`
   - `src/polisyos/runtime/http/dependencies.py`
   - `src/polisyos/runtime/http/services/run_index.py`
   - `src/polisyos/core/contracts/runtime.py`
   - removed `src/polisyos/runtime/http/services/adapters/legacy_runtime.py`
2. Runtime public surface narrowed:

   - `src/polisyos/runtime/__init__.py` no longer exports lifecycle helpers / `RunManifest`.
   - `src/polisyos/scientist/governance/preflight.py` removed dependency on runtime package lifecycle export.
3. Audit compatibility path removal:

   - `src/polisyos/core/audit/_assembler_core.py` removed legacy manifest detector branch.
   - removed `src/polisyos/core/audit/_manifest_compat.py`.
4. Foundry execute contract hardened to input bindings only:

   - `src/polisyos/core/contracts/foundry.py` (`ExecuteRequest` requires `input_bindings_ref`).
   - `src/polisyos/foundry/execute/api.py` removed `state_snapshot_ref`/`data_snapshot_ref` fallback path.
   - `src/polisyos/scientist/nodes/builtins/simulate/run_simulation.py` fails fast without `input_bindings_ref`.
   - `src/polisyos/scientist/nodes/builtins/data/build_data_snapshot.py` removed state snapshot wrapping fallback.
5. P5/P6/P7 compatibility removals:

   - removed Foundry facade modules:
     - `src/polisyos/foundry/base.py`
     - `src/polisyos/foundry/types.py`
     - `src/polisyos/foundry/domain/state.py`
     - `src/polisyos/foundry/domain/mechanisms/__init__.py`
     - `src/polisyos/foundry/domain/mechanisms/fiscal.py`
     - `src/polisyos/foundry/domain/mechanisms/labor.py`
     - `src/polisyos/foundry/domain/mechanisms/treasury.py`
   - runtime bootstrap no longer uses legacy connector bridges:
     - `src/polisyos/core/components/bootstrap.py`
     - `src/polisyos/fabric/connectors/_registry_lifecycle.py`
     - `src/polisyos/fabric/connectors/components_bridge.py`
   - removed legacy packaging groups from `pyproject.toml`:
     - `[project.entry-points."polisyos.methods"]`
     - `[project.entry-points."polisyos.connectors"]`
6. Dashboard/docs cutover:

   - removed top-level `dashboard.py`.
   - updated `README.md` and `src/polisyos/runtime/README.md` to API-first/core-only guidance.
   - updated reference shell core-only assumptions:
     - `frontend/runtime-reference-shell/app.js`
     - `frontend/runtime-reference-shell/styles.css`
7. Migration/archive tooling added:

   - `tools/ops/runtime/inventory_legacy_runs.py`
   - `tools/ops/runtime/archive_legacy_runs.py`
8. Regression-prevention gate + tests added:

   - `tools/quality/lint/lint_legacy_cutover.py`
   - `tests/lint/test_legacy_cutover_lint.py`
   - `tests/unit/runtime/http/test_core_only_runs_api.py`
   - `tests/unit/runtime/http/test_runtime_api_no_legacy_sources.py`
   - `tests/unit/foundry/test_execute_requires_input_bindings_ref.py`
   - `tests/unit/foundry/test_no_compat_facade_imports.py`
   - `tests/unit/core/components/test_no_legacy_entrypoint_groups.py`
