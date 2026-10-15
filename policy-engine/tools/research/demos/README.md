# tools/demos

Demonstration and research scenarios. These are not production gates or part of the CI path.

Demo commands can be discovered with `polisyos-tools demos --help`, but the unified CLI intentionally blocks legacy/quarantined scenarios unless `--allow-deprecated` is explicitly provided.

## Role

- quick experiments with ideas and APIs;
- manual hypothesis checks for `foundry/fabric`.

## Scripts

| Script | Purpose | Current Status |
|---|---|---|
| `run_laffer_demo.py` | JAX/Optax demo of the Laffer curve | partially current; manual run |
| `run_foundry_ws9_frontier_demo.py` | Smoke walkthrough for WS-9 frontier causal/ML/policy methods | current; manual run |
| `run_export_demo.py` | Exports simulation data to DuckDB | deprecated stub; legacy `foundry.engine` import removed |
| `run_mechanism_design.py` | E2E differentiable mechanism design | legacy imports and path drift |
| `run_udf_query_demo.py` | Example UDF panel/snapshot queries | requires missing `polisyos.fabric.udf.*` |
| `run_udf_hybrid_demo.py` | DuckDB + graph UDF hybrid | requires missing `polisyos.fabric.udf.*` and `polisyos.fabric.io.graph_store` |

## Quarantine policy

- `run_udf_query_demo.py` and `run_udf_hybrid_demo.py` are in legacy
  quarantine because their dependencies are absent from the current package.
- `run_export_demo.py` is now an explicit deprecated stub with no import of the removed
  `foundry.engine`; `run_mechanism_design.py` remains a deprecated reference
  script until it is rewritten against current Foundry contracts.
- Quarantine metadata and replacements are recorded in
  [`tools/archive/README.md`](../../archive/README.md) and
  `tools.registry`.

## Repository Connections

- historically use `src/polisyos/foundry/*`, `src/polisyos/fabric/*`, and `data/*`
- are not configured as required quality gates in GitHub Actions

## Notes

- These scripts are useful as references and examples, but not as the source of truth for the compatibility matrix.
- JAX entry points call the shared `apply_jax_env_defaults()` before importing Equinox/JAX;
  backend selection is still determined by the existing helper and the operator's environment.
- Before running any scenario, check that its imports match the current `src/polisyos` tree.
