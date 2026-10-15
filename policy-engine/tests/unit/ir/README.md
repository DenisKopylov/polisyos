# IR Tests

`tests/unit/ir` covers the intermediate-representation layer: Trinity loading,
migrations, analytics models, observation/governance contracts, and the
architectural rule that IR remains mostly independent from `core`. At source
snapshot `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, a full tracked-path census
under `tests/unit/ir/` counted `172` files whose basename matches `test_*.py`.
That path count is not a pytest collection or execution result; tests were not
run during this documentation review.

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

## Where Tests Are Grouped

`analytics/`, `observation/`, `governance/`, and `data/` organize focused
contract families. Other areas cover artifacts, registry, migrations, and
cross-package mirror contracts. Consult the directory tree for the current
complete grouping rather than relying on a fixed inventory here.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/ir/trinity/README.md`](../../src/polisyos/ir/trinity/README.md)
- [`../../src/polisyos/ir/analytics/README.md`](../../src/polisyos/ir/analytics/README.md)
- `src/polisyos/core/canon` for parity checks

### Depended On By

- [`../fabric/README.md`](../fabric/README.md),
  [`../foundry/README.md`](../foundry/README.md), and
  [`../scientist/README.md`](../scientist/README.md)

- Contract and migration gates that assume IR compatibility

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full IR slice
uv run pytest tests/unit/ir -q

# conceptual: targeted checks
uv run pytest tests/unit/ir/test_no_core_imports.py -q
uv run pytest tests/unit/ir/test_loaders.py -q
uv run pytest tests/unit/ir/analytics -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/ir -q
```

## Reference Docs

- [`../../src/polisyos/ir/README.md`](../../src/polisyos/ir/README.md)
- [`../../src/polisyos/ir/trinity/README.md`](../../src/polisyos/ir/trinity/README.md)
- [`../../src/polisyos/ir/analytics/README.md`](../../src/polisyos/ir/analytics/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
