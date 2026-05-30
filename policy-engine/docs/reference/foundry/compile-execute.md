# Foundry Compile and Execute

Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The compile/execute surface is the narrow public entry point into Foundry.
`compile()` turns a Trinity-backed policy bundle into replayable CAS artifacts,
while `execute()` replays the compiled plan from a bound `GlobalState` snapshot
and persists simulation evidence.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/__init__.py`, `src/polisyos/foundry/compile/api.py`, `src/polisyos/foundry/execute/api.py`, `src/polisyos/foundry/data_plane/bindings.py`, `src/polisyos/foundry/quickstart.py`

## Phase Coverage

| Source phase | Compile/execute meaning                                                                                                                                               |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0      | Non-critical runtime expansion is frozen behind the Trinity-only facade and default registry bundle.                                                                  |
| Phase 1      | Facade failures return structured `CompileResult` or `ExecuteResult` envelopes where the contract says they should; malformed requests still raise validation errors. |
| Phase 2      | ProgramGraph, ExecPlan, state delta, and snapshot hand-offs are the hardened kernel boundary.                                                                         |
| Phase 3      | Execution posture carries NaN guard and determinism metadata; numeric claims are verified through the numeric/JAX tests linked below.                                 |
| Phase 4      | Identical CAS inputs, registry bundle, seed, and execution config are the replay unit for reproducibility checks.                                                     |

## When to Call Which API

- Call `compile()` when a Scientist or Trinity workflow has produced a new
  `ir.trinity_bundle` and you need an `ExecPlanRef`.

- Call `build_input_bindings()` after structure is fixed and a data snapshot is
  ready to bind into concrete `GlobalState` inputs.

- Call `execute()` once both `exec_plan_ref` and `input_bindings_ref` exist and
  you need durable evidence: simulation result, metrics, state delta, constraint
  diagnostics, and optional environment metadata.

- Call `execute(..., feedback_config_ref=...)` when the run must solve a
  compact feedback fixed point before producing the final `SimulationResult`.
  In that mode the facade emits additional derived artifacts:
  `feedback_trace`, `feedback_convergence_certificate`,
  optional `feedback_jacobian_diagnostics`, and `feedback_result`.

- Set `FeedbackSolverConfig.detect_multiplicity=True` when a feedback solve
  should also produce a structured equilibrium multiplicity report. The report
  is persisted as `foundry.equilibrium_multiplicity_report`, attached to
  `FeedbackSolveResult.multiplicity_report_ref`, and exposed through the
  runtime debug endpoint `/api/v1/debug/runs/{run_id}/equilibria`.

## Runtime Contract

- `compile()` accepts `input_kind="trinity"` or `input_kind="auto"` for
  `policy_ref.kind == "ir.trinity_bundle"`.

- Unsupported compile requests produce `CompileResult(ok=False,
exec_plan_ref=None, compile_report_ref=...)` instead of raising at the facade
  boundary.

- `execute()` requires `ExecuteRequest.input_bindings_ref`; this is validated by
  `tests/unit/foundry/runtime/test_execute_requires_input_bindings_ref.py`.

- `execute()` requires `registry_bundle_ref` and raises `ValueError` when it is
  absent, because runtime mechanism resolution must be explicit.

- `ExecuteRequest.feedback_config_ref` is optional and opt-in. When omitted,
  `execute()` replays exactly one static run as before.

- Fixed-point feedback mode returns solver failures as `ExecuteResult(ok=False)`
  with durable feedback artifacts whenever possible. Non-convergence does not
  erase the residual trace or convergence certificate.

- Multiplicity discovery is additive. Existing feedback runs are unchanged
  unless `detect_multiplicity=True` or `multiplicity_mode != "off"`. The first
  production path runs bounded multi-start exploration, clusters fixed points,
  classifies local stability from the Jacobian, flags fold/flip/loss-of-stability
  candidates, and optionally estimates basin shares with Wilson intervals.
  Research callers can provide a continuation map factory to
  `discover_equilibria(...)`; the explorer then walks `continuation_grid` with
  pseudo-arclength predictors and records nearest-neighbor branch metadata in
  `EquilibriumMultiplicityReport.branches`.

- Unsupported runtime mechanisms and hard constraint failures return
  `ExecuteResult(ok=False, notes=[...])` envelopes.

## Artifact Flow

| Step                  | API                                                                                        | Primary output                                         |
| --------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| Compile               | `polisyos.foundry.compile(store, request)`                                                 | `CompileResult.exec_plan_ref`                          |
| Bind data             | `build_input_bindings(store, data_snapshot_ref=..., registry_bundle_ref=...)`              | `FoundryInputBindingsRef` and bound `StateSnapshotRef` |
| Execute               | `polisyos.foundry.execute(store, request)`                                                 | `ExecuteResult.simulation_result_ref`                  |
| Execute with feedback | `polisyos.foundry.execute(store, request.model_copy(update={"feedback_config_ref": ...}))` | `SimulationResult` plus `feedback_*` derived artifacts |
| Multiplicity report   | `FeedbackSolverConfig.detect_multiplicity=True`                                           | `foundry.equilibrium_multiplicity_report`              |

The downstream contract is refs, not in-memory objects. Consumers should persist
`CompileResult.exec_plan_ref`, `FoundryInputBindingsRef`, and
`ExecuteResult.simulation_result_ref` rather than rebuilding graphs from local
process state.

## Runnable Quickstart

This quickstart is verified against the current code path and is not
conceptual:

```bash
uv run python - <<'PY'
from tempfile import TemporaryDirectory
from polisyos.foundry._quickstart import run_trivial_compile_execute

