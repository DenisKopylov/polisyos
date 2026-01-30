# Core Module Documentation

## Обзор

Модуль `core` представляет собой фундаментальную часть системы PolisyOS, предоставляя основные протоколы и инфраструктуру для работы с артефактами, трассировкой, каноническим JSON, контрактами между модулями и контекстами выполнения. Модуль обеспечивает надежность, воспроизводимость и наблюдаемость всей системы.

**Архитектурная роль**: Core является самым нижним слоем в иерархии зависимостей PolisyOS, предоставляя примитивы, используемые всеми остальными модулями системы. Все модули (Fabric, Foundry, IR, Scientist, Runtime) зависят от core, но core не зависит ни от одного модуля системы. Core реализует паттерн "Clean Architecture" с четким разделением ответственности и строгой типизацией.

## Архитектура

```
core/
├── artifacts/          # Управление артефактами и их хранением
│   ├── ids.py          # Уникальные идентификаторы артефактов (ArtifactID)
│   ├── manifest.py     # Метаданные артефактов (ArtifactManifest, ArtifactRef)
│   ├── environment.py  # Манифесты окружения для reproducible симуляций (EnvironmentManifest)
│   ├── registry.py     # Пакеты реестров компонентов (RegistryBundle)
│   └── store.py        # Хранилище артефактов (FileSystemCAS, PutOptions, VerificationReport)
├── canon/              # Каноническая сериализация JSON
│   └── canon_json.py   # Детерминированная сериализация (CanonSpec, to_canonical_bytes)
├── compiler/           # Отчеты компиляции и линковки
│   └── report.py       # Управление отчетами компиляции (CompileReport, put_compile_report)
├── contracts/          # Контракты между модулями системы
│   ├── compiler.py     # Контракты компилятора (CompileReportRef, LinkReportRef)
│   ├── fabric.py       # Контракты Fabric (6 типов ссылок + модели данных)
│   ├── foundry.py      # Контракты Foundry (15+ типов ссылок + модели исполнения, AgentPolicy, Patch-based state management)
│   ├── scientist.py    # Контракты Scientist (ArtifactRef, FailureCardRef, PolicyIRRef, CritiqueRef, TimelineRef, DecisionCardRef)
│   ├── trinity.py      # Trinity контракты (ProblemFrame, PolicySpec, ModelSpec, TrinityBundle)
│   └── legal.py        # Legal compliance контракты (NormPack, NormRule, RuleType, RuleBackend)
├── observability/      # Production-grade телеметрия и мониторинг
│   ├── config.py       # Конфигурация OpenTelemetry (OTelConfig, ResourceConfig)
│   ├── decorators.py   # Декораторы для автоматической трассировки (@traced, @traced_method)
│   ├── logs.py         # Структурированное логирование с trace correlation (TraceContextFilter, StructuredFormatter)
│   ├── metrics.py      # Prometheus-совместимые метрики (MetricsRegistry, HistogramTimer)
│   ├── propagation.py  # Распространение контекста трассировки (inject_headers, extract_headers)
│   └── tracer.py       # OpenTelemetry трассировщик (PolicyOSTracer, get_tracer)
├── registry/           # Сборка и загрузка реестров компонентов
│   ├── builder.py      # Сборка реестров (build_default_registry_bundle, build_registry_bundle)
│   └── loader.py       # Загрузка реестров (load_registry_bundle_content, load_registry_bundle_payload)
├── run/                # Контексты и манифесты выполнения
│   ├── context.py      # Контекст выполнения (RunContext)
│   └── manifest.py     # Манифест выполнения (RunManifest)
└── trace/              # Трассировка и логирование операций
    ├── record.py       # Записи трассировки (TraceRecord)
    └── sink.py         # Вывод трассировки (JsonlTraceSink, TraceSink)
```

### Принципы организации

- **Модульная структура**: Каждый подмодуль отвечает за одну область ответственности с четкими границами
- **Строгая типизация**: Все публичные API используют Pydantic модели с `extra="forbid"` для предотвращения неожиданных полей
- **Content-Addressable Storage**: Артефакты адресуются по SHA256 хешу содержимого, обеспечивая дедупликацию и верификацию
- **Декларативные контракты**: Четкое разделение между ссылками на артефакты (ArtifactRef) и моделями данных
- **Наблюдаемость**: Встроенная система трассировки для всех операций с поддержкой распределенного трекинга
- **Безопасность типов**: Литеральные типы для kind и media_type артефактов обеспечивают compile-time проверки

