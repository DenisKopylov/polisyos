# ir.kernel

`ir.kernel` — базовый слой контрактов `polisyos.ir`: типы значений, семантика времени и registry-модели, на которые опираются governance/model/linking.

## Роль в архитектуре

```text
kernel (types + registries)
   │
   ├─► ir.governance / ir.model_spec
   ├─► ir.registry_fragments
   ├─► ir.linker
   └─► foundry/core runtime
```

Контекст верхнего уровня: [`../README.md`](../README.md)

## Состав

| Файл | Что содержит |
|---|---|
| `base.py` | `KernelModel`, ID patterns, float guards |
| `numbers.py`, `values.py` | `DecimalValue`, `MoneyValue`, `RateValue`, `CountValue`, `DurationValue`, `ParamValue` |
| `units.py` | `UnitsRegistry`, `MoneyUnit/RateUnit/...`, `DEFAULT_UNITS_REGISTRY` |
| `merge_rules.py` | `MergeRuleRegistry` (schema `2.0`), algebra properties, conflict policy |
| `slots.py` | `SlotRegistry`, `SlotSpec`, `SlotValueType`, обязательный `merge_rule` |
| `mechanisms.py` | `MechanismTypeRegistry`, `ParamSpec`, `resolve_mechanism_slots()` |
| `constraints.py` | `ConstraintRegistry` |
| `metrics.py` | `MetricRegistry` |
| `selector_fields.py` | `SelectorFieldRegistry` |
| `trust.py` | `TrustRegistry` (`TrustPolicySpec`) |
| `time_semantics.py` | `TimeSemantics` и `date_for_step()` для `M/Q/Y` частот |

## Ключевые инварианты

- `KernelModel`: `extra="forbid"`, `frozen=True`.
- В детерминированных контрактах `float` блокируется через `reject_float`/`reject_floats_deep`.
- `SlotSpec.merge_rule` обязателен для предотвращения неявной order-dependent merge логики.
- `MergeRuleSpec` проверяет согласованность algebra properties с `kind` (`sum`, `override`, `priority`, `error`).
- `resolve_mechanism_slots()` для `adaptive_agent` динамически выводит read/write slots из `observation_space` и `action_space`.

## Версии схем

- Большинство kernel registry: `schema_version="1.0"`.
- `MergeRuleRegistry`: `schema_version="2.0"`.

## Связь с другими подсистемами

| Директория | Использование |
|---|---|
| `ir/governance`, `ir/model_spec.py` | value types, IDs, time semantics |
| `ir/registry_fragments.py` | композиция registry bundle-ов из fragment-ов |
| `ir/linker` | проверка mechanisms/slots/units/metrics/constraints/selector fields |
| `core/registry` | загрузка и объединение registry-данных |
| `foundry/` | runtime execution semantics по slot/mechanism/merge |
| `packs/` | доменные расширения registry через fragments |

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
