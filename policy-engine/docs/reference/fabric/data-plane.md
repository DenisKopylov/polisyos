# Fabric Data Plane

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-26.
Owner: `@fabric-owners`
Source plan: `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/data_plane/**`, `src/polisyos/fabric/world_query.py`, `tests/fabric/data_plane/**`, `tests/fabric/test_{semantic_diff,lineage,world_time_travel}.py`
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)
Processing guarantees: [processing-guarantees.md](processing-guarantees.md)

The Fabric data plane coordinates ingestion modes, cursor advancement,
watermark selection, quarantine/DLQ records, streaming/CDC processing,
document/claim normalization, semantic diffs, and read-only world queries. Its
main job is to fetch once, persist evidence and provenance to CAS, materialize
world tables, and expose downstream snapshot/query artifacts without redundant
network fetches.

## Core Modules

| Module          | Responsibility                                                                                                 | D1-L2 phase |
| --------------- | -------------------------------------------------------------------------------------------------------------- | ----------- |
| `orchestrator`  | Single-call ingestion plus optional `DataSnapshot` assembly from CAS evidence                                  | Phase 1/4   |
| `modes`         | Batch incremental, record, replay, and streaming-windowed execution modes                                      | Phase 1/5   |
| `cursor_store`  | Cursor and stream checkpoint persistence                                                                       | Phase 1/5   |
| `watermark`     | Connector-family watermark extraction strategy for cursor advancement                                          | Phase 0/5   |
| `quarantine`    | CAS-backed `QuarantineRecord` storage, report, and deterministic reprocess API                                 | Phase 5     |
| `streaming`     | `StreamingSourceSession`, checkpoint recovery, processing contracts, backpressure, CDC schema-change events    | Phase 5/8   |
| `semantic_diff` | Historical row comparison and schema-evolution regression reports                                              | Phase 4     |
| `benchmarks`    | Ingestion, stream, materialization, and query benchmark reports with latency/correctness counters              | Phase 5/8   |
| `docs.*`        | Raw document ingest, text normalization, anchor extraction, and chunking with `DocMeta` lineage                | Phase 0/3   |
| `claims.*`      | Claim extraction, canonicalization, conflict resolution, trust scoring, and evidence bundles                   | Phase 0/3/5 |
| `world_query`   | Governed read-only query helpers over materialized world tables with column masking                            | Phase 3/4   |

## Execution Modes

| Function                   | Mode               | Purpose                                                                                                                                     |
| -------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `run_batch_incremental()`  | Batch incremental  | Uses `CursorStore` and watermark policy to resume dataset fetches                                                                           |
| `run_record_mode()`        | Record             | Captures HTTP traffic into CAS-backed replay fixtures                                                                                       |
| `run_replay_mode()`        | Replay             | Re-runs ingestion from captured fixtures without network access                                                                             |
| `run_streaming_windowed()` | Streaming windowed | Persists chunked fetches for larger paginated sources                                                                                       |
| `process_stream_dataset()` | Stream runtime     | Polls `StreamingSourceSession`, checkpoints offsets/dedupe keys, applies backpressure, persists windows, and emits CDC schema-change events |

## Watermark Policies

| Policy               | Use case                                         |
| -------------------- | ------------------------------------------------ |
| `TimestampWatermark` | Default for most HTTP statistical APIs           |
| `ETagWatermark`      | Useful for SPARQL or versioned content endpoints |
| `RevisionWatermark`  | Revision-number based sources                    |
| `OffsetWatermark`    | Pagination / row-offset progress tracking        |

## Quality And Lineage Artifacts

The current examples are executable tests, not hand-written sample payloads:

