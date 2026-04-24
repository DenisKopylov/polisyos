# Performance Tests

`tests/performance` contains the benchmark and hot-path regression slice. It
currently contains `8` `test_*.py` files covering CLI, runtime overhead,
extended benchmark stacks, and scientist/runtime performance paths.

## Purpose

- Catch performance regressions that should not be treated as ordinary unit
  failures.

- Keep runtime hot paths and benchmark orchestration behavior visible in the
  main test tree.

- Provide a stable landing page for the `performance` taxonomy lane.

## Where To Start

- `test_runtime_hot_paths.py` and `test_scientist_runtime_paths.py` for runtime
  path regressions.

- `test_extended_benchmark_stack.py` for wider benchmark/evidence coverage.
- [`../../docs/how-to/run-benchmarks.md`](../../docs/how-to/run-benchmarks.md)
  for the supported benchmark command surface.

## Public Entrypoints

- `tests/performance/test_benchmark_phase15_cli.py`
- `tests/performance/test_benchmark_phase15_contract.py`
- `tests/performance/test_benchmark_runtime_pipeline.py`
- `tests/performance/test_extended_benchmark_stack.py`
- `tests/performance/test_local_real_benchmark_pack.py`
- `tests/performance/test_overhead.py`
- `tests/performance/test_runtime_hot_paths.py`
- `tests/performance/test_scientist_runtime_paths.py`

## Depends On / Depended On By

### Depends On

- Benchmark tooling under `tools/benchmarks` / `tools/research/benchmarks`
- Runtime and scientist hot-path code
- `pytest-benchmark` / performance-oriented optional dependencies

### Depended On By

- The `performance` lane described in [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- Release and evidence workflows that need stable benchmark/regression checks

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: performance slice
uv run pytest tests/performance -q

# conceptual: performance taxonomy lane
uv run pytest -m performance
```

## Test And Verification Commands

The file-level collect-only commands below were smoke-checked on `2026-04-17`.
The full `tests/performance` slice remains conceptual here because collection in
the current tree is blocked by `test_benchmark_runtime_pipeline.py`.

```bash
cd policy-engine
uv run pytest --collect-only tests/performance/test_overhead.py -q
uv run pytest --collect-only tests/performance/test_runtime_hot_paths.py -q
```

## Reference Docs

- [`../../docs/how-to/run-benchmarks.md`](../../docs/how-to/run-benchmarks.md)
- [`../../docs/benchmarks/confidential-computing-overhead.md`](../../docs/benchmarks/confidential-computing-overhead.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