## Компоненты

### 1. Artifacts (Артефакты)

**Назначение**: Управление артефактами системы - неизменяемыми объектами с метаданными, хранящимися в Content-Addressable Storage (CAS). Обеспечивает надежное хранение и верификацию результатов вычислений.

**Основные компоненты**:
- `ArtifactID` - уникальный идентификатор артефакта на основе SHA256 хеша
- `ArtifactManifest` - полные метаданные артефакта (производитель, схема, окружение, входы)
- `ArtifactRef` - ссылка на артефакт с типизацией по kind и media_type
- `FileSystemCAS` - реализация хранилища артефактов в файловой системе
- `RegistryBundle` - пакет реестров компонентов системы
- `PutOptions` - опции сохранения артефактов с метаданными
- `VerificationReport` - отчет о верификации целостности артефактов

**Дополнительные структуры метаданных**:
- `ProducerInfo` - информация о производителе артефакта
- `SchemaInfo` - информация о схеме данных
- `EnvInfo` - информация об окружении выполнения
- `GitInfo` - информация о Git коммите
- `InputRef` - ссылки на входные артефакты
- `IntegrityInfo` - информация о целостности
- `WarningRecord` - записи предупреждений

**Функционал**:
- Хранение артефактов с SHA256 хешированием и дедупликацией
- Верификация целостности артефактов при загрузке
- Управление зависимостями и provenance между артефактами
- Поддержка различных типов артефактов (JSON, бинарные данные, изображения)
- Типизированные ссылки на артефакты с проверкой kind и media_type

### 1.1. Environment (Окружение)

**Назначение**: Захват и управление манифестами окружения для обеспечения воспроизводимости симуляций. EnvironmentManifest фиксирует все факторы, влияющие на результаты вычислений: оборудование, ПО, рантаймы и конфигурацию.

**Основные компоненты**:
- `EnvironmentManifest` - полный манифест окружения с аппаратным и программным обеспечением
- `CPUInfo` - информация о CPU (архитектура, инструкции AVX, ядра, потоки)
- `GPUInfo` - информация о GPU (NVIDIA/Apple Silicon, CUDA, память)
- `OSInfo` - информация об ОС (система, версия ядра, libc)
- `PythonInfo` - информация о Python рантайме и исполняемом файле
- `JAXInfo` - информация о JAX/XLA (версии, бэкенды, флаги)
- `GitInfo` - информация о Git коммите и состоянии репозитория
- `DependencyInfo` - хеш lock-файла зависимостей (uv.lock, poetry.lock)
- `ContainerInfo` - информация о контейнеризации (Docker, Podman)
- `SystemLibraryInfo` - хеши системных библиотек (CUDA, cuDNN)
- `EnvironmentDiff` - различия между двумя манифестами окружения
- `capture_environment()` - функция захвата текущего окружения

**Ключевые возможности**:
- **Fingerprinting**: Генерация компактного fingerprint для быстрого сравнения окружений
- **Compatibility scoring**: Оценка совместимости между окружениями (1.0 = идентичные, 0.0 = несовместимые)
- **Risk assessment**: Автоматическое определение рисков несовместимости (CPU архитектура, CUDA версии, XLA флаги)
- **Cross-platform detection**: Обнаружение потенциальных проблем с переносимостью (ARM vs x86, GPU determinism)
- **System library tracking**: Отслеживание версий критичных системных библиотек

**Функционал**:
- Захват полного состояния окружения для reproducible симуляций
- Сравнение окружений с оценкой рисков несовместимости
- Отслеживание изменений в зависимостях и системных библиотеках
- Поддержка различных платформ (Linux, macOS, Windows)
- Интеграция с CI/CD для валидации окружения

### 2. Canon (Канонический JSON)

**Назначение**: Обеспечивает детерминированную сериализацию данных в JSON формат для обеспечения воспроизводимости вычислений и создания стабильных хешей артефактов.

**Основные компоненты**:
- `CanonSpec` - спецификация канонизации с настраиваемыми правилами
- `to_canonical_bytes()` - преобразование объектов в канонические байты
- `from_canonical_bytes()` - десериализация из канонических байт
- `from_canonical_obj()` - десериализация из канонического объекта
- `CanonViolation` - исключение при нарушении правил канонизации

