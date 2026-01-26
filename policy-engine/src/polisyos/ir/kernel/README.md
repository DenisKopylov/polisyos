# IR Kernel: Фундаментальные реестры и типы

**Kernel** - это фундаментальный слой типизированных определений и реестров системы IR, обеспечивающий type safety и единообразие интерпретации компонентов Policy Engine.

**Обновлено**: документация актуализирована для отражения текущего состояния на 2026-01-26, включая новые реестры (constraints, metrics, selector_fields, trust) и расширенную систему типов.

## Архитектурная роль

Kernel предоставляет фундаментальные строительные блоки для всей системы IR:

- **Type Safety**: Строгая типизация всех компонентов через Pydantic модели
- **Registry Pattern**: Централизованные реестры для всех типов сущностей
- **Validation**: Автоматическая валидация корректности определений
- **Versioning**: Версионирование схем с обратной совместимостью
- **Extensibility**: Расширяемая архитектура для новых типов компонентов

## Структура модуля

```
kernel/
├── __init__.py              # Экспорт всех kernel компонентов
├── base.py                  # KernelModel, паттерны ID, утилиты валидации
├── mechanisms.py            # Реестр типов механизмов (MechanismTypeRegistry)
├── slots.py                 # Реестр слотов состояний (SlotRegistry)
├── constraints.py           # Реестр ограничений (ConstraintRegistry)
├── metrics.py               # Реестр метрик оптимизации (MetricRegistry)
├── selector_fields.py       # Реестр полей селекторов (SelectorFieldRegistry)
├── merge_rules.py           # Правила слияния состояний (MergeRuleRegistry)
├── time_semantics.py        # Семантика времени и расписаний (TimeSemantics)
├── trust.py                 # Политики доверия к данным (TrustRegistry)
├── units.py                 # Система единиц измерения (UnitsRegistry)
├── numbers.py               # Типизированные числовые значения (DecimalValue, etc.)
└── values.py                # Типизированные значения (MoneyValue, RateValue, etc.)
```

## Основные компоненты

### 1. Base модели (`base.py`)

#### KernelModel - базовый класс

Все модели Kernel наследуются от `KernelModel`, который предоставляет:

```python
class KernelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

**Особенности:**
- `extra="forbid"`: Запрещает дополнительные поля
- `frozen=True`: Модели неизменяемы после создания
- Автоматическая валидация всех полей

#### Паттерны идентификаторов

```python
ID_PATTERN = r"^[a-z][a-z0-9_.-]*$"           # Общий паттерн ID
SLOT_ID_PATTERN = r"^[a-z][a-z0-9_.]*$"       # Паттерн для slot_id
ARTIFACT_ID_PATTERN = r"^sha256:[0-9a-f]{64}$" # SHA256 хеши артефактов
```

#### Утилиты валидации

```python
def reject_float(value: Any) -> Any:
    """Запрещает использование float, требует Decimal/int/str"""

def reject_floats_deep(value: Any) -> Any:
    """Рекурсивно проверяет отсутствие float в структурах данных"""
```

### 2. Реестр механизмов (`mechanisms.py`)

#### MechanismTypeRegistry

Определяет доступные типы механизмов интервенций с полной спецификацией:

```python
from polisyos.ir.kernel import MechanismTypeRegistry, MechanismTypeSpec, ParamSpec, ParamType

# Типы параметров
class ParamType(str, Enum):
    DECIMAL = "decimal"
    INT = "int"
    BOOL = "bool"
    STRING = "string"
    MONEY = "money"
    RATE = "rate"
    COUNT = "count"
    DURATION = "duration"
    ENUM = "enum"
    OBJECT = "object"
    ARRAY = "array"

# Спецификация параметра
class ParamSpec(KernelModel):
    param_id: str
    required: bool = False
    value_type: ParamType = ParamType.DECIMAL
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    trainable: bool = False  # Для калибровки
    unit_id: str | None = None
    description: str | None = None
    enum_values: list[str] | None = None

# Спецификация механизма
class MechanismTypeSpec(KernelModel):
    mechanism_id: str
    params: dict[str, ParamSpec] = {}
    reads_slots: list[str] = []   # Читаемые слоты
    writes_slots: list[str] = []  # Записываемые слоты
    default_merge: dict[str, str] = {}  # Правила слияния
    description: str | None = None
```

**Примеры predefined механизмов:**
- `tax_subsidy`: Субсидии с настраиваемой ставкой
- `income_tax`: Прогрессивный подоходный налог
- `adaptive_agent`: Агент с reinforcement learning

### 3. Реестр слотов (`slots.py`)

#### SlotRegistry

Определяет слоты состояния агентов и сущностей:

```python
from polisyos.ir.kernel import SlotRegistry, SlotSpec, SlotKind, SlotScope

class SlotKind(str, Enum):
    STOCK = "stock"       # Накопительные величины
    FLOW = "flow"         # Потоковые величины
    PARAMETER = "parameter"  # Параметры системы

class SlotScope(str, Enum):
    GLOBAL = "global"
    PER_AGENT = "per_agent"
    PER_FIRM = "per_firm"
    PER_ENTITY = "per_entity"

