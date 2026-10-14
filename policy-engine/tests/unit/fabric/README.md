# Fabric Tests

`tests/unit/fabric` covers the data-fabric layer: connectors, data plane,
provenance, trust, world queries, claims/docs pipelines, and the fabric-facing
parts of lex and scholar. At source snapshot
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, a full tracked-path census under
`tests/unit/fabric/` counted `187` files whose basename matches `test_*.py`.
That path count is not a pytest collection or execution result; tests were not
run during this documentation review.

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

## Where Tests Are Grouped

`connectors/` groups protocol, registry, schema, transform, cache, federation,
and source-adapter coverage. `data_plane/` groups ingestion, replay, watermarks,
cursor-store, and semantic-diff coverage. Other focused areas include
`mirror_contracts/` and `pii/`; consult the directory tree for the current
complete grouping rather than relying on a fixed inventory here.

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
