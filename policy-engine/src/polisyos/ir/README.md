# Polisyos IR: Policy Intermediate Representation

**IR (Intermediate Representation)** - это промежуточное представление политик и симуляций в системе Policy Engine. Модуль определяет канонические контракты данных, обеспечивая единообразие коммуникации между всеми компонентами системы: от LLM-агентов до JAX-симуляций.

**Обновлено**: документация актуализирована для отражения текущей архитектуры IR v2.0, включая детальное описание всех компонентов, связей с другими модулями и обновленные примеры использования.

## Архитектурная роль

Согласно [архитектурным принципам](../../../../architecture.md) проекта, **IR** является фундаментальным слоем контрактов:

```
NL → LLM → IR (AST) → Compilation → Runtime (UDF + Foundry) → Artifacts
```

### Положение в графе зависимостей

- **Входящие зависимости**: НИКАКИХ (чистый контракт)
- **Исходящие зависимости**: Используется всеми модулями (`scientist`, `fabric`, `foundry`, `runtime`)
- **Принцип**: "IR → никого" (Закон A - граф зависимостей только внутрь)

### Архитектурная эволюция

Модуль IR прошел через несколько этапов развития:

1. **IR v1.0**: Простые контракты с базовой валидацией (`PolicyIR`)
2. **IR v2.0**: Разделение на semantic и advisory части (`PolicySurfaceIR`)
3. **Текущая версия**: Расширенная система с kernel-реестрами и линкером

Текущая архитектура разделяет политику на две части:
- **Semantic**: Исполняемая логика (интервенции, цели, ограничения)
- **Advisory**: Человекочитаемые описания и метаданные

### Ключевые обязанности

1. **Канонические схемы**: Pydantic-модели для всех артефактов системы
2. **Валидация данных**: Строгие ограничения и проверки корректности
3. **Версионирование**: Детерминированные миграции схем
4. **Многоязычность**: Поддержка локализации интерфейсов
5. **Безопасность**: Анти-runaway лимиты на размеры и глубину

## Технологический стек

- **Pydantic v2**: Строгая валидация и сериализация данных
- **Python typing**: Полная статическая типизация
- **JSON Schema**: Экспорт схем для внешних интеграций
- **difflib**: Генерация отчетов об изменениях при валидации

## Структура модуля

```
ir/
├── __init__.py              # Экспорт основных типов данных и функций
├── types.py                  # Перечисления, базовые типы и утилиты
├── surface.py                # PolicySurfaceIR (v2.0) - основной контракт системы
├── data_views.py             # Модели запросов данных (DataViewRequest, DataViewType)
├── validation.py             # Утилиты валидации и отчетов об ошибках
├── fact_log.py               # Контракты для семантической сети фактов
├── linker.py                 # Линкер политик с валидацией по реестрам
├── predicate.py              # Реестры предикатов для запросов данных
├── loaders.py                # Универсальная загрузка политик с автораспознаванием версий
├── calibration.py            # Контракты калибровки политик относительно данных
├── kernel/                   # Kernel: фундаментальные реестры и типы
│   ├── __init__.py          # Экспорт всех kernel компонентов
│   ├── base.py              # KernelModel, паттерны ID, утилиты валидации
│   ├── constraints.py       # Реестр ограничений (ConstraintRegistry)
│   ├── mechanisms.py        # Реестр типов механизмов (MechanismTypeRegistry)
│   ├── merge_rules.py       # Правила слияния слотов состояний (MergeRuleRegistry)
│   ├── metrics.py           # Реестр метрик оптимизации (MetricRegistry)
│   ├── numbers.py           # Типизированные числовые значения (DecimalValue, etc.)
│   ├── selector_fields.py   # Реестр полей для селекторов (SelectorFieldRegistry)
│   ├── slots.py             # Реестр слотов состояний (SlotRegistry)
│   ├── time_semantics.py    # Семантика времени и расписаний (TimeSemantics)
│   ├── trust.py             # Политики доверия к данным (TrustRegistry)
│   ├── units.py             # Система единиц измерения (UnitsRegistry)
│   └── values.py            # Типизированные значения (MoneyValue, RateValue, etc.)
└── migrations/
    └── __init__.py          # API миграций между версиями схем
```

## Основные компоненты

