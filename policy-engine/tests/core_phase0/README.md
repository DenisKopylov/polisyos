# Core Phase 0 Tests

Тесты фундаментальных компонентов core layer - базовые примитивы и система обсервабилити для всей системы Policy Engine.

**Последнее обновление:** 1 февраля 2026
**Уровень:** Core Phase 0 (фундаментальные примитивы + Observability v2.0)
**Зависимости:** Только стандартная библиотека Python, pathlib, hashlib, opentelemetry

## Архитектурный контекст

Core Phase 0 - фундаментальная инфраструктура системы. Обеспечивает корректность базовых примитивов: content-addressable storage, канонической сериализации, environment capture, registry систем и распределенной обсервабилити (tracing, metrics, logging, context propagation).

## Структура тестов

```
core_phase0/
├── conftest.py                    # Специфичные fixtures для core + observability
├── test_artifact_store.py         # FileSystemCAS, дедупликация, integrity checks
├── test_canon_json.py             # Каноническая JSON сериализация, детерминированные хэши
├── test_decorators.py             # @traced декоратор для автоматической трассировки
├── test_environment_manifest.py   # Захват и сравнение environment манифестов
├── test_logs.py                   # Корреляция логов с trace context
├── test_metrics.py                # MetricsRegistry singleton, timers, counters
├── test_observability.py          # Интеграционные сценарии workflow tracing
├── test_propagation.py            # Распространение trace context между потоками
├── test_registry_bundle.py        # Сборка и загрузка registry bundles
├── test_run_context.py            # Контекст выполнения и артефакты producer'а
└── test_tracer.py                 # PolicyOSTracer singleton и tracing behaviors
```

## Категории тестов

### Artifact Store (`test_artifact_store.py`)

**Цель:** Content-addressable storage с дедупликацией и integrity checks.

**Ключевые тесты:** Roundtrip operations, content deduplication, canonical JSON deduplication, manifest persistence.

**Принципы:** SHA256 addressing, immutable artifacts, automatic deduplication, full provenance tracking.

### Canonical JSON (`test_canon_json.py`)

**Цель:** Детерминированная сериализация с математическими гарантиями стабильности.

**Ключевые тесты:**
- **Key Order Independence**: Порядок ключей не влияет на сериализацию
- **Float Prohibition**: Запрет на float значения (только Decimal для денег)
- **NaN/Inf Rejection**: Отклонение нечисловых значений даже в permissive mode
- **Datetime Normalization**: UTC timestamps с Z-сuffixed format
- **Golden Hash Stability**: Детерминированные SHA256 для валидных структур

**Принципы:**
- **Mathematical Stability**: Хэши независимы от порядка ключей/элементов
- **Type Safety**: Строгая типизация, запрет на неопределенные значения
- **Decimal Money**: Принудительное использование Decimal для финансовых расчетов
- **UTC Timestamps**: Нормализованное представление времени

### Registry Bundle (`test_registry_bundle.py`)

**Цель:** Централизованное управление метаданными и конфигурациями системы.

**Ключевые тесты:** Bundle construction, artifact persistence, reference integrity.

**Принципы:** Centralized metadata, version tracking, artifact-based storage.

### Environment Manifest (`test_environment_manifest.py`)

**Цель:** Захват и сравнение вычислительных окружений для reproducibility.

**Ключевые тесты:** Environment capture, manifest fingerprinting, compatibility scoring, component validation.

**Принципы:** Deterministic fingerprinting, privacy protection, risk-based comparison, fast capture (<2s).

### Run Context (`test_run_context.py`)

**Цель:** Управление жизненным циклом выполнения и метаданными producer'ов.

**Ключевые тесты:** Context initialization, trace emission, manifest writing, path resolution.

**Принципы:** Producer tracking, audit trail, reproducible execution, portable paths.

### Observability System (`test_observability.py`)

**Цель:** Интеграционные сценарии полной системы обсервабилити с workflow tracing.

**Ключевые тесты:** Full workflow trace, span hierarchy, workflow metrics, trace correlation.

**Принципы:** End-to-end tracing, hierarchical spans, distributed correlation, performance monitoring.

### Tracer (`test_tracer.py`)

**Цель:** PolicyOSTracer singleton и core tracing behaviors.

**Ключевые тесты:** Singleton pattern, lazy initialization, span creation, nested spans, attribute setting.

**Принципы:** Singleton guarantee, lazy loading, OTEL compatibility, PolicyOS extensions.

### Metrics Registry (`test_metrics.py`)

**Цель:** Централизованный реестр метрик производительности и workflow статистики.

**Ключевые тесты:** Singleton pattern, histogram timers, counter recording, workflow metrics.

**Принципы:** Centralized collection, performance monitoring, business metrics, statistical aggregation.

### Log Correlation (`test_logs.py`)

**Цель:** Корреляция лог записей с trace context для distributed tracing.

**Ключевые тесты:** Trace context in logs, TraceContextFilter, context dict extraction.

