# Observability (Наблюдаемость)

Модуль `observability` предоставляет production-grade систему телеметрии для PolicyOS, включая распределенную трассировку с OpenTelemetry, Prometheus-совместимые метрики, структурированное логирование с корреляцией трассировки и инструменты распространения контекста через thread/async границы.

## Обзор

Модуль обеспечивает унифицированные возможности наблюдения за всей системой PolicyOS:

- **Распределенная трассировка**: span-based моделирование с поддержкой OpenTelemetry
- **Prometheus метрики**: готовые метрики для workflow, симуляций, LLM вызовов и HPC операций
- **Структурированное логирование**: JSON-формат с автоматической инъекцией trace_id/span_id
- **Zero-configuration instrumentation**: простые декораторы для автоматической трассировки
- **Контекстная пропаганда**: распространение трассировки через потоки, async задачи и сервисы

## Архитектура

Модуль состоит из следующих компонентов:

```
observability/
├── config.py          # Конфигурация OpenTelemetry (OTelConfig, ResourceConfig)
├── tracer.py          # OpenTelemetry трассировщик (PolicyOSTracer, get_tracer)
├── decorators.py      # Декораторы для автоматической трассировки (@traced, @traced_method)
├── logs.py            # Структурированное логирование с trace correlation
├── metrics.py         # Prometheus-совместимые метрики (MetricsRegistry, HistogramTimer)
├── propagation.py     # Распространение контекста трассировки
└── __init__.py        # Экспорт основных функций
```

## Быстрый старт

```python
from polisyos.core.observability import get_tracer, get_metrics, traced

# Получение глобальных экземпляров
tracer = get_tracer()
metrics = get_metrics()

# Использование декоратора для автоматической трассировки
@traced(phase="EXECUTE", node="run_sim")
def run_simulation():
    with metrics.time_simulation({"node": "run_sim"}):
        # Логика симуляции
        pass
```

## Конфигурация

### Переменные окружения

- `POLISYOS_OTEL_ENABLED` (default: `true`) - Включение/отключение OpenTelemetry
- `POLISYOS_HPC_OBSERVABILITY_ENABLED` (default: `true`) - Включение HPC observability (Phase 3)
- `OTEL_EXPORTER_OTLP_ENDPOINT` - OTLP collector endpoint
- `OTEL_EXPORTER_OTLP_PROTOCOL` - Протокол (grpc или http/protobuf)
- `POLISYOS_OTEL_CONSOLE_EXPORT` (default: `false`) - Консольный экспорт для отладки
- `POLISYOS_METRICS_PORT` (default: `9464`) - Порт для Prometheus метрик

### Основные классы конфигурации

#### OTelConfig
Централизованная конфигурация OpenTelemetry с поддержкой переменных окружения:

```python
from polisyos.core.observability.config import OTelConfig

config = OTelConfig(
    enabled=True,
    hpc_observability_enabled=True,
    service_name="policy-engine",
    trace_exporter="otlp_grpc",
    metrics_exporter="prometheus",
    metrics_port=9464
)
```

#### ResourceConfig
Атрибуты ресурса для идентификации сервиса:

```python
from polisyos.core.observability.config import ResourceConfig

resource = ResourceConfig(
    service_name="policy-engine",
    service_version="1.0.0",
    deployment_environment="production",
    determinism_tier="REPRODUCIBLE"
)
```

## Компоненты

### 1. Tracer (Трассировщик)

#### PolicyOSTracer
Singleton-обертка для OpenTelemetry TracerProvider с ленивой инициализацией.

```python
from polisyos.core.observability import get_tracer

tracer = get_tracer()

# Создание дочернего спана
with tracer.start_as_current_span("operation_name") as span:
    span.set_attribute("custom.attribute", "value")
    # Операция
    pass
```

#### get_tracer()
Глобальный доступ к трассировщику:

```python
tracer = get_tracer()
current_context = tracer.get_current_trace_context()
```

### 2. Decorators (Декораторы)

#### @traced
Автоматическое создание спанов вокруг функций с поддержкой async/sync:

```python
from polisyos.core.observability import traced

@traced(phase="FABRIC", node="data_processor")
def process_data(input_data: dict) -> dict:
    # Функция автоматически трассируется
    return {"result": "processed"}

@traced(phase="FOUNDRY", node="simulator", attributes={"simulation_type": "agent"})
async def run_async_simulation(params: dict) -> dict:
    # Async функция тоже поддерживается
    return {"status": "completed"}
```

#### @traced_method
Специализированный декоратор для методов классов:

