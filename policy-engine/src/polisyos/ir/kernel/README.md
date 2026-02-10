# ir.kernel — Базовые типы и реестры IR

`ir.kernel` — нижний контрактный слой `polisyos.ir`.
Он задаёт систему типов, базовые валидаторы и реестры (`units`, `slots`, `mechanisms`, `merge_rules`, `metrics`, `constraints`, `selector_fields`, `trust`), на которые опираются Trinity-контракты и линкер.

## Роль в архитектуре

```text
kernel (types + registries)
   │
   ├─► governance/* + model_spec.py
   ├─► ir.linker (валидация Trinity against registries)
   ├─► foundry (compile/execute через slot/mechanism semantics)
   └─► core.registry / packs (сборка registry bundles)
```

Подробнее про общий контекст: [`../README.md`](../README.md)

## Состав директории

```text
kernel/
├── base.py             # KernelModel, ID patterns, float guards
├── numbers.py          # Decimal aliases (DecimalValue, NonNegativeDecimal, PositiveDecimal)
├── values.py           # MoneyValue / RateValue / CountValue / DurationValue / ParamValue
├── time_semantics.py   # TimeSemantics + date_for_step()
├── units.py            # UnitSpec types + UnitsRegistry + DEFAULT_UNITS_REGISTRY
├── merge_rules.py      # MergeRuleSpec/Registry (schema v2.0)
├── slots.py            # SlotSpec/SlotRegistry + DEFAULT_SLOT_REGISTRY
├── mechanisms.py       # MechanismTypeSpec/Registry + ParamSpec + resolve_mechanism_slots()
├── constraints.py      # ConstraintSpec/ConstraintRegistry
├── metrics.py          # MetricSpec/MetricRegistry
├── selector_fields.py  # SelectorFieldSpec/Registry
├── trust.py            # TrustPolicySpec/TrustRegistry
└── __init__.py         # публичные re-exports
```

## Ключевые контракты

### Base

- `KernelModel`: `frozen=True`, `extra="forbid"`.
- `ID_PATTERN`, `SLOT_ID_PATTERN`, `ARTIFACT_ID_PATTERN`.
- `reject_float()` и `reject_floats_deep()` для запрета `float` в контрактах, где нужен детерминизм.

### Типизированные значения

- `DecimalValue`, `NonNegativeDecimal`, `PositiveDecimal` (`numbers.py`).
- `MoneyValue` (`amount`, `currency`, `nominal_year`).
- `RateValue` (`ratio|percent`) с проверкой диапазона и `as_ratio()`.
- `CountValue`, `DurationValue`.
- `ParamValue` — глубокая float-защита для параметров механизмов.

### Реестры

- `UnitsRegistry`: `UnitKind` (`money`, `rate`, `count`, `duration`, `dimensionless`, `generic`).
- `MechanismTypeRegistry`: `MechanismTypeSpec` + `ParamSpec` (`ParamType`), чтение/запись слотов.
- `SlotRegistry`: явная merge-семантика на каждом слоте через обязательный `merge_rule`.
- `MergeRuleRegistry` (schema `2.0`): формальные свойства (коммутативность, ассоциативность, идемпотентность).
- `ConstraintRegistry`: типизированные ограничения (`slot_id`, `unit_id`, `operator` и т.д.).
- `MetricRegistry`: описания метрик.
- `SelectorFieldRegistry`: поля для `SelectorExpr` с scope/state_path.
- `TrustRegistry`: политики доверия/порогов.

## Важные особенности

- Явный merge-контракт:
  у `SlotSpec` `merge_rule` обязателен, чтобы избежать неявного order-dependent поведения.
- Алгебра merge-правил:
  `MergeRuleSpec` валидирует согласованность `kind` с algebraic properties.
- Специальный путь `adaptive_agent`:
  `resolve_mechanism_slots()` вычисляет `reads_slots`/`writes_slots` динамически из `observation_space` и `action_space`.
- Temporal mapping:
  `TimeSemantics.date_for_step()` переводит simulation step в календарную дату (`M/Q/Y`).

## Связи с другими директориями

| Директория | Как использует `ir.kernel` |
|---|---|
| `ir/governance`, `ir/model_spec.py` | базовые типы значений и ID-паттерны |
| `ir/linker` | валидация Trinity против registry bundle |
| `foundry/` | слоты, merge rules, mechanisms, unit-aware параметры |
| `core/registry` | загрузка/сборка bundle-ов реестров |
| `fabric/`, `lex/`, `scientist/` | точечные типы и validators (ID/float guards и др.) |
| `packs/` | расширение доменных реестров через fragments |

## Минимальный пример использования

```python
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY

assert "income_tax" in DEFAULT_MECHANISM_REGISTRY.mechanisms
assert "agents.income" in DEFAULT_SLOT_REGISTRY.slots
```

## Рекомендуемые проверки

```bash
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_kernel_models.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/ir/test_registry_fragments.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_trinity_linker_contract.py
```
