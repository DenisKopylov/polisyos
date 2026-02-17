# Workflows Layer (`polisyos.scientist.workflows`)

`workflows` — сборка и запуск workflow-спецификаций Scientist поверх `engine`.

## Роль

- определяет default DAG (`default_workflow_spec()`);
- собирает `ExecutionContext` (run context, tenant/cell/access scope, adapters);
- регистрирует builtin и plugin-ноды;
- запускает `WorkflowExecutor` с checkpoint hook и run lock.

## Ключевые файлы

- `default.py` — canonical spec `scientist_default`.
- `builder.py`
  - `run_default_workflow(...)`
  - `build_execution_context(...)`
  - `build_registry_with_builtin_nodes(...)`
  - `build_default_registry(...)`
- `engine_base.py` — protocol `WorkflowEngine`/`WorkflowEngineFactory`.
- `engine_simple.py` — `SimpleLoopEngine` (легкий цикл для search/dev).
- `engine_langgraph.py` — compatibility adapter для legacy LangGraph движка.

## Default DAG

Текущая спецификация включает:
- data path (`build_data_snapshot -> bind_foundry_inputs -> run_data_plane_gate`),
- planning/preflight path (`build_execution_plan -> build_method_catalog_snapshot -> run_preflight -> ready_to_run`),
- compile/simulate/governance/evaluator path,
- финальный `build_decision_packet`.

`error_policy` default spec: `continue`.

## Расширяемость

`build_registry_with_builtin_nodes(include_discovered_nodes=True)`:
- всегда подключает engine/scientist builtin nodes;
- дополнительно сканирует plugin nodes через компонентную группу `ENTRY_POINT_GROUP_SCIENTIST_NODES`.

## Важные эксплуатационные нюансы

- при пустом `run_id` он генерируется автоматически;
- `registry_bundle_ref` автосоздается при отсутствии;
- обязателен хотя бы один источник snapshot (`data_snapshot_ref` или `input_bindings_ref` или `data_view_request_ref`);
- запуск защищен `run.lock` и checkpoint policy (`off|strict|best_effort`).
