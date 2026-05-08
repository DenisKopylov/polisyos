# ADR-RSR-0148: Cross-Cutting Concern Canonical Homes

## Status

Accepted

## Date

2026-05-07

## Context

The last-mile repository review found repeated concern names such as
`observability`, `security`, `registry`, `discovery`, `config`, `trace`, and
`calibration` across package roots and package subgroups. Some of these names
are intentional domain concepts, but without a canonical-home contract new
Fabric and IR Wave 3 moves could introduce another generic root API while still
passing existing package-layout gates.

## Decision

1. Process-wide observability and telemetry contracts are canonical under
   `polisyos.core.observability`.
2. Tenant identity, authorization, audit, quota, and related security contracts
   are canonical under `polisyos.core.security`.
3. Generic registry contracts are canonical under `polisyos.core.registry`.
   Per-package registries remain domain registries and must be documented as
   scoped exceptions when their path uses the generic `registry` name.
4. Plugin and entry-point discovery contracts are canonical under
   `polisyos.core.discovery`. Package workflow discovery must use
   package-scoped names or carry a sunset/backlog decision.
5. Runtime-agnostic configuration helpers are canonical under
   `polisyos.common.config`.
6. Persisted trace records and trace sinks are canonical under
   `polisyos.core.trace`; package tracing files are scoped emitters or
   compatibility facades.
7. Generic calibration diagnostics remain canonical under
   `polisyos.calibration`, extending ADR-RSR-0139.
8. A package may add `<package>/_adapters/<concern>.py` to adapt package data to
   a canonical interface. The adapter must import from the canonical home and
   must not create a competing top-level concern API.
9. New root concern files, first-level concern packages, and group-level
   concern files are blocked unless the path is the canonical home, is an
   `_adapters` module that imports the canonical interface, or has an explicit
   scoped exception in `architecture/policies/cross_cutting_concerns.toml` with owner,
   rationale, and sunset.

## Consequences

Package moves can still keep domain-specific registries, discovery workflows,
security controls, and calibration routines, but those names no longer imply a
new repository-wide API. Fabric and IR Wave 3 consolidations must either reuse
the canonical home, create `_adapters` modules, or record a scoped exception
before adding concern-named roots.

## Concrete Impact

- Contract: `architecture/policies/cross_cutting_concerns.toml`.
- Registry: `architecture/name_registry.toml`.
- Gate: `tools/quality/validation/check_package_import_gates.py`.
- Test: `tests/repo_quality/architecture/test_last_mile_cross_cutting_concerns.py`.
- Owner: `team-architecture`.
- Target phase: `1.5`.
- Rollback: remove the Phase 1.5 gate and reopen the scoped exceptions for each
  concern path added after this ADR.

## Related Decisions

- Extends: ADR-RSR-0134 Cross-Package Shared Name Registry.
- Extends: ADR-RSR-0139 Canonical Home for Calibration.
- Related: ADR-0116 Observability OTel First.