| Artifact or API                             | Current example                                                                                                                                                                                                                                    |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `QualityIndicators` and `DataFitnessReport` | `tests/fabric/test_quality_indicators.py` covers finite quality bounds, DuckDB identifier safety, injected metrics, and `DataFitnessReport.from_dict()` diagnostics                                                                                |
| `FabricLineageTracker`                      | `tests/fabric/test_lineage.py` builds graph `graph.lineage.test` from `worldbank.wdi` source field `gdp_local` to materialized table `world_gdp`, claim `claim-1`, world fact `fact-1`, query `query-1`, OpenLineage JSON, and visualization graph |
| Quarantine records                          | `tests/fabric/data_plane/test_quarantine.py` persists `transform_error`, `non_finite_metric`, and `poison_stream_message` records with downstream impacts and reprocess results                                                                    |
| CDC schema-change events                    | `tests/fabric/data_plane/test_streaming_runtime.py` asserts persisted CAS kind `fabric.cdc_schema_change` when stream rows introduce `new_field`                                                                                                   |
| Semantic diff reports                       | `tests/fabric/test_semantic_diff.py` covers historical comparison paths used by quality/materialization regression checks                                                                                                                          |

Dedicated reference pages split these surfaces by responsibility:

- [schema-compatibility.md](schema-compatibility.md) for connector contracts,
  schema diffs, and governance snapshots.

- [lineage.md](lineage.md) for `FabricLineageTracker`, traces, impact analysis,
  and export formats.

- [quality.md](quality.md) for quality indicators, dataset validation, drift,
  anomaly, and fitness-report semantics.

- [time-travel.md](time-travel.md) for bitemporal queries, snapshots, branches,
  merge policies, and retention.

## Schema And Artifact Gates

| Gate                                                                                                               | Purpose                                                                                                                                                          |
| ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out .tmp/fabric-schema-governance.json` | Validates Fabric connector contract evolution against `schemas/snapshots/fabric/connector_contract_registry.json` and writes impacted-surface/migration evidence |
| `uv run python tools/connectors/check_contracts.py --check`                                                        | Validates the legacy connector contract snapshot at `schemas/snapshots/connectors/contracts.json`                                                                |
| `uv run --extra ml polisyos-tools diagnostics gen-schema --check`                                                  | Validates Fabric ABI snapshots such as `schemas/snapshots/fabric/edge_kind.schema.json` and `node_kind.schema.json`                                              |

## Orchestration Notes

<!-- markdownlint-disable MD060 -->

| Item                   | Detail                                                                                                                            |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Double-fetch avoidance | `run_orchestrated_ingestion()` builds `DataSnapshot` from persisted evidence rather than refetching raw data                      |
| Cursor advancement     | `run_batch_incremental()` resolves connector-family watermark policy and stores cursor state in CAS                               |
| Replayability          | Record/replay mode uses `ReplayStore` fixtures so connector regressions can be reproduced without hitting live APIs               |
| Quarantine isolation   | Bad transform rows and non-finite metric rows can be isolated without losing the whole batch                                      |
| Streaming recovery     | `process_stream_dataset()` persists paused/closed checkpoints with offsets and dedupe keys so replay can resume deterministically |
| Guarantee honesty      | Streaming and distributed execution publish explicit processing guarantees, dedupe windows, replay retention, and trust metadata |

<!-- markdownlint-enable MD060 -->

## Validation Anchors

```bash
uv run pytest tests/fabric/data_plane/test_modes.py tests/fabric/data_plane/test_orchestrator.py -q
uv run pytest tests/fabric/data_plane/test_cursor_store.py tests/fabric/data_plane/test_record_replay.py -q
uv run pytest tests/fabric/data_plane/test_quarantine.py tests/fabric/test_ingestion_quarantine.py -q
uv run pytest tests/fabric/data_plane/test_streaming_runtime.py tests/fabric/data_plane/test_streaming_windowed.py -q
uv run pytest tests/fabric/test_quality_indicators.py tests/fabric/test_lineage.py -q
uv run pytest tests/fabric/test_world_materialization.py tests/fabric/test_world_time_travel.py -q
```

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

::: polisyos.fabric.world_query