**Особенности канонизации**:
- **Запрет float**: использование только Decimal для точных вычислений
- **Детерминированная сериализация**: сортировка ключей, фиксированные разделители
- **Специальные типы**: каноническое представление datetime, date, Decimal, bytes
- **Поддержка моделей**: автоматическая конвертация Pydantic моделей и датаклассов
- **Безопасность**: запрет NaN/Inf значений, валидация типов

**Правила канонизации**:
- `forbid_floats`: запрет использования float (по умолчанию True)
- `forbid_nan_inf`: запрет NaN/Inf (по умолчанию True)
- `sort_keys`: сортировка ключей объектов (по умолчанию True)
- `separators`: разделители JSON (по умолчанию `,:`)
- `ensure_ascii`: кодировка ASCII (по умолчанию False)

### 3. Compiler (Компилятор)

**Назначение**: Управление отчетами компиляции и линковки политики.

**Основные компоненты**:
- `CompileReport` - отчет о компиляции политики
- `put_compile_report()` - сохранение отчета компиляции как артефакта
- `put_link_report()` - сохранение отчета линковки как артефакта

**Функционал**:
- Отслеживание результатов компиляции
- Ссылки на скомпилированные артефакты (программа-граф, план исполнения)
- Управление входами и выходами компиляции

### 4. Contracts (Контракты)

**Назначение**: Определяет контракты взаимодействия между различными модулями системы, обеспечивая типобезопасность и стандартизацию интерфейсов.

**Основные компоненты по модулям**:

#### Compiler Contracts (Компилятор)
- `CompileReportRef` - ссылка на отчет компиляции
- `LinkReportRef` - ссылка на отчет линковки

#### Fabric Contracts (Fabric - обработка данных)
- `DataViewRequestRef` - запрос на представление данных
- `QueryPlan` / `QueryPlanRef` - план запроса с шагами выполнения
- `EvidenceBundle` / `EvidenceBundleRef` - пакет доказательств с трансформациями и provenance tracking
- `FabricResult` / `FabricResultRef` - результат обработки с полными метаданными
- `UncertaintyBounds` / `UncertaintyBoundsRef` - границы неопределенности
- `WarningsBundle` / `WarningsRef` - пакет предупреждений

#### Foundry Contracts (Foundry - симуляция и исполнение политик)
- `PolicySurfaceIRRef` - ссылка на IR поверхности политики
- `ProgramGraph` / `ProgramGraphRef` - граф программы с узлами и операциями
- `LoweredIR` / `LoweredIRRef` - пониженное IR для исполнения
- `ExecPlan` / `ExecPlanRef` - план исполнения с environment tracking и determinism
- `AgentPolicyRef` - ссылка на обученную политику агента с determinism guarantees
- `StateSnapshot` / `StateSnapshotRef` - снимок состояния симуляции
- `StateDelta` / `StateDeltaRef` - дельта изменений состояния
- `TreasurySeed` / `TreasurySeedRef` - детерминированный seed для RNG
- `ExecConfig` / `ExecConfigRef` - конфигурация исполнения
- `Metrics` / `MetricsRef` - метрики выполнения и калибровки
- `TraceSliceRef` - срез трассировки исполнения
- **Patch-based State Management**: `PatchOp`, `UpdateOp`, `Patch`, `PatchSet` с confidence scoring
- **Advanced Runtime**: `ConstraintReportRef`, `CalibrationReportRef` для compile-time validation

#### Trinity Contracts (Trinity - базовые спецификации)
- `ProblemFrameRef` - ссылка на спецификацию проблемы
- `PolicySpecRef` - ссылка на спецификацию политики
- `ModelSpecRef` - ссылка на спецификацию модели
- `TrinityBundle` - пакет из трех Trinity артефактов с валидацией совместимости
- `TrinityManifest` - манифест с метаданными Trinity эксперимента

#### Scientist Contracts (Scientist - эксперименты и агенты)
- `FailureCardRef` - ссылка на FailureCard с информацией об ошибках
- `PolicyIRRef` - ссылка на PolicySurfaceIR с версией и статусом
- `CritiqueRef` - ссылка на артефакт оценки критика с вердиктом
- `TimelineRef` - ссылка на RunTimeline с метаданными о событиях
- `DecisionCardRef` - ссылка на DecisionCard с вердиктом и метаданными

