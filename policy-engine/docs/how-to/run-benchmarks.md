# Run Benchmarks

Use the benchmark suite registry for benchmark circuits, and use targeted
pytest benchmark tests for Foundry/JAX hot paths. Directory names under
`benchmarks/` are not the source of truth; `benchmarks/suite_registry.py` is.

Freshness: 2026-04-17.

## Input

- selected benchmark circuit, mode, or claim profile
- optional real-data prerequisites for heavier suites
- decision whether you need smoke evidence, local SOTA evidence, or release summary aggregation

## Output

- suite JSON reports under benchmark report directories
- release-summary inputs for performance review
- enough evidence to compare smoke, hot-path, and broader benchmark circuits

## Commands

```bash
uv run polisyos-tools benchmarks run-all --help
uv run polisyos-tools benchmarks run-all --mode smoke
uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-only
```

## Canonical Commands

```bash
uv run polisyos-tools benchmarks run-all --help
uv run polisyos-tools benchmarks run-all
uv run polisyos-tools benchmarks build-release-summary --help
uv run polisyos-tools benchmarks run-parallel --help
uv run polisyos-tools benchmarks run-local-sota-profile --help
```

Compatibility module paths still exist, but the `polisyos-tools benchmarks ...`
surface is the command boundary to document.

## Smoke Runs

Start with smoke mode before running heavy profiles:

```bash
uv run polisyos-tools benchmarks run-all --mode smoke
uv run polisyos-tools benchmarks run-all --circuit symbolic --mode smoke
uv run polisyos-tools benchmarks run-all --circuit temporal_gold --mode smoke
```

Useful environment variables:

- `BENCH_MODE`
- `BENCH_TIER`
- `BENCH_PROFILE`
- `BENCH_VALIDATION_CONTOUR`
- `BENCH_VISIBILITY`
- `BENCH_CIRCUIT`
- `BENCH_RUN_ID`
- `BENCH_ESTIMATOR_PROFILE`
- `BENCH_JSON_DIR`

## Suite Registry

The authoritative registry is:

```text
benchmarks/suite_registry.py
```

It defines `SuiteSpec` rows with fields such as `suite_id`, `script_relpath`,
`aliases`, `profiles`, `claim_profiles`, `proof_class`,
`validation_contours`, `visibility`, `family`, and `primary_metrics`.

Useful helper APIs:

- `all_suite_specs()`
- `canonical_suite_id(...)`
- `spec_by_suite_id(...)`
- `suites_for_profile(...)`
- `suites_for_claim_profile(...)`
- `emit_registry_tsv(...)`

## Foundry/JAX Hot-Path Benchmarks

Foundry Phase 4 benchmark evidence is split between registry circuits and
pytest benchmark tests. For JAX-sensitive hot paths:

```bash
uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-only
uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-json=ws5-bench.json
```

For local domain probes:

```bash
PYTHONPATH=src:. uv run python tools/research/benchmarks/jax/bench_domain.py --repeat 3 --json
PYTHONPATH=src:. uv run python tools/research/benchmarks/jax/bench_simulation.py --agents 20000 --steps 24 --json
```

## Reports

Canonical runner reports land in one of these locations depending on entry
point and `BENCH_JSON_DIR`:

- `benchmarks/_reports/`
- `tools/research/benchmarks/_reports/`
- `tools/research/benchmarks/_reports/`

`polisyos-tools benchmarks build-release-summary` aggregates per-suite JSON into
release-level summaries with contour, comparator, ablation, leaderboard, and
gate-result fields.

## CI Reality

The benchmark registry and CI quality gates are related but not identical.
Foundry release-gate behavior is asserted by
`tests/unit/foundry/validation/test_release_gate.py`.
Benchmark suites remain the canonical way to run local or release benchmark
circuits and produce JSON evidence.

## Confidential Computing Overhead

For TEE/CVM overhead methodology and the current command pointers, see
`docs/benchmarks/confidential-computing-overhead.md`.

## Rollback

- Delete local JSON reports from `benchmarks/_reports/` or `tools/research/benchmarks/_reports/` when the run was exploratory and not intended as baseline evidence.
- Do not commit fresh benchmark outputs unless the PR intentionally advances a benchmark baseline or release-summary artifact.

## Troubleshooting

- If a suite id is unclear, resolve it from `benchmarks/suite_registry.py` before running wrappers ad hoc.
- If heavy paths are unstable, start with `--mode smoke` and then move to targeted suites.
- If JAX-sensitive probes behave differently across machines, capture the exact env/profile and keep CPU-vs-accelerator comparisons explicit in the report.
