# Prometheus Configuration (Мониторинг и алертинг)

Директория содержит конфигурацию Prometheus для сбора метрик, алертинга и предвычисления метрик PolicyOS. Обеспечивает комплексный мониторинг производительности и надежности.

## Структура

```
prometheus/
├── prometheus.yml                  # Основная конфигурация (15s scrape/eval)
├── alerts.yml                      # Alert rules (cost, agents, simulation)
├── recording_rules.yml             # Recording rules (30s interval)
└── README.md                       # Эта документация
```

## Конфигурация сбора метрик

### Основные настройки
```yaml
global:
  scrape_interval: 15s     # Сбор метрик каждые 15 секунд
  evaluation_interval: 15s # Оценка правил каждые 15 секунд

rule_files:
  - recording_rules.yml
  - alerts.yml

scrape_configs:
  - job_name: polisyos        # PolicyOS metrics
    metrics_path: /metrics
    targets: [host.docker.internal:9464]
  - job_name: prometheus      # Self-monitoring
    targets: [prometheus:9090]
```

## Система алертинга

### Alert Groups

#### polisyos.cost (LLM Budget)
- `HighLLMCost`: >$50/h (warning), `HighLLMCostCritical`: >$100/h (critical)
- **Formula**: `(prompt_tokens * 0.00001 + completion_tokens * 0.00003) * 3600`

#### polisyos.agents (Workflow & Governance)
- `AgentErrorSpike`: Error rate >5% (warning), >20% (critical)
- `GovernancePassSlowdown`: p95 latency >30s

#### polisyos.simulation (HPC Performance)
- `SimulationStall`: Active runs with zero throughput >5m
- `JITRecompilationStorm`: >10/min (warning), >30/min (critical)
- `LowCacheHitRatio`: Cache hit ratio <70%

#### polisyos.calibration (ML Training)
- `CalibrationDiverging`: Gradient norm >1000
- `CalibrationStuck`: Loss unchanged >30m

## Recording Rules

### Предвычисленные метрики (30s interval)
```yaml
groups:
  - name: polisyos.recording
    rules:
      - record: polisyos:llm_cost_per_hour:rate1h    # LLM cost USD/hour
      - record: polisyos:workflow_acceptance_rate:rate1h  # Success rate
      - record: polisyos:cas_cache_hit_ratio:rate5m       # Cache efficiency
      - record: polisyos:workflow_error_rate:rate5m       # Error rate
```

### Преимущества
- **Performance**: Сложные расчеты выполняются каждые 30s вместо каждого query
- **Consistency**: Единые расчеты для всех дашбордов
- **Reliability**: Изоляция от временных проблем сбора метрик

## Метрики PolicyOS

### Workflow & Governance
- `polisyos_workflow_runs_total{status, phase}` - Workflow execution counter
- `polisyos_governance_pass_duration_seconds{le, pass_id}` - Governance latency histogram

### LLM Usage
- `polisyos_llm_calls_total{model, status}` - LLM API calls counter
- `polisyos_llm_tokens_total{type}` - Token consumption (prompt/completion)

### HPC & Simulation
- `polisyos_simulation_steps_per_second` - Simulation throughput gauge
- `polisyos_simulation_compile_seconds{le}` - JIT compilation histogram
- `polisyos_artifact_cache_hits_total/misses_total` - Cache statistics

### Calibration
- `polisyos_calibration_loss` - Training loss gauge
- `polisyos_calibration_grad_norm` - Gradient norm gauge

## Конфигурация алертинга

### Severity Levels
- **warning**: Требует внимания (non-critical)
- **critical**: Требует немедленных действий

### Alert Labels
```yaml
labels:
  severity: warning|critical
  team: platform|scientist|foundry
```

## Кастомизация

### Добавление алертов
1. Добавьте правило в `alerts.yml` с `expr`, `for`, `labels`, `annotations`
2. Перезапустите Prometheus: `docker-compose restart prometheus`

### Изменение порогов
- **LLM budget**: `POLISYOS_LLM_BUDGET_HOURLY` env var
- **Error rates**: Edit expressions в `alerts.yml`
- **Latency thresholds**: Modify comparison values

### Новые метрики
1. **PolicyOS code**: Use `observability/metrics.py`
2. **Prometheus**: Add scrape target в `prometheus.yml`
3. **Alerts**: Create rules based on new metrics

## Мониторинг и отладка

### Web Interface
- **`/targets`**: Scrape target status
- **`/rules`**: Active alerts & recording rules
- **`/alerts`**: Current firing alerts
- **`/graph`**: PromQL query testing

### Performance Tuning
- **Scrape interval**: 15s (operational monitoring), can increase to 30s
- **Recording interval**: 30s (freshness/load balance)
- **Retention**: Configure in `prometheus.yml` for storage management

## Интеграция

### С Grafana
Автоматическое обнаружение через docker-compose service discovery.

### С Alert Manager
Для enterprise алертинга подключите внешний Alert Manager.

### С Observability Stack
- **Jaeger/Tempo**: Distributed tracing (OTLP integration)
- **Loki**: Structured logging
- **VictoriaMetrics**: Long-term metrics storage