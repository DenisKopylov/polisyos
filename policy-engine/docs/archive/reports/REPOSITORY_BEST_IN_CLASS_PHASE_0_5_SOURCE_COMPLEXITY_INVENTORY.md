---
title: Repository Best-In-Class Phase 0.5 Source Complexity Inventory
status: report
owner: team-architecture
created: 2026-05-05
last_verified: 2026-05-05
stability: snapshot
related:
  - ../../plans/archive/2026-05-07-repository-best-in-class-remediation-master-plan.md
  - ../../plans/active/DECOMPOSITION_BLUEPRINT.md
  - ../../plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md
  - ../../reference/ownership.md
  - ../../../architecture/package_boundaries.toml
  - ../../../architecture/package_layout.toml
  - ../../../architecture/name_registry.toml
  - ../../../architecture/shims.toml
  - ../../../architecture/complexity_exceptions.toml
---

# Repository Best-In-Class Phase 0.5 Source Complexity Inventory

This is the read-only source complexity inventory for Phase 0.5 of the
Repository Best-In-Class Remediation Master Plan.

No source files, imports, registry TOML files, public facades, tests, or package
directories were moved or rewritten by this phase. The report records current
debt, Wave 3 and Wave 4 move maps, characterization-test candidates, and the
initial owner/risk/target package for god-module candidates.

## Snapshot

| Field | Value |
| ----- | ----- |
| Date | 2026-05-05 |
| Product root | `policy-engine/` |
| Source root | `policy-engine/src/polisyos/` |
| Python source modules scanned | 2,176 |
| Top-level product package roots scanned | 15 |
| Source package roots with non-facade root `.py` files | 10 |
| Modules above 2,000 lines | 45 |
| Initial high-debt modules from master plan | 7 |
| Scientist first-level package count | 42 |
| Structural moves performed | None |
| Import rewrites performed | None |

Evidence commands used on 2026-05-05:

```bash
find policy-engine/src/polisyos -type f -name '*.py' | wc -l
python3 - <<'PY'
from pathlib import Path
root = Path("policy-engine/src/polisyos")
for p in sorted(root.rglob("*.py")):
    if "__pycache__" in p.parts:
        continue
    lines = sum(1 for _ in p.open("rb"))
    if lines >= 2000:
        print(lines, p)
PY
rg -n "^(from|import) polisyos\.(ddm_15_7|synthetic_world)(\b|\.)" \
  policy-engine/src policy-engine/tests policy-engine/benchmarks \
  policy-engine/examples policy-engine/tools -g '*.py'
```

## Executive Findings

- `fabric` and `ir` remain the primary Wave 3 root-facade violations:
  `fabric` has 25 non-facade root modules and `ir` has 19.
- `scientist`, `ddm_15_7`, `ddm`, and `synthetic_world` are root-facade clean
  at the package root. `ddm_15_7` and `synthetic_world` are wrapper-only shims.
- Several other active roots still violate the uniform facade rule:
  `berl`, `calibration`, `common`, `data_forge`, `foundry`, `lex`, `runtime`,
  and `scholar`.
- First-party imports of `polisyos.ddm_15_7` and `polisyos.synthetic_world`
  are limited to shim smoke tests. No first-party deep imports were observed.
- The Foundry executor canonical direction is `foundry.execute`. The
  `foundry.executor` package is a public compatibility shim to
  `foundry.execute.executor`; `_executor_*`, `_execution_posture`, and
  `_numeric` remain sibling shim packages that should collapse in Wave 4.1.
- Foundry methods still has 49 non-facade root `.py` files, excluding
  `__init__.py`; it needs a file-level taxonomy move before
  method-registration integration work.
- Scientist has 42 first-level packages. Some close pairs are already reduced to
  wrapper-only compatibility packages, but `continuous_governance`,
  `verification`, `policy_verified`, `search`, `discovery`, and `research_dag`
  still need Wave 4 decisions.
- Cross-cutting names are widespread. `registry` is the largest collision with
  19 occurrences across 5 top-level packages.

## Root-Facade Inventory

Phase 0.5 treats every active top-level product package as subject to the same
root-facade rule: root `.py` files should be limited to `__init__.py`, `api.py`,
and optional `_api.py`. Compatibility shim roots may remain wrapper-only until
their sunset dates.

| Package | Root `.py` | Non-facade root `.py` | Phase target | Notes |
| ------- | ----------: | --------------------: | ------------ | ----- |
| `berl` | 3 | 2 | later small-package cleanup | `perturbations.py`, `service.py` remain root implementations. |
| `calibration` | 8 | 7 | cross-cutting calibration cleanup | Shared calibration package is active but not facade-clean. |
| `common` | 8 | 7 | core/common cleanup | Utility modules remain at root; likely deliberate but not facade-clean. |
| `core` | 1 | 0 | compliant | Root has `__init__.py` only. |
| `data_forge` | 3 | 2 | Data Forge root cleanup | `_version.py` and `errors.py` remain root files. |
| `ddm` | 1 | 0 | compliant | Canonical DDM root is facade-clean. |
| `ddm_15_7` | 1 | 0 | Wave 3.3 shim collapse | Wrapper-only compatibility facade to `polisyos.ddm`. |
| `fabric` | 26 | 25 | Wave 3.1 | Main root-facade closeout lane. |
| `foundry` | 4 | 2 | Wave 4.1/4.2 leftovers | `_quickstart.py` and `_registry.py` remain root-private facades. |
| `ir` | 20 | 19 | Wave 3.2 | Main root-facade closeout lane. |
| `lex` | 10 | 8 | later Lex root cleanup | `interventions.py` is already in complexity exceptions. |
| `runtime` | 4 | 2 | runtime facade cleanup | `manifest.py` and `replay.py` remain root files. |
| `scholar` | 8 | 6 | Scholar facade cleanup | Small root models/helpers remain at package root. |
| `scientist` | 2 | 0 | compliant | Root has `__init__.py` and `api.py`. |
| `synthetic_world` | 1 | 0 | Wave 3.4 shim collapse | Wrapper-only compatibility facade to `foundry.agent_sim.world`. |

### Fabric Root Violations

