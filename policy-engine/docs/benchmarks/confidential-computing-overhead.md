# Confidential Computing Overhead Benchmark

This page documents how to measure confidential-node overhead for Foundry and
data-access workloads. It is a benchmark methodology page, not a source of
current measured results.

The named harness sources were inspected at repository pin
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; no benchmark was executed for this documentation
update. The manual simulation harness emits mean, median, and p95, not p99. The performance
regression helper also computes median and p95, with ten measured iterations by default. The WS5
test uses `pytest-benchmark`; use only the statistic actually present in its saved report and do
not relabel it as p95 unless the report contains that field.

## Scope

Measure runtime overhead of confidential nodes such as SEV-SNP or equivalent CVM
pools versus standard nodes for:

- CPU-bound Foundry/JAX execution;
- agent-simulation stepping;
- DuckDB-heavy or world-query data access paths.

## Current Commands

Use the current benchmark command boundary:

```bash
uv run polisyos-tools benchmarks run-all --mode smoke
uv run polisyos-tools benchmarks run-all --circuit symbolic --mode smoke
uv run pytest tests/unit/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-only --benchmark-json=ws5-bench.json
PYTHONPATH=src:. uv run python tools/research/benchmarks/jax/bench_simulation.py --agents 20000 --steps 24 --warmup 10 --repeat 100 --json
```

For broader performance tests:

```bash
uv run pytest tests/performance/test_overhead.py -q
uv run pytest tests/performance/test_extended_benchmark_stack.py -q
```

Run the same command set on the standard pool and the confidential pool, with
the same commit, Python version, dependency lock, CPU/GPU posture, and input
profile.

## Method

1. Record machine type, confidential-computing feature, kernel/runtime image,
   Python version, JAX/JAXLIB versions, and `JAX_PLATFORMS`.
2. Run equivalent workload on standard and confidential pools.
3. Use the same emitted latency statistic on both pools. For the manual simulation harness, use
   `p95_ms` and a larger explicit run count such as `--repeat 100`; its five-run default is
   suitable for a smoke probe, not a stable cross-pool tail estimate. The regression test's
   ten-run default is also a bounded regression sample, not a stable comparative p95 estimate.
   Do not report p99 unless the selected harness computes and emits p99.
4. Capture throughput and latency JSON artifacts.
5. Compute relative overhead:

```text
overhead_pct = (confidential_p95_ms - standard_p95_ms) / standard_p95_ms * 100
```

## Target SLOs

| Workload class        | Target overhead |
| --------------------- | --------------: |
| CPU-bound Foundry/JAX |          <= 10% |
| I/O-bound data access |          <= 30% |

## Result Table Template

| Workload                 | Standard measurement     | Confidential measurement | Relative overhead calculation                | Evidence artifact                |
| ------------------------ | ------------------------ | ------------------------ | -------------------------------------------- | -------------------------------- |
| Foundry WS5 JAX perf     | Same statistic in report | Same statistic in report | `((cvm / standard) - 1) * 100`               | `ws5-bench.json`                 |
| Agent simulation probe   | `p95_ms`                 | `p95_ms`                 | `((cvm_p95_ms / standard_p95_ms) - 1) * 100` | `bench_simulation --json` output |
| Benchmark registry smoke | Same emitted metric      | Same emitted metric      | `((cvm / standard) - 1) * 100`               | `BENCH_JSON_DIR` reports         |
| DuckDB/world query probe | Same declared metric     | Same declared metric     | `((cvm / standard) - 1) * 100`               | local workload report            |

Only use the p95 formula above when both measurements are p95 values. For another statistic,
record its exact name and units in the result artifact and use the same statistic for both pools.
The formula yields a percentage, matching `overhead_pct`; `(cvm / standard) - 1` alone is a
ratio, not a percentage.

## Notes

- Keep benchmark JSON artifacts with the environment metadata used to produce
  them.

- If I/O overhead exceeds the SLO, prefer encrypted datasets outside the CVM and
  release decrypt keys only after attestation.

- Compare replay-sensitive Foundry outputs using the tolerance budgets described
  in [Foundry Observability and Reproducibility](../reference/foundry/observability-reproducibility.md).
