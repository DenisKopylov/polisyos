# Fabric Tests

`tests/unit/fabric` covers the data-fabric layer: connectors, data plane,
provenance, trust, world queries, claims/docs pipelines, and the fabric-facing
parts of lex and scholar. The slice currently contains `87` `test_*.py` files.

## Purpose

- Protect the connector framework and built-in sources.
- Keep provenance, trust, quality, semantic-diff, and world materialization
  behavior stable.

- Validate the document, claim, legal, and scholar-facing fabric pipelines that
  upstream subsystems depend on.

## Where To Start

- [`../../src/polisyos/fabric/README.md`](../../src/polisyos/fabric/README.md)
- `connectors/` if the change touches source adapters, profiles, schema, cache,
  or resilience.

- `data_plane/` for semantic diff, cursor store, replay, and ingestion
  orchestration issues.

## Public Entrypoints

- `tests/unit/fabric/` root: `39` tests for trust, provenance, world, claims/docs,
  legal-evaluation, lex-corpus, and scholar-facing flows.

- `tests/unit/fabric/connectors/`: `36` tests for protocol compliance, registry,
  schema/type systems, transform pipeline, cache, federation, and sources.

- `tests/unit/fabric/data_plane/`: `11` tests for incremental ingestion, replay,
  watermarks, cursor store, and semantic diff.

- `tests/unit/fabric/pii/`: `1` test for PII detection behavior.

## Depends On / Depended On By

### Depends On

- [`../../src/polisyos/fabric/README.md`](../../src/polisyos/fabric/README.md)
- `src/polisyos/lex`
- `src/polisyos/scholar`
- `src/polisyos/ir`

### Depended On By

- [`../scientist/README.md`](../scientist/README.md),
  [`../scholar/README.md`](../scholar/README.md), and
  [`../data_forge/domains/catalog/README.md`](../data_forge/domains/catalog/README.md)

- The integration and local-stack flows that need connector and data-plane
  behavior to stay consistent

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: full fabric slice
uv run pytest tests/unit/fabric -q

# conceptual: focused slices
uv run pytest tests/unit/fabric/connectors -q
uv run pytest tests/unit/fabric/data_plane -q

# conceptual: integration-classified connector reference subset
uv run pytest tests/unit/fabric/connectors/reference -q -m integration
```

## Test And Verification Commands

The collect-only commands below were smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/unit/fabric -q
uv run pytest --collect-only tests/unit/fabric/connectors -q
```

## Reference Docs

- [`../../src/polisyos/fabric/README.md`](../../src/polisyos/fabric/README.md)
- [`../../src/polisyos/fabric/connectors/README.md`](../../src/polisyos/fabric/connectors/README.md)
- [`../../src/polisyos/fabric/data_plane/README.md`](../../src/polisyos/fabric/data_plane/README.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