| Current file | Lines | Initial target | Characterization-test candidates |
| ------------ | ----: | -------------- | -------------------------------- |
| `src/polisyos/fabric/_connector_bridge.py` | 282 | `src/polisyos/fabric/connectors/_bridge.py` | `tests/unit/fabric/connectors/**`, connector registry smoke tests. |
| `src/polisyos/fabric/_numeric_parsing.py` | 101 | `src/polisyos/fabric/_internal/numeric_parsing.py` | `tests/unit/fabric/test_claim_canonicalize.py`, schema semantic correctness tests. |
| `src/polisyos/fabric/compatibility.py` | 107 | `src/polisyos/fabric/_internal/compatibility.py` | Fabric public-surface smoke and import-shim tests. |
| `src/polisyos/fabric/config.py` | 58 | `src/polisyos/fabric/_internal/config.py` | Fabric API/import contract tests. |
| `src/polisyos/fabric/connectors_ingestion.py` | 36 | `src/polisyos/fabric/ingestion/connectors.py` | ingestion and connector source tests. |
| `src/polisyos/fabric/decision_data.py` | 694 | `src/polisyos/fabric/data_plane/decision_data.py` | data-plane and decision packet integration tests. |
| `src/polisyos/fabric/evidence.py` | 187 | `src/polisyos/fabric/provenance/evidence.py` | claims/provenance unit tests. |
| `src/polisyos/fabric/fact_writer.py` | 171 | `src/polisyos/fabric/provenance/fact_writer.py` | fact-log/world write tests. |
| `src/polisyos/fabric/finite.py` | 57 | `src/polisyos/fabric/quality/finite.py` | finite/non-finite quality boundary tests. |
| `src/polisyos/fabric/fitness_report.py` | 263 | `src/polisyos/fabric/quality/fitness_report.py` | quality indicator and report tests. |
| `src/polisyos/fabric/ingestion.py` | 1,081 | `src/polisyos/fabric/ingestion/core.py` | ingestion, source, and connector e2e tests. |
| `src/polisyos/fabric/ingestion_providers.py` | 76 | `src/polisyos/fabric/ingestion/providers.py` | ingestion provider discovery tests. |
| `src/polisyos/fabric/manifest.py` | 68 | `src/polisyos/fabric/provenance/manifest.py` | manifest serialization/contract tests. |
| `src/polisyos/fabric/observability.py` | 729 | `src/polisyos/fabric/observability/adapter.py` | observability governance and runtime API observability tests. |
| `src/polisyos/fabric/processing_guarantees.py` | 279 | `src/polisyos/fabric/governance/processing_guarantees.py` | governance/guarantee contract tests. |
| `src/polisyos/fabric/product_integration.py` | 143 | `src/polisyos/fabric/data_plane/product_integration.py` | product integration and data-plane tests. |
| `src/polisyos/fabric/quality.py` | 657 | `src/polisyos/fabric/quality/core.py` | quality indicators, finite values, and schema semantic tests. |
| `src/polisyos/fabric/registry.py` | 48 | `src/polisyos/fabric/catalog/package_registry.py` | connector/catalog registry tests. |
| `src/polisyos/fabric/safety.py` | 230 | `src/polisyos/fabric/security/safety.py` | access control and injection-hardening tests. |
| `src/polisyos/fabric/segment_manifest.py` | 15 | `src/polisyos/fabric/world/segment_manifest.py` | world segment and materialization tests. |
| `src/polisyos/fabric/tabular.py` | 40 | `src/polisyos/fabric/io/tabular.py` | tabular connector/coercion tests. |
| `src/polisyos/fabric/temporal.py` | 118 | `src/polisyos/fabric/data_plane/temporal.py` | temporal route and time-travel tests. |
| `src/polisyos/fabric/trust.py` | 65 | `src/polisyos/fabric/trust/core.py` | trust adapter and quality/governance tests. |
| `src/polisyos/fabric/trust_adapter.py` | 49 | `src/polisyos/fabric/trust/adapter.py` | trust adapter tests and downstream Scientist pass tests. |
| `src/polisyos/fabric/world_query.py` | 869 | `src/polisyos/fabric/world/query.py` | world store/query/materialization tests. |

Wave 3.1 should add or retain `src/polisyos/fabric/api.py` as the public
surface and keep only targeted re-export shims for imports that are already
documented.

### IR Root Violations

| Current file | Lines | Initial target | Characterization-test candidates |
| ------------ | ----: | -------------- | -------------------------------- |
| `src/polisyos/ir/_lazy_facade.py` | 34 | `src/polisyos/ir/_internal/lazy_facade.py` | public-surface and import-time tests. |
| `src/polisyos/ir/_validation.py` | 371 | `src/polisyos/ir/_internal/validation.py` | validation and schema compatibility tests. |
| `src/polisyos/ir/canon.py` | 276 | `src/polisyos/ir/canon/core.py` | canon roundtrip, CAS/hash, property tests. |
| `src/polisyos/ir/citations.py` | 107 | `src/polisyos/ir/references/citations.py` | refs/citation contract tests. |
| `src/polisyos/ir/connectors.py` | 994 | `src/polisyos/ir/interoperability/connectors.py` | connector bridge/interoperability tests. |
| `src/polisyos/ir/fact_log.py` | 153 | `src/polisyos/ir/world/fact_log.py` | fact-log/world contract tests. |
| `src/polisyos/ir/loaders.py` | 119 | `src/polisyos/ir/artifacts/loaders.py` | artifact loader compatibility tests. |
| `src/polisyos/ir/migration_report.py` | 50 | `src/polisyos/ir/migrations/report.py` | migration report tests. |
| `src/polisyos/ir/model_spec.py` | 289 | `src/polisyos/ir/kernel/model_spec.py` | model spec validation tests. |
| `src/polisyos/ir/norm_pack.py` | 127 | `src/polisyos/ir/governance/norm_pack.py` | governance/norm pack tests. |
| `src/polisyos/ir/portfolio.py` | 317 | `src/polisyos/ir/analytics/portfolio.py` | analytics portfolio tests. |
| `src/polisyos/ir/predicate.py` | 79 | `src/polisyos/ir/kernel/predicate.py` | predicate/query tests. |
| `src/polisyos/ir/public_surface.py` | 1,050 | `src/polisyos/ir/_internal/public_surface.py` | `tests/unit/ir/test_public_surface.py`. |
| `src/polisyos/ir/queries.py` | 121 | `src/polisyos/ir/kernel/queries.py` | query/ref tests. |
| `src/polisyos/ir/refs.py` | 1,008 | `src/polisyos/ir/references/refs.py` | ref algebra, canonical ref, and linker tests. |
| `src/polisyos/ir/registry_fragments.py` | 986 | `src/polisyos/ir/kernel/registry_fragments.py` | registry/linker correctness tests. |
| `src/polisyos/ir/schema_catalog.py` | 575 | `src/polisyos/ir/schemas/catalog.py` | schema catalog/reflection tests. |
| `src/polisyos/ir/types.py` | 83 | `src/polisyos/ir/kernel/types.py` | type import/public facade tests. |
| `src/polisyos/ir/units.py` | 26 | `src/polisyos/ir/units/__init__.py` | units/selector field tests. |

