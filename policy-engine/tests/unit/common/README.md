# Common Tests

`tests/unit/common` covers the low-level `polisyos.common` helpers shared across the
repository: async bridging, config bootstrap, logging, serialization,
timestamps, and migration purity. The tracked `test_*.py` files under this
directory are the source inventory; a file count is not a count of tests
collected or executed.

## Purpose

- Keep the lowest utility layer stable for every higher subsystem.
- Catch serialization, timestamp, and bootstrap regressions early.
- Preserve the helper behavior that many other tests implicitly depend on.

## Where To Start

- `src/polisyos/common/README.md`
- `test_fast_json_serialization.py` for canonical serialization behavior.
- `serialization/test__strict_json.py` for strict JSON duplicate-key and non-finite-number behavior.
- `test__selected_artifact_intake.py` for absent-versus-refused selected-artifact intake.
- `jax_env/test__policy.py` for default and explicit JAX platform behavior.
- `migrations/test_base.py` and `migrations/test_manifest.py` for migration ownership behavior.
- `test_text.py` for Common whitespace normalization.
- `test_config_bootstrap.py` and `test_async_tools.py` for bootstrap/runtime
  helper issues.

## Test Module Inventory

The canonical inventory is the tracked `test_*.py` files under this directory,
including nested test folders. From `policy-engine/`, list those source files
with:

```bash
git ls-files tests/unit/common | rg '(^|/)test_[^/]+\.py$'
```

This lists test modules; it does not collect or execute test cases.

## Depends On / Depended On By

### Depends On

- `src/polisyos/common/README.md`
- `src/polisyos/common/migrations`
- `tests/conftest.py`

### Depended On By

- Nearly every subsystem test slice under [`../README.md`](../README.md)
- Core/runtime verification that reuses bootstrap, serialization, and timing
  helpers

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full common slice
uv run pytest tests/unit/common -q

# conceptual: targeted probes
uv run pytest tests/unit/common/test_serialization_properties.py -q
uv run pytest tests/unit/common/test_config_bootstrap.py -q
```

## Test And Verification Commands

The collect-only command below is a historical receipt dated `2026-04-17`; it
was not rerun for this documentation correction.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/common -q
```

## Reference Docs

- `src/polisyos/common/README.md`
- `tests/TESTING_POLICY.md`
- `tests/unit/README.md`

## Last Updated

2026-10-14
