# Core Phase 0 Tests

Тесты фундаментальных компонентов core layer - базовые примитивы и система обсервабилити для всей системы Policy Engine.

**Последнее обновление:** 29 января 2026
**Уровень:** Core Phase 0 (фундаментальные примитивы + Observability)
**Зависимости:** Только стандартная библиотека Python, pathlib, hashlib, opentelemetry

## Архитектурный контекст

Core Phase 0 представляет собой фундаментальную инфраструктуру, на которой строятся все остальные компоненты системы. Эти тесты обеспечивают корректность базовых примитивов хранения, сериализации, управления метаданными и распределенной обсервабилити (tracing, metrics, logging).

## Структура тестов

```
core_phase0/
├── conftest.py                    # Специфичные fixtures для core тестов + observability fixtures
├── test_artifact_store.py         # FileSystemCAS, дедупликация, верификация integrity
├── test_canon_json.py             # Каноническая JSON сериализация, детерминированные хэши
├── test_decorators.py             # @traced декоратор для автоматической трассировки функций
├── test_environment_manifest.py   # Захват и сравнение environment манифестов
├── test_logs.py                   # Корреляция логов с trace context
├── test_metrics.py                # MetricsRegistry singleton, histogram timers, counters
├── test_observability.py          # Интеграционные сценарии обсервабилити, workflow tracing
├── test_propagation.py            # Распространение trace context между потоками/сервисами
├── test_registry_bundle.py        # Сборка и загрузка registry bundles
├── test_run_context.py            # Контекст выполнения и артефакты producer'а
└── test_tracer.py                 # PolicyOSTracer singleton и core tracing behaviors
```

## Категории тестов

### Artifact Store (`test_artifact_store.py`)

**Цель:** Валидация content-addressable storage с дедупликацией и integrity checks.

**Ключевые тесты:**
- **Roundtrip Operations**: `put_bytes` → `get_bytes` с верификацией SHA256
- **Content Deduplication**: Идентичный контент производит одинаковые artifact ID
- **Canonical JSON Deduplication**: Нормализованная сериализация предотвращает дубликаты
- **Manifest Persistence**: Сохранение и загрузка метаданных артефактов

**Принципы:**
- **SHA256 Addressing**: Content-addressable storage с криптографической integrity
- **Immutable Artifacts**: Артефакты неизменяемы после создания
- **Deduplication**: Автоматическое обнаружение и переиспользование идентичного контента
- **Metadata Tracking**: Полная provenance информация для каждого артефакта

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

**Ключевые тесты:**
- **Bundle Construction**: Сборка полного registry bundle из компонентов
- **Artifact Persistence**: Все registry компоненты сохраняются как артефакты
- **Reference Integrity**: Корректные ссылки между компонентами bundle

**Принципы:**
- **Centralized Metadata**: Единое место для всех системных конфигураций
- **Version Tracking**: Полная traceability версий registry компонентов
- **Artifact-based Storage**: Registry данные immutable и versioned

### Environment Manifest (`test_environment_manifest.py`)

**Цель:** Захват и сравнение вычислительных окружений для обеспечения reproducibility.

**Ключевые тесты:**
- **Environment Capture**: Захват CPU/GPU/OS/Python/JAX информации без приватных данных
- **Manifest Fingerprinting**: Детерминированные SHA256 fingerprints для environment comparison
- **Compatibility Scoring**: Автоматическое определение compatibility между окружениями с risk levels
- **Component Validation**: Валидация отдельных компонентов (CPU info, GPU info, OS info, etc.)

**Принципы:**
- **Deterministic Fingerprinting**: Стабильные хэши независимо от порядка компонентов
- **Privacy Protection**: Исключение hostname, username и других приватных данных
- **Risk-based Comparison**: Классификация различий по уровням риска (CRITICAL/HIGH/MEDIUM/LOW/INFO)
- **Performance Bounds**: Быстрый capture (< 2 сек) для CI/CD интеграции

### Run Context (`test_run_context.py`)

**Цель:** Управление жизненным циклом выполнения и метаданными producer'ов.

**Ключевые тесты:**
- **Context Initialization**: Создание run context с producer метаданными
- **Trace Emission**: Запись операций в audit trail
- **Manifest Writing**: Сохранение run manifest с детерминированными seed'ами
- **Path Resolution**: Корректное разрешение относительных путей артефактов

