# Runtime Tests

`tests/unit/runtime` covers replay correctness, runtime manifest portability, and
the FastAPI runtime surface, with focused HTTP and mirror-contract suites.

## Purpose

- Preserve replay completeness and manifest path semantics.
- Keep runtime HTTP routes, OpenAPI behavior, and problem+json responses stable.
- Protect feedback, run-compare, review, and reissue surfaces from regressions.

## Where To Start

- [`../../../src/polisyos/runtime/README.md`](../../../src/polisyos/runtime/README.md)
- [`../../../src/polisyos/runtime/http/README.md`](../../../src/polisyos/runtime/http/README.md)
- `test_replay_runtime.py` and the `runtime/http/` directory for route-level
  debugging.

## Public Entrypoints

- `tests/unit/runtime/` root: replay completeness and manifest path portability.

- `tests/unit/runtime/http/`: tests for runs, timeline, debug, control, artifacts,
  review, auth, and OpenAPI hardening.

Runtime HTTP tests that materialize data-backed catalog readers should select a
complete test-owned source bundle through `CatalogServingSourceSelection`. The
`build_runtime_api_env_with_fixture_catalog` helper composes a published L1
snapshot with synthetic L5/L2/L3/L6 inputs below `tmp_path` when no explicit
source selection is provided. It preserves explicit selections and leaves the
normal source identity and registry checks enabled. Keep selected-path
readback and a fail-closed missing-source or publish-receipt case in each
opting-in suite; do not use a no-op retrieval service for catalog-backed requests.

- `tests/unit/runtime/mirror_contracts/`: runtime mirror-contract coverage.

- `tests/unit/runtime/http/conftest.py` for HTTP-specific fixtures.

## Depends On / Depended On By

### Depends On

- [`../../../src/polisyos/runtime/README.md`](../../../src/polisyos/runtime/README.md)
- [`../../../src/polisyos/runtime/http/README.md`](../../../src/polisyos/runtime/http/README.md)
- `src/polisyos/core/run` and `src/polisyos/core/security`
- Optional `runtime-http` dependencies such as `fastapi` and `PyJWT`

### Depended On By

- Frontend and local stack flows that assume runtime API compatibility
- [`../../integration/README.md`](../../integration/README.md) and
  [`../../performance/README.md`](../../performance/README.md)

- `tools/quality/testing/local_integration_stack.py`

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full runtime slice
uv run pytest tests/unit/runtime -q

# conceptual: runtime HTTP slice
uv run pytest tests/unit/runtime/http -q

# conceptual: targeted probes
uv run pytest tests/unit/runtime/test_replay_runtime.py -q
uv run pytest tests/unit/runtime/http/test_runs_api.py -q
uv run pytest tests/unit/runtime/http/test_control_api.py -q
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/runtime -q
uv run pytest --collect-only tests/unit/runtime/http -q
```

## Reference Docs

- [`../../../src/polisyos/runtime/README.md`](../../../src/polisyos/runtime/README.md)
- [`../../../src/polisyos/runtime/http/README.md`](../../../src/polisyos/runtime/http/README.md)
- [`../../../tools/ops_runners/runtime/README.md`](../../../tools/ops_runners/runtime/README.md)
- [`../../TESTING_POLICY.md`](../../TESTING_POLICY.md)

## Last Updated

2026-10-14
