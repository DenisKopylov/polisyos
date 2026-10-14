# English reader translation of ADR-0006: SLO definitions for the Scientist DAG

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0006-slo-definitions.md`

This page translates the decision text in the [source ADR](../../adr/0006-slo-definitions.md), whose SHA-256 is
`6e9a0ef9b3cdf9b044f3cd002d909cf804eab8a1d3dee2fdfabbfffef68c570e`.
The generated ADR index reports the source status as `accepted` at the source
pin. This derivative does not ratify or revise the decision and does not
establish that the decision was implemented.

- **Date:** 2026-02-06
- **Status in source:** Accepted
- **Decision:** Formalize SLO metrics and alerting for the Scientist DAG,
  simulations, and connectors.

## Context

Before this change, observability covered operational metrics
(`workflow_runs_total`, `llm_tokens_total`,
`governance_pass_duration_seconds`) but did not have contract SLO metrics
for production readiness.

## Decision

Add these metrics:

- `polisyos_slo_dag_runs_total` (status/workflow_id/env)
- `polisyos_slo_dag_duration_seconds` (workflow_id/env)
- `polisyos_slo_run_cost_usd` (workflow_id/env)
- `polisyos_slo_simulation_nan_total` (method/env)
- `polisyos_slo_simulation_runs_total` (method/status/env)
- `polisyos_slo_connector_requests_total` (connector_id/status/env)

Add recording rules and alerts for:

- DAG success rate (5m/30m)
- DAG p99 latency
- run cost p95
- simulation NaN rate
- connector error rate

Add a Grafana dashboard: `ops/observability/grafana/dashboards/slo-overview.json`.

## Targets

- DAG Success Rate: `>= 95%` (30m)
- DAG p99 Latency: `<= 300s`
- Simulation NaN Rate: `< 0.1%`
- Connector Error Rate: `< 1%`

## Consequences

### Advantages

- A formal SLO and alerting contour is introduced.
- Metrics are associated with workflow / environment and are usable for error
  budget practices.

### Disadvantages

- Telemetry volume and the number of rule evaluations increase.

### Risks

- A lack of traffic may produce NaN / empty series in derived metrics.

### Mitigations

- Add a guard to the rules with `clamp_min(...)` and volume checks
  (`...:rate30m > 0`).

## Related Decisions

- Extended by: ADR-0116 (OTel-first observability).
- Related: ADR-0127 (repository hygiene gates).
