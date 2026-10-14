# tools/research/benchmarks

Canonical benchmark entry points live under `tools/research/benchmarks/`; the root
`benchmarks/` package remains a backend library plus compatibility wrappers.

## Scripts

| Script | What It Checks | Current Status |
|---|---|---|
| `run_all.py` | canonical suite-registry benchmark launcher | canonical operational entry point |
| `jax/bench_domain.py` | Release-gate domains `bayesian`, `optimization`, and `survey` on representative current-API inputs | current; supports `--json` |
| `jax/bench_simulation.py` | Throughput of the current `agent_sim` executor (`PureExecutor` + `TaxationMechanism`) | current; supports `--json` |
| `lex/benchmark_lex_llm_steady_state.py` | steady-state Lex SPO LLM throughput probe | manual/research |
| `lex/benchmark_lex_llm_sweep.py` | sequential config sweep over the Lex steady-state benchmark | manual/research |

## Role in the System

- canonical tools-facing launcher for the benchmark registry;
- supporting engineering JAX/Lex smoke probes;
- local source of baseline measurements for `tests/unit/foundry/benchmarks/*`.
- canonical `run-all.py` writes reports to `tools/research/benchmarks/_reports/` unless `BENCH_JSON_DIR` overrides it.

## Limitations

- Canonical suite execution uses `run_all.py`, `run_all_benchmarks.sh`, and `polisyos-tools benchmarks run-all` under `tools/research/benchmarks/`;
- JAX entry points call the shared `apply_jax_env_defaults()` before importing JAX;
  backend selection is still determined by the existing helper and the operator's environment.
- The root `benchmarks/` remains a backend library/reporting and compatibility layer, not a user-facing entry point;
- Measurements vary by CPU/GPU backend, so regression comparisons should keep the JSON output alongside the environment in which it was produced.

## Examples

```bash
uv run polisyos-tools benchmarks run-all --help
PYTHONPATH=src:. python3 tools/research/benchmarks/jax/bench_domain.py --repeat 3
PYTHONPATH=src:. python3 tools/research/benchmarks/jax/bench_domain.py --repeat 3 --json
PYTHONPATH=src:. python3 tools/research/benchmarks/jax/bench_simulation.py --agents 20000 --steps 24
```
