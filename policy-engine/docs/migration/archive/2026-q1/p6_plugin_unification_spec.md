# P6 Plugin Unification - Detailed Specification

- Status: Implemented
- Version: 1.0
- Effective phase: P6 (`2026-04-13` -> `2026-04-26`)
- Hard deadline for legacy bootstrap cutover: `2026-05-31`
- Scope: `policy-engine`
- Owners: `team-core` (primary), `team-fabric`, `team-foundry`, `team-lex`, `team-scientist`, `team-scholar`
- Related docs:
  - `p1_import_policy_v2_spec.md`
  - `p5_foundry_domain_decoupling_spec.md`
  - `p1_refactor_queue.md`
  - `src/polisyos/core/components/README.md`
  - `src/polisyos/core/components/discovery.py`
  - `src/polisyos/fabric/connectors/registry_core_parts.py`
  - `src/polisyos/foundry/methods/components_bridge.py`

## 1. Context and Problem Statement

After P5, import graph and package-cycle closure is complete (`package_cycles_count = 0`), but plugin discovery/registration is still fragmented across multiple stacks.

Current split points:

| Area | Current bootstrap path | Problem |
| --- | --- | --- |
| Fabric connectors | `fabric/connectors/_registry_lifecycle.py` -> `fabric/connectors/discovery.py` (`polisyos.connectors`) | Connectors bypass `core.components`; no shared metadata/compliance flow |
| Foundry methods | `foundry/methods/discovery.py` (`polisyos.methods`) + optional `components_bridge.py` | Two parallel entry models and duplicate bootstrap logic |
| Lex evaluators | `lex/legal_evaluation/evaluator_registry.py` -> per-call `discover_components(...)` | Repeated discovery/index build and local registry-specific flow |
| Scholar/Lex extractors | `fabric/claims/extractor_registry.py` -> per-call `discover_components(...)` | Same duplication pattern as evaluators |
| Norm pack providers | `lex/normpack/provider_registry.py` -> per-call `discover_components(...)` | Same duplication pattern as evaluators |
| Scientist nodes | `scientist/engine/registry.py` discovery path + separate builtin registration in `scientist/workflows/builder.py` | Runtime uses mixed registration models |

Additional inconsistencies:

1. `core.components` has no connector kind/capability.
2. Entry-point namespaces are split (`polisyos.methods` vs `polisyos.foundry_methods`; `polisyos.connectors` outside `core.components`).
3. Discovery happens repeatedly in different runtime entrypoints instead of one canonical pass.

Net effect: plugin onboarding is harder than needed, compliance rules are uneven, and runtime behavior depends on which bootstrap surface was called.

## 2. Goals and Non-Goals

### 2.1 Goals (MUST)

1. Establish `core.components` as the single canonical discovery/indexing layer for connectors, methods, nodes, extractors, and providers.
2. Keep existing domain registries (`ConnectorRegistry`, `MethodRegistry`, `NodeRegistry`, evaluator/extractor/provider registries) as runtime indices, but convert their discovery paths to thin adapters over `core.components`.
3. Add explicit connector support in the component model (kind, capability, compliance rules, discovery group).
4. Ensure one shared component index can bootstrap all plugin registries in one pass.
5. Preserve one-release backward compatibility for legacy entry-point groups and legacy bootstrap APIs with `DeprecationWarning`.

### 2.2 Non-Goals (P6)

1. Full replacement of runtime registries with `ComponentRegistry` at execution-time lookup.
2. Redesign of connector runtime contracts (`FetchRequest`, `FetchResult`, pooling/resilience internals).
3. Redesign of Foundry domain-plugin framework under `foundry/plugins`.
4. Immediate hard removal of legacy bootstrap modules in this phase.

## 3. Normative Language

This document uses:

- `MUST` / `MUST NOT` for hard requirements.
- `SHOULD` / `SHOULD NOT` for strong recommendations.
- `MAY` for optional behavior.

## 4. Target Architecture Contract

### 4.1 Canonical plugin lifecycle

After P6:

