# Core Module Documentation

## Обзор

Модуль `core` представляет собой фундаментальную часть системы PolisyOS, предоставляя основные протоколы и инфраструктуру для работы с артефактами, трассировкой, каноническим JSON, контрактами между модулями и контекстами выполнения. Модуль обеспечивает надежность, воспроизводимость и наблюдаемость всей системы.

**Архитектурная роль**: Core является самым нижним слоем в иерархии зависимостей PolisyOS, предоставляя примитивы, используемые всеми остальными модулями системы. Все модули (Fabric, Foundry, IR, Scientist, Runtime) зависят от core, но core не зависит ни от одного модуля системы. Core реализует паттерн "Clean Architecture" с четким разделением ответственности и строгой типизацией.

## Архитектура

Модуль `core` состоит из следующих основных компонентов:

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
│   ├── foundry.py      # Контракты Foundry (13 типов ссылок + модели исполнения)
│   ├── scientist.py    # Контракты Scientist (FailureCardRef, PolicyIRRef, CritiqueRef)
│   ├── trinity.py      # Trinity контракты (ProblemFrame, PolicySpec, ModelSpec)
│   └── legal.py        # Legal compliance контракты (NormPack, NormRule, RuleType, RuleBackend)
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
- `ProvenanceCoreRefModel` - модель для отслеживания происхождения данных

#### Foundry Contracts (Foundry - симуляция и исполнение политик)
- `PolicySurfaceIRRef` - ссылка на IR поверхности политики
- `ProgramGraph` / `ProgramGraphRef` - граф программы с узлами и операциями (механизмы, операции)
- `LoweredIR` / `LoweredIRRef` - пониженное IR для исполнения
- `ExecPlan` / `ExecPlanRef` - план исполнения с конфигурацией, environment tracking, determinism tier и random seed
- `AgentPolicyRef` - ссылка на артефакт обученной политики агента с типом политики, determinism tier и метаданными обучения
- `StateSnapshot` / `StateSnapshotRef` - снимок состояния симуляции с schema tracking
- `StateDelta` / `StateDeltaRef` - дельта изменений состояния (patch-based updates)
- `TreasurySeed` / `TreasurySeedRef` - детерминированный seed для RNG
- `ExecConfig` / `ExecConfigRef` - конфигурация исполнения (JAX, ресурсы, параметры)
- `Metrics` / `MetricsRef` - метрики выполнения и калибровки
- `ConstraintReportRef` - отчет о проверке ограничений
- `CalibrationReportRef` - отчет калибровки параметров
- `TraceSliceRef` - срез трассировки исполнения в формате JSONL
- `PatchOp` / `UpdateOp` - операции для patch-based state management
- `Patch` / `PatchSet` - структурированные патчи с метаданными и confidence scoring
- `PatchMeta` - метаданные патчей с source tracking и confidence levels

#### Trinity Contracts (Trinity - базовые спецификации)
- `ProblemFrameRef` - ссылка на спецификацию проблемы (ProblemFrame)
- `PolicySpecRef` - ссылка на спецификацию политики (PolicySpec)
- `ModelSpecRef` - ссылка на спецификацию модели (ModelSpec)
- `TrinityBundle` - пакет из трех Trinity артефактов с валидацией совместимости
- `TrinityManifest` - манифест с метаданными Trinity эксперимента и полными полями

#### Scientist Contracts (Scientist - эксперименты и агенты)
- `ArtifactRef` - базовый класс для всех ссылок на артефакты с CAS хешированием
- `FailureCardRef` - ссылка на FailureCard с информацией об ошибках экспериментов (attempt_number, error_code, source_step, can_retry)
- `PolicyIRRef` - ссылка на PolicySurfaceIR с версией и статусом (version, status)
- `CritiqueRef` - ссылка на артефакт оценки критика с вердиктом (verdict, ir_ref)

#### Legal Contracts (Legal - compliance и валидация)
- `NormPack` - пакет нормативных правил и ограничений
- `NormRef` - ссылка на нормативное правило
- `NormRule` - определение отдельного правила
- `RuleType` - типы нормативных правил
- `RuleBackend` - интерфейс для реализации движков валидации

