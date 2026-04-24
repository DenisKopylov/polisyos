# Confidential Computing Overhead Benchmark

This page documents how to measure confidential-node overhead for Foundry and
data-access workloads. It is a benchmark methodology page, not a source of
current measured results.

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
uv run pytest tests/foundry/benchmarks/test_ws5_jax_perf.py -m benchmark --benchmark-only
PYTHONPATH=src:. uv run python tools/benchmarks/jax/bench_simulation.py --agents 20000 --steps 24 --json
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
3. Execute each benchmark enough times to stabilize p50/p95/p99 latency.
4. Capture throughput and latency JSON artifacts.
5. Compute relative overhead:

```text
overhead_pct = (confidential_p99 - standard_p99) / standard_p99 * 100
```

## Target SLOs

| Workload class        | Target overhead |
| --------------------- | --------------: |
| CPU-bound Foundry/JAX | <= 10%          |
| I/O-bound data access | <= 30%          |

## Result Table Template

| Workload                 | Standard p99             | Confidential p99    | Overhead calculation           | Evidence artifact                |
| ------------------------ | -----------------------: | ------------------: | ------------------------------ | -------------------------------- |
| Foundry WS5 JAX perf     | Record from standard run | Record from CVM run | `(cvm_p99 / standard_p99) - 1` | `ws5-bench.json`                 |
| Agent simulation probe   | Record from standard run | Record from CVM run | `(cvm_p99 / standard_p99) - 1` | `bench_simulation --json` output |
| Benchmark registry smoke | Record from standard run | Record from CVM run | `(cvm_p99 / standard_p99) - 1` | `BENCH_JSON_DIR` reports         |
| DuckDB/world query probe | Record from standard run | Record from CVM run | `(cvm_p99 / standard_p99) - 1` | local workload report            |

## Notes

- Keep benchmark JSON artifacts with the environment metadata used to produce
  them.

- If I/O overhead exceeds the SLO, prefer encrypted datasets outside the CVM and
  release decrypt keys only after attestation.

- Compare replay-sensitive Foundry outputs using the tolerance budgets described
  in [Foundry Observability and Reproducibility](../reference/foundry/observability-reproducibility.md).
