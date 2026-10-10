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
- Each query result carries `search_mode` and `vector_refusal_code` independently of the
  optional score explanation. `search_mode="vector"` denotes the vector-enabled hybrid path;
  `search_mode="text"` keeps text matches as candidates and carries the selected-generation or
  encoder refusal reason when vector admission is unavailable. Deterministic lookup results that
  did not run a search leave both fields unset.
- Query rows and the atomic response also carry `query_generation_context`, with an explicit
  `selected`, `absent`, `refused`, or `unknown` state. A selected context includes the persisted
  generation/profile and the live reader encoder profile checked for that query, including the
  content identity used by the compatibility check. The identity describes loaded encoder assets;
  it does not prove executable `encode` behavior, trusted provider ownership, ranking quality, or
  policy authority. Legacy list callers cannot preserve status for empty results; use the atomic
  response where query-local context matters.
- `DatasetCatalogGraph.search_datasets_with_status` returns one `DatasetSearchResponse` envelope
  containing the rows and mode/refusal from that same query, so a vector refusal remains visible
  when text fallback finds no rows. `DatasetCatalogGraph.search_datasets` and the direct
  `KnowledgeToolkit.search_datasets` method retain their legacy list return. The registered
  `search_datasets` knowledge tool uses the envelope bridge and serializes `results`,
  `search_mode`, `vector_refusal_code`, `limitation_code`, and `query_generation_context` together.
  A missing catalog or legacy reader without per-query status reports a limitation and unknown
  query context instead of an unqualified empty result.
- Measurement-root artifacts and semantic benchmark runs preserve status from the same query
  envelope; they do not reconstruct it from the graph's last-query diagnostic metrics. A v2
  semantic benchmark run carries query-local status and generation context while v1 serialization
  remains unchanged.
- **Dataset registry** - `DatasetRegistry` resolves datasets for canonical variables and P*(Z) estimates.
- **Proxy resolution** - `proxy_resolver.py` builds fallback chains when direct observations are missing.
- **Variable alignment** - `variable_alignment.py` maps canonical SKG variables onto dataset variables.
- **Derivation catalog selection** - `derivation_catalog_selection.py` strictly loads
  purpose-addressable family policies and evaluates candidates against exact metric/canonical
  owner edges plus rights, alignment, binding, and completeness evidence.
- **Semantic epoch overlay** - `CatalogAcquisitionOverlay` keeps operational
  ordinals distinct from semantic epoch identity, records a complete native
  membership relation for every baseline-union table, and exposes rows only
  after a separately persisted production receipt activates the pending
  admission. Legacy/null stamps and incomplete physical membership remain
  audit-visible but fail closed for read visibility and positive chronology.

## Public API

- `DatasetCatalogGraph`
- `DatasetRegistry`
- `proxy_resolver`
- `variable_alignment`
- `derivation_catalog_selection`
- `types.py`
- `store.py`
- `search.py`

## Current State

- Last updated: 2026-04-03
- Data Forge Phase 8 physically removed the old `polisyos.datasets` namespace;
  this package is now the canonical implementation owner.
- `variable_alignment.py` now normalizes against both the academic canonical seed and the runtime canonical registry.
- The read-only store still opens DuckDB in `read_only=True` mode and falls back to text-only search if the vector index is unavailable.
