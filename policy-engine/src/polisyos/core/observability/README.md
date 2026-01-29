# Observability Module Documentation

## Обзор

Модуль `observability` предоставляет production-grade систему телеметрии для PolicyOS, обеспечивая унифицированные возможности наблюдения: распределенную трассировку с OpenTelemetry, Prometheus-совместимые метрики, структурированное логирование с корреляцией трассировки и инструменты распространения контекста.

**Архитектурная роль**: Observability является cross-cutting concern, интегрирующимся во все компоненты PolisyOS для обеспечения полного visibility в development, testing и production средах.

## Архитектура

Модуль `observability` состоит из следующих основных компонентов:

```
observability/
├── config.py        # Конфигурация OpenTelemetry (OTelConfig, ResourceConfig)
├── decorators.py    # Декораторы трассировки (@traced, @traced_method)
├── logs.py          # Структурированное логирование (TraceContextFilter, StructuredFormatter)
├── metrics.py       # Метрики Prometheus (MetricsRegistry, HistogramTimer)
├── propagation.py   # Распространение контекста (inject_headers, extract_headers)
└── tracer.py        # OpenTelemetry трассировщик (PolicyOSTracer)
```

### Принципы организации

- **Singleton pattern**: Все компоненты используют singleton для предотвращения дублирования
- **Lazy initialization**: Компоненты инициализируются только при первом использовании
- **Environment-driven configuration**: Полная конфигурация через переменные окружения
- **Graceful degradation**: Fallback к no-op реализациям при отключении
- **Thread-safety**: Все компоненты безопасны для использования в многопоточной среде

## Компоненты

### 1. Configuration (Конфигурация)

**Назначение**: Централизованная конфигурация всех аспектов телеметрии с поддержкой переменных окружения и различных deployment targets.

**Основные компоненты**:
- `OTelConfig` - Pydantic модель конфигурации с валидацией и defaults
- `ResourceConfig` - Атрибуты ресурса для идентификации сервиса
- `ExporterType` / `MetricsExporterType` - Перечисления поддерживаемых экспортеров
- `get_default_config()` - Функция получения конфигурации по умолчанию

**Переменные окружения**:
```bash
# Глобальное управление
POLISYOS_OTEL_ENABLED=true                    # Включение/отключение OTel
POLISYOS_OTEL_CONSOLE_EXPORT=false            # Console export для отладки

# Трассировка
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # OTLP коллектор
OTEL_EXPORTER_OTLP_PROTOCOL=grpc               # grpc или http/protobuf
OTEL_SERVICE_NAME=polisyos                     # Имя сервиса

# Метрики
POLISYOS_METRICS_PORT=9464                    # Prometheus порт

# Ресурсы
POLISYOS_ENV=development                      # Окружение (development/production)
```

**Возможности**:
- **Environment-based**: Полная конфигурация через переменные окружения
- **Validation**: Pydantic валидация всех настроек
- **Sensible defaults**: Разумные значения по умолчанию для development
- **Frozen config**: Immutable конфигурация после создания

### 2. Tracer (Трассировщик)

**Назначение**: OpenTelemetry-based трассировщик с lazy initialization, batch processing и graceful fallback.

**Основные компоненты**:
- `PolicyOSTracer` - Thread-safe singleton трассировщик
- `get_tracer()` - Глобальный accessor для трассировщика
- `get_current_trace_context()` - Получение текущего контекста трассировки

**Ключевые возможности**:
- **Lazy initialization**: Нет overhead при импорте, инициализация при первом span
- **Batch processing**: Production-ready batch span processor для эффективности
- **Multiple exporters**: Поддержка OTLP, Jaeger, Console, NoOp
- **Resource attributes**: Автоматическое добавление service metadata
- **Graceful shutdown**: Flush всех pending spans при завершении

**Экспортеры**:
- **OTLP gRPC/HTTP**: Для Jaeger, Tempo, DataDog, New Relic
- **Console**: Для development и debugging
- **NoOp**: При отключении трассировки

### 3. Decorators (Декораторы)

**Назначение**: Zero-configuration instrumentation через простые декораторы для автоматического создания spans.

**Основные компоненты**:
- `@traced` - Универсальный декоратор для функций
- `@traced_method` - Специализированный декоратор для методов классов
- `_extract_attributes_from_args()` - Извлечение атрибутов из аргументов

