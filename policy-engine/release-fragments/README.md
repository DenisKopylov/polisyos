# Release Fragments

PolicyOS release notes are drafted from structured TOML fragments under
`release-fragments/unreleased/` while changes are still landing.

Before a release tag is cut, release prep must freeze the selected entries into
an immutable snapshot under `release-fragments/releases/<version>/`. The
release workflow reads only from that versioned snapshot so future tags cannot
reuse stale unreleased notes.

Each fragment becomes part of the published GitHub release notes and should stay
human-readable. Required fields:

- `type`: one of `added`, `changed`, `deprecated`, `removed`, `fixed`, `security`
- `summary`: one concise sentence that will become the bullet body

Optional but strongly encouraged fields:

- `title`: short label for the change
- `component`: subsystem or surface (`platform`, `runtime-dashboard`, `schemas`, ...)
- `compatibility`: compatibility note if operators or consumers must care
- `surface_classification`: supported-surface impact in the format ``public_stable: polisyos.runtime`` / ``public_experimental: polisyos.scholar`` / ``internal: internal-only`` when the change touches a classified package surface
- `migration`: migration guidance if rollout steps are needed
- `api`: schema/runtime/API surface note
- `limitations`: known limitation that should ship with the release notes

Use `template.toml` as the starting point.

Release snapshots must cover `compatibility`, `migration`, `api`, and
`limitations` across the selected fragment set.

Release prep helper:

```bash
python3 policy-engine/tools/release/stage_release_snapshot.py \
  --version 0.1.0 \
  --move
```
