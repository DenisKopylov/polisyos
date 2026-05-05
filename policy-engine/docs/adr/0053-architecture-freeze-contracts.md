# ADR-0053: Architecture Freeze at Assembly Points

## Status

Proposed

## Date

2026-02-28

## Context

The policy engine architecture defines assembly point contracts: IR schemas, import gates
(enforced by `architecture/imports/policy.toml`), and foundry purity invariants. If these contracts change
during feature implementation, downstream modules built against the old contracts silently
break or produce incorrect results. A freeze discipline is needed to ensure stability during
implementation phases.

## Decision

1. All assembly point contracts (IR Pydantic schemas, import gate rules, foundry purity
   checks) must be locked before Phase 0 implementation begins.
2. "Locked" means: schema fields may not be removed or have their types changed; new optional
   fields may be added but must have defaults; import gates may not be relaxed.
3. Contract changes after freeze require a new ADR documenting the change, a migration path,
   and approval from the architecture owner.
4. The `gen_schema.py` tool produces JSON Schema snapshots that serve as the frozen reference;
   any drift between code and snapshot is a CI failure.
5. Freeze applies per-phase: Phase 0 contracts freeze before Phase 0 starts, Phase 9
   contracts freeze before Phase 9 starts, and so on.

## Consequences

### Positive

- Developers can build against stable contracts with confidence that they will not shift.
- Schema snapshot diffing in CI catches accidental contract breakage immediately.
- The ADR requirement for post-freeze changes creates a deliberate, documented change process.

### Negative

- Freeze discipline may slow iteration when a contract flaw is discovered mid-phase; the ADR
  process adds overhead.

- Optional-field-only additions can lead to schema bloat over time if not periodically pruned.
- Strict freeze may be overly rigid for early exploration phases where contracts are still
  being discovered.
