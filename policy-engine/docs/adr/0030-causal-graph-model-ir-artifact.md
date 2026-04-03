# ADR-0030: CausalGraphModel as IR Artifact (DAG / CPDAG / PAG)

## Status
Accepted

## Date
2026-02-28

## Context
Phase 5 introduces a first-class causal graph contract that must:
1. represent DAG, CPDAG, and PAG in one IR type;
2. preserve artifact lineage and reproducibility in CAS;
3. support downstream graph execution paths:
   - DoWhy graph input (DOT),
   - in-memory graph algorithms (`rustworkx`),
   - optional graph-query backend (Kuzu).

Before this ADR, graph handling in causal methods relied on ad-hoc string payloads and
did not provide a typed IR artifact with consistent validation and persistence.

## Decision
1. Add `polisyos.ir.analytics.causal_graph.CausalGraphModel` with:
   - `graph_type: dag | cpdag | pag`,
   - `nodes`, `edges` (`CausalEdge`),
   - provenance-friendly metadata (`skg_version_id`, edge evidence fields).
2. Standardize edge endpoint semantics through `EdgeMark`:
   - `TAIL`, `ARROW`, `CIRCLE`.
3. Persist graph as CAS JSON artifact:
   - `kind="ir.causal_graph_model"`,
   - typed ref `CausalGraphModelRef`.
4. Make DOT serialization the canonical DoWhy bridge (`to_dot()`).
5. Keep Kuzu integration optional:
   - lightweight in-model `to_kuzu(conn)`,
   - bulk materialization helper (`materialize_causal_kuzu_from_graph`) with CSV `COPY`.
6. Adopt confidence aggregation for edges via ADR-0064 formula:
   - `1 - Π(1-conf_i)^w_i`.

## Consequences
### Positive
- Single validated IR contract for structural causal graphs across discovery/inference phases.
- Deterministic, lineage-aware graph persistence compatible with existing artifact pipelines.
- Clear migration path for DoWhy inputs from legacy string payloads to typed graph artifacts.
- Optional Kuzu path for graph querying without forcing dependency in minimal installs.

### Negative
- Additional maintenance surface for graph serializers and optional backend adapters.
- Graph format migration requires SemVer management for DoWhy method contracts.

## Compatibility Notes
- `CausalGraphModelRef` is additive and backward-compatible for current IR consumers.
- DoWhy graph field rename (`graph_gml` -> `graph_dot`) is handled through versioned method contracts:
  `@1.0.0` legacy path remains available, `@2.0.0` is the primary contract.
