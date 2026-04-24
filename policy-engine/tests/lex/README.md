# Lex Tests

`tests/lex` covers the legal-corpus layer: intervention handling, knowledge
filters, batch normalization/sharding, legal evaluation, and the simulator diff
/ mutation path. The slice currently contains `45` `test_*.py` files.

## Purpose

- Keep legal corpus normalization, structuring, and quality behavior stable.
- Protect NormPack and intervention-facing outputs that downstream systems use.
- Preserve simulator determinism for diff, mutation, and impact analysis flows.

## Where To Start

- [`../../src/polisyos/lex/README.md`](../../src/polisyos/lex/README.md)
- [`../../src/polisyos/lex/batch/README.md`](../../src/polisyos/lex/batch/README.md)
- `batch/` for extraction, sharding, and normalization issues.

## Public Entrypoints

- `tests/lex/` root: `4` tests for API transport constraints, interventions,
  and knowledge-store filters.

- `tests/lex/batch/`: `37` tests for canonicalizers, structuring, SPO
  normalization, quality reports, manifests, and sharding.

- `tests/lex/legal_evaluation/`: `1` test for legal-evaluation integration.
- `tests/lex/simulator/`: `3` tests for norm-pack diff, mutator semantics, and
  impact analysis.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/lex/README.md`](../../src/polisyos/lex/README.md)
- [`../../src/polisyos/lex/batch/README.md`](../../src/polisyos/lex/batch/README.md)
- [`../../src/polisyos/lex/simulator/README.md`](../../src/polisyos/lex/simulator/README.md)
- `src/polisyos/ir/norm_pack`

### Depended On By

- [`../fabric/README.md`](../fabric/README.md) for fabric-driven legal/document
  pipelines

- [`../scientist/README.md`](../scientist/README.md) for policy/governance flows
  that consume lex artifacts

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full lex slice
uv run pytest tests/lex -q

# conceptual: focused slices
uv run pytest tests/lex/batch -q
uv run pytest tests/lex/simulator -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/lex -q
```

## Reference Docs

- [`../../src/polisyos/lex/README.md`](../../src/polisyos/lex/README.md)
- [`../../src/polisyos/lex/batch/README.md`](../../src/polisyos/lex/batch/README.md)
- [`../../src/polisyos/lex/simulator/README.md`](../../src/polisyos/lex/simulator/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
