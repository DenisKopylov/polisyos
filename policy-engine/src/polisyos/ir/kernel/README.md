# ir.kernel — Фундаментальные реестры и типы

Kernel — нижний слой IR, определяющий систему типов, реестры компонентов и валидационные примитивы. Kernel не зависит от остальных модулей IR; все остальные модули строятся поверх него.

13 Python-файлов, ~100 экспортируемых символов.

## Архитектурная роль

```
             kernel (реестры + типы)
            ╱       │       ╲
     problem_frame  policy_spec  model_spec   ← Trinity-контракты
           │            │           │
         linker (валидация vs kernel)
           │
       foundry (компиляция)
```

Kernel обеспечивает:
- **Type safety** — `KernelModel` (Pydantic, `frozen=True`, `extra="forbid"`), запрет `float`
- **Registry pattern** — единообразные реестры для всех типов сущностей с default-инстансами
- **Валидация** — ID-паттерны, диапазоны, уникальность ключей

## Структура

```
kernel/
├── __init__.py            # Реэкспорт всех публичных символов
├── base.py                # KernelModel, ID_PATTERN, reject_float()
├── numbers.py             # DecimalValue, NonNegativeDecimal, PositiveDecimal
├── values.py              # MoneyValue, RateValue, CountValue, DurationValue, ParamValue
├── time_semantics.py      # TimeSemantics — конфигурация шагов и дат
├── units.py               # UnitsRegistry: MoneyUnit, RateUnit, DurationUnit, CountUnit, ...
├── mechanisms.py          # MechanismTypeRegistry: MechanismTypeSpec, ParamSpec, ParamType
├── slots.py               # SlotRegistry: SlotSpec, SlotKind, SlotScope, SlotValueType
├── merge_rules.py         # MergeRuleRegistry: MergeRuleSpec, MergeRuleKind, ConflictResolution
├── constraints.py         # ConstraintRegistry: ConstraintSpec
├── metrics.py             # MetricRegistry: MetricSpec, MetricKind
├── selector_fields.py     # SelectorFieldRegistry: SelectorFieldSpec, FieldValueType
└── trust.py               # TrustRegistry: TrustPolicySpec, TrustLevel
```

## Base: KernelModel и валидация

`base.py` определяет базовый класс всех kernel-моделей:

```python
class KernelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
```

ID-паттерны:
- `ID_PATTERN` = `^[a-z][a-z0-9_.-]*$` — общий идентификатор
- `SLOT_ID_PATTERN` = `^[a-z][a-z0-9_.]*$` — слоты (без дефисов)
- `ARTIFACT_ID_PATTERN` = `^sha256:[0-9a-f]{64}$` — content-addressed артефакты

`reject_float(value)` / `reject_floats_deep(value)` — валидаторы, запрещающие `float` в пользу `Decimal`/`int`/`str`.

## Типизированные значения

### Числовые типы (`numbers.py`)

Обёртки над `Decimal` с reject_float валидатором:
- `DecimalValue` — `Annotated[Decimal, BeforeValidator(reject_float)]`
- `NonNegativeDecimal` — то же + `ge=0`
- `PositiveDecimal` — то же + `gt=0`

### Составные значения (`values.py`)

| Тип | Поля | Пример |
|---|---|---|
| `MoneyValue` | `amount`, `currency`, `nominal_year` | `MoneyValue(amount=Decimal("50000"), currency="UAH")` |
| `RateValue` | `value`, `base` (ratio / percent) | `RateValue.ratio(Decimal("0.15"))`, метод `as_ratio()` |
| `CountValue` | `value`, `label` | `CountValue(value=100, label="employees")` |
| `DurationValue` | `value`, `unit` | `DurationValue(value=12, unit="month")` |

`ParamValue` — union всех вышеперечисленных + `Decimal | int | str | bool`.

### TimeSemantics (`time_semantics.py`)

Конфигурация временных шагов: `step_unit`, `steps_per_period`, `origin_date`. Утилиты: `date_for_step()` — расчёт календарной даты по номеру шага.

## Реестры

