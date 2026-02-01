# Core Module (Фундаментальная инфраструктура)

## Обзор

Модуль `core` - фундамент PolisyOS, предоставляющий базовую инфраструктуру: управление артефактами, каноническую сериализацию, контракты между модулями, трассировку и observability. Core является самым нижним слоем зависимостей, от которого зависят все остальные модули системы.

## Архитектура

```
core/
├── artifacts/     # Content-Addressable Storage (CAS) для артефактов
├── canon/         # Детерминированная JSON сериализация
├── compiler/      # Отчеты компиляции и линковки
├── contracts/     # Типизированные контракты между модулями
├── observability/ # Production-grade телеметрия (OTel, Prometheus)
├── registry/      # Управление реестрами компонентов
├── run/           # Контексты выполнения с трассировкой
└── trace/         # Система логирования и трассировки
```

**Ключевые принципы**: Неизменяемость артефактов, строгая типизация, reproducible симуляции, distributed tracing, compile-time проверки.

## Компоненты

### Artifacts (CAS хранилище)
Content-Addressable Storage с SHA256 хешированием. Ключевые компоненты: `ArtifactID`, `ArtifactManifest`, `FileSystemCAS`, `EnvironmentManifest` для reproducible симуляций с fingerprinting и compatibility scoring.

### Canon (Канонизация JSON)
Детерминированная сериализация для стабильных хешей. Запрет float, сортировка ключей, поддержка Decimal/datetime. Функции: `to_canonical_bytes()`, `from_canonical_bytes()`.

### Contracts (Типизированные контракты)
Межмодульные интерфейсы: Fabric (6 типов), Foundry (15+ типов с patch-based state, conflict detection, cost modeling), Scientist, Trinity, Legal. Литеральные типы для compile-time проверок.

### Observability (Телеметрия)
OpenTelemetry трассировка, Prometheus метрики, структурированное логирование с trace correlation. Декораторы `@traced`, `@traced_method`, propagation через thread/async границы.

### Registry (Реестры компонентов)
Управление реестрами механизмов, метрик, ограничений. `build_default_registry_bundle()`, `load_registry_bundle_content()`.

### Run (Контексты выполнения)
`RunContext` с автоматической трассировкой и управлением жизненным циклом. `RunManifest` с метаданными запусков.

### Trace (Логирование)
Span-based трассировка с `TraceRecord`, `JsonlTraceSink`. Поддержка распределенного трекинга, provenance через артефактные ссылки.

### Compiler (Отчеты компиляции)
`CompileReport`, `put_compile_report()` для хранения результатов компиляции и линковки как артефактов.

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
