# Polisyos IR: Policy Intermediate Representation

**IR (Intermediate Representation)** - это промежуточное представление политик и симуляций в системе Policy Engine. Модуль определяет канонические контракты данных, обеспечивая единообразие коммуникации между всеми компонентами системы: от LLM-агентов до JAX-симуляций.

**Обновлено**: документация актуализирована для отражения текущего состояния на 2026-02-01, включая полную реализацию Trinity архитектуры (ProblemFrame, PolicySpec, ModelSpec), расширенную систему Kernel реестров с новыми компонентами (constraints, metrics, selector_fields, trust, numbers, values), интеграцию с Fact Log, новые контракты для нормативных документов (NormPack), контракты коннекторов данных (connectors.py) для интеграции с внешними источниками, асинхронные утилиты (async_tools.py), и систему миграции Trinity.

## Архитектурная роль

Согласно [архитектурным принципам](../../../../architecture.md) проекта, **IR** является фундаментальным слоем контрактов в компиляторной трубе:

```
NL/Request → Scientist (LLM + Workflow) → IR (contracts) → Compilation → Runtime (Fabric UDF + Foundry) → Artifacts
```

### Архитектура Trinity

Система IR реализует **Trinity архитектуру** - разделение на три независимых артефакта, каждый из которых отвечает за отдельный аспект моделирования политики:

- **ProblemFrame** ("Why"): Определение проблемы, целей, KPI и ограничений (неизменен в рамках эксперимента)
- **PolicySpec** ("What"): Спецификация политики, интервенций и параметров (итерируется при оптимизации)
- **ModelSpec** ("How"): Конфигурация модели мира, агентов, данных и предположений (для sensitivity analysis)

### Положение в графе зависимостей

- **Входящие зависимости**: НИКАКИХ (чистый контракт)
- **Исходящие зависимости**: Используется всеми модулями (`scientist`, `fabric`, `foundry`, `runtime`, `core`)
- **Принцип**: "IR → никого" (Закон A - направленный граф зависимостей только внутрь)

### Архитектурная эволюция

Модуль IR прошел через несколько этапов развития:

1. **IR v1.0**: Простые контракты с базовой валидацией (`PolicyIR`)
2. **IR v2.0**: Разделение на semantic и advisory части (`PolicySurfaceIR`)
3. **IR v2.1**: Расширенная система с kernel-реестрами, линкером и Fact Log
4. **Текущая версия (Trinity + Connectors)**: Разделение на три независимых артефакта (ProblemFrame, PolicySpec, ModelSpec) плюс контракты для интеграции с внешними источниками данных

**Текущая архитектура реализует Trinity паттерн с полной реализацией:**
- **ProblemFrame**: "Why" - постоянные аспекты проблемы (реализовано в `problem_frame.py`)
- **PolicySpec**: "What" - изменяемые аспекты политики (реализовано в `policy_spec.py`)
- **ModelSpec**: "How" - конфигурация моделирования (реализовано в `model_spec.py`)

PolicySurfaceIR v2.x остается совместимым интерфейсом для обратной совместимости.

### Ключевые обязанности

1. **Trinity артефакты**: Три независимых контракта (ProblemFrame, PolicySpec, ModelSpec)
2. **Канонические схемы**: Pydantic-модели для всех артефактов системы
3. **Валидация данных**: Строгие ограничения и проверки корректности
4. **Версионирование**: Детерминированные миграции схем, включая Trinity миграцию
5. **Многоязычность**: Поддержка локализации интерфейсов
6. **Безопасность**: Анти-runaway лимиты на размеры и глубину
7. **Линковка**: Валидация политик относительно расширенных kernel-реестров
8. **Fact Log**: Семантическая сеть фактов с provenance tracking и trust policies
9. **Kernel реестры**: Фундаментальные реестры типов, единиц, слотов, механизмов, ограничений, метрик, селекторных полей и политик доверия
10. **Калибровка**: Настройки оптимизации политик относительно исторических данных
11. **Запросы данных**: Структурированные запросы к результатам симуляции
12. **Предикаты**: Определение фильтров для доступа к данным симуляции
13. **Registry Fragments**: Детеминированная композиция доменных вкладов в реестры
14. **Norm Compliance**: Валидация политик на соответствие нормативным документам
15. **Data Connectors**: Контракты для интеграции с внешними источниками данных
16. **Типизированные значения**: Строго типизированные значения (MoneyValue, RateValue, CountValue, DurationValue)
17. **Асинхронные утилиты**: Инструменты для безопасной работы с асинхронным кодом

### Ключевые обязанности

1. **Канонические схемы**: Pydantic-модели для всех артефактов системы
2. **Валидация данных**: Строгие ограничения и проверки корректности
3. **Версионирование**: Детерминированные миграции схем
4. **Многоязычность**: Поддержка локализации интерфейсов
5. **Безопасность**: Анти-runaway лимиты на размеры и глубину

## Технологический стек

- **Pydantic v2**: Строгая валидация и сериализация данных
- **Python typing**: Полная статическая типизация с generics
- **JSON Schema**: Экспорт схем для внешних интеграций
- **difflib**: Генерация отчетов об изменениях при валидации
- **Canonical JSON**: Детерминированная сериализация для reproducible хешей
- **hashlib**: Детерминированные ID для артефактов и фактов

## Структура модуля

