# Prometheus Configuration (Мониторинг и алертинг)

Директория содержит конфигурацию Prometheus для сбора метрик, алертинга и предвычисления метрик системы PolicyOS. Обеспечивает комплексный мониторинг производительности и надежности.

## Структура

```
prometheus/
├── prometheus.yml                  # Основная конфигурация
├── alerts.yml                      # Правила алертинга
├── recording_rules.yml             # Правила предвычисления
└── README.md                       # Эта документация
```

## Конфигурация сбора метрик

### Основные настройки (prometheus.yml)

```yaml
global:
  scrape_interval: 15s     # Частота сбора метрик
  evaluation_interval: 15s # Частота оценки правил

rule_files:
  - /etc/prometheus/recording_rules.yml
  - /etc/prometheus/alerts.yml

scrape_configs:
  - job_name: polisyos
    metrics_path: /metrics
    static_configs:
      - targets:
          - host.docker.internal:9464  # PolicyOS metrics endpoint
```

### Мониторинг компонентов

**PolicyOS Core**:
- Metrics endpoint: `host.docker.internal:9464`
- Protocol: HTTP `/metrics` (Prometheus format)

**Self-monitoring**:
- Prometheus metrics: `prometheus:9090`
- Стандартные метрики самого Prometheus

## Система алертинга

### Группы алертов

#### polisyos.cost
**LLM Cost Monitoring**:
- `HighLLMCost`: >50 USD/час (warning)
- `HighLLMCostCritical`: >100 USD/час (critical)

**Расчет стоимости**:
```promql
(
  sum(rate(polisyos_llm_tokens_total{type="prompt"}[1h])) * 0.00001 +
  sum(rate(polisyos_llm_tokens_total{type="completion"}[1h])) * 0.00003
) * 3600
```

#### polisyos.agents
**Workflow Errors**:
- `AgentErrorSpike`: Error rate >5% за 5 минут
- `AgentErrorSpikeCritical`: Error rate >20% за 2 минуты

**Governance Performance**:
- `GovernancePassSlowdown`: p95 latency >30s за 10 минут

#### polisyos.simulation
**HPC Performance**:
- `SimulationStall`: Активные runs без прогресса >5 минут
- `JITRecompilationStorm`: >10 компиляций/минуту
- `LowCacheHitRatio`: Cache hit ratio <70% за 15 минут

#### polisyos.calibration
**ML Training**:
- `CalibrationDiverging`: Gradient norm >1000
- `CalibrationStuck`: Loss не уменьшается 30 минут

## Recording Rules

### Предвычисленные метрики

```yaml
groups:
  - name: polisyos.recording
    interval: 30s
    rules:
      # Стоимость LLM (предвычисление для производительности)
      - record: polisyos:llm_cost_per_hour:rate1h
        expr: (sum(rate(polisyos_llm_tokens_total{type="prompt"}[1h])) * 0.00001 + ...) * 3600

      # Acceptance rate
      - record: polisyos:workflow_acceptance_rate:rate1h
        expr: sum(rate(polisyos_workflow_runs_total{status="success"}[1h])) / sum(rate(polisyos_workflow_runs_total[1h]))

      # Cache efficiency
      - record: polisyos:cas_cache_hit_ratio:rate5m
        expr: sum(rate(polisyos_artifact_cache_hits_total[5m])) / (hits + misses)
```

### Преимущества recording rules

- **Производительность**: Сложные расчеты выполняются раз в 30 секунд вместо каждого query
- **Консистентность**: Все дашборды используют одинаковые расчеты
- **Надежность**: Изоляция от временных проблем сбора метрик

## Метрики PolicyOS

### Workflow метрики
- `polisyos_workflow_runs_total{status, phase}` - Counter запусков workflow
- `polisyos_governance_pass_duration_seconds{le, pass_id}` - Histogram времени governance

### LLM метрики
- `polisyos_llm_calls_total{model, status}` - Counter вызовов LLM API
- `polisyos_llm_tokens_total{type}` - Counter потребленных токенов (prompt/completion)

### HPC метрики
- `polisyos_simulation_steps_per_second` - Gauge throughput симуляций
- `polisyos_simulation_compile_seconds{le}` - Histogram времени JIT-компиляции
- `polisyos_artifact_cache_hits_total` / `polisyos_artifact_cache_misses_total` - Cache statistics

### Калибровка
- `polisyos_calibration_loss` - Gauge текущей потери
- `polisyos_calibration_grad_norm` - Gauge нормы градиента

## Конфигурация алертинга

### Severity levels
- **warning**: Требует внимания, не критично
- **critical**: Требует немедленных действий

### Alert routing
```yaml
labels:
  severity: warning
  team: platform|scientist|foundry
```

### Runbook URLs
Каждый алерт содержит ссылку на документацию по устранению проблемы.

## Кастомизация

### Добавление алертов

1. **Добавьте правило** в `alerts.yml`:
```yaml
- alert: CustomAlert
  expr: custom_metric > threshold
  for: 5m
  labels:
    severity: warning
    team: your_team
  annotations:
    summary: "Custom alert description"
```

2. **Перезапустите Prometheus**:
```bash
docker-compose restart prometheus
```

### Изменение порогов

- **LLM бюджет**: Переменная `POLISYOS_LLM_BUDGET_HOURLY`
- **Error thresholds**: Редактируйте `expr` в alerts.yml
- **Latency thresholds**: Измените значения в сравнениях

### Добавление новых метрик

1. **В коде PolicyOS**: Используйте `observability/metrics.py`
2. **В Prometheus**: Добавьте scrape target в `prometheus.yml`
3. **В алертах**: Создайте правила на основе новых метрик

## Мониторинг и отладка

### Проверка состояния
- **Targets**: `/targets` - статус всех scrape targets
- **Rules**: `/rules` - активные алерты и recording rules
- **Alerts**: `/alerts` - текущие алерты

### Query debugging
- **Expression browser**: `/graph` - тестирование PromQL
- **Query inspector** в Grafana для отладки dashboard queries

### Performance tuning
- **Scrape interval**: 15s для оперативного мониторинга, можно увеличить до 30s
- **Recording interval**: 30s баланс между свежестью и нагрузкой
- **Retention**: Настройте в `prometheus.yml` для управления размером базы

## Интеграция

### С Grafana
Автоматическое обнаружение через service discovery в docker-compose.

### С Alert Manager
Для enterprise алертинга подключите внешний Alert Manager вместо встроенного.

### С Observability stack
- **Jaeger/Tempo**: Для distributed tracing (интегрируется с OTLP)
- **Loki**: Для структурированного логирования
- **VictoriaMetrics**: Для долгосрочного хранения метрик