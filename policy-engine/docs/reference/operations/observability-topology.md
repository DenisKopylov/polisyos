# Observability Topology

Related reference: [Ownership](../ownership.md). Related ops assets:
`ops/prometheus/alerts.yml`, `ops/prometheus/slo_alerts.yml`,
`ops/grafana/dashboards/*.json`.

> Observability в Phase 6 считается завершённой не тогда, когда “данные где-то
> есть”, а тогда, когда понятно, какой сигнал trusted, где его смотреть и кто
> обязан отреагировать.

## Signal Taxonomy

| Signal type | Purpose | Current anchors | Owner |
|---|---|---|---|
| Traces | Request and workflow causality, latency decomposition, dependency hops | `polisyos.core.observability.tracer`, runtime traces, distributed context propagation | `@platform-owners` + service owner |
| Metrics | Fast SLO evaluation, alerting, capacity, burn-rate decisions | Prometheus metrics, recording rules, SLO alerts, domain alerts | service owner |
| Logs | Detailed failure context and operator breadcrumbs | structured runtime/frontend logs with correlation fields | service owner |
| Security events | Cross-tenant incidents, TEE, SBOM, signing, authz decisions | `security-phase4` dashboard, security alert families | security/compliance owner |
| Frontend UX telemetry | Browser-side route readiness, error capture, operator-perceived failures | Sentry, route/performance telemetry, platform dashboard UX | `@frontend-owners` |

## Golden Signal Coverage

### User-Facing / Runtime Services

| Surface | Latency | Traffic | Errors | Saturation |
|---|---|---|---|---|
| Runtime API read surface | request duration traces/metrics | request rate by route/env | `5xx`, health/readiness failures | worker pool pressure, state-store latency, app saturation |
| Control-plane write surface | job admission latency, DAG duration | run/job submit rate | failed jobs, outbox failure, worker errors | queue age, worker lease starvation, state-store contention |
| Frontend operator UX | route load and page-ready timing | active dashboard page loads | browser errors, failed data fetches | bundle size, slow rendering, client-side retry storms |

### Critical Dependencies

| Dependency class | Trusted signals | Owning responder |
|---|---|---|
| Connectors / external data APIs | connector error rate, replay parity, last health check | `@fabric-owners` |
| LLM gateway / agent path | workflow error spike, cost alerts, trace failures | `@scientist-owners` |
| Security sidecars / controls | authz failures, TEE failure rate, SBOM deny rate | security/compliance owner |
| Docs publication | docs-pages workflow, local `mkdocs build --strict` reproduction | `@docs-owners` |

## Dashboard Inventory

| Dashboard | File | Purpose | Owner |
|---|---|---|---|
| Executive Overview | `ops/grafana/dashboards/executive-overview.json` | platform-wide posture and leadership signal | `@platform-owners` |
| SLO Overview | `ops/grafana/dashboards/slo-overview.json` | shared SLO view across runtime API, control-plane, DAG, simulation, connectors | `@platform-owners` with service owners |
| Scientist Agents | `ops/grafana/dashboards/scientist-agents.json` | workflow/agent behavior and orchestration health | `@scientist-owners` |
| Foundry HPC | `ops/grafana/dashboards/foundry-hpc.json` | numerical/runtime compute signal | `@foundry-owners` |
| Knowledge Freshness | `ops/grafana/dashboards/knowledge-freshness.json` | evidence freshness and connector/data signal | `@fabric-owners` |
| Security Phase 4 | `ops/grafana/dashboards/security-phase4.json` | authz, TEE, SBOM, security posture | security/compliance owner |

## Alert Family Inventory

| Alert family | Source | Examples | Primary owner |
|---|---|---|---|
| SLO alerts | `ops/prometheus/slo_alerts.yml` | runtime API availability/latency, control-plane admission, DAG success breach, NaN rate, connector error rate | service owner named by label/team |
| Cost alerts | `ops/prometheus/alerts.yml` | `HighLLMCost*` | `@platform-owners` |
| Agent / governance alerts | `ops/prometheus/alerts.yml` | `AgentErrorSpike*`, `GovernancePassSlowdown` | `@scientist-owners` |
| Simulation alerts | `ops/prometheus/alerts.yml` | `SimulationStall`, `JITRecompilationStorm*`, `LowCacheHitRatio` | `@foundry-owners` |
| Security alerts | `ops/prometheus/alerts.yml` | cross-tenant, TEE, SBOM gate alerts | security/compliance owner |
| Cell / routing alerts | `ops/prometheus/alerts.yml` | routing failures and latency | `@platform-owners` |

