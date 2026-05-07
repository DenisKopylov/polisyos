# Data Forge Unit Tests

Owner: `team-data-forge`
Last updated: 2026-05-05

## Purpose

This subtree owns unit tests for Data Forge foundation, domain pipelines,
schema quality, read API consolidation, and shim sunset coverage.

## Public API

Tests assert Data Forge package behavior through documented domain APIs,
batch commands, read API surfaces, and migration shims.

## Internal Layout

| Path | Role |
| --- | --- |
| `test_phase*.py` | Phase-level package acceptance and cutover tests. |
| `legal_batch/` | Legal batch pipeline unit tests. |
| `domains/academic/` | Academic domain tests. |
| `domains/catalog/` | Catalog domain tests. |
| `domains/ukraine/` | Ukraine domain tests. |
| `conftest.py` | Shared Data Forge test configuration. |

## Extension Points

Data Forge domain extension tests should prove `polisyos.data_forge_domains`
compatibility and use offline fixtures.

## Tests

Run from `policy-engine/`:

```bash
uv run pytest tests/unit/data_forge -q
```

## Operability Links

- `src/polisyos/data_forge/README.md`
- `src/polisyos/data_forge/domains/README.md`
- `docs/reference/fabric/product-api-integration.md`

## Known Shims/Deprecations

Shim sunset tests remain here until Data Forge legacy import paths are removed.