**Функционал**:
- Типизированные ссылки на артефакты с проверкой kind и media_type
- Структурированные модели данных для межмодульного обмена
- Обеспечение контрактов с валидацией через Pydantic
- Поддержка provenance через ссылки на входные артефакты
- Интеграция с системой трассировки и метаданных
- Legal compliance контракты для валидации политик и правил

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
- **contracts.foundry**: Полный набор контрактов Foundry (ProgramGraph, ExecPlan, StateDelta, StateSnapshot, PatchOp, UpdateOp, Patch, PatchSet, etc.)
- **artifacts.store.FileSystemCAS**: Хранение всех артефактов симуляции (состояния, метрики, конфигурации)
- **artifacts.environment**: EnvironmentManifest для reproducible симуляций с fingerprinting окружения и compatibility scoring
- **run.RunContext**: Контексты выполнения симуляций с интегрированной трассировкой
- **trace**: Детальная трассировка всех этапов исполнения, калибровки и симуляции
- **canon**: Каноническая сериализация для обеспечения reproducible результатов
- **artifacts.manifest**: Метаданные для всех артефактов симуляции

**Обоснование**: Foundry реализует сложную логику симуляции с advanced patch-based state management, где все состояния и результаты хранятся как артефакты для обеспечения traceability и reproducibility. EnvironmentManifest обеспечивает reproducible результаты путем фиксации всех факторов окружения с автоматическим compatibility scoring и risk assessment. Новые возможности включают поддержку обученных политик агентов (AgentPolicyRef), детерминизм исполнения с configurable tier (determinism_tier) и JAX-based runtime для эффективного выполнения симуляций.

#### Scientist (Оркестрация экспериментов) - Зависит от core
- **run**: Контексты и манифесты выполнения экспериментов
- **artifacts**: Хранение всех результатов экспериментов и моделей
- **contracts.trinity**: Trinity контракты (ProblemFrame, PolicySpec, ModelSpec) для структурирования экспериментов
- **contracts.scientist**: Scientist контракты (FailureCardRef, PolicyIRRef, CritiqueRef) для управления жизненным циклом политик и оценок
- **trace**: Трассировка всех этапов workflow (draft → compile → execute → analyze)
- **registry**: Загрузка реестров компонентов для каждого эксперимента
- **contracts**: Ссылки на все типы артефактов в decision packets

**Обоснование**: Scientist оркестрирует полный жизненный цикл от LLM до оптимизированных политик, используя Trinity контракты для структурирования экспериментов по трем базовым аспектам (проблема, политика, модель) и Scientist контракты для типобезопасного управления артефактами экспериментов, включая обработку ошибок и оценок политик.

#### Runtime (Исполнение в production) - Зависит от core
- **artifacts**: Доступ к развернутым артефактам политик
- **contracts**: Взаимодействие с откомпилированными политиками
- **run**: Контексты выполнения в production среде

**Обоснование**: Runtime отвечает за развертывание и исполнение политик в production.

#### Scientist/Governance/Legal (Правовая валидация) - Зависит от core
- **contracts.legal**: Полный набор legal контрактов (NormPack, NormRule, RuleType, RuleBackend)
- **artifacts**: Хранение нормативных правил как артефактов
- **trace**: Трассировка всех операций legal валидации

**Обоснование**: Legal модуль использует контракты core для стандартизации интерфейсов валидации политик и обеспечения compliance через pluggable rule backends.

### Обратные зависимости на Core:
- **Core как фундамент**: все модули системы зависят от компонентов core
- **Артефакты**: являются универсальным механизмом хранения для всех результатов
- **Трассировка**: интегрируется во все контексты выполнения и операции
- **Контракты**: определяют стандартизированные интерфейсы между всеми модулями
- **Legal контракты**: обеспечивают compliance валидацию через pluggable rule backends
- **Каноническая сериализация**: обеспечивает воспроизводимость во всей системе
- **Реестры**: используются для загрузки компонентов во всех модулях

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

### Захват и сравнение окружений для reproducible симуляций:

