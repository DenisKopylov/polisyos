# Ops (`ops/`)

## Purpose

`ops/` описывает эксплуатационный периметр PolicyOS: identity и policy
enforcement, observability, tenant/RLS migrations и infrastructure artifacts
для runtime deployment и recovery.

## Where to Start

- Kubernetes packaging: `ops/cloud/helm/README.md`.
- Policy-as-code: `ops/policy/README.md`.
- Metrics/alerts: `ops/observability/prometheus/README.md`.
- Component operability bundles: `ops/components/README.md`.
- SQL tenant isolation chain: `ops/migrations/README.md`.
- Confidential node-pool module: `ops/cloud/terraform/README.md`.
- Локальная observability sandbox: `ops/docker/observability.compose.yml`.

## Public Entrypoints

| Surface                                   | Purpose                                                             |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `cloud/helm/`                             | Chart-ы `polisyos-cell`, `spire`, `keycloak` для platform baseline. |
| `policy/policies/*.rego`                  | Runtime authz и deploy gate decisions.                              |
| `observability/prometheus` + `observability/grafana` | Scrape config, alerts, SLO rules и dashboards.            |
| `migrations/*.sql`                        | Forward/rollback SQL chain для tenant/RLS hardening.                |
| `cloud/terraform/modules/confidential_nodepool` | AKS confidential workload scheduling baseline.                |
| `cloud/helm/install-linkerd.sh`           | Вспомогательный install helper для strict mTLS path.                |

## Top-Level Taxonomy

`ops/**` is the declarative/control-plane side of operations. Executable
operational runners live in `tools/ops_runners/**`.

| Folder | Owner | Artifact type | Contract |
| --- | --- | --- | --- |
| `ci/` | `team-devx` | `ci-template-control-plane` | Inactive CI and GitHub template sources. |
| `cloud/` | `team-ops` | `cloud-infrastructure-contracts` | Helm, Terraform, GCP launch, and cloud deployment assets. |
| `components/` | `team-ops` | `component-operability-bundles` | Component-first SLO, alert, dashboard, runbook, runtime-contract, and retention bundles. |
| `deploy/` | `team-ops` | `deployment-contracts` | Cross-environment deployment topology and support contracts. |
| `docker/` | `team-ops` | `local-runtime-infrastructure` | Compose and Docker assets for local/operational infrastructure. |
| `migrations/` | `team-ops` | `migration-contracts` | SQL and future classed migration source-of-truth contracts. |
| `observability/` | `team-ops` | `observability-contracts` | SLOs, alerts, dashboards, and telemetry baselines. |
| `policy/` | `team-security` | `policy-as-code` | Runtime authorization and deploy gate Rego policies. |
| `release/` | `team-ops` | `release-policy-contracts` | Release fragment, commit, topology, and promotion gate baselines. |
| `runtime/` | `team-runtime` | `runtime-operations-contracts` | Runtime deployment-facing compatibility and recovery contracts. |
| `security/` | `team-security` | `security-baseline-contracts` | Secret, vulnerability, and SBOM baseline policy. |

## Operability Organization

Phase 1.6 selects component-first operability bundles as the target shape:

```text
ops/components/<component>/
  README.md
  slo.yaml
  alerts.yml
  dashboard.json
  runbooks.md
  runtime-contract.toml
  retention-policy.toml
```

Phase 4.9 creates the physical `ops/components/**` draft tree. Its
machine-readable index is `ops/components/index.toml`; the legacy aggregate
coverage mirrors remain in `architecture/component_observability.toml` and
`architecture/runbook_coverage.toml` for Wave 6 gate conversion.

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
| `docker compose -f ops/docker/observability.compose.yml config`             | Проверить, что локальный observability compose file парсится корректно. | `smoke-tested`                              |
| `docker compose -f ops/docker/observability.compose.yml up -d`              | Поднять локальный Prometheus/Grafana sandbox.                           | `conceptual` (поднимает сервисы)            |
| `opa test ops/policy/policies -v`                                       | Прогнать policy unit tests для authz/deploy gate.                       | `conceptual` (требует установленный `opa`)  |
| `helm template cell-a ops/cloud/helm/polisyos-cell --set cell.id=cell-00112233` | Проверить render tenant/cell baseline chart.                    | `conceptual` (требует установленный `helm`) |

## Test And Verification

| Command                                                     | What it verifies                                     | Status         |
| ----------------------------------------------------------- | ---------------------------------------------------- | -------------- |
| `docker compose -f ops/docker/observability.compose.yml config` | Compose syntax для локального observability sandbox. | `smoke-tested` |
| `opa test ops/policy/policies -v`                            | Runtime authz и deploy gate Rego behavior.           | `conceptual`   |
| `helm template spire ops/cloud/helm/spire`                   | Chart render для identity plane baseline.            | `conceptual`   |
| `helm template keycloak ops/cloud/helm/keycloak`             | Chart render для OIDC baseline.                      | `conceptual`   |

## Reference Docs

- [Helm README](./cloud/helm/README.md)
- [Component Operability Bundles](./components/README.md)
- [Policy README](./policy/README.md)
- [Prometheus README](./observability/prometheus/README.md)
- [Grafana README](./observability/grafana/README.md)
- [Migrations README](./migrations/README.md)
- [Terraform README](./cloud/terraform/README.md)
- [Deploy Runtime How-To](../docs/how-to/deploy-runtime.md)
- [CI/CD Platform How-To](../docs/how-to/operate-ci-cd-platform.md)
- [Release Policy How-To](../docs/how-to/release-policy.md)
- [Operations Reference Index](../docs/reference/operations/index.md)
- [Security And Compliance Reference](../docs/reference/security-compliance.md)
- [Runtime API Outage Runbook](../docs/runbooks/runtime-api-outage.md)
- [Canary Rollback Runbook](../docs/runbooks/canary-rollback-or-promotion-failure.md)
- [Replay Or Restore Runbook](../docs/runbooks/replay-or-restore.md)

## Current State

- `ops/policy/policies/*.rego` и `ops/cloud/helm/polisyos-cell/policies/*.rego` должны
  оставаться синхронными: chart пакует копию runtime/deploy policies.

- `migrations/db/003_rls_disable_rollback.sql` — только emergency rollback
  после `003_rls_enable.sql`, не часть forward chain.

- `ops/docker/observability.compose.yml` полезен для локального smoke-check, но не
  покрывает весь production-like deployment path.

- Last updated: 2026-04-17
