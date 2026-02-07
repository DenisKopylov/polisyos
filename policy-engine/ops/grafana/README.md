# grafana — Dashboards & Visualization

4 ролевых дашборда с auto-provisioning для визуализации метрик PolicyOS. Данные поступают из Prometheus (`prometheus:9090` через docker-compose service discovery).

## Файлы

```
grafana/
├── dashboards/
│   ├── executive-overview.json    # Руководство: cost, acceptance, throughput
│   ├── scientist-agents.json      # Scientist: governance, LLM, validation
│   ├── foundry-hpc.json           # Foundry: simulation, JIT, cache, calibration
│   └── slo-overview.json          # SLO: success rates, latency, NaN, cost
└── provisioning/
    └── dashboards.yml             # Auto-provisioning config (folder: PolicyOS)
```

## Дашборды

### Executive Overview (`polisyos-executive`)
**Аудитория:** руководство, product owners
- **LLM Cost (USD/h)** — stat panel, thresholds: green <$10, yellow <$50, red >$50
- **Policy Acceptance Rate** — gauge, thresholds: red <70%, yellow <90%, green >90%
- **Active Experiments** — stat, текущие запуски
- **Workflow Throughput** — timeseries, workflows/hour за 5m window
- **Templating:** environment (production/staging)

### Scientist Agent Performance (`polisyos-scientist`)
**Аудитория:** data scientists, governance engineers
- **Governance Pass Duration (p95)** — timeseries по pass_id
- **Validation Failures by Pass** — barchart, increase за 1h
- **LLM Token Consumption by Model** — piechart
- **LLM Calls by Status** — timeseries (success/error/timeout)

### Foundry HPC Performance (`polisyos-foundry`)
**Аудитория:** simulation engineers, ML engineers
- **Simulation Throughput** — stat (steps/sec), thresholds: red <100, yellow <1000
- **CAS Cache Hit Ratio** — gauge, threshold: red <70%, yellow <90%
- **JIT Compilation Rate** — stat (compiles/min), red >20
- **JIT Compilation Time** — heatmap по bucket distribution
- **Simulation Duration Percentiles** — timeseries (p50, p95, p99)
- **CAS I/O Latency** — timeseries (p95)
- **Calibration Convergence** — timeseries (loss + grad norm)

### SLO Overview (`polisyos-slo-overview`)
**Аудитория:** platform team, SRE
- **DAG Success Rate (30m)** — gauge, thresholds: red <90%, yellow <95%
- **Simulation NaN Rate (5m)** — gauge, red >0.1%
- **Connector Error Rate (5m)** — gauge, red >1%
- **DAG p99 Latency** — stat, red >300s
- **Run Cost p95** — stat (USD), red >$5
- **DAG Success Rate Timeline** — timeseries by workflow_id
- **NaN Rate Timeline** — timeseries by env
- **Connector Error Rate Timeline** — timeseries by connector_id
- **DAG Latency Distribution** — heatmap
- **Run Cost Distribution** — heatmap
- **Templating:** environment (query), workflow_id (multi-select), connector_id (multi-select)

## Provisioning

Дашборды загружаются автоматически при старте контейнера через `provisioning/dashboards.yml`:
- **Provider:** `polisyos`, folder `PolicyOS`
- **Path:** `/etc/grafana/dashboards` (read-only volume mount)
- **editable:** true — можно менять через UI, но изменения не сохраняются при рестарте

## Общие настройки

- **Refresh:** 30s (все дашборды)
- **Schema version:** 38
- **Timezone:** browser
- **Data source:** Prometheus (auto-discovery через docker-compose)
- **Credentials:** admin/admin (default)

## Добавление нового дашборда

1. Создать JSON в `dashboards/` с уникальным `uid` (формат: `polisyos-<name>`)
2. Установить `tags: ["polisyos", ...]` для группировки
3. Перезапустить Grafana: `docker-compose restart grafana`
4. Для использования recording rules вместо raw queries — см. `prometheus/recording_rules.yml`

## Ключевые PromQL-паттерны

```promql
# LLM cost (USD/hour) — используется в Executive Overview
(sum(rate(polisyos_llm_tokens_total{type="prompt"}[1h])) * 0.00001 +
 sum(rate(polisyos_llm_tokens_total{type="completion"}[1h])) * 0.00003) * 3600

# Acceptance rate — или recording rule polisyos:workflow_acceptance_rate:rate1h
sum(rate(polisyos_workflow_runs_total{status="success"}[1h])) /
sum(rate(polisyos_workflow_runs_total[1h]))

# Governance p95 latency
histogram_quantile(0.95,
  sum by (le, pass_id) (rate(polisyos_governance_pass_duration_seconds_bucket[5m])))

# SLO DAG success rate — recording rule (рекомендуется)
polisyos:slo_dag_success_rate:rate30m{env="$environment", workflow_id=~"$workflow_id"}
```
