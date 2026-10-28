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

Configured source/WMR fixtures may additionally pass `l6_source_owner_root` to
select a small physical L6 data owner independently of the code root. The
`_seed_controlled_candidate_l6_source` helper creates exactly the three required
empty candidate JSON inputs in a fresh fixture directory. The real two-root L6
loader still reads the tracked authority manifest from the code root and
verifies content hashes; an absent operator is still refused. The fixture proves
source/WMR plumbing only. It supplies no grounded lever, legal permission,
production provenance or empirical calibration. Omitting the optional owner
preserves the existing configured-profile input selection.

The positive `_admit_served_wdi_projection` fixture explicitly declares its
controlled datasets bundle through the existing binder option. Partial and
invalid source owners retain native refusal; the binder default is unchanged.

## Operability Links

- `tests/README.md`
- `tests/TESTING_POLICY.md`

## Known Shims/Deprecations

Remove helpers when their final consumer moves away.

## Completed ex-ante Runtime source witnesses

`completed_ex_ante_runtime.py` launches and dispatches real authenticated Runtime
workflows from selected prepared inputs; it never registers a fake owner, completes
a job manually, or substitutes a metric. The HTTP A/B/planner witness and the
identical-input A/A witness share this producer path. A/A prepares once, executes
two distinct jobs, checks captured rows and independent exact mean1/1, and keeps
the normal duplicate-candidate ranking refusal. A/B, revocation and controls remain
separate qualifications.

`scientist_runtime_profile.py` is a fresh-process diagnostic. It calls the actual
public node discovery with `include_dev_scan=False`, resolves required nodes,
calls the installed sklearn native hash extension and the NumPy Ex-Ante method,
and retains actual tracebacks/report/PID/loaded Python hashes. It does not install
dependencies, replace nodes, establish a Runtime chain, or measure process-tree
resources. Run it with the admitted Python/profile and retain stdout/stderr plus
its `--output` JSON before the genuine Runtime witness.

The capture oracle derives every invocation's complete position/ID/kind/status
inventory from the actual selected graph and ExecPlan, retaining operator rows,
then joins the method by the current observation's occurrence ID. Both Runtime
A/A and A/B use it. The profile diagnostic retains every loaded polisyos Python
origin and refuses an import outside the selected checkout source root.