class SlotSpec(KernelModel):
    slot_id: str
    scope: SlotScope
    value_type: SlotValueType
    unit: UnitRef | None = None
    kind: SlotKind
    merge_rule: MergeRuleRef
    state_path: str | None = None
    description: str | None = None
    reset_rule: Literal["carry", "zero"] | None = None
    conservation_group_id: str | None = None
```

**Примеры слотов:**
- `agents.income`: Доход агента (FLOW, PER_AGENT)
- `government.balance`: Баланс правительства (STOCK, GLOBAL)
- `global.tax_rate`: Ставка налога (PARAMETER, GLOBAL)

### 4. Система единиц (`units.py`)

#### UnitsRegistry

Типизированная система единиц измерения:

```python
from polisyos.ir.kernel import UnitsRegistry, MoneyUnit, RateUnit, UnitKind

class UnitKind(str, Enum):
    MONEY = "money"
    RATE = "rate"
    COUNT = "count"
    DURATION = "duration"
    DIMENSIONLESS = "dimensionless"
    GENERIC = "generic"

# Денежная единица
class MoneyUnit(UnitSpec):
    kind: Literal["money"] = "money"
    currency: str  # "UAH", "USD", "EUR"
    nominal_year: int | None = None
    price_base: str | None = None

# Процентная ставка
class RateUnit(UnitSpec):
    kind: Literal["rate"] = "rate"
    base: Literal["ratio", "percent"] = "ratio"
```

### 5. Правила слияния (`merge_rules.py`)

#### MergeRuleRegistry

Логика разрешения конфликтов при пересекающихся интервенциях:

```python
from polisyos.ir.kernel import (
    ConflictResolution,
    MergeRuleRegistry,
    MergeRuleSpec,
    MergeRuleKind,
)

class MergeRuleKind(str, Enum):
    SUM = "sum"           # Сложение значений
    OVERRIDE = "override" # Последнее значение wins
    PRIORITY = "priority" # По полю priority
    ERROR = "error"       # Ошибка при конфликте

DEFAULT_MERGE_RULE_REGISTRY = MergeRuleRegistry(
    rules={
        "sum": MergeRuleSpec(
            rule_id="sum",
            kind=MergeRuleKind.SUM,
            commutativity=True,
            associativity=True,
            idempotency=False,
            conflict_resolution=ConflictResolution.AGGREGATE,
        ),
        "override": MergeRuleSpec(
            rule_id="override",
            kind=MergeRuleKind.OVERRIDE,
            commutativity=False,
            associativity=False,
            idempotency=True,
            conflict_resolution=ConflictResolution.LAST,
        ),
    }
)
```

### 6. Типизированные значения (`values.py`)

#### Строго типизированные значения

```python
from polisyos.ir.kernel import MoneyValue, RateValue, CountValue, DurationValue

# Денежная величина с валютой и годом
salary = MoneyValue(amount=50000.0, currency="UAH", nominal_year=2024)

# Процентная ставка
tax_rate = RateValue.ratio(0.15)  # 15%

# Количество
employees = CountValue(value=100)

# Продолжительность
duration = DurationValue(value=12, unit="month")
```

### 7. Политики доверия (`trust.py`)

#### TrustRegistry

Уровни доверия к источникам данных:

```python
from polisyos.ir.kernel import TrustRegistry, TrustPolicySpec, TrustLevel

class TrustLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TrustPolicySpec(KernelModel):
    policy_id: str
    level: TrustLevel
    sources: list[str] = []
    validation_rules: list[str] = []
    description: str | None = None
```

### 8. Ограничения (`constraints.py`)

#### ConstraintRegistry

Ограничения на применение политик, обеспечивающие корректность и безопасность симуляций:

```python
from polisyos.ir.kernel import ConstraintRegistry, ConstraintSpec

class ConstraintSpec(KernelModel):
    constraint_id: str
    unit_id: str | None = None
    slot_id: str | None = None
    operator: Literal["<", "<=", ">", ">=", "==", "!="] | None = None
    value: Any = None
    description: str | None = None
    constraint_type: Literal["accounting", "non_negative", "budget", "legal", "physical"] | None = None
    enforcement_level: Literal["hard", "soft", "warning"] = "hard"
    repair_strategy: str | None = None
```

**Типы ограничений:**
- `accounting`: Бухгалтерские балансы (дебет = кредит)
- `non_negative`: Неотрицательные значения
- `budget`: Бюджетные ограничения
- `legal`: Законодательные ограничения
- `physical`: Физические ограничения

### 9. Метрики оптимизации (`metrics.py`)

#### MetricRegistry

Спецификации метрик для оптимизации политик:

```python
from polisyos.ir.kernel import MetricRegistry, MetricSpec, MetricKind

class MetricKind(str, Enum):
    STOCK = "stock"        # Накопительные метрики
    FLOW = "flow"          # Потоковые метрики
    RATIO = "ratio"        # Относительные метрики
    INDEX = "index"        # Индексные метрики
    COMPOSITE = "composite"  # Составные метрики

