# Foundry Compile Execute
Related explanation: [Causal Engine](../../explanation/causal-engine.md).

The compile/execute surface is the narrow public entry point into Foundry.
`compile()` turns Trinity-backed input into an execution plan; `execute()`
replays that plan from a bound state snapshot and persists resulting runtime
artifacts.

## Flow

| Step | API | Output |
|------|-----|--------|
| Compile | `polisyos.foundry.compile()` | `CompileResult` with `exec_plan_ref` |
| Bind data | `build_input_bindings()` | `FoundryInputBindingsRef`, bound `StateSnapshotRef` |
| Execute | `polisyos.foundry.execute()` | `ExecuteResult` with `SimulationResultRef` |

## Root API

::: polisyos.foundry

## Compile API

::: polisyos.foundry.compile.api

## Execute API

::: polisyos.foundry.execute.api

## Input Binding Bridge

::: polisyos.foundry.data_plane.bindings
