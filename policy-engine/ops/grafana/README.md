# Grafana (`ops/grafana`)

Каталог prebuilt-дашбордов для observability контура PolicyOS.

## Структура

```text
grafana/
├── dashboards/
│   ├── executive-overview.json
│   ├── scientist-agents.json
│   ├── foundry-hpc.json
│   ├── slo-overview.json
│   ├── security-phase4.json
│   └── knowledge-freshness.json
└── provisioning/
    └── dashboards.yml
```

## Дашборды

| UID | Файл | Основной фокус |
|---|---|---|
| `polisyos-executive` | `executive-overview.json` | cost/acceptance/throughput KPI |
| `polisyos-scientist` | `scientist-agents.json` | scientist/governance/LLM pipeline |
| `polisyos-foundry` | `foundry-hpc.json` | simulation/JIT/cache/calibration |
| `polisyos-slo-overview` | `slo-overview.json` | SLO и error-budget индикаторы |
| `polisyos-knowledge-freshness` | `knowledge-freshness.json` | freshness/staleness knowledge bundle |
| `polisyos-security-phase4` | `security-phase4.json` | TEE attestation + SBOM gate/security |

## Provisioning

`provisioning/dashboards.yml` подключает file-provider и загружает JSON из `/etc/grafana/dashboards` в папку `PolicyOS`.

Datasource provisioning в репозитории отсутствует.

## Datasource

В dashboard JSON datasource не закреплен жестко, поэтому нужен default Prometheus datasource:

- URL: `http://prometheus:9090`

## Связь с другими модулями

- `ops/prometheus/` — правило именования метрик, recording rules и алерты;
- `src/polisyos/core/observability/*` — runtime метрики;
- `src/polisyos/core/security/*` — security/tenant/TEE/SBOM метрики.

## Локальный запуск

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
# Grafana: http://localhost:3000 (admin/admin)
```
