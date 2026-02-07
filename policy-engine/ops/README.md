# ops — Observability Infrastructure

Инфраструктурный (не кодовый) модуль PolicyOS: конфигурация Prometheus + Grafana для мониторинга, алертинга и SLO-трекинга. Все метрики генерируются в `core/observability` (OpenTelemetry SDK), а `ops` потребляет их через Prometheus scrape protocol.

## Архитектура

```
ops/
├── docker-compose.observability.yml   # Стек: Prometheus v2.50 + Grafana 10.4
├── prometheus/                        # Сбор метрик, алертинг, SLO (6 файлов)
│   ├── prometheus.yml                 # Scrape config (15s interval, 2 targets)
│   ├── alerts.yml                     # 11 alert rules: cost, agents, simulation, calibration
│   ├── slo_alerts.yml                 # 5 SLO alert rules: DAG success, latency, NaN, connectors
│   ├── recording_rules.yml            # 4 recording rules (30s): cost, acceptance, cache, errors
│   └── slo_recording_rules.yml        # 8 SLO recording rules (30s): rates, percentiles
├── grafana/                           # Визуализация (5 файлов)
│   ├── dashboards/                    # 4 JSON-дашборда
│   │   ├── executive-overview.json    # Cost USD/h, acceptance rate, throughput
│   │   ├── scientist-agents.json      # Governance latency, LLM tokens, validation
│   │   ├── foundry-hpc.json           # Simulation throughput, JIT, cache, calibration
│   │   └── slo-overview.json          # SLO gauges, timelines, heatmaps
│   └── provisioning/
│       └── dashboards.yml             # Auto-provisioning при старте контейнера
└── README.md
```

**14 файлов, 0 Python** — чистая инфраструктура.

## Быстрый запуск

```bash
cd policy-engine/ops
docker-compose -f docker-compose.observability.yml up -d

# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin/admin)

# PolicyOS должен экспортировать метрики:
export POLISYOS_METRICS_PORT=9464
```

## Роль в системе

```
┌─────────────────────────────────────────────────────────────────────┐
│  PolicyOS Runtime                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ scientist │ │  foundry  │ │  fabric   │ │   lex    │              │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬────┘             │
│        └──────────┬──┴──────────┬──┘              │                 │
│            core/observability/metrics.py           │                 │
│            (OTel SDK, MetricsRegistry)             │                 │
│                      │                             │                 │
│               :9464/metrics (Prometheus format)    │                 │
└──────────────────────┼─────────────────────────────┘                 │
                       │                                               │
┌──────────────────────┼───────────────────────────────────────────────┐
│  ops/                │                                               │
│  ┌───────────────────▼──────────────┐    ┌────────────────────────┐ │
│  │ Prometheus (scrape 15s)          │───▶│ Grafana (4 dashboards) │ │
│  │ alerts + recording rules + SLO   │    │ auto-provisioning      │ │
│  └──────────────────────────────────┘    └────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

## Мониторинг по доменам

| Домен | Метрики | Алерты | Дашборд |
|---|---|---|---|
| **LLM Cost** | `llm_tokens_total`, `llm_calls_total` | >$50/h warning, >$100/h critical | Executive Overview |
| **Scientist Agents** | `workflow_runs_total`, `governance_pass_duration_seconds`, `validation_issues_total` | Error spike >5%/>20%, governance >30s p95 | Scientist Agents |
| **Foundry HPC** | `simulation_steps_per_second`, `simulation_compile_seconds`, `artifact_cache_*` | Stall, JIT storm >10/>30 min⁻¹, cache <70% | Foundry HPC |
| **Calibration** | `calibration_loss`, `calibration_grad_norm` | Divergence (grad >1000), stuck (>30m) | Foundry HPC |
| **Connector Resilience** | `connector_circuit_*`, `connector_retry_*`, `connector_rate_limit_*`, `connector_fallback_*` | — (через SLO) | — |
| **SLO** | `slo_dag_runs_total`, `slo_dag_duration_seconds`, `slo_simulation_nan_total`, `slo_connector_requests_total`, `slo_run_cost_usd` | DAG <95%/<80%, p99 >300s, NaN >0.1%, connector >1% | SLO Overview |

## Связь с модулями PolicyOS

**core/observability** — единственная точка интеграции:
- `metrics.py` — singleton `MetricsRegistry` с ~40 метриками, экспорт через `PrometheusMetricReader` на порт `POLISYOS_METRICS_PORT` (default 9464)
- `pricing.py` — таблица LLM-цен (gpt-4o: $2.5e-6/$10e-6, gemini-pro: $1e-6/$4e-6, default: $1e-5/$3e-5 per token)
- `config.py` — `OTelConfig` с environment label (используется в SLO-метриках)

**Кто генерирует метрики:**
- **scientist** — `record_workflow_run()`, `record_slo_dag_run()`, `record_llm_call()`, `record_validation_issue()`
- **foundry** — `time_simulation()`, `simulation_steps_per_second.set()`, `calibration_loss.set()`
- **fabric/connectors** — `record_slo_connector_request()`, connector cache/resilience metrics

## Конфигурация

| Переменная | Default | Описание |
|---|---|---|
| `POLISYOS_METRICS_PORT` | 9464 | Порт Prometheus-экспорта метрик |
| `POLISYOS_LLM_BUDGET_HOURLY` | 50 | Порог warning-алерта по LLM cost (USD/h) |
| `POLISYOS_LLM_DEFAULT_INPUT_USD` | 1e-5 | Default цена input token |
| `POLISYOS_LLM_DEFAULT_OUTPUT_USD` | 3e-5 | Default цена output token |

## Кастомизация

- **Алерты**: редактировать `prometheus/alerts.yml` или `prometheus/slo_alerts.yml`, перезапустить Prometheus
- **Дашборды**: добавить JSON в `grafana/dashboards/` с уникальным `uid`, авто-загрузка при рестарте
- **Recording rules**: `prometheus/recording_rules.yml` или `prometheus/slo_recording_rules.yml`
- **Новые метрики**: зарегистрировать в `core/observability/metrics.py`, они автоматически появятся на `:9464/metrics`

Детальная документация: [prometheus/README.md](prometheus/README.md), [grafana/README.md](grafana/README.md).
