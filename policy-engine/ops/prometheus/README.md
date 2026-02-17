# Prometheus (`ops/prometheus`)

Конфигурация scrape, alerting и recording rules для PolicyOS.

## Файлы

| Файл | Назначение |
|---|---|
| `prometheus.yml` | global interval, `rule_files`, `scrape_configs` |
| `alerts.yml` | operational/security alerts |
| `slo_alerts.yml` | SLO alerts |
| `recording_rules.yml` | operational precompute |
| `slo_recording_rules.yml` | SLO precompute |
| `rules/audit_chain_alerts.yml` | alerts для audit chain и tenant boundary |
| `rules/mtls-rules.yaml` | mTLS alerts для mesh (не подключен в `rule_files` по умолчанию) |

## Что загружает `prometheus.yml`

- recording rules: `recording_rules.yml` (6) + `slo_recording_rules.yml` (9);
- alerts: `alerts.yml` (18) + `slo_alerts.yml` (5) + `rules/audit_chain_alerts.yml` (4).

Итого: 15 recording rules и 27 alerts.

## Scrape jobs

- `prometheus` -> `prometheus:9090`;
- `polisyos` -> `host.docker.internal:9464/metrics` с label `environment=development`.

## Группы алертов

- `polisyos.cost`
- `polisyos.agents`
- `polisyos.simulation`
- `polisyos.calibration`
- `polisyos.cell_isolation`
- `polisyos.phase4_security`
- `polisyos.slo`
- `polisyos_audit_chain`

## Особенности

- SLO alerts завязаны на precompute из `slo_recording_rules.yml`.
- В SLO recording используется `clamp_min(..., 1e-9)` для защиты от деления на ноль.
- Пороговые значения зашиты в PromQL выражениях; переменные окружения в `rule_files` не подставляются автоматически.

## Связь с кодом

- `src/polisyos/core/observability/*` публикует базовые runtime метрики;
- `src/polisyos/core/security/*` публикует security/tenant/TEE/SBOM метрики;
- метрики `polisyos_slo_*` приходят из runtime/scientist/fabric контуров.

## Локальный запуск

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
```

## Локальный caveat

`prometheus.yml` ссылается на `/etc/prometheus/rules/audit_chain_alerts.yml`, но `docker-compose.observability.yml` не монтирует `./prometheus/rules`.

Добавьте volume:

```yaml
- ./prometheus/rules:/etc/prometheus/rules:ro
```

## Проверка конфигурации

```bash
promtool check rules policy-engine/ops/prometheus/alerts.yml
promtool check rules policy-engine/ops/prometheus/slo_alerts.yml
promtool check rules policy-engine/ops/prometheus/rules/audit_chain_alerts.yml
```