```python
from polisyos.core.artifacts.environment import capture_environment, compare_environments
from pathlib import Path

# Захват текущего окружения
env_manifest = capture_environment(
    project_root=Path("/path/to/project"),
    include_git=True,
    include_dependencies=True,
    include_system_libraries=True
)

# Сохранение как артефакт
env_ref = store.put_json(
    env_manifest.model_dump(),
    PutOptions(
        kind="foundry.environment_manifest",
        media_type="application/json",
        producer=ProducerInfo(component="environment_capture", version="1.0.0")
    )
)

# Сравнение с сохраненным окружением
saved_env_data = store.get_json(saved_env_ref.artifact_id)
saved_env = EnvironmentManifest(**saved_env_data)

compatibility = env_manifest.compatibility_score(saved_env)
print(f"Environment compatibility: {compatibility}")

if compatibility < 0.8:
    diffs = compare_environments(env_manifest, saved_env)
    print("Critical differences found:")
    for diff in diffs:
        if diff.risk_level.name == "CRITICAL":
            print(f"  {diff.field_name}: {diff.explanation}")
```

### Работа с patch-based state management в Foundry:

```python
from polisyos.core.contracts.foundry import PatchOp, UpdateOp, Patch, PatchSet, PatchMeta, StateDelta

# Создание patch-based state update
patch_ops = [
    PatchOp(
        slot_id="user_balance",
        op="add",
        value_ref=balance_update_ref,
        mask_scope="per_agent"
    ),
    PatchOp(
        slot_id="system_interest_rate",
        op="set",
        value_ref=rate_ref
    )
]

update_ops = [
    UpdateOp(
        slot_id="market_price",
        op="clamp",
        value_ref=new_price_ref,
        min_ref=min_price_ref,
        max_ref=max_price_ref
    )
]

# Создание патча с метаданными
patch = Patch(
    schema_version="1.0",
    meta=PatchMeta(
        source_node_id="price_update_mechanism",
        step=100,
        confidence=0.95,
        tags=["market_update", "price_adjustment"]
    ),
    ops=update_ops
)

# Создание patch set для batch updates
patch_set = PatchSet(
    schema_version="1.0",
    patches=[patch],
    notes=["Monthly market price adjustment"]
)

# State delta с patch-based updates
state_delta = StateDelta(
    base_ref=previous_state_ref,
    patch_ref=patch_set_ref,
    ops=patch_ops,
    notes=["Combined market and user updates"]
)
```

### Работа с Trinity контрактами:

```python
from polisyos.core.contracts.trinity import ProblemFrameRef, PolicySpecRef, ModelSpecRef, TrinityBundle, TrinityManifest

# Создание Trinity bundle для эксперимента
trinity_bundle = TrinityBundle(
    problem_frame_ref=ProblemFrameRef(
        artifact_id=problem_id,
        kind="ir.problem_frame",
        media_type="application/json"
    ),
    policy_spec_ref=PolicySpecRef(
        artifact_id=policy_id,
        kind="ir.policy_spec",
        media_type="application/json"
    ),
    model_spec_ref=ModelSpecRef(
        artifact_id=model_id,
        kind="ir.model_spec",
        media_type="application/json"
    ),
    compatible=True,
    compatibility_notes=["All specs validated", "Compatible versions"]
)

# Создание манифеста эксперимента
manifest = TrinityManifest(
    manifest_id="exp_credit_risk_001",
    bundle=trinity_bundle,
    experiment_name="Credit Risk Policy Optimization",
    created_by="alice@finance.com",
    created_at="2024-01-15T10:00:00Z",
    notes=["First experiment with neural risk model", "Focus on fraud detection"]
)

# Сохранение Trinity bundle
bundle_ref = store.put_json(
    trinity_bundle.model_dump(),
    PutOptions(
        kind="scientist.trinity_bundle",
        media_type="application/json",
        producer=ProducerInfo(component="experiment_setup", version="1.0.0")
    )
)
```

## Архитектурные принципы

Модуль `core` следует принципам:

### 1. Content-Addressable Storage (CAS)
- Все артефакты адресуются по содержимому (SHA256 хеш)
- Автоматическая дедупликация и верификация целостности
- Неизменяемость артефактов после создания

### 2. Типобезопасные контракты
- Строгая типизация через Pydantic модели
- Литеральные типы для kind и media_type артефактов
- Валидация данных на границах модулей

