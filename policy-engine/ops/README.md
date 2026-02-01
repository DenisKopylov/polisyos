# Операционная инфраструктура (Operations)

Директория `ops` содержит production-ready стек для мониторинга, наблюдаемости и alerting системы PolicyOS. Обеспечивает комплексный трекинг производительности, автоматическое обнаружение проблем и визуализацию метрик.

## Архитектура

```
ops/
├── docker-compose.observability.yml    # Docker Compose для запуска стека мониторинга
├── prometheus/                         # Конфигурация Prometheus (сбор метрик, алертинг)
│   ├── prometheus.yml                  # Основная конфигурация (15s scrape interval)
│   ├── alerts.yml                      # Правила алертинга (cost, agents, simulation)
│   ├── recording_rules.yml             # Предвычисление метрик (30s interval)
│   └── README.md                       # Детальная документация Prometheus
├── grafana/                            # Дашборды и визуализация
│   ├── dashboards/                     # JSON определения дашбордов
│   │   ├── executive-overview.json     # Обзор для руководства (cost, acceptance)
│   │   ├── foundry-hpc.json           # HPC производительность (throughput, cache)
│   │   └── scientist-agents.json       # Агенты (governance, LLM usage)
│   ├── provisioning/
│   │   └── dashboards.yml              # Автозагрузка дашбордов
│   └── README.md                       # Детальная документация Grafana
└── README.md                           # Эта документация
```

## Функционал

### Быстрый запуск
```bash
cd ops
docker-compose -f docker-compose.observability.yml up -d
# Prometheus: http://localhost:9090, Grafana: http://localhost:3000 (admin/admin)
```

### Метрики и алертинг

**Ключевые метрики:**
- **LLM Cost**: Токены → USD (prompt: $0.00001, completion: $0.00003)
- **Agents**: Workflow success rate, governance latency, error rates
- **HPC**: Simulation throughput, JIT compilation, cache hit ratio
- **Calibration**: Loss convergence, gradient norms

**Алертинг (severity levels: warning/critical):**
- LLM budget exceeded (>$50/h warning, >$100/h critical)
- Agent error spikes (>5% warning, >20% critical)
- Simulation stalls, JIT recompilation storms
- Calibration divergence, convergence issues

### Дашборды
- **Executive Overview**: Cost & performance для руководства
- **Scientist Agent Performance**: Governance pipeline, LLM usage analysis
- **Foundry HPC Performance**: JAX runtime, simulation throughput, caching

## Особенности модулей

### Prometheus
- **15s scrape interval** для оперативного мониторинга
- **Recording rules** (30s) для предвычисления сложных метрик
- **Multi-level alerting** с эскалацией (warning → critical)
- **Self-monitoring** + PolicyOS metrics collection

### Grafana
- **Auto-provisioning** дашбордов при запуске
- **Role-based dashboards** для разных команд (executive/scientist/foundry)
- **30s refresh** для real-time monitoring
- **Environment templating** (production/staging filtering)

### Docker Compose
- **Dependency management** (Prometheus → Grafana startup order)
- **Read-only volumes** для конфигурационных файлов
- **Standard ports** (9090 Prometheus, 3000 Grafana)

## Связь с модулями PolicyOS

### Core/Observability
- **Metrics source**: `observability` модуль экспортирует на `:9464/metrics`
- **Zero-config**: Метрики доступны автоматически при запуске
- **Trace correlation**: Интеграция с distributed tracing (OTLP)

### Foundry (HPC)
- **JAX monitoring**: JIT compilation tracking, cache hit ratios
- **Simulation metrics**: Throughput, artifact caching, calibration progress
- **Performance alerts**: Stalls, recompilation storms, convergence issues

### Scientist (Agents)
- **Workflow metrics**: Success rates, governance pipeline latency
- **LLM monitoring**: Token consumption, cost tracking
- **Error detection**: Automated alerting on workflow failures

### Production Runtime
- **Full observability**: Production-grade monitoring stack
- **Alert integration**: Automated notifications via teams/channels

## Быстрый старт

1. **Запуск стека:**
   ```bash
   cd ops && docker-compose -f docker-compose.observability.yml up -d
   ```

2. **Доступ к интерфейсам:**
   - Prometheus: http://localhost:9090 (targets, alerts, rules)
   - Grafana: http://localhost:3000 (admin/admin)

3. **PolicyOS с метриками:**
   ```bash
   export POLISYOS_METRICS_PORT=9464
   python -m polisyos.core.observability
   ```

## Конфигурация

### Environment Variables
- `POLISYOS_METRICS_PORT=9464` - Metrics export port
- `POLISYOS_LLM_BUDGET_HOURLY=50` - LLM hourly budget (USD)

### Кастомизация
- **Alerts**: Edit `prometheus/alerts.yml`, restart Prometheus
- **Dashboards**: Add JSON to `grafana/dashboards/`, auto-loaded on restart
- **Recording rules**: Modify `prometheus/recording_rules.yml` for custom metrics