# Nodes (`polisyos.scientist.nodes`)

`nodes` содержит builtin Scientist nodes, которые `engine` регистрирует и исполняет
в workflow DAG. Именно здесь собран фактический runtime surface для data/planning/
compile/causal/simulate/governance/decide этапов.

## Роль в системе

- **Зависит от:** `engine`, `adapters`, `compute`, `governance`, `kernel`, `ir`, `foundry`, `fabric`, `lex`
- **Используется в:** `scientist.workflows`, `NodeRegistry`, runtime execution flows
- Корневая точка входа пакета — `builtin_nodes()`, но основной объем логики живет в `builtins/*`.

## Ключевые концепции

- **NodeSpec** — декларация state reads/writes, produces и metadata для каждой ноды.
- **Builtin families** — `data`, `planning`, `compile`, `causal`, `simulate`, `governance`, `decide`.
- **Causal expansion** — добавлены `CounterfactualIdentificationGateNode`,
  `RunCausalReadinessNode`, `RunCausalContractExecutionNode`.
- **C6c planning path** — добавлен `RunHierarchicalPolicySearchNode` и supporting runtime helpers.
- **State keys** — канонические artifact/report aliases живут в `state_keys.py`.
- **Error contract** — shared node error codes живут в `errors.py`.

## Public API

- `builtin_nodes()` — возвращает полный builtin registry Scientist nodes.
- Root package не re-export-ит отдельные node classes; они импортируются из
  `polisyos.scientist.nodes.builtins.*`.
- Ключевые новые causal nodes находятся в `builtins/causal/`.

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 63
- Root exports: 1 (`builtin_nodes`)
- Недавний delta: causal family теперь покрывает readiness, counterfactual gate
  и contract execution; planning family получила hierarchical policy search
