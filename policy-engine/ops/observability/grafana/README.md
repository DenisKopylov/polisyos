# Grafana (`ops/observability/grafana`)

Directory of prebuilt dashboards for PolicyOS operations, SLOs, and security monitoring.

## Contents

- `dashboards/executive-overview.json` (`uid=polisyos-executive`)
- `dashboards/scientist-agents.json` (`uid=polisyos-scientist`)
- `dashboards/foundry-hpc.json` (`uid=polisyos-foundry`)
- `dashboards/slo-overview.json` (`uid=polisyos-slo-overview`)
- `dashboards/knowledge-freshness.json` (`uid=polisyos-knowledge-freshness`)
- `dashboards/runtime-operability.json` (`uid=polisyos-runtime-operability`)
- `dashboards/security-phase4.json` (`uid=polisyos-security-phase4`)
- `dashboards/scientist-llm-cost.json` (`uid=polisyos-scientist-llm-cost`)
- `provisioning/dashboards.yml` (file provider in the `PolicyOS` folder)

## Role in the System

- visualizes metrics from `ops/observability/prometheus`;
- provides separate views for exec, scientist, scientist LLM cost, Foundry, runtime operability, security, and SLO areas.

## Provisioning

`dashboards.yml` provisions only dashboard files from `/etc/grafana/dashboards`.
The repository does not include datasource provisioning; a default Prometheus datasource (`http://prometheus:9090`) is required.

## Related Directories

- `ops/observability/prometheus/` — metric and alert recording/aggregation.
- `src/polisyos/core/observability/*` — source of runtime/SLO metrics.
- `src/polisyos/core/security/*` — source of security/TEE/SBOM/audit metrics.

## Local Run

```bash
docker compose -f ops/docker/observability.compose.yml up -d
# Grafana: http://localhost:3000 (admin/admin)
```
