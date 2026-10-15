# Ops (`ops/`)

## Purpose

`ops/` describes the PolicyOS operational perimeter: identity and policy enforcement, observability, tenant/RLS migrations, and infrastructure artifacts for runtime deployment and recovery.

## Where to Start

- Kubernetes packaging: `ops/cloud/helm/README.md`.
- Policy-as-code: `ops/policy/README.md`.
- Metrics/alerts: `ops/observability/prometheus/README.md`.
- Component operability bundles: `ops/components/README.md`.
- SQL tenant isolation chain: `ops/migrations/README.md`.
- Confidential node-pool module: `ops/cloud/terraform/README.md`.
- Local observability sandbox: `ops/docker/observability.compose.yml`.

## Public Entrypoints

| Surface                                              | Purpose                                                            |
| ---------------------------------------------------- | ------------------------------------------------------------------ |
| `cloud/helm/`                                        | Baseline Helm charts for `polisyos-cell`, `spire`, and `keycloak`. |
| `policy/policies/*.rego`                             | Runtime authorization and deployment-gate decisions.               |
| `observability/prometheus` + `observability/grafana` | Scrape configuration, alerts, SLO rules, and dashboards.           |
| `migrations/*.sql`                                   | Forward/rollback SQL chain for tenant/RLS hardening.               |
| `cloud/terraform/modules/confidential_nodepool`      | AKS confidential workload scheduling baseline.                     |
| `cloud/helm/install-linkerd.sh`                      | Helper for installing the strict mTLS path.                        |

## Top-Level Taxonomy

`ops/**` is the declarative/control-plane side of operations. Executable
operational runners live in `tools/ops_runners/**`.

| Folder           | Owner           | Artifact type                    | Contract                                                                                 |
| ---------------- | --------------- | -------------------------------- | ---------------------------------------------------------------------------------------- |
| `ci/`            | `team-devx`     | `ci-template-control-plane`      | Inactive CI and GitHub template sources.                                                 |
| `cloud/`         | `team-ops`      | `cloud-infrastructure-contracts` | Helm, Terraform, GCP launch, and cloud deployment assets.                                |
| `components/`    | `team-ops`      | `component-operability-bundles`  | Component-first SLO, alert, dashboard, runbook, runtime-contract, and retention bundles. |
| `deploy/`        | `team-ops`      | `deployment-contracts`           | Cross-environment deployment topology and support contracts.                             |
| `docker/`        | `team-ops`      | `local-runtime-infrastructure`   | Compose and Docker assets for local/operational infrastructure.                          |
| `migrations/`    | `team-ops`      | `migration-contracts`            | SQL and future classed migration source-of-truth contracts.                              |
| `observability/` | `team-ops`      | `observability-contracts`        | SLOs, alerts, dashboards, and telemetry baselines.                                       |
| `policy/`        | `team-security` | `policy-as-code`                 | Runtime authorization and deploy gate Rego policies.                                     |
| `release/`       | `team-ops`      | `release-policy-contracts`       | Release fragment, commit, topology, and promotion gate baselines.                        |
| `runtime/`       | `team-runtime`  | `runtime-operations-contracts`   | Runtime deployment-facing compatibility and recovery contracts.                          |
| `security/`      | `team-security` | `security-baseline-contracts`    | Secret, vulnerability, and SBOM baseline policy.                                         |

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
  `src/polisyos/runtime/http/authz_middleware.py`, deployment tooling, and the target cluster/database environment.

- **Depended on by:** platform/ops engineers, release and compliance workflows,
  runtime deployment/recovery runbooks, observability rehearsals, and tenant isolation reviews.

## Common Commands

The commands below were smoke-tested on `2026-04-17` unless explicitly marked as `conceptual`.

| Command                                                                         | Purpose                                                               | Status                                         |
| ------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------- |
| `docker compose -f ops/docker/observability.compose.yml config`                 | Verify that the local observability Compose file parses successfully. | `smoke-tested`                                 |
| `docker compose -f ops/docker/observability.compose.yml up -d`                  | Start the local Prometheus/Grafana sandbox.                           | `conceptual` (starts services)                 |
| `opa test ops/policy/policies -v`                                               | Run policy unit tests for the authorization/deployment gate.          | `conceptual` (requires `opa` to be installed)  |
| `helm template cell-a ops/cloud/helm/polisyos-cell --set cell.id=cell-00112233` | Render the tenant/cell baseline chart.                                | `conceptual` (requires `helm` to be installed) |

## Test And Verification

| Command                                                         | What it verifies                                         | Status         |
| --------------------------------------------------------------- | -------------------------------------------------------- | -------------- |
| `docker compose -f ops/docker/observability.compose.yml config` | Compose syntax for the local observability sandbox.      | `smoke-tested` |
| `opa test ops/policy/policies -v`                               | Runtime authorization and deployment-gate Rego behavior. | `conceptual`   |
| `helm template spire ops/cloud/helm/spire`                      | Chart rendering for the identity-plane baseline.         | `conceptual`   |
| `helm template keycloak ops/cloud/helm/keycloak`                | Chart rendering for the OIDC baseline.                   | `conceptual`   |

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

- `ops/policy/policies/*.rego` and `ops/cloud/helm/polisyos-cell/policies/*.rego` must remain synchronized because the chart packages a copy of the runtime/deployment policies.

- `migrations/db/003_rls_disable_rollback.sql` is for emergency rollback only after `003_rls_enable.sql`; it is not part of the forward chain.

- `ops/docker/observability.compose.yml` is useful for a local smoke check, but it does not cover the full production-like deployment path.

- Last updated: 2026-04-17