### 1. Surface контракты (`surface.py`) - v2.0

#### PolicySurfaceIR - основной контракт системы

Текущий основной контракт системы, разделяющий политику на исполняемую (semantic) и advisory части. PolicySurfaceIR является центральным контрактом, используемым всеми компонентами системы для обмена данными о политиках.

```python
from polisyos.ir.surface import PolicySurfaceIR, PolicySemantic, PolicyAdvisory

# Semantic часть - исполняемая логика
semantic = PolicySemantic(
    context_snapshot_ref="sha256:...",
    registry_bundle_ref="sha256:...",
    objectives=[
        ObjectiveSpec(
            objective_id="max_gdp",
            metric_id="gdp",
            direction=OptimizationDirection.MAXIMIZE
        )
    ],
    interventions=[
        InterventionSpec(
            intervention_id="tax_reform",
            kind="TaxMechanism",
            target=SelectorAll(clauses=[
                SelectorPredicate(field="income", operator=">", value=10000)
            ]),
            schedule=ScheduleSpec(start_step=0, end_step=120),  # 10 лет
            params={"rate": 0.15}
        )
    ]
)

# Advisory часть - человекочитаемые описания
advisory = PolicyAdvisory(
    entities=[
        AdvisoryEntity(
            entity_id="government",
            entity_type=EntityType.AGENT,
            name=TranslatableString(en="Government", ua="Уряд")
        )
    ],
    narrative="Fiscal policy reform to stimulate economic growth"
)

# Полная политика
policy = PolicySurfaceIR(
    schema_version="2.0",
    semantic=semantic,
    advisory=advisory
)
```

### 2. Унаследованные контракты (`contract.py`) - v1.0

#### PolicyIR - корневой документ (устаревший)

Унаследованная структура v1.0, сохранена для обратной совместимости:

```python
from polisyos.ir.contract import PolicyIR, PolicyEntity, Intervention

# Создание сущностей с иерархической структурой
entities = [
    PolicyEntity(
        id="government",
        entity_type=EntityType.AGENT,
        name=TranslatableString(en="Government", ua="Уряд", ru="Правительство"),
        state_variables={"budget": 1000000.0}
    ),
    PolicyEntity(
        id="tax_office",
        entity_type=EntityType.RESOURCE,
        name=TranslatableString(en="Tax Office", ua="Податкова", ru="Налоговая"),
        parent_id="government"  # Иерархия
    )
]

# Определение вмешательств
interventions = [
    Intervention(
        id="income_tax_2024",
        name=TranslatableString(en="Income Tax 2024", ua="Податок на доход 2024"),
        target_selector=TargetSelector(
            all_of=[
                SelectorPredicate(field="income", operator=">", value=10000)
            ]
        ),
        mechanism_type="IncomeTax",
        parameters={"rate": 0.15, "threshold": 10000}
    )
]

# Полный документ политики
policy_ir = PolicyIR(
    schema_version="1.0",
    project_name="Economic Policy Simulation 2024",
    entities=entities,
    interventions=interventions,
    objectives=[Objective(metric_name="gdp", direction="maximize")],
    simulation_parameters=SimulationParameters(
        scope_years=5,
        time_unit=TimeUnit.YEAR
    )
)
```

#### PolicyEntity - сущности системы

Иерархическая модель агентов, ресурсов и инфраструктуры:

```python
@dataclass
class PolicyEntity:
    id: str                    # Уникальный snake_case идентификатор
    entity_type: EntityType    # AGENT, RESOURCE, INFRASTRUCTURE, ENVIRONMENT
    name: TranslatableString   # Многоязычное название
    parent_id: Optional[str]   # Иерархия (adjacency list)
    state_variables: dict      # Начальное состояние (balance, capacity, etc.)
```

#### Intervention - вмешательства политики

Структурированное описание изменений в системе:

```python
@dataclass
class Intervention:
    id: str                          # Уникальный идентификатор
    name: TranslatableString        # Название вмешательства
    target_selector: TargetSelector  # AST-селектор целей
    mechanism_type: str             # Ссылка на механизм Foundry
    parameters: dict                 # Параметры механизма
    constraints: dict                # Ограничения применения
```

### 2. Селекторы целей (`contract.py`)

#### TargetSelector - AST для фильтров