### 3. Детерминированная сериализация
- Канонический JSON для воспроизводимых хешей
- Запрет float чисел в пользу Decimal
- Сортировка ключей и фиксированные разделители

### 4. Распределенная трассировка
- Span-based трассировка с parent-child отношениями
- Структурированные события с метаданными
- Интеграция с контекстами выполнения

### 5. Провенанс и аудит
- Полный трекинг зависимостей между артефактами
- Метаданные о происхождении и окружении
- Аудитные записи для compliance

## Интеграция в общую архитектуру PolisyOS

### Положение в технологическом стеке

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface (NL)                      │
├─────────────────────────────────────────────────────────────┤
│                 Scientist (AI Policy Design)                │
│           ┌─────────────────────────────────────┐           │
│           │         IR (Contracts)             │           │
│           └─────────────────────────────────────┘           │
├─────────────────────────────────────────────────────────────┤
│    Core (Infrastructure & Protocols) ← ТЕКУЩИЙ МОДУЛЬ      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Artifacts • Contracts • CAS • Canonical JSON • Trace │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│            Runtime Layer (Fabric + Foundry)                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │   Fabric (Data)   ←   Foundry (Simulation)   ←   Core   │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Роль в pipeline обработки

Core обеспечивает инфраструктуру для всего pipeline PolisyOS:

1. **IR Layer**: Определяет контракты данных, использует core для сериализации
2. **Fabric Layer**: Обрабатывает данные как артефакты через CAS
3. **Foundry Layer**: Выполняет симуляции с трассировкой через RunContext
4. **Scientist Layer**: Оркестрирует эксперименты, используя все компоненты core
5. **Runtime Layer**: Развертывает политики через артефакты core

### Принципы интеграции

- **Zero dependencies**: Core не зависит ни от одного модуля
- **Universal contracts**: Все межмодульные взаимодействия через core contracts
- **Artifact-centric**: Все результаты - это артефакты с provenance
- **Trace everywhere**: Все операции трассируются для observability

## Текущее состояние и развитие

### Стабильность API

Модуль `core` находится в стабильном состоянии с зафиксированными контрактами. Все изменения следуют принципам:

- **Версионирование**: Изменения в контрактах сопровождаются новыми версиями схем
- **Обратная совместимость**: Существующие артефакты остаются читаемыми
- **Миграции**: Автоматические миграции между версиями схем при необходимости

### Активное использование

Core активно используется всеми модулями PolisyOS в production среде:

- **Fabric**: Обрабатывает >100K артефактов в типичном ingestion pipeline с полным provenance tracking
- **Foundry**: Хранит состояния симуляций, результаты калибровки и все артефакты исполнения политик
- **Scientist**: Оркестрирует эксперименты с сотнями артефактов, обеспечивая reproducible research
- **Runtime**: Обеспечивает production-ready исполнение политик с полным аудитом операций
- **IR**: Определяет контракты данных с использованием core для инфраструктуры хранения

### Производительность и надежность

- **CAS операции**: <1ms на операцию чтения/записи с атомарными транзакциями
- **Каноническая сериализация**: Детерминированные хеши для reproducible builds и кеширования
- **Трассировка**: <0.1ms overhead на операцию с поддержкой распределенного трекинга
- **Верификация**: Криптографическая проверка целостности всех артефактов
- **Масштабируемость**: Поддержка миллионов артефактов с эффективной дедупликацией

## Заключение

Модуль `core` предоставляет фундаментальную инфраструктуру для всей системы PolisyOS, обеспечивая:

- **Надежность**: через CAS с криптографической верификацией целостности
- **Воспроизводимость**: через детерминированную каноническую сериализацию
- **Наблюдаемость**: через распределенную систему трассировки с span-based моделированием
- **Модульность**: через строго типизированные контракты между компонентами
- **Масштабируемость**: через эффективное хранение и кеширование артефактов
- **Аудитоспособность**: через полный провенанс и метаданные операций
- **Legal compliance**: через стандартизированные контракты для валидации политик и pluggable rule backends

Все компоненты модуля спроектированы для работы в распределенной среде, обеспечивают высокую степень надежности, отслеживаемости и соответствия требованиям enterprise-grade систем.

**Статус**: Production-ready, активно используется во всех компонентах PolisyOS.
