# Workflows Layer (`polisyos.scientist.workflows`)

`workflows` собирает и запускает workflow-спецификации Scientist поверх `engine`.

## Роль

- определяет канонические DAG-спеки (`scientist_default`, `scientist_causal_full`);
- строит `ExecutionContext` (run context + tenant/cell/access scope + adapters);
- формирует `NodeRegistry` (builtin + discovered plugins);
- запускает `WorkflowExecutor` под `run.lock` и checkpoint policy.

## Ключевые файлы

- `default.py` — `default_workflow_spec()` (`scientist_default`).
- `causal_full.py` — `causal_full_workflow_spec()` (`scientist_causal_full`).
- `builder.py`
  - `run_default_workflow(...)`
  - `run_causal_full_workflow(...)`
  - `build_execution_context(...)`
  - `build_registry_with_builtin_nodes(...)`
  - `build_default_registry(...)`
- `engine_base.py` — protocol `WorkflowEngine`/`WorkflowEngineFactory`.
- `engine_simple.py` — lightweight `SimpleLoopEngine`.
- `engine_langgraph.py` — compatibility adapter для legacy LangGraph path.

## Актуальные DAG

`scientist_default`:
- data branch: `build_data_snapshot -> bind_foundry_inputs -> run_data_plane_gate`;
- planning branch: `build_execution_plan -> build_method_catalog_snapshot -> run_preflight -> ready_to_run`;
- execute branch: `link_trinity -> compile_foundry -> resolve_parameters -> run_simulation`;
- analysis/governance: `run_distributional_analysis`, `propagate_uncertainty`, `run_causal_evaluation`, `run_governance`, `run_evaluator`, `build_decision_packet`.

`scientist_causal_full` добавляет causal-ноды:
- `build_literature_prior`
- `reconcile_causal_graph`
- `run_causal_queries`
- `run_causal_ensemble`
- `run_abm_consistency`
- `run_transportability`

Обе спецификации работают с `error_policy="continue"`.

## Расширяемость

`build_registry_with_builtin_nodes(include_discovered_nodes=True)`:
- всегда подключает engine/scientist builtin nodes;
- дополнительно загружает plugin-ноды из `ENTRY_POINT_GROUP_SCIENTIST_NODES`.

## Эксплуатационные нюансы

- `run_id` автогенерируется при пустом значении;
- `registry_bundle_ref` создается автоматически при отсутствии;
- обязателен хотя бы один input snapshot-источник:
  - `data_snapshot_ref`, или
  - `input_bindings_ref`, или
  - `data_view_request_ref`;
- запуск и resume защищены `.polisyos/runs/<run_id>/run.lock`;
- checkpoint policy: `off | strict | best_effort`.