1. Discovery MUST run via `polisyos.core.components.discover_components(...)`.
2. `ComponentRegistry` MUST be the only cross-domain index of discovered plugin candidates.
3. Runtime registries MUST be populated only from `ComponentRegistry` (via bridges), not by direct entry-point/file scans.
4. Bridges MUST be deterministic and idempotent for the same component index.

### 4.2 Component taxonomy extension

P6 adds connector support to `core.components`:

1. `ComponentKind.FABRIC_CONNECTOR = "fabric_connector"`.
2. `Capability.FABRIC_CONNECTOR` as a type capability.
3. Discovery group constant: `ENTRY_POINT_GROUP_FABRIC_CONNECTORS = "polisyos.fabric_connectors"`.
4. Compliance mapping MUST enforce:
   - kind-capability alignment (`FABRIC_CONNECTOR` <-> `Capability.FABRIC_CONNECTOR`),
   - required ABI key alternatives for connectors (`fabric_connectors_api` or `fabric_api`).

### 4.3 Dependency and direction invariants

After P6 merge:

1. `fabric/connectors/_registry_lifecycle.py` MUST NOT call `discover_connectors()` directly.
2. `foundry/methods/discovery.bootstrap_registry()` MUST become compatibility wrapper over component-driven bootstrap.
3. Domain-level `discover_and_bootstrap_*` helpers (lex/scholar/provider) MUST consume a shared component index path.
4. `scientist` runtime bootstrap MUST support registering discovered `SCIENTIST_NODE` components in addition to builtins.

### 4.4 One-release compatibility contract

Through `2026-05-31`:

1. Legacy entry-point groups remain supported via adapters:
   - `polisyos.connectors`
   - `polisyos.methods`
2. Legacy APIs remain callable:
   - `polisyos.fabric.connectors.discovery.discover_connectors`
   - `polisyos.foundry.methods.discovery.bootstrap_registry`
3. Legacy paths MUST emit `DeprecationWarning` and route through canonical component bootstrap flow where possible.
4. No duplicated business logic in legacy wrappers; wrappers only adapt/forward.

## 5. Detailed Technical Design

### 5.1 Core component model updates

Required updates:

1. Extend metadata/capabilities/compliance:
   - `src/polisyos/core/components/metadata.py`
   - `src/polisyos/core/components/capabilities.py`
   - `src/polisyos/core/components/compliance.py`
2. Extend discovery groups and mapping:
   - `src/polisyos/core/components/discovery.py`
3. Update public exports:
   - `src/polisyos/core/components/__init__.py`
4. Update docs:
   - `src/polisyos/core/components/README.md`

Hard constraints:

1. Existing component kinds and validation behavior remain backward-compatible.
2. Current entry-point group constants for existing kinds remain unchanged.
3. Legacy `ENTRY_POINT_GROUP = LEGACY_ENTRY_POINT_GROUP` behavior stays intact for one release.

### 5.2 Connector bridge into `ConnectorRegistry`

Required implementation:

1. Add bridge module:
   - `src/polisyos/fabric/connectors/components_bridge.py`
2. Bridge responsibilities:
   - query components by `ComponentKind.FABRIC_CONNECTOR`,
   - validate metadata against host ABI,
   - create connector class/object from component factory,
   - enforce protocol compliance (`validate_protocol_compliance`),
   - register into `ConnectorRegistry` via existing `register(...)` API.
3. Add report model aligned with existing bridges:
   - `registered`, `duplicates`, `errors`.

Compatibility adapter:

1. Legacy connector entry points in `polisyos.connectors` SHOULD be adapted into synthetic component entries when canonical connector components are absent.
2. Synthetic mapping MUST preserve connector FQID based on `ConnectorMetadataSpec.fully_qualified_id`.

### 5.3 Method bootstrap cutover

Required changes:

1. Keep `src/polisyos/foundry/methods/components_bridge.py` as canonical bridge for method registration.
2. Rework `src/polisyos/foundry/methods/discovery.py`:
   - `bootstrap_registry(...)` becomes compatibility facade,
   - prefer component-driven flow first,
   - support legacy `polisyos.methods` adapters during compatibility window.
3. Update method bootstrap callsites to prefer component flow:
   - `src/polisyos/scientist/compute/runner.py`.

