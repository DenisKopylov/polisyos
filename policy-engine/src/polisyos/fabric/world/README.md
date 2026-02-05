# World Model System

**World Model System** — это система материализации и управления моделью мира из Fact Log с поддержкой множественных представлений. Система обеспечивает восстановление реляционных и графовых представлений из immutable фактов, предоставляя унифицированный интерфейс для работы с данными мира симуляции.

## Архитектурная роль

World Model System является мостом между immutable Fact Log и queryable представлениями данных:

### Положение в экосистеме Fabric

```
Fact Log → World Materialization → Query Interfaces
     ↓              ↓                      ↓
 store/       materialize/            DuckDB + Kùzu
 ddl/         projections/            world schemas
```

### Ключевые обязанности

1. **Schema Management**: Автоматическая инициализация и управление схемами хранилищ
2. **Incremental Materialization**: Постепенное восстановление представлений из новых фактов
3. **Multi-View Projections**: Поддержка различных проекций данных для разных use cases
4. **Data Validation**: Проверка целостности материализованных данных
5. **Merge Conflict Resolution**: Разрешение конфликтов при материализации
6. **Provenance Tracking**: Связь материализованных данных с их provenance

## Структура модуля

```
world/
├── __init__.py              # Экспорт основного API
├── ddl/                     # DDL скрипты для инициализации хранилищ
│   ├── duckdb_world.sql     # Реляционная схема мира для DuckDB
│   └── kuzu_world.cypher    # Графовая схема мира для Kùzu
├── materialize/             # Материализация представлений из Fact Log
│   ├── __init__.py          # Экспорт materialize API
│   ├── duckdb.py            # Материализация в DuckDB
│   ├── kuzu.py              # Материализация в Kùzu
│   ├── errors.py            # Специфичные ошибки материализации
│   ├── projections.py       # Проекции данных для разных представлений
│   ├── rules.py             # Правила материализации и merge стратегии
│   ├── sql.py               # Генерация SQL запросов для материализации
│   └── staging.py           # Staging area для промежуточных данных
└── store/                   # Хранение и управление сегментами мира
    ├── __init__.py          # Экспорт store API
    ├── emit.py              # Эмиссия фактов мира
    ├── errors.py            # Специфичные ошибки хранения
    ├── ids.py               # Управление идентификаторами мира
    ├── persist.py           # Персистентность данных мира
    ├── provenance.py        # Provenance для сегментов мира
    ├── segments.py          # Управление сегментами мира
    └── validate.py          # Валидация фактов мира
```

## Ключевые компоненты

### 1. DDL Management (`ddl/`)

DDL скрипты для инициализации схем хранилищ мира:

#### DuckDB Schema (`duckdb_world.sql`)
Реляционная схема для хранения фактов мира в табличном виде:

```sql
-- Основные таблицы фактов
CREATE TABLE world.world_facts (
    fact_id VARCHAR PRIMARY KEY,
    subject_id VARCHAR NOT NULL,
    predicate_id VARCHAR NOT NULL,
    object_value VARCHAR,
    valid_time VARCHAR,
    tx_time VARCHAR NOT NULL
);

-- Проекции для разных типов сущностей
CREATE TABLE world.doc_meta (
    doc_source_id VARCHAR PRIMARY KEY,
    canonical_url VARCHAR,
    license VARCHAR,
    retrieved_at TIMESTAMP
);

CREATE TABLE world.doc_fragments (
    fragment_id VARCHAR PRIMARY KEY,
    doc_version_id VARCHAR,
    offset_start INTEGER,
    offset_end INTEGER,
    text_preview VARCHAR
);
```

#### Kùzu Schema (`kuzu_world.cypher`)
Графовая схема для хранения связей между сущностями мира:

```cypher
// Узлы документов
CREATE NODE TABLE DocMeta(
    id STRING,
    source_url STRING,
    license STRING,
    retrieved_at STRING,
    PRIMARY KEY(id)
);

// Узлы фрагментов
CREATE NODE TABLE DocFragment(
    id STRING,
    doc_version_id STRING,
    offset_start INT64,
    offset_end INT64,
    text_content STRING,
    PRIMARY KEY(id)
);

// Релации между документами и фрагментами
CREATE REL TABLE HasFragment(
    FROM DocMeta TO DocFragment
);
```

