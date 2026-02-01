# Grafana Dashboards (Визуализация)

Директория содержит конфигурацию Grafana и JSON-определения дашбордов для визуализации метрик PolicyOS. Предоставляет ролевые дашборды с автоматическим provisioning.

## Структура

```
grafana/
├── dashboards/                     # JSON дашборды (3 шт.)
│   ├── executive-overview.json     # Executive overview (cost, acceptance)
│   ├── foundry-hpc.json           # HPC performance (throughput, cache)
│   └── scientist-agents.json       # Agent performance (governance, LLM)
└── provisioning/
    └── dashboards.yml              # Auto-provisioning конфигурация
```

## Дашборды

### Executive Overview
**Цель**: Высокоуровневый обзор для руководства
- **Метрики**: LLM cost (USD/h с thresholds), acceptance rate, active runs
- **Особенности**: 30s refresh, environment templating, color-coded thresholds

### Scientist Agent Performance
**Цель**: Аналитика работы AI агентов
- **Метрики**: Governance latency (p95), workflow success/error rates, LLM token usage
- **Особенности**: Timeline governance pipeline, error heatmaps, experiment drill-down

### Foundry HPC Performance
**Цель**: Мониторинг HPC симуляций и JAX
- **Метрики**: Simulation throughput, JIT compilation stats, cache hit ratios, calibration metrics
- **Особенности**: Real-time monitoring, performance alerts, capacity planning trends

## Provisioning

### Автозагрузка
Дашборды автоматически загружаются при запуске через `provisioning/dashboards.yml`. Конфигурация монтируется в контейнер read-only.

### Добавление дашбордов
1. Создайте JSON в `dashboards/` с уникальным `uid`
2. Установите `folder: "PolicyOS"`
3. Перезапустите Grafana для загрузки
4. Проверьте в интерфейсе (admin/admin)

## Интеграция с Prometheus

### Data Source
Автоматическое подключение к `prometheus:9090` через docker-compose service discovery.

### Примеры запросов
```promql
# LLM cost (USD/hour)
(sum(rate(polisyos_llm_tokens_total{type="prompt"}[1h])) * 0.00001 +
 sum(rate(polisyos_llm_tokens_total{type="completion"}[1h])) * 0.00003) * 3600

# Acceptance rate
sum(rate(polisyos_workflow_runs_total{status="success"}[1h])) /
sum(rate(polisyos_workflow_runs_total[1h]))

# Governance p95 latency
histogram_quantile(0.95, sum by (le, pass_id) (rate(polisyos_governance_pass_duration_seconds_bucket[5m])))
```

## Кастомизация

### Настройки по умолчанию
- **Theme**: Light для лучшей читаемости
- **Time range**: Last 1 hour для оперативного мониторинга
- **Refresh**: 30s (баланс real-time/производительности)

### Permissions & Organization
- **Admin**: Полный доступ к редактированию
- **Viewer**: Read-only для просмотра
- **Folder**: Все дашборды в "PolicyOS"

## Troubleshooting

### Дашборды не загружаются
- Проверьте volume mounts в docker-compose.yml
- Валидируйте JSON: `jq . dashboard.json`
- Проверьте logs: `docker logs grafana`

### Метрики отсутствуют
- Проверьте Prometheus targets (`/targets`)
- Валидируйте queries в query inspector
- Проверьте time range и label filters

### Performance issues
- Увеличьте refresh interval при нагрузке
- Используйте recording rules для сложных запросов
- Рассмотрите sharding для большого количества panels