#### Legal Contracts (Legal - compliance и валидация)
- `NormPack` - пакет нормативных правил и ограничений
- `NormRule` - определение отдельного правила
- `RuleType` - типы нормативных правил
- `RuleBackend` - интерфейс для реализации движков валидации

**Функционал**:
- Типизированные ссылки на артефакты с проверкой kind и media_type
- Структурированные модели данных для межмодульного обмена
- Поддержка provenance через ссылки на входные артефакты
- Интеграция с системой трассировки и метаданных
- Legal compliance контракты для валидации политик
- Timeline tracking для observability экспериментов
- Decision cards для deterministic summarization результатов

### 5. Registry (Реестр)

**Назначение**: Управление реестрами компонентов системы (механизмы, метрики, ограничения и т.д.).

**Основные компоненты**:
- `build_registry_bundle()` - сборка пакета реестров
- `load_registry_bundle()` - загрузка пакета реестров
- `RegistryBundleContent` - содержимое пакета реестров

**Функционал**:
- Автоматическая сборка стандартных реестров из IR-модуля
- Сохранение реестров как артефактов
- Загрузка и валидация реестров компонентов

### 6. Run (Выполнение)

**Назначение**: Управление контекстами и манифестами выполнения операций.

**Основные компоненты**:
- `RunContext` - контекст выполнения с трассировкой
- `RunManifest` - манифест выполнения (метаданные о запуске)
- `new_run_id()` - генерация уникальных ID запусков

**Функционал**:
- Инициализация контекстов выполнения
- Управление жизненным циклом запусков
- Интеграция с системой трассировки
- Хранение результатов выполнения

### 7. Trace (Трассировка)

**Назначение**: Система логирования и трассировки операций для отладки и мониторинга.

**Основные компоненты**:
- `TraceRecord` - запись трассировки с временными метками
- `TraceSink` - интерфейс для вывода записей трассировки
- `JsonlTraceSink` - реализация вывода в JSON Lines формат

**Функционал**:
- Структурированное логирование операций
- Поддержка распределенной трассировки (span_id, parent_span_id)
- Ссылки на артефакты в записях трассировки
- Метрики и предупреждения в записях

### 8. Observability (Наблюдаемость)

**Назначение**: Production-grade система телеметрии, предоставляющая унифицированные возможности наблюдения: распределенную трассировку с OpenTelemetry, Prometheus-совместимые метрики, структурированное логирование с корреляцией трассировки и инструменты распространения контекста.

**Основные компоненты**:

#### Configuration (Конфигурация)
- `OTelConfig` - централизованная конфигурация OpenTelemetry с поддержкой переменных окружения
- `ResourceConfig` - атрибуты ресурса для идентификации сервиса (имя, версия, окружение)
- `get_default_config()` - функция получения конфигурации по умолчанию

#### Tracer (Трассировщик)
- `PolicyOSTracer` - singleton-обертка для OpenTelemetry TracerProvider с ленивой инициализацией
- `get_tracer()` - глобальный доступ к трассировщику
- `get_current_trace_context()` - получение текущего контекста трассировки

#### Decorators (Декораторы)
- `@traced` - автоматическое создание спанов вокруг функций с поддержкой async/sync
- `@traced_method` - специализированный декоратор для методов классов
- Автоматический захват аргументов, результатов и исключений

#### Logs (Логирование)
- `TraceContextFilter` - фильтр логирования, добавляющий trace_id и span_id
- `StructuredFormatter` - JSON-форматтер для структурированного логирования
- `configure_otel_logging_handler()` - интеграция с существующей системой логирования
- `get_trace_context_dict()` - получение контекста трассировки для логов

#### Metrics (Метрики)
- `MetricsRegistry` - singleton-реестр метрик с Prometheus-совместимыми экспортерами
- `HistogramTimer` - контекстный менеджер для измерения времени выполнения
- `get_metrics()` - глобальный доступ к реестру метрик

#### Propagation (Распространение контекста)
- `inject_headers()` / `extract_headers()` - инъекция/экстракция контекста в HTTP заголовки
- `propagate_context()` - контекстный менеджер для распространения контекста
- `with_trace_context()` - обертка функций для захвата контекста
- `TracedExecutorWrapper` - обертка для ThreadPoolExecutor с распространением трассировки

