# Fabric

`polisyos.fabric` — слой данных PolicyOS: он связывает внешние источники, обработку документов, извлечение фактов, материализацию world-модели и безопасный query-доступ к ней.

## Роль в системе

Fabric находится между инфраструктурными контрактами (`polisyos.ir`, `polisyos.core`) и прикладными потребителями (`polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`).

Упрощенно:

```text
External APIs / Documents
        |
        v
connectors + docs + claims
        |
        v
Fact Log (segments + manifests)
        |
        v
world materialization (DuckDB, optional Kuzu)
        |
        v
world_query / bridge API
```

## Ключевые потоки

### 1) Коннекторы и ingestion внешних данных

- Канонический entrypoint: `run_connectors_ingestion(...)` (`ingestion.py`)
- Совместимый wrapper: `connectors_ingestion.run(...)`
- Что делает: fetch через `connectors`, опциональные transform/PII stages, кэширование, provenance graph, evidence bundle в CAS

### 2) Документы -> claims -> fact log

- `docs/`: `ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc`
- `claims/`: `extract_claims_from_doc -> normalize_claims -> detect_conflicts -> resolve_conflicts`
- Результат: world events, world facts, segment manifests

### 3) Materialized world и запросы

- `world/store`: эмиссия/валидация/персист фактов
- `world/materialize`: инкрементальная загрузка в DuckDB, обновление projections, опциональная выгрузка в Kuzu
- `world_query.py`: безопасный табличный query API с column guard/masking

## Структура пакета

- `catalog/` — метрические контракты, binding, поиск, валидация
- `claims/` — extraction/normalization/conflict processing
- `connectors/` — протокол коннекторов, registry, cache/resilience/federation/contracts/transform/types
- `docs/` — конвейер обработки документов
- `world/` — world store + materialization + DDL
- `provenance/` — фасад и экспорт provenance
- `pii/` — PII-сканирование (Presidio + regex fallback) для ingestion
- `security/` — column-level guards для query
- `storage/` — `StoragePort`, `DuckDBStorageAdapter`, `InMemoryStorageAdapter`
- `io/` — `SimulationDB` (DuckDB runtime)
- `quality.py`, `fitness_report.py` — оценка качества и fitness-report
- `trust.py`, `trust_adapter.py` — uncertainty bounds/envelope
- `evidence.py` — сборка/персистенция evidence bundles
- `fact_writer.py`, `segment_manifest.py` — запись fact segments/manifests
- `manifest.py`, `registry.py` — dataset manifest models/registry

## Публичный API (`polisyos.fabric`)

Экспортируется lazy-loaded API:

- `fabric_get_data`
- `run_connectors_ingestion`
- `execute_world_query`
- `query_world_table`
- `query_claims`
- `query_events`
- `WorldQueryRequest`
- `WorldQueryError`
- `world` (submodule)

Дополнительно lazy-доступны типы каталога (`DataContract`, `MetricBinding`, `DataContractRegistry` и др.).

## Связи с другими директориями

### Fabric зависит от

- `polisyos.ir` — доменные модели и ID-алгоритмы (facts, world, connectors, uncertainty)
- `polisyos.core` — CAS/manifest/contracts/components/registry/security helpers
- `polisyos.common` — async/logger/utilities

### Fabric используется в

- `polisyos.scientist` — bridge (`fabric_get_data`), quality gate/fitness
- `polisyos.scholar` — doc/claims/world pipeline orchestration
- `polisyos.lex` — doc ingest, claims, world materialization/query paths

Fabric не импортирует `scientist/scholar/lex` обратно; зависимости направлены сверху вниз.

## Что важно учитывать при развитии

- `fabric/_connector_bridge.py` — официальный синхронный мост для верхнего слоя.
- `world/materialize/kuzu.py` — опционален; по умолчанию materialization в Kuzu выключен.
- `docs` в core-сборке не включает полноценную PDF-нормализацию без optional deps.
- В README модулей ниже (`connectors`, `docs`, `claims`, `world`, `catalog`) описаны детали подсистем.