**Принципы:** Distributed tracing, correlation IDs, standard format, non-intrusive.

### Decorators (`test_decorators.py`)

**Цель:** @traced декоратор для автоматической трассировки функций.

**Ключевые тесты:** Basic decoration, async support, custom attributes, exception handling.

**Принципы:** Zero-config tracing, async compatibility, semantic attributes, error propagation.

### Context Propagation (`test_propagation.py`)

**Цель:** Распространение trace context между потоками и сервисами.

**Ключевые тесты:** Header injection/extraction, thread context, service boundaries, with_trace_context wrapper.

**Принципы:** Distributed tracing, thread safety, standard headers, async operations.

## Конфигурация окружения (conftest.py)

### Специфичные Fixtures

#### Core Fixtures
```python
@pytest.fixture()
def cas_root(tmp_path: Path) -> Path:
    return tmp_path / ".polisyos"

@pytest.fixture()
def store(cas_root: Path) -> FileSystemCAS:
    return FileSystemCAS(cas_root)

@pytest.fixture()
def producer() -> ProducerInfo:
    return ProducerInfo(
        component="tests.phase0",
        version="0.0.0",
        git=GitInfo(commit="0000000", dirty=False),
    )

@pytest.fixture()
def env_info() -> EnvInfo:
    return EnvInfo(
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=platform.platform(),
        deps_lock_hash="sha256:" + "0" * 64,
    )
```

#### Observability Fixtures
```python
@pytest.fixture()
def reset_singleton():
    """Reset singleton instances for testing."""
    from polisyos.core.observability.tracer import PolicyOSTracer
    from polisyos.core.observability.metrics import MetricsRegistry

    PolicyOSTracer._instance = None
    PolicyOSTracer._initialized = False
    MetricsRegistry._instance = None

    yield

    # Cleanup after test
    PolicyOSTracer._instance = None
    PolicyOSTracer._initialized = False
    MetricsRegistry._instance = None

@pytest.fixture()
def test_tracer_provider():
    """Configure tracer provider for testing."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    tracer_provider = TracerProvider()
    # Add in-memory exporter for testing
    from polisyos.core.observability.tracer import InMemorySpanExporter
    span_processor = SimpleSpanProcessor(InMemorySpanExporter())
    tracer_provider.add_span_processor(span_processor)

    # Set as global provider
    from opentelemetry import trace
    original_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(tracer_provider)

    yield tracer_provider

    # Restore original provider
    trace.set_tracer_provider(original_provider)

@pytest.fixture()
def in_memory_exporter(test_tracer_provider):
    """Get in-memory span exporter for assertions."""
    from polisyos.core.observability.tracer import InMemorySpanExporter
    processors = test_tracer_provider._span_processors
    for processor in processors:
        if isinstance(processor.span_exporter, InMemorySpanExporter):
            return processor.span_exporter
    raise RuntimeError("InMemorySpanExporter not found")
```

## Запуск тестов

```bash
# Все core phase 0 тесты (core + observability)
pytest tests/core_phase0/ -v

# Core компоненты
pytest tests/core_phase0/test_artifact_store.py -v
pytest tests/core_phase0/test_canon_json.py -v
pytest tests/core_phase0/test_registry_bundle.py -v
pytest tests/core_phase0/test_run_context.py -v
pytest tests/core_phase0/test_environment_manifest.py -v

# Observability система
pytest tests/core_phase0/test_observability.py -v     # Integration scenarios
pytest tests/core_phase0/test_tracer.py -v           # PolicyOSTracer singleton
pytest tests/core_phase0/test_metrics.py -v          # Metrics registry
pytest tests/core_phase0/test_logs.py -v             # Log-trace correlation
pytest tests/core_phase0/test_decorators.py -v       # @traced decorator
pytest tests/core_phase0/test_propagation.py -v      # Context propagation
```

## Связи с другими модулями

### Зависимости от Core Phase 0

**Все модули системы** используют компоненты Core Phase 0:
- **Artifact Store**: Фундаментальное хранилище для всех immutable артефактов
- **Canonical JSON**: Стандартизированная сериализация для детерминированных хэшей
- **Environment Manifest**: Захват и сравнение окружений для reproducibility и debugging
- **Registry System**: Централизованное управление метаданными и конфигурациями
- **Run Context**: Базовая инфраструктура для execution tracking и audit trails
- **Observability System**: Распределенная трассировка, метрики и логи для всей системы
- **Tracer**: Единый tracer для всех компонентов с PolicyOS extensions
- **Metrics Registry**: Централизованный сбор метрик производительности
- **Log Correlation**: Связывание логов с traces для debugging
- **Context Propagation**: Сохранение trace context в distributed operations
- **@traced Decorator**: Автоматическая трассировка функций во всех модулях

### Архитектурные инварианты

