# Prometheus (`ops/prometheus`)

Конфигурация scrape, alerting и recording rules для метрик PolicyOS.

## Структура

| Файл | Назначение |
|---|---|
| `prometheus.yml` | global scrape/eval interval + rule_files + scrape jobs |
| `alerts.yml` | operational alerts (cost/agents/simulation/calibration/cell/security) |
| `slo_alerts.yml` | SLO alerts |
| `recording_rules.yml` | operational recording rules |
| `slo_recording_rules.yml` | SLO recording rules |
| `rules/audit_chain_alerts.yml` | alerts по audit chain и tenant boundary violations |
| `rules/mtls-rules.yaml` | Linkerd/mTLS alerts (файл есть, но не подключен по умолчанию) |

## Что реально загружается из `prometheus.yml`

- recording: `recording_rules.yml` (6) + `slo_recording_rules.yml` (9)
- alerts: `alerts.yml` (18) + `slo_alerts.yml` (5) + `rules/audit_chain_alerts.yml` (4)

Итого: 15 recording rules и 27 alerts (по текущим файлам).

## Scrape jobs

- `prometheus` -> `prometheus:9090`
- `polisyos` -> `host.docker.internal:9464/metrics` (label `environment=development`)

## Alert groups

`alerts.yml`:

- `polisyos.cost` (2)
- `polisyos.agents` (3)
- `polisyos.simulation` (4)
- `polisyos.calibration` (2)
- `polisyos.cell_isolation` (3)
- `polisyos.phase4_security` (4)

`slo_alerts.yml`:

- `polisyos.slo` (5)

`rules/audit_chain_alerts.yml`:

- `polisyos_audit_chain` (4)

## Важные особенности

- SLO правила используют precompute из `slo_recording_rules.yml`.
- В `slo_recording_rules.yml` применяется `clamp_min(..., 1e-9)` против деления на ноль.
- Пороги в alert-выражениях заданы прямо в PromQL (комментарии могут ссылаться на env vars, но подстановка env в rule files не выполняется автоматически).

## Связь с кодом

- Метрики публикуются из `src/polisyos/core/observability/*`.
- Security/tenant/cell/sbom/tee метрики приходят из `src/polisyos/core/security/*`.
- SLO метрики формируются в runtime/scientist/fabric интеграциях и читаются тут как `polisyos_slo_*`.

## Локальный запуск

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
```

## Ограничение текущего docker-compose

`prometheus.yml` включает `/etc/prometheus/rules/audit_chain_alerts.yml`, но `docker-compose.observability.yml` не монтирует `./prometheus/rules`.

Для работы rule-файлов из `prometheus/rules/` нужно добавить volume mount, например:

```yaml
- ./prometheus/rules:/etc/prometheus/rules:ro
```
