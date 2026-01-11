# Polisyos IR: Policy Intermediate Representation

**IR (Intermediate Representation)** - это промежуточное представление политик и симуляций в системе Policy Engine. Модуль определяет канонические контракты данных, обеспечивая единообразие коммуникации между всеми компонентами системы: от LLM-агентов до JAX-симуляций.

## Архитектурная роль

Согласно [архитектурным принципам](../../../../architecture.md) проекта, **IR** является фундаментальным слоем контрактов:

```
NL → LLM → IR (AST) → Compilation → Runtime (UDF + Foundry) → Artifacts
```

### Положение в графе зависимостей

- **Входящие зависимости**: НИКАКИХ (чистый контракт)
- **Исходящие зависимости**: Используется всеми модулями (`scientist`, `fabric`, `foundry`)
- **Принцип**: "IR → никого" (Закон A - граф зависимостей только внутрь)

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
├── __init__.py              # Экспорт основных типов данных
├── kernel/                  # Shared kernel: units, slots, merge rules, time semantics
├── contract.py               # Основные модели данных (316 строк)
├── types.py                  # Перечисления и базовые типы (81 строка)
├── data_views.py             # Модели запросов данных (60 строк)
├── validation.py             # Утилиты валидации и отчетов (89 строк)
├── units.py                  # Default units registry + legacy UNIT_REGISTRY
└── migrations/
    ├── __init__.py          # Экспорт миграций
    ├── base.py               # Инфраструктура миграций
    └── policy_ir.py          # Конкретные миграции IR
```

## Основные компоненты

### 1. Контракты данных (`contract.py`)

#### PolicyIR - корневой документ

Основная структура, описывающая полную политику симуляции:

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
from polisyos.ir.data_views import DataViewRequest, DataViewType, AccessTier

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

- `issues_from_validation_error()` - конвертация Pydantic ошибок
- `diff_payloads()` - генерация diff между версиями
- `summarize_issues()` - суммарный отчет проблем

### 6. Система версий (`migrations/`)

#### Детерминированные миграции

```python
from polisyos.ir.migrations import migrate_policy_ir

# Миграция данных между версиями
migrated_data = migrate_policy_ir(
    data=input_data,
    target_version="1.0",
    allow_major=False  # Защита от major изменений
)
```

#### Регистрация миграций

```python
from polisyos.ir.migrations.base import register_migration

@register_migration("0.9", "1.0")
def migrate_policy_ir_0_9_to_1_0(data: dict) -> dict:
    """Миграция: projectName → project_name"""
    if "projectName" in data:
        data["project_name"] = data.pop("projectName")
    return data
```

## Ограничения безопасности

IR включает строгие лимиты для предотвращения runaway-симуляций:

```python
# Анти-runaway константы
MAX_ENTITIES = 500      # Максимум сущностей
MAX_INTERVENTIONS = 200 # Максимум вмешательств
MAX_DEPTH = 4          # Максимальная глубина иерархии
MAX_CHILDREN = 200     # Максимум детей у сущности
MAX_ID_LEN = 64        # Длина идентификаторов
```

## Единицы измерения (`units.py`)

Стандартизированный реестр единиц для параметров:

```python
UNIT_REGISTRY = {
    "ratio": {"kind": "dimensionless"},
    "percent": {"kind": "dimensionless"},
    "uah": {"kind": "currency"},
    "usd": {"kind": "currency"},
    "year": {"kind": "time"},
    "month": {"kind": "time"},
    "per_step": {"kind": "rate"},
}
```

## Использование в коде

### Базовый импорт

```python
from polisyos.ir import (
    # Основные типы
    EntityType, OptimizationDirection, TranslatableString,

    # Модели данных
    PolicyIR, PolicyEntity, Intervention, TargetSelector,

    # Запросы данных
    DataViewRequest, DataViewType, AccessTier,

    # Валидация
    ValidationReport
)
```

### Создание политики

```python
from polisyos.ir.contract import PolicyIR, PolicyEntity, Intervention
from polisyos.ir.types import EntityType, TranslatableString

# Создание простой политики
policy = PolicyIR(
    schema_version="1.0",
    project_name="Tax Policy Simulation",
    entities=[
        PolicyEntity(
            id="government",
            entity_type=EntityType.AGENT,
            name=TranslatableString(en="Government", ua="Уряд"),
            state_variables={"budget": 1000000.0}
        )
    ],
    interventions=[
        Intervention(
            id="basic_income",
            name=TranslatableString(en="Basic Income", ua="Базовий дохід"),
            target_selector=TargetSelector(
                all_of=[SelectorPredicate(field="income", operator="<", value=500)]
            ),
            mechanism_type="TransferPayment",
            parameters={"amount": 200.0, "frequency": "monthly"}
        )
    ]
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
```

## JSON Schema экспорт

IR поддерживает автоматический экспорт JSON Schema для интеграций:

```bash
# Генерация схемы (через tools/diagnostics/generate_ir_schema.py)
python tools/diagnostics/generate_ir_schema.py

# Результат: policy_ir_schema.json
```

## Тестирование

Модуль включает исчерпывающее тестирование:

```bash
# Контрактные тесты
pytest tests/contract/test_ir_contract.py

# Миграции
pytest tests/contract/test_ir_migrations.py

# Валидация
pytest tests/contract/test_fabric_gates.py
```

## Архитектурные принципы

IR строго следует архитектурным законам проекта:

1. **Закон A**: Граф зависимостей только внутрь - IR не зависит ни от кого
2. **Закон B**: Это компилятор - чистое frontend/IR/backend разделение
3. **Закон C**: Контракты = единственный источник истины
4. **Закон D**: Воспроизводимость через versioning и миграции

## Связанные компоненты

- **Scientist**: Использует IR для генерации политик из NL
- **Fabric**: Импортирует типы данных из IR для запросов
- **Foundry**: Получает скомпилированные параметры из IR
- **Runtime**: Хранит артефакты IR для аудита

---

**См. также**: [Общая архитектура](../../../../architecture.md), [Примеры использования](../../../examples/ir_base_demo.py)
