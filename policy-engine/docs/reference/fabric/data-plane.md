# Fabric Data Plane
Related explanation: [Data Fabric](../../explanation/data-fabric.md).

The Fabric data plane coordinates ingestion modes, cursor advancement, watermark selection,
document/claim normalization, and read-only world queries. Its main job is to fetch once, persist
evidence and provenance to CAS, materialize world tables, and expose downstream snapshot/query
artifacts without redundant network fetches.

## Core Modules

| Module | Responsibility |
|--------|----------------|
| `orchestrator` | Single-call ingestion plus optional `DataSnapshot` assembly from CAS evidence |
| `modes` | Batch incremental, record, replay, and streaming-windowed execution modes |
| `watermark` | Connector-family watermark extraction strategy for cursor advancement |
| `docs.*` | Raw document ingest, text normalization, anchor extraction, and chunking with `DocMeta` lineage |
| `claims.*` | Claim extraction, canonicalization, conflict resolution, trust scoring, and evidence bundles |
| `world_query` | Read-only query helpers over materialized world tables with column masking |

## Execution Modes

| Function | Mode | Purpose |
|----------|------|---------|
| `run_batch_incremental()` | Batch incremental | Uses `CursorStore` and watermark policy to resume dataset fetches |
| `run_record_mode()` | Record | Captures HTTP traffic into CAS-backed replay fixtures |
| `run_replay_mode()` | Replay | Re-runs ingestion from captured fixtures without network access |
| `run_streaming_windowed()` | Streaming windowed | Persists chunked fetches for larger paginated sources |

## Watermark Policies

| Policy | Use case |
|--------|----------|
| `TimestampWatermark` | Default for most HTTP statistical APIs |
| `ETagWatermark` | Useful for SPARQL or versioned content endpoints |
| `RevisionWatermark` | Revision-number based sources |
| `OffsetWatermark` | Pagination / row-offset progress tracking |

## Orchestration Notes

| Item | Detail |
|------|--------|
| Double-fetch avoidance | `run_orchestrated_ingestion()` builds `DataSnapshot` from persisted evidence rather than refetching raw data |
| Cursor advancement | `run_batch_incremental()` resolves connector-family watermark policy and stores cursor state in CAS |
| Replayability | Record / replay mode uses `ReplayStore` fixtures so connector regressions can be reproduced without hitting live APIs |

## API Reference

::: polisyos.fabric.data_plane.orchestrator

::: polisyos.fabric.data_plane.modes

::: polisyos.fabric.data_plane.watermark

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
