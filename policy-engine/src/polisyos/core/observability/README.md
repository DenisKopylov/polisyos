# Observability (Телеметрия)

Production-grade телеметрия: OpenTelemetry трассировка, Prometheus метрики, структурированное логирование с trace correlation.

## Архитектура

```
observability/
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

## Компоненты

- **Tracer**: `PolicyOSTracer` singleton, `get_tracer()` для доступа
- **Decorators**: `@traced(phase="...", node="...")` для автоматической трассировки
- **Logs**: `TraceContextFilter`, `StructuredFormatter` для JSON логов с trace correlation
- **Metrics**: `MetricsRegistry` с Prometheus (workflow, simulation, LLM calls, artifacts)
- **Propagation**: Контекст propagation через thread/async границы

## Инструментация по фазам

- **Phase 2 (Scientist)**: Workflow nodes, LLM calls, governance pipeline, experiment tracking
- **Phase 3 (Foundry)**: JAX runtime spans, calibration metrics, CAS I/O operations

## Экспортеры и интеграции

- **OTLP**: gRPC/HTTP для Jaeger, Tempo, DataDog
- **Prometheus**: HTTP сервер на порту 9464
- **Console**: Для отладки (stdout)
- **Structured Logging**: JSON-формат для ELK, Loki, CloudWatch

## Связи с модулями

- **Core (Artifacts)**: Трассировка CAS операций и метрики производительности
- **Fabric**: Трассировка операций обработки данных
- **Foundry**: Детальная трассировка исполнения, JAX runtime, метрики калибровки
- **Scientist**: Workflow трассировка, LLM метрики, timeline tracking
- **Runtime**: Production телеметрия с distributed tracing

## Производительность

- **Overhead**: <0.1ms на операцию трассировки
- **Lazy initialization**: Загрузка конфигурации по требованию
- **Graceful fallback**: Работа при недоступности экспортеров
- **Batch processing**: Оптимизированная отправка в production
- **Sampling**: Конфигурируемое сэмплирование

## Примеры использования

### Логирование с трассировкой

```python
from polisyos.core.observability.logs import TraceContextFilter, StructuredFormatter

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.addFilter(TraceContextFilter())
handler.setFormatter(StructuredFormatter())
logger.addHandler(handler)
logger.info("Experiment started", extra={"experiment_id": "exp_123"})
```

### Async контекст propagation

```python
from polisyos.core.observability.propagation import with_trace_context

@with_trace_context
async def main():
    tasks = [async_worker(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    return results
```

### Комплексная трассировка

```python
@traced(phase="FOUNDRY", node="calibration")
def run_calibration_loop(model, dataset):
    tracer = get_tracer()
    metrics = get_metrics()

    for step in range(1000):
        with tracer.start_as_current_span("calibration_step") as span:
            span.set_attribute("step", step)
            with metrics.time_calibration_step():
                loss = train_step(model, dataset)
                metrics.calibration_loss.set(loss, {"step": step})
            if loss < 0.01:
                span.set_attribute("converged", True)
                break
    return model
```

## Заключение

Production-grade телеметрия для PolisyOS: distributed tracing, Prometheus метрики, структурированное логирование. Минимальный overhead, graceful fallback, enterprise-ready.
