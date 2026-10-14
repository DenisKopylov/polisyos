# Fabric Data Plane

Related explanation: [Data Fabric](../../explanation/data-fabric.md). Related
surfaces: [lineage](lineage.md), [quality](quality.md),
[processing guarantees](processing-guarantees.md), and
[time travel](time-travel.md).

Freshness: 2026-10-14
Owner: `@fabric-owners`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `policy-engine/src/polisyos/fabric/data_plane/`,
  `policy-engine/src/polisyos/fabric/ingestion/ingestion.py`,
  `policy-engine/src/polisyos/fabric/docs/`,
  `policy-engine/src/polisyos/fabric/claims/`,
  `policy-engine/src/polisyos/fabric/world/`, and the tests named below.
Evidence level: implementation and focused test behavior inspected at the
source pin. Tests use local fixtures, test connectors, and injected
dependencies; they do not establish live-provider readiness or source truth.
Test status: tests were inspected but not run in this documentation pass.

The data plane provides connector-ingestion modes, cursor and streaming state,
quarantine, and optional snapshot assembly. It does not make every Fabric input
follow one fetch-to-world-table path. Connector ingestion writes source and
transform evidence to CAS. Document and claim producers separately emit world
facts/events and fact-log segments; world-store materialization and query are
separate consumers. A connector `EvidenceBundleRef` or `DataSnapshotRef` does
not by itself represent a world fact.

## Intended composition

The broader target in `policy-engine/docs/plans/active/FABRIC_AUDIT_REMEDIATION_PLAN.md`
is a reusable path from ingestion through materialization and query, with
operational traces and lineage that answer origin and impact questions. That is
the intended composition, not a claim that the generic bridge is currently
wired; the implementation evidence and gap state below describe what this pin
demonstrates.

## Bounded paths and evidence

| Path | Producer and persisted artifacts | Consumer or boundary | Evidence at this pin |
| --- | --- | --- | --- |
| Connector ingestion | `run_connectors_ingestion` fetches manifest datasets, applies configured transforms and sanitization, and can persist payload artifacts, a connector `ProvenanceCoreGraph`, and an `EvidenceBundleRef` in CAS. | Returns evidence references; it does not generally emit world facts or materialize world tables. | `policy-engine/tests/unit/fabric/connectors/test_integration.py` exercises test-connector ingestion and CAS evidence. `policy-engine/tests/unit/fabric/connectors/test_ingestion_fetch_activity_contract.py` checks connector provenance fields and merging a transform graph built with `FabricLineageTracker`. |
| Orchestrated snapshot | `run_orchestrated_ingestion` calls connector ingestion, then optionally reads its persisted evidence bundle and writes a `DataSnapshot`. The snapshot uses the first `EvidenceBundle.sources` entry as `data_ref`. | The snapshot builder writes `fabric.quality_report` metadata (source, dataset count, evidence notes); this wrapper does not compute a full content-quality assessment. | `policy-engine/tests/unit/fabric/data_plane/test_orchestrator.py` patches the ingestion producer, then verifies snapshot assembly from a persisted evidence bundle. That test proves the assembly step, not an unmocked connector-to-snapshot run. |
| Streaming-window snapshot | `run_streaming_windowed` fetches chunks, writes a streaming run manifest and can write evidence and a snapshot to CAS. | The snapshot's `data_ref` is the run manifest; this is a streaming-mode chain, not a generic connector-to-world-fact bridge. | `policy-engine/tests/unit/fabric/data_plane/test_r13_ingestion_store_custody.py::test_streaming_snapshot_uses_owner_tenant_store_for_the_full_artifact_chain` runs a local JSONL `EventStreamConnector` through persisted chunks, manifest, evidence bundle, and snapshot, and checks tenant-scoped reads. This is a bounded fixture-backed demonstration. |
| Document and claim processing | Document stages start from raw bytes and create document artifacts; claim stages consume their own source artifacts and persist claim outputs. These producers append their own world facts/events and fact-log segments. | World-store materialization and query consume those segments. Connector evidence is not automatically routed into these producers. | `policy-engine/tests/unit/fabric/test_docs_pipeline.py` covers document bytes through fact-log materialization; `policy-engine/tests/unit/fabric/test_claims_pipeline.py` covers claim persistence and materialization. |
| Stream runtime | `process_stream_dataset` coordinates a streaming session, windows, checkpoints, schema binding, deduplication, and backpressure; compatible schema changes can persist CDC events. | This is a Fabric streaming path. It does not establish an all-domain Data Forge scheduler or a world-fact sink for generic connector rows. | `policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py` covers checkpoint/restart and boundary behavior, including persisted CDC events and quarantine cases. |

