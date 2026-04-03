# Engine (`polisyos.scientist.engine`)

`engine` — workflow runtime Scientist: state model, DAG execution, checkpoint/resume,
idempotency, runner backends, fan-out/subworkflow utilities и trace metadata.

## Роль в системе

- **Зависит от:** `core.artifacts`, `core.observability`, builtin node protocols
- **Используется в:** `scientist.api`, `scientist.workflows`, replay/resume flows
- Пакет задает execution semantics для всего Scientist orchestration stack.

## Ключевые концепции

- **ExperimentState** — строгая модель run-state.
- **WorkflowSpec / NodeInvocation** — декларативное описание DAG.
- **WorkflowExecutor** — основной runtime executor, plus async and remote variants.
- **Checkpoint + run lock** — safe resume и workflow fingerprint validation.
- **Idempotency** — state-slice based cache contract для node outcomes.
- **Runner backends** — local, fallback, temporal, ray and related orchestration helpers.

## Public API

- `ExperimentState`, `WorkflowSpec`, `NodeInvocation`
- `Node`, `NodeSpec`, `NodeOutcome`, `NodeError`, `NodeStatus`
- `WorkflowExecutor`, `AsyncWorkflowExecutor`
- `resume_from_checkpoint(...)`, `acquire_run_lock(...)`,
  `compute_idempotency_key(...)`, `discover_nodes(...)`
- Runner/config surfaces: `WorkflowRunnerBackend`, `WorkflowRunnerConfig`,
  `build_workflow_runner(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 52
- Exports: 89
- README расширен, чтобы отражать checkpoint/idempotency/runner surface,
  а не только базовый executor
