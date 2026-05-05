# Grafana (`ops/observability/grafana`)

Каталог prebuilt dashboards для operational, SLO и security мониторинга PolicyOS.

## Состав

- `dashboards/executive-overview.json` (`uid=polisyos-executive`)
- `dashboards/scientist-agents.json` (`uid=polisyos-scientist`)
- `dashboards/foundry-hpc.json` (`uid=polisyos-foundry`)
- `dashboards/slo-overview.json` (`uid=polisyos-slo-overview`)
- `dashboards/knowledge-freshness.json` (`uid=polisyos-knowledge-freshness`)
- `dashboards/security-phase4.json` (`uid=polisyos-security-phase4`)
- `provisioning/dashboards.yml` (file-provider в folder `PolicyOS`)

## Роль в системе

- визуализирует метрики из `ops/observability/prometheus`;
- поддерживает отдельные представления для exec/scientist/foundry/security/SLO контуров.

## Provisioning

`dashboards.yml` провиженит только dashboard-файлы из `/etc/grafana/dashboards`.
Datasource provisioning в репозитории отсутствует: нужен default Prometheus datasource (`http://prometheus:9090`).

## Связи с другими директориями

- `ops/observability/prometheus/` — запись и агрегация метрик/алертов.
- `src/polisyos/core/observability/*` — источник runtime/SLO метрик.
- `src/polisyos/core/security/*` — источник security/TEE/SBOM/audit метрик.

## Локальный запуск

```bash
docker compose -f ops/docker/observability.compose.yml up -d
# Grafana: http://localhost:3000 (admin/admin)
```
