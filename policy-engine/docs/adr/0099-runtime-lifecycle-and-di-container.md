# ADR-0099: Runtime Lifecycle and Dependency-Injection Container

## Status

Accepted

## Date

2026-04-12

## Context

The runtime app previously assembled services by mutating `app.state` directly
at creation time. Startup/shutdown behavior, test overrides, and health status
were implicit, and import-time side effects in bootstrap code made backend
substitution difficult.

WS-2C introduced a typed runtime container and explicit bootstrap flow. This
decision records that model as the supported lifecycle contract.

## Decision

1. Runtime services are assembled through a typed container that owns:

   - dependency graph construction;
   - startup ordering;
   - shutdown ordering;
   - lifecycle state;
   - health/dependency snapshots;
   - test override points.
2. Process bootstrap and logging initialization are explicit entrypoint steps,
   not side effects of importing `common.config` or route modules.
3. `app.state` may still expose legacy aliases for compatibility, but the
   container is the source of truth for runtime-owned services.
4. Health endpoints expose container lifecycle state and dependency status so
   operators can distinguish `created`, `starting`, `ready`, `stopping`,
   `stopped`, and `failed`.
5. New runtime services must register through the container or a provider
   factory rather than as new import-time singletons.
6. Tests override services by passing container overrides, not by monkeypatching
   global registries.

## Consequences

### Positive

- Runtime startup and shutdown become deterministic and inspectable.
- Service replacement for tests or alternate embeddings is explicit.
- Import-time behavior becomes safer and easier to reason about.

### Negative

- There is a temporary hybrid period where container-managed services are also
  mirrored into legacy `app.state` fields.

- Engineers must update the container when adding new runtime-owned services,
  which makes drift visible but adds process discipline.
