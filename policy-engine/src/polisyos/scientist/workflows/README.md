# Workflows (`polisyos.scientist.workflows`)

`workflows` описывает и запускает канонические Scientist DAG-спеки, строит
execution context, собирает registry нод и вызывает `WorkflowExecutor`.

## Роль в системе

- **Зависит от:** `engine`, `nodes`, `adapters`, `governance`, `core`
- **Используется в:** `run_experiment()`, runtime control flows, policy-design/discovery launchers
- Пакет соединяет декларативные `WorkflowSpec` с реальным execution context и builtin registry.

## Ключевые концепции

- **Canonical specs** — `scientist_default`, `scientist_causal_full`,
  `scientist_discovery`, `scientist_policy_design`.
- **Builder layer** — сбор `ExecutionContext`, registry и workflow selection logic.
- **Engine adapters** — `SimpleLoopEngine` и legacy-compatible `LangGraphEngine`.
- **Causal readiness integration** — `scientist_causal_full` теперь запускает
  `run_causal_readiness` перед governance/decision surfaces.
- **C6c policy design** — `policy_design.py` добавил literature prior, reconciliation,
  hierarchical policy search, readiness и counterfactual gate.

## Public API

- `run_default_workflow(...)`, `run_causal_full_workflow(...)`,
  `run_discovery_workflow(...)`, `run_policy_design_workflow(...)`,
  `run_selected_workflow(...)`
- `build_execution_context(...)`, `build_default_registry(...)`,
  `build_registry_with_builtin_nodes(...)`, `resolve_workflow_id(...)`
- `default_workflow_spec()`, `causal_full_workflow_spec()`,
  `discovery_workflow_spec()`, `policy_design_workflow_spec()`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 11
- Exports: 18
- Недавний delta: `policy_design.py` и `causal_full.py` расширены новым causal-readiness
  и hierarchical-search path