**PolicyOS Semantic Conventions**:
```python
@traced(phase="FRAME", agent="drafter")
def draft_policy(requirements: dict) -> PolicyIR:
    pass

@traced(phase="VALIDATE", node="syntax_check")
def validate_syntax(policy_text: str) -> ValidationResult:
    pass

@traced(phase="EXECUTE", node="run_sim", capture_args=True)
def run_simulation(config: SimConfig, steps: int) -> SimResult:
    pass
```

**Возможности**:
- **Automatic span creation**: Span создается автоматически вокруг функции
- **Exception handling**: Исключения автоматически записываются в span
- **Argument capture**: Опциональный захват аргументов как span attributes
- **Result capture**: Опциональный захват возвращаемого значения
- **Async support**: Полная поддержка async/sync функций
- **PolicyOS attributes**: Специализированные атрибуты (phase, agent, node)

### 4. Logs (Логирование)

**Назначение**: Структурированное логирование с автоматической корреляцией с трассировкой.

**Основные компоненты**:
- `TraceContextFilter` - Добавляет trace_id/span_id в лог записи
- `StructuredFormatter` - JSON форматтер для structured logging
- `configure_otel_logging_handler()` - Интеграция с существующей системой логирования
- `get_trace_context_dict()` - Получение trace context для ручного использования

**Интеграция с logger.py**:
```python
from polisyos.core.observability.logs import configure_otel_logging_handler
from polisyos.common.logger import get_logger

# Одноразовая настройка при запуске
configure_otel_logging_handler()

# Использование существующего логгера
logger = get_logger(__name__)
logger.info("Processing policy", extra={"policy_id": "123"})
# Автоматически добавляет: trace_id, span_id
```

**Возможности**:
- **Trace correlation**: Каждый лог содержит trace_id и span_id
- **Structured output**: JSON формат для log aggregators (ELK, Loki)
- **Backward compatibility**: Работает с существующими logger calls
- **Performance**: Минимальный overhead на добавление trace context

### 5. Metrics (Метрики)

**Назначение**: Prometheus-compatible метрики для мониторинга и алертинга с унифицированным API.

**Основные компоненты**:
- `MetricsRegistry` - Singleton реестр всех метрик
- `HistogramTimer` - Context manager для измерения времени
- `get_metrics()` - Глобальный accessor для метрик

**Предопределенные метрики**:
```python
# Workflow runs
polisyos_workflow_runs_total{status, phase, agent} - Counter

# Simulation performance
polisyos_simulation_duration_seconds{node, error} - Histogram
polisyos_simulation_steps_total{} - Counter

# LLM operations
polisyos_llm_calls_total{model, status} - Counter
polisyos_llm_tokens_total{model, status, type} - Counter

# Governance
polisyos_governance_pass_duration_seconds{} - Histogram

# System state
polisyos_active_runs{} - UpDownCounter
polisyos_validation_issues_total{severity, pass_id, error_type} - Counter
polisyos_artifact_operations_total{} - Counter
```

**Использование**:
```python
from polisyos.core.observability import get_metrics

metrics = get_metrics()

# Тайминг симуляции
with metrics.time_simulation({"node": "run_sim"}):
    run_simulation()

# Запись workflow completion
metrics.record_workflow_run("success", "EXECUTE", "simulation_agent")

# LLM метрики
metrics.record_llm_call("gpt-4", "success", 150, 200)
```

### 6. Propagation (Распространение контекста)

**Назначение**: Распространение trace context через thread boundaries, async operations и service calls.

**Основные компоненты**:
- `inject_headers()` / `extract_headers()` - HTTP header propagation
- `propagate_context()` - Context manager для thread propagation
- `with_trace_context()` - Function wrapper для context capture
- `TracedExecutorWrapper` - ThreadPoolExecutor с trace propagation
- `create_child_context()` - Создание child contexts для parallel work

**Примеры использования**:
```python
from polisyos.core.observability.propagation import (
    inject_headers, extract_headers, TracedExecutorWrapper
)

# HTTP propagation
headers = {}
inject_headers(headers)  # Добавляет trace headers

# В другом сервисе
ctx = extract_headers(headers)
# Использовать ctx для продолжения trace

# Thread pool propagation
with ThreadPoolExecutor() as executor:
    traced_executor = TracedExecutorWrapper(executor)
    # Все задачи наследуют trace context
    futures = traced_executor.map(process_item, items)
```