Wave 3.2 should add or retain `src/polisyos/ir/api.py`, move implementation
modules behind package paths, and keep `src/polisyos/ir/__init__.py` as a thin
lazy facade.

### Other Active Root Violations

These are not the primary Wave 3 lanes, but they are active facade debt that
future waves should not forget.

| Package | Non-facade root files | Initial proposal |
| ------- | --------------------- | ---------------- |
| `berl` | `perturbations.py`, `service.py` | Move to `berl/metrics/perturbations.py` and `berl/adapters/service.py`; expose through `berl/api.py`. |
| `calibration` | `_sklearn_compat.py`, `adapters.py`, `continuous.py`, `curve.py`, `diagnostics.py`, `multiclass.py`, `recalibration.py` | Keep canonical shared package, but move implementations under `calibration/diagnostics/`, `calibration/recalibration/`, and `calibration/adapters/`. |
| `common` | `async_tools.py`, `config.py`, `env_parsing.py`, `jax_env.py`, `logger.py`, `serialization.py`, `timestamps.py` | Decide whether `common` is exempt as utility package or split into `common/runtime/`, `common/config/`, `common/logging/`, and `common/serialization/`. |
| `data_forge` | `_version.py`, `errors.py` | Move to `data_forge/_internal/version.py` and `data_forge/kernel/errors.py` or explicitly allow package-level error facade. |
| `foundry` | `_quickstart.py`, `_registry.py` | Keep as private facade helpers only until public imports are routed through `foundry/api.py`. |
| `lex` | `artifacts.py`, `common.py`, `errors.py`, `factlog.py`, `intervention_artifacts.py`, `interventions.py`, `provenance.py`, `types.py` | Move into `lex/normpack/`, `lex/legal_evaluation/`, `lex/knowledge/`, and `lex/_internal/`; `interventions.py` is already a complexity exception. |
| `runtime` | `manifest.py`, `replay.py` | Move to `runtime/http/manifest.py` and `runtime/http/replay.py`, or expose through `runtime/api.py`. |
| `scholar` | `errors.py`, `freshness.py`, `freshness_store.py`, `policies.py`, `provenance.py`, `types.py` | Move to `scholar/search/`, `scholar/orchestrator/`, and `scholar/_internal/` with `scholar/api.py` as the public surface. |

## Compatibility Shim Imports

### `polisyos.ddm_15_7`

Current state:

- `src/polisyos/ddm_15_7/__init__.py` is a wrapper-only facade to
  `polisyos.ddm`.
- No first-party source imports or tests deep-import through
  `polisyos.ddm_15_7.*`.
- First-party import observed: `tests/unit/ddm_15_7/test_shim.py:3`.
- `tests/unit/ddm_15_7/**` is collapsed to the single facade smoke test; DDM
  behavior and acceptance tests now live under `tests/unit/ddm/**`.
- Documented external/import surface remains in:
  `docs/reference/public-surface.md`,
  `src/polisyos/ddm_15_7/README.md`,
  `src/polisyos/ddm/README.md`,
  `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md`,
  ADR-RSR-0135, and architecture public-surface/package-boundary registries.

Wave 3.3 move map:

| Current source | Canonical target | Current state | Test candidate |
| -------------- | ---------------- | ------------- | -------------- |
| `src/polisyos/ddm_15_7/__init__.py` / `polisyos.ddm_15_7` | `src/polisyos/ddm/__init__.py` / `polisyos.ddm` | wrapper-only shim | `tests/unit/ddm_15_7/test_shim.py` |
| `tests/unit/ddm/test_delayed_label_replay.py` | `tests/unit/ddm/**` | moved to canonical test root and imports canonical `polisyos.ddm` | DDM behavior characterization tests. |
| `tests/unit/ddm/test_full_acceptance.py` | `tests/unit/ddm/**` | moved to canonical test root and imports canonical `polisyos.ddm` | DDM acceptance surface. |
| `tests/unit/ddm/test_readiness_mapping.py` | `tests/unit/ddm/**` | moved to canonical test root | readiness mapping contract. |
| `tests/unit/ddm/test_stationary_replay.py` | `tests/unit/ddm/**` | moved to canonical test root | stationary replay contract. |
| `tests/unit/ddm/test_synthetic_drift_delay.py` | `tests/unit/ddm/**` | moved to canonical test root | drift delay contract. |

Wave 3.3 acceptance state: behavior tests are under `tests/unit/ddm/**`; exactly
one shim smoke test remains under `tests/unit/ddm_15_7/`.

### `polisyos.synthetic_world`

Current state:

- `src/polisyos/synthetic_world/__init__.py` is a wrapper-only facade to
  `polisyos.foundry.agent_sim.world`.
- No first-party source imports or tests deep-import through
  `polisyos.synthetic_world.*`.
- First-party import observed: `tests/unit/synthetic_world/test_shim.py:3`.
- Behavior tests now live under the canonical target:
  `tests/unit/foundry/agent_sim/world/test_seed_worlds.py` imports
  `polisyos.foundry.agent_sim.world`.
- Documented external/import surface remains in:
  `docs/reference/public-surface.md`,
  `src/polisyos/synthetic_world/README.md`,
  `src/polisyos/foundry/agent_sim/world/README.md`,
  `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md`,
  ADR-RSR-0138, and architecture public-surface/package-boundary registries.

Wave 3.4 move map:

