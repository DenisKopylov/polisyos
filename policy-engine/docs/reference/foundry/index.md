# Foundry

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

`polisyos.foundry` is the PolicyOS computation layer. It compiles Trinity
bundles into CAS-backed execution plans, binds data snapshots into runtime
state, executes patch-first simulation graphs, calibrates parameters, exposes a
method catalog, and runs agent-simulation surfaces.

This page is the D1-L3 documentation map for the Foundry remediation plan in
`docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: stable `polisyos.foundry` facade, `src/polisyos/foundry/**`, linked tests/ADRs, and generated method-snapshot inputs from `polisyos.foundry.methods.catalog.snapshot`

## Phase Map

| Source phase                                          | Documentation owner                                                                                                                                                                                                                | Validation anchor                                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0: program freeze and backlog normalization     | This index and the source plan keep the backlog, page ownership, and release-gate evidence together.                                                                                                                               | `tests/unit/foundry/validation/test_release_gate.py`                                                                                                                                                                                                                                                                    |
| Phase 1: correctness emergency train                  | [Compile Execute](compile-execute.md), [State](state.md), and [Observability Reproducibility](observability-reproducibility.md) describe fail-closed compile/execute, input bindings, FailureCard behavior, and NaN guard posture. | `tests/unit/foundry/facade/test_quickstart.py`, `tests/unit/foundry/runtime/test_executor_fail_semantics.py`, `tests/unit/foundry/runtime/test_nan_guard_public.py`                                                                                                                                                                                  |
| Phase 2: execution kernel hardening                   | [Compile Execute](compile-execute.md) and [State](state.md) cover program graphs, exec plans, state snapshots, merge/delta application, and private executor evidence.                                                             | `tests/unit/foundry/runtime/test_executor_private_modules.py`, `tests/unit/foundry/runtime/test_executor_snapshots.py`, `tests/unit/foundry/analysis/test_merge_determinism.py`                                                                                                                                                                 |
| Phase 3: numerical stability and JAX semantics        | [Calibration](calibration.md), [State](state.md), and [Observability Reproducibility](observability-reproducibility.md) point numeric/JAX claims to tests and ADRs.                                                                | `tests/unit/foundry/calibration/test_measurement.py`, `tests/unit/foundry/methods/backends/test_numerical_stability.py`, `docs/reference/foundry/numeric-guardrails.md`                                                                                                                                                     |
| Phase 4: performance, concurrency and reproducibility | [Observability Reproducibility](observability-reproducibility.md) and [Run Benchmarks](../../how-to/run-benchmarks.md) define capability, replay, tolerance, and benchmark command boundaries.                                     | `tests/unit/foundry/methods/backends/test_backend_determinism.py`, `tests/unit/foundry/benchmarks/test_ws5_jax_perf.py`, `benchmarks/suite_registry.py`                                                                                                                                                           |
| Phase 5: Bayesian, UQ and calibration frontier        | [Calibration](calibration.md), [Methods Catalog](methods-catalog.md), and [Frontier Methods](frontier-methods.md) separate available UQ/calibration surfaces from research-gated Bayesian claims.                                  | [`docs/adr/0012-uncertainty-envelope-ir-contract.md`](../../adr/0012-uncertainty-envelope-ir-contract.md), [`docs/adr/0013-uncertainty-propagation-pipeline.md`](../../adr/0013-uncertainty-propagation-pipeline.md), [`docs/adr/0074-numpyro-bayesian-scm.md`](../../adr/0074-numpyro-bayesian-scm.md) |
| Phase 6: causal, ML, agent-sim and policy frontier    | [Methods Catalog](methods-catalog.md), [Frontier Methods](frontier-methods.md), [Agent Sim](agent-sim.md), and [Causal Engine](../../explanation/causal-engine.md) document runnable frontier families and governance boundaries.  | `tests/unit/foundry/methods/catalog/causal/test_frontier_methods.py`, `tests/unit/foundry/methods/catalog/ml/test_frontier.py`, `tests/unit/foundry/methods/catalog/policy/test_frontier.py`                                                                                                                           |

## Page Map

| Page                                                              | Scope                                                                            | Primary modules                                                                                                                          |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| [Compile Execute](compile-execute.md)                             | Root API, compile requests, execute requests, input bindings, quickstart         | `polisyos.foundry`, `foundry.compile.api`, `foundry.execute.api`, `foundry.data_plane.bindings`, `foundry.quickstart`                    |
| [Calibration](calibration.md)                                     | Fit loop, measurement-aware loss, auxiliary penalties, Hessian/UQ boundary       | `foundry.calibration.*`, `foundry.uncertainty.*`                                                                                         |
| [Demography](demography.md)                                       | Static aging with demographic consistency, donor entrants, integerized draws     | `foundry.methods.catalog.survey.demographic_consistency`, `foundry.methods.catalog.simulation.demography`, `data_forge.read_api.ukraine` |
| [Methods Catalog](methods-catalog.md)                             | ABI, registry, dispatch, capability matrix, advisor, truthfulness tiers          | `foundry.methods.*`, `foundry.methods.catalog.*`                                                                                         |
| [Frontier Methods](frontier-methods.md)                           | Bayesian/UQ and Phase 6 causal, ML, agent-sim, policy frontier surfaces          | `foundry.methods.catalog.causal.frontier`, `foundry.methods.catalog.ml.frontier`, `foundry.methods.catalog.policy.frontier`              |
| [Observability Reproducibility](observability-reproducibility.md) | Runtime fingerprints, determinism tiers, tolerance budgets, release acceptance   | `foundry.runtime.*`, `foundry.methods.backends.*`, `foundry.release_acceptance`                                                          |
| [Agent Sim](agent-sim.md)                                         | ABM/RL runtime layers, wiring contracts, graph/population/distribution executors | `foundry.agent_sim.*`                                                                                                                    |
| [State](state.md)                                                 | `GlobalState`, slot layout, snapshots, patch/delta boundary, JAX state contracts | `foundry.contracts.state`, `foundry.methods.layout`, `foundry.execute.executor`                                                          |

Pages in `docs/reference/foundry/` are manually maintained. The methods-catalog
and observability pages reuse generated `MethodCatalogSnapshot`,
capability-matrix, and operator-evidence inputs, and they document their
regeneration commands directly on the page.

## Documentation Impact

| Output cluster                              | Exact files                                                                                                                                                                                                                                                                                                                                                                                     | Source of truth                                                                                                                                                | Validation                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reference set                               | `docs/reference/foundry/index.md`, `docs/reference/foundry/compile-execute.md`, `docs/reference/foundry/calibration.md`, `docs/reference/foundry/demography.md`, `docs/reference/foundry/methods-catalog.md`, `docs/reference/foundry/frontier-methods.md`, `docs/reference/foundry/observability-reproducibility.md`, `docs/reference/foundry/agent-sim.md`, `docs/reference/foundry/state.md` | `polisyos.foundry` facade, compile/execute APIs, calibration and methods subsystems, runtime fingerprints, agent-sim modules, demography static-aging surfaces | `uv run pytest tests/unit/foundry/facade/test_quickstart.py tests/unit/foundry/compile/test_compile_determinism.py tests/unit/foundry/runtime/test_execute_input_bindings.py tests/unit/foundry/runtime/test_nan_guard_public.py tests/unit/foundry/calibration/test_measurement.py tests/unit/foundry/methods/backends/test_numerical_stability.py tests/unit/foundry/methods/catalog/survey/test_demographic_consistency.py tests/unit/foundry/methods/catalog/simulation/test_demography.py -q` |
| Explanation, how-to, and benchmark surfaces | `docs/explanation/causal-engine.md`, `docs/how-to/run-causal-analysis.md`, `docs/how-to/run-benchmarks.md`, `docs/benchmarks/confidential-computing-overhead.md`                                                                                                                                                                                                                                | causal-engine architecture notes, benchmark suite registry, current benchmark commands, measurement methodology                                                | `uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -q`                                                                                                                                                                                                                                                                                                                                                     |
| Package boundary READMEs                    | `src/polisyos/foundry/README.md`, `src/polisyos/foundry/methods/README.md`, `src/polisyos/foundry/calibration/README.md`, `src/polisyos/foundry/agent_sim/README.md`                                                                                                                                                                                                                            | package facades, catalog/method boundaries, calibration loops, agent-sim runtime boundary                                                                      | quickstart snippet above plus the relevant package-local pytest slices referenced from each README                                                                                                                                                                                                                                                                                                                   |

## Public Surface

| Export              | Role                                                                                                      |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| `compile()`         | Compile a Trinity bundle into `foundry.program_graph`, `foundry.exec_plan`, and compile report artifacts. |
| `compile_program()` | Compatibility alias for `compile()` on the package facade.                                                |
| `execute()`         | Execute a compiled plan from a `FoundryInputBindingsRef` and persist simulation evidence.                 |

The stable package facade is intentionally narrow. Internal helpers are
documented only where they are part of a tested operational or authoring
workflow.

## Quick Validation

The compile/execute quickstart is runnable, not conceptual:

```bash
uv run python - <<'PY'
from tempfile import TemporaryDirectory
from polisyos.foundry.quickstart import run_trivial_compile_execute

with TemporaryDirectory(prefix="foundry-docs-") as tmp:
    result = run_trivial_compile_execute(cas_root=tmp)
    print(result)
    assert result.compile_ok and result.execute_ok
PY
```

The same path is covered by
`tests/unit/foundry/facade/test_quickstart.py`.

For a compact D1-L3 smoke pass:

```bash
uv run pytest tests/unit/foundry/facade/test_quickstart.py \
  tests/unit/foundry/compile/test_compile_determinism.py \
  tests/unit/foundry/runtime/test_execute_input_bindings.py \
  tests/unit/foundry/runtime/test_nan_guard_public.py \
  tests/unit/foundry/calibration/test_measurement.py \
  tests/unit/foundry/methods/backends/test_numerical_stability.py -q
```

## Backlog

| Gap                                         | Priority | Tracking note                                                                                                                                                   |
| ------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No missing required D1-L3 output pages      | -        | All required D1-L3 files are present and mapped above.                                                                                                          |
| Standalone generated capability-matrix page | P2       | D2 now uses generated method-snapshot inputs inside the methods/observability reference pages. A dedicated standalone capability-matrix page is still optional. |
