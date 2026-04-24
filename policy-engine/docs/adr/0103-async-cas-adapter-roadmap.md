# ADR-0103: Async CAS Adapter Roadmap

## Status

Accepted

## Date

2026-04-12

## Context

Runtime hot paths use storage operations that are still primarily synchronous:
filesystem access, manifest reads, cloud SDK calls, and integrity verification.
Moving directly to an async-native storage stack would increase migration risk
unless the boundary, metrics, and failure semantics are fixed first.

WS-2A and WS-2B introduced a shared-executor direction and backend-neutral
runtime storage boundary. This ADR defines the staged roadmap.

## Decision

1. Async CAS adoption is staged:

   - adapter phase;
   - shared-executor phase;
   - selective async-native backend phase;
   - acceptance phase backed by benchmarks and corruption tests.
2. The public storage contract remains stable across phases:

   - immutable manifest creation;
   - read-time integrity verification;
   - typed integrity failures;
   - bounded resource usage.
3. Runtime services use guarded adapters with timeout and circuit-breaker
   behavior before any async-native rewrite becomes default.
4. Selective rewrites are justified only by measured hot paths such as CAS
   `put/get`, timeline/index refresh, and lineage traversal.
5. The roadmap itself is operator-facing documentation and must stay aligned
   with actual implementation posture.

## Consequences

### Positive

- Storage evolution can continue without destabilizing runtime contracts.
- Performance work remains benchmark-driven rather than speculative.
- The system avoids the anti-pattern of `new ThreadPoolExecutor per call` while
  preserving a future async path.

### Negative

- There will be an interim period where sync backends still exist behind async
  guards and shared executors.

- The roadmap creates a documentation maintenance burden because operators will
  rely on it during rollout planning.