**Ключевые возможности**:
- **Распределенная трассировка**: span-based моделирование с поддержкой OpenTelemetry
- **Корреляция логов и трассировки**: автоматическая инъекция trace_id в логи
- **Prometheus метрики**: готовые метрики для workflow, симуляций, LLM вызовов
- **Zero-configuration instrumentation**: простые декораторы для автоматической трассировки
- **Контекстная пропаганда**: распространение трассировки через потоки, async задачи и сервисы
- **Production-ready**: поддержка batching, sampling, graceful fallback
- **Semantic conventions**: специализированные атрибуты для PolicyOS (phase, agent, node)

**Экспортеры и интеграции**:
- **OTLP gRPC/HTTP**: для Jaeger, Tempo, DataDog и других OTLP коллекторов
- **Prometheus**: встроенный HTTP сервер для сбора метрик
- **Console**: для отладки и разработки
- **JSON structured logging**: совместимый с ELK stack, Loki, CloudWatch

**Функционал**:
- Автоматическое создание спанов для функций с атрибутами PolicyOS (phase, agent, node)
- Захват исключений и установка статусов ошибок в спанах
- Измерение производительности с гистограммами и счетчиками
- Корреляция между логами, метриками и трассировкой через trace_id/span_id
- Распространение контекста через thread boundaries и async operations
- Конфигурируемое поведение (включение/отключение, sampling, экспортеры)

## Связи с другими модулями

### Архитектурные принципы зависимостей

Core является фундаментом всей системы PolisyOS и следует принципу "граф зависимостей направлен только внутрь" (Закон A). Все модули верхнего уровня зависят от core, но core не зависит ни от одного модуля.

### Детальные зависимости от Core

#### IR (Промежуточное представление) - Зависит от core
- **canon.canon_json**: Каноническая сериализация для детерминированных хешей
- **artifacts.ids.ArtifactID**: Адресация артефактов по содержимому
- **artifacts.manifest**: Метаданные для всех IR артефактов
- **contracts**: Определение ссылок на артефакты для IR компонентов

**Обоснование**: IR определяет контракты данных, но использует core для инфраструктуры хранения и сериализации.

#### Fabric (Обработка и агрегация данных) - Зависит от core
- **artifacts.store.FileSystemCAS**: Хранение всех результатов обработки данных
- **contracts.fabric**: Полный набор контрактов Fabric (QueryPlan, EvidenceBundle, FabricResult, etc.)
- **artifacts.manifest.ArtifactRef**: Типизированные ссылки на артефакты
- **trace**: Трассировка всех операций обработки данных
- **canon**: Каноническая сериализация для evidence и фактов

**Обоснование**: Fabric работает с данными как с артефактами и использует контракты core для типобезопасного обмена.

#### Foundry (Симуляция и исполнение политик) - Зависит от core
- **contracts.foundry**: Полный набор контрактов Foundry (ProgramGraph, ExecPlan, StateDelta, StateSnapshot, AgentPolicy, Patch-based state management)
- **artifacts.store.FileSystemCAS**: Хранение всех артефактов симуляции
- **artifacts.environment**: EnvironmentManifest для reproducible симуляций с fingerprinting и compatibility scoring
- **run.RunContext**: Контексты выполнения симуляций с трассировкой
- **trace**: Детальная трассировка всех этапов исполнения
- **canon**: Каноническая сериализация для reproducible результатов

**Обоснование**: Foundry реализует сложную логику симуляции с patch-based state management, где все состояния хранятся как артефакты для обеспечения traceability. EnvironmentManifest обеспечивает reproducible результаты с compatibility scoring. Новые возможности включают AgentPolicy контракты, детерминизм исполнения, JAX runtime, compile-time conflict detection, cost modeling и NaN guard.

#### Scientist (Оркестрация экспериментов) - Зависит от core
- **run**: Контексты и манифесты выполнения экспериментов
- **artifacts**: Хранение всех результатов экспериментов и моделей
- **contracts.trinity**: Trinity контракты (ProblemFrame, PolicySpec, ModelSpec, TrinityBundle) для структурирования экспериментов
- **contracts.scientist**: Scientist контракты (FailureCardRef, PolicyIRRef, CritiqueRef, TimelineRef, DecisionCardRef) для управления жизненным циклом
- **trace**: Трассировка всех этапов workflow
- **registry**: Загрузка реестров компонентов

**Обоснование**: Scientist оркестрирует жизненный цикл экспериментов, используя Trinity контракты для структурирования и Scientist контракты для timeline tracking, decision cards и observability с полным provenance tracking.

