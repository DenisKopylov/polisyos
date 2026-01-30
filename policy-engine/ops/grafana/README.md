# Grafana Dashboards (Визуализация)

Директория содержит конфигурацию Grafana и JSON-определения дашбордов для визуализации метрик PolicyOS. Предоставляет ролевые дашборды для разных пользователей системы.

## Структура

```
grafana/
├── dashboards/                     # JSON определения дашбордов
│   ├── executive-overview.json     # Обзор для руководства
│   ├── foundry-hpc.json           # Производительность HPC
│   └── scientist-agents.json       # Производительность агентов
└── provisioning/
    └── dashboards.yml              # Автоматическое provisioning
```

## Дашборды

### Executive Overview
**Цель**: Высокоуровневый обзор для руководства и стейкхолдеров

**Метрики:**
- Стоимость LLM (USD/час) с порогами warning/critical
- Общий acceptance rate workflow
- Активные эксперименты и симуляции

**Особенности:**
- 30-секундное обновление
- Templating по environment (production/staging)
- Threshold-based coloring (зеленый/желтый/красный)

### Scientist Agent Performance
**Цель**: Детальная аналитика работы AI агентов и экспериментов

**Метрики:**
- Governance pass duration (p95) по типам проверок
- Workflow acceptance/error rates
- LLM token consumption по типам (prompt/completion)
- Error rate агентов с трендами

**Особенности:**
- Timeline view для governance pipeline
- Heatmaps для error patterns
- Drill-down по конкретным экспериментам

### Foundry HPC Performance
**Цель**: Мониторинг производительности HPC симуляций и JAX runtime

**Метрики:**
- Simulation throughput (steps/second)
- JIT compilation time и частота
- Cache hit ratio для артефактов
- Calibration loss и gradient norms
- Memory/CPU utilization (при наличии)

**Особенности:**
- Real-time throughput monitoring
- Alert integration для performance degradation
- Historical trends для capacity planning

## Provisioning

### Автоматическая загрузка
Дашборды автоматически загружаются при запуске Grafana через `provisioning/dashboards.yml`:

```yaml
providers:
  - name: polisyos
    folder: PolicyOS
    type: file
    options:
      path: /etc/grafana/dashboards  # Монтируется из host
```

### Добавление новых дашбордов

1. **Создайте JSON файл** в `dashboards/` с уникальным `uid`
2. **Установите folder** в "PolicyOS"
3. **Перезапустите Grafana** или используйте hot reload
4. **Проверьте** в интерфейсе Grafana

## Интеграция с Prometheus

### Data Source
Grafana автоматически подключается к Prometheus на `prometheus:9090` (service name в docker-compose).

### Query Examples

```promql
# Стоимость LLM
sum(rate(polisyos_llm_tokens_total{type="prompt"}[1h])) * 0.00001 * 3600 +
sum(rate(polisyos_llm_tokens_total{type="completion"}[1h])) * 0.00003 * 3600

# Acceptance rate
sum(rate(polisyos_workflow_runs_total{status="success"}[1h])) /
sum(rate(polisyos_workflow_runs_total[1h]))

# Governance latency
histogram_quantile(0.95, sum by (le, pass_id) (rate(polisyos_governance_pass_duration_seconds_bucket[5m])))
```

## Кастомизация

### Темы и настройки
- **Default theme**: Light (для readability)
- **Time range**: Last 1 hour (для оперативного мониторинга)
- **Refresh**: 30 seconds (баланс между real-time и нагрузкой)

### Alert Integration
Дашборды показывают метрики, которые используются в алертах Prometheus. При срабатывании алертов можно быстро перейти из alert manager в соответствующий дашборд.

### Permissions
- **Admin access**: Полный доступ к редактированию
- **Viewer access**: Read-only для dashboard consumption
- **Folder organization**: Все дашборды в папке "PolicyOS"

## Troubleshooting

### Дашборды не загружаются
1. Проверьте volume mounts в docker-compose
2. Проверьте JSON syntax: `jq . dashboard.json`
3. Проверьте Grafana logs: `docker logs grafana`

### Метрики не отображаются
1. Проверьте Prometheus targets: `/targets`
2. Проверьте query в Grafana query inspector
3. Проверьте time range и label filters

### Performance issues
- Увеличьте refresh interval при высокой нагрузке
- Используйте recording rules для complex queries
- Рассмотрите dashboard sharding для большого количества panels