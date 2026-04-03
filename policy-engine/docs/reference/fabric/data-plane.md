# Fabric Data Plane
Related explanation: [Data Fabric](../../explanation/data-fabric.md).

The Fabric data plane coordinates ingestion modes, cursor advancement, and watermark selection. Its main job is to fetch once, persist evidence to CAS, and build downstream snapshot artifacts without redundant network fetches.

## Core Modules

| Module | Responsibility |
|--------|----------------|
| `orchestrator` | Single-call ingestion plus optional `DataSnapshot` assembly from CAS evidence |
| `modes` | Batch incremental, record, replay, and streaming-windowed execution modes |
| `watermark` | Connector-family watermark extraction strategy for cursor advancement |

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