#### Runtime (Исполнение в production) - Зависит от core
- **artifacts**: Доступ к развернутым артефактам политик
- **contracts**: Взаимодействие с откомпилированными политиками
- **run**: Контексты выполнения в production среде
- **observability**: Полная телеметрия production execution с distributed tracing, metrics и structured logging

**Обоснование**: Runtime отвечает за развертывание и исполнение политик в production с полным observability coverage через distributed tracing и metrics.

#### Scientist/Governance/Legal (Правовая валидация) - Зависит от core
- **contracts.legal**: Полный набор legal контрактов (NormPack, NormRule, RuleType, RuleBackend)
- **artifacts**: Хранение нормативных правил как артефактов
- **trace**: Трассировка всех операций legal валидации

**Обоснование**: Legal модуль использует контракты core для стандартизации интерфейсов валидации политик и обеспечения compliance через pluggable rule backends.

### Обратные зависимости на Core:
- **Артефакты**: универсальный механизм хранения для всех результатов
- **Трассировка**: интегрируется во все контексты выполнения
- **Контракты**: стандартизированные интерфейсы между модулями
- **Environment manifests**: reproducible симуляции с compatibility scoring
- **Каноническая сериализация**: воспроизводимость во всей системе
- **Observability**: унифицированная телеметрия с distributed tracing и metrics
- **Legal контракты**: compliance валидация через pluggable backends
- **Trinity контракты**: структурирование экспериментов

## Примеры использования

### Создание контекста выполнения с трассировкой:

```python
from pathlib import Path
from polisyos.core.run import RunContext
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ProducerInfo, ArtifactRef
from polisyos.core.trace import TraceRecord

# Инициализация хранилища артефактов
store = FileSystemCAS(Path("/tmp/artifacts"))

# Загрузка пакета реестров (предполагается, что он уже создан)
registry_bundle_ref = ArtifactRef(...)  # Загрузить из хранилища

# Создание контекста выполнения
ctx = RunContext.start(
    store=store,
    registry_bundle=registry_bundle_ref,
    producer=ProducerInfo(
        component="data_processor",
        version="2.1.0",
        git_commit="abc123def",
        build_time=datetime.now()
    )
)

# Эмиссия событий трассировки
ctx.trace.emit(TraceRecord(
    run_id=ctx.run_manifest.run_id,
    span_id="process_data",
    parent_span_id=None,
    phase="data_processing",
    event="batch_loaded",
    timestamp=datetime.now(),
    metrics={"batch_size": 1000, "memory_mb": 256},
    artifacts={"input_batch": input_ref}
))
```

### Работа с артефактами и контрактами:

```python
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.artifacts.manifest import SchemaInfo, ProducerInfo
from polisyos.core.contracts.fabric import FabricResult, FabricResultRef

# Сохранение результата обработки данных
result_data = FabricResult(
    request_ref=data_request_ref,
    plan_ref=query_plan_ref,
    data_ref=processed_data_ref,
    sources=[source1_ref, source2_ref],
    evidence_ref=evidence_bundle_ref,
    uncertainty_ref=uncertainty_bounds_ref
)

# Сохранение как артефакт с типизированной ссылкой
result_ref = store.put_json(
    result_data.model_dump(),
    PutOptions(
        kind="fabric.result_bundle",
        media_type="application/json",
        schema=SchemaInfo(
            name="fabric.result.schema",
            version="1.2.0"
        ),
        producer=ProducerInfo(
            component="fabric_processor",
            version="3.0.1"
        )
    )
)

# Получение типизированной ссылки
typed_ref = FabricResultRef.from_artifact_ref(result_ref)
```

### Каноническая сериализация для хеширования:

```python
from polisyos.core.canon import to_canonical_bytes, from_canonical_bytes
from polisyos.core.artifacts.ids import ArtifactID
from decimal import Decimal
from datetime import datetime

# Данные политики для сериализации
policy_data = {
    "version": "1.0.0",
    "parameters": {
        "threshold": Decimal("0.75"),
        "max_iterations": 1000,
        "created_at": datetime(2024, 1, 15, 10, 30, 0)
    },
    "constraints": ["budget_limit", "fairness_check"]
}

# Каноническая сериализация для стабильного хеширования
canonical_bytes = to_canonical_bytes(policy_data)
artifact_id = ArtifactID.from_bytes(canonical_bytes)

# Восстановление данных
restored_data = from_canonical_bytes(canonical_bytes)
assert restored_data["parameters"]["threshold"] == Decimal("0.75")
```

