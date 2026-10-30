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
- **Selected work vectors** - `ScholarKnowledgeStore` recomputes the complete
  current work ID/title/abstract projection against the selected generation
  basis and verifies that its native HNSW labels and vectors match the selected
  matrix. It rechecks the resolved generation before cache reuse and exposes
  refusal through `vector_index_refusal_reason`. A legacy flat pair is not
  admitted as a selected source. These checks do not attest the matrix's
  producer, establish query-encoder compatibility, or make the high-level
  hybrid search return a typed refusal envelope.
- **SKG queries** - `SKGQuery` reads the `ac_skg_*` tables for edge and parameter evidence.
- **Parameter selection** - `ParameterSelector` scores candidates for the current context.
- **Canonical variables** - `VariableCanonizer` and the runtime registry normalize naming across domains.
- **Versioning** - `SKGVersionManager` handles retractions and confidence recomputation.
- **Retained source identity** - `skg_identity_bridge.py` persists and replays the
  selected references against an independently supplied snapshot and selection.
  `skg_source_population.py` reads the complete retained numeric-reference
  projection for source discovery. Both are exposed through
  `polisyos.data_forge.read_api.academic`. Snapshot equality establishes stored
  identity only; literal target matches establish neither semantic coverage nor
  scientific eligibility. Source authenticity, causal grounding and calibration
  authority remain unestablished.
- **Confidence vintage** - `skg_versioning.confidence_layer_vintage` binds the accepted historical
  snapshot declaration by full-file SHA-256. `SKGQuery.confidence_layer_vintage` exposes it through
  the existing read API; confidence readers and named Runtime/copy consumers refuse forwarding via
  `require_forwardable_confidence`. Foundry returns an empty prior with the declaration in metadata.
  Values remain in the read-only source for audit. This is a known-snapshot restriction, not a
  currentness verifier: unregistered hashes and row-wise rewrites need their own binding.
- **Prepared K_ref source rows** - `PreparedSKGRead._prepare_credal_source_stream()` exposes only the
  fixed typed SKG table projections used by K_ref from the same read-only transaction whose source
  bytes and version it binds. Runtime consumes bounded typed batches; the existing
  `read_credal_source_rows()` compatibility API still returns the complete immutable row snapshot.
  Neither path exposes arbitrary SQL; known historical confidence remains refused, and
  authenticity/currentness remain unestablished.

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
- `PreparedSKGCredalSourceRows` (through `polisyos.data_forge.read_api.academic`)

## Current State

- Last updated: 2026-04-03
- Data Forge Phase 8 physically removed the old `polisyos.academic` namespace;
  this package is now the canonical implementation owner.
- `runtime_canonical_registry.py` now exposes `runtime_canonical_entries()`, `runtime_canonical_names()`, and `runtime_approved_synonyms()`.
- `variable_canonizer.py` still layers exact-match, cache, fuzzy, and slug fallback resolution on top of the canonical registry.
