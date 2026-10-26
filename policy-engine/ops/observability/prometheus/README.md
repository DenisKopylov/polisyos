# Prometheus (`ops/observability/prometheus`)

Scrape configuration, recording rules, and alerting for the PolicyOS observability/security area.

Source inspection: snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` (2026-10-14); `prometheus.yml`, the configured rule files, and `ops/docker/observability.compose.yml` were read. `promtool` and Docker Compose were not run.

## Contents

| File                                   | Purpose                                          |
| -------------------------------------- | ------------------------------------------------ |
| `prometheus.yml`                       | global interval, `scrape_configs`, `rule_files`  |
| `recording_rules.yml`                  | operational precompute (6 rules)                 |
| `slo_recording_rules.yml`              | SLO precompute (16 rules)                        |
| `alerts.yml`                           | operational + security alerts (18)               |
| `slo_alerts.yml`                       | SLO alerts (10)                                  |
| `rules/audit_chain_alerts.yml`         | audit-chain/tenant-boundary alerts (4)           |
| `rules/runtime_operability_alerts.yml` | runtime operability alerts (7)                   |
| `rules/scientist-alerts.yml`           | Scientist SLO alerts (5)                         |
| `rules/mtls-rules.yaml`                | Linkerd mTLS alerts (2, enabled by default)      |

By default, `prometheus.yml` loads 22 recording rules and 46 alerts, including all rule files named in the component observability contracts.

## Scrape jobs

- `prometheus` -> `prometheus:9090`
- `polisyos` -> `host.docker.internal:9464/metrics` (`environment=development`)

## Related Code

- `src/polisyos/core/observability/*` — runtime and SLO metrics;
- `src/polisyos/core/security/*` — authorization, audit, TEE, and SBOM metrics;
- `src/polisyos/scientist/*`, `src/polisyos/foundry/*`, `src/polisyos/fabric/*` — sources of domain SLO signals.

## Local Run

```bash
docker compose -f ops/docker/observability.compose.yml up -d
```

## Local Compose Caveat

`ops/docker/observability.compose.yml` mounts all of `rules/`, so the local sandbox uses the same set of rule files as the committed observability baseline.

## Rule Checks

Check individual rule files with `promtool` from `policy-engine/`. The full configuration uses `/etc/prometheus/...` paths inside the Compose container; after starting the local stack, validate it there:

```bash
docker compose -f ops/docker/observability.compose.yml exec prometheus \
  promtool check config /etc/prometheus/prometheus.yml
promtool check rules ops/observability/prometheus/alerts.yml
promtool check rules ops/observability/prometheus/slo_alerts.yml
promtool check rules ops/observability/prometheus/rules/audit_chain_alerts.yml
promtool check rules ops/observability/prometheus/rules/runtime_operability_alerts.yml
promtool check rules ops/observability/prometheus/rules/scientist-alerts.yml
promtool check rules ops/observability/prometheus/rules/mtls-rules.yaml
```

## Recording Rule Semantic Tests

Run the Scientist SLO fixture from `policy-engine/` with the pinned Prometheus 2.50.0 `promtool`:

```bash
promtool test rules tests/contract/fixtures/prometheus/scientist_slo_recording_rules.test.yml
```

The fixture loads `ops/observability/prometheus/slo_recording_rules.yml` and `ops/observability/prometheus/rules/scientist-alerts.yml` directly. It exercises absent and zero-rate API/engine series, API success/error traffic, engine ok/fail traffic, mixed API/engine populations, and API-versus-engine histogram buckets. Assertions inspect actual recording-rule and alert-rule outputs, including no SLI without eligible traffic and scope-bound engine failure alerts; they do not duplicate PromQL calculations in a separate oracle.

Runtime API rule/alert fixture: promtool test rules tests/contract/fixtures/prometheus/runtime_api_slo_rules.test.yml