```python
class DataProcessor:
    @traced_method(phase="FABRIC", node="validator")
    def validate_input(self, data: dict) -> bool:
        return len(data) > 0
```

### 3. Logs (Логирование)

#### TraceContextFilter
Фильтр логирования, добавляющий trace_id и span_id:

```python
import logging
from polisyos.core.observability.logs import TraceContextFilter, StructuredFormatter

# Настройка структурированного логирования
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()

# Добавление фильтра для trace correlation
handler.addFilter(TraceContextFilter())

# JSON форматтер
handler.setFormatter(StructuredFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Логи автоматически включают trace_id и span_id
logger.info("Processing started", extra={"user_id": 123})
```

#### StructuredFormatter
JSON-форматтер для структурированного логирования совместимый с ELK stack.

#### configure_otel_logging_handler()
Интеграция с существующей системой логирования:

```python
from polisyos.core.observability.logs import configure_otel_logging_handler

# Настройка интеграции
configure_otel_logging_handler()
```

### 4. Metrics (Метрики)

#### MetricsRegistry
Singleton-реестр метрик с Prometheus-совместимыми экспортерами:

```python
from polisyos.core.observability import get_metrics

metrics = get_metrics()

# Счетчики
metrics.workflow_runs_total.add(1, {"status": "success", "phase": "EXECUTE"})
metrics.llm_calls_total.add(1, {"model": "gpt-4", "status": "success"})

# Гистограммы
with metrics.time_simulation({"node": "run_sim"}):
    run_simulation()

# Gauges
metrics.active_runs.add(1)  # Увеличить
metrics.active_runs.add(-1)  # Уменьшить
```

#### Доступные метрики

- `polisyos_workflow_runs_total` (Counter) - Общее количество запусков workflow по статусу
- `polisyos_simulation_duration_seconds` (Histogram) - Время выполнения симуляций
- `polisyos_simulation_steps_total` (Counter) - Общее количество шагов симуляции
- `polisyos_simulation_compile_seconds` (Histogram) - Время компиляции симуляций
- `polisyos_simulation_steps_per_second` (Gauge) - Шаги симуляции в секунду
- `polisyos_llm_calls_total` (Counter) - Вызовы LLM API по модели и статусу
- `polisyos_llm_tokens_total` (Counter) - Потребленные токены LLM по типу
- `polisyos_active_runs` (UpDownCounter) - Активные эксперименты
- `polisyos_validation_issues_total` (Counter) - Проблемы валидации по severity
- `polisyos_artifact_operations_total` (Counter) - Операции с артефактами CAS
- `polisyos_artifact_io_bytes` (Histogram) - Байты ввода-вывода артефактов
- `polisyos_artifact_cache_hits_total` (Counter) - Попадания в кеш артефактов
- `polisyos_artifact_cache_misses_total` (Counter) - Промахи кеша артефактов
- `polisyos_calibration_loss` (Gauge) - Потери калибровки
- `polisyos_calibration_grad_norm` (Gauge) - Норма градиента калибровки
- `polisyos_governance_pass_duration_seconds` (Histogram) - Время проходов governance

#### HistogramTimer
Контекстный менеджер для измерения времени выполнения:

```python
timer = HistogramTimer(metrics.simulation_duration_seconds, {"node": "simulator"})

with timer:
    run_expensive_operation()
```

### 5. Propagation (Распространение контекста)

#### inject_headers() / extract_headers()
Инъекция/экстракция контекста в HTTP заголовки:

```python
from polisyos.core.observability.propagation import inject_headers, extract_headers

# Инъекция в заголовки
headers = {}
inject_headers(headers)

# Экстракция из заголовков
extract_headers(headers)
```

#### propagate_context()
Контекстный менеджер для распространения контекста:

```python
from polisyos.core.observability.propagation import propagate_context

with propagate_context(headers):
    # Контекст трассировки восстановлен
    pass
```

#### TracedExecutorWrapper
Обертка для ThreadPoolExecutor с распространением трассировки:

```python
from concurrent.futures import ThreadPoolExecutor
from polisyos.core.observability.propagation import TracedExecutorWrapper

def worker_task(task_id: int):
    # Trace context наследуется автоматически
    return f"Task {task_id} completed"

with ThreadPoolExecutor() as executor:
    traced_executor = TracedExecutorWrapper(executor)
    # Все задачи в thread pool наследуют trace context
    futures = traced_executor.map(worker_task, range(10))
```

## Инструментация по фазам

### Phase 2 (Scientist - эксперименты)

