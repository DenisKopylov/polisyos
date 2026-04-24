# ADR-0098: CAS Abstraction Boundary for Runtime Services

## Status

Accepted

## Date

2026-04-12

## Context

Runtime read/write services historically depended on concrete
`FileSystemCAS` details, backend-specific helpers, and filesystem path access.
That made tests brittle, encouraged private-attribute coupling, and blocked
future backend substitution for object stores or async adapters.

At the same time, the CAS itself had accumulated too many responsibilities:
blob persistence, manifest lifecycle, signing/integrity, audit attachment, and
bulk import/export behavior.

## Decision

1. Runtime-facing code depends on a narrow storage boundary centered on the
   `ArtifactStore` service contract rather than on concrete CAS backends.
2. Concrete backends own physical layout, manifest files, signing material, and
   backend-specific persistence details. Runtime routes and services do not rely
   on those internals directly.
3. CAS responsibilities are separated conceptually into:

   - blob storage;
   - manifest lifecycle;
   - signing and integrity verification;
   - bulk import/export;
   - observability and audit attachment.
4. Read-time integrity verification is part of the storage contract, not an
   optional caller responsibility.
5. Runtime lineage, preview, and download paths consume typed metadata and
   backend-neutral service methods. Transitional legacy aliases may exist, but
   they are compatibility shims and not the official contract.
6. Any future async-native CAS implementation must preserve the same storage
   semantics at this boundary.

## Consequences

### Positive

- Runtime can switch between filesystem, cloud, or wrapped async stores without
  route-level rewrites.

- Tests can use focused doubles or fixtures without monkeypatching concrete CAS
  internals.

- Integrity and manifest semantics become reviewable as platform contracts.

### Negative

- Backend-specific optimization surfaces must move behind adapters or explicit
  extension points.

- Transitional compatibility shims add short-term duplication until all callers
  stop depending on legacy backend details.