### 2. Materialization Engine (`materialize/`)

Система материализации представлений из Fact Log:

#### Incremental Materialization
```python
from polisyos.fabric.world.materialize import ensure_world_materialized

# Инкрементальная материализация новых фактов
stats = ensure_world_materialized(
    fact_dir=Path("data/facts"),
    db_conn=duckdb_conn,
    force=False  # Только новые сегменты
)

print(f"Applied {stats.segments_applied} segments")
print(f"Inserted {stats.total_facts_inserted} facts")
```

#### Multi-Backend Support
```python
from polisyos.fabric.world.materialize import (
    materialize_world_duckdb_from_fact_log,
    materialize_world_kuzu_from_duckdb
)

# Материализация в DuckDB
duckdb_stats = materialize_world_duckdb_from_fact_log(
    fact_dir=Path("data/facts"),
    db_conn=duckdb_conn
)

# Синхронизация с Kùzu
kuzu_stats = materialize_world_kuzu_from_duckdb(
    duckdb_conn=duckdb_conn,
    kuzu_conn=kuzu_conn
)
```

#### Merge Strategies (`rules.py`)
Стратегии разрешения конфликтов при материализации:

```python
class MergeStrategy(Enum):
    LATEST_WINS = "latest_wins"          # Последнее значение побеждает
    ERROR_ON_CONFLICT = "error_on_conflict"  # Ошибка при конфликте
    UNION = "union"                       # Объединение значений
    CUSTOM = "custom"                     # Кастомная логика
```

### 3. Projections System (`projections.py`)

Множественные проекции данных для разных use cases:

#### Типы проекций
- **Document Projections**: Метаданные и контент документов
- **Claim Projections**: Извлеченные факты и их атрибуты
- **Event Projections**: События и их связи
- **Entity Projections**: Сущности мира и их свойства

#### Управление проекциями
```python
from polisyos.fabric.world.materialize.projections import WorldProjections

projections = WorldProjections(db_conn=duckdb_conn)

# Обновление проекций после материализации
projections.update_doc_projection()
projections.update_claim_projection()
projections.update_entity_graph()
```

### 4. World Store (`store/`)

Хранение и управление сегментами мира:

#### Fact Emission
```python
from polisyos.fabric.world.store import emit_world_node_facts, emit_edge_fact

# Эмиссия фактов узла мира
node_facts = emit_world_node_facts(
    node_id="doc_001",
    node_type="document",
    attributes={"title": "Economic Report", "author": "BEA"}
)

# Эмиссия фактов ребра
edge_facts = emit_edge_fact(
    from_id="doc_001",
    to_id="fragment_001",
    edge_type="has_fragment",
    attributes={"offset": 0, "length": 1000}
)
```

#### Segment Management
```python
from polisyos.fabric.world.store import write_world_fact_segment

# Запись сегмента фактов мира
segment_path, manifest = write_world_fact_segment(
    facts=all_world_facts,
    segment_dir=Path("data/world_segments"),
    segment_id="world_segment_001"
)
```

#### Validation
```python
from polisyos.fabric.world.store import validate_world_facts

# Валидация фактов мира
validation_errors = validate_world_facts(world_facts)
if validation_errors:
    raise WorldValidationError(f"Invalid facts: {validation_errors}")
```

## Основные типы данных

### World Facts
Факты мира следуют стандартной структуре RDF triples с расширениями:

```python
# Факт атрибута (subject predicate object)
Fact(
    subject_id="doc_001",
    predicate_id="has_title",
    object_value="Economic Report 2024"
)

# Факт ребра (subject predicate target)
Fact(
    subject_id="doc_001",
    predicate_id="has_fragment",
    target_id="fragment_001"
)

# Факт с временными атрибутами
Fact(
    subject_id="agent_001",
    predicate_id="has_income",
    object_value="50000",
    valid_time="2024-01-01T00:00:00Z",
    tx_time="2024-01-15T10:00:00Z"
)
```

