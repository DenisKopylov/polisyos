# Data Plane (`polisyos.fabric.data_plane`)

`polisyos.fabric.data_plane` orchestrates ingestion modes, cursor lifecycle,
record/replay, streaming and CDC, quarantine, semantic diffs, and benchmark
reports.

Last updated: 2026-04-17.

## Purpose

Use this package when you need to control how Fabric ingestion executes without
changing connector contracts: batch, replay, and streaming modes live here, as
do the operational recovery surfaces for quarantine and schema-drift evidence.

## Where to Start

- Read [cli.py](./cli.py) and [modes.py](./modes.py) for the operational entry
  surfaces used by tooling and runtime services.

- Read [orchestrator.py](./orchestrator.py) and
  [cursor_store.py](./cursor_store.py) for the main ingestion and checkpoint
  lifecycle.

- Read [quarantine.py](./quarantine.py), [streaming.py](./streaming.py), and
  [semantic_diff.py](./semantic_diff.py) for recovery, CDC, and historical
  comparison logic.

- Follow downstream links to [../docs/README.md](../docs/README.md),
  [../claims/README.md](../claims/README.md), and
  [../world/README.md](../world/README.md) when you need the full pipeline.

## Public Entrypoints

| Entrypoint                                                                        | Description                                                                 |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `run_orchestrated_ingestion()`                                                    | Main orchestration entrypoint.                                              |
| `run_batch_incremental()`                                                         | Incremental batch mode with cursor advancement.                             |
| `run_record_mode()` / `run_replay_mode()`                                         | Deterministic capture and replay flow.                                      |
| `run_streaming_windowed()`                                                        | Windowed streaming mode over connector-backed datasets.                     |
| `process_stream_dataset()`                                                        | Streaming runtime with checkpoint, dedupe, backpressure, and CDC artifacts. |
| `QuarantineRecord`, `list_quarantine_records()`, `reprocess_quarantine_records()` | CAS-backed poison-record storage and reprocessing API.                      |
| `compare_historical_rows()` / `persist_historical_semantic_diff_report()`         | Historical schema-evolution diff helpers.                                   |
| `python -m polisyos.fabric.data_plane.cli`                                        | Package-local CLI for quarantine report and replay operations.              |

## Depends On / Depended On By

- Depends on: `polisyos.fabric.ingestion`, `polisyos.fabric.connectors`,
  `polisyos.fabric.world`, `polisyos.core.artifacts`, and cursor/replay
  storage helpers in this package.

- Depended on by: `polisyos.runtime.http.services.control`,
  `polisyos.scientist.feedback`, `polisyos.fabric.claims.normalize`, and
  `polisyos.fabric.world.store.quarantine`.

## Common Commands

Run from the repository root (`policy-engine/`).

- `uv run python -m polisyos.fabric.data_plane.cli --help`
  Inspect the quarantine report and replay CLI. Smoke-tested on 2026-04-17.

- `rg -n "run_batch_incremental|run_record_mode|run_replay_mode|run_streaming_windowed" src/polisyos/fabric/data_plane`
  Jump to the execution-mode entrypoints. Smoke-tested on 2026-04-17.

- `rg -n "QuarantineRecord|build_quarantine_report|reprocess_quarantine_records" src/polisyos/fabric/data_plane`
  Jump to the quarantine surface and replay hooks. Smoke-tested on 2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/unit/fabric/data_plane/test_modes.py tests/unit/fabric/data_plane/test_orchestrator.py -q`
  Batch and orchestrator smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/data_plane/test_quarantine.py tests/unit/fabric/data_plane/test_streaming_runtime.py -q`
  Quarantine and streaming smoke suite. Smoke-tested on 2026-04-17.

- `uv run pytest tests/unit/fabric/data_plane -q`
  Full data-plane suite. Conceptual in this README refresh; not run in this
  pass.

## Reference Docs

- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Fabric lineage reference](../../../../docs/reference/fabric/lineage.md)
- [Fabric time-travel reference](../../../../docs/reference/fabric/time-travel.md)
- [Cache rebuild storm runbook](../../../../docs/runbooks/cache-rebuild-storm.md)
- [Retained artifact recovery runbook](../../../../docs/runbooks/retained-artifact-recovery.md)
- [Artifact corruption recovery runbook](../../../../docs/runbooks/artifact-corruption-recovery.md)
- [Fabric tests map](../../../../tests/unit/fabric/README.md)