## Route From Alert to Action

Phase 6 standard flow:

1. Alert fires.
2. Responder opens owning dashboard family.
3. Responder pivots into correlated traces/logs using shared identifiers.
4. Responder opens the matching runbook.
5. Incident timeline records the path used.

### Canonical Mapping

| Alert type | Dashboard | Correlation pivot | Runbook |
|---|---|---|---|
| Runtime availability / latency | `executive-overview`, `slo-overview` | `request_id`, `trace_id`, `route`, `env`, `release` | [Runtime API Outage](../../runbooks/runtime-api-outage.md) |
| DAG / governance / agent failures | `slo-overview`, `scientist-agents` | `run_id`, `job_id`, `workflow_id`, `trace_id` | [Runtime API Outage](../../runbooks/runtime-api-outage.md) |
| Connector / replay failures | `slo-overview`, `knowledge-freshness` | `connector_id`, `replay_ref`, `artifact_id`, `env` | [Replay or Restore Workflow](../../runbooks/replay-or-restore.md) |
| SBOM / signing / TEE alerts | `security-phase4` | `artifact_id`, `key_id`, `signer_identity`, `release` | [Artifact Signing or SBOM Failure](../../runbooks/artifact-signing-sbom-failure.md) |
| Docs publication alerts | CI run + local `mkdocs build --strict` reproduction | workflow run ID, commit SHA, docs path | [Docs Publication Failure](../../runbooks/docs-publication-failure.md) |
| Benchmark regressions | release summary + suite reports | `suite_id`, `run_id`, `profile`, `baseline_snapshot_ref` | [Benchmark Regression Triage](../../runbooks/benchmark-regression-triage.md) |

## Trace / Log Correlation Policy

All incident-relevant telemetry should allow responders to pivot using a shared
identifier set.

### Required Correlation Fields

- `trace_id`
- `span_id`
- `request_id`
- `run_id`
- `job_id`
- `workflow_id`
- `artifact_id` when artifact-producing
- `connector_id` for data-plane incidents
- `env`
- `release` / commit SHA where available

### Cardinality Rules

- low-cardinality dimensions go in metrics labels: `env`, `workflow_id`,
  `connector_id`, templated `route`, `team`, `decision`;
- high-cardinality identifiers stay in logs/traces/events: `request_id`,
  `trace_id`, `artifact_id`, `run_id`, `job_id`;
- do not “fix” an incident by adding unbounded labels to Prometheus metrics;
- if a new metric explodes label cardinality, it needs explicit platform owner
  approval and a cost note.

## Alert Validation Strategy

Critical alerts must be periodically proven alive.

| Signal | Validation strategy |
|---|---|
| runtime availability alerts | synthetic `/health` and `/ready` checks against known-good deployment path |
| contract/codegen drift | `./scripts/doctor` plus dedicated contract checks on clean workspace |
| replay failures | known-good record/replay fixture path from `tests/fabric/data_plane/test_record_replay.py` |
| docs publication | local `mkdocs build --strict` and green `Docs Pages` workflow from `main` |
| security alerts | focused test fixtures for signing/SBOM plus staged verification against trusted keys |

Until an external synthetic platform is added, CI-backed known-good emitters are
the minimum validation layer.

## Ownership for Silent Failures

These silent failures are explicitly owned even when no human customer reports
them first:

| Silent failure class | Owner |
|---|---|
| docs publishing stalls or site staleness | `@docs-owners` |
| codegen drift and stale generated contracts | `@platform-owners` |
| replay failures and restore regressions | `@fabric-owners` with `@platform-owners` |
| control-plane degradation without hard outage | `@runtime-owners` |

## Telemetry Cost Discipline

- add metrics only when someone can name the question they answer;
- default to sampled traces and structured logs for high-cardinality detail;
- remove stale dashboards and duplicate alerts during quarterly platform review;
- prefer one trusted dashboard per family over many half-maintained views.
