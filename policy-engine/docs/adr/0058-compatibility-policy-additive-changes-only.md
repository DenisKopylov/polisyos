# ADR-0058: Only additive schema changes (1.0 to 1.1), dual-read migration

## Status
Proposed

## Date
2026-02-28

## Context
The IR layer serialises causal models, governance reports, and decision packets
into versioned JSON schemas. Breaking schema changes force coordinated upgrades
across the scientist, fabric, and lex subsystems simultaneously. Past incidents
showed that removing or renaming fields caused silent data loss when older
consumers read newer payloads. A compatibility policy is needed to keep the
system evolvable without multi-module lockstep deployments.

## Decision
1. All schema changes within a minor version (e.g., 1.0 to 1.1) must be purely
   additive: new optional fields only, no removals or renames.
2. Consumers must implement dual-read: accept both the current and the
   immediately preceding minor schema version.
3. Field deprecations are announced one minor version before removal and
   enforced via `gen_schema.py` snapshot diffing in CI.
4. Major version bumps (e.g., 1.x to 2.0) are permitted only when accompanied
   by a migration script and a documented cutover plan.

## Consequences
### Positive
- Producers and consumers can be upgraded independently within the same minor
  version window, reducing deployment coordination overhead.
- Dual-read guarantees that in-flight payloads are never silently dropped during
  rolling upgrades.

### Negative
- Additive-only changes accumulate deprecated fields over time, increasing
  schema size and cognitive load on new contributors.
- Dual-read logic in every consumer adds implementation and testing cost per
  schema evolution cycle.
