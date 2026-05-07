# ADR-RSR-0146: Foundry Execute/Executor Naming Boundary

## Status

Accepted

## Date

2026-05-05

## Context

Phase 4.1 consolidates Foundry executor internals. The repository already has
`polisyos.foundry.execute` as the canonical package for the public `execute()`
entrypoint, while `polisyos.foundry.executor` exists as an older helper import
surface. Moving private `_executor_*`, `_execution_posture`, and `_numeric`
siblings without a naming decision would leave `execute` and `executor` looking
like equal public roots.

## Decision

1. `polisyos.foundry.execute` remains the canonical public execution package and
   owns executor implementation internals.
2. Private executor implementation lives under
   `polisyos.foundry.execute._internal`.
3. `polisyos.foundry.executor` is a compatibility helper facade only. It
   re-exports targeted helper names from `polisyos.foundry.execute.executor` and
   is not a second canonical root.
4. `polisyos.foundry.runtime.numeric` remains the public numeric guardrail
   import path, but its implementation is owned by
   `polisyos.foundry.execute._internal.numeric`.
5. The removed root-private siblings `_executor_*`, `_execution_posture`, and
   `_numeric` must not be recreated as compatibility packages.

## Consequences

Foundry has one execution owner boundary while preserving public helper imports
that downstream tests and runtime glue still use. New private executor code goes
under `execute._internal`; callers that need the public execution entrypoint use
`polisyos.foundry.execute`, and callers that still need helper utilities use the
explicit compatibility facade.

## Related Decisions

- ADR-RSR-0143 Decomposition Blueprint Contract.
- ADR-RSR-0144 JAX/Pydantic Registrations and Re-export Shim Shape.
- ADR-RSR-0145 Import Cycle Baseline.
