# IR Interoperability
Related reference: [IR Schema Catalog](schema-catalog.md), [Schemas](../schemas.md). Related ADRs: [0108](../../adr/0108-ir-schema-catalog-and-reflection.md), [0109](../../adr/0109-ir-transport-and-interoperability-bridges.md).

> Reflection, transport, and bridge surfaces that let external tooling understand and exchange IR artifacts without manual grep.

## Reflection And Catalog

- `polisyos.ir.schema_catalog` exposes the unified introspection surface:
  `get_ir_schema_catalog()`, `list_ir_types()`, `get_ir_type()`,
  `inspect_ir_schema()`, and `enumerate_ir_exports()`.
- `tools/diagnostics/gen_schema.py` now regenerates both ABI snapshots and the
  generated reference pages backed by the same catalog.
- `docs/reference/ir/schema-catalog.md` is the full generated inventory of IR
  types, fields, refs, public status, docs anchors, and ABI linkage.

## Transport Strategy

- Canonical manifests stay JSON-first and continue to flow through IR canonical
  JSON + CAS hashing.
- Large observation-heavy families can opt into binary sidecars while keeping a
  JSON manifest as the compatibility anchor.
- The current pilot family is `observation_record_batch`, represented by:
  `ObservationBinaryBatchArtifact`, `ArtifactDeltaEnvelope`,
  `IncrementalRelinkManifest`, and `ObservationStreamUpdate`.
- Arrow IPC is the current binary pilot because it matches columnar
  observation/panel payloads and streaming append patterns better than
  protobuf/msgpack/FlatBuffers for this family.

::: polisyos.ir.artifacts.transport

## PROV-O Mapping

- `polisyos.ir.world.prov_o` maps `ProvAgent`, `ProvActivity`,
  `WorldObjectRef`, and `WorldEvent` into PROV-O aligned records and JSON-LD.
- The mapping keeps deterministic duration semantics and explicitly emits
  `prov:used`, `prov:wasGeneratedBy`, `prov:wasAssociatedWith`, and
  `prov:wasAttributedTo` relations.

::: polisyos.ir.world.prov_o

## Observation Standards Bridges

- `polisyos.ir.observation.bridges` provides bridge contracts for SDMX, DDI,
  FHIR, and CDISC-oriented consumers.
- These are bridge contracts, not lossy hidden converters: the output keeps the
  source `ObservationRecord` / `ObservationPanel` semantics explicit so callers
  can review mapping choices.

::: polisyos.ir.observation.bridges

## Causal Ecosystem Bridges

- `polisyos.ir.analytics.ecosystem_bridges` projects `CausalGraphModel`
  contracts into exchange shapes for DoWhy, EconML, CausalNex, pgmpy, and
  Tigramite PCMCI.
- The bridge layer is intentionally contract-first: it exposes graph/design
  payloads that external adapters can consume without forcing those libraries
  into the core IR dependency set.

::: polisyos.ir.analytics.ecosystem_bridges