| Current source | Canonical target | Current state | Test candidate |
| -------------- | ---------------- | ------------- | -------------- |
| `src/polisyos/synthetic_world/__init__.py` / `polisyos.synthetic_world` | `src/polisyos/foundry/agent_sim/world/__init__.py` / `polisyos.foundry.agent_sim.world` | wrapper-only shim | `tests/unit/synthetic_world/test_shim.py` |
| `tests/unit/foundry/agent_sim/world/test_seed_worlds.py` | `tests/unit/foundry/agent_sim/world/test_seed_worlds.py` | behavior test targets canonical imports | seed world characterization. |

Wave 3.4 closeout state: behavior tests live in the Foundry agent-sim tree and
`tests/unit/synthetic_world/` contains exactly one shim smoke test.

## Foundry Executor And Methods Inventory

### Executor Naming And Private Siblings

The canonical executor naming direction is `execute`, not `executor`:

- `polisyos.foundry.execute` is documented as the compile/execute API surface.
- `polisyos.foundry.executor` is a public compatibility shim to
  `polisyos.foundry.execute.executor`.
- `_executor_*`, `_execution_posture`, and `_numeric` are private sibling shim
  packages whose targets are already recorded in `DECOMPOSITION_BLUEPRINT.md`
  and `architecture/shims.toml`.

Wave 4.1 move map:

| Current sibling | Target | Public/private | Characterization-test candidates |
| --------------- | ------ | -------------- | -------------------------------- |
| `src/polisyos/foundry/_execution_posture/` | `src/polisyos/foundry/execute/_posture.py` | private | `tests/unit/foundry/runtime/test_executor_private_modules.py`, runtime replay tests. |
| `src/polisyos/foundry/_executor_graph/` | `src/polisyos/foundry/execute/_graph.py` | private | executor fail semantics and runtime semantics tests. |
| `src/polisyos/foundry/_executor_models/` | `src/polisyos/foundry/execute/_models.py` | private | state contract, constraints, provenance, and snapshots tests. |
| `src/polisyos/foundry/_executor_ops/` | `src/polisyos/foundry/execute/_ops.py` | private | executor private modules and ops compatibility tests. |
| `src/polisyos/foundry/_executor_patching/` | `src/polisyos/foundry/execute/_patching.py` | private | patch executor and patch VM parity tests. |
| `src/polisyos/foundry/_executor_snapshots/` | `src/polisyos/foundry/execute/_snapshots.py` | private | snapshot round-trip tests. |
| `src/polisyos/foundry/_numeric/` | `src/polisyos/foundry/runtime/numeric.py` | private | numeric guard, agent-sim, calibration, and method backend tests. |
| `src/polisyos/foundry/executor/` | `src/polisyos/foundry/execute/executor.py` | public shim | compile/execute facade and runtime executor tests. |

The Wave 4.1 branch must not touch method discovery or the Foundry extension
registry; those are separate integration surfaces.

### Methods Root Loose Files

`src/polisyos/foundry/methods/` currently has 49 non-facade root `.py` files
plus `__init__.py`. The catalog-domain subpackages are already present; Wave
4.2 should move root implementation files into explicit taxonomy packages and
leave only facade and high-level coordination files at the root.

Wave 4.2 move map:

| Current file | Initial target |
| ------------ | -------------- |
| `_artifacts_chain.py` | `methods/artifacts/chain.py` |
| `_artifacts_evidence.py` | `methods/artifacts/evidence.py` |
| `_artifacts_fingerprint.py` | `methods/artifacts/fingerprint.py` |
| `_artifacts_method.py` | `methods/artifacts/method.py` |
| `_artifacts_records.py` | `methods/artifacts/records.py` |
| `_logging.py` | `methods/_internal/logging.py` |
| `artifacts.py` | `methods/artifacts/api.py` |
| `artifacts_parts.py` | `methods/artifacts/parts.py` |
| `base.py` | `methods/contracts/base.py` |
| `bayesian.py` | `methods/catalog/bayesian/api.py` |
| `cache.py` | `methods/lifecycle/cache.py` |
| `catalog_snapshot.py` | `methods/catalog/snapshot.py` |
| `causal.py` | `methods/catalog/causal/api.py` |
| `compat.py` | `methods/lifecycle/compat.py` |
| `compat_matrix.py` | `methods/lifecycle/compat_matrix.py` |
| `compiler.py` | `methods/compiler/core.py` |
| `components_bridge.py` | `methods/components/bridge.py` |
| `composer.py` | `methods/components/composer.py` |
| `consensus.py` | `methods/selection/consensus.py` |
| `cost_model.py` | `methods/selection/cost_model.py` |
| `dependence.py` | `methods/catalog/dependence/api.py` |
| `deprecation.py` | `methods/lifecycle/deprecation.py` |
| `discovery.py` | `methods/selection/discovery.py` until extension registry consolidation chooses a final home. |
| `econometrics.py` | `methods/catalog/econometrics/api.py` |
| `exceptions.py` | `methods/contracts/exceptions.py` |
| `hot_reload.py` | `methods/compiler/hot_reload.py` |
| `io.py` | `methods/artifacts/io.py` |
| `layout.py` | `methods/compiler/layout.py` |
| `lifecycle.py` | `methods/lifecycle/core.py` |
| `linker.py` | `methods/compiler/linker.py` |
| `loss.py` | `methods/components/loss.py` |
| `merge_engine.py` | `methods/compiler/merge_engine.py` |
| `microsim.py` | `methods/catalog/microsim/api.py` |
| `ml.py` | `methods/catalog/ml/api.py` |
| `mypy_plugin.py` | `methods/compiler/mypy_plugin.py` |
| `network.py` | `methods/catalog/network/api.py` |
| `observability.py` | `methods/lifecycle/observability.py` |
| `optimization.py` | `methods/catalog/optimization/api.py` |
| `output_monitor.py` | `methods/lifecycle/output_monitor.py` |
| `plan_optimizer.py` | `methods/selection/plan_optimizer.py` |
| `profiler.py` | `methods/lifecycle/profiler.py` |
| `registry.py` | `methods/selection/registry.py` or `methods/catalog/registry.py`; final choice should be serialized with Phase 5.1. |
| `resolution.py` | `methods/selection/resolution.py` |
| `selection.py` | `methods/selection/ranking.py` |
| `selection_history.py` | `methods/selection/history.py` |
| `semantic_validator.py` | `methods/contracts/semantic_validator.py` |
| `slot_schema.py` | `methods/contracts/slot_schema.py` |
| `spatial.py` | `methods/catalog/spatial/api.py` |
| `specialization.py` | `methods/compiler/specialization.py` |

