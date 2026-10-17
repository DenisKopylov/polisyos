# Release Fragments

PolicyOS release notes are drafted from structured TOML fragments under
`release-fragments/unreleased/` while changes are still landing.

Before a release tag is cut, release prep must freeze the selected entries into
an immutable snapshot under `_build/release-fragments/<version>/`. The
release workflow reads only from that versioned snapshot so future tags cannot
reuse stale unreleased notes.

Each fragment becomes part of the published GitHub release notes and should stay
human-readable. These fields are required at the TOML root, as declared by
`ops/release/release-fragment-policy.toml`:

- `id`: stable fragment id, usually date plus short slug
- `title`: short label for the change
- `type`: one of `added`, `changed`, `deprecated`, `removed`, `fixed`, `security`
- `owner`: team that currently owns the release note
- `summary`: one concise sentence that will become the bullet body
- `evidence`: reviewed docs, tests, manifests, or reports that support the note

The `id`, `title`, `owner`, and `summary` values must be non-empty strings.
`evidence` must be a non-empty list of non-empty evidence references. `type` is
validated against the release policy and must be supported by the release-note
renderer. Nested tables do not replace any of these root-level fields.

Optional but strongly encouraged fields:

- `component`: subsystem or surface (`platform`, `runtime-dashboard`, `schemas`, ...)
- `compatibility`: compatibility note if operators or consumers must care
- `change_class`: optional legacy descriptive prose rendered in the `Change Classes` section; it is not enum-validated and does not drive compatibility gates. Put machine-readable compatibility claims in `[[compatibility_change]].change_class` instead.
- `surface_classification`: supported-surface impact in the format `public_stable: polisyos.runtime` / `public_experimental: polisyos.scholar` / `internal: internal-only` when the change touches a classified package surface
- `migration`: migration guidance if rollout steps are needed
- `api`: schema/runtime/API surface note
- `limitations`: known limitation that should ship with the release notes
- `generated_client_compatibility`: `not_applicable`, `declared_compatible`,
  `requires_regeneration`, or `breaking_requires_consumer_action`; every supplied
  value must match the policy enum, and schema/OpenAPI or JS package compatibility
  entries must use a value other than `not_applicable`
- `public_surface_inventory_reviewed`: optional TOML boolean at the fragment root
  or in a structured compatibility change; when supplied it must be `true` or
  `false`, and a `python-public-api` change requires an actual boolean `true` at
  either scope. The marker is consumer-asserted: this checker does not authenticate
  reviewer identity or independently establish that the inventory was reviewed.
- `migration_docs` / `runbook_docs`: repo-relative paths that must exist before
  the release candidate is promoted

Structured compatibility changes use repeated `[[compatibility_change]]` tables.
Each entry must include `id`, `change_class`, `impact`, `surface`, `owner`,
`version_owner`, `deprecation_window`, and `release_note`. Use these records for
breaking, deprecation, migration, generated-client, or public-surface promises so
release notes can render a machine-readable compatibility section.

Use `template.toml` as the starting point.

Release snapshots must cover `compatibility`, `migration`, `api`, and
`limitations` across the selected fragment set. User-visible compatibility changes should use `[[compatibility_change]]`
records when a machine-readable compatibility claim is needed. Their
`change_class` is checked against the compatibility-gate enum. The top-level
`change_class` remains legacy curated prose only; it is rendered for readers but
does not classify compatibility or satisfy a structured gate.

Release prep helper:

```bash
python3 policy-engine/tools/ops_runners/release/stage_release_snapshot.py \
  --version 0.1.0 \
  --move
```