```
ir/
├── __init__.py              # Экспорт основных типов данных и функций
├── types.py                  # Перечисления, базовые типы и утилиты
├── connectors.py             # Контракты коннекторов для интеграции с внешними источниками данных
├── trinity/                  # Канонический Trinity пакет (ProblemFrame, PolicySpec, ModelSpec, TrinityBundle)
├── problem_frame.py          # ProblemFrame: определение проблемы и целей
├── policy_spec.py            # PolicySpec: спецификация политики и интервенций
├── model_spec.py             # ModelSpec: конфигурация модели мира
├── surface.py                # Legacy shim для PolicySurfaceIR (v2.x)
├── legacy/                   # Устаревшие контракты и миграции
├── selector_expr.py          # Селекторы для таргетинга интервенций
├── schedule.py               # Контракт расписаний
├── data_views.py             # Модели запросов данных (DataViewRequest, DataViewType)
├── queries.py                # Контракты запросов к миру (QueryScope, DocQuery, ClaimQuery, NormQuery)
├── validation.py             # Утилиты валидации и отчетов об ошибках
├── fact_log.py               # Контракты для семантической сети фактов
├── linker.py                 # Линкер политик с валидацией по реестрам
├── predicate.py              # Реестры предикатов для запросов данных
├── loaders.py                # Универсальная загрузка политик с автораспознаванием версий
├── calibration.py            # Контракты калибровки политик относительно данных
├── norm_pack.py              # Контракты для нормативных документов (NormPack, NormRule, NormRef)
├── registry_fragments.py     # Фрагменты реестров + контракт composer
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
├── migrations/
│   ├── __init__.py          # API миграций между версиями схем
│   └── trinity_migration.py # Legacy shim (реэкспорт из ir.legacy.migrations)
├── async_tools.py           # Асинхронные утилиты (run_coro_sync) - находится в common/
└── units.py                 # Устаревшие утилиты для работы с единицами измерения (дубликат kernel/units.py)
```

## Trinity артефакты

Система Trinity представляет политику как три независимых артефакта, каждый из которых отвечает за отдельный аспект моделирования. Эта архитектура обеспечивает разделение ответственности и позволяет независимо оптимизировать различные аспекты политики.

### TrinityBundle - контейнер артефактов

**TrinityBundle** объединяет все три артефакта для совместного использования и транспортировки:

```python
from polisyos.ir.trinity import TrinityBundle, ProblemFrame, PolicySpec, ModelSpec

# Создание полного Trinity Bundle
bundle = TrinityBundle(
    problem_frame=problem_frame,
    policy_spec=policy_spec,
    model_spec=model_spec,
)

# Сериализация для хранения
import json
with open('policy_bundle.json', 'w') as f:
    json.dump(bundle.model_dump(), f, indent=2, ensure_ascii=False)
```

### 1. ProblemFrame (`problem_frame.py`) - "Why" артефакт

**ProblemFrame** определяет постоянные аспекты проблемы, которые не изменяются в рамках эксперимента. Это включает цели, ограничения, заинтересованные стороны и критерии успеха.

```python
from polisyos.ir.problem_frame import ProblemFrame, KPISpec, SuccessCriterion, StakeholderSpec
from polisyos.ir.types import OptimizationDirection, EntityType

problem_frame = ProblemFrame(
    schema_version="1.0",
    domain=ProblemDomain.FISCAL,
    objectives=[
        KPISpec(
            kpi_id="gdp_growth",
            name=TranslatableString(en="GDP Growth Rate"),
            direction=OptimizationDirection.MAXIMIZE,
            unit_id="ratio",
            description="Annual GDP growth rate"
        )
    ],
    constraints=[
        ConstraintSpec(
            constraint_id="budget_deficit_limit",
            operator="<=",
            value=0.03,  # 3% of GDP
            description="Budget deficit cannot exceed 3% of GDP"
        )
    ],
    stakeholders=[
        StakeholderSpec(
            stakeholder_id="government",
            entity_type=EntityType.AGENT,
            influence_level="high",
            interests=["fiscal_stability", "economic_growth"]
        )
    ],
    success_criteria=[
        SuccessCriterion(
            criterion_id="poverty_reduction",
            description="Reduce poverty rate by at least 10%",
            metric_id="poverty_rate",
            threshold=0.1,
            direction="decrease"
        )
    ]
)
```

### 2. PolicySpec (`policy_spec.py`) - "What" артефакт

**PolicySpec** определяет, какие действия предпринимаются - интервенции, механизмы и их параметры. Этот артефакт изменяется при оптимизации политики.

**Ключевые компоненты:**
- **InterventionSpec**: Спецификация отдельных интервенций с параметрами, расписанием и целями
- **MechanismBinding**: Связывание интервенций с механизмами Foundry
- **implementation_notes**: Технические заметки по реализации
- **policy_labels**: Метки для категоризации и фильтрации