### Работа с реестрами компонентов:

```python
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle
from polisyos.core.artifacts.store import FileSystemCAS

# Сборка стандартного пакета реестров из IR модуля
store = FileSystemCAS(Path("/tmp/artifacts"))
registry_bundle = build_default_registry_bundle(store)

# Сохранение пакета реестров
bundle_ref = registry_bundle.save(store)

# Загрузка реестров в другом контексте
loaded_bundle = load_registry_bundle(store, bundle_ref)
mechanisms = loaded_bundle.mechanisms
metrics = loaded_bundle.metrics
constraints = loaded_bundle.constraints
```

### Работа с Environment Manifest:

```python
from polisyos.core.artifacts.environment import capture_environment

# Захват окружения для reproducible симуляций
env_manifest = capture_environment(
    project_root=Path("/path/to/project"),
    include_git=True,
    include_dependencies=True,
    include_system_libraries=True
)

# Fingerprinting для быстрого сравнения
fingerprint = env_manifest.fingerprint
compatibility = env_manifest.compatibility_score(other_env)
```

### Работа с observability (трассировка, метрики, логи):

```python
from polisyos.core.observability import get_tracer, get_metrics, traced

@traced(phase="EXECUTE", node="policy_simulation")
def run_policy_simulation(config: dict) -> dict:
    tracer = get_tracer()
    metrics = get_metrics()

    with metrics.time_simulation({"policy_type": config.get("type", "unknown")}):
        result = perform_simulation(config)
        metrics.record_workflow_run("success", "EXECUTE", "simulation_agent")
        return result
```

## Архитектурные принципы

- **Content-Addressable Storage**: SHA256 хеширование, дедупликация, верификация целостности
- **Типобезопасные контракты**: Pydantic модели, литеральные типы, валидация данных
- **Детерминированная сериализация**: Канонический JSON, Decimal вместо float
- **Distributed tracing**: Span-based трассировка с OpenTelemetry
- **Environment manifests**: Reproducible симуляции с compatibility scoring
- **Production observability**: Metrics, structured logging, context propagation

## Текущее состояние и развитие

### Стабильность API

Модуль `core` находится в стабильном состоянии с зафиксированными контрактами. Все изменения следуют принципам:

- **Версионирование**: Изменения в контрактах сопровождаются новыми версиями схем
- **Обратная совместимость**: Существующие артефакты остаются читаемыми
- **Миграции**: Автоматические миграции между версиями схем при необходимости

### Активное использование

Core активно используется всеми модулями PolisyOS в production среде:

- **Fabric**: Обрабатывает >100K артефактов в типичном ingestion pipeline с полным provenance tracking и observability через distributed tracing и metrics
- **Foundry**: Хранит состояния симуляций, результаты калибровки и все артефакты исполнения политик с compile-time conflict detection, cost modeling для resource-aware исполнения, NaN guard для numerical stability и полной телеметрией через observability module
- **Scientist**: Оркестрирует эксперименты с сотнями артефактов, обеспечивая reproducible research с comprehensive observability coverage (workflow metrics, LLM call tracking, validation issues)
- **Runtime**: Обеспечивает production-ready исполнение политик с полным аудитом операций и distributed tracing для всех execution paths
- **IR**: Определяет контракты данных с использованием core для инфраструктуры хранения и observability для tracing всех compilation operations

### Производительность и надежность

- **CAS операции**: <1ms на операцию чтения/записи с атомарными транзакциями
- **Каноническая сериализация**: Детерминированные хеши для reproducible builds и кеширования
- **Трассировка**: <0.1ms overhead на операцию с поддержкой распределенного трекинга
- **Верификация**: Криптографическая проверка целостности всех артефактов
- **Масштабируемость**: Поддержка миллионов артефактов с эффективной дедупликацией

## Заключение

Модуль `core` предоставляет фундаментальную инфраструктуру для PolisyOS:

- **Надежность**: CAS с криптографической верификацией
- **Воспроизводимость**: Каноническая сериализация + environment manifests
- **Наблюдаемость**: Distributed tracing, metrics, structured logging
- **Модульность**: Типизированные контракты (Fabric, Foundry, Trinity, Scientist, Legal)
- **Масштабируемость**: Эффективное хранение и кеширование артефактов

**Статус**: Production-ready, используется во всех модулях PolisyOS.
