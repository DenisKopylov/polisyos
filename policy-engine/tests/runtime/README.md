# Runtime Tests

`tests/runtime` covers replay correctness, runtime manifest portability, and
the FastAPI runtime surface. The slice currently contains `31` `test_*.py`
files: `3` in the root runtime directory and `28` under `runtime/http/`.

## Purpose

- Preserve replay completeness and manifest path semantics.
- Keep runtime HTTP routes, OpenAPI behavior, and problem+json responses stable.
- Protect feedback, run-compare, review, and reissue surfaces from regressions.

## Where To Start

- [`../../src/polisyos/runtime/README.md`](../../src/polisyos/runtime/README.md)
- [`../../src/polisyos/runtime/http/README.md`](../../src/polisyos/runtime/http/README.md)
- `test_replay_runtime.py` and the `runtime/http/` directory for route-level
  debugging.

## Public Entrypoints

- `tests/runtime/` root: `3` tests for replay completeness and manifest path
  portability.

- `tests/runtime/http/`: `28` tests for runs, timeline, debug, control,
  artifacts, review, auth, and OpenAPI hardening.

- `tests/runtime/http/conftest.py` for HTTP-specific fixtures.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/runtime/README.md`](../../src/polisyos/runtime/README.md)
- [`../../src/polisyos/runtime/http/README.md`](../../src/polisyos/runtime/http/README.md)
- `src/polisyos/core/run` and `src/polisyos/core/security`
- Optional `runtime-http` dependencies such as `fastapi` and `PyJWT`

### Depended On By

- Frontend and local stack flows that assume runtime API compatibility
- [`../integration/README.md`](../integration/README.md) and
  [`../performance/README.md`](../performance/README.md)

- `tools/testing/local_integration_stack.py`

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full runtime slice
uv run pytest tests/runtime -q

# conceptual: runtime HTTP slice
uv run pytest tests/runtime/http -q

# conceptual: targeted probes
uv run pytest tests/runtime/test_replay_runtime.py -q
uv run pytest tests/runtime/http/test_runs_api.py -q
uv run pytest tests/runtime/http/test_control_api.py -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/runtime -q
uv run pytest --collect-only tests/runtime/http -q
```

## Reference Docs

- [`../../src/polisyos/runtime/README.md`](../../src/polisyos/runtime/README.md)
- [`../../src/polisyos/runtime/http/README.md`](../../src/polisyos/runtime/http/README.md)
- [`../../tools/runtime/README.md`](../../tools/runtime/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
