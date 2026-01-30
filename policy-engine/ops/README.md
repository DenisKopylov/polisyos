# Операционная инфраструктура (Operations)

Директория `ops` содержит инфраструктуру для мониторинга, наблюдаемости и alerting системы PolicyOS. Предоставляет production-ready стек для трекинга производительности, обнаружения проблем и визуализации метрик.

## Архитектура

```
ops/
├── docker-compose.observability.yml    # Docker Compose для запуска стека мониторинга
├── prometheus/                         # Конфигурация Prometheus и alerting
│   ├── prometheus.yml                  # Основная конфигурация сбора метрик
│   ├── alerts.yml                      # Правила алертинга
│   ├── recording_rules.yml             # Правила предвычисления метрик
│   └── README.md                       # Документация Prometheus
├── grafana/                            # Дашборды и конфигурация визуализации
│   ├── dashboards/                     # JSON определения дашбордов
│   │   ├── executive-overview.json     # Обзор для руководства
│   │   ├── foundry-hpc.json           # Производительность HPC
│   │   └── scientist-agents.json       # Производительность агентов
│   ├── provisioning/
│   │   └── dashboards.yml              # Автоматическое provisioning дашбордов
│   └── README.md                       # Документация Grafana
└── README.md                           # Эта документация
```

## Функционал

### Запуск стека мониторинга

```bash
# Запуск полного observability стека
docker-compose -f docker-compose.observability.yml up -d

# Prometheus будет доступен на http://localhost:9090
# Grafana будет доступен на http://localhost:3000 (admin/admin)
```

### Метрики и алертинг

**Собираемые метрики:**
- **Стоимость LLM**: Потребление токенов и долларовые расходы
- **Производительность агентов**: Успешность workflow, время governance-проверок
- **HPC симуляции**: Throughput, JIT-компиляция, кеширование артефактов
- **Калибровка**: Loss, градиенты, сходимость

**Система алертинга:**
- Превышение бюджета LLM (>50$/час, >100$/час критично)
- Высокая ошибка workflow (>5%, >20% критично)
- Проблемы симуляций (застревание, низкий cache hit ratio)
- Проблемы калибровки (расходящиеся градиенты)

### Дашборды

**Executive Overview**: Ключевые метрики для руководства (стоимость, производительность)

**Scientist Agent Performance**: Детальная аналитика работы агентов, governance pipeline, LLM использование

**Foundry HPC Performance**: Производительность симуляций, JAX runtime, кеширование артефактов

## Особенности модулей

### Prometheus
- **Scrape interval**: 15 секунд для оперативного мониторинга
- **Recording rules**: Предвычисление сложных метрик для производительности
- **Alerting rules**: Автоматическое обнаружение проблем с эскалацией по severity
- **Multi-target**: Сбор метрик из PolicyOS и самого Prometheus

### Grafana
- **Автоматическое provisioning**: Дашборды загружаются автоматически при старте
- **Ролевая аналитика**: Специализированные дашборды для разных пользователей
- **Real-time**: Обновление каждые 30 секунд
- **Templating**: Фильтрация по environment (production/staging)

### Docker Compose
- **Service dependencies**: Правильный порядок запуска (Prometheus → Grafana)
- **Volume mounting**: Конфигурационные файлы монтируются read-only
- **Port mapping**: Стандартные порты для локальной разработки

## Связь с другими модулями

### Core/Observability
- **Источник метрик**: Модуль `observability` экспортирует метрики на порт 9464
- **Trace correlation**: Метрики коррелируют с distributed tracing
- **Zero-configuration**: Метрики доступны автоматически при запуске PolicyOS

### Foundry (HPC)
- **JIT monitoring**: Трекинг компиляции JAX программ
- **Simulation metrics**: Throughput, cache efficiency, calibration progress
- **Performance alerts**: Обнаружение проблем производительности

### Scientist (Agents)
- **Workflow tracking**: Метрики успешности экспериментов
- **LLM cost monitoring**: Контроль расходов на AI
- **Governance metrics**: Время и качество проверок

### Runtime (Production)
- **Production monitoring**: Полная наблюдаемость в production среде
- **Alert integration**: Автоматические оповещения о проблемах

## Быстрый старт

1. **Запуск мониторинга:**
   ```bash
   cd ops
   docker-compose -f docker-compose.observability.yml up -d
   ```

2. **Проверка метрик:**
   - Prometheus: http://localhost:9090/targets
   - Grafana: http://localhost:3000 (admin/admin)

3. **PolicyOS с метриками:**
   ```bash
   export POLISYOS_METRICS_PORT=9464
   python -m polisyos.core.observability  # или любой модуль PolicyOS
   ```

## Конфигурация

### Переменные окружения
- `POLISYOS_METRICS_PORT=9464` - Порт экспорта метрик
- `POLISYOS_LLM_BUDGET_HOURLY=50` - Бюджет LLM в долларах/час

### Кастомизация алертов
- Редактируйте `prometheus/alerts.yml` для изменения порогов
- Перезапустите Prometheus после изменений

### Добавление дашбордов
- Добавьте JSON файлы в `grafana/dashboards/`
- Grafana автоматически загрузит их при следующем запуске