# Data Plane

`polisyos.fabric.data_plane` — orchestration-слой над ingestion: execution modes, cursor lifecycle, record/replay и snapshot production.

## Назначение

Data Plane управляет способом выполнения ingestion, не меняя контракт `SourceConnector`.

```text
connector manifest
  -> run_orchestrated_ingestion / run_*_mode
  -> evidence + optional DataSnapshot
  -> cursor/session artifacts + regression checks
```

## Основные модули

- `orchestrator.py`
  `run_orchestrated_ingestion(...)`: решает double-fetch (snapshot собирается из уже сохраненных CAS-артефактов).
- `modes.py`
  - `run_batch_incremental(...)`
  - `run_record_mode(...)`
  - `run_replay_mode(...)`
  - `run_streaming_windowed(...)`
- `cursor_store.py`
  CAS + lightweight индекс `cursor_index.json`.
- `watermark.py`
  Политики watermark (`Timestamp`, `ETag`, `Revision`, `Offset`) и mapping по семействам коннекторов.
- `replay_store.py`
  `RecordSession`/`ReplayStore` для record/replay fixtures.
- `regression.py`
  deterministic compare record/replay результатов.

## Возвращаемые результаты

Базовый тип: `IngestionResult`:

- `evidence_bundle_ref`
- `data_snapshot_ref`
- `datasets_fetched`
- `warnings`
- `cursor_ref`
- `mode_effective`

Специальный случай: `run_record_mode(...)` возвращает `(IngestionResult, record_ref_hex)`.

## Связи

- upstream: `fabric.ingestion`.
- replay/runtime: `fabric.connectors.testing.simulator` (`APISimulator`).
- контракты: `polisyos.core.contracts.cursor`, `polisyos.core.contracts.fabric`.
