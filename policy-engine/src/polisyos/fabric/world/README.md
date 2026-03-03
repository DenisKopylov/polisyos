# World

`polisyos.fabric.world` превращает append-only fact segments в queryable world-представление (DuckDB, optional Kuzu export).

## Состав

- `store/` — emit/validate/persist world entities, segment lifecycle (`write`, `append index`, `load manifests`).
- `materialize/` — применение сегментов в DuckDB projections + optional export в Kuzu.
- `events.py` — генерация детерминированных world events для pipeline-стадий.

## Поток данных

```text
Fact segments + manifests
   -> world.store (CAS + _segments.jsonl)
   -> world.materialize.duckdb (idempotent apply)
   -> world.* projection tables
   -> world_query (safe read API)
```

## Materialization API

- `ensure_world_schema(...)` — применяет DDL + idempotent online migrations (в т.ч. conflict projections).
- `apply_world_segment(...)` — применяет один сегмент транзакционно.
- `ensure_world_materialized(...)` — инкрементально применяет набор сегментов.
- `materialize_world_duckdb_from_fact_log(...)` — materialize from fact-log root.
- `materialize_world_kuzu_from_duckdb(...)` — optional экспорт в Kuzu.

## Консистентность и merge

Merge rules задаются в `materialize/rules.py`:

- `ERROR_ON_CONFLICT`
- `PREFER_NON_NULL_LAST_TX`
- `LAST_TX`
- `FIRST_TX`

Если для одного `node_id` конфликтует `kind`, поднимается `WorldMergeConflict`.

## DuckDB schema

DDL: [duckdb_world.sql](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world/ddl/duckdb_world.sql)

Ключевые таблицы:

- meta: `world._meta_world_segments`
- event-sourcing view: `world.world_facts`
- graph: `world.world_nodes`, `world.world_edges`, `world.world_events`
- docs: `world.doc_sources`, `world.doc_versions`, `world.doc_fragments`
- claims/conflicts: `world.claims`, `world.claim_citations`, `world.conflict_sets`, `world.conflict_members`
- trust/quality: `world.trust_assessments`, `world.quality_reports`

## Связи

- producers: `fabric.docs`, `fabric.claims`, ingestion-related pipelines.
- consumers: [world_query.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world_query.py), retrieval/control/scientist paths.
- runtime: `fabric.io` (`SimulationDB`) и `fabric.storage` adapters.
