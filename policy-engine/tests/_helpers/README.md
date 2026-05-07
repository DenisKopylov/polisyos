# Shared Test Helpers

Owner: `team-quality`
Last updated: 2026-05-05

## Purpose

`tests/_helpers` stores shared pytest helper modules that are imported by
multiple test slices.

## Public API

Only tests import this subtree. Product code must not depend on it.

## Internal Layout

| File | Role |
| --- | --- |
| `artifacts.py` | Artifact test helpers. |
| `causal_scm_fixtures.py` | Causal SCM fixtures. |
| `observability.py` | Observability assertions. |
| `runtime_http.py` | Runtime HTTP test helpers. |
| `scientist_runtime.py`, `search_strategies.py` | Scientist runtime/search helpers. |

## Extension Points

Add helpers here only when at least two test slices use them. Single-slice
helpers stay under the owning test subtree.

## Tests

Helper behavior is covered indirectly by consuming tests.

## Operability Links

- `tests/README.md`
- `tests/TESTING_POLICY.md`

## Known Shims/Deprecations

Remove helpers when their final consumer moves away.