### Materialization Stats
Статистика процесса материализации:

```python
@dataclass
class WorldMaterializeStats:
    segments_applied: int           # Применено сегментов
    total_facts_inserted: int       # Вставлено фактов
    nodes_touched: int             # Затронуто узлов
    edges_inserted: int            # Вставлено ребер
    projections_updated: int       # Обновлено проекций
    duration_seconds: float        # Время выполнения
    errors: list[str]              # Ошибки (если есть)
```

## Интеграция с системой

### Связь с Fact Log

World Model получает данные из Fact Log через материализацию:

```python
from polisyos.fabric.fact_log import load_fact_segments
from polisyos.fabric.world.materialize import apply_world_segment

# Загрузка сегментов Fact Log
segments = load_fact_segments(fact_dir=Path("data/facts"))

# Применение к модели мира
for segment in segments:
    apply_world_segment(
        segment=segment,
        db_conn=duckdb_conn,
        strategy=MergeStrategy.LATEST_WINS
    )
```

### Связь с Claims Processing

Claims интегрируются в модель мира как факты:

```python
from polisyos.fabric.claims.persist import persist_claims_to_world
from polisyos.fabric.world.store import emit_claim_facts

# Сохранение claims как фактов мира
world_facts = emit_claim_facts(claims_result.claims)
persist_world_facts(world_facts, db_conn=duckdb_conn)
```

### Связь с Document Processing

Документы становятся частью модели мира:

```python
from polisyos.fabric.docs import DocIngestResult
from polisyos.fabric.world.store import emit_doc_meta_facts, emit_doc_fragment_facts

# Преобразование результатов обработки документов в факты мира
doc_facts = emit_doc_meta_facts(doc_result.doc_meta)
fragment_facts = emit_doc_fragment_facts(doc_result.chunks)

# Сохранение в модель мира
persist_world_facts(doc_facts + fragment_facts, db_conn=duckdb_conn)
```

### Связь с Query Interfaces

Материализованная модель мира доступна для запросов:

```python
# Реляционные запросы через DuckDB
doc_info = duckdb_conn.execute("""
    SELECT dm.title, COUNT(df.fragment_id) as fragments
    FROM world.doc_meta dm
    LEFT JOIN world.doc_fragments df ON dm.id = df.doc_version_id
    WHERE dm.license = 'public-domain'
    GROUP BY dm.id, dm.title
""").fetchdf()

# Графовые запросы через Kùzu
entity_connections = kuzu_conn.execute("""
    MATCH (d:DocMeta)-[:has_fragment]->(f:DocFragment)
    WHERE d.license = 'public-domain'
    RETURN d.id, count(f) as fragment_count
""")
```

## Производительность и масштабируемость

### Оптимизации

**Incremental Processing:**
- Материализация только новых сегментов
- Delta updates для проекций
- Smart merge conflict resolution

**Memory Management:**
- Streaming обработка больших сегментов
- Chunked fact emission
- Connection pooling для баз данных

**Indexing:**
- Автоматические индексы на часто используемые поля
- Composite indexes для сложных запросов
- Partitioning по времени для временных данных

### Масштабирование

**Текущее состояние:**
- Поддержка до 100M фактов в одном сегменте
- Материализация до 1M фактов в минуту
- Параллельная обработка множественных сегментов

**Расширения:**
- Distributed материализация через кластер
- GPU acceleration для complex projections
- Hierarchical caching для частых запросов

## Безопасность и приватность

### Data Validation
- **Schema Compliance**: Проверка соответствия фактов схеме мира
- **Reference Integrity**: Валидация связей между фактами
- **Temporal Consistency**: Проверка временной логики фактов

### Access Control
- **Fact-level Permissions**: Контроль доступа к фактам
- **Projection Security**: Безопасные проекции для разных ролей
- **Audit Logging**: Полное логирование всех операций