class MetricSpec(KernelModel):
    metric_id: str
    name: str
    kind: MetricKind
    unit_id: str | None = None
    description: str | None = None
    aggregation_method: Literal["sum", "mean", "median", "last"] = "mean"
    normalization: Literal["none", "zscore", "minmax", "robust"] | None = None
    direction_preference: Literal["higher_better", "lower_better", "target_range"] | None = None
```

### 10. Поля селекторов (`selector_fields.py`)

#### SelectorFieldRegistry

Определения полей для фильтрации сущностей в селекторах политик:

```python
from polisyos.ir.kernel import SelectorFieldRegistry, SelectorFieldSpec, FieldValueType

class FieldValueType(str, Enum):
    NUMBER = "number"
    STRING = "string"
    BOOLEAN = "boolean"
    ENUM = "enum"
    DATE = "date"

class SelectorFieldSpec(KernelModel):
    field_id: str
    slot_id: str
    value_type: FieldValueType
    unit_id: str | None = None
    allowed_values: list[str] | None = None
    range_min: Any = None
    range_max: Any = None
    description: str | None = None
    searchable: bool = True
```

### 11. Политики доверия (`trust.py`)

#### TrustRegistry

Уровни доверия к источникам данных для семантической сети фактов:

```python
from polisyos.ir.kernel import TrustRegistry, TrustPolicySpec, TrustLevel

class TrustLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTRUSTED = "untrusted"

class TrustPolicySpec(KernelModel):
    policy_id: str
    level: TrustLevel
    sources: list[str] = []
    validation_rules: list[str] = []
    confidence_threshold: float = 0.5
    description: str | None = None
```

## Использование в коде

### Импорт компонентов

```python
# Основные реестры
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_TRUST_REGISTRY,
)

# Типы и модели
from polisyos.ir.kernel import (
    MechanismTypeSpec, SlotSpec, UnitRef,
    MoneyValue, RateValue, CountValue,
    MergeRuleRef, TrustPolicySpec,
    ConstraintSpec, MetricSpec, SelectorFieldSpec,
    DecimalValue, NonNegativeDecimal, PositiveDecimal,
)
```

### Создание кастомных реестров

```python
from polisyos.ir.kernel import MechanismTypeRegistry, MechanismTypeSpec, ParamSpec, ParamType

# Кастомный механизм
custom_mechanism = MechanismTypeSpec(
    mechanism_id="custom_tax",
    params={
        "rate": ParamSpec(
            param_id="rate",
            required=True,
            value_type=ParamType.RATE,
            min_value=Decimal("0"),
            max_value=Decimal("1"),
            trainable=True,
            unit_id="ratio",
            description="Custom tax rate"
        )
    },
    reads_slots=["agents.income"],
    writes_slots=["agents.tax_paid", "government.balance"],
    default_merge={"agents.tax_paid": "sum", "government.balance": "sum"},
    description="Custom tax mechanism"
)

registry = MechanismTypeRegistry(mechanisms={"custom_tax": custom_mechanism})
```

## Архитектурные принципы

### Design Patterns

1. **Registry Pattern**: Централизованное хранение определений всех типов
2. **Type Safety**: Строгая типизация через Pydantic с immutable моделями
3. **Validation**: Автоматическая валидация корректности определений
4. **Versioning**: Версионирование схем для обеспечения совместимости
5. **Composition**: Композиция сложных типов из простых примитивов

### Безопасность

- **Immutable Models**: Все модели неизменяемы после создания
- **Forbidden Extra Fields**: Запрещены дополнительные поля в моделях
- **Float Rejection**: Запрещено использование float, только Decimal/int/str
- **Pattern Validation**: Строгие паттерны для идентификаторов

### Расширяемость

Kernel спроектирован для легкого расширения:
- Новые типы единиц добавляются через наследование от `UnitSpec`
- Новые правила слияния добавляются в `MergeRuleKind`
- Новые типы параметров добавляются в `ParamType`
- Новые реестры следуют единому паттерну `Registry` классов

## Тестирование

Kernel включает comprehensive тестирование:

```bash
# Unit-тесты отдельных компонентов
pytest tests/unit/test_ir_kernel_*.py

# Contract-тесты реестров
pytest tests/contract/test_ir_kernel.py
```

**Ключевые тестовые сценарии:**
- Валидация всех predefined реестров
- Type safety проверка
- Immutable models тестирование
- Pattern validation для ID
- Registry consistency проверки

## Связанные компоненты

### Зависимости

Kernel является фундаментом и не зависит от других модулей IR. Он используется:

- **Linker**: Для валидации политик относительно реестров
- **Surface**: Для типизации компонентов политик
- **Foundry**: Для компиляции механизмов
- **Calibration**: Для оптимизации параметров

### Архитектурные контракты

```
Kernel (реестры) ← Linker ← Surface (PolicySurfaceIR)
       ↓
   Foundry (компиляция)    Calibration (оптимизация)
```

---

**См. также:**
- [IR README](../../../../ir/README.md) - общая архитектура IR
- [Linker](../linker.py) - использование kernel-реестров
- [Surface](../surface.py) - интеграция с kernel-типами
