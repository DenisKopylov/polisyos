# World

`polisyos.fabric.world` превращает append-only fact segments в queryable world-представление (DuckDB, optional Kuzu).

## Роль подсистемы

- `store/` — emit/validate/persist world-объектов и segment manifests.
- `materialize/` — применение сегментов в DuckDB schema + projection tables.
- `events.py` — детерминированные world events для стадий ingestion/docs/claims.

## Поток данных

```text
Fact segments + manifests (CAS)
      |
      v
world.store (validate + append index)
      |
      v
world.materialize.duckdb
      |
      +-> world.* projections (docs/claims/conflicts/trust/quality/events)
      |
      +-> optional world.materialize.kuzu export
```

## Основные API

### Store API

- `emit_*` функции: сборка world-compatible `Fact`.
- `persist_*` функции: CAS-персист доменных сущностей (`DocMeta`, `Claim`, `ConflictSet`, `TrustAssessment`, `QualityReport`, `WorldEvent`).
- `validate_*` функции: детерминизм ID и ABI-совместимость.
- segment lifecycle: `write_world_fact_segment(...)`, `persist_fact_segment_manifest(...)`, `append_world_segment_index(...)`, `load_world_fact_manifests(...)`.

### Materialization API

- `ensure_world_schema(...)` — инициализация DuckDB DDL.
- `apply_world_segment(...)` — применение одного сегмента.
- `ensure_world_materialized(...)` — инкрементальная материализация набора сегментов.
- `materialize_world_duckdb_from_fact_log(...)` — materialization из fact-log root.
- `materialize_world_kuzu_from_duckdb(...)` — optional экспорт в Kuzu.

## Merge-правила и консистентность

Используются стратегии `MergeStrategy` из `materialize/rules.py`:

- `ERROR_ON_CONFLICT`
- `PREFER_NON_NULL_LAST_TX`
- `LAST_TX`
- `FIRST_TX`

Конфликт `kind` для одного `node_id` приводит к `WorldMergeConflict`.

## DuckDB schema

Контракт DDL расположен в `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql`.

Ключевые группы таблиц:

- meta: `world._meta_world_segments`.
- raw facts: `world.world_facts`.
- graph: `world.world_nodes`, `world.world_edges`, `world.world_events`.
- docs: `world.doc_sources`, `world.doc_versions`, `world.doc_fragments`.
- claims/conflicts: `world.claims`, `world.claim_citations`, `world.conflict_sets`, `world.conflict_members`.
- trust/quality: `world.trust_assessments`, `world.quality_reports`.

## Связи

- `fabric.docs` и `fabric.claims` — основные producers world-facts.
- `/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world_query.py` — безопасный query API над materialized таблицами.
- `fabric.io`/`fabric.storage` — runtime доступ к DuckDB/CAS.
