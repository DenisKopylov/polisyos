# Core Module Documentation

## Обзор

Модуль `core` представляет собой фундаментальную часть системы PolisyOS, предоставляя основные протоколы и инфраструктуру для работы с артефактами, трассировкой, каноническим JSON, контрактами между модулями и контекстами выполнения. Модуль обеспечивает надежность, воспроизводимость и наблюдаемость всей системы.

## Архитектура

Модуль `core` состоит из следующих основных компонентов:

```
core/
├── artifacts/          # Управление артефактами и их хранением
│   ├── ids.py          # Уникальные идентификаторы артефактов (ArtifactID)
│   ├── manifest.py     # Метаданные артефактов (ArtifactManifest, ArtifactRef)
│   ├── registry.py     # Пакеты реестров компонентов (RegistryBundle)
│   └── store.py        # Хранилище артефактов (FileSystemCAS, PutOptions)
├── canon/              # Каноническая сериализация JSON
│   └── canon_json.py   # Детерминированная сериализация (CanonSpec, to_canonical_bytes)
├── compiler/           # Отчеты компиляции и линковки
│   └── report.py       # Управление отчетами компиляции
├── contracts/          # Контракты между модулями системы
│   ├── compiler.py     # Контракты компилятора (CompileReportRef, LinkReportRef)
│   ├── fabric.py       # Контракты Fabric (QueryPlan, EvidenceBundle, FabricResult)
│   └── foundry.py      # Контракты Foundry (ProgramGraph, ExecPlan, StateDelta)
├── registry/           # Сборка и загрузка реестров компонентов
│   ├── builder.py      # Сборка реестров (build_registry_bundle)
│   └── loader.py       # Загрузка реестров (load_registry_bundle)
├── run/                # Контексты и манифесты выполнения
│   ├── context.py      # Контекст выполнения (RunContext)
│   └── manifest.py     # Манифест выполнения (RunManifest)
└── trace/              # Трассировка и логирование операций
    ├── record.py       # Записи трассировки (TraceRecord)
    └── sink.py         # Вывод трассировки (JsonlTraceSink, TraceSink)
```

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
- `EvidenceBundle` / `EvidenceBundleRef` - пакет доказательств с трансформациями
- `FabricResult` / `FabricResultRef` - результат обработки с метаданными
- `UncertaintyBounds` / `UncertaintyBoundsRef` - границы неопределенности
- `WarningsBundle` / `WarningsRef` - пакет предупреждений

#### Foundry Contracts (Foundry - симуляция и исполнение)
- `PolicySurfaceIRRef` - IR поверхности политики
- `ProgramGraph` / `ProgramGraphRef` - граф программы с узлами и операциями
- `LoweredIR` / `LoweredIRRef` - пониженное IR для исполнения
- `ExecPlan` / `ExecPlanRef` - план исполнения
- `StateSnapshot` / `StateSnapshotRef` - снимок состояния
- `StateDelta` / `StateDeltaRef` - дельта изменений состояния
- `TreasurySeed` / `TreasurySeedRef` - seed казначейства
- `ExecConfig` / `ExecConfigRef` - конфигурация исполнения
- `Metrics` / `MetricsRef` - метрики выполнения
- `CalibrationReportRef` - отчет калибровки
- `TraceSliceRef` - срез трассировки

**Функционал**:
- Типизированные ссылки на артефакты с проверкой kind и media_type
- Структурированные модели данных для межмодульного обмена
- Обеспечение контрактов с валидацией через Pydantic
- Поддержка provenance через ссылки на входные артефакты
- Интеграция с системой трассировки и метаданных

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

### Зависимости от Core (что использует каждый модуль):

#### Fabric (Обработка и агрегация данных)
- `artifacts.store.FileSystemCAS` - хранение результатов обработки данных
- `artifacts.manifest.ArtifactRef` - ссылки на артефакты в результатах
- `contracts.fabric.*` - все контракты Fabric (QueryPlan, EvidenceBundle, FabricResult, etc.)
- `trace.*` - трассировка операций обработки данных

#### Foundry (Симуляция и исполнение политик)
- `artifacts.*` - все компоненты артефактов для хранения состояний и результатов
- `contracts.foundry.*` - все контракты Foundry (ProgramGraph, ExecPlan, StateDelta, etc.)
- `trace.*` - трассировка симуляций и исполнения
- `run.RunContext` - контексты выполнения симуляций

#### IR (Промежуточное представление)
- `canon.*` - каноническая сериализация для создания стабильных хешей
- `artifacts.*` - хранение IR артефактов и метаданных

#### Scientist (Оркестрация экспериментов)
- `run.*` - контексты и манифесты выполнения экспериментов
- `artifacts.*` - хранение результатов экспериментов
- `trace.*` - трассировка этапов экспериментов
- `registry.*` - загрузка реестров компонентов

#### Runtime (Исполнение в production)
- `artifacts.*` - доступ к развернутым артефактам
- `contracts.*` - взаимодействие с результатами компиляции

#### Common (Общие утилиты)
- `canon.*` - каноническая сериализация для конфигураций

### Обратные зависимости на Core:
- **Core как фундамент**: все модули системы зависят от компонентов core
- **Артефакты**: являются универсальным механизмом хранения для всех результатов
- **Трассировка**: интегрируется во все контексты выполнения и операции
- **Контракты**: определяют стандартизированные интерфейсы между всеми модулями
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

## Заключение

Модуль `core` предоставляет фундаментальную инфраструктуру для всей системы PolisyOS, обеспечивая:

- **Надежность**: через CAS с криптографической верификацией целостности
- **Воспроизводимость**: через детерминированную каноническую сериализацию
- **Наблюдаемость**: через распределенную систему трассировки с span-based моделированием
- **Модульность**: через строго типизированные контракты между компонентами
- **Масштабируемость**: через эффективное хранение и кеширование артефактов
- **Аудитоспособность**: через полный провенанс и метаданные операций

Все компоненты модуля спроектированы для работы в распределенной среде, обеспечивают высокую степень надежности, отслеживаемости и соответствия требованиям enterprise-grade систем.
