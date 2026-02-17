# Engine Layer (`polisyos.scientist.engine`)

`engine` — ядро выполнения workflow в `scientist`: строгий state, DAG executor, registry, idempotency, checkpoint/resume.

## Что делает

- валидирует `WorkflowSpec` (уникальные aliases, зависимости, required binds);
- выполняет ноды в topological order;
- пишет run-артефакты (`scientist.workflow_spec`, `scientist.experiment_state`, `scientist.workflow_report`);
- кэширует успешные `NodeOutcome` по idempotency key;
- создает checkpoint после успешных нод и поддерживает resume.

## Ключевые файлы

- `state.py` — `ExperimentState` (`schema_version=1.2`, `extra="forbid"`).
- `protocol.py` — `Node`, `NodeSpec`, `NodeOutcome`, `NodeError`.
- `workflow_spec.py` — `WorkflowSpec`, `NodeInvocation`, `error_policy`.
- `registry.py` — `NodeRegistry`, `discover_nodes()`.
- `executor.py` — `WorkflowExecutor.execute()`.
- `idempotency.py` — `compute_idempotency_key()`, `NodeResultCache`.
- `checkpoint.py` — `CASCheckpointHook`, `resume_from_checkpoint()`, `acquire_run_lock()`.
- `iteration_state_machine.py` — переходы iteration lifecycle для evaluator контура.
- `builtins/` — engine-level ноды `noop`, `set_state`, `emit_artifact`.

## Публичный API

Через `polisyos.scientist.engine` доступны:
- модели/протоколы (`ExperimentState`, `WorkflowSpec`, `NodeSpec`, `NodeOutcome`, ...);
- `WorkflowExecutor`;
- checkpoint/idempotency API (`resume_from_checkpoint`, `compute_idempotency_key`, ...).

## Особенности

- `error_policy`: `fail_fast` или `continue`.
- при `continue` зависимые ноды skip, независимые ветки продолжают выполнение.
- idempotency scope: `run_id + node_id + state_reads + bind params`.
- кэш отключен для `noop/set_state/emit_artifact/enrich_knowledge`.
- cache может восстановиться из run trace и из checkpoint `cache_entry_refs`.
- checkpoint policy: `off | strict | best_effort`.
- run lock файл: `.polisyos/runs/<run_id>/run.lock`.

## Связи

- `workflows/` строит context/registry и запускает executor.
- `nodes/` поставляет бизнес-ноды.
- `core/` дает CAS, run context, discovery и observability.