Characterization-test candidates:

- `tests/unit/foundry/methods/catalog/**`
- `tests/property/foundry/methods/catalog/**`
- `tests/unit/foundry/methods/backends/**`
- `tests/unit/foundry/methods/test_causal_engine_integration.py`
- `tests/unit/foundry/methods/catalog/causal/test_dynamic_registration.py`
- `tests/unit/runtime/http/test_control_api.py` for catalog snapshot
  integration through runtime.

### Method Catalog Registration

Current built-in registration path:

- `foundry/methods/catalog/__init__.py` imports every
  `ensure_*_methods_registered()` helper and implements
  `ensure_all_methods_registered()`.
- Each family package implements an `ensure_*_methods_registered()` function in
  its `__init__.py`.
- Each family has `_registry_boot.py` with a `register_*_methods()` function
  returning method classes.
- `foundry/methods/discovery.py` defines `ENTRY_POINT_GROUP = "polisyos.methods"`
  and can discover external method classes by entry point or filesystem scan.
- `pyproject.toml` does not currently declare a
  `[project.entry-points."polisyos.methods"]` group for built-in methods.

Current `_registry_boot.py` families:

| Family | Registration function |
| ------ | --------------------- |
| `bayesian` | `register_bayesian_methods()` |
| `causal` | `register_causal_methods()` |
| `dependence` | `register_dependence_methods()` |
| `distributional` | `register_distributional_methods()` |
| `econometrics` | `register_econometric_methods()` |
| `forecasting` | `register_forecasting_methods()` |
| `mechanism` | `register_mechanism_methods()` |
| `microsim` | `register_microsim_methods()` |
| `ml` | `register_ml_methods()` |
| `network` | `register_network_methods()` |
| `optimization` | `register_optimization_methods()` |
| `policy` | `register_policy_methods()` |
| `sensitivity` | `register_sensitivity_methods()` |
| `simulation` | `register_simulation_methods()` |
| `spatial` | `register_spatial_methods()` |
| `survey` | `register_survey_methods()` |
| `validation` | `register_validation_methods()` |

### Extension Registry Entry Points

Only two Python entry-point groups are declared in `pyproject.toml` today:

| Group | Entries | Owner |
| ----- | ------: | ----- |
| `polisyos.fabric_connectors` | 11 | `team-fabric` |
| `polisyos.scientist_governance_passes` | 13 | `team-scientist` |

Additional plugin-like internals exist but are not declared as package entry
points:

- Foundry methods: code supports `polisyos.methods`, but no built-in entry
  points are declared.
- Foundry domain plugins: `foundry/plugins/discovery.py` scans
  `polisyos.plugins` via `pkg_resources.iter_entry_points`, but
  `pyproject.toml` has no matching group.
- Method slot schemas and catalog snapshots are internally registered, not
  externally discoverable.

Wave 4.2 should not solve extension registry consolidation. It should make the
method registration path explicit enough for Wave 5.1 to add or formalize entry
points without moving the same files again.

## Scientist Package Inventory

Scientist currently has 42 first-level package directories:

```text
adapters, agent, autotune, backtesting, causal, claims, compute,
continuous_governance, cross_graph, decision_validity, discovery, doe, engine,
error_semantics, evals, evidence, evidence_sources, feedback, feedback_utils,
frontier_runtime, governance, human_review, kernel, latent_separation, llm,
llm_cycle, memory, nodes, orchestrator, policy_design, policy_verified,
provenance, publisher, reliability_scorecard, remediation_status, replay,
replay_backend, research_dag, search, validation, verification, workflows
```

Close-pair inventory and Wave 4 target proposals:

| Pair or cluster | Current state | Initial Wave 4 target | Characterization-test candidates |
| --------------- | ------------- | --------------------- | -------------------------------- |
| `feedback` / `feedback_utils` | `feedback` has `core.py` and `utils.py`; `feedback_utils` is wrapper-only. | Retire `feedback_utils` after shim sunset; keep `scientist/feedback/` as canonical. | `tests/unit/scientist/engine/test_feedback_runtime.py`, feedback workflow integration tests. |
| `replay` / `replay_backend` | `replay` has backend/comparators/diff; `replay_backend` is wrapper-only. | Retire `replay_backend`; keep `scientist/replay/` as canonical. | `tests/unit/scientist/replay/**`, runtime replay measurement tests. |
| `evidence` / `evidence_sources` | `evidence` has `sources.py`; `evidence_sources` is wrapper-only. | Retire `evidence_sources`; keep `scientist/evidence/` as canonical. | `tests/unit/scientist/evidence/**`, cross-graph evidence tests. |
| `governance` / `continuous_governance` | Both are implementation packages. | Move continuous-governance loop code under `scientist/governance/continuous/` with a targeted shim. | `tests/unit/scientist/continuous_governance/**`, governance pass registry tests. |
| `validation` / `verification` / `policy_verified` | `validation` is active; `verification/ic` and `policy_verified` are separate first-level packages. | Move IC verification under `scientist/validation/verification/` and policy-verified service under `scientist/validation/policy_verified/` or `scientist/governance/policy_verified/` after Wave 1 semantic decision. | `tests/unit/scientist/governance/test_ic_*`, `tests/unit/scientist/policy_design/test_policy_verified_*`, validation suites. |
| `llm` / `llm_cycle` | `llm/cycle.py` is canonical; `llm_cycle` is wrapper-only. | Retire `llm_cycle`; keep `scientist/llm/` as canonical. | `tests/unit/scientist/llm/test_llm_cycle_preflight.py`, search loop tests. |
| `discovery` / `search` / `research_dag` | All three are implementation packages; `search` is large with 72 Python files. | Initial target is `scientist/orchestrator/discovery/`, `scientist/orchestrator/search/`, and `scientist/orchestrator/research_dag/`; Wave 1 should decide whether optimization search is a `methods/` boundary instead. | `tests/unit/scientist/discovery/**`, `tests/unit/scientist/search/**`, `tests/unit/scientist/research_dag/**`, engine research DAG integration tests. |