Hard constraints:

1. `MethodRegistry` resolution semantics and policies MUST remain unchanged.
2. Existing method FQN behavior and version resolution MUST remain unchanged.

### 5.4 Consolidate evaluator/extractor/provider/node bootstrap paths

Required changes:

1. Add optional `components_index` input to existing bootstrap helpers:
   - `src/polisyos/lex/legal_evaluation/evaluator_registry.py`
   - `src/polisyos/fabric/claims/extractor_registry.py`
   - `src/polisyos/lex/normpack/provider_registry.py`
   - `src/polisyos/scientist/engine/registry.py`
2. If `components_index` is supplied, helpers MUST skip local re-discovery.
3. Default helper behavior MAY call shared bootstrap orchestrator (see 5.5).

For Scientist runtime:

1. `build_registry_with_builtin_nodes()` in `src/polisyos/scientist/workflows/builder.py` MUST support overlaying discovered component nodes without replacing builtins.
2. Duplicate node ids between builtin and discovered nodes MUST be resolved deterministically (dev-scan override policy preserved).

### 5.5 Shared bootstrap orchestrator

Required new module:

- `src/polisyos/core/components/bootstrap.py`

Required public API:

1. `build_components_index(...)`:
   - one call to `discover_components(...)`,
   - builds `ComponentRegistry`,
   - returns index + discovery report.
2. `bootstrap_plugin_registries(...)`:
   - consumes `ComponentRegistry`,
   - invokes bridges for connectors/methods/evaluators/extractors/providers/nodes,
   - returns aggregated bootstrap report.

Determinism requirements:

1. Sorting and registration order MUST be stable by `component_id`.
2. Re-running bootstrap on unchanged index MUST be idempotent.

### 5.6 Runtime and CLI integration

Required runtime rewiring:

1. `src/polisyos/fabric/connectors/_registry_lifecycle.py` bootstrap path uses shared component bootstrap.
2. `src/polisyos/scientist/compute/runner.py` method bootstrap fallback routes through component path.
3. `src/polisyos/lex/api.py`, `src/polisyos/scholar/orchestrator/enrich.py`, and `src/polisyos/lex/normpack/assemble_pack.py` SHOULD reuse shared bootstrap index/report (avoid repeated discovery passes per call).

CLI update (recommended):

1. Add a command under `polisyos components` to run plugin bootstrap dry-run and print unified report.

### 5.7 Deprecation policy in code

P6 deprecates but does not remove:

1. `fabric/connectors/discovery.py` as primary runtime bootstrap mechanism.
2. `foundry/methods/discovery.py` as primary runtime bootstrap mechanism.

Deprecation requirements:

1. Emit `DeprecationWarning` with canonical replacement path.
2. Add explicit removal target date in warning message (`2026-05-31`).

## 6. Migration Plan (2 Weeks)

### 6.1 Milestones

1. `M1` (`2026-04-13` -> `2026-04-15`): extend component model for connectors and introduce shared bootstrap orchestrator skeleton.
2. `M2` (`2026-04-15` -> `2026-04-19`): implement connector and method cutover bridges + legacy adapters.
3. `M3` (`2026-04-19` -> `2026-04-23`): consolidate evaluator/extractor/provider/node bootstrap flows onto shared component index.
4. `M4` (`2026-04-24` -> `2026-04-26`): docs, deprecation warnings, CI assertions, freeze evidence.

### 6.2 PR slicing (recommended)

1. `PR-A`: core component taxonomy/discovery/compliance extension for connectors.
2. `PR-B`: connector bridge + `_registry_lifecycle` bootstrap cutover.
3. `PR-C`: method bootstrap cutover + compatibility wrapper in `foundry.methods.discovery`.
4. `PR-D`: shared bootstrap adoption in lex/scholar/scientist + tests/docs.

## 7. CI and Governance Updates

### 7.1 Mandatory artifact updates

1. `p1_refactor_queue.md`
   - mark `Q7` as `Done` when unified bootstrap is merged.
2. `import_debt_register.csv`
   - P6 SHOULD not introduce new temporary architecture debt rows.
