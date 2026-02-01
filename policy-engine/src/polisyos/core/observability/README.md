# Observability (Телеметрия)

Production-grade система телеметрии: OpenTelemetry трассировка, Prometheus метрики, структурированное логирование с trace correlation, декораторы для zero-configuration instrumentation.

## Архитектура

```
observability/
├── __init__.py        # Quick start и экспорт
├── config.py          # OTelConfig, ResourceConfig
├── tracer.py          # PolicyOSTracer, get_tracer
├── decorators.py      # @traced, @traced_method
├── logs.py            # TraceContextFilter, StructuredFormatter
├── metrics.py         # MetricsRegistry, HistogramTimer
└── propagation.py     # inject_headers, TracedExecutorWrapper
```

## Быстрый старт

```python
from polisyos.core.observability import get_tracer, get_metrics, traced

@traced(phase="EXECUTE", node="run_sim")
def run_simulation():
    with get_metrics().time_simulation({"node": "run_sim"}):
        pass
```

## Конфигурация

Переменные окружения: `POLISYOS_OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `POLISYOS_METRICS_PORT`, `POLISYOS_TRACE_SAMPLING_RATIO`.

Классы: `OTelConfig` (централизованная конфигурация), `ResourceConfig` (атрибуты сервиса). Trace sampling с head-based политикой.

## Компоненты

### Tracer
`PolicyOSTracer` singleton с ленивой инициализацией. `get_tracer()` для глобального доступа.

### Decorators
`@traced(phase="...", node="...")` для автоматической трассировки функций. `@traced_method` для классов.

### Logs
`TraceContextFilter` добавляет trace_id/span_id. `StructuredFormatter` для JSON логов.

### Metrics
`MetricsRegistry` с Prometheus экспортерами. Метрики: workflow, simulation, LLM calls, artifacts, calibration.

### Propagation
`inject_headers()`, `extract_headers()`, `propagate_context()`, `TracedExecutorWrapper` для распространения контекста через границы.

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