## Cross-Cutting Concern Collisions

| Concern | Occurrences | Packages | Current registry state | Phase 4.8 action |
| ------- | ----------: | -------- | ---------------------- | ---------------- |
| `observability` | 4 | `core`, `data_forge`, `fabric`, `foundry` | Not explicitly registered in `name_registry.toml`. | Add canonical `core/observability` plus package adapter rule. |
| `security` | 4 | `core`, `fabric`, `runtime`, `scholar` | Registered only for `core` and `fabric`. | Register runtime/scholar adapters or rename package-local modules. |
| `registry` | 19 | `core`, `data_forge`, `fabric`, `foundry`, `scientist` | Registered for `core` and `foundry`; many extra module-level registries exist. | Add disambiguated registry taxonomy or package-local adapter rule. |
| `discovery` | 8 | `core`, `fabric`, `foundry`, `scientist` | Rename backlog lists `core`, `foundry`, `scientist`; Fabric discovery modules also exist. | Reconcile discovery backlog with Fabric connector/catalog discovery. |
| `governance` | 6 | `core`, `fabric`, `ir`, `scientist` | Registered for `core`, `foundry`, `ir`, `scientist`; Fabric module-level governance exists. | Register Fabric connector-contract governance or rename it. |
| `contracts` | 13 | `berl`, `core`, `data_forge`, `ddm`, `fabric`, `foundry`, `ir`, `scientist` | Registered for `berl`, `core`, `ddm`, `fabric`, `foundry`, `lex`, `scientist`; Data Forge and IR module-level contracts exist. | Decide canonical contract semantics per package and register module-level exceptions. |
| `calibration` | 9 | `calibration`, `data_forge`, `ddm`, `foundry`, `ir`, `scientist` | Registered for `calibration`, `ddm`, `foundry`, `scientist`. | Add IR/Data Forge scoped calibration semantics or rename to avoid global calibration ambiguity. |
| `runtime` | 7 | `core`, `data_forge`, `foundry`, `runtime`, `scientist` | Registered for `data_forge`, `runtime`; rename backlog lists foundry/scientist. | Reserve top-level `runtime`, rename package internals to runtime glue or adapters. |
| `trace` | 3 | `core`, `foundry` | Registered for `core`, `foundry`. | Keep canonical `core/trace` and Foundry adapter distinction. |

Detailed collision examples:

- `registry`: `core/registry`, `core/*/registry.py`,
  `fabric/*/registry.py`, `foundry/methods/registry.py`,
  `foundry/registry`, and multiple Scientist registries all share the same
  generic noun.
- `runtime`: top-level `runtime` is a product package; Foundry and Scientist
  still use runtime as an internal concept in modules/directories.
- `observability`: `core/observability` should be canonical, while Fabric,
  Data Forge, and Foundry should expose package-local adapters.

## Module-Size Inventory

All modules above 2,000 lines are classified below. Classification categories:

- `domain model concentration`: many domain concepts or algorithms in one file.
- `mixed IO/business logic`: source/network/filesystem/persistence mixed with
  domain decisions.
- `registry/catalog assembly`: registry, catalog, or schema assembly dominates.
- `service orchestration`: API/node/service orchestration dominates.
- `generated or semi-generated code`: generated contract, schema, or bulk
  declarative code.