3. `import_exceptions.toml` and `import_exceptions_registry.md`
   - no new long-lived exceptions; temporary compatibility exceptions (if any) MUST have owner/expiry.

### 7.2 Required verification commands

Architecture freeze checks:

```bash
python3 tools/lint/collect_arch_metrics.py \
  --repo-root . \
  --output-dir .tmp/p6_metrics \
  --summary-path .tmp/p6_metrics/summary.json \
  --print-summary

python3 tools/lint/compare_baseline.py \
  --baseline summary.json \
  --current .tmp/p6_metrics/summary.json \
  --mode blocking \
  --exceptions import_exceptions.toml \
  --exceptions-registry import_exceptions_registry.md \
  --baseline-import-gate import_gate.txt \
  --current-import-gate .tmp/p6_metrics/import_gate.txt \
  --debt-register import_debt_register.csv
```

Targeted tests (minimum):

```bash
python3 -m pytest \
  tests/test_components_discovery.py \
  tests/test_components_bridge.py \
  tests/fabric/test_scholar_extractor_components.py \
  tests/fabric/connectors/test_registry.py \
  tests/foundry/methods/test_discovery.py \
  tests/scientist/test_engine_registry_v0.py
```

Required new tests (P6):

```bash
python3 -m pytest \
  tests/fabric/connectors/test_components_bridge.py \
  tests/foundry/methods/test_components_bootstrap_adapter.py \
  tests/scientist/test_node_registry_components_bootstrap.py \
  tests/core/components/test_connector_kind_compliance.py \
  tests/core/components/test_unified_bootstrap_idempotency.py
```

## 8. Acceptance Criteria and DoD

P6 is complete only if all criteria are met:

1. Connectors, methods, nodes, evaluators, extractors, and providers can be bootstrapped from a single `ComponentRegistry` snapshot.
2. No runtime callsite in production path performs direct plugin discovery outside `core.components` (legacy adapter modules excluded).
3. Legacy entry-point groups (`polisyos.connectors`, `polisyos.methods`) still function with deprecation warnings.
4. Discovery duplication is removed from hot runtime paths (single shared discovery pass per bootstrap flow).
5. Architecture freeze checks pass with no regressions.
6. `Q7` in `p1_refactor_queue.md` is closed with evidence.

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| External plugin breakage due to new component requirements | High | Keep one-release legacy adapters and explicit migration examples |
| Bootstrap order drift causes behavior changes | High | Stable sort by `component_id`, idempotency tests, deterministic conflict policy |
| Performance regression from heavier metadata validation | Medium | One-pass discovery/index cache and report reuse across modules |
| Duplicate registration conflicts between builtin and discovered plugins | Medium | Explicit precedence policy and conflict reporting in aggregated bootstrap report |
| Scope creep into runtime-registry redesign | Medium | Keep registries intact; change only discovery/bootstrap surfaces |

## 10. Post-P6 Follow-Ups (Out of Scope)

1. Remove legacy adapter paths and deprecated groups after compatibility window (`target: 2026-06-30`).
2. Consider unifying runtime lookup on top of `ComponentRegistry.resolve(...)` where feasible.
3. Decide whether `foundry/plugins` domain-plugin system should join component model or remain separate.

## 11. Baseline Snapshot for P6 Planning (`2026-02-09`)

Reference baseline from completed P5 stage:

- `package_cycles_count = 0`
- `import_violations_count = 0`
- `test_collect_errors_count = 42`
- remaining architecture debt focus shifted from cycles/import edges to plugin bootstrap unification (`Q7`).

This confirms P6 is a consolidation phase, not a cycle-break phase.

## 12. Implementation Evidence (`2026-02-10`)

### 12.1 Core component model extended

1. Added connector type to component model:
   - `src/polisyos/core/components/metadata.py` (`ComponentKind.FABRIC_CONNECTOR`)
   - `src/polisyos/core/components/capabilities.py` (`Capability.FABRIC_CONNECTOR`)
2. Added connector discovery group and mapping:
   - `src/polisyos/core/components/discovery.py` (`ENTRY_POINT_GROUP_FABRIC_CONNECTORS`)
