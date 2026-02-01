# Agent Simulation Monitoring Tests

Тесты компонентов мониторинга, метрик и визуализации для симуляции агентов.

**Последнее обновление:** 1 февраля 2026
**Уровень:** Foundry Layer / Agent Simulation
**Зависимости:** JAX, Matplotlib, Core artifacts

## Архитектурный контекст

Agent Simulation Monitoring предоставляет комплексную систему сбора метрик, трекинга экспериментов и визуализации обучения для симуляций агентов. Тесты валидируют все аспекты monitoring pipeline от сбора данных до генерации dashboards.

## Структура тестов

```
agent_sim/
└── test_monitoring.py         # MetricsCollector, ExperimentTracker, DashboardGenerator, визуализация
```

## Категории тестов

### Metrics Collection (`MetricsCollector`)

**Цель:** Валидация системы сбора и хранения метрик обучения агентов.

**Ключевые тесты:**
- **Collector Creation**: Инициализация коллектора с custom метриками
- **Metrics Collection**: Сбор метрик на каждом шаге симуляции
- **History Management**: Управление историей метрик с ограничением размера
- **Step Counting**: Корректный подсчет шагов симуляции

**Принципы:**
- **Structured Metrics**: Типизированная система метрик (scalar, histogram, distribution)
- **Memory Efficiency**: Ограничение истории для предотвращения memory leaks
- **Thread Safety**: Безопасная работа в многопоточной среде

### Experiment Tracking (`ExperimentTracker`)

**Цель:** Трекинг экспериментов с конфигурациями, результатами и метаданными.

**Ключевые тесты:**
- **Experiment Config**: Валидация конфигураций экспериментов
- **Run Tracking**: Отслеживание прогресса и результатов экспериментов
- **Metadata Storage**: Сохранение метаданных экспериментов
- **Experiment History**: Управление историей экспериментов

**Принципы:**
- **Immutable Configs**: Конфигурации экспериментов неизменяемы после старта
- **Structured Results**: Стандартизированные форматы результатов
- **Metadata Richness**: Богатые метаданные для анализа и воспроизводимости

### Dashboard Generation (`DashboardGenerator`)

**Цель:** Автоматическая генерация визуализаций и отчетов обучения.

**Ключевые тесты:**
- **Visualization Config**: Настройка параметров визуализации
- **Plot Generation**: Создание графиков различных типов
- **Dashboard Layout**: Компоновка dashboard'ов
- **Export Formats**: Поддержка различных форматов экспорта

**Принципы:**
- **Automated Generation**: Полностью автоматическая генерация визуализаций
- **Configurable Layout**: Настраиваемые layouts и стили
- **Multiple Formats**: Поддержка PNG, SVG, HTML форматов

### Training Visualization (`TrainingVisualizer`)

**Цель:** Специализированные визуализации для обучения агентов.

**Ключевые тесты:**
- **Training Curves**: Визуализация кривых обучения
- **Agent Behavior**: Анализ поведения агентов
- **Performance Metrics**: Визуализация метрик производительности
- **Convergence Analysis**: Анализ сходимости обучения

**Принципы:**
- **Real-time Updates**: Возможность обновления в реальном времени
- **Interactive Elements**: Интерактивные элементы для детального анализа
- **Statistical Summaries**: Статистические сводки и confidence intervals

### Behavior Analysis (`BehaviorAnalyzer`)

**Цель:** ML-based анализ поведения агентов и паттернов.

**Ключевые тесты:**
- **Clustering Algorithms**: Кластеризация агентов по поведению
- **Pattern Recognition**: Распознавание паттернов в поведении
- **Behavioral Diversity**: Оценка разнообразия поведения
- **Anomaly Detection**: Детекция аномального поведения

**Принципы:**
- **Unsupervised Learning**: Автоматическое обнаружение паттернов
- **Statistical Validation**: Статистическая валидация кластеров
- **Scalability**: Эффективная работа с большим количеством агентов

## Запуск тестов

```bash
# Все тесты agent simulation monitoring
pytest tests/foundry/agent_sim/ -v

# Конкретные компоненты
pytest tests/foundry/agent_sim/test_monitoring.py::TestMetricsCollector -v
pytest tests/foundry/agent_sim/test_monitoring.py::TestExperimentTracker -v
pytest tests/foundry/agent_sim/test_monitoring.py::TestDashboardGenerator -v
pytest tests/foundry/agent_sim/test_monitoring.py::TestBehaviorAnalyzer -v
```

## Конфигурация окружения

### JAX Configuration (conftest.py в корне)
```python
# CPU enforcement для consistency
os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```

### Visualization Dependencies
- **Matplotlib**: Основная библиотека визуализации
- **Seaborn**: Статистические визуализации
- **Plotly**: Интерактивные графики (опционально)

## Связи с другими модулями

### Зависимости Agent Simulation Monitoring

**Core Layer** (`core/`):
- **Artifact Storage**: Сохранение результатов экспериментов и визуализаций

**Foundry Layer** (`foundry/`):
- **Global State**: Источник данных для метрик
- **Agent Simulation**: Основной источник данных для анализа

### Потребители Agent Simulation Monitoring

**Scientist Layer** (`scientist/`):
- **Experiment Orchestration**: Использование трекинга для управления экспериментами

**Integration Layer** (`integration/`):
- **Workflow Monitoring**: Мониторинг end-to-end симуляций

### Архитектурные инварианты

- **Monitoring Overhead**: Минимальный overhead на симуляцию
- **Real-time Capability**: Возможность real-time мониторинга
- **Data Integrity**: Гарантии целостности собранных данных

## Разработка и расширение

### Добавление новых monitoring тестов

1. **Для metrics**: Определяйте новые типы метрик с соответствующими compute functions
2. **Для visualization**: Добавляйте новые типы графиков и layouts
3. **Для analysis**: Реализуйте новые алгоритмы анализа поведения
4. **Всегда проверяйте performance**: Мониторинг не должен замедлять симуляцию

### Структура monitoring теста

```python
def test_monitoring_component():
    # Setup: create monitoring component
    component = MonitoringComponent(config)

    # Execute: run monitoring operation
    result = component.process_data(data)

    # Verify: check monitoring results
    assert result.metrics_valid
    assert result.visualization_generated
```

## Troubleshooting

### Распространенные проблемы

**Memory issues с большими экспериментами:**
```bash
# Уменьшите max_history
collector = MetricsCollector(metrics, max_history=50)
```

**Visualization failures:**
```bash
# Проверьте matplotlib backend
pytest tests/foundry/agent_sim/test_monitoring.py::TestDashboardGenerator -v -s
```

**Experiment tracking corruption:**
```bash
# Проверьте filesystem permissions
pytest tests/foundry/agent_sim/test_monitoring.py::TestExperimentTracker -v
```

## Технологии и зависимости

### Core Monitoring Stack
- **JAX**: Вычислительная основа для метрик
- **Matplotlib/Seaborn**: Визуализация результатов
- **Pandas**: Data manipulation для анализа

### Experiment Management
- **Pathlib**: Файловая система для хранения результатов
- **JSON/YAML**: Сериализация конфигураций и метаданных

### Analysis Components
- **Scikit-learn**: ML алгоритмы для анализа поведения
- **NumPy**: Численные операции для статистики