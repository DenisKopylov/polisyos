# Grafana (`ops/grafana`)

Набор prebuilt-дашбордов для PolicyOS observability.

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

- `polisyos-executive` — executive KPI (LLM cost, acceptance rate, throughput).
- `polisyos-scientist` — governance/LLM/validation + drafter multipass метрики.
- `polisyos-foundry` — simulation throughput, JIT, cache, calibration.
- `polisyos-slo-overview` — SLO + cell/security обзор (использует `polisyos:slo_*` recording rules).
- `polisyos-security-phase4` — TEE attestation + SBOM security метрики.
- `polisyos-knowledge-freshness` — freshness/refresh статусы knowledge bundles.

## Provisioning

`provisioning/dashboards.yml` провиженит только dashboard-файлы из `/etc/grafana/dashboards` в папку `PolicyOS`.

## Источник данных

В JSON-панелях datasource не зафиксирован (используется default datasource Grafana).
Поэтому после локального старта нужен default Prometheus datasource в UI:

- URL: `http://prometheus:9090`

## Связь с другими модулями

- `ops/prometheus/` — источник PromQL/rules для панелей.
- `src/polisyos/core/observability/` — источник метрик.
- `src/polisyos/core/security/*` и runtime/scientist/fabric компоненты — security/SLO/freshness метрики.

## Локальный старт

```bash
cd policy-engine/ops
docker compose -f docker-compose.observability.yml up -d
# Grafana: http://localhost:3000 (admin/admin)
```