with TemporaryDirectory(prefix="foundry-docs-") as tmp:
    result = run_trivial_compile_execute(cas_root=tmp)
    print(result)
    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.exec_plan_artifact_id is not None
    assert result.simulation_result_artifact_id is not None
PY
```

`run_trivial_compile_execute()` pins the docs path to CPU by default via
`JAX_PLATFORMS=cpu` and `JAX_PLATFORM_NAME=cpu` unless the caller already set
those variables.

Expected shape:

```text
QuickstartRunResult(...) with `compile_ok=True`, `execute_ok=True`, and
non-null `exec_plan_artifact_id` / `simulation_result_artifact_id`.
```

The same helper is covered by
`tests/unit/foundry/facade/test_quickstart.py`.

Feedback-enabled quickstart:

```bash
uv run python - <<'PY'
from tempfile import TemporaryDirectory
from polisyos.foundry._quickstart import run_feedback_compile_execute

with TemporaryDirectory(prefix="foundry-feedback-docs-") as tmp:
    result = run_feedback_compile_execute(cas_root=tmp)
    print(result)
    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.feedback_result_artifact_id is not None
    assert result.feedback_convergence_certificate_artifact_id is not None
PY
```

Feedback multiplicity quickstart:

```bash
uv run python - <<'PY'
from tempfile import TemporaryDirectory
from polisyos.foundry._quickstart import run_feedback_multiplicity_demo

with TemporaryDirectory(prefix="foundry-multiplicity-docs-") as tmp:
    result = run_feedback_multiplicity_demo(cas_root=tmp)
    print(result)
    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.feedback_result_artifact_id is not None
    assert result.equilibrium_multiplicity_report_artifact_id is not None
PY
```

## Minimal Programmatic Flow

```python
from polisyos.foundry import compile, execute
from polisyos.foundry.data_plane.bindings import build_input_bindings

compile_result = compile(store, compile_request)
if not compile_result.ok:
    raise RuntimeError(compile_result.notes)

bindings = build_input_bindings(
    store,
    data_snapshot_ref=data_snapshot_ref,
    registry_bundle_ref=registry_bundle_ref,
)

execute_result = execute(
    store,
    execute_request.model_copy(
        update={
            "exec_plan_ref": compile_result.exec_plan_ref,
            "input_bindings_ref": bindings.input_bindings_ref,
            "registry_bundle_ref": registry_bundle_ref,
        }
    ),
)
```

Feedback mode follows the same contract but adds one more CAS-backed artifact:

```python
from polisyos.foundry._quickstart import prepare_trivial_feedback_config

feedback_config_ref = prepare_trivial_feedback_config(
    store,
    exec_plan_ref=compile_result.exec_plan_ref,
)

feedback_result = execute(
    store,
    execute_request.model_copy(
        update={
            "exec_plan_ref": compile_result.exec_plan_ref,
            "input_bindings_ref": bindings.input_bindings_ref,
            "registry_bundle_ref": registry_bundle_ref,
            "feedback_config_ref": feedback_config_ref,
        }
    ),
)
```

`FeedbackSolveResult` records `status`, `converged`, `failure_reason`,
`trace_ref`, `convergence_certificate_ref`, optional
`jacobian_diagnostics_ref`, final diagnostics, and any deduplicated
`alternative_fixed_points` found by multi-start solving. If
`FeedbackSolverConfig.budget_diagnostic_id` and `budget_tolerance` are set, the
solver requires both numeric fixed-point convergence and fiscal closure before
marking the run converged.

When multiplicity discovery is enabled, `FeedbackSolveResult` also carries
`multiplicity_report_ref`. The report contains `search_protocol`, clustered
`equilibria`, continuation `branches`, `bifurcation_candidates`,
`basin_estimates`, `unresolved_starts`, and `global_diagnostics`. Basin shares
are properties of the declared start distribution and should not be read as
model-invariant probabilities.

## Evidence Links

- Compile determinism:
  `tests/unit/foundry/compile/test_compile_determinism.py`

- Compile facade:
  `tests/unit/foundry/facade/test_compile_facade.py`

- Execute facade smoke:
  `tests/unit/foundry/facade/test_execute_facade_smoke.py`

- Execute feedback fixed point:
  `tests/unit/foundry/runtime/test_execute_feedback.py`

- Feedback multiplicity explorer:
  `tests/unit/foundry/analysis/test_feedback_fixed_point.py`

- Runtime equilibria endpoint:
  `tests/unit/runtime/http/test_debug_api.py`

- Input bindings:
  `tests/unit/foundry/runtime/test_execute_input_bindings.py`

- Fail-closed executor semantics:
  `tests/unit/foundry/runtime/test_executor_fail_semantics.py`

## Reference

::: polisyos.foundry

::: polisyos.foundry.compile.api

::: polisyos.foundry.execute.api

::: polisyos.foundry.data_plane.bindings

::: polisyos.foundry._quickstart
