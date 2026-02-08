# Confidential Computing Overhead Benchmark

## Scope

Measure runtime overhead of confidential nodes (`SEV-SNP`) versus standard nodes for:

- CPU-bound Foundry/JAX execution
- I/O-bound data access paths (DuckDB-heavy workloads)

## Method

1. Run equivalent workload on standard and confidential pools.
2. Execute each benchmark 10 times.
3. Capture p50/p95/p99 latency and throughput.
4. Compute relative overhead:

`overhead = (confidential_p99 - standard_p99) / standard_p99 * 100%`

## Target SLOs

- CPU-bound overhead: <= 10%
- I/O-bound overhead: <= 30%

## Placeholder Results

| Workload | Standard p99 | Confidential p99 | Overhead |
|---|---:|---:|---:|
| Foundry simulation (10k agents) | TBD | TBD | TBD |
| DuckDB world query | TBD | TBD | TBD |

## Notes

- If I/O overhead exceeds threshold, keep encrypted datasets outside CVM and release decrypt keys post-attestation only.
- Track kernel/runtime tuning per provider image (Azure Linux/Kata runtime).