Безопасная альтернатива текстовым селекторам с поддержкой композиции:

```python
# Простой селектор: доход > 10000 И сектор = IT
selector = TargetSelector(
    all_of=[
        SelectorPredicate(field="income", operator=">", value=10000),
        SelectorPredicate(field="sector", operator="==", value="IT")
    ]
)

# Комплексный селектор: (доход > 10000 ИЛИ возраст < 25) И НЕ unemployed
complex_selector = TargetSelector(
    any_of=[
        SelectorPredicate(field="income", operator=">", value=10000),
        SelectorPredicate(field="age", operator="<", value=25)
    ],
    not_=TargetSelector(
        all_of=[SelectorPredicate(field="employment_status", operator="==", value="unemployed")]
    )
)
```

#### SelectorPredicate - атомарные условия

```python
@dataclass
class SelectorPredicate:
    field: str              # Атрибут сущности (entity state variable)
    operator: SelectorOperator  # ==, !=, >, <, >=, <=, in, not_in, between, contains
    value: Union[str, int, float, bool, List]  # Значение для сравнения
```

### 3. Типы и перечисления (`types.py`)

#### Базовые типы сущностей

```python
class EntityType(str, Enum):
    AGENT = "agent"           # Активные агенты (люди, фирмы, правительство)
    RESOURCE = "resource"     # Пассивные ресурсы (бюджет, зерно)
    INFRASTRUCTURE = "infrastructure"  # Инфраструктура (дороги, больницы)
    ENVIRONMENT = "environment"       # Окружающая среда (климат, вирусы)
```

#### Оптимизационные цели

```python
class OptimizationDirection(str, Enum):
    MAXIMIZE = "maximize"           # Максимизировать метрику
    MINIMIZE = "minimize"           # Минимизировать метрику
    MAINTAIN_RANGE = "maintain_range"  # Поддерживать в диапазоне
```

#### Многоязычные строки

```python
class TranslatableString(BaseModel):
    en: str = Field(..., description="English text for LLM logic")
    ua: str = Field(..., description="Ukrainian text for UI")
    ru: Optional[str] = Field(None, description="Russian text (optional)")

# Использование
name = TranslatableString(
    en="Income Tax Policy",
    ua="Політика податку на доход",
    ru="Политика налога на доход"
)
```

### 4. Запросы данных (`data_views.py`)

#### DataViewRequest - унифицированные запросы

Структурированные запросы к данным симуляции:

```python
from polisyos.ir.data_views import DataViewRequest, DataViewType, AccessTier, DataFilter

# Запрос панельных данных агентов
panel_request = DataViewRequest(
    request_id="agents_income_2024",
    run_id="sim_001",
    view_type=DataViewType.PANEL,
    metrics=["income", "savings", "employment_status"],
    filters=[
        DataFilter(column="sector", op="==", value="IT"),
        DataFilter(column="age", op=">=", value=25)
    ],
    step_start=0,
    step_end=60,  # 5 лет по месяцам
    aggregation="mean",
    access_tier=AccessTier.INTERNAL
)

# Запрос сетевых взаимодействий
network_request = DataViewRequest(
    request_id="agent_network_q4",
    run_id="sim_001",
    view_type=DataViewType.NETWORK,
    metrics=["neighbor_id", "transaction_amount"],
    ego_node_id="agent_123",  # Центр сети
    hop_depth=2,              # Глубина поиска
    relation_types=["trade", "investment"],
    access_tier=AccessTier.SENSITIVE
)

# Запрос снимка состояния на конкретный момент
snapshot_request = DataViewRequest(
    request_id="economy_snapshot_2024",
    run_id="sim_001",
    view_type=DataViewType.SNAPSHOT,
    metrics=["gdp", "unemployment_rate", "inflation"],
    step_start=48,  # Фиксированный момент времени
    step_end=48,    # Для snapshot start == end
    access_tier=AccessTier.PUBLIC
)
```

### 5. Валидация и отчеты (`validation.py`)

#### ValidationReport - отчеты об ошибках

Структурированные отчеты о проблемах валидации:

```python
from polisyos.ir.validation import ValidationReport, build_validation_report

try:
    policy_ir = PolicyIR.model_validate(input_data)
except ValidationError as e:
    report = build_validation_report(e, before=old_data, after=input_data)
    print(f"Validation failed: {report.error_summary}")

    # Детальный отчет по проблемам
    for issue in report.issues:
        print(f"  {issue.loc}: {issue.message}")
```

#### Функции валидации

- `build_validation_report()` - полный отчет с diff и детализацией проблем
- `issues_from_validation_error()` - конвертация Pydantic ошибок в структурированный формат
- `diff_payloads()` - генерация унифицированного diff между версиями данных
- `summarize_issues()` - компактный суммарный отчет о проблемах валидации

### 6. Fact Log контракты (`fact_log.py`)

#### Семантическая сеть фактов

Модель для представления знаний в виде семантической сети RDF-подобных фактов:

```python
from polisyos.ir.fact_log import Fact, FactBatch, FactProvenance, FactTrust, FactLegal

# Факт о доходе агента
fact = Fact(
    fact_id="income_john_2024",
    subject_id="agent_john",
    predicate_id="has_income",
    object_value=50000.0,
    target_id=None,
    valid_time="2024-01-01",
    provenance=FactProvenance(
        source_id="tax_authority",
        license="public_domain",
        raw_hash="sha256:...",
        ingestion_run_id="ingest_001"
    ),
    trust=FactTrust(confidence=0.95, method="official_source"),
    legal=FactLegal(pii_class="aggregated", access_tier="public")
)

# Пакет фактов для загрузки
batch = FactBatch(facts=[fact])
```

#### Детерминированные идентификаторы

```python
from polisyos.ir.fact_log import build_fact_id

# Генерация детерминированного ID на основе содержимого
payload = {"subject": "agent_john", "predicate": "has_income", "value": 50000}
fact_id = build_fact_id(payload)  # sha256:...
```

### 7. Линкер политик (`linker.py`)

#### Валидация и линковка политик

Система проверки корректности политик относительно реестров механизмов, слотов, метрик и ограничений. Линкер обеспечивает, что все ссылки в политике (механизмы, слоты, метрики) существуют в соответствующих реестрах и имеют корректные параметры:

```python
from polisyos.ir.linker import link_policy
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY, DEFAULT_METRIC_REGISTRY
)

# Линковка политики с реестрами
report = link_policy(
    policy=surface_policy,
    mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
    slot_registry=DEFAULT_SLOT_REGISTRY,
    merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    metric_registry=DEFAULT_METRIC_REGISTRY
)

if not report.ok:
    for issue in report.issues:
        print(f"{issue.severity}: {issue.message}")
```

#### Типы проблем линковки

- `unknown_mechanism`: Механизм интервенции не найден в реестре
- `missing_param`: Отсутствует обязательный параметр механизма
- `param_type`: Тип параметра не соответствует спецификации
- `param_range`: Значение параметра вне допустимого диапазона
- `unknown_slot`: Слот состояния не найден в реестре
- `slot_type_mismatch`: Несоответствие типов слота
- `merge_conflict`: Конфликт правил слияния состояний
- `constraint_violation`: Нарушение ограничений политики

### 8. Реестры предикатов (`predicate.py`)

#### Предикаты для запросов данных

Определение предикатов для доступа к данным симуляции:

```python
from polisyos.ir.predicate import PredicateRegistry, ScalarPredicateSpec, EdgePredicateSpec

registry = PredicateRegistry(
    scalars={
        "income": ScalarPredicateSpec(
            predicate_id="income",
            slot_id="agent.income",
            value_type="number",
            unit=UnitRef(unit_id="uah"),
            default_agg="mean"
        )
    },
    edges={
        "trades_with": EdgePredicateSpec(
            predicate_id="trades_with",
            src_entity_type="agent",
            dst_entity_type="agent",
            cardinality="many_to_many"
        )
    }
)
```

### 9. Загрузчики политик (`loaders.py`)

#### Универсальная загрузка политик

Система загрузки поддерживает автоматическое распознавание версий политик и конвертацию между форматами. Основная функция `load_policy()` принимает любые поддерживаемые форматы политик и возвращает унифицированный `PolicySurfaceIR`:

```python
from polisyos.ir.loaders import load_policy

# Автоматическая загрузка с распознаванием версии
policy = load_policy(input_data)  # Возвращает PolicySurfaceIR

# Поддерживает как v1.0 (PolicyRequestIR), так и v2.0 (PolicySurfaceIR)
# Автоматически конвертирует v1.0 в v2.0 при необходимости
```

#### Конвертация версий

```python
from polisyos.ir.loaders import _coerce_v1_to_surface

# Ручная конвертация из v1.0 в v2.0
surface_policy = _coerce_v1_to_surface(v1_data)
```

### 10. Калибровка политик (`calibration.py`)

#### Настройки калибровки

Контракты для калибровки политик относительно исторических данных:

```python
from polisyos.ir.calibration import (
    TargetAlignConfig, TargetLossConfig, CalibrationTarget,
    CalibrationConfig, CalibrationReport
)

# Настройки выравнивания временных рядов
align_config = TargetAlignConfig(
    frequency="monthly",
    method="linear",
    fill_value=None
)

# Параметры расчета ошибки
loss_config = TargetLossConfig(
    kind="mse",
    relative=True,
    scale="mean_abs",
    weight=1.0
)

# Цель калибровки
target = CalibrationTarget(
    target_id="gdp_calibration",
    series_ref="historical_gdp",
    align=align_config,
    loss=loss_config,
    tolerance=0.05
)

# Конфигурация калибровки политики
calibration = CalibrationConfig(
    policy_ref="policy_sha256_hash",
    targets=[target],
    max_iterations=100,
    tolerance=0.01
)
```

### 11. Система версий (`migrations/`)

#### Детерминированные миграции

Модуль IR использует общую систему миграций из `common.migrations` для управления версиями схем политик:

```python
from polisyos.ir.migrations import migrate_policy_ir, IR_CURRENT_VERSION

# Миграция данных между версиями в рамках 2.x
migrated_data = migrate_policy_ir(
    data=input_data,
    target_version="2.1",  # или IR_CURRENT_VERSION
    allow_major=False     # Защита от major изменений
)

# Проверка версии
from polisyos.ir.migrations import parse_version, is_major_bump
major, minor = parse_version("2.1")
is_major = is_major_bump("2.0", "2.1")  # False для minor изменений
```

#### Поддерживаемые версии

- **v2.x**: PolicySurfaceIR (текущая версия, обратная совместимость в рамках 2.x)
- **v1.x**: Устаревший PolicyIR (конвертация через `load_policy()`)
- **v0.x**: Устаревшие форматы (требуют ручной миграции)

## Kernel: базовые реестры и типы

Kernel предоставляет фундаментальные реестры и типы для всей системы IR. Это слой типизированных определений, которые используются всеми остальными компонентами для валидации и линковки политик:

### 1. Реестры механизмов (`mechanisms.py`)

Определение доступных типов механизмов интервенций:

```python
from polisyos.ir.kernel import MechanismTypeRegistry, MechanismTypeSpec, ParamSpec, ParamType

registry = MechanismTypeRegistry(mechanisms={
    "TaxMechanism": MechanismTypeSpec(
        mechanism_id="TaxMechanism",
        params={
            "rate": ParamSpec(
                param_id="rate",
                value_type=ParamType.RATE,
                unit_id="percent",
                required=True,
                min_value=0.0,
                max_value=1.0
            )
        },
        reads_slots=["income"],
        writes_slots=["tax_paid"]
    )
})
```

### 2. Реестр слотов (`slots.py`)

Определение слотов состояния агентов и сущностей:

```python
from polisyos.ir.kernel import SlotRegistry, SlotSpec, SlotKind

registry = SlotRegistry(slots={
    "agent.income": SlotSpec(
        slot_id="agent.income",
        kind=SlotKind.AGGREGATE,
        scope=SlotScope.AGENT,
        merge_rule=MergeRuleRef(rule_id="sum")
    )
})
```

### 3. Поля селекторов (`selector_fields.py`)

#### Реестр полей для селекторов

Определение доступных полей для фильтрации сущностей в селекторах:

```python
from polisyos.ir.kernel import SelectorFieldRegistry, SelectorFieldSpec, FieldValueType

registry = SelectorFieldRegistry(fields={
    "income": SelectorFieldSpec(
        field_id="income",
        slot_id="agent.income",
        value_type=FieldValueType.NUMBER,
        description="Доход агента"
    ),
    "sector": SelectorFieldSpec(
        field_id="sector",
        slot_id="agent.sector",
        value_type=FieldValueType.STRING,
        allowed_values=["IT", "finance", "manufacturing"],
        description="Сектор экономики"
    )
})
```

