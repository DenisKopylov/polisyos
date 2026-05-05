---
title: Repository Structure Remediation Closeout
status: accepted
owner: team-polisyos
created: 2026-05-05
last_verified: 2026-05-05
stability: stable
---

# Repository Structure Remediation Closeout

## Verdict

Repository Structure Remediation Phase 7 is closed on 2026-05-05.

All gates listed by the plan are now fail-closed. Remaining non-blocking
structure debt is explicit, owner-approved, and time-bounded in
`architecture/exceptions/structure_remediation.toml`.

The final cloud full-suite baseline is green:

- Command: `pytest tests/unit tests/integration tests/property tests/contract tests/golden -q`.
- Cloud runner: GCP VM `phase3a-fulltests-20260503`, `europe-west1-b`, 12 xdist workers.
- Main suite: 10,955 tests, 0 failures, 0 errors, 35 accepted skips, 2,318 s.
- Benchmark slice: 20 tests, 0 failures, 0 errors, 24 s.
- Total: 10,975 total tests, 0 failures, 0 errors, 35 accepted skips.
- Evidence: `gs://lex-1-494208-data/experiments/phase3a_fulltests/phase3a-fulltests-12core-20260504-rerun-20260504T111449Z/`.

The accepted skips are optional dependency or environment gates: `dowhy`,
`pygraphviz`, `ray`, `kuzu`, `econml`, `plotly`, BoTorch, OTel metrics backend,
`POLISYOS_RUN_INTEGRATION=1`, and compatibility skips for environments where
optional accelerated capabilities are already installed.

## Inventory Delta

| Metric | Phase 0 baseline | Closeout | Status |
| --- | ---: | ---: | --- |
| Foundry methods empty placeholders | 0 | 0 | closed |
| Duplicate cache/env buckets | 7 | 0 | closed |
| Build-output paths detected | 15 | 4 | fail-closed with exceptions |
| Repeated directory names | 37 | 41 | fail-closed with registry coverage |
| `pyproject.toml` lines | 267 | 275 | within <= 300 budget |
| `scientist` root `.py` files | 14 | 2 | closed |
| `foundry` root `.py` files | 29 | 4 | closed |
| `scientist` top-level entries | not recorded | 45 | within <= 250 budget |
| `foundry` top-level entries | not recorded | 51 | within <= 250 budget |

Notes:

- The closeout gate now enforces top-level package entry budget rather than
  recursive file count. This matches the plan acceptance language for Phase 5
  and Phase 6.
- `scientist` and `foundry` decomposition is complete at the root-facade level.
  Recursive package size remains a future package-local concern, not the
  repository structure gate.
- Generic empty `__init__.py`-only packages are inventoried but not part of the
  `empty_namespace_gate`; the fail-closed gate targets the specific
  `foundry/methods` placeholder/collision risk from the plan.

## Gate Status

| Gate | Mode | Evidence |
| --- | --- | --- |
| `empty_namespace_gate` | fail-closed | `architecture/baselines/structure_remediation/foundry_methods_empty_placeholders.json` |
| `loose_files_gate` | fail-closed | `architecture/package_layout.toml`, `architecture/exceptions/structure_remediation.toml` |
| `name_collision_gate` | fail-closed | `architecture/name_registry.toml` |
| `pyproject_size_gate` | fail-closed, <= 300 lines | `architecture/baselines/structure_remediation/pyproject_sections.json` |
| `cache_dir_gate` | fail-closed | `architecture/baselines/structure_remediation/cache_and_env_paths.json`, `architecture/exceptions/structure_remediation.toml` |
| `build_output_gate` | fail-closed | `architecture/baselines/structure_remediation/build_outputs.json`, `architecture/exceptions/structure_remediation.toml` |
| `dynamic_imports_gate` | fail-closed | `architecture/dynamic_imports.toml` |
| `pickle_compat_gate` | fail-closed | `tests/fixtures/checkpoint_compat` |
| `public_surface_snapshot_gate` | fail-closed | `architecture/baselines/structure_remediation/public_surface_pre_decomp.json` |
| `import_cycles_gate` | fail-closed | `architecture/imports/lazy.toml` |
| `import_time_regression_gate` | fail-closed, <= 15% | `architecture/baselines/structure_remediation/import_time_pre_decomp.json` |
| `reexport_shim_shape_gate` | fail-closed, no star import | `architecture/shims.toml` |

Verified commands:

- `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed`.
- `uv run python tools/quality/validation/decomposition_preflight.py gate`.
- `uv run pytest tests/unit/scientist tests/integration/scientist tests/property/scientist tests/contract -q`.
- `uv run pytest tests/unit/foundry tests/property/foundry tests/contract -q`.
- `POLISYOS_RUN_IMPORT_TIME_GATE=1 uv run pytest tests/architecture/test_decomposition_preflight_gates.py -q`.
- `uv run pytest tests/contract/test_pickle_compat.py tests/architecture/test_public_surface_snapshot.py tests/architecture/test_decomposition_preflight_gates.py tests/architecture/test_repository_structure_phase1a.py tests/architecture/test_repository_structure_phase1c.py -q`.

## Remaining Exceptions

All exceptions are in `architecture/exceptions/structure_remediation.toml`.

| Category | Count | Sunset |
| --- | ---: | --- |
| Non-target package root-module cleanup (`calibration`, `common`, `fabric`, `ir`, `lex`, `scholar`) | 6 | 2026-09-01 |
| Local cache state during active refactor (`.mypy_cache`, `.hypothesis`) | 2 | 2026-06-15 |
| Root release/workspace artifact staging (`release`, `release-fragments`, workspace `tmp`) | 3 | 2026-06-15 to 2026-09-01 |

No exception is open-ended. Expired exceptions fail the closeout gate.

## Shim Sunset Audit

`architecture/shims.toml` remains active and fail-closed.

| Shim type | Count | Closeout action |
| --- | ---: | --- |
| `python_reexport` | 40 | retained until `2027-03-02` per Phase 5/6 workflow-lifetime rule |
| `file_relocation` | 8 | retained; earliest sunset `2026-07-01` |
| `wrapper_only` | 5 | retained; earliest sunset `2026-08-01` |

No shim created by this plan is expired as of 2026-05-05. Therefore none is
retired in this closeout. The sunset audit is enforced through the
Phase 7 closeout test and the existing shim registry metadata.

## Final Metrics

| Metric | Value |
| --- | --- |
| `scientist` root `.py` files | 2: `__init__.py`, `api.py` |
| `scientist` top-level entries | 45 |
| `foundry` root `.py` files | 4: `__init__.py`, `_quickstart.py`, `_registry.py`, `api.py` |
| `foundry` top-level entries | 51 |
| Import-time baseline, `polisyos.scientist` | median 89.161 ms, p95 174.028 ms |
| Import-time baseline, `polisyos.foundry` | median 79.243 ms, p95 155.636 ms |
| Public surface diff | accepted final snapshot; no current drift after closeout refresh |
| Pickle compat coverage | 2 canonical fixtures: Foundry agent-sim result and Scientist engine checkpoint artifact |

Public-surface closeout note: the final snapshot accepts one non-breaking
signature rendering update in `polisyos.foundry.calibration.identifiability`,
where default values now render via named constants rather than inline model
construction. No modules were added or removed by this refresh.

## Plan Closure

The former active repository-structure remediation plan has been moved to
`docs/plans/accepted/REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md` with
`status: accepted` and `stability: stable`.

Phase 5 and Phase 6 may proceed only through the fail-closed gate set above;
future structural exceptions must be added to `architecture/exceptions/` with
owner and sunset.
