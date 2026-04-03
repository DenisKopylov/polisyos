# Kernel (`polisyos.ir.kernel`)

`polisyos.ir.kernel` содержит базовые типы, registry contracts и deterministic
semantics, на которых держатся governance, linking и runtime execution. Это
наиболее низкоуровневый слой IR: здесь фиксируются value types, units,
mechanism/slot registries, merge rules, trust policies и selector fields.

## Роль в системе

- **Зависит от:** базовый canonical/pydantic stack внутри `polisyos.ir`
- **Используется в:** `polisyos.ir.governance`, `polisyos.ir.linker`, `polisyos.ir.registry_fragments`, `polisyos.foundry`, `polisyos.core.registry`
- Kernel описывает domain-neutral contracts, через которые runtime и компиляторы договариваются о state layout и merge semantics.

## Ключевые концепции

- **KernelModel** — frozen, extra-forbid base class для deterministic contracts.
- **Slot registry** — `SlotRegistry` задает canonical state slots и merge rules.
- **Selector fields** — `SelectorFieldRegistry` описывает legal/policy targeting surface.
- **Mechanism registry** — `MechanismTypeRegistry` фиксирует параметры и read/write slots механизмов.
- **Merge algebra** — `MergeRuleRegistry` устраняет order-dependent behavior при конкурентных writes.
- **Cell-aware runtime surface** — новые `PER_CELL` slots и selector fields расширяют IR под cell/household-cell state.

## Public API

| Type/Function | Description |
|---|---|
| `KernelModel` | Базовый класс для immutable IR contracts |
| `SlotRegistry`, `SlotSpec`, `DEFAULT_SLOT_REGISTRY` | Canonical state slot definitions |
| `SelectorFieldRegistry`, `SelectorFieldSpec`, `DEFAULT_SELECTOR_FIELD_REGISTRY` | Policy targeting fields и их scope/state paths |
| `MechanismTypeRegistry`, `MechanismTypeSpec` | Реестр механизмов и их параметров |
| `MergeRuleRegistry`, `MergeRuleSpec` | Merge semantics для concurrent writes |
| `UnitsRegistry`, `MetricRegistry`, `ConstraintRegistry` | Units, metrics и constraints registries |
| `TimeSemantics` | Step-to-date semantics для monthly/quarterly/yearly timelines |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 14 Python files
- Exports: 52 public names in `__init__.py`
- Recent delta: `slots.py` теперь содержит 30 literal slot specs, а `selector_fields.py` — 12 predefined fields, включая `PER_CELL`, `household_cell_id`, `firm_cell_id`, `region_code` и `sector_id`
