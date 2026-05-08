# ADR-RSR-0135: Versioning Out of Package Names And Compatibility Contracts

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

Phase 1.5 of the Repository Best-In-Class Remediation Master Plan generalizes
this package-name rule into one versioning policy for Python APIs, schemas,
extension contracts, runtime state, persisted artifacts, and JS packages.

## Decision

1. Canonical package names must not encode versions.
2. `src/polisyos/ddm_15_7` migrates to `src/polisyos/ddm` in Phase 4A.
3. The target Python facade is `polisyos.ddm`.
4. The old `polisyos.ddm_15_7` facade remains wrapper-only until
   2026-07-31.
5. Deep `polisyos.ddm_15_7.*` imports are internal and must be migrated in
   first-party source and tests during Phase 4A.
6. Existing schema IDs, YAML contract IDs, and policy IDs that contain
   `ddm_15_7` are compatibility identifiers, not package names; they are not
   rewritten by this package-name ADR.
7. Version information moves to explicit metadata: package version, ABI
   contracts, schema versions, or migration shims.
8. New Python package names must not encode problem numbers, policy numbers, or
   version numbers such as `*_15_7`, `*_v2`, or `*_2026` unless a follow-up ADR
   explicitly grants a temporary shim exception.
9. Versioned data and API concepts live under JSON schemas, OpenAPI snapshots,
   artifact metadata, or explicit contract IDs. They do not create new Python
   package names.
10. Extension contracts declare `contract_version` in
    `architecture/extension_points.toml`; incompatible plugin ABI changes move
    by contract version, not by import path.
11. Release fragments communicate user-visible change classes so release notes
    can distinguish public API, schema ABI, plugin ABI, runtime-state,
    persisted-artifact, and JS package compatibility.

## Consequences

External root-facade importers get a sunset window. First-party tests and deep
imports move to `polisyos.ddm` immediately in Phase 4A. New versioned Python
package names fail the package layout gate once Phase 4A closes.

Phase 2.3 of the last-mile remediation keeps the root compatibility import
because the caller report shows only intentional compatibility tests, while the
release policy still requires a dated public-import window. The owner remains
`team-architecture`, the migration target is `polisyos.ddm`, and the smoke
test lives under `tests/unit/ddm/`.

Future decomposition work must name which compatibility category it is changing
before it moves code, schemas, artifacts, generated clients, or plugin
contracts.

## Compatibility Categories

| Category | Source of truth | Breaking-change signal |
| --- | --- | --- |
| Python public API | `architecture/public_surface/contract.toml`, package facades, and shim registry | SemVer major or explicit shim/deprecation entry |
| Schema/OpenAPI ABI | `schemas/**` and committed OpenAPI snapshots | schema major, OpenAPI path major, or migration guide entry |
| Extension plugin ABI | `architecture/extension_points.toml` | `contract_version` major or incompatible ABI policy |
| Runtime-state format | `architecture/local_runtime_state.toml` and `.polisyos` schema docs | migration reader/writer version change |
| Persisted artifact format | artifact schemas, CAS manifests, and `producer_version` metadata | artifact schema major or migration manifest |
| JS package API | frontend workspaces, package exports, and generated client snapshots | npm package major or generated client compatibility note |

## Deprecation Windows

| Surface | Minimum window | Removal gate |
| --- | --- | --- |
| Shim packages | 2 minor releases | `architecture/shims.toml` sunset, release note, and migration docs |
| Renamed public imports | 2 minor releases | wrapper-only shim, warning, release fragment, and public-surface update |
| Extension contract versions | 2 minor releases | replacement `contract_version`, adapter or migration note, and installable example update |
| Runtime-state migration readers | 1 major release | operator migration guide and reader compatibility test removal |
| Generated client compatibility | 2 minor releases | OpenAPI snapshot, generated client release note, and dashboard compatibility test |

## Dynamic Imports And Extension Points

Plugin discovery must use a declared entry-point group or declared builtin
loader from `architecture/extension_points.toml`. Ad hoc string imports remain
governed by `architecture/imports/dynamic.toml` and must have an owner, target
or allowed target list, and verifier.

## Release Fragments

Release fragments should set `change_class` when a user-visible change touches
one of the compatibility categories above. The value should be one of:
`python-public-api`, `schema-openapi-abi`, `extension-plugin-abi`,
`runtime-state-format`, `persisted-artifact-format`, `js-package-api`, or
`internal`.

## Concrete Impact

- Contract: `architecture/packages/layout.toml`.
- Extension contracts: `architecture/extension_points.toml`.
- Blueprint:
  `docs/plans/active/SMALL_PACKAGE_CONSOLIDATION_BLUEPRINT.md#ddm_15_7-to-ddm`.
- Shim registry: `architecture/shims.toml`.
- Package owner: `team-scientist`.
- Migration owner: `team-architecture`.
- Target phase: `4A`.
- Rollback: keep `ddm_15_7` as canonical and reopen ADR-RSR-0135.

## Related Decisions

- Related: ADR-0118 Release Train and SemVer Contracts.