**Принципы:**
- **Producer Tracking**: Полная информация о создателе и окружении
- **Audit Trail**: JSON Lines логирование всех операций с timestamps
- **Reproducible Execution**: Детерминированные seed'ы для воспроизводимости
- **Portable Paths**: Относительные пути для переносимости между окружениями

### Observability System (`test_observability.py`)

**Цель:** Интеграционные сценарии полной системы обсервабилити с workflow tracing.

**Ключевые тесты:**
- **Full Workflow Trace**: Полный цикл policy workflow (draft → validate → execute → decide) с tracing
- **Span Hierarchy**: Корректная иерархия spans и trace correlation
- **Workflow Metrics**: Интеграция метрик в traced operations
- **Trace Correlation**: Единый trace_id для всего workflow

**Принципы:**
- **End-to-End Tracing**: Полное покрытие workflow операций
- **Hierarchical Spans**: Логическая структура parent/child spans
- **Distributed Correlation**: Trace context preservation across operations
- **Performance Monitoring**: Метрики интегрированы в tracing infrastructure

### Tracer (`test_tracer.py`)

**Цель:** Валидация PolicyOSTracer singleton и core tracing behaviors.

**Ключевые тесты:**
- **Singleton Pattern**: Гарантия единственного экземпляра tracer'а
- **Lazy Initialization**: Инициализация только при первом использовании
- **Span Creation**: Создание spans с корректными атрибутами
- **Nested Spans**: Корректная вложенность и иерархия spans
- **Attribute Setting**: PolicyOS-specific атрибуты (phase, node, agent, run_id)

**Принципы:**
- **Singleton Guarantee**: Один tracer на всю систему
- **Lazy Loading**: Экономия ресурсов при инициализации
- **OpenTelemetry Compatibility**: Стандартные OTEL интерфейсы
- **PolicyOS Extensions**: Специфические атрибуты для policy workflows

### Metrics Registry (`test_metrics.py`)

**Цель:** Тестирование централизованного реестра метрик производительности и workflow статистики.

**Ключевые тесты:**
- **Singleton Pattern**: Гарантия единственного экземпляра metrics registry
- **Histogram Timers**: Запись duration метрик для операций
- **Counter Recording**: Инкремент счетчиков для различных событий
- **Workflow Metrics**: Специфические метрики для policy workflows

**Принципы:**
- **Centralized Collection**: Единая точка сбора всех метрик
- **Performance Monitoring**: Duration и throughput metrics
- **Business Metrics**: Workflow completion, success rates
- **Statistical Aggregation**: Histogram-based распределения

### Log Correlation (`test_logs.py`)

**Цель:** Корреляция лог записей с trace context для distributed tracing.

**Ключевые тесты:**
- **Trace Context in Logs**: Автоматическое добавление trace_id в лог records
- **TraceContextFilter**: Фильтр для enrichment лог записей
- **Context Dict Extraction**: Получение текущего trace context

**Принципы:**
- **Distributed Tracing**: Trace context в каждом лог сообщении
- **Correlation IDs**: Связывание логов с traces для debugging
- **Standard Format**: Совместимый с OTEL trace format
- **Non-Intrusive**: Минимальное влияние на performance logging'а

### Decorators (`test_decorators.py`)

**Цель:** Тестирование @traced декоратора для автоматической трассировки функций.

**Ключевые тесты:**
- **Basic Decoration**: Создание spans для decorated функций
- **Async Support**: Работа с async/await функциями
- **Custom Attributes**: Применение phase/node/agent атрибутов
- **Exception Handling**: Корректная обработка исключений в spans

**Принципы:**
- **Zero-Config Tracing**: Автоматическая трассировка без boilerplate
- **Async Compatibility**: Поддержка async функций и корутин
- **Semantic Attributes**: Богатые метаданные для policy operations
- **Error Propagation**: Исключения правильно отражаются в spans

### Context Propagation (`test_propagation.py`)

**Цель:** Распространение trace context между потоками и сервисами.

**Ключевые тесты:**
- **Header Injection/Extraction**: Round-trip через HTTP headers
- **Thread Context**: Сохранение context при thread transitions
- **Service Boundaries**: Context preservation across service calls
- **with_trace_context**: Wrapper для сохранения context

**Принципы:**
- **Distributed Tracing**: Context через network boundaries
- **Thread Safety**: Context preservation в multi-threaded environments
- **Standard Headers**: Совместимый с W3C Trace Context format
- **Asynchronous Operations**: Context в async workflows

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