- **Scientist flow nodes**: Инструментированы с атрибутами из `ExperimentState`
- **LLM calls**: Обертка `TracedLLMClient` для захвата использования токенов и статуса
- **Governance pipeline**: Спаны для каждого прохода валидации с метриками проблем
- **Scientist entrypoint**: Корневой спан workflow в `run_experiment`

### Phase 3 (Foundry - HPC симуляции)

- **JAX runtime**: Спаны и JIT-aware timing для `run_scan` и `execute_program_batch`
- **Calibration loop**: Метрики для loss, grad norm, продолжительности шагов и сходимости
- **Artifact I/O**: Спаны и метрики для CAS операций чтения/записи, попаданий в кеш и размеров payload

## Экспортеры и интеграции

### OpenTelemetry Protocol (OTLP)
- **OTLP gRPC**: Для Jaeger, Tempo, DataDog и других OTLP коллекторов
- **OTLP HTTP**: Альтернативный HTTP транспорт

### Prometheus
Встроенный HTTP сервер для сбора метрик на порту 9464.

### Console
Для отладки и разработки с выводом в stdout.

### Structured Logging
JSON-формат совместимый с ELK stack, Loki, CloudWatch.

## Связи с другими модулями

### Core (Artifacts, CAS)
Интеграция с `FileSystemCAS` для трассировки операций чтения/записи артефактов и метрик кеширования.

### Fabric (Обработка данных)
Автоматическая трассировка всех операций обработки данных с метриками производительности.

### Foundry (Симуляция и исполнение)
- Детальная трассировка всех этапов исполнения, калибровки и симуляции
- JAX runtime spans для HPC операций
- Метрики калибровки и сходимости

### Scientist (Оркестрация экспериментов)
- Трассировка полного workflow (draft → compile → execute → analyze)
- Метрики LLM вызовов и токенов
- Timeline tracking с observability coverage

### Runtime (Production исполнение)
Полная телеметрия production execution с distributed tracing для всех execution paths.

## Производительность и надежность

- **Минимальный overhead**: <0.1ms на операцию трассировки
- **Lazy initialization**: Конфигурация загружается только при первом использовании
- **Graceful fallback**: Продолжение работы при недоступности экспортеров
- **Batch processing**: Оптимизированная отправка данных в production
- **Sampling**: Конфигурируемое сэмплирование для снижения нагрузки

## Примеры использования

### Полная настройка логирования с трассировкой

```python
import logging
from polisyos.core.observability import configure_otel_logging_handler
from polisyos.core.observability.logs import TraceContextFilter, StructuredFormatter

# Настройка логирования
configure_otel_logging_handler()

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.addFilter(TraceContextFilter())
handler.setFormatter(StructuredFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Использование
logger.info("Experiment started", extra={"experiment_id": "exp_123"})
```

### Распространение контекста через async операции

```python
import asyncio
from polisyos.core.observability.propagation import with_trace_context

async def async_worker(task_id: int):
    # Контекст трассировки наследуется автоматически
    logger.info(f"Processing task {task_id}")
    return await process_task(task_id)

@with_trace_context
async def main():
    tasks = [async_worker(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    return results
```

### Комплексная трассировка симуляции

```python
from polisyos.core.observability import get_tracer, get_metrics, traced

@traced(phase="FOUNDRY", node="calibration")
def run_calibration_loop(model, dataset):
    tracer = get_tracer()
    metrics = get_metrics()

    for step in range(1000):
        with tracer.start_as_current_span("calibration_step") as span:
            span.set_attribute("step", step)

            # Измерение метрик
            with metrics.time_calibration_step():
                loss = train_step(model, dataset)
                grad_norm = compute_grad_norm(model)

            # Запись метрик
            metrics.calibration_loss.set(loss, {"step": step})
            metrics.calibration_grad_norm.set(grad_norm, {"step": step})

            if loss < 0.01:  # Сходимость
                span.set_attribute("converged", True)
                break

    return model
```

## Заключение

Модуль observability обеспечивает production-grade телеметрию для всей системы PolicyOS, гарантируя:

- **Полную наблюдаемость**: распределенная трассировка всех операций
- **Метрики производительности**: Prometheus-compatible monitoring
- **Отладку**: структурированное логирование с trace correlation
- **Надежность**: graceful fallback и минимальный overhead
- **Масштабируемость**: batch processing и sampling для production

Все компоненты спроектированы для работы в enterprise-grade средах с поддержкой распределенного трекинга, мониторинга и отладки.