### 4. Политики доверия (`trust.py`)

#### Реестр политик доверия

Определение уровней доверия к источникам данных:

```python
from polisyos.ir.kernel import TrustRegistry, TrustPolicySpec, TrustLevel

registry = TrustRegistry(policies={
    "official_stats": TrustPolicySpec(
        policy_id="official_stats",
        level=TrustLevel.HIGH,
        sources=["government_api", "central_bank"],
        validation_rules=["signature_required", "freshness_check"],
        description="Официальная статистика от государственных органов"
    ),
    "survey_data": TrustPolicySpec(
        policy_id="survey_data",
        level=TrustLevel.MEDIUM,
        sources=["research_firms"],
        validation_rules=["sample_size_check"],
        description="Данные опросов и исследований"
    )
})
```

### 5. Реестр единиц (`units.py`)

Типизированная система единиц измерения:

```python
from polisyos.ir.kernel import UnitsRegistry, MoneyUnit, RateUnit

registry = UnitsRegistry(units={
    "uah": MoneyUnit(
        unit_id="uah",
        currency="UAH",
        nominal_year=2024
    ),
    "percent": RateUnit(
        unit_id="percent",
        base="percent"
    )
})
```

### 6. Типизированные значения (`values.py`)

Строго типизированные значения с единицами:

```python
from polisyos.ir.kernel import MoneyValue, RateValue, CountValue

salary = MoneyValue(amount=50000.0, currency="UAH", nominal_year=2024)
tax_rate = RateValue.ratio(0.15)  # 15%
employees = CountValue(value=100)
```

### 7. Правила слияния (`merge_rules.py`)

Логика разрешения конфликтов при пересекающихся интервенциях:

```python
from polisyos.ir.kernel import MergeRuleRegistry, MergeRuleSpec, MergeRuleKind

registry = MergeRuleRegistry(rules={
    "priority": MergeRuleSpec(
        rule_id="priority",
        kind=MergeRuleKind.PRIORITY,
        description="Resolve by priority field"
    ),
    "error": MergeRuleSpec(
        rule_id="error",
        kind=MergeRuleKind.ERROR,
        description="Raise error on conflict"
    )
})
```

## Ограничения безопасности

IR включает строгие лимиты для предотвращения runaway-симуляций:

```python
# Анти-runaway константы (surface.py)
MAX_SELECTOR_DEPTH = 6      # Максимальная глубина селекторов
MAX_SELECTOR_NODES = 200    # Максимум узлов в селекторе
MAX_SELECTOR_CLAUSES = 50   # Максимум выражений в селекторе
MAX_INTERVENTIONS = 200     # Максимум интервенций
MAX_OBJECTIVES = 50         # Максимум целей
MAX_CONSTRAINTS = 100       # Максимум ограничений

# Анти-runaway константы (contract.py - устаревшие)
MAX_ENTITIES = 500          # Максимум сущностей
MAX_DEPTH = 4               # Максимальная глубина иерархии
MAX_ID_LEN = 64             # Длина идентификаторов
```

## Использование в коде

### Базовый импорт

```python
# Основные типы (рекомендуемый импорт)
from polisyos.ir import (
    PolicySurfaceIR, load_policy, CalibrationConfig, CalibrationTarget,
    DataViewRequest, DataViewType, AccessTier
)

# Альтернативный импорт для доступа ко всем компонентам
from polisyos.ir.surface import (
    PolicySurfaceIR, PolicySemantic, PolicyAdvisory,
    InterventionSpec, ObjectiveSpec, ConstraintSpec,
    SelectorPredicate, SelectorAll, SelectorAny, SelectorNot,
    ScheduleSpec, schedule_range
)

from polisyos.ir.kernel import (
    MechanismTypeRegistry, SlotRegistry, UnitsRegistry,
    SelectorFieldRegistry, TrustRegistry,
    MoneyValue, RateValue, CountValue,
    MergeRuleRegistry, MetricRegistry, ConstraintRegistry,
    DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY
)

from polisyos.ir.linker import link_policy, LinkReport
from polisyos.ir.fact_log import Fact, FactBatch, FactProvenance
from polisyos.ir.validation import ValidationReport, build_validation_report
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget
```

