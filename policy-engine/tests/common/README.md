# Common Tests

`tests/common` covers the low-level `polisyos.common` helpers shared across the
repository: async bridging, config bootstrap, logging, serialization,
timestamps, and migration purity. The slice currently contains `7`
`test_*.py` files.

## Purpose

- Keep the lowest utility layer stable for every higher subsystem.
- Catch serialization, timestamp, and bootstrap regressions early.
- Preserve the helper behavior that many other tests implicitly depend on.

## Where To Start

- [`../../src/polisyos/common/README.md`](../../src/polisyos/common/README.md)
- `test_serialization_properties.py` for canonical serialization behavior.
- `test_config_bootstrap.py` and `test_async_tools.py` for bootstrap/runtime
  helper issues.

## Public Entrypoints

- `tests/common/test_async_tools.py`
- `tests/common/test_config_bootstrap.py`
- `tests/common/test_fast_json_serialization.py`
- `tests/common/test_logger.py`
- `tests/common/test_migrations_purity.py`
- `tests/common/test_serialization_properties.py`
- `tests/common/test_timestamps.py`

## Depends On / Depended On By

**Depends on**

- [`../../src/polisyos/common/README.md`](../../src/polisyos/common/README.md)
- `src/polisyos/common/migrations`
- `tests/conftest.py`

**Depended on by**

- Nearly every subsystem test slice under [`../README.md`](../README.md)
- Core/runtime verification that reuses bootstrap, serialization, and timing
  helpers

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full common slice
uv run pytest tests/common -q

# conceptual: targeted probes
uv run pytest tests/common/test_serialization_properties.py -q
uv run pytest tests/common/test_config_bootstrap.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/common -q
```

## Reference Docs

- [`../../src/polisyos/common/README.md`](../../src/polisyos/common/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../README.md`](../README.md)

## Last Updated

2026-04-17
