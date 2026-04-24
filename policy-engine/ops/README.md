# Ops (`ops/`)

## Purpose

`ops/` описывает эксплуатационный периметр PolicyOS: identity и policy
enforcement, observability, tenant/RLS migrations и infrastructure artifacts
для runtime deployment и recovery.

## Where to Start

- Kubernetes packaging: `ops/helm/README.md`.
- Policy-as-code: `ops/opa/README.md`.
- Metrics/alerts: `ops/prometheus/README.md`.
- SQL tenant isolation chain: `ops/migrations/README.md`.
- Confidential node-pool module: `ops/terraform/README.md`.
- Локальная observability sandbox: `ops/docker-compose.observability.yml`.

## Public Entrypoints

| Surface                                   | Purpose                                                             |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `helm/`                                   | Chart-ы `polisyos-cell`, `spire`, `keycloak` для platform baseline. |
| `opa/policies/*.rego`                     | Runtime authz и deploy gate decisions.                              |
| `prometheus/` + `grafana/`                | Scrape config, alerts, SLO rules и dashboards.                      |
| `migrations/*.sql`                        | Forward/rollback SQL chain для tenant/RLS hardening.                |
| `terraform/modules/confidential_nodepool` | AKS confidential workload scheduling baseline.                      |
| `scripts/install-linkerd.sh`              | Вспомогательный install helper для strict mTLS path.                |

## Depends On / Depended On By

- **Depends on:** runtime metrics under `src/polisyos/core/observability/*`,
  security/authz code under `src/polisyos/core/security/*`,
  `src/polisyos/runtime/http/authz_middleware.py`, deployment tooling и target
  cluster/database environment.

- **Depended on by:** platform/ops engineers, release and compliance workflows,
  runtime deployment/recovery runbooks, observability rehearsals и tenant
  isolation reviews.

## Common Commands

Команды ниже smoke-tested на `2026-04-17`, если явно не помечены как
`conceptual`.

| Command                                                                 | Purpose                                                                 | Status                                      |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------- |
| `docker compose -f docker-compose.observability.yml config`             | Проверить, что локальный observability compose file парсится корректно. | `smoke-tested`                              |
| `docker compose -f docker-compose.observability.yml up -d`              | Поднять локальный Prometheus/Grafana sandbox.                           | `conceptual` (поднимает сервисы)            |
| `opa test ./opa/policies -v`                                            | Прогнать policy unit tests для authz/deploy gate.                       | `conceptual` (требует установленный `opa`)  |
| `helm template cell-a ./helm/polisyos-cell --set cell.id=cell-00112233` | Проверить render tenant/cell baseline chart.                            | `conceptual` (требует установленный `helm`) |

## Test And Verification

| Command                                                     | What it verifies                                     | Status         |
| ----------------------------------------------------------- | ---------------------------------------------------- | -------------- |
| `docker compose -f docker-compose.observability.yml config` | Compose syntax для локального observability sandbox. | `smoke-tested` |
| `opa test ./opa/policies -v`                                | Runtime authz и deploy gate Rego behavior.           | `conceptual`   |
| `helm template spire ./helm/spire`                          | Chart render для identity plane baseline.            | `conceptual`   |
| `helm template keycloak ./helm/keycloak`                    | Chart render для OIDC baseline.                      | `conceptual`   |

## Reference Docs

- [Helm README](./helm/README.md)
- [OPA README](./opa/README.md)
- [Prometheus README](./prometheus/README.md)
- [Grafana README](./grafana/README.md)
- [Migrations README](./migrations/README.md)
- [Terraform README](./terraform/README.md)
- [Deploy Runtime How-To](../docs/how-to/deploy-runtime.md)
- [CI/CD Platform How-To](../docs/how-to/operate-ci-cd-platform.md)
- [Release Policy How-To](../docs/how-to/release-policy.md)
- [Operations Reference Index](../docs/reference/operations/index.md)
- [Security And Compliance Reference](../docs/reference/security-compliance.md)
- [Runtime API Outage Runbook](../docs/runbooks/runtime-api-outage.md)
- [Canary Rollback Runbook](../docs/runbooks/canary-rollback-or-promotion-failure.md)
- [Replay Or Restore Runbook](../docs/runbooks/replay-or-restore.md)

## Current State

- `ops/opa/policies/*.rego` и `ops/helm/polisyos-cell/policies/*.rego` должны
  оставаться синхронными: chart пакует копию runtime/deploy policies.

- `migrations/003_rls_disable_rollback.sql` — только emergency rollback после
  `003_rls_enable.sql`, не часть forward chain.

- `docker-compose.observability.yml` полезен для локального smoke-check, но не
  покрывает весь production-like deployment path.

- Last updated: 2026-04-17