### Создание политики v2.0

```python
from polisyos.ir.surface import (
    PolicySurfaceIR, PolicySemantic, PolicyAdvisory,
    InterventionSpec, ObjectiveSpec, AdvisoryEntity,
    SelectorPredicate, ScheduleSpec
)
from polisyos.ir.types import EntityType, TranslatableString, OptimizationDirection

# Семантическая часть - исполняемая логика
semantic = PolicySemantic(
    context_snapshot_ref="sha256:...",  # Ссылка на snapshot контекста
    objectives=[
        ObjectiveSpec(
            objective_id="max_economic_growth",
            metric_id="gdp_growth",
            direction=OptimizationDirection.MAXIMIZE,
            weight=1.0
        )
    ],
    interventions=[
        InterventionSpec(
            intervention_id="basic_income_policy",
            kind="TransferMechanism",  # Ссылка на механизм в Foundry
            target=SelectorPredicate(
                field="income",
                operator="<",
                value=500
            ),
            schedule=ScheduleSpec(
                start_step=0,
                end_step=120  # 10 лет месячной симуляции
            ),
            params={
                "amount": 200.0,
                "frequency": "monthly"
            }
        )
    ]
)

# Advisory часть - человекочитаемые метаданные
advisory = PolicyAdvisory(
    entities=[
        AdvisoryEntity(
            entity_id="government",
            entity_type=EntityType.AGENT,
            name=TranslatableString(en="Government", ua="Уряд"),
            attributes={"budget_authority": True}
        ),
        AdvisoryEntity(
            entity_id="citizens",
            entity_type=EntityType.AGENT,
            name=TranslatableString(en="Citizens", ua="Громадяни")
        )
    ],
    narrative="Universal basic income policy to reduce poverty and stimulate consumption",
    labels=["social_policy", "economic_stimulus"]
)

# Полная политика
policy = PolicySurfaceIR(
    schema_version="2.0",
    semantic=semantic,
    advisory=advisory
)
```

### Валидация данных

```python
from pydantic import ValidationError
from polisyos.ir.validation import build_validation_report

try:
    validated_policy = PolicyIR.model_validate_json(json_string)
    print("✅ Policy is valid")
except ValidationError as e:
    report = build_validation_report(e)
    print(f"❌ Validation failed: {report.error_summary}")
    for issue in report.issues[:3]:  # Показать первые 3 проблемы
        print(f"   {'.'.join(issue.loc)}: {issue.message}")

### Калибровка политики

```python
from polisyos.ir.calibration import (
    CalibrationConfig, CalibrationTarget,
    TargetAlignConfig, TargetLossConfig
)

# Настройка цели калибровки
calibration_target = CalibrationTarget(
    target_id="gdp_target",
    series_ref="historical_gdp_quarterly",
    align=TargetAlignConfig(
        frequency="quarterly",
        method="linear"
    ),
    loss=TargetLossConfig(
        kind="mse",
        relative=True,
        scale="mean_abs",
        weight=1.0
    ),
    tolerance=0.05
)

# Конфигурация калибровки
calibration_config = CalibrationConfig(
    policy_ref="sha256:abc123...",
    targets=[calibration_target],
    max_iterations=50,
    tolerance=0.01,
    learning_rate=0.01
)

# Использование в Foundry для калибровки
from polisyos.foundry.calibration import calibrate_policy
result = calibrate_policy(calibration_config)
```

### Загрузка политик с автоматическим распознаванием версии

```python
from polisyos.ir.loaders import load_policy

# Загрузка политики с автоматическим распознаванием версии
policy_data = {
    "schema_version": "2.0",
    "semantic": {
        "context_snapshot_ref": "sha256:123...",
        "objectives": [...],
        "interventions": [...]
    },
    "advisory": {
        "entities": [...],
        "narrative": "Economic policy"
    }
}

# Автоматическая загрузка и валидация
policy = load_policy(policy_data)
print(f"✅ Loaded policy: {policy.schema_version}")

