# SLO and Error Budget Policy

Related ADR: [ADR-0006](../../adr/0006-slo-definitions.md). Related reference:
[Observability Topology](observability-topology.md). Related runbooks:
[Runtime API Outage](../../runbooks/runtime-api-outage.md),
[Canary Rollback or Failed Promotion](../../runbooks/canary-rollback-or-promotion-failure.md).

Owner: `@platform-owners`
Source of truth: `docs/reference/operations/observability-topology.md`, linked runbooks, `tools/devx/workspace/acceptance_audit.py`, and the repo-tracked workflows that exercise runtime/performance gates
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; source inspection only. Targets are policy definitions, not measured current service levels; no telemetry or dashboard was read.
The command rows below describe intended repository gate coverage; those
commands and workflows were not executed for this update.

> This page establishes a shared vocabulary for deciding when reliability is
> “good enough,” when feature work can proceed, and when the platform must pause
> to restore reliability.

## Service-Level View

This policy covers three operational service surfaces around the runtime and control plane:

| Service surface                 | User promise                                                                           | Primary signals                                                                               | Primary owner                                                 |
| ------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Runtime API read surface        | Health, readiness, runs, artifacts, and operator read APIs are available and truthful  | synthetic `/health`, `/ready`, request success/error/latency, trace/log correlation           | `@runtime-owners`                                             |
| Control-plane write surface     | `POST /api/v1/control/*` creates and advances jobs without silent stalls               | job admission success, DAG success rate, outbox/worker health, queue age, timeline continuity | `@runtime-owners` + `@scientist-owners`                       |
| Critical execution dependencies | LLMs, connectors, authz, state store, and security gates do not silently break runtime | connector error rate, agent errors, SBOM/security signals, dependency-specific dashboards     | affected subsystem owner with `@platform-owners` coordination |

## Acceptance and Runtime Gates

Repository-defined SLO review is tied to the executable gates listed below,
not only to dashboards. This source map does not report measured availability.
The acceptance audit and release gate should be read together when runtime
availability, auth, tenant isolation, OpenAPI, or control-plane write semantics
change.