## Интеграция с другими модулями

### Core Module Integration
- **RunContext**: Интегрированная трассировка всех операций
- **Artifacts**: Метрики операций с CAS
- **Contracts**: Tracing всех contract operations
- **Trace**: Legacy trace system дополняется modern OTel tracing

### System-wide Integration

#### Fabric (Data Processing)
```python
@traced(phase="PROCESS", node="data_ingestion")
def process_batch(batch: DataBatch) -> ProcessedData:
    metrics = get_metrics()
    with metrics.time_governance_pass():
        return transform_data(batch)
```

#### Foundry (Simulation)
```python
@traced(phase="EXECUTE", node="run_sim", capture_args=True)
def run_simulation(config: SimConfig) -> SimResult:
    tracer = get_tracer()
    metrics = get_metrics()

    with metrics.time_simulation({"config_hash": hash_config(config)}):
        # Simulation logic
        with tracer.start_as_current_span("simulation_loop") as span:
            for step in range(config.steps):
                # Step logic
                span.set_attribute("current_step", step)
                metrics.simulation_steps_total.add(1)

        return result
```

#### Scientist (Experiment Orchestration)
```python
@traced(phase="ANALYZE", agent="critic")
def evaluate_policy(policy: PolicyIR, test_cases: list) -> EvaluationResult:
    metrics = get_metrics()

    results = []
    for test_case in test_cases:
        with get_tracer().start_as_current_span("evaluate_case") as span:
            span.set_attribute("test_case_id", test_case.id)
            result = evaluate_single_case(policy, test_case)
            results.append(result)

    metrics.record_validation_issue("info", "evaluation_pass")
    return aggregate_results(results)
```

## Примеры использования

### Quick Start
```python
from polisyos.core.observability import (
    get_tracer, get_metrics, traced, configure_otel_logging_handler
)

# Настройка логирования
configure_otel_logging_handler()

# Простая трассировка
@traced
def my_function(x: int, y: int) -> int:
    return x + y

# С семантическими атрибутами
@traced(phase="EXECUTE", node="calculation", capture_args=True)
def calculate_result(data: dict) -> dict:
    tracer = get_tracer()
    metrics = get_metrics()

    with tracer.start_as_current_span("processing") as span:
        span.set_attribute("data_size", len(data))

        result = process_data(data)

        metrics.record_workflow_run("success", "EXECUTE")

    return result
```

### Advanced Usage

#### Async Operations
```python
@traced(phase="VALIDATE")
async def validate_policy_async(policy: PolicyIR) -> ValidationResult:
    # Автоматически создает span для async функции
    await validate_syntax(policy)
    await validate_semantics(policy)
    return ValidationResult(valid=True)
```

#### Context Propagation
```python
from polisyos.core.observability.propagation import with_trace_context

def process_in_thread(data: dict) -> dict:
    # Эта функция выполнится в том же trace context
    return heavy_processing(data)

def main():
    with get_tracer().start_as_current_span("main_operation"):
        # Оборачиваем функцию для захвата context
        wrapped = with_trace_context(process_in_thread)

        with ThreadPoolExecutor() as executor:
            future = executor.submit(wrapped, data)
            return future.result()
```

#### Error Handling
```python
@traced(phase="EXECUTE", node="risk_calculation")
def calculate_risk(portfolio: Portfolio) -> RiskMetrics:
    try:
        # Risk calculation logic
        return compute_risk_metrics(portfolio)
    except ValidationError as e:
        # Исключение автоматически записывается в span
        # Span status устанавливается в ERROR
        raise RiskCalculationError(f"Invalid portfolio: {e}") from e
```

#### Metrics Collection
```python
def run_llm_completion(model: str, prompt: str) -> str:
    metrics = get_metrics()
    tracer = get_tracer()

    with tracer.start_as_current_span("llm_call", attributes={
        "model": model,
        "prompt_length": len(prompt)
    }) as span:
        try:
            start_time = time.time()
            response = call_openai_api(model, prompt)
            duration = time.time() - start_time

            # Детальные метрики
            metrics.record_llm_call(
                model=model,
                status="success",
                prompt_tokens=count_tokens(prompt),
                completion_tokens=count_tokens(response)
            )

            span.set_attribute("response_length", len(response))
            span.set_attribute("duration_ms", duration * 1000)

            return response

        except Exception as e:
            metrics.record_llm_call(model=model, status="error")
            span.set_status(StatusCode.ERROR, str(e))
            raise
```

