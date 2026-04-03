# Foundry (`polisyos.foundry`)

Foundry - вычислительный слой PolicyOS для Trinity compile/execute, registry-driven
method execution, calibration, uncertainty propagation и agent-based simulation.

## Role in System

- **Depends on:** `polisyos.core`, `polisyos.ir`
- **Used by:** `polisyos.scientist`, `polisyos.foundry.plugins`
- Собирает declarative IR в исполняемый runtime-контур с CAS-артефактами, snapshot-ами
  и строгими guardrails.

## Key Concepts

- **Trinity-only execution** - Foundry компилирует и исполняет только `ir.trinity_bundle`.
- **Input bindings** - `data_plane` материализует `FoundryInputBindings` и bound state snapshot.
- **Contracts and state** - `contracts/` задает shared state/machine contracts для runtime.
- **Method catalog** - `methods/` и `methods/catalog/` обеспечивают typed method ABI и dispatch.
- **Micro simulation** - `agent_sim/`, `plugins/` и `wiring/` поддерживают ABM/RL сценарии.
- **Calibration and uncertainty** - `calibration/` и `uncertainty/` работают поверх execution outputs.

## Public API

| Type/Function | Description |
|---|---|
| `compile()` | Компилирует Trinity IR в `ProgramGraph` и `ExecPlan`. |
| `execute()` | Исполняет подготовленный Foundry run и пишет результат в артефакты. |
| `build_input_bindings()` | Строит `FoundryInputBindings` из data snapshot и registry bundle. |
| `execute_program_graph()` | Выполняет ProgramGraph с patch-first semantics. |
| `apply_state_delta_and_snapshot()` | Применяет delta и materializes state snapshot. |

→ Full reference: [docs/reference/foundry/index.md](../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 395 Python files
- Exports: 2
