# ADR-RSR-0140: Pickle and Checkpoint Compatibility Safety Net

## Status

Accepted

## Date

2026-05-03

## Context

Scientist and Foundry decomposition can change module FQNs. Python pickle,
checkpoint payloads, and framework serializers can embed those FQNs and fail to
load after a source move.

## Decision

1. Phase 3A inventories pickle/checkpoint call sites in `src/` and `tools/`.
2. Phase 3A inventories live `*.pkl`, `*.pickle`, `*.joblib`, and `*.ckpt`
   artifacts under `.polisyos/` and `tests/_data/`.
3. Canonical compatibility fixtures live under
   `tests/_data/checkpoint_compat/`.
4. `tests/contract/test_pickle_compat.py` is part of the normal pytest suite
   and must load every committed compatibility fixture.
5. Phase 5/6 module moves must keep old FQNs loadable through targeted
   re-export shims until the sunset window in the decomposition blueprint
   expires.

## Consequences

Checkpoint compatibility becomes a committed contract. A decomposition PR that
breaks a historical pickle fixture fails before merge.

## Related Decisions

- ADR-RSR-0143 Decomposition Blueprint Contract.
- ADR-RSR-0144 JAX/Pydantic Registrations and Re-export Shim Shape.
