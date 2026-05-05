# tools/research/benchmarks

Canonical benchmark entry points live under `tools/research/benchmarks/`; the root
`benchmarks/` package remains a backend library plus compatibility wrappers.

## Скрипты

| Скрипт | Что проверяет | Текущее состояние |
|---|---|---|
| `run_all.py` | canonical suite-registry benchmark launcher | canonical operational entry point |
| `jax/bench_domain.py` | release-gate домены `bayesian`, `optimization`, `survey` на репрезентативных current-API входах | актуален, умеет `--json` |
| `jax/bench_simulation.py` | пропускная способность текущего `agent_sim` executor (`PureExecutor` + `TaxationMechanism`) | актуален, умеет `--json` |
| `lex/benchmark_lex_llm_steady_state.py` | steady-state Lex SPO LLM throughput probe | manual/research |
| `lex/benchmark_lex_llm_sweep.py` | sequential config sweep over the Lex steady-state benchmark | manual/research |

## Роль в системе

- canonical tools-facing launcher for the benchmark registry;
- вспомогательные инженерные JAX/lex smoke probes;
- локальный источник baseline-замеров для `tests/unit/foundry/benchmarks/*`.
- canonical `run-all.py` writes reports to `tools/research/benchmarks/_reports/` unless `BENCH_JSON_DIR` overrides it.

## Ограничения

- canonical suite execution идет через `run_all.py`, `run_all_benchmarks.sh` и `polisyos-tools benchmarks run-all` внутри `tools/research/benchmarks/`;
- root `benchmarks/` остается backend library/reporting layer и compatibility layer, а не пользовательской точкой входа;
- замеры чувствительны к CPU/GPU backend, поэтому для регрессионных сравнений лучше хранить JSON-вывод рядом с окружением, на котором он был получен.

## Примеры

```bash
uv run polisyos-tools benchmarks run-all --help
PYTHONPATH=src:. python3 tools/research/benchmarks/jax/bench_domain.py --repeat 3
PYTHONPATH=src:. python3 tools/research/benchmarks/jax/bench_domain.py --repeat 3 --json
PYTHONPATH=src:. python3 tools/research/benchmarks/jax/bench_simulation.py --agents 20000 --steps 24
```
