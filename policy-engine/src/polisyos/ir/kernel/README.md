# Kernel (`polisyos.ir.kernel`)

## Purpose

`polisyos.ir.kernel` contains the base deterministic contracts and registry
surface used by governance, linking, and runtime execution. It is the lowest IR
layer: it defines the base model discipline, slots, selector fields, mechanism
types, merge rules, units, metrics, constraints, and time semantics.

## Where to Start

- [`base.py`](./base.py) — `KernelModel` and shared validation/immutability rules.
- [`slots.py`](./slots.py) — canonical state slots and `DEFAULT_SLOT_REGISTRY`.
- [`selector_fields.py`](./selector_fields.py) — legal targeting fields and `DEFAULT_SELECTOR_FIELD_REGISTRY`.
- [`mechanisms.py`](./mechanisms.py) — mechanism registry and its read/write contracts.
- [`merge_rules.py`](./merge_rules.py) — merge algebra for concurrent writes.
- [`units.py`](./units.py), [`metrics.py`](./metrics.py), [`constraints.py`](./constraints.py) — base registries for domain semantics.
- [`time_semantics.py`](./time_semantics.py) — step-to-date semantics.
- To assemble a registry bundle, see [`../registry/registry_fragments.py`](../registry/registry_fragments.py); for downstream linking, see [`../linker/README.md`](../linker/README.md).

## Public entrypoints
`ParamValue` is included in the lazy kernel value facade with the existing count, duration, money, and rate value types.


| Entrypoint                                                                    | Use when                                                          | Defined in                                                                                   |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `polisyos.ir.kernel.KernelModel`                                              | Use the base immutable IR contract type                           | [`base.py`](./base.py)                                                                       |
| `polisyos.ir.kernel.SlotRegistry`, `DEFAULT_SLOT_REGISTRY`                    | Describe canonical state slots                                    | [`slots.py`](./slots.py)                                                                     |
| `polisyos.ir.kernel.SelectorFieldRegistry`, `DEFAULT_SELECTOR_FIELD_REGISTRY` | Describe supported policy targeting fields                        | [`selector_fields.py`](./selector_fields.py)                                                 |
| `polisyos.ir.kernel.MechanismTypeRegistry`                                    | Use the mechanism registry and its parameter/read-write contracts | [`mechanisms.py`](./mechanisms.py)                                                           |
| `polisyos.ir.kernel.MergeRuleRegistry`                                        | Define canonical merge semantics                                  | [`merge_rules.py`](./merge_rules.py)                                                         |
| `polisyos.ir.kernel.UnitsRegistry`, `MetricRegistry`, `ConstraintRegistry`    | Use the registries for units, metrics, and constraints            | [`units.py`](./units.py), [`metrics.py`](./metrics.py), [`constraints.py`](./constraints.py) |
| `polisyos.ir.kernel.TimeSemantics`                                            | Map runtime steps to calendar semantics                           | [`time_semantics.py`](./time_semantics.py)                                                   |

## Depends on / depended on by

- Depends on: the base canonical/Pydantic stack within `polisyos.ir`.
- Depended on by: [`../governance/README.md`](../governance/README.md), [`../linker/README.md`](../linker/README.md), `polisyos.core.registry`, `polisyos.foundry`, `polisyos.fabric`, `polisyos.ir.registry.registry_fragments`.

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

`2026-10-14` (broken registry source link corrected; smoke-test date above is historical and was not rerun)