| Gate                         | Command or workflow                                                                                                                                                                                            | Documented purpose                                                                                        |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Runtime OpenAPI contract     | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`                                                                                            | checks committed OpenAPI, generated client, examples, problem payloads, and contract invariants           |
| Auth and tenant middleware   | `uv run pytest -q tests/unit/core/security/test_auth_middlewares.py tests/unit/core/security/test_router.py tests/unit/core/security/test_tenant_context.py tests/unit/runtime/http/test_runtime_api_authz.py` | exercises documented JWT, tenant/cell routing, OPA denial, timeout, and fail-closed access paths          |
| Runtime write path           | `uv run pytest -q tests/unit/runtime/http/test_runtime_api_write_path_hardening.py tests/unit/runtime/http/test_control_hardening.py`                                                                          | exercises documented idempotency, rate limiting, mutation audit, dependency timeouts, and lifecycle paths |
| Core-runtime closeout ledger | `uv run polisyos-tools workspace core-runtime-closeout` and `uv run polisyos-tools workspace core-runtime-long-soak`                                                                                           | emits the repo-tracked ledger's closeout and long-soak evidence when run with its prerequisites           |
| Platform acceptance audit    | `uv run polisyos-tools workspace acceptance-audit`                                                                                                                                                             | checks repository acceptance references and emits an audit result when run                                |

## Initial SLO Set

These SLO targets are intended to use repository-defined signals or simple
synthetic checks; no current measurement is asserted here.

Repository-defined recording/alerting rules for runtime API, control-plane
admission, and DAG/simulation/connector SLOs live in
`ops/observability/prometheus/slo_*`; this does not show that they are deployed
or receiving telemetry.

| SLO                         | Target                                            | Measurement                                                                                                | Notes                                                                 |
| --------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Runtime API availability    | `>= 99.5%` over 30d                               | synthetic `/health` + `/ready` + request success rate for user-facing read APIs                            | user-facing read surface                                              |
| Runtime API latency         | `p95 <= 750ms`, `p99 <= 1500ms` for read APIs     | ingress/runtime request metrics + traces                                                                   | measure excluding locally induced test traffic                        |
| Control-plane job admission | `>= 99.0%` over 30d                               | successful `POST /api/v1/control/*` admissions and durable job creation                                    | errors caused by invalid user payloads excluded                       |
| Scientist DAG success       | `>= 95%` over rolling 30m and release review      | `polisyos_slo_dag_success_rate:rate30m`                                                                    | repository rule/metric definition; no current observed value asserted |
| Scientist DAG latency       | `p99 <= 300s`                                     | `polisyos:slo_dag_p99_latency_seconds:5m`                                                                  | from ADR-0006                                                         |
| Simulation numerical health | NaN rate `< 0.1%`                                 | `polisyos:slo_simulation_nan_rate:rate5m`                                                                  | from ADR-0006                                                         |
| Connector reliability       | error rate `< 1%` per connector/env               | `polisyos:slo_connector_error_rate:rate5m`                                                                 | from ADR-0006                                                         |
| Docs publication freshness  | successful strict build on the reviewed docs tree | `.github/workflows/docs-pages.yml`, `.github/workflows/abi.yml`, or local `mkdocs build --strict` evidence | source presence is not a build or publication result                  |

## Error Budget Model

This policy uses a rolling 30-day error budget per SLO-bearing surface.

- Budget size = `1 - SLO target`.
- Burn is measured against user-visible failure, not internal discomfort.
- One incident may spend budget for more than one surface.
- Budget accounting is reviewed at least weekly and at every failed promotion.

### Response Bands

| Budget remaining | Response                                                                                     |
| ---------------- | -------------------------------------------------------------------------------------------- |
| `> 50%`          | Normal feature delivery. Reliability work still tracked, but not mandatory freeze.           |
| `25% - 50%`      | Caution. New risky rollout classes require explicit owner acknowledgement and rollback plan. |
| `0% - 25%`       | Reliability-first. Platform owners may defer non-critical feature work on affected surfaces. |
| `<= 0%`          | Release freeze for the affected surface until recovery plan approved and burn stabilizes.    |

## Release-Freeze Policy

When the rolling error budget for a service surface is exhausted:

- new feature promotions on that surface pause;
- dependency upgrades, migrations, and infra changes on that surface pause unless
  they are part of recovery;

- platform review must explicitly approve any exception.

### Explicit Carve-Outs

Even under freeze, the following remain allowed:

- security fixes with clear risk reduction;
- P0 restoration work required to return service;
- actions needed to complete rollback or stop further budget burn;
- observability-only changes that improve detection without increasing blast radius.

## Default Postmortem Trigger

Default rule until a service chooses tighter numbers:

- any single incident that spends `>= 20%` of a rolling 30-day error budget
  requires a blameless postmortem;

- any incident that causes rollback, failed promotion, or manual release hold
  requires a postmortem regardless of computed burn;

- repeated smaller incidents with common root cause may be merged into one
  postmortem only if a single owner accepts responsibility for the combined fix.

## Ownership for Alerts and Interpretation

| Signal family                                | Interpreting owner        | Coordination owner |
| -------------------------------------------- | ------------------------- | ------------------ |
| runtime health, request errors, control jobs | `@runtime-owners`         | `@platform-owners` |
| DAG success, governance, agent errors        | `@scientist-owners`       | `@platform-owners` |
| simulation, HPC, numerical stability         | `@foundry-owners`         | `@platform-owners` |
| connectors, replay/data ingestion            | `@fabric-owners`          | `@platform-owners` |
| security, signing, SBOM, TEE                 | security/compliance owner | `@platform-owners` |
| docs publishing and docs freshness           | `@docs-owners`            | `@platform-owners` |

## Decision Rules

- If the signal is user-facing and trustworthy, responders act first and debate
  nuance later.

- If signal trust is uncertain, the first mitigation is to confirm signal
  quality, not to ignore it.

- Reliability exceptions must name an owner, scope, and expiry date.

## Review Cadence

- weekly: error-budget review on all currently active surfaces;
- pre-promotion: explicit “budget allows this rollout” check;
- quarterly: service targets re-tuned based on actual traffic and incident data.
