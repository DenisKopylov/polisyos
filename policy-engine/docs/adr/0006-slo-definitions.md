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

Добавлен Grafana dashboard: `ops/grafana/dashboards/slo-overview.json`.

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
