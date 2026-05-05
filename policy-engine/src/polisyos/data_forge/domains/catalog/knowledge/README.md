# Catalog Knowledge (`polisyos.data_forge.domains.catalog.knowledge`)

`polisyos.data_forge.domains.catalog.knowledge` is the read-only discovery and
transportability layer over the dataset catalog built by the batch pipeline.

## Role in System

- **Depends on:** the DuckDB/HNSW artifacts materialized by
  `data_forge.domains.catalog.batch`.
- **Used by:** `fabric.retrieval`, `scientist`, and dataset discovery tooling.
- **Boundary function:** keeps dataset search and transportability scoring read-only.

## Key Concepts

- **Hybrid search** - `DatasetCatalogGraph` combines text and vector retrieval.
- **Dataset registry** - `DatasetRegistry` resolves datasets for canonical variables and P*(Z) estimates.
- **Proxy resolution** - `proxy_resolver.py` builds fallback chains when direct observations are missing.
- **Variable alignment** - `variable_alignment.py` maps canonical SKG variables onto dataset variables.

## Public API

- `DatasetCatalogGraph`
- `DatasetRegistry`
- `proxy_resolver`
- `variable_alignment`
- `types.py`
- `store.py`
- `search.py`

## Current State

- Last updated: 2026-04-03
- Data Forge Phase 8 physically removed the old `polisyos.datasets` namespace;
  this package is now the canonical implementation owner.
- `variable_alignment.py` now normalizes against both the academic canonical seed and the runtime canonical registry.
- The read-only store still opens DuckDB in `read_only=True` mode and falls back to text-only search if the vector index is unavailable.
