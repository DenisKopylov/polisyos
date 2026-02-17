# Data Plane

`polisyos.fabric.data_plane` — orchestration-слой исполнения ingestion. Подсистема добавляет режимы выполнения, cursor lifecycle, record/replay и snapshot-сборку поверх базового connector ingestion.

## Роль в Fabric

```text
connector manifest
   -> run_orchestrated_ingestion / run_*_mode
   -> evidence bundle + optional data snapshot
   -> cursor/session artifacts + regression checks
```

Цель слоя: управлять "как" выполняется ingestion, не меняя контракты самих коннекторов.

## Основные модули

### `orchestrator.py`

- `run_orchestrated_ingestion(...)` выполняет ingestion и, при необходимости, строит `DataSnapshot` из CAS evidence.
- Решает double-fetch сценарий: snapshot строится из уже сохраненных артефактов, без повторного запроса к источнику.

### `modes.py`

- `run_batch_incremental(...)` — cursor-based режим с обновлением watermark.
- `run_record_mode(...)` — запись HTTP fixture-сессии через `APISimulator` и сохранение в CAS.
- `run_replay_mode(...)` — воспроизведение ingestion из записанных fixtures (без live network).
- `run_streaming_windowed(...)` — chunk-ориентированный режим через `fetch_stream(...)`.

### `cursor_store.py`

- `CursorStore` сохраняет `CursorState` в CAS и поддерживает lightweight индекс `cursor_index.json`.

### `watermark.py`

- Политики watermark (`Timestamp`, `ETag`, `Revision`, `Offset`) и mapping по семействам коннекторов.

### `replay_store.py`

- `ReplayStore` и `RecordSession` для персиста/восстановления record/replay fixtures.

### `regression.py`

- Deterministic сравнение record/replay результатов (`compare_ingestion_runs`, `compare_artifact_hashes`).

## Результаты выполнения

Базовый тип результата: `IngestionResult`:

- `evidence_bundle_ref`
- `data_snapshot_ref`
- `datasets_fetched`
- `warnings`
- `cursor_ref`
- `mode_effective`

Особенность: `run_record_mode(...)` возвращает tuple `(IngestionResult, record_ref_hex)`.

## Связи

- `fabric.ingestion` — базовый ingestion entrypoint.
- `fabric.connectors.testing.simulator` — record/replay interception HTTP.
- `polisyos.core.contracts.cursor` — типы курсоров и watermark semantics.
- `polisyos.core.contracts.fabric` — `EvidenceBundleRef`, `DataSnapshotRef`.