- **Закон D**: Core layer как фундамент (core → runtime → ir → fabric → foundry → scientist)
- **Content Addressing**: Все артефакты адресуются по SHA256 хэшу контента
- **Immutability**: Артефакты неизменяемы после создания
- **Provenance Tracking**: Полная traceability для всех операций
- **Observability First**: Все компоненты интегрированы с tracing/metrics/logging системой
- **Distributed Tracing**: Trace context сохраняется через все границы (threads, services, async operations)
- **Centralized Metrics**: Единая система сбора метрик для всей архитектуры
- **Log Correlation**: Каждый лог связан с trace context для debugging

## Разработка и расширение

### Добавление новых тестов

1. Используйте стандартные fixtures: `store`, `producer`, `env_info`, `test_tracer_provider`, `in_memory_exporter`
2. Тестируйте roundtrip операции для всех CRUD-like функций
3. Проверяйте integrity через SHA256 верификацию
4. Валидируйте immutable constraints (артефакты нельзя изменять)
5. Тестируйте дедупликацию для идентичного контента
6. Для observability тестов: проверяйте span creation, attribute setting, trace correlation
7. Для tracer тестов: тестируйте singleton pattern, lazy initialization, nested spans
8. Для metrics тестов: валидируйте histogram recording, counter increments
9. Для decorator тестов: проверяйте span creation, async support, custom attributes
10. Для propagation тестов: тестируйте header injection/extraction, thread context preservation
11. Для log correlation тестов: проверяйте trace_id injection в log records

### Отладка

```bash
# С подробным выводом для конкретного теста
pytest tests/core_phase0/test_canon_json.py::test_golden_hash_is_stable -v -s

# С остановкой на первой ошибке
pytest tests/core_phase0/ --tb=short -x
```

## Troubleshooting

### Распространенные проблемы

**Artifact store integrity failures:**
```bash
# Проверьте что SHA256 хэши совпадают
pytest tests/core_phase0/test_artifact_store.py::test_put_get_roundtrip_and_verify -v
```

**Canonical JSON serialization issues:**
```bash
# Проверьте запрет на float значения
pytest tests/core_phase0/test_canon_json.py::test_float_forbidden -v
```

**Registry bundle construction failures:**
```bash
# Проверьте persistence всех компонентов
pytest tests/core_phase0/test_registry_bundle.py -v
```

**Environment manifest capture issues:**
```bash
# Проверьте capture без приватных данных
pytest tests/core_phase0/test_environment_manifest.py::TestCaptureEnvironment::test_capture_no_private_data -v
# Проверьте fingerprint determinism
pytest tests/core_phase0/test_environment_manifest.py::TestEnvironmentManifest::test_manifest_fingerprint_deterministic -v
```

**Run context path resolution issues:**
```bash
# Проверьте относительные пути
pytest tests/core_phase0/test_run_context.py -v
```

**Observability system issues:**
```bash
# Проверьте tracer singleton
pytest tests/core_phase0/test_tracer.py::TestPolicyOSTracer::test_singleton_pattern -v
# Проверьте lazy initialization
pytest tests/core_phase0/test_tracer.py::TestPolicyOSTracer::test_lazy_initialization -v
```

**Span creation failures:**
```bash
# Проверьте span creation and attributes
pytest tests/core_phase0/test_tracer.py::TestPolicyOSTracer::test_span_creation -v
# Проверьте nested spans
pytest tests/core_phase0/test_tracer.py::TestPolicyOSTracer::test_nested_spans -v
```

**Metrics registry issues:**
```bash
# Проверьте singleton pattern
pytest tests/core_phase0/test_metrics.py::TestMetricsRegistry::test_singleton_pattern -v
# Проверьте histogram timer
pytest tests/core_phase0/test_metrics.py::TestMetricsRegistry::test_histogram_timer -v
```

**@traced decorator issues:**
```bash
# Проверьте basic decoration
pytest tests/core_phase0/test_decorators.py::TestTracedDecorator::test_basic_decoration -v
# Проверьте async decoration
pytest tests/core_phase0/test_decorators.py::TestTracedDecorator::test_async_decoration -v
```

**Context propagation issues:**
```bash
# Проверьте header round-trip
pytest tests/core_phase0/test_propagation.py::TestContextPropagation::test_inject_extract_headers -v
# Проверьте thread context
pytest tests/core_phase0/test_propagation.py::TestContextPropagation::test_with_trace_context_wrapper -v
```

**Log correlation issues:**
```bash
# Проверьте trace context in logs
pytest tests/core_phase0/test_logs.py::TestLogCorrelation::test_trace_context_in_logs -v
# Проверьте context dict extraction
pytest tests/core_phase0/test_logs.py::TestLogCorrelation::test_get_trace_context_dict -v
```

**Integration workflow issues:**
```bash
# Проверьте full workflow tracing
pytest tests/core_phase0/test_observability.py::TestIntegrationScenarios::test_full_workflow_trace -v
# Проверьте span hierarchy
pytest tests/core_phase0/test_observability.py::TestIntegrationScenarios::test_span_hierarchy -v
```