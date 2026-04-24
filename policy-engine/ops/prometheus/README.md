# Prometheus (`ops/prometheus`)

Конфигурация scrape, recording rules и alerting для observability/security контура PolicyOS.

## Состав

| Файл                           | Назначение                                          |
| ------------------------------ | --------------------------------------------------- |
| `prometheus.yml`               | global interval, `scrape_configs`, `rule_files`     |
| `recording_rules.yml`          | operational precompute (6 rules)                    |
| `slo_recording_rules.yml`      | SLO precompute (9 rules)                            |
| `alerts.yml`                   | operational + security alerts (18)                  |
| `slo_alerts.yml`               | SLO alerts (5)                                      |
| `rules/audit_chain_alerts.yml` | audit-chain/tenant-boundary alerts (4)              |
| `rules/mtls-rules.yaml`        | Linkerd mTLS alerts (2, не подключены по умолчанию) |

`prometheus.yml` по умолчанию загружает 15 recording rules и 27 alerts.

## Scrape jobs

- `prometheus` -> `prometheus:9090`
- `polisyos` -> `host.docker.internal:9464/metrics` (`environment=development`)

## Связи с кодом

- `src/polisyos/core/observability/*` — runtime и SLO метрики;
- `src/polisyos/core/security/*` — authz/audit/TEE/SBOM метрики;
- `src/polisyos/scientist/*`, `src/polisyos/foundry/*`, `src/polisyos/fabric/*` — источники доменных SLO-сигналов.

## Локальный запуск

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
```

## Важный caveat для local compose

`prometheus.yml` ссылается на `/etc/prometheus/rules/audit_chain_alerts.yml`, но в `docker-compose.observability.yml` директория `./prometheus/rules` не смонтирована.

Для полного набора rule_files добавьте volume:

```yaml

- ./prometheus/rules:/etc/prometheus/rules:ro
```

## Проверка правил

```bash
promtool check rules policy-engine/ops/prometheus/alerts.yml
promtool check rules policy-engine/ops/prometheus/slo_alerts.yml
promtool check rules policy-engine/ops/prometheus/rules/audit_chain_alerts.yml
```