```python
from polisyos.ir.policy_spec import PolicySpec, InterventionSpec, MechanismBinding, ParameterSpec
from polisyos.ir.surface import ScheduleSpec, SelectorPredicate
from polisyos.ir.types import TranslatableString

policy_spec = PolicySpec(
    schema_version="1.0",
    interventions=[
        InterventionSpec(
            intervention_id="progressive_tax",
            name=TranslatableString(en="Progressive Income Tax", ua="Прогресивний податок"),
            kind="income_tax_mechanism",
            target=SelectorPredicate(
                field="annual_income",
                operator=">",
                value=10000
            ),
            schedule=ScheduleSpec(
                start_step=0,
                end_step=120,  # 10 лет
                frequency="annual"
            ),
            params={
                "tax_brackets": [
                    {"min_income": 0, "max_income": 10000, "rate": 0.0},
                    {"min_income": 10000, "max_income": 50000, "rate": 0.15},
                    {"min_income": 50000, "rate": 0.25}
                ],
                "deductions": ["standard_deduction", "mortgage_interest"]
            }
        ),
        InterventionSpec(
            intervention_id="corporate_subsidies",
            name=TranslatableString(en="Green Energy Subsidies"),
            kind="subsidy_mechanism",
            target=SelectorPredicate(
                field="industry",
                operator="in",
                value=["renewable_energy", "clean_tech"]
            ),
            schedule=ScheduleSpec(
                start_step=12,  # Начать через год
                end_step=120,
                frequency="quarterly"
            ),
            params={
                "subsidy_rate": 0.3,  # 30% от инвестиций
                "max_subsidy": 1000000,
                "eligibility_criteria": ["employment_creation", "co2_reduction"]
            }
        )
    ],
    mechanism_bindings=[
        MechanismBinding(
            binding_id="tax_collection",
            mechanism_id="income_tax_mechanism",
            intervention_ids=["progressive_tax"]
        ),
        MechanismBinding(
            binding_id="subsidy_program",
            mechanism_id="subsidy_mechanism",
            intervention_ids=["corporate_subsidies"]
        )
    ],
    implementation_notes=[
        "Progressive tax requires annual income data aggregation",
        "Subsidies need quarterly business performance metrics",
        "Both mechanisms require integration with existing tax system"
    ],
    policy_labels=[
        "fiscal_policy",
        "green_transition",
        "income_redistribution"
    ]
)
```

### 3. ModelSpec (`model_spec.py`) - "How" артефакт

**ModelSpec** определяет, как моделируется мир - агенты, окружение, данные и предположения. Этот артефакт используется для sensitivity analysis с разными конфигурациями моделирования.

**Ключевые компоненты:**
- **data_snapshot_ref**: Ссылка на моментальный снимок данных для симуляции
- **registry_bundle_ref**: Ссылка на реестры механизмов и единиц
- **time_semantics**: Конфигурация временных параметров
- **assumptions**: Явные предположения модели для анализа чувствительности
- **model_notes**: Технические заметки по моделированию
- **model_labels**: Метки для категоризации конфигураций

```python
from polisyos.ir.model_spec import ModelSpec, AgentTypeConfig, EnvironmentConfig, AssumptionSpec
from polisyos.ir.types import AssumptionType, FidelityLevel
from polisyos.ir.surface import TimeSemantics

model_spec = ModelSpec(
    schema_version="1.0",
    data_snapshot_ref="sha256:abc123def456789...",  # CAS reference to data
    registry_bundle_ref="sha256:fed789ghi012345...", # CAS reference to registries
    time_semantics=TimeSemantics(
        time_unit="month",
        total_steps=120,
        step_size=1,
        start_date="2024-01-01"
    ),
    assumptions=[
        AssumptionSpec(
            assumption_id="rational_households",
            type=AssumptionType.BEHAVIORAL,
            description="Households optimize utility based on income and consumption"
        ),
        AssumptionSpec(
            assumption_id="perfect_information",
            type=AssumptionType.INFORMATIONAL,
            description="All agents have complete information about market conditions"
        ),
        AssumptionSpec(
            assumption_id="sticky_prices",
            type=AssumptionType.STRUCTURAL,
            description="Prices adjust slowly to market changes (menu costs)"
        )
    ],
    model_notes=[
        "Uses quarterly GDP data from national statistics office",
        "Inflation expectations based on historical adaptive model",
        "Unemployment follows Okun's law with coefficient 2.0"
    ],
    model_labels=[
        "baseline_economy",
        "rational_expectations",
        "menu_costs"
    ]
)

# Альтернативная конфигурация для sensitivity analysis
alternative_model = ModelSpec(
    schema_version="1.0",
    data_snapshot_ref="sha256:xyz789...",  # Different data snapshot
    registry_bundle_ref="sha256:fed789ghi012345...",
    time_semantics=TimeSemantics(
        time_unit="month",
        total_steps=120,
        step_size=1,
        start_date="2024-01-01"
    ),
    assumptions=[
        AssumptionSpec(
            assumption_id="bounded_rationality",
            type=AssumptionType.BEHAVIORAL,
            description="Households use heuristics and have limited cognitive capacity"
        ),
        AssumptionSpec(
            assumption_id="information_asymmetry",
            type=AssumptionType.INFORMATIONAL,
            description="Some agents have better access to information than others"
        ),
        AssumptionSpec(
            assumption_id="flexible_prices",
            type=AssumptionType.STRUCTURAL,
            description="Prices adjust instantly to clear markets"
        )
    ],
    model_notes=[
        "Same economic data but different behavioral assumptions",
        "Tests robustness of policy recommendations"
    ],
    model_labels=[
        "sensitivity_analysis",
        "bounded_rationality",
        "flexible_prices"
    ]
)
```

## Основные компоненты

### 1. Surface контракты (`surface.py`) - v2.0

#### PolicySurfaceIR - legacy контракт совместимости

Legacy контракт системы, разделяющий политику на исполняемую (semantic) и advisory части. PolicySurfaceIR сохраняется для обратной совместимости; канонический контракт политики — Trinity (ProblemFrame/PolicySpec/ModelSpec).

**Ключевые особенности:**
- Разделение на semantic (исполняемая логика) и advisory (человекочитаемые метаданные) части
- Строгая типизация с анти-runaway лимитами
- Поддержка многоязычных описаний
- Интеграция с kernel-реестрами для валидации

