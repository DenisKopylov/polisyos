# Kernel (`polisyos.ir.kernel`)

## Purpose

`polisyos.ir.kernel` содержит базовые deterministic contracts и registry surface,
на которых держатся governance, linking и runtime execution. Это самый низкий
уровень IR: здесь фиксируются базовая model discipline, slots, selector fields,
mechanism types, merge rules, units, metrics, constraints и time semantics.

## Where to Start

- [`base.py`](./base.py) — `KernelModel` и общие validation/immutability rules.
- [`slots.py`](./slots.py) — canonical state slots и `DEFAULT_SLOT_REGISTRY`.
- [`selector_fields.py`](./selector_fields.py) — legal targeting fields и `DEFAULT_SELECTOR_FIELD_REGISTRY`.
- [`mechanisms.py`](./mechanisms.py) — registry механизмов и их read/write contracts.
- [`merge_rules.py`](./merge_rules.py) — merge algebra для конкурентных writes.
- [`units.py`](./units.py), [`metrics.py`](./metrics.py), [`constraints.py`](./constraints.py) — базовые registries для domain semantics.
- [`time_semantics.py`](./time_semantics.py) — step-to-date semantics.
- Для составления registry bundle откройте [`../registry_fragments.py`](../registry_fragments.py), для downstream linking — [`../linker/README.md`](../linker/README.md).

## Public entrypoints

| Entrypoint                                                                    | Use when                                                      | Defined in                                                                                   |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `polisyos.ir.kernel.KernelModel`                                              | Нужен базовый immutable IR contract type                      | [`base.py`](./base.py)                                                                       |
| `polisyos.ir.kernel.SlotRegistry`, `DEFAULT_SLOT_REGISTRY`                    | Нужно описать canonical state slots                           | [`slots.py`](./slots.py)                                                                     |
| `polisyos.ir.kernel.SelectorFieldRegistry`, `DEFAULT_SELECTOR_FIELD_REGISTRY` | Нужно описать supported policy targeting fields               | [`selector_fields.py`](./selector_fields.py)                                                 |
| `polisyos.ir.kernel.MechanismTypeRegistry`                                    | Нужен registry механизмов и их parameter/read-write contracts | [`mechanisms.py`](./mechanisms.py)                                                           |
| `polisyos.ir.kernel.MergeRuleRegistry`                                        | Нужна canonical merge semantics                               | [`merge_rules.py`](./merge_rules.py)                                                         |
| `polisyos.ir.kernel.UnitsRegistry`, `MetricRegistry`, `ConstraintRegistry`    | Нужны registry units, metrics и constraints                   | [`units.py`](./units.py), [`metrics.py`](./metrics.py), [`constraints.py`](./constraints.py) |
| `polisyos.ir.kernel.TimeSemantics`                                            | Нужно сопоставить runtime steps с calendar semantics          | [`time_semantics.py`](./time_semantics.py)                                                   |

## Depends on / depended on by

- Depends on: базовый canonical/pydantic stack внутри `polisyos.ir`.
- Depended on by: [`../governance/README.md`](../governance/README.md), [`../linker/README.md`](../linker/README.md), `polisyos.core.registry`, `polisyos.foundry`, `polisyos.fabric`, `polisyos.ir.registry_fragments`.

## Common commands

Run from the repository root (`policy-engine/`).

Smoke-tested on `2026-04-17`.

```bash
uv run python -c "import polisyos.ir.kernel as kernel; from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY, KernelModel; print(len(kernel.__all__), KernelModel.__name__, len(DEFAULT_SLOT_REGISTRY.slots))"
```

## Test/verification commands

Run from the repository root (`policy-engine/`).

Conceptual in this README refresh; run these checks before landing kernel or
schema-generation changes.

```bash
uv run pytest tests/contract/test_trinity_linker_contract.py tests/unit/ir/test_phase2_passes.py -q
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

## Reference docs

- [IR public surface](../../../../docs/reference/ir/public-surface.md)
- [IR schema catalog](../../../../docs/reference/ir/schema-catalog.md)
- [Merge semantics contract](../../../../docs/contracts/MERGE_SEMANTICS.md)
- [Shared schemas reference](../../../../docs/reference/schemas.md)
- [IR root README](../README.md)
- [Linker README](../linker/README.md)

## Last updated

`2026-04-17`
