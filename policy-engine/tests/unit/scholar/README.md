# Scholar Tests

`tests/unit/scholar` covers the knowledge-bundle orchestration layer built around
`polisyos.scholar`: freshness handling, search planning/providers, and service
bootstrap. The slice currently contains `6` `test_*.py` files.

## Purpose

- Keep scholar freshness and search orchestration behavior stable.
- Protect the bootstrap and service wiring used by knowledge-bundle flows.
- Provide a small focused slice separate from the larger fabric/scientist test
  surfaces.

## Where To Start

- [`../../src/polisyos/scholar/README.md`](../../src/polisyos/scholar/README.md)
- `search/` for planner/provider/fetcher issues.
- `test_api_web_bootstrap.py` and `test_freshness.py` for service bootstrap and
  freshness semantics.

## Public Entrypoints

- `tests/unit/scholar/test_api_web_bootstrap.py`
- `tests/unit/scholar/test_freshness.py`
- `tests/unit/scholar/search/test_fetcher_security_cache.py`
- `tests/unit/scholar/search/test_planner.py`
- `tests/unit/scholar/search/test_providers.py`
- `tests/unit/scholar/search/test_service_jobs_tools.py`

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/scholar/README.md`](../../src/polisyos/scholar/README.md)
- `src/polisyos/scholar/search`
- `src/polisyos/fabric`

### Depended On By

- [`../scientist/README.md`](../scientist/README.md) when scholar-backed
  knowledge acquisition participates in workflows

- [`../fabric/README.md`](../fabric/README.md) for docs/claims handoff paths

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: scholar slice
uv run pytest tests/unit/scholar -q

# conceptual: search-focused subset
uv run pytest tests/unit/scholar/search -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/scholar -q
```

## Reference Docs

- [`../../src/polisyos/scholar/README.md`](../../src/polisyos/scholar/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)
- [`../README.md`](../README.md)

## Last Updated

2026-04-17
