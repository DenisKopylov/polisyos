# Prometheus (`ops/observability/prometheus`)

Конфигурация scrape, recording rules и alerting для observability/security контура PolicyOS.

Проверка исходников: snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
(2026-10-14); прочитаны `prometheus.yml`, настроенные rule files и
`ops/docker/observability.compose.yml`. `promtool` и Docker Compose не запускались.

## Состав

| Файл                                   | Назначение                                       |
| -------------------------------------- | ------------------------------------------------ |
| `prometheus.yml`                       | global interval, `scrape_configs`, `rule_files`  |
| `recording_rules.yml`                  | operational precompute (6 rules)                 |
| `slo_recording_rules.yml`              | SLO precompute (16 rules)                        |
| `alerts.yml`                           | operational + security alerts (18)               |
| `slo_alerts.yml`                       | SLO alerts (10)                                  |
| `rules/audit_chain_alerts.yml`         | audit-chain/tenant-boundary alerts (4)           |
| `rules/runtime_operability_alerts.yml` | runtime operability alerts (7)                   |
| `rules/scientist-alerts.yml`           | Scientist SLO alerts (5)                         |
| `rules/mtls-rules.yaml`                | Linkerd mTLS alerts (2, подключены по умолчанию) |

`prometheus.yml` по умолчанию загружает 22 recording rules и 46 alerts,
включая все rule-файлы, заявленные в component observability contracts.

## Scrape jobs

- `prometheus` -> `prometheus:9090`
- `polisyos` -> `host.docker.internal:9464/metrics` (`environment=development`)

## Связи с кодом

- `src/polisyos/core/observability/*` — runtime и SLO метрики;
- `src/polisyos/core/security/*` — authz/audit/TEE/SBOM метрики;
- `src/polisyos/scientist/*`, `src/polisyos/foundry/*`, `src/polisyos/fabric/*` — источники доменных SLO-сигналов.

## Локальный запуск

```bash
docker compose -f ops/docker/observability.compose.yml up -d
```

## Важный caveat для local compose

`ops/docker/observability.compose.yml` монтирует `rules/` целиком, поэтому
локальный sandbox использует тот же набор rule files, что и committed
observability baseline.

## Проверка правил

Отдельные файлы правил проверяйте через `promtool` из `policy-engine/`. Полная
конфигурация использует пути `/etc/prometheus/...` из compose-контейнера;
после запуска локального стека проверяйте её там:

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
