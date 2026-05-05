# ADR-RSR-0135: Versioning Out of Package Names

## Status

Accepted

## Date

2026-05-03

## Context

`ddm_15_7` encodes version information in the import namespace. Versioned
package names make public imports look permanent while freezing implementation
details into paths.

Phase 3B of the Repository Structure Remediation Plan needs an exact move map
before Phase 4A can touch source files.

## Decision

1. Canonical package names must not encode versions.
2. `src/polisyos/ddm_15_7` migrates to `src/polisyos/ddm` in Phase 4A.
3. The target Python facade is `polisyos.ddm`.
4. The old `polisyos.ddm_15_7` facade remains wrapper-only until
   2026-10-01.
5. Deep `polisyos.ddm_15_7.*` imports are internal and must be migrated in
   first-party source and tests during Phase 4A.
6. Existing schema IDs, YAML contract IDs, and policy IDs that contain
   `ddm_15_7` are compatibility identifiers, not package names; they are not
   rewritten by this package-name ADR.
7. Version information moves to explicit metadata: package version, ABI
   contracts, schema versions, or migration shims.

## Consequences

External root-facade importers get a sunset window. First-party tests and deep
imports move to `polisyos.ddm` immediately in Phase 4A. New versioned Python
package names fail the package layout gate once Phase 4A closes.

## Concrete Impact

- Contract: `architecture/package_layout.toml`.
- Blueprint:
  `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#ddm_15_7-to-ddm`.
- Shim registry: `architecture/shims.toml`.
- Package owner: `team-scientist`.
- Migration owner: `team-architecture`.
- Target phase: `4A`.
- Rollback: keep `ddm_15_7` as canonical and reopen ADR-RSR-0135.

## Related Decisions

- Related: ADR-0118 Release Train and SemVer Contracts.