### Integrity Protection
- **Hash Verification**: Проверка целостности сегментов
- **Provenance Tracking**: Полная traceability фактов
- **Immutable Storage**: Защита от несанкционированных изменений

## Тестирование

### Unit Tests
```bash
# Тесты компонентов мира
pytest tests/fabric/world/test_store.py
pytest tests/fabric/world/test_materialize.py
pytest tests/fabric/world/test_projections.py
```

### Integration Tests
```bash
# Полная материализация
pytest tests/integration/test_world_materialization.py

# Интеграция с Fact Log
pytest tests/integration/test_world_fact_log_integration.py
```

### Performance Tests
```bash
# Бенчмарки материализации
pytest tests/benchmarks/test_world_materialization_perf.py

# Масштабирование
pytest tests/benchmarks/test_world_scalability.py
```

## Примеры использования

### Полная материализация модели мира

```python
from pathlib import Path
from polisyos.fabric.world.materialize import (
    ensure_world_schema,
    ensure_world_materialized
)
import duckdb

# Инициализация схемы
conn = duckdb.connect("world.duckdb")
ensure_world_schema(conn)

# Материализация из Fact Log
fact_dir = Path("data/facts")
stats = ensure_world_materialized(
    fact_dir=fact_dir,
    db_conn=conn,
    force=True  # Полная материализация
)

print(f"Materialized {stats.total_facts_inserted} facts")
print(f"Applied {stats.segments_applied} segments")
conn.close()
```

### Запросы к модели мира

```python
# Реляционные запросы к документам
doc_stats = conn.execute("""
    SELECT
        license,
        COUNT(*) as doc_count,
        AVG(fragment_count) as avg_fragments
    FROM (
        SELECT
            dm.license,
            dm.id,
            COUNT(df.fragment_id) as fragment_count
        FROM world.doc_meta dm
        LEFT JOIN world.doc_fragments df ON dm.id = df.doc_version_id
        GROUP BY dm.id, dm.license
    )
    GROUP BY license
""").fetchdf()

# Графовые запросы к связям
connections = conn.execute("""
    MATCH (d:DocMeta)-[r:has_fragment]->(f:DocFragment)
    WHERE d.license = 'public-domain'
    RETURN d.title, count(r) as connections
    ORDER BY connections DESC
    LIMIT 10
""").fetchdf()
```

### Кастомная проекция

```python
from polisyos.fabric.world.materialize.projections import BaseProjection

class CustomDocProjection(BaseProjection):
    def update(self, conn):
        # Кастомная логика проекции
        conn.execute("""
            CREATE OR REPLACE TABLE world.custom_doc_view AS
            SELECT
                dm.*,
                COUNT(df.fragment_id) as fragment_count,
                SUM(LENGTH(df.text_content)) as total_text_length
            FROM world.doc_meta dm
            LEFT JOIN world.doc_fragments df ON dm.id = df.doc_version_id
            GROUP BY dm.id
        """)

# Регистрация и обновление проекции
projection = CustomDocProjection()
projection.update(conn)
```

### Управление сегментами мира

```python
from polisyos.fabric.world.store import (
    write_world_fact_segment,
    load_world_fact_manifests
)

# Создание нового сегмента фактов мира
segment_path, manifest = write_world_fact_segment(
    facts=world_facts,
    segment_dir=Path("data/world_segments"),
    segment_id="world_segment_2024_01_15"
)

# Загрузка существующих сегментов
manifests = load_world_fact_manifests(Path("data/world_segments"))
print(f"Found {len(manifests)} world segments")

# Проверка применения сегментов
applied_segments = conn.execute(
    "SELECT segment_id FROM world._meta_world_segments"
).fetchall()
```

## Заключение

**World Model System** обеспечивает надежное и эффективное восстановление queryable представлений из immutable Fact Log, поддерживая как реляционные, так и графовые модели данных. Система предоставляет гибкие проекции для разных use cases, обеспечивает data integrity и масштабируется для обработки больших объемов фактов мира симуляции.