```python
from polisyos.ir.surface import (
    PolicySurfaceIR, PolicySemantic, PolicyAdvisory,
    InterventionSpec, ObjectiveSpec, AdvisoryEntity,
    SelectorPredicate, ScheduleSpec
)
from polisyos.ir.types import EntityType, TranslatableString, OptimizationDirection

# Semantic часть - исполняемая логика
semantic = PolicySemantic(
    context_snapshot_ref="sha256:abc123def456...",
    registry_bundle_ref="sha256:fed789ghi012...",
    objectives=[
        ObjectiveSpec(
            objective_id="maximize_gdp_growth",
            metric_id="gdp_growth",
            direction=OptimizationDirection.MAXIMIZE,
            weight=1.0
        )
    ],
    interventions=[
        InterventionSpec(
            intervention_id="income_tax_reform",
            kind="income_tax",
            target=SelectorPredicate(
                field="income",
                operator=">",
                value=10000.0
            ),
            schedule=ScheduleSpec(
                start_step=0,
                end_step=120  # 10 лет месячной симуляции
            ),
            params={
                "rate": 0.15,
                "threshold": 10000.0
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

Система проверки корректности политик относительно kernel-реестров. Линкер обеспечивает, что все ссылки в политике (механизмы, слоты, метрики, ограничения) существуют в соответствующих реестрах и имеют корректные параметры. Выполняет комплексную валидацию с учетом зависимостей между компонентами.

```python
from polisyos.ir.linker import link_policy, LinkReport
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY, DEFAULT_METRIC_REGISTRY,
    DEFAULT_CONSTRAINT_REGISTRY, DEFAULT_UNITS_REGISTRY
)

# Линковка политики с полным набором реестров
report = link_policy(
    policy=surface_policy,
    mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
    slot_registry=DEFAULT_SLOT_REGISTRY,
    merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    metric_registry=DEFAULT_METRIC_REGISTRY,
    constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
    units_registry=DEFAULT_UNITS_REGISTRY
)

if not report.ok:
    for issue in report.issues:
        print(f"{issue.severity}: {issue.message}")
        print(f"  Path: {'.'.join(str(p) for p in issue.path)}")
```

#### Типы проблем линковки

- `unknown_mechanism`: Механизм интервенции не найден в реестре
- `missing_param`: Отсутствует обязательный параметр механизма
- `param_type_mismatch`: Тип параметра не соответствует спецификации
- `param_range_violation`: Значение параметра вне допустимого диапазона
- `param_unit_mismatch`: Единица измерения параметра некорректна
- `unknown_slot`: Слот состояния не найден в реестре
- `slot_type_mismatch`: Несоответствие типов слота
- `slot_scope_mismatch`: Слот не доступен в данном scope
- `merge_rule_conflict`: Конфликт правил слияния состояний
- `constraint_violation`: Нарушение ограничений политики
- `metric_not_found`: Метрика оптимизации не найдена в реестре
- `unit_conversion_error`: Ошибка конвертации единиц измерения

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

Система загрузки поддерживает автоматическое распознавание форматов и конвертацию между legacy PolicySurfaceIR и каноническим TrinityBundle. Основная функция `load_policy()` принимает любые поддерживаемые форматы политик:

```python
from polisyos.ir.loaders import load_policy, load_trinity_bundle

# Автоматическая загрузка с распознаванием версии
policy = load_policy(input_data)  # Возвращает PolicySurfaceIR (legacy)
bundle = load_policy(input_data, as_trinity=True)  # Возвращает TrinityBundle

# Для миграций можно получить MigrationReport
bundle, report = load_trinity_bundle(input_data)
```

#### Конвертация версий

Миграции legacy → Trinity выполняются в `polisyos.ir.legacy.migrations.*` и не имеют побочных эффектов.

### 10. Калибровка политик (`calibration.py`)

#### Контракты калибровки

Система настройки параметров политик для соответствия историческим данным:

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

### 11. Контракты нормативных документов (`norm_pack.py`)

#### NormPack - пакеты нормативных документов

Система контрактов для представления нормативных документов и их применения к политикам. NormPack позволяет структурированно описывать юридические нормы, регуляторные требования и правила, которые должны учитываться при оценке политик.

**Ключевые особенности:**
- Деонтическая классификация норм (обязанности, запреты, разрешения)
- Ссылки на конкретные положения нормативных документов
- Декларативная применимость (jurisdiction, actors, concepts)
- Backend hints/exprs без интерпретации внутри IR

```python
from polisyos.ir.norm_pack import NormPack, NormRule, NormRef, RuleType

