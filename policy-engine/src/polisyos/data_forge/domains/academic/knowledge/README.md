# Academic Knowledge (`polisyos.data_forge.domains.academic.knowledge`)

`polisyos.data_forge.domains.academic.knowledge` is the read-only query layer
over the academic DuckDB/SKG store. It serves literature search, causal
evidence lookup, prior construction, and transportability-aware parameter
selection.

## Role in System

- **Depends on:** the graph materialized by
  `polisyos.data_forge.domains.academic.batch.graph_builder` and publish stages.
- **Used by:** runtime search, transportability selection, and downstream decision support.
- **Boundary function:** keeps graph/query logic read-only and separate from batch graph construction.

## Key Concepts

- **Hybrid search** - `ScholarKnowledgeGraph` combines text and vector retrieval.
- **SKG queries** - `SKGQuery` reads the `ac_skg_*` tables for edge and parameter evidence.
- **Parameter selection** - `ParameterSelector` scores candidates for the current context.
- **Canonical variables** - `VariableCanonizer` and the runtime registry normalize naming across domains.
- **Versioning** - `SKGVersionManager` handles retractions and confidence recomputation.

## Public API

- `ScholarKnowledgeGraph`
- `CanonicalVariableResolver`
- `ResolutionResult`
- `ParameterSelector`
- `SKGQuery`
- `ParameterCandidate`
- `EdgeSupportRecord`
- `EdgeTransportRecord`
- `SKGVersionManager`
- `VariableCanonizer`

## Current State

- Last updated: 2026-04-03
- Data Forge Phase 8 physically removed the old `polisyos.academic` namespace;
  this package is now the canonical implementation owner.
- `runtime_canonical_registry.py` now exposes `runtime_canonical_entries()`, `runtime_canonical_names()`, and `runtime_approved_synonyms()`.
- `variable_canonizer.py` still layers exact-match, cache, fuzzy, and slug fallback resolution on top of the canonical registry.
