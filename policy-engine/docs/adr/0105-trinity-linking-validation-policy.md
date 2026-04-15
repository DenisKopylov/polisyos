# ADR-0105: Trinity Linking, Dependency Ordering, and Validation Containment

Status: accepted

Date: 2026-04-12

## Context

Trinity bundle assembly previously mixed dependency validation, fragment
application, linker diagnostics, and best-effort analytics normalization in ways
that were hard to reason about. Missing dependencies could still influence the
merged registry state, fragment order depended on lexicographic coincidence
instead of dependency structure, unknown mechanisms could suppress later
diagnostics, and malformed analytics payloads could collapse into `None`, empty
fallbacks, or partially normalized objects.

These behaviors made repeated runs less diagnosable and weakened the ABI around
registry composition, schedule conflict checks, param traversal, and degraded
analytics outcomes.

## Decision

Registry fragment composition is a two-phase process:

1. Validate fragment dependencies and classify failures before any payload is
   applied.
2. Apply only dependency-closed fragments in deterministic topological order.

Fragments with unresolved, missing, or cyclic dependencies never enter
`applied_fragments` and never mutate the composed registry bundle. Dependency
failures are surfaced as explicit conflict kinds:
`dependency_missing`, `dependency_unresolved`, and `dependency_cycle`.

Topological order is the linker/composer ordering contract. Lexicographic order
is used only as a deterministic tie-breaker among otherwise independent nodes.
Dependency cycles are detected explicitly and reported for all fragments in the
cycle.

Trinity linker diagnostics are fail-complete rather than fail-fast for local
validation phases. Unknown mechanisms remain errors, but the linker still:

- validates selector fields,
- records schedule/conflict accounting,
- preserves linked intervention entries with empty slot bindings,
- emits unused-registry diagnostics in the same pass.

Warning and note accumulation use ordered-set semantics so repeated runs emit the
same diagnostic sequence without duplicated messages from repeated membership
checks.

Schedule overlap uses inclusive interval semantics: Trinity schedules are
interpreted as `[start, end]`. Conflict checks, boundary tests, and reference
documentation must use the same convention.

Parameter traversal reserves `.` as path syntax between nested object fields.
Raw parameter field names containing `.` are invalid. Parameter traversal depth
is capped at `16` to bound recursion and diagnostic path growth.

Validation containment in IR analytics, observation loading, migrations, and
portfolio interaction modes follows this rule:

- malformed required input raises an explicit validation/domain error, or
- optional/external-adapter failure degrades with structured warning/error
  telemetry and preserved provenance.

`assert` is not part of runtime validation semantics. Production and
`python -O` must behave the same on validation paths.

## Consequences

Trinity composition is deterministic across input order permutations that
preserve the same dependency graph. Invalid fragments no longer contaminate the
merged registry state. Link reports accumulate the full deterministic diagnostic
set for missing dependencies, cycles, unknown mechanisms, unused registry items,
and schedule conflicts in one pass.

Analytics and observation pipelines now distinguish malformed payloads from
absent payloads, making degraded outcomes inspectable in telemetry and contract
tests rather than silently normalizing them away.
