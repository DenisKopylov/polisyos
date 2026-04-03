# Data Plane (`polisyos.fabric.data_plane`)

`data_plane` - orchestration layer for ingestion modes, cursor lifecycle, record/replay
and snapshot production.

## Role in System

- **Depends on:** `polisyos.fabric.ingestion`, connector/runtime artifacts
- **Used by:** batch ingestion, replay tooling and historical regression checks
- Leaves source contracts unchanged and controls how ingestion is executed.

## Key Concepts

- **Execution modes** - batch incremental, record, replay and streaming-windowed runs.
- **Cursor state** - cursor persistence and resume support.
- **Semantic diff** - compares historical rows across schema evolution.
- **Snapshot production** - builds data snapshots from already stored CAS artifacts.

## Public API

| Type/Function | Description |
|---|---|
| `run_orchestrated_ingestion()` | Main orchestration entrypoint. |
| `run_batch_incremental()` | Batch ingestion mode. |
| `run_record_mode()` | Record-mode ingestion with replay artifacts. |
| `run_replay_mode()` | Replay a recorded ingestion session. |
| `run_streaming_windowed()` | Windowed streaming ingestion mode. |
| `compare_historical_rows()` | Computes semantic diff for historical data. |
| `persist_historical_semantic_diff_report()` | Persists semantic diff reports. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 8 Python files
- Exports: 2