| Lines | Module | Classification | Owner | Risk note | Initial target subpackage |
| ----: | ------ | -------------- | ----- | --------- | ------------------------- |
| 10,231 | `src/polisyos/foundry/methods/catalog/causal/causal_engine.py` | domain model concentration; service orchestration | `team-foundry` | Highest review and regression risk; mixes causal engines, estimand paths, diagnostics, and adapters. | `foundry/methods/catalog/causal/engine/` split into models, estimands, diagnostics, execution adapters. |
| 8,236 | `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | mixed IO/business logic; registry/catalog assembly | `team-data-forge` | Catalog source ingestion mixes harvest IO, normalization, registry writes, and trust decisions. | `data_forge/domains/catalog/batch/core_sources_ingest/` split into harvesting, normalization, registry assembly, quality gates. |
| 5,769 | `src/polisyos/foundry/methods/catalog/causal/interference.py` | domain model concentration | `team-foundry` | Interference estimators, exposure mappings, diagnostics, and method classes are coupled. | `foundry/methods/catalog/causal/interference/` split into exposure, estimators, diagnostics, protocols. |
| 5,045 | `src/polisyos/foundry/methods/catalog/causal/id_engine.py` | domain model concentration | `team-foundry` | Identification algorithms and graph transforms have high correctness risk. | `foundry/methods/catalog/causal/identification/` split into graph ops, ID algorithms, proof trace, errors. |
| 4,684 | `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py` | service orchestration; mixed IO/business logic | `team-scientist` | Decision packet builder mixes section emitters, validation, artifact assembly, and evidence hydration. | `scientist/nodes/builtins/decide/decision_packet/` split into sections, validation, evidence, serialization. |
| 4,622 | `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py` | mixed IO/business logic; service orchestration | `team-data-forge` | Academic extraction resolution mixes parsing, source fetches, adjudication, and output assembly. | `data_forge/domains/academic/batch/resolve_extract/` split into resolver, extractors, adjudication, persistence. |
| 4,114 | `src/polisyos/runtime/http/services/control.py` | service orchestration; mixed IO/business logic | `team-runtime` | Runtime control service is a broad API orchestration hub with CAS, method catalog, Scientist, and HTTP concerns. | `runtime/http/services/control/` split into runs, artifacts, method catalog, collaboration, graph endpoints. |
| 3,881 | `src/polisyos/data_forge/domains/legal/batch/graph_builder.py` | mixed IO/business logic; domain model concentration | `team-data-forge` | Legal graph construction combines extraction outputs, graph semantics, persistence, and validation. | `data_forge/domains/legal/batch/graph_builder/` split into models, builders, validation, writers. |
| 3,658 | `src/polisyos/foundry/methods/catalog/causal/invariance_tests.py` | domain model concentration | `team-foundry` | Multiple invariance tests and regimes are concentrated in one catalog file. | `foundry/methods/catalog/causal/invariance/` |
| 3,435 | `src/polisyos/foundry/methods/catalog/causal/constraint_discovery.py` | domain model concentration; service orchestration | `team-foundry` | Discovery algorithms, constraints, and method registrations are coupled. | `foundry/methods/catalog/causal/discovery/constraints/` |
| 3,210 | `src/polisyos/foundry/methods/catalog/bayesian/advanced.py` | domain model concentration | `team-foundry` | Advanced Bayesian estimators and optional-stack behavior are concentrated. | `foundry/methods/catalog/bayesian/advanced/` |
| 3,114 | `src/polisyos/foundry/methods/selection.py` | registry/catalog assembly; service orchestration | `team-foundry` | Catalog scoring, ranking, evidence overlays, and serialization are coupled. | `foundry/methods/selection/` split into ranking, evidence, payloads, alternatives. |
| 3,085 | `src/polisyos/ir/analytics/strategic.py` | domain model concentration | `team-ir` | Strategic analytics contracts and validation rules are dense. | `ir/analytics/strategic/` |
| 2,866 | `src/polisyos/runtime/http/openapi_contract.py` | generated or semi-generated code; service orchestration | `team-runtime` | API contract surface is large and likely generated/semi-generated; manual edits are risky. | `runtime/http/contracts/openapi/` plus generated-artifact classification. |
| 2,824 | `src/polisyos/foundry/methods/catalog/ml/uncertainty.py` | domain model concentration | `team-foundry` | ML uncertainty methods and calibration semantics are concentrated. | `foundry/methods/catalog/ml/uncertainty/` |
| 2,743 | `src/polisyos/scientist/validation/fairness_audit.py` | domain model concentration; service orchestration | `team-scientist` | Fairness models, audit execution, and reporting are coupled. | `scientist/validation/fairness/` |
| 2,733 | `src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py` | service orchestration; mixed IO/business logic | `team-scientist` | Welfare transforms, evidence, and node glue are mixed. | `scientist/nodes/builtins/simulate/welfare/` |
| 2,520 | `src/polisyos/foundry/methods/catalog/causal/missing_data.py` | domain model concentration | `team-foundry` | Missingness/recoverability methods and diagnostics are concentrated. | `foundry/methods/catalog/causal/missing_data/` |
| 2,497 | `src/polisyos/foundry/methods/catalog/network/analysis.py` | domain model concentration | `team-foundry` | Network analysis methods and models are concentrated. | `foundry/methods/catalog/network/analysis/` |
| 2,426 | `src/polisyos/foundry/methods/catalog/causal/estimand_compiler.py` | domain model concentration; registry/catalog assembly | `team-foundry` | Estimand compilation, transforms, and catalog method glue are coupled. | `foundry/methods/catalog/causal/estimands/` |
| 2,416 | `src/polisyos/ir/observation/contract_compilers.py` | domain model concentration; service orchestration | `team-ir` | Observation contract compilation mixes models, validation, and compiler flow. | `ir/observation/compilers/` |
| 2,414 | `src/polisyos/foundry/methods/catalog/causal/distributional_bounds.py` | domain model concentration | `team-foundry` | Distributional bounds estimators and diagnostics are concentrated. | `foundry/methods/catalog/causal/bounds/distributional.py` |
| 2,407 | `src/polisyos/ir/analytics/alignment_certification.py` | domain model concentration | `team-ir` | Alignment certification contracts and cross-package references are dense. | `ir/analytics/alignment/` |
| 2,392 | `src/polisyos/foundry/methods/catalog/microsim/advanced.py` | domain model concentration | `team-foundry` | Advanced microsim methods concentrate many estimators. | `foundry/methods/catalog/microsim/advanced/` |
| 2,367 | `src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py` | service orchestration; mixed IO/business logic | `team-scientist` | Distributional metrics, reporting, and node behavior are coupled. | `scientist/nodes/builtins/simulate/distributional/` |
| 2,337 | `src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py` | registry/catalog assembly | `team-data-forge` | Runtime canonical registry assembly is large and domain-coupled. | `data_forge/domains/academic/knowledge/registry/` |
| 2,317 | `src/polisyos/foundry/methods/consensus.py` | domain model concentration; service orchestration | `team-foundry` | Consensus adapters, scoring, and method outputs are coupled. | `foundry/methods/selection/consensus/` |
| 2,295 | `src/polisyos/scientist/search/judge_stack.py` | service orchestration | `team-scientist` | Judge stack orchestration, persistence, and verdict models are concentrated. | `scientist/search/judging/` or future `scientist/orchestrator/search/judging/`. |
| 2,270 | `src/polisyos/foundry/methods/catalog/causal/protocols.py` | domain model concentration | `team-foundry` | Protocol/model definitions are too dense for a single module. | `foundry/methods/catalog/causal/contracts/` |
| 2,253 | `src/polisyos/core/contracts/runtime.py` | domain model concentration | `team-core` | Runtime contract models are centralized and broad. | `core/contracts/runtime/` |
| 2,241 | `src/polisyos/scientist/verification/ic/service.py` | service orchestration; domain model concentration | `team-scientist` | Incentive-compatibility service combines verification models and execution. | `scientist/validation/verification/ic/service.py` |
| 2,171 | `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py` | service orchestration; mixed IO/business logic | `team-scientist` | Blueprint runtime validation, evidence mapping, and artifact writes are coupled. | `scientist/nodes/builtins/decide/policy_blueprint/` |
| 2,158 | `src/polisyos/data_forge/domains/catalog/batch/harvester.py` | mixed IO/business logic | `team-data-forge` | Harvest IO, retry, sampling, and output shaping are mixed. | `data_forge/domains/catalog/batch/harvester/` |
| 2,156 | `src/polisyos/foundry/methods/catalog/causal/frontier.py` | domain model concentration | `team-foundry` | Frontier causal estimators and optional dependencies are concentrated. | `foundry/methods/catalog/causal/frontier/` |
| 2,145 | `src/polisyos/ir/analytics/estimand.py` | domain model concentration | `team-ir` | Estimand models and normalization rules are dense. | `ir/analytics/estimand/` |
| 2,136 | `src/polisyos/foundry/methods/catalog/network/missingness.py` | domain model concentration | `team-foundry` | Network missingness methods and diagnostics are concentrated. | `foundry/methods/catalog/network/missingness/` |
| 2,119 | `src/polisyos/data_forge/domains/ukraine/adapters.py` | mixed IO/business logic | `team-data-forge` | Ukraine domain adapters mix source normalization and domain projections. | `data_forge/domains/ukraine/adapters/` |
| 2,073 | `src/polisyos/data_forge/domains/academic/batch/article_extractor.py` | mixed IO/business logic; service orchestration | `team-data-forge` | Article extraction mixes parsing, IO, validation, and output assembly. | `data_forge/domains/academic/batch/article_extractor/` |
| 2,060 | `src/polisyos/foundry/methods/catalog/survey/adaptive.py` | domain model concentration | `team-foundry` | Adaptive survey methods are concentrated. | `foundry/methods/catalog/survey/adaptive/` |
| 2,048 | `src/polisyos/foundry/methods/catalog/bayesian/frontier.py` | domain model concentration | `team-foundry` | Frontier Bayesian methods and optional stack handling are concentrated. | `foundry/methods/catalog/bayesian/frontier/` |
| 2,034 | `src/polisyos/runtime/http/services/debug.py` | service orchestration | `team-runtime` | Debug service is large and crosses artifact, timeline, and method catalog concerns. | `runtime/http/services/debug/` |
| 2,033 | `src/polisyos/foundry/methods/catalog/econometrics/thresholds.py` | domain model concentration | `team-foundry` | Threshold econometrics variants are concentrated. | `foundry/methods/catalog/econometrics/thresholds/` |
| 2,032 | `src/polisyos/foundry/methods/catalog/econometrics/advanced.py` | domain model concentration | `team-foundry` | Advanced econometrics methods are concentrated. | `foundry/methods/catalog/econometrics/advanced/` |
| 2,031 | `src/polisyos/scientist/cross_graph/compiler.py` | service orchestration; domain model concentration | `team-scientist` | Cross-graph compiler mixes compilation, evidence mapping, and artifact shaping. | `scientist/cross_graph/compiler/` |
| 2,018 | `src/polisyos/ir/analytics/frontier.py` | domain model concentration | `team-ir` | Frontier analytics contracts are dense. | `ir/analytics/frontier/` |

## Initial High-Debt Module List

The master plan explicitly seeds the high-debt list with seven modules. Those
modules are all above 4,000 lines and should receive characterization tests and
shrink budgets before any extraction.

| Module | Lines | Owner | Risk note | Initial target subpackage | First characterization candidates |
| ------ | ----: | ----- | --------- | ------------------------- | --------------------------------- |
| `src/polisyos/foundry/methods/catalog/causal/causal_engine.py` | 10,231 | `team-foundry` | Broad causal method hub; high algorithmic regression risk. | `foundry/methods/catalog/causal/engine/` | `tests/unit/foundry/methods/catalog/causal/test_causal_engine*.py`, `tests/unit/foundry/methods/test_causal_engine_integration.py`. |
| `src/polisyos/data_forge/domains/catalog/batch/core_sources_ingest.py` | 8,236 | `team-data-forge` | Batch IO and catalog semantics are coupled. | `data_forge/domains/catalog/batch/core_sources_ingest/` | `tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py`. |
| `src/polisyos/foundry/methods/catalog/causal/interference.py` | 5,769 | `team-foundry` | Interference estimators and diagnostics are concentrated. | `foundry/methods/catalog/causal/interference/` | `tests/unit/foundry/methods/catalog/causal/test_interference*.py`. |
| `src/polisyos/foundry/methods/catalog/causal/id_engine.py` | 5,045 | `team-foundry` | ID algorithms are correctness-critical and graph-sensitive. | `foundry/methods/catalog/causal/identification/` | `tests/unit/foundry/methods/catalog/causal/test_id_engine_extensions.py`, ID-star/cyclic-ID tests. |
| `src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py` | 4,684 | `team-scientist` | Decision packet assembly has broad downstream API impact. | `scientist/nodes/builtins/decide/decision_packet/` | decision packet node, metric validation, welfare, distributional/econometrics tests. |
| `src/polisyos/data_forge/domains/academic/batch/resolve_extract.py` | 4,622 | `team-data-forge` | Academic extraction resolution couples parsing, fetch, and adjudication. | `data_forge/domains/academic/batch/resolve_extract/` | article extraction, fulltext resolver, extractor stage tests. |
| `src/polisyos/runtime/http/services/control.py` | 4,114 | `team-runtime` | Central HTTP orchestration surface; high API regression blast radius. | `runtime/http/services/control/` | `tests/unit/runtime/http/test_control_api.py`, hardening, DI, route, and access invariant tests. |

## Wave 3 And Wave 4 Acceptance Readiness

Wave 3 readiness:

- Fabric and IR file-level move maps are recorded above.
- DDM and Synthetic World shim import inventories show no first-party deep
  import blockers.
- Characterization-test candidates are listed for Fabric, IR, DDM, and
  Synthetic World.
- No physical source move has started.

Wave 4 readiness:

- Foundry executor/execute naming is resolved to `execute` as canonical.
- Foundry private sibling move map is recorded.
- Foundry methods root taxonomy map is recorded.
- Scientist close-pair/package-count inventory is recorded.
- Cross-cutting concern collision inventory identifies the Phase 4.8 registry
  decisions needed before broad adapter work.
- Every module above 2,000 lines has an owner, risk note, and initial target
  subpackage proposal.

## Acceptance Check

- Root-facade violations are inventoried for Fabric, IR, and every active
  product package root.
- First-party and documented external uses of `polisyos.ddm_15_7` and
  `polisyos.synthetic_world` are inventoried.
- Foundry executor sibling packages, `executor` versus `execute`, methods-root
  loose files, method registration, and extension entry points are inventoried.
- Scientist first-level package count and close semantic pairs are inventoried.
- Cross-cutting concern collisions are inventoried for observability, security,
  registry, discovery, governance, contracts, calibration, runtime, and trace.
- Modules above 2,000 lines are classified and assigned owner/risk/target.
- The master-plan high-debt seed list is recorded with characterization-test
  candidates.
- No import rewrites, source moves, or registry edits were performed.