The runtime control service routes `run_data_ingestion` to the supported mode
entrypoints in `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py`.
`policy-engine/tests/unit/runtime/http/test_e2e_ingestion.py` patches the
ingestion producer, so that test demonstrates request dispatch rather than a
live-provider-to-persisted-result flow.

## Execution modes

| Entry point | Bounded behavior | Focused evidence |
| --- | --- | --- |
| `run_batch_incremental` | Uses cursor state and a connector's declared incremental-fetch capability to select a version for the next request. Watermark policy is connector/version input, not a universal source update clock. | `policy-engine/tests/unit/fabric/data_plane/test_modes.py`, `policy-engine/tests/unit/fabric/data_plane/test_cursor_store.py`, and `policy-engine/tests/unit/fabric/data_plane/test_watermark.py`. |
| `run_record_mode` and `run_replay_mode` | Record mode captures the configured HTTP response witness; replay mode uses recorded fixtures and does not fall back to a live fetch when replay fails. | `policy-engine/tests/unit/fabric/data_plane/test_modes.py` exercises fixture replay, failure behavior, and recorded response bytes. |
| `run_streaming_windowed` | Persists fetched chunks and can assemble a manifest, evidence bundle, and snapshot. | The full local-source artifact chain is tested by the named `test_streaming_snapshot_uses_owner_tenant_store_for_the_full_artifact_chain` case above. |
| `process_stream_dataset` | Runs a streaming session with resumable state, dedupe/frontier handling, capacity limits, and schema-bound CDC handling. | `policy-engine/tests/unit/fabric/data_plane/test_streaming_runtime.py` contains focused restart, backpressure, frontier, and CDC cases; these are behavioral tests, not deployment-readiness evidence. |

Related components have narrower contracts: `policy-engine/src/polisyos/fabric/data_plane/quarantine.py`
persists, reports, and reprocesses quarantine records;
`policy-engine/src/polisyos/fabric/data_plane/semantic_diff.py` compares
historical rows under a configured grain; and
`policy-engine/src/polisyos/fabric/data_plane/benchmarks.py` produces benchmark
reports. Their tests do not, on their own, establish a cross-component
governance or materialization gate.

## Provenance and quality limits

Connector ingestion builds and persists a provenance graph for its fetch
activity and merges transform-stage lineage when a transform pipeline is
configured. Transform instrumentation can also emit spans and graph-size
metrics. The persisted graph describes the source and transform relationships
that this ingestion path records; it is not automatically extended with every
later materialized column, claim, world fact, or query result. See
[Fabric lineage](lineage.md) for the distinction between graph-builder methods
and producer/consumer wiring.

`DataFitnessReport` and connector quality indicators are separate quality
surfaces. The metadata-only report built by `run_orchestrated_ingestion` is not
a complete quality assessment. Likewise, a semantic-diff result is a comparison
artifact; the focused tests in `policy-engine/tests/unit/fabric/test_semantic_diff.py`
do not demonstrate a universally wired materialization-regression gate.

## Capability boundaries

| Claim | State at this pin | Evidence-based boundary |
| --- | --- | --- |
| Generic connector-result-to-world-fact and world-table path | `bridge_missing` | Connector ingestion writes CAS evidence; document and claim producers write their own world facts and segments. No general connector-result consumer bridge is established by the inspected path. |
| Automatic source-to-query lineage across ingestion, world materialization, claims, and query | `semantic_test_missing` | `FabricLineageTracker` can represent those nodes, but the all-node trace test manually calls the tracker methods. Connector ingestion captures fetch/transform lineage only. |
| Live provider readiness or source truth | `not_established` | The cited fixtures use local or test connectors and prove the named code paths only. |

These boundaries keep the snapshot, world-store, and lineage claims tied to the
producer, persisted artifact, and consumer demonstrated by the code and tests.

## API Reference

::: polisyos.fabric.data_plane.orchestrator

::: polisyos.fabric.data_plane.modes

::: polisyos.fabric.data_plane.watermark

::: polisyos.fabric.data_plane.quarantine

::: polisyos.fabric.data_plane.streaming

::: polisyos.fabric.data_plane.semantic_diff

::: polisyos.fabric.data_plane.benchmarks

::: polisyos.fabric.docs.ingestion

::: polisyos.fabric.docs.normalize

::: polisyos.fabric.docs.structure

::: polisyos.fabric.docs.chunking

::: polisyos.fabric.docs.types

::: polisyos.fabric.claims.extraction

::: polisyos.fabric.claims.normalize

::: polisyos.fabric.claims.types

::: polisyos.fabric.claims.conflicts.resolve

::: polisyos.fabric.claims.conflicts.types

::: polisyos.fabric.world.query
