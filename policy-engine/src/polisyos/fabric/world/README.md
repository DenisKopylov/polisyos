# World — World Model Materialization

Система материализации модели мира из immutable Fact Log в queryable представления (DuckDB + Kùzu). Мост между append-only фактами и реляционными/графовыми запросами.

## Архитектура

```
Fact Log (Parquet segments)
    │
    ▼
store/              ←── Эмиссия и валидация фактов мира
    │
    ▼
materialize/        ←── Инкрементальная материализация
    ├── DuckDB      ←── Реляционные таблицы (world schema)
    └── Kùzu        ←── Entity-event граф
    │
    ▼
world_query.py      ←── Query API (fabric корневой уровень)
```

## Структура

```
world/
├── ddl/                       # DDL скрипты для инициализации
│   ├── duckdb_world.sql       # SQL schema: world_nodes, world_edges, claims, docs, conflicts...
│   └── kuzu_world.cypher      # Cypher schema: Agent, DocMeta, Interaction, HasFragment...
├── store/                     # Эмиссия, валидация и персистенция фактов (8 файлов)
│   ├── emit.py                # emit_world_node_facts(), emit_edge_fact(), emit_claim_facts()...
│   ├── persist.py             # persist_claim(), persist_doc_meta(), persist_world_event()...
│   ├── validate.py            # validate_world_facts(), validate_claim_id()...
│   ├── ids.py                 # Управление ID мира
│   ├── segments.py            # Сегменты Fact Log: write, append index, load manifests
│   ├── provenance.py          # stable_world_provenance_v1(), event_world_provenance_v1()
│   └── errors.py              # WorldFactError, WorldValidationError, WorldSegmentError...
└── materialize/               # Материализация в хранилища (8 файлов)
    ├── duckdb.py              # materialize_world_duckdb_from_fact_log()
    ├── kuzu.py                # materialize_world_kuzu_from_duckdb()
    ├── rules.py               # MergeStrategy (LAST_WRITE_WINS, HIGHEST_CONFIDENCE, MANUAL)
    ├── projections.py         # Multi-view projections для разных use cases
    ├── staging.py             # Staging area для промежуточных данных
    ├── sql.py                 # Генерация SQL для материализации
    └── errors.py              # WorldMaterializationError, WorldSchemaError, WorldSegmentHashMismatch...
```

## Store — эмиссия фактов

Функции эмиссии конвертируют domain-объекты в IR `Fact`:

```python
from polisyos.fabric.world import (
    emit_world_node_facts,     # NodeKind → Facts (agent attributes)
    emit_edge_fact,            # EdgeKind → Fact (interaction)
    emit_claim_facts,          # Claim → Facts
    emit_doc_meta_facts,       # DocMeta → Facts
    emit_doc_fragment_facts,   # DocFragment → Facts
)
```

Все Facts создаются через IR `build_fact_id()` с deterministic SHA-256 ID. Валидация: `validate_world_facts()` проверяет ABI-совместимость (NodeKind/EdgeKind predicates), `validate_claim_id()` / `validate_doc_meta_ids()` — referential integrity.

Персистенция: `persist_claim()`, `persist_doc_meta()`, `persist_world_event()`, `persist_conflict_set()`, `persist_quality_report()`, `persist_trust_assessment()` — запись в DuckDB world schema.

## Materialize — материализация

Двухфазный процесс:

### 1. DuckDB Materialization

```python
from polisyos.fabric.world import ensure_world_materialized

stats = ensure_world_materialized(fact_dir=Path("data/facts"), db_conn=conn)
```

`ensure_world_schema()` → инициализация DDL из `duckdb_world.sql`.
`materialize_world_duckdb_from_fact_log()` → инкрементальная обработка: читает segment manifests, проверяет `_meta_segments` (какие уже применены), применяет новые через `apply_world_segment()`.

Integrity: SHA-256 hash verification сегментов → `WorldSegmentHashMismatch` при несовпадении.

### 2. Kùzu Materialization

```python
from polisyos.fabric.world import materialize_world_kuzu_from_duckdb

materialize_world_kuzu_from_duckdb(duckdb_conn=conn, kuzu_db_path=Path("world.kuzu"))
```

Читает материализованные DuckDB таблицы → экспортирует в Kùzu graph (nodes: Agent, DocMeta; edges: Interaction, HasFragment).

### Merge Strategies (`rules.py`)

При конфликтах (одинаковый subject + predicate, разные значения):

| Стратегия | Поведение |
|-----------|-----------|
| `LAST_WRITE_WINS` | Последний факт по tx_time |
| `HIGHEST_CONFIDENCE` | Факт с максимальным confidence |
| `MANUAL` | Требует ручного разрешения |

### Projections (`projections.py`)

Multi-view: разные проекции одних и тех же фактов для разных потребителей (e.g. macro view, network view, temporal view).

## DDL Schema

### DuckDB (`duckdb_world.sql`)

Таблицы: `world_nodes`, `world_edges`, `world_facts`, `world_events`, `claims`, `claim_citations`, `doc_sources`, `doc_versions`, `doc_fragments`, `conflict_sets`, `conflict_members`, `trust_assessments`, `quality_reports`.

### Kùzu (`kuzu_world.cypher`)

Nodes: `Agent`, `DocMeta`, `DocFragment`. Edges: `Interaction`, `HasFragment`.

## Связи

- **Fact Log** (IR) — `FactSegmentManifest`, `Fact`, `build_fact_id()` — все факты приходят через IR
- **claims/** — основной поставщик фактов через emit_claim_facts() + persist_claim()
- **docs/** — DocMeta/DocFragment → emit + persist
- **fabric/world_query.py** — query API поверх материализованных таблиц
- **fabric/io/db.py** — `SimulationDB` для DuckDB connection