# Поддержка обратной совместимости с v1.0
v1_policy_data = {
    "schema_version": "1.0",
    "project_name": "Legacy Policy",
    "entities": [...],
    "interventions": [...]
}

legacy_policy = load_policy(v1_policy_data)  # Автоматически конвертируется в v2.0
```
```

## JSON Schema экспорт

IR поддерживает автоматический экспорт JSON Schema для интеграций с внешними системами:

```python
from polisyos.ir.surface import PolicySurfaceIR
import json

# Генерация схемы для PolicySurfaceIR
schema = PolicySurfaceIR.model_json_schema()

# Сохранение в файл
with open('policy_ir_schema.json', 'w') as f:
    json.dump(schema, f, indent=2, ensure_ascii=False)

# Схема включает:
# - Полную валидацию всех полей
# - Описания и примеры
# - Перечисления и ограничения
# - Многоязычные описания
```

#### Инструменты диагностики

```bash
# Генерация полной схемы IR (через tools/diagnostics/)
python tools/diagnostics/generate_ir_schema.py

# Валидация политик по схеме
python tools/diagnostics/validate_policy.py policy.json
```

## Тестирование

Модуль включает исчерпывающее тестирование, разделенное на контрактные, интеграционные и unit-тесты:

```bash
# Контрактные тесты IR
pytest tests/contract/test_ir_*.py

# Основные тесты контрактов
pytest tests/contract/test_ir_surface.py      # PolicySurfaceIR и компоненты
pytest tests/contract/test_ir_linker.py       # Линкер и валидация
pytest tests/contract/test_ir_loaders.py      # Загрузчики политик
pytest tests/contract/test_ir_calibration.py  # Калибровка политик
pytest tests/contract/test_ir_kernel.py       # Kernel реестры и типы

# Тесты валидации и ворота
pytest tests/contract/test_fabric_gates.py    # Валидационные ворота

# Интеграционные тесты
pytest tests/integration/test_foundry_ir.py   # IR + Foundry интеграция
pytest tests/integration/test_scientist_ir.py # IR + Scientist интеграция

# Unit-тесты отдельных компонентов
pytest tests/unit/test_ir_validation.py       # Система валидации
pytest tests/unit/test_ir_fact_log.py         # Fact Log контракты
```

## Архитектурные принципы

IR строго следует архитектурным законам проекта:

1. **Закон A**: Граф зависимостей только внутрь - IR не зависит ни от кого
2. **Закон B**: Это компилятор - чистое frontend/IR/backend разделение
3. **Закон C**: Контракты = единственный источник истины
4. **Закон D**: Воспроизводимость через versioning и миграции

## Связанные компоненты

### Зависимости и взаимодействие

- **Scientist** (11 файлов): Генерирует и обрабатывает политики в формате `PolicySurfaceIR`. Использует типы из `types.py`, `surface.py`, валидацию из `validation.py`, загрузчики из `loaders.py`
- **Fabric** (14 файлов): Использует `DataViewRequest` из `data_views.py` для структурированных запросов данных, предикаты из `predicate.py` для семантических фильтров, контракты фактов из `fact_log.py` для семантической сети
- **Foundry** (13 файлов): Компилирует `InterventionSpec` из `surface.py` в исполняемые механизмы JAX. Использует реестры из `kernel/` для линковки, калибровку из `calibration.py` для оптимизации параметров
- **Core** (3 файла): Использует `Fact` и `FactBatch` из `fact_log.py` для построения семантической сети знаний
- **Runtime**: Хранит артефакты `PolicySurfaceIR` для аудита и воспроизводимости симуляций

### Архитектурные контракты

```
Scientist → PolicySurfaceIR → [Linker] → Foundry → Simulation
       ↓                        ↓             ↓
   types.py                  kernel/     calibration.py
       ↓                        ↓             ↓
   validation.py           surface.py     executor.py

                     ↓
                  Fabric → DataViewRequest → Runtime
                     ↓
                Fact Log → Semantic Network
```

---

**См. также**:
- [Общая архитектура](../../../../architecture.md)
- [Примеры использования](../../../examples/ir_base_demo.py)
- [Kernel реестры](../foundry/README.md) - механизмы и слоты
- [Fabric](../fabric/README.md) - система данных
- [Scientist](../scientist/README.md) - генерация политик