# Создание пакета норм
norm_pack = NormPack(
    pack_id="tax_regulation_2024",
    jurisdiction="Ukraine",
    effective_date="2024-01-01",
    norms=[
        NormRule(
            norm_id="income_tax_limit",
            provision_refs=[
                NormRef(
                    provision_id="article_167_1",
                    source_document="Tax_Code_Ukraine",
                    version="2024"
                )
            ],
            rule_type=RuleType.OBLIGATION,
            description="Income tax rate cannot exceed 18% for individuals",
            backend_refs=["expr_ast"],
            applicability={"jurisdiction": "UA", "concepts": ["income"]},
            backend_metadata={"when": "income > 50000"}
        ),
        NormRule(
            norm_id="minimum_wage",
            provision_refs=[
                NormRef(
                    provision_id="article_95",
                    source_document="Labor_Code_Ukraine",
                    version="2023"
                )
            ],
            rule_type=RuleType.PROHIBITION,
            description="Employer cannot pay less than minimum wage",
            backend_refs=["expr_ast"],
            applicability={"jurisdiction": "UA", "concepts": ["wage"]},
            backend_metadata={"when": "employment_status == 'employed'"}
        )
    ],
    metadata={
        "regulator": "Ministry_of_Finance",
        "review_date": "2024-12-31"
    }
)
```

#### Компоненты NormPack

**NormRule** - отдельное правило в пакете норм:
- `norm_id`: Уникальный идентификатор правила
- `provision_refs`: Ссылки на положения нормативных документов
- `rule_type`: Деонтическая классификация (обязанность/запрет/разрешение)
- `description`: Человекочитаемое описание правила
- `backend_refs`: Идентификаторы backend'ов, способных оценивать норму
- `backend_metadata`: Backend-специфичные данные (например, when/must/must_not)

**NormRef** - ссылка на положение нормативного документа:
- `provision_id`: Идентификатор положения (статья, пункт)
- `source_document`: Название документа
- `version`: Версия документа

**RuleType** - деонтическая классификация:
- `OBLIGATION`: Должен (обязанность)
- `PROHIBITION`: Не должен (запрет)
- `PERMISSION`: Может (разрешение)

### 13. Kernel: фундаментальные реестры (`kernel/`)

#### Архитектурная роль Kernel

Kernel предоставляет фундаментальный слой типизированных определений и реестров, обеспечивающих type safety на уровне всей системы Policy Engine. Все реестры Kernel используются линкером для валидации политик и обеспечивают единообразие интерпретации компонентов системы.

**Ключевые реестры:**
- **Mechanism Registry**: Спецификации типов механизмов интервенций с параметрами, слотами чтения/записи и правилами слияния
- **Slot Registry**: Определения слотов состояния агентов и сущностей с типизацией, scope и правилами слияния
- **Units Registry**: Типизированная система единиц измерения (валюты, проценты, количества)
- **Merge Rules Registry**: Правила разрешения конфликтов при пересекающихся интервенциях
- **Constraints Registry**: Ограничения на применение политик (accounting, non_negative, budget, legal)
- **Metrics Registry**: Спецификации метрик оптимизации с агрегацией и нормализацией
- **Selector Fields Registry**: Доступные поля для фильтрации сущностей в селекторах с типизацией
- **Trust Registry**: Политики доверия к источникам данных с уровнями confidence и validation rules

**Особенности Kernel:**
- Все реестры имеют версионирование (schema_version)
- Детерминированная валидация и линковка
- Поддержка type safety через Pydantic модели
- Интеграция с системой единиц измерения
- Расширяемая архитектура для новых типов компонентов
- Строгая типизация значений с reject float policy

```python
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY, DEFAULT_CONSTRAINT_REGISTRY,
    MechanismTypeRegistry, SlotRegistry, UnitsRegistry
)

# Использование default реестров
mechanism = DEFAULT_MECHANISM_REGISTRY.mechanisms["income_tax"]
slot = DEFAULT_SLOT_REGISTRY.slots["agents.income"]
unit = DEFAULT_UNITS_REGISTRY.units["usd"]
```

### 14. Контракты коннекторов данных (`connectors.py`)

#### Архитектурная роль

**Connectors** определяет канонические контракты для интеграции с внешними источниками данных в системе PolicyOS. Модуль устанавливает стандарты для коннекторов, обеспечивая единообразие интерфейсов и метаданных для всех типов источников данных.

**Ключевые особенности:**
- **Capability System**: Декларативная система возможностей коннекторов с битовой маской
- **Trust & Quality**: Уровни доверия и качества данных от источников
- **Versioning**: Детерминированное версионирование данных с поддержкой разных стратегий
- **Metadata Schema**: Стандартизированные метаданные коннекторов

#### Основные компоненты

```python
from polisyos.ir.connectors import (
    ConnectorCapability, TrustLevel, QualityTier,
    VersionStrategy, DataVersion, ConnectorMetadataSpec,
    capabilities_from_flags, flags_from_capabilities
)

# Определение возможностей коннектора
caps = (
    ConnectorCapability.FULL_FETCH |
    ConnectorCapability.STREAMING |
    ConnectorCapability.DATE_RANGE_FILTER
)

# Спецификация метаданных коннектора
metadata = ConnectorMetadataSpec(
    connector_id="worldbank_wdi",
    version="1.0.0",
    namespace="worldbank",
    source_name="World Bank World Development Indicators",
    source_organization="World Bank",
    trust_level=TrustLevel.HIGH,
    quality_tier=QualityTier.GOLD,
    capabilities=capabilities_from_flags(caps),
    description="Comprehensive development indicators database"
)

# Версионирование данных
version = DataVersion(
    strategy=VersionStrategy.TIMESTAMP,
    value="2024-01-01T00:00:00Z",
    timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    content_hash="sha256:abc123..."
)
```

#### Связь с Fabric Layer

Контракты из `ir.connectors` используются в `fabric.connectors` для реализации протокола SourceConnector:

- **IR Level**: Декларативные контракты (ConnectorCapability, ConnectorMetadataSpec)
- **Fabric Level**: Исполняемые протоколы (SourceConnector, FetchRequest, FetchResult)
- **Runtime Level**: Кэширование и оркестрация запросов к источникам

### 14. Типизированные значения (`kernel/numbers.py`, `kernel/values.py`)

#### Строгая типизация числовых значений

Kernel предоставляет строго типизированные числовые значения с автоматической валидацией и защитой от использования float:

```python
from polisyos.ir.kernel import DecimalValue, NonNegativeDecimal, PositiveDecimal