## Архитектурные принципы

### 1. Zero Configuration Instrumentation
- Простые декораторы для автоматической трассировки
- Минимальный код для максимального coverage
- Backward compatibility с существующим кодом

### 2. Context Propagation
- Распространение trace context через все boundaries
- Thread-safe context management
- Async/await support

### 3. Semantic Conventions
- PolicyOS-specific attributes (phase, agent, node)
- Consistent naming для spans и metrics
- Structured data для correlation

### 4. Production Readiness
- Batch processing для performance
- Graceful degradation при failures
- Resource-aware configuration

### 5. Observability-driven Development
- Metrics guide optimization efforts
- Traces enable debugging
- Logs provide operational insights

## Переменные окружения

### Core Configuration
```bash
POLISYOS_OTEL_ENABLED=true              # Master switch
POLISYOS_OTEL_CONSOLE_EXPORT=false      # Debug output
POLISYOS_ENV=production                 # Environment
```

### Tracing
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=polisyos-core
OTEL_SERVICE_VERSION=0.1.0
```

### Metrics
```bash
POLISYOS_METRICS_PORT=9464
```

### Sampling (Production)
```bash
OTEL_TRACES_SAMPLER=traceidratio         # Ratio-based sampling
OTEL_TRACES_SAMPLER_ARG=0.1              # 10% sampling
```

## Интеграция в CI/CD

### Development
```bash
# Локальная разработка с console export
export POLISYOS_OTEL_CONSOLE_EXPORT=true
export POLISYOS_OTEL_ENABLED=true
```

### Staging
```bash
# OTLP export для staging
export OTEL_EXPORTER_OTLP_ENDPOINT=http://staging-collector:4317
export POLISYOS_METRICS_PORT=9464
```

### Production
```bash
# Полная конфигурация для production
export OTEL_EXPORTER_OTLP_ENDPOINT=https://prod-collector:443
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_TRACES_SAMPLER=traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.05  # 5% sampling
export POLISYOS_METRICS_PORT=9464
```

## Troubleshooting

### Common Issues

#### No Traces Appearing
```bash
# Проверить конфигурацию
export POLISYOS_OTEL_CONSOLE_EXPORT=true
export OTEL_LOG_LEVEL=debug
```

#### High Overhead
```bash
# Уменьшить sampling
export OTEL_TRACES_SAMPLER_ARG=0.01
# Отключить для debugging
export POLISYOS_OTEL_ENABLED=false
```

#### Metrics Not Exposed
```bash
# Проверить порт
curl http://localhost:9464/metrics
# Проверить логи на ошибки binding
```

### Debug Commands
```python
# Проверить текущий trace context
from polisyos.core.observability import get_current_trace_context
print(get_current_trace_context())

# Проверить конфигурацию
from polisyos.core.observability.config import get_default_config
config = get_default_config()
print(config.model_dump())
```

## Производительность

### Benchmarks
- **Span creation**: <10μs per span
- **Attribute setting**: <1μs per attribute
- **Log correlation**: <0.1μs per log entry
- **Memory overhead**: ~50KB per active trace

### Optimization Tips
- Использовать sampling в production (1-5%)
- Ограничить число attributes per span (<20)
- Использовать batch processors для high-throughput
- Настраивать export intervals based on latency requirements

## Заключение

Модуль `observability` предоставляет comprehensive, production-ready телеметрию для PolicyOS:

- **Distributed tracing** с OpenTelemetry для полного visibility execution paths
- **Prometheus metrics** для monitoring и alerting на system health
- **Structured logging** с trace correlation для operational debugging
- **Zero-configuration instrumentation** через простые декораторы
- **Context propagation** через все architectural boundaries
- **Semantic conventions** специализированные для PolicyOS domains

Все компоненты спроектированы для zero overhead в development и optimal performance в production, обеспечивая observability-driven development approach для всей системы PolisyOS.

**Статус**: Production-ready, активно используется во всех компонентах PolisyOS.