# Bootstrap Environment Registry

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `src/polisyos/common/config.py` via `get_env_registry()`, `build_process_bootstrap_config()`, and `apply_process_bootstrap()`
Validation: `uv run pytest -q tests/common/test_config_bootstrap.py`

This page is manually maintained from the explicit bootstrap registry in
`polisyos.common.config`. It documents only the environment variables that the
common bootstrap layer resolves before runtime entrypoints initialize logging,
DuckDB, JAX, Torch, or tenant-routing defaults.

Security, CAS, and runtime HTTP toggles that are not part of explicit process
bootstrap are documented in [Configuration Reference](configuration.md).

## Bootstrap Contract

- Importing `polisyos.common.config` is side-effect free.
- Entry points that want bootstrap defaults must call
  `apply_process_bootstrap()` explicitly.
- Validation runs before bootstrap mutates process env or configures logging.
- `load_dotenv()` is optional and runs only inside `apply_process_bootstrap()`
  when `load_dotenv_file=True`.
- Logging sink setup is optional and happens once per process through
  `configure_logging()`.

## Derived Defaults

- `allowed_cores` is computed as `max(1, total_cores - max(1, int(total_cores * 0.20)))`.
- `<allowed_cores>` in the table below means that derived host-specific value.
- `XLA_FLAGS` defaults to
  `--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=<allowed_cores>`
  when not already set.

## Registry

| Variable | Owner | Default | Bootstrap behavior | Purpose |
|---|---|---|---|---|
| `LOG_LEVEL` | `common` | `DEBUG` | read-only | Console/file logging verbosity consumed by `configure_logging()` |
| `DUCKDB_MEMORY_LIMIT` | `common` | `4GB` | `setdefault` | Default DuckDB memory cap for local workloads |
| `DUCKDB_THREADS` | `common` | `<allowed_cores>` | `setdefault` | Default DuckDB worker-thread count |
| `POLISYOS_MULTI_TENANT_ENABLED` | `runtime` | `false` | `setdefault` | Default multi-tenant posture for runtime entrypoints |
| `POLISYOS_CELL_REGISTRY_PATH` | `runtime` | empty | `setdefault` | Filesystem path to the cell/tenant registry |
| `POLISYOS_DEFAULT_CELL_TIER` | `runtime` | `shared` | `setdefault` | Fallback cell tier when no tenant-specific route exists |
| `JAX_PLATFORM_NAME` | `common` | `cpu` | `set` | Safe default JAX backend |
| `JAX_PLATFORMS` | `common` | `cpu` | `set` | Preferred JAX platform order; must include `JAX_PLATFORM_NAME` |
| `JAX_ENABLE_X64` | `common` | `false` | `set` | Disable x64 unless explicitly enabled |
| `JAX_DISABLE_MOST_OPTIMIZATIONS` | `common` | `true` | `set` | Favor safer local JAX execution posture |
| `JAX_CHECK_TRACER_LEAKS` | `common` | `false` | `set` | Keep expensive tracer leak checks off by default |
| `XLA_PYTHON_CLIENT_PREALLOCATE` | `common` | `false` | `setdefault` | Avoid eager accelerator memory reservation |
| `XLA_FLAGS` | `common` | derived | `setdefault` | CPU/XLA threading posture |
| `SCIENTIST_TORCH_DEVICE` | `scientist` | `cpu` | `setdefault` | Default Torch device |
| `SCIENTIST_TORCH_NUM_THREADS` | `scientist` | `<allowed_cores>` | `setdefault` | Torch intra-op thread count |
| `SCIENTIST_TORCH_NUM_INTEROP_THREADS` | `scientist` | `1` | `setdefault` | Torch inter-op parallelism |
| `OMP_NUM_THREADS` | `scientist` | `<allowed_cores>` | `setdefault` | OpenMP thread cap |
| `OPENBLAS_NUM_THREADS` | `scientist` | `<allowed_cores>` | `setdefault` | OpenBLAS thread cap |
| `VECLIB_MAXIMUM_THREADS` | `scientist` | `<allowed_cores>` | `setdefault` | Apple vecLib thread cap |
| `NUMEXPR_NUM_THREADS` | `scientist` | `<allowed_cores>` | `setdefault` | NumExpr thread cap |

## Validation Rules

- `DUCKDB_THREADS` must remain `>= 1`.
- Derived `allowed_cores` must remain `>= 1`.
- When both are set, `JAX_PLATFORM_NAME` must be present in `JAX_PLATFORMS`.
- `SCIENTIST_TORCH_NUM_THREADS`,
  `SCIENTIST_TORCH_NUM_INTEROP_THREADS`, `OMP_NUM_THREADS`,
  `OPENBLAS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, and
  `NUMEXPR_NUM_THREADS` must parse as integers and remain `>= 1`.

## Operational Notes

- `apply_process_bootstrap()` always writes the resolved JAX keys back into the
  target env, even if they were previously unset.
- Threading, DuckDB, and tenant defaults use `setdefault`, so caller-provided
  env values win over bootstrap defaults.
- `LOG_LEVEL` affects logger sink configuration but is not written back into the
  env by bootstrap itself.