# Типизированные decimal значения с reject float
income: DecimalValue = Decimal("50000.50")  # ✅ Правильно
# income: float = 50000.50  # ❌ Ошибка валидации

# Ограниченные диапазоны
balance: NonNegativeDecimal = Decimal("1000.00")  # ≥ 0
count: PositiveDecimal = Decimal("5")  # > 0
```

#### Специализированные типы значений

```python
from polisyos.ir.kernel import MoneyValue, RateValue, CountValue, DurationValue

# Денежные величины с валютой и номинальным годом
salary = MoneyValue(amount=Decimal("50000"), currency="UAH", nominal_year=2024)

# Процентные ставки с автоматической конвертацией
tax_rate = RateValue.ratio(Decimal("0.15"))  # 15% как отношение
tax_rate_percent = RateValue(base="percent", value=Decimal("15"))  # 15% как процент

# Количества и продолжительности
employees = CountValue(value=100, label="IT specialists")
duration = DurationValue(value=12, unit="month")  # 12 месяцев
```

### 15. Асинхронные утилиты (`common/async_tools.py`)

#### Безопасная работа с корутинами

Утилиты для безопасного запуска асинхронного кода из синхронного контекста:

```python
from polisyos.common.async_tools import run_coro_sync

async def async_operation():
    # Асинхронная операция
    return await some_async_call()

# Безопасный запуск из sync кода
result = run_coro_sync(async_operation())
```

**Особенности:**
- Автоматическое обнаружение активного event loop
- ThreadPoolExecutor для случаев с running loop
- Graceful fallback к asyncio.run()

### 16. Система версий (`migrations/`)

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

#### Trinity миграция (legacy → canonical)

Специальная система миграции для преобразования PolicySurfaceIR в Trinity артефакты (ProblemFrame, PolicySpec, ModelSpec). Реализует структурное разделение политики на независимые компоненты:

```python
from polisyos.ir.legacy.migrations.surface_to_trinity import (
    migrate_surface_ir_to_trinity,
    migrate_trinity_to_surface_ir,
)

# Разделение PolicySurfaceIR на Trinity артефакты
surface_policy = PolicySurfaceIR(...)  # Исходная политика v2.x

bundle, report = migrate_surface_ir_to_trinity(surface_policy)
reconstructed, report = migrate_trinity_to_surface_ir(bundle)
```

**Логика разделения:**
- **ProblemFrame**: Цели, ограничения, stakeholders из advisory.entities
- **PolicySpec**: Интервенции, параметры, расписания
- **ModelSpec**: Ссылки на данные, реестры, предположения

#### Поддерживаемые версии

- **Trinity 1.0**: ProblemFrame, PolicySpec, ModelSpec (канонический контракт)
- **PolicySurfaceIR 2.x**: Унаследованный интерфейс с автоматической миграцией в Trinity
- **PolicySurfaceIR 2.0**: Текущая стабильная версия с полной поддержкой
- **PolicySurfaceIR 1.x**: Устаревший PolicyIR (конвертация через `load_policy()`)
- **v0.x**: Устаревшие форматы (требуют ручной миграции)
    "adaptive_agent": MechanismTypeSpec(
        mechanism_id="adaptive_agent",
        params={
            "observation_space": ParamSpec(
                param_id="observation_space",
                value_type=ParamType.ARRAY,
                required=True,
                description="List of slot IDs to observe"
            ),
            "action_space": ParamSpec(
                param_id="action_space",
                value_type=ParamType.OBJECT,
                required=True,
                description="Action specification object"
            ),
            "utility_function": ParamSpec(
                param_id="utility_function",
                value_type=ParamType.STRING,
                required=True,
                description="Utility function identifier"
            ),
            "policy_model": ParamSpec(
                param_id="policy_model",
                value_type=ParamType.OBJECT,
                required=False,
                description="Neural network architecture"
            ),
            "weights_artifact": ParamSpec(
                param_id="weights_artifact",
                value_type=ParamType.STRING,
                required=False,
                description="Trained model artifact reference"
            ),
            "learning_rate": ParamSpec(
                param_id="learning_rate",
                value_type=ParamType.DECIMAL,
                required=False,
                default_value=Decimal("0.001")
            ),
            "seed": ParamSpec(
                param_id="seed",
                value_type=ParamType.INT,
                required=False,
                description="RNG seed for reproducibility"
            )
        },
        reads_slots=[],  # Dynamic based on observation_space
        writes_slots=[], # Dynamic based on action_space
        description="Reinforcement learning adaptive agent"
    )
})
```

