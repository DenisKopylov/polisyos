# Fabric IO: Storage Adapters

Модуль `fabric.io` предоставляет унифицированные интерфейсы для работы с различными системами хранения данных в Policy Engine. Реализует паттерн "Storage Adapter" для абстрагирования от конкретных технологий хранения.

## Архитектурная роль

Согласно архитектуре Policy Engine, `fabric.io` является **Data Persistence Layer** - слоем персистентности данных, обеспечивающим:

- **Multi-Backend Storage**: Поддержка реляционных (DuckDB) и графовых (Kùzu) хранилищ
- **Unified Interface**: Единый API для всех операций с данными
- **Performance Optimization**: Специфичные для каждого хранилища оптимизации
- **Schema Management**: Автоматическое создание и управление схемами

## Структура модуля

```
fabric/io/
├── __init__.py              # Экспорт адаптеров хранения
├── db.py                    # DuckDB адаптер (SimulationDB)
└── graph_store.py           # Kùzu графовый адаптер (GraphStore)
```

## Компоненты

### 1. DuckDB Adapter (`db.py`)

Реляционный адаптер для хранения структурированных данных симуляции.

#### Ключевые возможности:

- **Macro Data Storage**: Хранение макроэкономических показателей (ВВП, инфляция, безработица)
- **Agent Snapshots**: Срезы состояния агентов по шагам симуляции
- **Entity Resolution**: Соответствия raw/canonical ID агентов
- **Run Records**: Метаданные прогонов симуляции для воспроизводимости
- **Fact Log Materialization**: Восстановление реляционных представлений из immutable фактов

#### Схема базы данных:

```sql
-- Макро-показатели (1 строка на шаг симуляции)
CREATE TABLE macro_history (
    run_id VARCHAR,
    step INTEGER,
    gdp DOUBLE,
    unemployment_rate DOUBLE,
    inflation_rate DOUBLE,
    avg_price DOUBLE,
    avg_income DOUBLE,
    government_balance DOUBLE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Срезы агентов (1M+ строк на срез)
CREATE TABLE agents_snapshot (
    run_id VARCHAR,
    step INTEGER,
    agent_id VARCHAR,
    age INTEGER,
    income DOUBLE,
    savings DOUBLE,
    is_employed BOOLEAN
);

-- Entity resolution mapping
CREATE TABLE entity_resolution (
    raw_id VARCHAR,
    canonical_id VARCHAR,
    match_confidence DOUBLE,
    match_method VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Метаданные прогонов для воспроизводимости
CREATE TABLE run_records (
    run_id VARCHAR,
    parent_run_id VARCHAR,
    seed INTEGER,
    repro_mode VARCHAR,
    backend VARCHAR,
    python_version VARCHAR,
    platform VARCHAR,
    generated_at TIMESTAMP,
    schema_version VARCHAR,
    generator_name VARCHAR,
    generator_version VARCHAR,
    library_versions VARCHAR,
    flags VARCHAR
);

-- Метаданные примененных сегментов Fact Log
CREATE TABLE _meta_segments (
    segment_id VARCHAR PRIMARY KEY,
    sha256 VARCHAR,
    row_count INTEGER,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### API:

```python
from polisyos.fabric.io.db import SimulationDB

# Инициализация
db = SimulationDB("simulation.duckdb")

# Сохранение макро-данных
macro_data = [
    {"run_id": "run_001", "step": 1, "gdp": 1000.0, "unemployment_rate": 0.05},
    {"run_id": "run_001", "step": 2, "gdp": 1020.0, "unemployment_rate": 0.04},
]
db.save_macro(macro_data)

# Сохранение среза агентов (тяжелая операция ~1M строк)
db.save_agents("run_001", step=50, agents_state=jax_agents_state)

# Сохранение метаданных прогона
db.save_run_record(run_record)

# SQL запросы
result = db.conn.execute("""
    SELECT step, gdp, unemployment_rate
    FROM macro_history
    WHERE run_id = 'run_001'
    ORDER BY step
""").fetchdf()

