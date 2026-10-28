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
| `controlled_candidate_profile.py`, `generic_n4_served_replay.py` | Candidate-only SKG selection and persisted base/child WMR fixture ownership. |
| `causal_scm_fixtures.py` | Causal SCM fixtures. |
| `observability.py` | Observability assertions. |
| `runtime_http.py` | Runtime HTTP test helpers. |
| `scientist_runtime.py`, `search_strategies.py` | Scientist runtime/search helpers. |

## Extension Points

Add helpers here only when at least two test slices use them. Single-slice
helpers stay under the owning test subtree.

## Tests

Helper behavior is covered by consuming tests and the bounded source-root tests:

```bash
.venv/bin/python -m pytest -q tests/unit/runtime/quality/test_controlled_candidate_source_roots.py tests/integration/runtime_quality/test_controlled_world_model_source_binding.py
```

For controlled candidate profiles, `source_root` admits the independently selected
SKG input directory. Its resolved `academic-skg.duckdb` path, version, snapshot,
schema and bytes remain checked by the existing owner. Omitting it preserves the
legacy `tmp_path/controlled-candidate-source` input. The canonical seed producer
also accepts the same root when no selection is supplied. Generated Fabric world,
DuckDB and data-forge artifacts always retain the separate fixture output owner
`tmp_path/controlled-candidate-source`; an explicit input root does not relocate
those writes. Pass the same explicit root and actual selected source to base and
child profiles. Fixture evidence remains candidate-only and does not supply
empirical grounding, currentness or authority.

## Operability Links

- `tests/README.md`
- `tests/TESTING_POLICY.md`

## Known Shims/Deprecations

Remove helpers when their final consumer moves away.
