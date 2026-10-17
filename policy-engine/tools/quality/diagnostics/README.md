# tools/quality/diagnostics

Diagnostic tooling for contracts, quality, and verification reports. This directory contains both CI gates and manual engineering checks.

## Role in the System

- Checks ABI/schema drift and enforces SemVer discipline.
- Checks Scientist/Foundry/Runtime architecture contracts.
- Produces verification evidence/matrices, including SCM v3 full-spec reports.
- Supports local diagnostics for the environment, provenance, and data contracts.

## Scripts

| Script                                 | Purpose                                                                                                                                        | Scope                               |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| `gen_schema.py`                        | Generates/checks ABI snapshots in `schemas/snapshots` (IR, Fabric, and registered Scientist payload variants) and generated IR reference pages | `pre-commit`, `arch.yml`, `abi.yml` |
| `generate_ir_reference_catalog.py`     | Generates/checks `docs/reference/ir/schema-catalog.md` and `docs/reference/schemas.md` from the reflection catalog                             | docs / ABI tooling                  |
| `abi_diff.py`                          | Semantic diff of baseline/current snapshots (`PASS/WARN/FAIL`)                                                                                 | `abi.yml`                           |
| `check_state_reads.py`                 | AST check that Scientist builtin nodes match their `state_reads` declarations                                                                  | `arch.yml`                          |
| `check_scientist_node_version_bump.py` | Requires a SemVer bump for changed builtin nodes (`--base-ref`)                                                                                | `arch.yml`                          |
| `check_perf_regression.py`             | Compares benchmark JSON against latency/throughput thresholds                                                                                  | `perf.yml`                          |
| `verify_scm_v3.py`                     | Runs the quick/full set of SCM v3 checks and generates evidence/matrices plus logs                                                             | manual verification                 |
| `verify_scm_v3_fullspec.py`            | Full-spec DoD/Laws/SL matrix based on `verify_scm_v3.py`; synchronizes canonical reports                                                       | manual verification                 |
| `check_setup.py`                       | Local smoke check for JAX/DuckDB/Pydantic and environment settings                                                                             | local                               |
| `capture_env.py`                       | `capture/compare/validate` for `EnvironmentManifest`                                                                                           | local                               |
| `scan_fabric.py`                       | Generates draft data contracts from DuckDB schemas                                                                                             | local                               |
| `visualize_provenance.py`              | Validates/visualizes provenance (core graph, PROV-JSON, CAS, audit package)                                                                    | local                               |
| `check_udf_perf.py`                    | UDF performance gate against a baseline JSON                                                                                                   | legacy                              |
| `generate_ir_schema.py`                | Deprecated shim: forwards the call to `gen_schema.py`                                                                                          | deprecated                          |

## Repository Connections

- `src/polisyos/*`: runtime contracts, builtin nodes, and artifact models.
- `schemas/snapshots/*`: committed ABI snapshot outputs.
- `src/polisyos/schemas/abi_models/`: Python ABI definitions and public API/selectors in `__init__.py`, and registry tables in `catalog.py, imported through `polisyos.*`.
- `docs/reports/*`: primary output location for verification reports (SCM v3 evidence/matrices and logs).
- `data/curated/*`, `data/databases/*`: inputs for local Fabric/UDF checks.
- `baseline/*.json` and benchmark artifacts: inputs for performance-regression scenarios.

## Typical Usage

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check --changed-only --cache-dir _cache/polisyos-tools/cache --baseline-label ci --skip-if-unchanged
PYTHONPATH=src:. uv run python tools/quality/diagnostics/abi_diff.py --baseline /tmp/baseline --current /tmp/current --format markdown
PYTHONPATH=src:. uv run python tools/quality/diagnostics/check_state_reads.py
PYTHONPATH=src:. uv run python tools/quality/diagnostics/check_scientist_node_version_bump.py --base-ref origin/main
PYTHONPATH=src:. uv run python tools/quality/diagnostics/verify_scm_v3.py --profile quick --output-dir docs/reports
PYTHONPATH=src:. uv run python tools/quality/diagnostics/verify_scm_v3_fullspec.py --output-dir docs/reports
```

## Filtered Snapshot Runs

The `--models` filter selects the run scope, while the canonical module manifest always lists that module's full active registry.

- Generation into `schemas/snapshots` accepts a filter only when every registry entry for each selected module is selected. An attempt to write a single snapshot into the canonical directory stops before writing; use a separate `--output-dir` for a partial preview.
- A filtered check of the canonical directory checks every entry for the selected modules and their complete manifests. It is not a full-registry check unless all modules are selected; running without `--models` checks the entire registry.
- With a separate `--output-dir`, generation and checking remain scoped to the selected entries. These preview runs do not write or check the global generated IR reference pages.
- The result prints the selection scope and the number of checked entries relative to the full registry, so a partial preview cannot be mistaken for full acceptance.
- Canonical scope is determined by the directory's physical identity: existing paths are compared through the filesystem (including case and symlink aliases), while missing paths are compared using the nearest existing ancestor's identity plus the full unresolved suffix. If both paths are missing beneath the same physical ancestor but have different suffixes, the generator returns `UNRUN` instead of assuming they are separate previews. Create the preview directory first or choose a path under a different existing ancestor.

## Known Limitations

- The codebase does not contain `polisyos.fabric.udf.*` or `polisyos.fabric.io.graph_store`; therefore, `check_udf_perf.py` does not currently match the structure of `src/polisyos`.
- `generate_ir_schema.py` remains only as a backward-compatible alias for `gen_schema.py`.
- `gen_schema.py` uses a content-addressable schema cache; the invalidation key includes the ABI model module source hash, ABI metadata, schema mode/version variant, generator version, and `pydantic` version.
- `gen_schema.py --changed-only` preserves manifest correctness: unchanged models are read from the cache, and the run is skipped entirely only when ABI sources are unchanged or the persisted successful-baseline fingerprint matches.
