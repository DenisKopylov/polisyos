# Foundry Compile and Execute
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The compile/execute surface is the narrow public entry point into Foundry.
`compile()` turns a Trinity-backed policy bundle into CAS artifacts that define
the runtime program, while `execute()` replays that program from a bound
synthetic state snapshot and persists simulation outputs.

## When to call which API

- Call `compile()` when a Scientist or Trinity workflow has produced a new bundle and you need a replayable `ExecPlanRef`.
- Call `build_input_bindings()` after structure is fixed and you are ready to bind registry-backed datasets into concrete `GlobalState` inputs.
- Call `execute()` once both an `exec_plan_ref` and `input_bindings_ref` exist and you want durable evidence: simulation results, metrics, state deltas, and constraint diagnostics.

## Runtime Contract

- `compile()` is deterministic for identical Trinity bundle, registry bundle,
  and compile flags. Unsupported bundle kinds or compile failures return
  `CompileResult(ok=False, exec_plan_ref=None, compile_report_ref=...)` instead
  of raising at the facade boundary.
- `execute()` expects `ExecuteRequest.input_bindings_ref` to reference a
  `FoundryInputBindings` artifact produced by `build_input_bindings()`. It
  persists `foundry.simulation_result`, `metrics`, `state_delta`, and optional
  `constraint_report` / `environment_manifest` artifacts.
- Runtime failures that reflect unsupported mechanisms or hard constraint
  violations are returned as `ExecuteResult(ok=False, notes=[...])`; malformed
  requests and missing `registry_bundle_ref` are raised as regular exceptions.

## Flow

| Step | API | Output |
|------|-----|--------|
| Compile | `polisyos.foundry.compile()` | `CompileResult` with `exec_plan_ref` |
| Bind data | `build_input_bindings()` | `FoundryInputBindingsRef`, bound `StateSnapshotRef` |
| Execute | `polisyos.foundry.execute()` | `ExecuteResult` with `SimulationResultRef` |

## Operational Notes

- `CompileResult.exec_plan_ref` is the hand-off object downstream runners, replay tooling, and governance reports should persist instead of rebuilding graphs in memory.
- `FoundryInputBindingsRef` is the boundary between structural planning and data readiness. If bindings change, rerun `execute()`; if the Trinity bundle changes, rerun `compile()` first.
- `ExecuteResult` is an evidence-emission receipt. Consumers should treat it as a pointer to persisted artifacts, not as the full payload itself.

## Minimal Flow

```python
compile_result = polisyos.foundry.compile(store, compile_request)
if not compile_result.ok:
    raise RuntimeError(compile_result.notes)

bindings = build_input_bindings(
    store,
    data_snapshot_ref=data_snapshot_ref,
    registry_bundle_ref=registry_bundle_ref,
)

execute_result = polisyos.foundry.execute(
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

## Root API

::: polisyos.foundry

## Compile API

::: polisyos.foundry.compile.api

## Execute API

::: polisyos.foundry.execute.api

## Input Binding Bridge

::: polisyos.foundry.data_plane.bindings
