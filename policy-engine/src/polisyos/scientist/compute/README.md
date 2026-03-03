# Compute Layer (`polisyos.scientist.compute`)

`compute` — адаптер исполнения вычислительных job-ов для Scientist (legacy program и method-based path).

## Состав

- `job_spec.py`
  - `JobSpec` — контракт job-а (`job_kind`, refs, method params, seed, input refs);
  - `JobKey` — стабильный ключ дедупликации/кеша по canonical payload;
  - `JobResult` — ссылки на выходные artifacts, warnings/issues.
- `runner.py`
  - `run_job(...)` — единая точка запуска;
  - `LocalBackend` — legacy execute через `foundry.executor`;
  - `MethodBackend` — запуск Foundry methods через dispatcher/registry;
  - materialization bridge `scientist.unified_dag_adapter` для method path.

## Режимы выполнения

- `job_kind="legacy_program"`
  - ожидает `program_ref`, `exec_plan_ref`, `state_snapshot_ref`/`base_state`;
  - возвращает refs на `state_delta`, `metrics`, `state_snapshot`, `simulation_results`.
- `job_kind="method"` (или задан `method_fqn`)
  - вызывает method dispatcher;
  - сохраняет `scientist.method_result` и `scientist.method_evidence`;
  - поддерживает подзагрузку `input_refs` из CAS.

## Где используется

- `nodes/builtins/simulate/run_causal_evaluation.py`
- `nodes/builtins/causal/run_causal_queries.py`
- `nodes/builtins/causal/run_causal_ensemble.py`

Именно эти ноды используют `compute` для method-ориентированных causal этапов.

## Связи

- `foundry.executor` и `foundry.methods.*` — фактический runtime backend;
- `core.artifacts`/CAS — persistence всех результатов;
- `ir.governance.validation` — единый формат issues при runtime ошибках.
