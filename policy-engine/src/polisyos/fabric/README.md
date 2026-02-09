# Fabric — Unified Data Fabric

**Fabric** — слой данных Policy Engine, отвечающий за весь жизненный цикл: от получения сырых данных из внешних источников до материализации модели мира, доступной для запросов из Scientist.

## Роль в системе

```
External Sources ──→ Connectors ──→ Ingestion ──→ Fact Log ──→ World Model ──→ Query API
                                        │                          │
                                   Provenance               Materialization
                                   + Evidence              (DuckDB + Kùzu)
```

Fabric занимает позицию между IR-контрактами (ниже) и Scientist (выше):

- **Зависит от:** `polisyos.ir` (контракты, типы фактов, uncertainty), `polisyos.core` (артефакты, CAS, компоненты)
- **Используется в:** `polisyos.scientist` (quality gate, fitness report), `polisyos.foundry` (опосредовано через world model)

Направление зависимостей строго соблюдается (Law A): Scientist импортирует из Fabric, но не наоборот. Для обратного направления существует `_connector_bridge.py` — единственная публичная точка, через которую Scientist запрашивает данные коннекторов.

## Архитектура модуля

```
fabric/
├── __init__.py                  # Lazy-loaded public API (10 exports)
├── _connector_bridge.py         # fabric_get_data() — мост для Scientist
├── ingestion.py                 # run_connectors_ingestion() — канонический entrypoint
├── world_query.py               # execute_world_query(), query_claims(), query_events()
├── config.py                    # FabricConfig, CatalogConfig
├── evidence.py                  # EvidenceBundle: build, persist, load, composite
├── quality.py                   # QualityIndicators, QualityLevel, thresholds (FAST/MVP/STRICT)
├── fitness_report.py            # DataFitnessReport для DecisionPacket
├── trust.py                     # UncertaintyBounds, two-pass compare
├── trust_adapter.py             # Мост Trust → IR UncertaintyEnvelope
├── fact_writer.py               # build_fact(), facts_from_dataframe(), write_fact_segment()
├── manifest.py                  # DatasetManifest (Pydantic schema)
├── registry.py                  # ManifestRegistry — реестр dataset manifests
├── segment_manifest.py          # write_segment_manifest() для Fact Log
│
├── catalog/                     # Data Contract Catalog (6 файлов)
├── claims/                      # Claims Processing Pipeline (22 файла)
├── connectors/                  # External Data Connectors (59 файлов)
├── docs/                        # Document Processing (11 файлов)
├── io/                          # Storage Adapters (2 файла)
├── provenance/                  # W3C PROV-O Lineage (3 файла)
└── world/                       # World Model Materialization (17 файлов)
```

## Ключевые подсистемы

### Connectors — внешние источники данных

Protocol-based система коннекторов с capability-driven security. 59 файлов, 70+ экспортов, включая кэширование, resilience (circuit breaker, retry, rate limiter), federation, quality validation и transform pipeline.

Подробнее: [connectors/README.md](connectors/README.md)

### Claims — извлечение фактов из документов

Pipeline: Document → Extraction (pluggable backends) → Normalization → Conflict Detection → Resolution → Fact Log. Поддерживает explicit lines, lexical regex и numeric regex extractors.

Подробнее: [claims/README.md](claims/README.md)

### World — материализация модели мира

Инкрементальная материализация из Fact Log в DuckDB (реляционные таблицы) и Kùzu (граф). DDL-управление схемами, merge-стратегии, multi-view projections.

Подробнее: [world/README.md](world/README.md)

### Catalog — контракты на метрики

Metric-level система контрактов с hash-locked bindings, fuzzy search, disambiguation и 5-уровневой PII-классификацией. Предотвращает hallucination метрик в Scientist.

Подробнее: [catalog/README.md](catalog/README.md)

### Docs — обработка документов

Pipeline: Ingestion → Normalization → Structure Analysis → Chunking. Поддерживает PDF (layout preservation), HTML, plain text через pluggable backends.

Подробнее: [docs/README.md](docs/README.md)

### IO — адаптеры хранения

Два адаптера в 2 файлах:

| Модуль | Хранилище | Назначение |
|--------|-----------|------------|
| `io/db.py` — `SimulationDB` | DuckDB | Макро-история, снимки агентов, entity resolution, run records, `_meta_segments` |
| `io/graph_store.py` — `GraphStore` | Kùzu | Entity-event граф (Agent nodes, Interaction edges) с Cypher-запросами |

`SimulationDB` — основной адаптер для аналитических SQL-запросов и bulk-insert (DataFrame → DuckDB). `GraphStore` — для сетевого анализа взаимодействий агентов.

### Provenance — W3C PROV-O lineage

3 файла, реализующие стандарт W3C PROV-O:

- **`core.py`** — `ProvenanceCoreGraph` с nodes (Entity, Activity, Agent) и edges (wasDerivedFrom, wasGeneratedBy, used, wasAttributedTo, wasAssociatedWith). Deterministic stable_id через SHA-256 канонического JSON. BFS-поиск предков с depth limit.
- **`export_provo.py`** — экспорт в JSON-LD и N-Quads для внешнего аудита и RDF triple stores.
- **`ProvenanceCoreRef`** — легковесная ссылка (graph_id + stable_id + artifact_id) для хранения в EvidenceBundle.