3. Added compliance rules for connectors:
   - `src/polisyos/core/components/compliance.py`
   - kind/capability alignment for `FABRIC_CONNECTOR`
   - ABI alternatives `fabric_connectors_api | fabric_api`
4. Added unified bootstrap module:
   - `src/polisyos/core/components/bootstrap.py`
   - `build_components_index(...)`
   - `bootstrap_plugin_registries(...)`
5. Updated public surface and docs:
   - `src/polisyos/core/components/__init__.py`
   - `src/polisyos/core/components/README.md`

### 12.2 Connector and method compatibility bridges

1. Added canonical connector bridge and component wrappers:
   - `src/polisyos/fabric/connectors/components.py`
   - `src/polisyos/fabric/connectors/components_bridge.py`
2. Rewired connector registry bootstrap to component-driven flow:
   - `src/polisyos/fabric/connectors/_registry_lifecycle.py`
3. Added deprecation warning for legacy connector discovery API:
   - `src/polisyos/fabric/connectors/discovery.py` (`discover_connectors`)
4. Reworked method bootstrap compatibility facade:
   - `src/polisyos/foundry/methods/discovery.py`
   - legacy `polisyos.methods` entry points adapted to component entries

### 12.3 Runtime adoption of shared component index

1. Runner method fallback now prefers component bootstrap:
   - `src/polisyos/scientist/compute/runner.py`
2. Evaluator/extractor/provider bootstrap helpers accept optional `components_index`:
   - `src/polisyos/lex/legal_evaluation/evaluator_registry.py`
   - `src/polisyos/fabric/claims/extractor_registry.py`
   - `src/polisyos/lex/normpack/provider_registry.py`
3. Scientist node discovery supports prebuilt index and deterministic dev-scan override:
   - `src/polisyos/scientist/engine/registry.py`
4. Builtin Scientist registry builder overlays discovered nodes:
   - `src/polisyos/scientist/workflows/builder.py`
5. Lex/Scholar/NormPack runtime paths now reuse one component discovery pass per flow:
   - `src/polisyos/lex/api.py`
   - `src/polisyos/scholar/orchestrator/enrich.py`
   - `src/polisyos/lex/normpack/assemble_pack.py`
6. Added CLI dry-run command for unified bootstrap:
   - `src/polisyos/core/components/_cli_components.py`
   - `src/polisyos/core/components/cli_parts.py`
   - command: `polisyos components bootstrap ...`

### 12.4 Entry-point and governance updates

1. Added canonical connector component entry-point group:
   - `pyproject.toml` (`[project.entry-points.\"polisyos.fabric_connectors\"]`)
2. Closed refactor queue item:
   - `p1_refactor_queue.md` (`Q7 -> Done`, `2026-02-10`)

### 12.5 Tests added

1. `tests/core/components/test_connector_kind_compliance.py`
2. `tests/core/components/test_unified_bootstrap_idempotency.py`
3. `tests/fabric/connectors/test_components_bridge.py`
4. `tests/scientist/test_node_registry_components_bootstrap.py`
5. `tests/foundry/methods/test_components_bootstrap_adapter.py`

### 12.6 Verification

Executed locally:

1. Targeted regression + new P6 tests:
   - `python3 -m pytest tests/core/components/test_connector_kind_compliance.py tests/fabric/connectors/test_components_bridge.py tests/scientist/test_node_registry_components_bootstrap.py tests/core/components/test_unified_bootstrap_idempotency.py tests/test_components_discovery.py tests/test_components_bridge.py tests/fabric/test_scholar_extractor_components.py tests/scientist/test_engine_registry_v0.py`
   - Result: `14 passed`
2. Architecture metrics and freeze blocking check:
   - `python3 tools/lint/collect_arch_metrics.py ...`
   - `python3 tools/lint/compare_baseline.py --mode blocking ...`
   - Result: `[OK] Architecture freeze checks passed.`

Environment limitations:

1. `tests/foundry/methods/*` suite requires `jax` in this environment and was not executable end-to-end (`ModuleNotFoundError: jax` during conftest import). New file `tests/foundry/methods/test_components_bootstrap_adapter.py` was added and syntax-validated.
