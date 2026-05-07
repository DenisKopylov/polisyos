# Release Fragments

PolicyOS release notes are drafted from structured TOML fragments under
`release-fragments/unreleased/` while changes are still landing.

Before a release tag is cut, release prep must freeze the selected entries into
an immutable snapshot under `_build/release-fragments/<version>/`. The
release workflow reads only from that versioned snapshot so future tags cannot
reuse stale unreleased notes.

Each fragment becomes part of the published GitHub release notes and should stay
human-readable. Required fields:

- `type`: one of `added`, `changed`, `deprecated`, `removed`, `fixed`, `security`
- `summary`: one concise sentence that will become the bullet body

Optional but strongly encouraged fields:

- `id`: stable fragment id, usually date plus short slug
- `title`: short label for the change
- `component`: subsystem or surface (`platform`, `runtime-dashboard`, `schemas`, ...)
- `owner`: team that owns the release note
- `evidence`: reviewed docs, tests, manifests, or reports that support the note
- `compatibility`: compatibility note if operators or consumers must care
- `change_class`: one of `python-public-api`, `schema-openapi-abi`, `extension-plugin-abi`, `runtime-state-format`, `persisted-artifact-format`, `js-package-api`, or `internal`
- `surface_classification`: supported-surface impact in the format `public_stable: polisyos.runtime` / `public_experimental: polisyos.scholar` / `internal: internal-only` when the change touches a classified package surface
- `migration`: migration guidance if rollout steps are needed
- `api`: schema/runtime/API surface note
- `limitations`: known limitation that should ship with the release notes
- `generated_client_compatibility`: `not_applicable`, `declared_compatible`,
  `requires_regeneration`, or `breaking_requires_consumer_action`
- `public_surface_inventory_reviewed`: true when a public-surface change has a
  regenerated or explicitly reviewed inventory
- `migration_docs` / `runbook_docs`: repo-relative paths that must exist before
  the release candidate is promoted

Structured compatibility changes use repeated `[[compatibility_change]]` tables.
Each entry must include `id`, `change_class`, `impact`, `surface`, `owner`,
`version_owner`, `deprecation_window`, and `release_note`. Use these records for
breaking, deprecation, migration, generated-client, or public-surface promises so
release notes can render a machine-readable compatibility section.

Use `template.toml` as the starting point.

Release snapshots must cover `compatibility`, `migration`, `api`, and
`limitations` across the selected fragment set. User-visible compatibility
changes should also set `change_class` so release notes can distinguish Python
public API, schema/OpenAPI ABI, extension plugin ABI, runtime-state format,
persisted artifact format, and JS package API changes.

Release prep helper:

```bash
python3 policy-engine/tools/ops_runners/release/stage_release_snapshot.py \
  --version 0.1.0 \
  --move
```