Каждый реестр — `KernelModel` с `dict[str, Spec]`, `schema_version` и default-инстансом `DEFAULT_*_REGISTRY`.

### MechanismTypeRegistry (`mechanisms.py`)

Типы механизмов интервенций. `MechanismTypeSpec`: `mechanism_id`, `params: dict[str, ParamSpec]`, `reads_slots`, `writes_slots`, `default_merge`.

`ParamSpec`: `param_id`, `value_type` (enum `ParamType`: decimal / int / bool / string / money / rate / count / duration / enum / object / array), `min_value`, `max_value`, `trainable` (для калибровки), `unit_id`.

Predefined: `tax_subsidy`, `income_tax`, `adaptive_agent` и др.

### SlotRegistry (`slots.py`)

Слоты состояния сущностей. `SlotSpec`:
- `scope`: global / per_agent / per_firm / per_entity
- `value_type`: bool / int / decimal / string
- `kind`: stock (carry) / flow (reset) / parameter
- `merge_rule`: обязательный `MergeRuleRef` — явное разрешение конфликтов
- `reset_rule`: carry / zero
- `merge_override`: slot-specific переопределение merge
- Опционально: `conservation_group_id`, `dtype`, `shape`, `axes`, `resample_rule`

Predefined: `agents.income` (flow, per_agent, sum), `agents.reported_income`, `government.balance` (stock, global, sum), `global.tax_rate` (parameter, global, override), `agents.employer_id`, `agents.is_employed`, `agents.skill_level`, `agents.risk_aversion`, `firms.labor_count`, `firms.wage_offer`.

### UnitsRegistry (`units.py`)

`UnitKind`: money / rate / count / duration / dimensionless / generic. Типы единиц:
- `MoneyUnit` — `currency`, `nominal_year`, `price_base`
- `RateUnit` — `base`: ratio / percent
- `DurationUnit`, `CountUnit`, `DimensionlessUnit`, `GenericUnit`

### MergeRuleRegistry (`merge_rules.py`)

Разрешение конфликтов при наложении интервенций. `MergeRuleKind`: sum / override / priority / error. Каждое правило: `commutativity`, `associativity`, `idempotency`, `conflict_resolution` (aggregate / last / ...).

Predefined: `sum` (коммутативное, ассоциативное), `override` (idempotent, last wins).

### ConstraintRegistry (`constraints.py`)

Ограничения: `constraint_type` (accounting / non_negative / budget / legal / physical), `enforcement_level` (hard / soft / warning), `operator`, `repair_strategy`.

### MetricRegistry (`metrics.py`)

Метрики оптимизации: `kind` (stock / flow / ratio / index / composite), `aggregation_method` (sum / mean / median / last), `normalization` (zscore / minmax / robust), `direction_preference` (higher_better / lower_better / target_range).

### SelectorFieldRegistry (`selector_fields.py`)

Поля для `SelectorExpr`: `field_id` → `slot_id`, `value_type` (number / string / boolean / enum / date), `allowed_values`, `range_min`/`range_max`, `searchable`.

### TrustRegistry (`trust.py`)

Политики доверия: `level` (high / medium / low), `sources`, `validation_rules`.

## Использование

```python
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    MechanismTypeSpec, ParamSpec, ParamType,
    MoneyValue, RateValue, DecimalValue,
)

# Проверка существования механизма
assert "income_tax" in DEFAULT_MECHANISM_REGISTRY.mechanisms

# Кастомный механизм
custom = MechanismTypeSpec(
    mechanism_id="carbon_tax",
    params={"rate": ParamSpec(param_id="rate", required=True, value_type=ParamType.RATE)},
    reads_slots=["firms.emissions"],
    writes_slots=["firms.tax_paid", "government.balance"],
)
```

## Зависимости

**Kernel ни от чего не зависит** (кроме pydantic). Его используют:
- Все Trinity-контракты (`problem_frame`, `policy_spec`, `model_spec`)
- `linker/` — валидация vs реестров
- `foundry/` — компиляция механизмов
- `packs/` — domain-specific расширения реестров

## Тестирование

```bash
pytest tests/unit/test_ir_kernel_*.py
pytest tests/contract/test_ir_kernel.py
```
