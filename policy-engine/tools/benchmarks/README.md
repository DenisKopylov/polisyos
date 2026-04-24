# tools/benchmarks

`tools/benchmarks` is the stable public compatibility package for benchmark
execution.

Canonical implementation lives under `tools/research/benchmarks/`.

## Ownership Boundary

- `tools/research/benchmarks/` owns executable/orchestration code:
  `run_all`, `run_parallel`, local SOTA profile runners, release summary
  generation, real-data preparation, JAX/lex smoke probes.

- root `benchmarks/` owns benchmark-domain code:
  suites, fixtures, comparators, scorecards, reporting, runtime helpers,
  `harness.py`, `metrics.py`, `suite_registry.py`, and other support modules
  imported by suites.

- root `benchmarks/*.py` and `benchmarks/*.sh` executables are deprecated
  compatibility wrappers.

## Canonical Commands

```bash
uv run polisyos-tools benchmarks run-all
uv run polisyos-tools benchmarks build-release-summary --help
uv run polisyos-tools benchmarks prepare-real-benchmark-data --help
uv run polisyos-tools benchmarks run-parallel --help
uv run polisyos-tools benchmarks run-local-sota-profile --help
uv run polisyos-tools benchmarks benchmark-lex-llm-steady-state --help
uv run polisyos-tools benchmarks benchmark-lex-llm-sweep --help
```

## Compatibility Notes

- `tools/benchmarks/*` top-level modules remain importable for one deprecation window.
- `python -m tools.benchmarks.run_all` and similar module paths still work through shims.
- `benchmarks/run_all_benchmarks.sh` and related root wrappers print a deprecation warning and forward to the canonical zoned tooling surface.

## Reports

- default benchmark orchestration reports still land in `benchmarks/_reports/`
  or `tools/research/benchmarks/_reports/` depending on the entry point;

- report schemas are preserved across the reorganization.