db.close()
```

#### Оптимизации производительности:

- **Bulk Inserts**: Использование нативного DuckDB API для массовых вставок
- **Memory Management**: Эффективная обработка больших DataFrame
- **Chunking**: Разделение больших операций на chunks для управления памятью
- **Connection Pooling**: Переиспользование соединений

### 2. Kùzu Graph Adapter (`graph_store.py`)

Графовый адаптер для хранения и анализа социально-экономических взаимодействий.

#### Ключевые возможности:

- **Entity-Event Graph**: Графовая модель агентов и их взаимодействий
- **Cypher Queries**: Поддержка Cypher языка запросов
- **Temporal Data**: Хранение временных аспектов взаимодействий
- **Network Analysis**: Возможности для анализа сетевых структур

#### Схема графа:

```cypher
-- Узлы (Agents)
CREATE NODE TABLE Agent(
    id STRING,
    type STRING,
    PRIMARY KEY(id)
);

-- Ребра (Interactions/Events)
CREATE REL TABLE Interaction(
    FROM Agent TO Agent,
    step INT64,
    amount DOUBLE,
    type STRING,
    predicate_id STRING,
    valid_time STRING,
    tx_time STRING
);
```

#### API:

```python
from polisyos.fabric.io.graph_store import GraphStore

# Инициализация
graph = GraphStore("simulation.kuzu")

# Добавление агентов
graph.add_agent("agent_001", "household")
graph.add_agent("agent_002", "firm")

# Добавление взаимодействий
graph.add_interaction(
    from_id="agent_001",
    to_id="agent_002",
    step=1,
    amount=100.0,
    type_="purchase",
    predicate_id="buys_from",
    valid_time="2024-01-01T00:00:00Z"
)

# Cypher запросы
network_data = graph.query("""
    MATCH (a:Agent)-[r:Interaction]->(b:Agent)
    WHERE r.step = 1 AND r.type = 'purchase'
    RETURN a.id as from_id, b.id as to_id, r.amount, r.type
""")

# Анализ сетевых метрик
centrality = graph.query("""
    MATCH (a:Agent)
    OPTIONAL MATCH (a)-[out:Interaction]->()
    OPTIONAL MATCH ()-[inp:Interaction]->(a)
    RETURN a.id,
           count(out) as out_degree,
           count(inp) as in_degree
""")
```

## Использование в системе

### Интеграция с Fabric Ingestion

```python
from polisyos.fabric.ingestion import run_ingestion

# Полный pipeline сохраняет данные в оба хранилища
run_ingestion(
    raw_dir=Path("data/raw"),
    curated_dir=Path("data/curated"),
    db_path=Path("simulation.duckdb"),
    kuzu_path=Path("simulation.kuzu"),
    source="simulation_data"
)
```

### Интеграция с UDF Engine

```python
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore

# Инициализация движка с обоими хранилищами
engine = UDFEngine(
    db=SimulationDB("simulation.duckdb"),
    graph=GraphStore("simulation.kuzu"),
    curated_dir=Path("data/curated")
)

# Реляционные запросы (DuckDB)
macro_data = engine.query(relational_request)

# Графовые запросы (Kùzu)
network_data = engine.query(network_request)
```

## Производительность и масштабируемость

### DuckDB Performance:
- **Read Performance**: ⭐⭐⭐⭐⭐ - Оптимизированные columnar запросы
- **Write Performance**: ⭐⭐⭐⭐⭐ - Bulk inserts через нативный API
- **Scalability**: До миллионов строк, подходит для временных рядов и срезов
- **Use Case**: Аналитические запросы, агрегации, временные ряды

### Kùzu Performance:
- **Read Performance**: ⭐⭐⭐⭐ - Графовые запросы с индексами
- **Write Performance**: ⭐⭐⭐ - Транзакционные вставки
- **Scalability**: Тысячи узлов/ребер, подходит для сетевого анализа
- **Use Case**: Социально-экономические взаимодействия, сетевой анализ

### Совместное использование:
- **Hybrid Queries**: UDF Engine автоматически выбирает оптимальное хранилище
- **Data Consistency**: Синхронизация между реляционными и графовыми данными
- **Backup & Recovery**: Независимое резервное копирование каждого хранилища

## Тестирование

```bash
# Тесты адаптеров хранения
pytest tests/fabric/test_io_adapters.py

# Интеграционные тесты с ingestion
pytest tests/integration/test_fabric_storage.py

# Бенчмарки производительности
pytest tests/benchmarks/test_storage_perf.py
```

## Архитектурные принципы

- **Storage Abstraction**: Единый интерфейс для разных технологий хранения
- **Performance-First**: Оптимизации специфичные для каждого хранилища
- **Schema Evolution**: Поддержка миграций схем данных
- **Data Integrity**: Валидация и consistency checks на уровне адаптеров