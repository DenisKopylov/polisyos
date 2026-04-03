# Release, Versioning, and Deprecation Policy

This page defines the version namespaces used in PolicyOS and the deprecation
rules that keep them understandable.

Released versions are immutable. If something changes after release, it ships
as a new version rather than replacing an existing artifact.

## Release Prep Workflow

Before a release tag is created:

1. Update `pyproject.toml` and `frontend/runtime-dashboard/package.json` to the
   target version.
2. Freeze the selected `release-fragments/unreleased/` entries into
   `release-fragments/releases/<version>/`.
3. Review the generated release notes for compatibility, migration,
   schema/runtime/API, and limitation coverage.
4. Cut the signed `v<version>` tag only after that immutable snapshot exists.

The release workflow validates the versioned snapshot, not the mutable
`unreleased/` directory.

## Version Namespaces

| Namespace | Format | Source of truth | Meaning |
|---|---|---|---|
| Package release version | `MAJOR.MINOR.PATCH` | `pyproject.toml` and release metadata | Version of the published product package and release notes line |
| Architecture milestone language | `Phase N`, `WS-nX`, ADR IDs, milestone bundle names | docs and planning artifacts | Planning and architecture vocabulary only; not a compatibility contract |
| Schema version | `MAJOR.MINOR` | model `schema_version` fields and committed schema snapshots | Compatibility version for serialized schemas and ABI snapshots |
| Runtime API version | path major plus semantic version, for example `/api/v1` and `1.2.0` | runtime app, OpenAPI snapshot, capability manifest | Compatibility version for the public HTTP API |
| Frontend contract generation | exact generated artifacts derived from the committed OpenAPI file | `schemas/runtime_api_v1.openapi.json`, generated client files, dashboard API types | Build-time synchronization state for frontend consumers of the Runtime API |

Architecture milestone names are never a substitute for release, schema, or
runtime API version numbers.

## Package Release Version Policy

PolicyOS uses semantic versioning for package releases with one pre-1.0
clarification:

- while `MAJOR` is `0`, breaking supported-surface changes bump `MINOR`;
- backward-compatible additions bump `MINOR`;
- fixes, refactors, docs-only, and internal-only changes bump `PATCH`.

Once the project reaches `1.0.0`, standard semantic versioning applies:

- breaking change -> `MAJOR`
- backward-compatible addition -> `MINOR`
- backward-compatible fix -> `PATCH`

## Schema Version Policy

Schema versions use `MAJOR.MINOR`.

- additive backward-compatible changes, such as new optional fields or new enum
  values explicitly declared compatible by policy, bump `MINOR`;
- removals, renames, type changes, newly required fields, or other
  compatibility breaks bump `MAJOR`;
- docs-only or implementation-only changes that do not alter the serialized
  contract do not change schema version.

Schema changes must be reflected in committed snapshots and reviewed as contract
changes, not only as code edits.

## Runtime API Version Policy

Runtime API compatibility has two layers:

- the path major, for example `/api/v1`, defines the public compatibility line;
- the semantic version value reported by the runtime and documented with the
  OpenAPI contract describes additive vs breaking evolution within that line.

Rules:

- additive backward-compatible endpoint or field additions stay on the current
  path major and bump the runtime API minor version;
- fixes that do not change the supported contract bump the runtime API patch
  version;
- breaking changes require a new path major and a matching runtime API major
  version, for example `/api/v2` with `2.0.0`.

## Frontend Contract Generation Policy

Frontend contract generation does not define its own public version namespace.
It tracks the committed Runtime API contract.

When a PR changes Runtime API shape or generated frontend contract surfaces, the
same PR must update or verify:

- `schemas/runtime_api_v1.openapi.json`
- `frontend/runtime-api-client/runtimeApiClient.ts`
- `frontend/runtime-api-client/runtimeApiClient.js`
- `frontend/runtime-dashboard/src/api/types.ts`, when generated types change
- runtime contract verification and frontend contract checks

Generated artifacts must not drift from the committed OpenAPI source of truth.

## Deprecation Window Policy

Deprecated schema fields, runtime API fields, config keys, and generated-client
surfaces stay supported for at least:

- one subsequent minor package release; and
- 90 days after the first published deprecation notice.

Use the longer of those two windows. Faster removal is allowed only for
security, data-corruption, or legal-compliance reasons, and the release notes
must say so explicitly.

## Deprecation Announcement Requirements

Every deprecation must be announced in all relevant places:

- the PR classification and labels;
- the release notes entry for the release that introduces the deprecation;
- the affected reference or how-to docs;
- warnings, compatibility notes, or operator-facing messaging when the runtime
  can surface them safely.

## Release Notes Curation Requirements

Each release snapshot must cover all of the following sections across the
selected fragment set:

- compatibility notes;
- migration notes;
- schema/runtime/API changes;
- known limitations.

The workflow refuses to publish a release when any of those sections would be
empty.

## When a Migration Guide Is Required

A migration guide is required when a change:

- removes or renames a supported schema or runtime API field;
- introduces a schema major bump;
- introduces a runtime API major bump or new path major;
- requires regenerating consumers or coordinating a frontend/client rollout;
- changes config, secrets, deployment steps, or operational runbooks in a way
  that operators must act on before or during rollout.

## Public Surface Classification Linkage

Public-surface classification and compatibility classification are related, but
they answer different questions:

- `public_stable` / `public_experimental` / `internal` says **what kind of
  surface changed**;
- `breaking` / `additive` / `internal` says **how the change affects
  consumers/operators**.

Use them together:

- changes to `public_stable` entrypoints must be treated as supported-surface
  work: choose the correct `compat:*` label, update the relevant reference doc,
  and add `surface_classification = "public_stable: <entrypoint>"` to the
  release fragment when a fragment is required;
- changes to `public_experimental` entrypoints should stay visible in docs and
  release notes, but they may evolve without the same long-term compatibility
  promises; use `surface_classification = "public_experimental: <entrypoint>"`
  in the release fragment when the change is user-facing, operator-facing, or
  otherwise part of the shipped story;
- internal-only changes stay off the public-surface inventory and normally use
  `compat:internal`; if they still need a fragment because operators must care,
  record `surface_classification = "internal: internal-only"` explicitly.

## Practical Classification Rules

- use `breaking` when an existing supported consumer or operator must change
  behavior;
- use `additive` when existing integrations keep working unchanged;
- use `internal` when no supported surface changes.

That classification drives both the version bump and the migration-guide
expectation.
