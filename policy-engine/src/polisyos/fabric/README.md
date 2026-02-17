# Fabric

`polisyos.fabric` — data-fabric слой PolicyOS. Подсистема отвечает за ingestion данных и документов, извлечение и нормализацию фактов, сбор evidence/provenance, материализацию world-представления и безопасный доступ к нему.

## Роль в системе

Fabric расположен между инфраструктурными слоями (`polisyos.ir`, `polisyos.core`) и прикладными потребителями (`polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`).

Сквозной поток:

```text
External APIs + Documents
          |
          v
connectors/docs/claims (+ pii, quality, trust)
          |
          v
CAS artifacts + fact segments + manifests + evidence
          |
          +--> world/store -> world/materialize (DuckDB, optional Kuzu)
          |        |
          |        v
          |     world_query
          |
          +--> data_plane (snapshots, cursors, record/replay, regression)
          |
          +--> retrieval (FastLane/ExploreLane + fetch execution)
```

## Ключевые потоки

### 1) Коннекторный ingestion

- Канонический entrypoint: `run_connectors_ingestion(...)` в `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/ingestion.py`.
- Совместимый wrapper: `run(...)` в `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/connectors_ingestion.py`.
- Что делает: fetch через `connectors`, optional transform DAG, PII stage, CAS cache, provenance graph, evidence bundle.

### 2) Документы -> claims -> world facts

- `docs/`: `ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc`.
- `claims/`: `extract_claims_from_doc -> normalize_claims -> detect_conflicts -> resolve_conflicts`.
- Результат: артефакты claim/doc, world events, world fact segments и manifests.

### 3) Materialized world и query

- `world/store`: emit/validate/persist world-сущностей и segment index.
- `world/materialize`: apply сегментов в DuckDB projections, optional export в Kuzu.
- `world_query.py`: безопасный табличный API с allowlist колонок и masking.

### 4) Data-plane оркестрация

- `data_plane/orchestrator.py`: ingestion + DataSnapshot без double-fetch.
- `data_plane/modes.py`: `batch_incremental`, `record`, `replay`, `streaming_windowed`.
- `data_plane/cursor_store.py`, `replay_store.py`, `regression.py`: курсоры, сессии record/replay, детерминированные сравнения прогонов.

### 5) Retrieval для control/NL контуров

- `retrieval/service.py`: orchestration FastLane + ExploreLane + promotion queue.
- `retrieval/executor.py`: preview gate, fallback, execute fetch plans.
- `retrieval/explore_lane.py`: bounded discovery с бюджетами по времени/кандидатам.

## Структура директории

- `catalog/` — контракты метрик, bindings, fast-lane resolver, поиск.
- `connectors/` — протокол коннекторов, registry, quality/cache/resilience/transform/federation.
- `docs/` — документный конвейер (raw -> normalized -> structure -> chunks).
- `claims/` — extraction/normalization/conflict processing.
- `world/` — world store + materialization + DDL.
- `data_plane/` — режимы исполнения ingestion и snapshot/cursor lifecycle.
- `retrieval/` — гибридное разрешение метрик и выполнение fetch plans.
- `pii/` — PII detection stage (`Presidio` + fallback).
- `provenance/`, `evidence.py`, `fact_writer.py`, `segment_manifest.py` — трассируемость и факт-сегменты.
- `security/` — column-level guard/masking для world query.
- `storage/`, `io/` — хранилище и DuckDB runtime (`SimulationDB`).
- `quality.py`, `fitness_report.py`, `trust.py`, `trust_adapter.py` — quality/trust модели и адаптеры.

## Публичный API `polisyos.fabric`

Экспортируется lazy-load API:

- `fabric_get_data`
- `run_connectors_ingestion`
- `execute_world_query`
- `query_world_table`
- `query_claims`
- `query_events`
- `WorldQueryRequest`
- `WorldQueryError`
- `world`

Также lazy-экспортируются ключевые сущности каталога (`DataContract`, `MetricBinding`, `DataContractRegistry`, `MetricSearcher` и другие).

## Связи с остальной кодовой базой

- Зависит от: `polisyos.ir`, `polisyos.core`, `polisyos.common`.
- Используется в: `polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`.
- Архитектурное правило: зависимости направлены сверху вниз; Fabric не должен импортировать прикладные слои обратно.

## Важные особенности

- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/_connector_bridge.py` — официальный синхронный bridge для верхнего слоя.
- `Kuzu`-материализация остается optional (`world/materialize/kuzu.py`).
- `docs/backends/pdf.py` в текущем ядре работает как заглушка и требует расширения/optional deps для полноценного OCR/PDF extraction.
- Детали подсистем вынесены в README внутри `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/connectors`, `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/docs`, `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/claims`, `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world`, `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/catalog`, `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/data_plane`, `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval`.
