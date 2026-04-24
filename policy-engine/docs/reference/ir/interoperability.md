# IR Interoperability

Related reference: [IR Schema Catalog](schema-catalog.md), [Schemas](../schemas.md). Related ADRs: [0108](../../adr/0108-ir-schema-catalog-and-reflection.md), [0109](../../adr/0109-ir-transport-and-interoperability-bridges.md).

> Reflection, transport, and bridge surfaces that let external tooling understand and exchange IR artifacts without manual grep.

Freshness: 2026-04-17
Owner: `@ir-owners`
Source of truth: `src/polisyos/ir/schema_catalog.py`, `src/polisyos/ir/artifacts/transport.py`, `src/polisyos/ir/world/prov_o.py`, `src/polisyos/ir/observation/bridges.py`, `src/polisyos/ir/analytics/ecosystem_bridges.py`
Source plan phase: D1-L4 Phase 4 reflection, schema catalog, transport, streaming, and ecosystem bridges.

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

## Validation Hooks

| Surface                                     | Source of truth                                                                            | Evidence                                                                                                            |
| ------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| Reflection catalog and generated references | `src/polisyos/ir/schema_catalog.py`, `tools/diagnostics/generate_ir_reference_catalog.py`  | `tests/ir/test_schema_catalog.py`, [IR Schema Catalog](schema-catalog.md)                                           |
| JSON-first transport and streaming pilot    | `src/polisyos/ir/artifacts/transport.py`                                                   | `docs/contracts/E2_11_IR_TRANSPORT_STREAMING_V1_0.md`, `docs/adr/0109-ir-transport-and-interoperability-bridges.md` |
| PROV-O mapping                              | `src/polisyos/ir/world/prov_o.py`                                                          | generated anchors in [IR Schema Catalog](schema-catalog.md#polisyos-ir-world-prov-o-provodocument)                  |
| Observation and causal bridges              | `src/polisyos/ir/observation/bridges.py`, `src/polisyos/ir/analytics/ecosystem_bridges.py` | `tests/ir/test_interoperability_bridges.py`                                                                         |
