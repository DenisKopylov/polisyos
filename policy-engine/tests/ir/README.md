# IR Tests

`tests/ir` covers the intermediate-representation layer: Trinity loading,
migrations, analytics models, observation/governance contracts, and the
architectural rule that IR remains mostly independent from `core`. The slice
currently contains `64` `test_*.py` files.

## Purpose

- Keep schema loading and migration behavior compatible across versions.
- Preserve analytics, causal, observation, and governance model contracts.
- Guard IR architectural boundaries such as `ir -> core` import restrictions
  and canon-hash parity expectations.

## Where To Start

- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/ir/trinity/README.md`](../../src/polisyos/ir/trinity/README.md)
- `analytics/`, `observation/`, and `governance/` when a change touches those
  contract families.

## Public Entrypoints

- `tests/ir/` root: `36` tests for loaders, migrations, canon parity,
  architectural boundaries, and core IR contracts.
- `tests/ir/analytics/`: `17` tests for analytics and policy-portfolio style
  contracts.
- `tests/ir/observation/`: `7` tests for observation and measurement surfaces.
- `tests/ir/governance/`: `2` tests for governance-facing IR models.
- `tests/ir/data/`: `2` tests for data-adjacent IR behavior.

## Depends On / Depended On By

**Depends on**

- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/ir/trinity/README.md`](../../src/polisyos/ir/trinity/README.md)
- [`../../src/polisyos/ir/analytics/README.md`](../../src/polisyos/ir/analytics/README.md)
- `src/polisyos/core/canon` for parity checks

**Depended on by**

- [`../fabric/README.md`](../fabric/README.md),
  [`../foundry/README.md`](../foundry/README.md), and
  [`../scientist/README.md`](../scientist/README.md)
- Contract and migration gates that assume IR compatibility

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full IR slice
uv run pytest tests/ir -q

# conceptual: targeted checks
uv run pytest tests/ir/test_no_core_imports.py -q
uv run pytest tests/ir/test_loaders.py -q
uv run pytest tests/ir/analytics -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/ir -q
```

## Reference Docs

- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/ir/trinity/README.md`](../../src/polisyos/ir/trinity/README.md)
- [`../../src/polisyos/ir/analytics/README.md`](../../src/polisyos/ir/analytics/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
