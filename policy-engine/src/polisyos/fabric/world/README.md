# World

`polisyos.fabric.world` превращает append-only fact segments в queryable world-представления.

## Что делает подсистема

- `store/` — эмиссия фактов, валидация ID/ABI, персист доменных объектов в CAS, запись segment manifests
- `materialize/` — инкрементальная материализация в DuckDB и обновление projections
- `materialize/kuzu.py` — опциональная выгрузка в Kuzu-граф
- `events.py` — helper'ы для детерминированных world events

## Поток данных

```text
Fact log segments (parquet + manifests)
      |
      v
materialize.duckdb -> world schema tables (DuckDB)
      |
      +-> projections update (claims/docs/conflicts/trust/quality/events)
      |
      +-> optional export to Kuzu
```

## Основные API

### Store

- `emit_*` функции: генерация world-compatible `Fact`
- `persist_*` функции: CAS-персист `DocMeta`, `Claim`, `ConflictSet`, `TrustAssessment`, `QualityReport`, `WorldEvent`
- `validate_*` функции: детерминизм ID и ABI-проверки
- `write_world_fact_segment(...)`, `append_world_segment_index(...)`, `load_world_fact_manifests(...)`

### Materialization

- `ensure_world_schema(db, ddl_path=None)`
- `materialize_world_duckdb_from_fact_log(fact_log_root, db, cas)`
- `ensure_world_materialized(db, cas, fact_manifests)`
- `apply_world_segment(db, cas, manifest)`
- `materialize_world_kuzu_from_duckdb(db, kuzu_path=..., kuzu_enabled=True)`

## Merge и консистентность

Для world attributes используются стратегии из `materialize/rules.py`:

- `ERROR_ON_CONFLICT`
- `PREFER_NON_NULL_LAST_TX`
- `LAST_TX`
- `FIRST_TX`

Конфликты `world.kind` для одного node приводят к `WorldMergeConflict`.

## DuckDB world schema (DDL)

Ключевые таблицы:

- `world.world_facts`, `world.world_nodes`, `world.world_edges`, `world.world_events`
- `world.doc_sources`, `world.doc_versions`, `world.doc_fragments`
- `world.claims`, `world.claim_citations`
- `world.conflict_sets`, `world.conflict_members`
- `world.trust_assessments`, `world.quality_reports`
- `world._meta_world_segments`

## Связи

- `docs/` и `claims/` — основные producers world-фактов
- `world_query.py` (на уровень выше) — безопасный query API по materialized таблицам
- `io/db.py` и `storage/duckdb_adapter.py` — runtime доступ к DuckDB
