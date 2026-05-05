# Merge Semantics Specification

## Overview

This document specifies the formal merge semantics for Policy OS state updates.
The merge system provides CRDT-inspired guarantees for deterministic execution.

## Core Principles

1. Explicit over implicit: every slot must declare its merge rule.
2. Deterministic: same inputs always produce same outputs, regardless of order.
3. Traceable: conflicts are never silently swallowed.
4. JAX-compatible: merge operations can be differentiated for calibration.

## Merge Rules

### SUM (Commutative + Associative)

Use for accumulating quantities (balances, totals, flows).

```text
merge(delta_1, delta_2) = delta_1 + delta_2
final_value = base + merge(all_deltas)
```

Properties:

- Commutative: delta_1 + delta_2 = delta_2 + delta_1
- Associative: (delta_1 + delta_2) + delta_3 = delta_1 + (delta_2 + delta_3)
- Idempotent: no, delta + delta = 2 \* delta

Constraints: numeric types only (int, decimal, array)

### OVERRIDE (Last-Write-Wins)

Use for status flags, parameters, singleton values.

```text
merge(v1, v2) = v2 if timestamp(v2) > timestamp(v1)
             = v1 if timestamp(v1) > timestamp(v2)
             = tiebreak_by_node_id(v1, v2) otherwise
```

Properties:

- Commutative: no (order matters without timestamps)
- Associative: no
- Idempotent: yes, merge(v, v) = v

### PRIORITY (Highest Priority Wins)

Use for competing mechanisms with explicit precedence.

```text
merge(v1, v2) = v1 if priority(v1) > priority(v2)
             = v2 if priority(v2) > priority(v1)
             = tiebreak_by_node_id(v1, v2) if priority(v1) = priority(v2)
```

Properties:

- Commutative: yes
- Associative: yes
- Idempotent: yes

### ERROR (Explicit Conflict Detection)

Use for slots with single ownership, safety-critical values.

```text
merge(v1, v2) = raise MergeConflict if |writers| > 1
             = v1 if |writers| = 1
```

Properties:

- Commutative: yes (conflict is symmetric)
- Associative: yes (conflict propagates)
- Idempotent: yes

## Migration Guide

### From Implicit to Explicit Merge Rules

Before (dangerous):

```python
state["balance"] = mechanism_a_output
state["balance"] = mechanism_b_output  # Overwrites silently
```

After (safe):

```python
records = [
    MergeRecord(node_id="mechanism_a", delta=100.0),
    MergeRecord(node_id="mechanism_b", delta=-50.0),
]
report = engine.merge_records(records, base_values={"balance": 1000.0})
# result: 1050.0 (regardless of order)
```

## Error Handling

All conflicts produce MergeConflict objects with:

- slot_id: which slot had the conflict
- kind: classification (MULTIPLE_WRITERS, TYPE_MISMATCH, etc.)
- writers: node IDs responsible
- message: human-readable description

## Performance Considerations

- Python path: use MergeEngine for IO-bound operations.
- JAX path: use JAXMergeEngine for JIT-compiled simulations.
- Vectorization: SUM and PRIORITY support batch operations.

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Source plan phase   | D1-L4 Phase 0 registry/linker conflict containment and Phase 3 algebra/property verification                                   |
| Contract tests      | `tests/contract/test_kernel_models.py`, `tests/contract/test_trinity_linker_contract.py`, `tests/unit/ir/test_phase3_properties.py` |
| Schema snapshots    | `schemas/snapshots/ir/policy_spec.schema.json`, `schemas/snapshots/ir/trinity_bundle.schema.json`                              |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                         |
