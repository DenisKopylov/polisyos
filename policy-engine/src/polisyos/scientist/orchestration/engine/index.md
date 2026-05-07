# Generated Index: Scientist Orchestration Engine

Owner: `team-scientist`
Last updated: 2026-05-05

## Subtrees And Groups

| Path or Group | Role |
| --- | --- |
| `builtins/` | Engine-local builtins such as emit artifact, noop, and set state. |
| `locks/` | Lock protocol implementations and lock configuration. |
| `runner/` | Runner helpers for workflow execution. |
| Protocol | `protocol.py`, `workflow_spec.py`, `context.py`, `state.py` |
| Reliability | `checkpoint.py`, `retry.py`, `circuit_breaker.py`, `idempotency.py` |
| Execution | `executor.py`, `async_executor.py`, `fan_out.py`, `sub_workflow.py` |
| Observability | `telemetry.py`, `metrics.py`, `trace_attributes.py`, `operational_monitoring.py` |

## Tests

Primary tests live under `tests/unit/scientist/`.
