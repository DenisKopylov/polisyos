# ADR-0006: SLO Definitions for Scientist DAG

- **Дата**: 2026-02-06
- **Статус**: Accepted
- **Решение**: Формализовать SLO-метрики и alerting для Scientist DAG, симуляций и коннекторов.

## Контекст

До изменения observability покрывала операционные метрики (`workflow_runs_total`, `llm_tokens_total`,
`governance_pass_duration_seconds`), но не имела контрактных SLO-метрик для production readiness.

## Решение

Добавлены метрики:

- `polisyos_slo_dag_runs_total` (status/workflow_id/env)
- `polisyos_slo_dag_duration_seconds` (workflow_id/env)
- `polisyos_slo_run_cost_usd` (workflow_id/env)
- `polisyos_slo_simulation_nan_total` (method/env)
- `polisyos_slo_simulation_runs_total` (method/status/env)
- `polisyos_slo_connector_requests_total` (connector_id/status/env)

Добавлены recording rules и alerts:

- DAG success rate (5m/30m)
- DAG p99 latency
- run cost p95
- simulation NaN rate
- connector error rate

Добавлен Grafana dashboard: `ops/observability/grafana/dashboards/slo-overview.json`.

## Targets

- DAG Success Rate: `>= 95%` (30m)
- DAG p99 Latency: `<= 300s`
- Simulation NaN Rate: `< 0.1%`
- Connector Error Rate: `< 1%`

## Последствия

### Плюсы

- Появился формальный SLO-контур с alerting.
- Метрики привязаны к workflow/env и пригодны для error budget практик.

### Минусы

- Увеличение объёма telemetry и количества rule evaluations.

### Риски

- Отсутствие трафика может давать NaN/empty series в производных метриках.

### Митигации

- В правила добавлен guard через `clamp_min(...)` и volume checks (`...:rate30m > 0`).

## Related Decisions

- Extended by: ADR-0116 (OTel-first observability).
- Related: ADR-0127 (repository hygiene gates).


## E02 clarification — measurement scope (2026-10-25)

The public Scientist API SLI population begins after observability-provider resolution, input/state validation, and workflow_id resolution, immediately before selected-workflow dispatch. It records success/error for results and exceptions caught inside that dispatch wrapper; failures before the wrapper are outside the denominator. The API duration histogram measures selected-workflow dispatch and execution only; it excludes provider/state/workflow resolution and result serialization. API instruments use measurement_scope=scientist_api; orchestration lifecycle observations use measurement_scope=scientist_engine with statuses ok/fail. The API SLO selects only the API scope. For this API SLI, the clamp_min mitigation described above is replaced by a positive-eligible-rate filter: absent or zero eligible rates produce no series, while positive error-only traffic yields zero success when success samples are absent. Other SLI rules retain their existing behavior. This controlled instrumentation change makes no claim about deployed profile selection or production attainment.
