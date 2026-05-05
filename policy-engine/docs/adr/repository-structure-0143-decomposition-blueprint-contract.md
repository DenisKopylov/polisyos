# ADR-RSR-0143: Decomposition Blueprint Contract

## Status

Accepted

## Date

2026-05-03

## Context

Scientist and Foundry are large packages with root-level modules that need
decomposition. Before any physical moves, owners need an exhaustive move map,
external importer inventory, shim plan, schema impact analysis, registration
audit, and rollback-friendly gates.

## Decision

1. `docs/plans/active/DECOMPOSITION_BLUEPRINT.md` is the Phase 3A plan-first
   artifact.
2. Phase 5 and Phase 6 may not start until the blueprint exists and all Phase 3A
   gates are green.
3. The blueprint records source FQN, target FQN, public/internal type,
   reasoning, external importers, planned shims, Pydantic schema exposure, and
   top-level registrations.
4. Phase 3A moves zero `.py` files in `src/polisyos/scientist/` or
   `src/polisyos/foundry/`.

## Consequences

The decomposition is reviewed as a contract before it becomes a source move.
Any later drift must update the blueprint and baselines explicitly.

## Related Decisions

- ADR-RSR-0140 Pickle and Checkpoint Compatibility Safety Net.
- ADR-RSR-0141 Dynamic Import Registry.
- ADR-RSR-0145 Import Cycle Baseline.
