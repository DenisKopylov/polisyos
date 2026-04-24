# ADR-0109: IR Transport and Interoperability Bridges

- Status: accepted
- Date: 2026-04-13
- Related: ADR-0005, ADR-0098, ADR-0104, ADR-0108

## Context

IR contracts were designed around canonical JSON and CAS stability, but Phase 4
requires a clearer answer for:

- incremental updates versus full artifact replacement;
- binary transport for large payload families;
- streaming ingestion for observation-heavy flows;
- standards-aligned export to provenance and external data ecosystems;
- bridge contracts for causal tooling without taking hard runtime dependencies
  on every external library.

Without an explicit policy, binary or delta transport would be introduced
piecemeal and external adapters would infer semantics from implementation
details.

## Decision

### 1. Transport stays JSON-first

Canonical JSON remains the compatibility anchor for all IR payloads. Binary
transport is optional and must be attached to a JSON manifest that preserves
schema name/version, CAS identity, and delta semantics.

### 2. Observation record batches are the pilot binary family

The first optional-binary family is `observation_record_batch`, modeled by:

- `ObservationBinaryBatchArtifact`
- `ArtifactDeltaEnvelope`
- `IncrementalRelinkManifest`
- `ObservationStreamUpdate`

Arrow IPC stream is the pilot format because it matches large tabular
observation batches and append/update flows better than protobuf/msgpack or
FlatBuffers for this family.

### 3. Incremental relinking is explicit

Delta artifacts do not imply global recomposition. Producers must emit an
`IncrementalRelinkManifest` listing affected slots, mechanisms, constraints, and
queries, plus a `requires_full_relink` escape hatch when localized relinking is
unsafe.

### 4. Bridge contracts are contract-first, dependency-light

We provide bridge contracts and pure-Python conversions for:

- PROV-O aligned world provenance (`polisyos.ir.world.prov_o`)
- SDMX / DDI / FHIR / CDISC observation mappings (`polisyos.ir.observation.bridges`)
- DoWhy / EconML / CausalNex / pgmpy / Tigramite graph exchange
  (`polisyos.ir.analytics.ecosystem_bridges`)

The IR layer does not import those external libraries directly; adapters may
consume the bridge contracts in downstream packages.

## Consequences

### Positive

- Large observation payloads have a documented binary and streaming story.
- Delta application and incremental relinking become explicit reviewable
  contracts instead of hidden implementation behavior.

- Provenance export is interpretable through a standard ontology mapping.
- External causal tooling can integrate through deterministic bridge payloads
  without hard-coupling those libraries into IR.

### Trade-offs

- Producers now have to maintain both manifest and sidecar semantics.
- Bridge contracts intentionally stop short of full round-trip equivalence for
  every external standard; adapter packages still own ecosystem-specific edge
  cases.

## Rejected alternatives

- **Binary-first IR**: rejected because it would weaken canonical JSON and CAS
  reviewability.

- **Implicit relinking after every delta**: rejected because it hides cost and
  invalidation boundaries.

- **Direct library dependencies in IR**: rejected because it would inflate the
  compatibility surface and make tooling/runtime imports less predictable.
