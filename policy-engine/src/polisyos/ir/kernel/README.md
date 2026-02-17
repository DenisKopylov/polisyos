# ir.kernel

`ir.kernel` — нижний слой контрактов `polisyos.ir`: базовые типы значений и реестры, на которых держатся governance/model/linking.

## Роль в архитектуре

```text
kernel (types + registries)
   │
   ├─► ir.governance / ir.model_spec
   ├─► ir.linker
   ├─► foundry execution
   └─► core registry builders
```

Контекст верхнего уровня: [`../README.md`](../README.md)

## Состав

| Файл | Что содержит |
|---|---|
| `base.py` | `KernelModel`, ID-паттерны, float guards |
| `numbers.py`, `values.py` | `DecimalValue`, `MoneyValue`, `RateValue`, `CountValue`, `DurationValue`, `ParamValue` |
| `units.py` | `UnitsRegistry`, `UnitSpec*`, `DEFAULT_UNITS_REGISTRY` |
| `merge_rules.py` | `MergeRuleRegistry` (schema `2.0`) и формальная merge-алгебра |
| `slots.py` | `SlotRegistry`, `SlotSpec`, обязательный `merge_rule` |
| `mechanisms.py` | `MechanismTypeRegistry`, `ParamSpec`, `resolve_mechanism_slots()` |
| `constraints.py` | `ConstraintRegistry` |
| `metrics.py` | `MetricRegistry` |
| `selector_fields.py` | `SelectorFieldRegistry` |
| `trust.py` | `TrustRegistry` |
| `time_semantics.py` | `TimeSemantics` и `date_for_step()` |

## Ключевые инварианты

- `KernelModel`: `extra="forbid"`, `frozen=True`.
- В контрактах, где нужна детерминированность, `float` блокируется через `reject_float`/`reject_floats_deep`.
- `SlotSpec.merge_rule` обязателен, чтобы исключить неявную order-dependent merge-логику.
- `MergeRuleSpec` проверяет согласованность algebra properties с `kind` (`sum/override/priority/error`).
- Для `adaptive_agent` читаемые/записываемые слоты вычисляются динамически из `observation_space` и `action_space`.

## Версии схем

- Большинство kernel-реестров: `schema_version="1.0"`.
- `MergeRuleRegistry`: `schema_version="2.0"`.

## Связь с другими подсистемами

| Директория | Использование |
|---|---|
| `ir/governance`, `ir/model_spec.py` | value types, ID и временная семантика |
| `ir/linker` | проверка mechanisms/slots/units/metrics/constraints/selector_fields |
| `core/registry` | сборка и загрузка bundle-ов реестров |
| `foundry/` | execution semantics по slot/mechanism/merge |
| `packs/` | доменные расширения реестров через fragments |

## Минимальный пример

```python
from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY, DEFAULT_SLOT_REGISTRY

assert "income_tax" in DEFAULT_MECHANISM_REGISTRY.mechanisms
assert "agents.income" in DEFAULT_SLOT_REGISTRY.slots
```

## Проверки

```bash
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_kernel_models.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/ir/test_registry_fragments.py
pytest /Users/deniskopylov/polisyos/policy-engine/tests/contract/test_trinity_linker_contract.py
```
