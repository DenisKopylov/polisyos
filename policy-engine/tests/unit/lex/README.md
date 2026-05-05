# Lex Tests

`tests/unit/lex` covers runtime Lex behavior: intervention handling, knowledge
filters, legal evaluation, and the simulator diff / mutation path. Offline
batch normalization, sharding, and corpus preprocessing tests live under
`tests/unit/data_forge/legal_batch`.

## Purpose

- Keep runtime legal evaluation, knowledge, and intervention behavior stable.
- Protect NormPack and intervention-facing outputs that downstream systems use.
- Preserve simulator determinism for diff, mutation, and impact analysis flows.

## Where To Start

- [`../../src/polisyos/lex/README.md`](../../src/polisyos/lex/README.md)
- [`../../src/polisyos/data_forge/domains/legal/batch/README.md`](../../src/polisyos/data_forge/domains/legal/batch/README.md)
- `../data_forge/legal_batch/` for extraction, sharding, and normalization issues.

## Public Entrypoints

- `tests/unit/lex/` root: `4` tests for API transport constraints, interventions,
  and knowledge-store filters.

- `tests/unit/data_forge/legal_batch/`: tests for canonicalizers, structuring, SPO
  normalization, quality reports, manifests, and sharding.

- `tests/unit/lex/legal_evaluation/`: `1` test for legal-evaluation integration.
- `tests/unit/lex/simulator/`: `3` tests for norm-pack diff, mutator semantics, and
  impact analysis.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/lex/README.md`](../../src/polisyos/lex/README.md)
- [`../../src/polisyos/data_forge/domains/legal/batch/README.md`](../../src/polisyos/data_forge/domains/legal/batch/README.md)
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
uv run pytest tests/unit/lex -q

# conceptual: focused slices
uv run pytest tests/unit/data_forge/legal_batch -q
uv run pytest tests/unit/lex/simulator -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/lex -q
```

## Reference Docs

- [`../../src/polisyos/lex/README.md`](../../src/polisyos/lex/README.md)
- [`../../src/polisyos/data_forge/domains/legal/batch/README.md`](../../src/polisyos/data_forge/domains/legal/batch/README.md)
- [`../../src/polisyos/lex/simulator/README.md`](../../src/polisyos/lex/simulator/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-05-02