**Ключевые возможности:**
- Полная типизация параметров с единицами измерения
- Валидация диапазонов значений
- Поддержка trainable параметров для калибровки
- Спецификация слотов чтения/записи для dependency analysis
- Правила слияния для разрешения конфликтов

    "agents.income": SlotSpec(
        slot_id="agents.income",
        scope=SlotScope.PER_AGENT,
        value_type="decimal",
        unit=UnitRef(unit_id="usd"),
        kind=SlotKind.FLOW,
        merge_rule=MergeRuleRef(rule_id="sum"),
        state_path="agents.income",
        description="Agent income (per-step flow)",
        reset_rule="zero"
    ),
    "agents.reported_income": SlotSpec(
        slot_id="agents.reported_income",
        scope=SlotScope.PER_AGENT,
        value_type="decimal",
        unit=UnitRef(unit_id="usd"),
        kind=SlotKind.FLOW,
        merge_rule=MergeRuleRef(rule_id="override"),
        state_path="agents.reported_income",
        description="Income reported by agent for taxation",
        reset_rule="zero"
    ),
    "government.balance": SlotSpec(
        slot_id="government.balance",
        scope=SlotScope.GLOBAL,
        value_type="decimal",
        unit=UnitRef(unit_id="usd"),
        kind=SlotKind.STOCK,
        merge_rule=MergeRuleRef(rule_id="sum"),
        state_path="government_balance",
        description="Government balance (stock)",
        reset_rule="carry"
    ),
    "global.tax_rate": SlotSpec(
        slot_id="global.tax_rate",
        scope=SlotScope.GLOBAL,
        value_type="decimal",
        unit=UnitRef(unit_id="ratio"),
        kind=SlotKind.PARAMETER,
        merge_rule=MergeRuleRef(rule_id="override"),
        state_path="global_tax_rate",
        description="Global tax rate parameter",
        reset_rule="carry"
    ),
    "global.inflation_rate": SlotSpec(
        slot_id="global.inflation_rate",
        scope=SlotScope.GLOBAL,
        value_type="decimal",
        unit=UnitRef(unit_id="ratio"),
        kind=SlotKind.FLOW,
        merge_rule=MergeRuleRef(rule_id="last_wins"),
        state_path="global_inflation",
        description="Inflation rate (updated externally)",
        reset_rule="carry"
    )
})
```



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
from polisyos.ir.kernel import (
    ConflictResolution,
    MergeRuleRegistry,
    MergeRuleSpec,
    MergeRuleKind,
)

registry = MergeRuleRegistry(
    rules={
        "priority": MergeRuleSpec(
            rule_id="priority",
            kind=MergeRuleKind.PRIORITY,
            commutativity=True,
            associativity=True,
            idempotency=True,
            conflict_resolution=ConflictResolution.ERROR,
            description="Resolve by priority field",
        ),
        "error": MergeRuleSpec(
            rule_id="error",
            kind=MergeRuleKind.ERROR,
            commutativity=True,
            associativity=True,
            idempotency=True,
            conflict_resolution=ConflictResolution.ERROR,
            description="Raise error on conflict",
        ),
    }
)
```

## Expression Handling (IR Only)

IR хранит выражения как декларативные строки и не импортирует backend-движки
для их оценки. Проверка семантики и выполнение выражений происходят в Lex/Scientist.

Для синтаксической проверки выражений в IR доступен helper
`polisyos.ir.norm_pack.parse_expr_syntax`, который вызывает `ast.parse(expr, mode=\"eval\")`
и возвращает только статус/ошибку.

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

### Работа с Trinity артефактами

```python
from polisyos.ir import ProblemFrame, PolicySpec, ModelSpec
from polisyos.ir.trinity import TrinityBundle

# Создание полного набора Trinity артефактов
bundle = TrinityBundle(
    problem_frame=problem_frame,
    policy_spec=policy_spec,
    model_spec=model_spec,
)

# Сериализация для хранения
import json
with open('policy_bundle.json', 'w') as f:
    json.dump(bundle.model_dump(), f, indent=2, ensure_ascii=False)

# Доступ к отдельным артефактам
pf = bundle.problem_frame
ps = bundle.policy_spec
ms = bundle.model_spec
```

### Базовый импорт

```python
# Основные типы (рекомендуемый импорт через __init__.py)
from polisyos.ir import (
    # Trinity артефакты
    ProblemFrame, PolicySpec, ModelSpec, TrinityBundle,
    # Контракты нормативных документов
    NormPack, NormRule, NormRef, RuleType,
    # Контракты коннекторов данных
    ConnectorCapability, TrustLevel, QualityTier, ConnectorMetadataSpec,
    # Унаследованные интерфейсы
    PolicySurfaceIR, load_policy, CalibrationConfig, CalibrationTarget,
    DataViewRequest, DataViewType, AccessTier, DataFilter
)

# Асинхронные утилиты
from polisyos.common.async_tools import run_coro_sync

# Полный импорт для доступа ко всем компонентам
from polisyos.ir.trinity import (
    TrinityBundle,
    ProblemFrame, PolicySpec, ModelSpec
)

from polisyos.ir.norm_pack import (
    NormPack, NormRule, NormRef, RuleType
)

from polisyos.ir.connectors import (
    ConnectorCapability, TrustLevel, QualityTier, VersionStrategy,
    DataVersion, ConnectorMetadataSpec, capabilities_from_flags, flags_from_capabilities
)

from polisyos.ir.surface import (
    PolicySurfaceIR, PolicySemantic, PolicyAdvisory,
    InterventionSpec, ObjectiveSpec, ConstraintSpec,
    SelectorPredicate, SelectorAll, SelectorAny, SelectorNot,
    ScheduleSpec, schedule_range
)

from polisyos.ir.kernel import (
    MechanismTypeRegistry, SlotRegistry, UnitsRegistry,
    SelectorFieldRegistry, TrustRegistry, ConstraintRegistry,
    MoneyValue, RateValue, CountValue, DurationValue,
    MergeRuleRegistry, MetricRegistry,
    DecimalValue, NonNegativeDecimal, PositiveDecimal,
    DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY, DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_METRIC_REGISTRY, DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_TRUST_REGISTRY, DEFAULT_MERGE_RULE_REGISTRY
)

from polisyos.ir.linker import link_policy, LinkReport, LinkIssue
from polisyos.ir.fact_log import Fact, FactBatch, FactProvenance, FactTrust, FactLegal
from polisyos.ir.validation import ValidationReport, build_validation_report
from polisyos.ir.calibration import (
    CalibrationConfig, CalibrationTarget, TargetAlignConfig, TargetLossConfig
)
from polisyos.ir.legacy.migrations.surface_to_trinity import (
    migrate_surface_ir_to_trinity, migrate_trinity_to_surface_ir
)
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

Модуль IR включает всестороннее тестирование, покрывающее контракты, интеграцию и unit-тесты:

```bash
# Контрактные тесты IR (ядро системы)
pytest tests/contract/test_ir_surface.py      # PolicySurfaceIR и компоненты
pytest tests/contract/test_ir_connectors.py    # Контракты коннекторов данных
pytest tests/contract/test_ir_linker.py       # Линкер и валидация политик
pytest tests/contract/test_ir_loaders.py      # Загрузчики и конвертация версий
pytest tests/contract/test_ir_calibration.py  # Калибровка политик
pytest tests/contract/test_ir_kernel.py       # Kernel реестры и типы
pytest tests/contract/test_ir_fact_log.py     # Fact Log контракты