Provenance пронизывает все операции Fabric: каждая ingestion, extraction, materialization создает граф lineage, который хранится immutable в CAS.

## Корневые модули

### Ingestion (`ingestion.py`)

Канонический entrypoint для загрузки данных:

```python
from polisyos.fabric import run_connectors_ingestion

ref = run_connectors_ingestion(
    connector_manifest={"datasets": [{"connector_id": "wb", "dataset_id": "gdp_ua"}]},
    source="world_bank",
    license_name="CC-BY-4.0",
)
```

Pipeline: normalize manifest → build cache registry → load transform pipeline → fetch each dataset → apply transforms → persist to CAS → build provenance graph → create evidence bundle.

### World Query (`world_query.py`)

Типобезопасные запросы к материализованной модели мира:

```python
from polisyos.fabric import execute_world_query, WorldQueryRequest

df = execute_world_query(db, WorldQueryRequest(
    table="claims",
    columns=("claim_id", "predicate_id", "value"),
    where={"predicate_id": "gdp"},
    limit=100,
))
```

Доступные таблицы: `world_nodes`, `world_edges`, `world_facts`, `world_events`, `claims`, `claim_citations`, `doc_sources`, `doc_versions`, `doc_fragments`, `conflict_sets`, `conflict_members`, `trust_assessments`, `quality_reports`.

Все запросы параметризированы (защита от SQL-injection), колонки проходят regex-валидацию.

### Quality & Fitness (`quality.py`, `fitness_report.py`)

Система оценки качества данных с тремя профилями:

| Профиль | Missingness (acceptable) | Staleness (acceptable) | Coverage (acceptable) |
|---------|--------------------------|------------------------|-----------------------|
| FAST | 20% | 120 дней | 70% |
| MVP | 10% | 60 дней | 85% |
| STRICT | 5% | 14 дней | 95% |

`QualityIndicators` вычисляются из DataFrame (`compute_quality_indicators`) или напрямую из DuckDB (`compute_quality_from_duckdb`). Scored dimensions: missingness, staleness, coverage, schema drift, outlier ratio.

`DataFitnessReport` агрегирует per-metric fitness в отчет для DecisionPacket с ASCII и Markdown форматированием.

### Evidence (`evidence.py`)

Сборка и персистенция Evidence Bundles в CAS:

- `build_evidence_bundle()` — создает bundle из sources, transforms, provenance ref, quality indicators
- `persist_provenance_graph()` — сохраняет ProvenanceCoreGraph в CAS, возвращает ProvenanceCoreRef с integrity verification
- `persist_evidence_bundle()` — сохраняет EvidenceBundle, возвращает EvidenceBundleRef
- `build_composite_evidence_bundle()` — агрегация bundles из federation (делегирует в connectors.federation)

### Trust (`trust.py`, `trust_adapter.py`)

Two-pass comparison для uncertainty bounds:

```python
bounds, envelope = two_pass_compare_with_envelope(
    optimistic_value=100.0,
    pessimistic_value=95.0,
    assume_triangular=True,
)
```

`trust_adapter.py` конвертирует `UncertaintyBounds` → IR `UncertaintyEnvelope` с поддержкой TRIANGULAR/UNKNOWN distribution families и DETERMINISTIC_BOUNDS interval semantics.

### Fact Writer (`fact_writer.py`)

Создание immutable фактов для Fact Log:

- `build_fact()` — единичный факт с deterministic `fact_id` (SHA-256)
- `facts_from_dataframe()` — массовая генерация из DataFrame
- `write_fact_segment()` — запись сегмента в Parquet с manifest

Значения sanitized через `_sanitize_value()`: float → Decimal (canonical JSON), NaN → None.

## Технологический стек

| Технология | Назначение |
|------------|-----------|
| DuckDB | Аналитические SQL-запросы, bulk insert, columnar storage |
| Kùzu | Графовые Cypher-запросы, entity-event network |
| PyArrow / Parquet | Формат хранения Fact Log сегментов |
| Pydantic | Валидация моделей (DataContract, Manifest, FetchResult) |
| hashlib SHA-256 | Deterministic IDs, content-addressable storage |
| pandas | DataFrame-операции, quality computation |

## Public API

Lazy-loaded через `__init__.py`:

```python
from polisyos.fabric import (
    fabric_get_data,           # Высокоуровневый запрос данных (для Scientist)
    run_connectors_ingestion,  # Канонический ingestion entrypoint
    execute_world_query,       # Выполнение запроса к World Model
    query_claims,              # Shortcut: запрос claims
    query_events,              # Shortcut: запрос world events
    query_world_table,         # Универсальный запрос к таблице
    WorldQueryRequest,         # Параметры запроса
    WorldQueryError,           # Ошибка запроса
    world,                     # Lazy-loaded world submodule
)
```

Дополнительно через lazy imports доступны все типы из `catalog` (DataContract, MetricBinding, SearchResponse и др.).
