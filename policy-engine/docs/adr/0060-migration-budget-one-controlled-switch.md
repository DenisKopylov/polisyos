# ADR-0060: Migration Budget = 1: single controlled switch, no feature flags

## Status
Proposed

## Date
2026-02-28

## Context
Feature flags provide runtime flexibility but introduce combinatorial testing
complexity and long-lived conditional paths that are easy to forget. Previous
migrations in the policy engine that used feature flags resulted in stale
branches persisting for months and inconsistent behaviour between flag states.
With the introduction of `scientist_causal_full` and new IR schema versions, a
disciplined migration strategy is needed to keep the codebase tractable.

## Decision
1. Adopt a migration budget of exactly one: at any given time, at most one
   subsystem may be undergoing a controlled migration.
2. Migrations use a compile-time constant (not a runtime flag) that selects
   the old or new code path, enforced by a CI lint check.
3. Each migration must include a rollback plan documented in the associated ADR
   or PR description.
4. The migration constant is removed within two release cycles of the cutover
   completing.
5. No runtime feature-flag library is introduced into the policy engine.

## Consequences
### Positive
- A hard limit of one concurrent migration keeps the codebase auditable and
  prevents flag-interaction bugs.
- Compile-time selection makes dead-code elimination straightforward and
  avoids the runtime overhead of flag evaluation.

### Negative
- Teams wanting to migrate multiple subsystems simultaneously must serialize
  their work, potentially slowing velocity.
- Without runtime flags, canary or percentage-based rollouts are not possible;
  rollback requires a new deployment.