# Тесты валидации и quality gates
pytest tests/contract/test_fabric_gates.py    # Валидационные ворота

# Интеграционные тесты
pytest tests/integration/test_foundry_ir.py   # IR + Foundry интеграция
pytest tests/integration/test_scientist_ir.py # IR + Scientist интеграция
pytest tests/integration/test_runtime_ir.py   # IR + Runtime интеграция

# Unit-тесты отдельных компонентов
pytest tests/unit/test_ir_validation.py       # Система валидации и отчетов
pytest tests/unit/test_ir_data_views.py       # Запросы данных
pytest tests/unit/test_ir_predicate.py        # Предикаты для фильтров
pytest tests/unit/test_ir_migrations.py       # Миграции схем
pytest tests/unit/test_ir_units.py            # Система единиц измерения
```

**Ключевые тестовые сценарии:**
- **Contract tests**: Проверяют совместимость API и behavior контрактов
- **Integration tests**: Валидируют взаимодействие IR с другими модулями
- **Unit tests**: Покрывают edge cases и error handling, включая новые kernel реестры и типы
- **Migration tests**: Гарантируют backward compatibility при изменениях схем, включая Trinity миграцию
- **Async tests**: Тестирование асинхронных утилит и интеграций

## Архитектурные принципы

IR строго следует архитектурным законам проекта:

1. **Закон A**: Граф зависимостей только внутрь - IR не зависит ни от кого
2. **Закон B**: Это компилятор - чистое frontend/IR/backend разделение
3. **Закон C**: Контракты = единственный источник истины
4. **Закон D**: Воспроизводимость через versioning и миграции

## Связанные компоненты

### Зависимости и взаимодействие

IR является фундаментом всей системы и используется всеми модулями Policy Engine:

- **Scientist**: Генерирует Trinity артефакты (ProblemFrame, PolicySpec, ModelSpec) или PolicySurfaceIR, использует линкер для валидации, типы из `types.py` и загрузчики из `loaders.py`.
- **Foundry**: Компилирует `InterventionSpec` из PolicySpec в JAX-механизмы, использует kernel-реестры для линковки, калибровку из `calibration.py` для оптимизации, работает с ModelSpec для конфигурации симуляции
- **Fabric**: Обрабатывает `DataViewRequest` для запросов данных, использует предикаты из `predicate.py`, контракты фактов из `fact_log.py` для семантической сети, работает с ModelSpec для понимания структуры данных. Использует контракты коннекторов из `connectors.py` для стандартизации интерфейсов внешних источников данных
- **Core**: Предоставляет базовую инфраструктуру, использует `Fact` и `FactBatch` для построения семантической сети знаний, интегрируется с ModelSpec для загрузки данных
- **Runtime**: Хранит артефакты Trinity и PolicySurfaceIR для аудита, использует `CalibrationConfig` для управления оптимизацией, сохраняет метаданные из всех артефактов
- **Common**: Использует систему миграций из `common.migrations` для версионирования схем, включая Trinity миграции; предоставляет `async_tools.py` для асинхронных операций
- **Legal (Scientist/Governance)**: Использует `NormPack` и `NormRule` для определения нормативных документов и backend-движки для оценки выражений в правилах compliance

### Архитектурные контракты

```
Scientist → Trinity (ProblemFrame, PolicySpec, ModelSpec) → Linker → Foundry → Simulation
   ↓                                                        ↓             ↓
PolicySurfaceIR (legacy)                              kernel/     calibration.py
   ↓                                                        ↓             ↓
loaders.py (migration)                             surface.py     executor.py

                     ↓                                    ↓
                  Fabric → DataViewRequest → Runtime   Legal Pass → Backend
                     ↓                                    ↓
                Fact Log → Semantic Network → Core   NormPack → Expression Backend
```

**Trinity Workflow:**
```
ProblemFrame (constant) + PolicySpec (iterated) + ModelSpec (varied)
    ↓
  Linker validation
    ↓
Foundry compilation → Simulation → Analysis
```

---

**См. также**:
- [Общая архитектура](../../../../architecture.md)
- [Примеры использования](../../../examples/ir_base_demo.py)
- [Kernel реестры](kernel/README.md) - фундаментальные реестры и типы
- [Migrations](migrations/README.md) - система версионирования схем
- [Expression AST Backend](../../scientist/governance/legal/backends/expr_ast.py) - интеграция с Legal Pass
- [Fabric](../fabric/README.md) - система данных
- [Scientist](../scientist/README.md) - генерация политик
