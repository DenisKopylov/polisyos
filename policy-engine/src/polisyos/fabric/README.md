# Polisyos Fabric: Unified Data Fabric

**Fabric** — это унифицированная система обработки и хранения данных для AI-driven симуляции экономической политики. Модуль обеспечивает полный жизненный цикл данных: от сырых CSV файлов до высокопроизводительных запросов через Unified Data Fabric (UDF).

## Архитектурная роль

Согласно [архитектурным принципам](../../../../../architecture.md) проекта, **Fabric** является ключевым компонентом **Runtime Backend**:

```
NL → LLM → IR (AST) → Compilation → Runtime (UDF + Foundry) → Artifacts
```

### Положение в графе зависимостей

- **Входящие зависимости**: Только `ir` (контракты и типы данных)
- **Исходящие зависимости**: Предоставляет данные для `scientist` и `foundry`
- **Принцип**: Граф зависимостей направлен только внутрь (Закон A)

### Ключевые обязанности

1. **Data Ingestion Pipeline**: Загрузка и валидация сырых данных
2. **Multi-Backend Storage**: Хранение в DuckDB + Kùzu
3. **Data Quality Management**: Валидация, reconciliation, manifests
4. **Entity Resolution**: Нормализация идентификаторов агентов
5. **Unified Data Fabric**: Безопасные запросы к разнородным данным

## Технологический стек

### Хранение данных
- **DuckDB**: Аналитическая реляционная БД (макро-метрики, срезы агентов)
- **Kùzu**: Встраиваемая графовая БД (социально-экономические взаимодействия)
- **PyArrow/Parquet**: Эффективная передача данных между компонентами

### Обработка данных
- **Pydantic v2**: Валидация схем и структур данных
- **pandas**: ETL и трансформации данных
- **hashlib**: Контроль целостности данных

### UDF (Unified Data Fabric)
- **Безопасные запросы**: Whitelist-based SQL/Cypher компиляция
- **Access Control**: PII tiers и classification
- **Schema-driven**: Конфигурация через JSON-схемы

## Структура модуля

```
fabric/
├── __init__.py              # Экспорт run_ingestion
├── ingestion.py             # Главный ETL pipeline
├── schema.py                # Pydantic модели данных
├── manifest.py              # Метаданные и качество данных
├── registry.py              # Управление манифестами
├── config.py                # Правила нормализации и reconciliation
├── io/                      # Интерфейсы хранения
│   ├── db.py               # DuckDB адаптер
│   └── graph_store.py      # Kùzu адаптер
└── udf/                     # Unified Data Fabric
    ├── engine.py           # UDF движок запросов
    ├── compiler.py         # Безопасный компилятор SQL/Cypher
    ├── plan.py             # Планы выполнения запросов
    ├── config.py           # UDF конфигурация и whitelist
    └── schema.py           # Реэкспорт типов из ir.data_views
```

## Ключевые компоненты

### 1. Data Ingestion Pipeline (`ingestion.py`)

Главный ETL-конвейер, обеспечивающий загрузку и обработку трех типов данных:

#### Функции:
- **`run_ingestion()`**: Оркестрация полного pipeline
- **`ingest_agents()`**: Загрузка данных агентов с entity resolution
- **`ingest_interactions()`**: Загрузка взаимодействий с reconciliation
- **`ingest_macro()`**: Загрузка макроэкономических показателей

#### Этапы обработки:
1. **Валидация**: Pydantic-схемы для каждой строки
2. **Трансформация**: Нормализация, entity resolution
3. **Хранение**: Загрузка в DuckDB + Kùzu
4. **Манифесты**: Генерация метаданных качества

### 2. Схемы данных (`schema.py`)

Pydantic v2 модели для строгой типизации и валидации:

```python
class AgentRow(BaseModel):
    agent_id: str           # Уникальный ID агента
    agent_type: str         # Тип агента (person, firm, government)
    age: int               # Возраст (0-120)
    income: float          # Доход (>=0)
    savings: float         # Сбережения (>=0)
    is_employed: bool      # Статус занятости

class InteractionRow(BaseModel):
    from_id: str           # Отправитель
    to_id: str             # Получатель
    step: int              # Шаг симуляции (>=0)
    amount: float          # Сумма транзакции (>=0)
    type: str              # Тип взаимодействия
    relation_type: Optional[str]  # Дополнительная классификация

class MacroRow(BaseModel):
    run_id: str            # ID прогона симуляции
    step: int              # Шаг (>=0)
    gdp: float             # ВВП (>=0)
    unemployment_rate: float  # Уровень безработицы (0-1)
    inflation_rate: float  # Инфляция (-100% до +1000%)
    avg_price: float       # Средняя цена (>=0)
    avg_income: float      # Средний доход (>=0)
    government_balance: float  # Баланс правительства
```

### 3. Data Quality & Manifests (`manifest.py`, `registry.py`)

#### Dataset Manifest
Метаданные для каждого загруженного датасета:

```python
class DatasetManifest(BaseModel):
    dataset_name: str
    source: str              # Источник данных
    license: str             # Лицензия
    raw_hash: str            # SHA256 хэш сырых данных
    schema_version: str      # Версия схемы
    row_count: int           # Количество строк
    pii_flags: Dict[str, bool]  # Флаги PII полей
    quality: QualityMetrics  # Метрики качества
    reconciliation: Optional[ReconciliationReport]  # Результат reconciliation
```

#### Quality Metrics
Автоматическая оценка качества данных:
- **missing_rate**: Доля пропущенных значений
- **duplicate_rate**: Доля дублированных строк
- **outlier_rate**: Доля выбросов
- **coverage**: Временные и географические границы

#### Manifest Registry
Централизованное управление манифестами с валидацией:
- Загрузка и кэширование манифестов
- Проверка reconciliation status
- Требование обязательных датасетов

### 4. Entity Resolution (`ingestion.py`, `config.py`)

Нормализация идентификаторов агентов для обеспечения консистентности:

#### Правила нормализации:
```python
NORMALIZATION_RULES = [
    {"pattern": r"\s+", "repl": "_"},      # Пробелы → подчеркивания
    {"pattern": r"[^a-zA-Z0-9_]", "repl": ""},  # Только буквы/цифры/подчеркивания
    {"pattern": r"_+", "repl": "_"},      # Множественные подчеркивания → одно
]
```

#### Процесс:
1. **Raw ID → Canonical ID**: "John_Doe_123" → "john_doe_123"
2. **Confidence Scoring**: Оценка уверенности в matching
3. **Mapping Table**: Сохранение соответствий для аудита

### 5. Reconciliation (`ingestion.py`, `config.py`)

Проверка баланса финансовых транзакций:

#### Правила reconciliation:
```python
RECONCILIATION_RULES = {
    "paid_tax": {"debit": "from_id", "credit": "to_id"},
    "transfer": {"debit": "from_id", "credit": "to_id"},
}
```

#### Процесс:
- Группировка транзакций по типам
- Расчет дебет/кредит сумм
- Проверка баланса с заданной toleranc'ей
- Генерация отчета с per-type breakdown

### 6. Storage Adapters (`io/`)

#### DuckDB Adapter (`db.py`)
```python
class SimulationDB:
    def __init__(self, db_path: str = "simulation.duckdb")
    def save_macro(self, data: list[dict])  # Макро-метрики
    def save_agents(self, run_id: str, step: int, agents_state)  # Срезы агентов
```

**Таблицы:**
- `macro_history`: Временные ряды макро-показателей
- `agents_snapshot`: Срезы состояния агентов по шагам
- `entity_resolution`: Соответствия raw/canonical ID
- `run_records`: Метаданные прогонов симуляции

#### Kùzu Graph Adapter (`graph_store.py`)
```python
class GraphStore:
    def add_agent(self, agent_id: str, agent_type: str)
    def add_interaction(self, from_id: str, to_id: str, step: int, amount: float, type_: str)
    def query(self, cypher: str, params: dict = None) -> pd.DataFrame
```

**Схема графа:**
- **Узлы (Nodes)**: Agent(id, type)
- **Ребра (Relationships)**: Interaction(step, amount, type)

### 7. Unified Data Fabric (`udf/`)

Безопасный слой запросов к разнородным данным:

#### Data View Types:
- **PANEL**: Временные ряды (макро-метрики)
- **SNAPSHOT**: Срезы агентов на конкретный шаг
- **NETWORK**: Графовые запросы (взаимодействия)

#### Безопасность:
- **Column Whitelist**: Разрешенные поля для каждого типа запросов
- **Access Tiers**: public/internal/sensitive PII классификация
- **SQL Injection Prevention**: Параметризованные запросы

#### UDF Engine:
```python
class UDFEngine:
    def compile(self, request: DataViewRequest) -> DataViewPlan
    def query(self, request: DataViewRequest) -> pd.DataFrame
    def execute(self, plan: DataViewPlan) -> pd.DataFrame
```

#### Schema-driven Configuration:
UDF конфигурация загружается из `data/curated/udf_schema.json`:
```json
{
  "allowed_columns": {
    "macro_history": ["run_id", "step", "gdp", "unemployment_rate"],
    "agents_snapshot": ["agent_id", "age", "income", "savings"]
  },
  "field_classification": {
    "agents_snapshot": {
      "agent_id": "sensitive",
      "income": "internal",
      "age": "public"
    }
  }
}
```

## API и использование

### Полный Ingestion Pipeline

```python
from pathlib import Path
from polisyos.fabric import run_ingestion

# Запуск полного pipeline ingestion
run_ingestion(
    raw_dir=Path("data/raw"),
    staging_dir=Path("data/staging"),
    curated_dir=Path("data/curated"),
    db_path=Path("simulation.duckdb"),
    kuzu_path=Path("simulation.kuzu"),
    source="demo_dataset",
    license_name="MIT"
)
```

### Индивидуальные функции ingestion

```python
from polisyos.fabric.ingestion import ingest_agents, ingest_interactions, ingest_macro
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore

# Инициализация хранилищ
db = SimulationDB("simulation.duckdb")
graph = GraphStore("simulation.kuzu")

# 1. Загрузка макро-данных
macro_path = ingest_macro(
    raw_path=Path("data/raw/macro.csv"),
    staging_dir=Path("data/staging"),
    curated_dir=Path("data/curated"),
    db=db,
    manifest_source="demo",
    manifest_license="MIT"
)

# 2. Загрузка агентов с entity resolution
agents_path, entity_map, resolution_path = ingest_agents(
    raw_path=Path("data/raw/agents.csv"),
    staging_dir=Path("data/staging"),
    curated_dir=Path("data/curated"),
    db=db,
    graph=graph,
    manifest_source="demo",
    manifest_license="MIT"
)

# 3. Загрузка взаимодействий с reconciliation
interactions_path = ingest_interactions(
    raw_path=Path("data/raw/interactions.csv"),
    staging_dir=Path("data/staging"),
    curated_dir=Path("data/curated"),
    graph=graph,
    entity_map=entity_map,
    manifest_source="demo",
    manifest_license="MIT"
)

db.close()
```

### Работа с Manifest Registry

```python
from polisyos.fabric.registry import ManifestRegistry

# Инициализация registry
registry = ManifestRegistry(Path("data/curated"))

# Получение манифеста с проверкой качества
agents_manifest = registry.require("agents")
macro_manifest = registry.require("macro")

# Проверка reconciliation status
if agents_manifest.reconciliation:
    if agents_manifest.reconciliation.status != "pass":
        raise ValueError("Agents data has reconciliation issues")

# Доступ к метаданным
print(f"Agents: {agents_manifest.row_count} rows")
print(f"Quality: {agents_manifest.quality.missing_rate:.2%} missing")
```

### UDF Queries

```python
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.ir.data_views import DataViewRequest, DataViewType, AccessTier

# Инициализация UDF движка
engine = UDFEngine(
    db=SimulationDB("simulation.duckdb"),
    graph=GraphStore("simulation.kuzu"),
    curated_dir=Path("data/curated")
)

# Запрос макро-метрик (PANEL view)
macro_request = DataViewRequest(
    view_type=DataViewType.PANEL,
    dataset_name="macro",
    metrics=["gdp", "unemployment_rate", "inflation_rate"],
    filters=[
        DataFilter(column="step", operator=">=", value=0),
        DataFilter(column="step", operator="<=", value=100)
    ],
    access_tier=AccessTier.PUBLIC
)

macro_data = engine.query(macro_request)
print(macro_data.head())

# Запрос среза агентов (SNAPSHOT view)
agents_request = DataViewRequest(
    view_type=DataViewType.SNAPSHOT,
    dataset_name="agents",
    metrics=["agent_id", "age", "income", "savings"],
    filters=[DataFilter(column="step", operator="=", value=50)],
    access_tier=AccessTier.INTERNAL
)

agents_snapshot = engine.query(agents_request)

# Графовый запрос (NETWORK view)
network_request = DataViewRequest(
    view_type=DataViewType.NETWORK,
    dataset_name="interactions",
    metrics=["degree_centrality", "betweenness_centrality"],
    filters=[
        DataFilter(column="step", operator="=", value=50),
        DataFilter(column="type", operator="=", value="transfer")
    ],
    access_tier=AccessTier.INTERNAL
)

network_metrics = engine.query(network_request)
```

### Низкоуровневая работа с хранилищами

```python
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore

# DuckDB операции
db = SimulationDB("simulation.duckdb")

# Сохранение макро-данных
macro_data = [
    {"run_id": "run_001", "step": 1, "gdp": 1000.0, "unemployment_rate": 0.05},
    {"run_id": "run_001", "step": 2, "gdp": 1020.0, "unemployment_rate": 0.04},
]
db.save_macro(macro_data)

# SQL запросы
result = db.conn.execute("""
    SELECT step, gdp, unemployment_rate
    FROM macro_history
    WHERE run_id = 'run_001'
    ORDER BY step
""").fetchdf()

# Kùzu операции
graph = GraphStore("simulation.kuzu")

# Добавление агентов и взаимодействий
graph.add_agent("agent_001", "household")
graph.add_agent("agent_002", "firm")
graph.add_interaction("agent_001", "agent_002", 1, 100.0, "purchase")

# Cypher запросы
network_data = graph.query("""
    MATCH (a:Agent)-[r:Interaction]->(b:Agent)
    WHERE r.step = 1
    RETURN a.id as from_id, b.id as to_id, r.amount, r.type
""")

db.close()
```

### Кастомная валидация данных

```python
import pandas as pd
from polisyos.fabric.schema import AgentRow, InteractionRow, MacroRow
from polisyos.fabric.ingestion import _validate_rows

# Загрузка CSV
df_raw = pd.read_csv("data/raw/agents.csv")

# Валидация через Pydantic
df_valid, rejects = _validate_rows(df_raw, AgentRow)

# Обработка ошибок валидации
if rejects:
    print(f"Найдено {len(rejects)} некорректных строк:")
    for reject in rejects[:5]:  # Показать первые 5
        print(f"Row {reject['row_index']}: {reject['errors']}")

print(f"Загружено {len(df_valid)} валидных агентов")
```

### Работа с Entity Resolution

```python
from polisyos.fabric.ingestion import _build_entity_resolution

# Данные агентов
agents_df = pd.DataFrame({
    'agent_id': ['John_Doe', 'john.doe@example.com', 'Agent-001', 'agent_001'],
    'age': [30, 30, 25, 25],
    'income': [50000, 50000, 40000, 40000]
})

# Построение entity resolution
resolution_df, entity_map = _build_entity_resolution(agents_df)

print("Entity mapping:")
for raw_id, canonical_id in entity_map.items():
    print(f"  {raw_id} → {canonical_id}")

print("\nResolution table:")
print(resolution_df)
```

### Reconciliation отчеты

```python
from polisyos.fabric.ingestion import _reconcile_interactions

# Данные взаимодействий
interactions_df = pd.DataFrame({
    'from_id': ['agent_1', 'agent_2', 'agent_1'],
    'to_id': ['gov', 'agent_1', 'agent_3'],
    'step': [1, 1, 1],
    'amount': [1000, 500, 300],
    'type': ['paid_tax', 'transfer', 'transfer']
})

# Проверка reconciliation
try:
    report = _reconcile_interactions(
        interactions_df,
        tolerance=1e-6,
        rules={
            "paid_tax": {"debit": "from_id", "credit": "to_id"},
            "transfer": {"debit": "from_id", "credit": "to_id"}
        }
    )
    print(f"Reconciliation: {report.status}")
    print(f"Total outflow: {report.total_outflow}")
    print(f"Total inflow: {report.total_inflow}")
    print(f"Difference: {report.diff}")
except ValueError as e:
    print(f"Reconciliation failed: {e}")
```

## Интеграция с системой

### Архитектурные принципы

Согласно [Закону A архитектуры](../../../../../architecture.md), Fabric находится на **Runtime Backend** уровне и обеспечивает данные для верхних уровней:

```
scientist → ir + fabric + foundry
fabric → ir (только контракты)
foundry → ir (только типы)
```

### Интерфейсы для Scientist (Orchestrator)

**Scientist** использует Fabric для загрузки baseline состояния и выполнения запросов к данным:

```python
# orchestrator/data_loader.py - загрузка начального состояния
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.registry import ManifestRegistry

class DataLoader:
    def __init__(self, curated_dir: Path):
        self.udf = UDFEngine(curated_dir=curated_dir)
        self.manifests = ManifestRegistry(curated_dir)

    def load_baseline_state(self) -> dict:
        """Загрузка baseline состояния агентов для симуляции."""
        request = DataViewRequest(
            view_type=DataViewType.SNAPSHOT,
            dataset_name="agents",
            metrics=["agent_id", "age", "income", "savings", "is_employed"],
            filters=[DataFilter(column="step", operator="=", value=0)]
        )
        return self.udf.query(request)
```

**Decision Packet** включает метаданные из Fabric manifests:

```python
# orchestrator/decision_packet.py
from polisyos.fabric.registry import ManifestRegistry

@dataclass
class DecisionPacket:
    ir: PolicyRequestIR
    manifests: Dict[str, DatasetManifest]  # Из Fabric
    run_record: RunRecord
    audit_trail: List[AuditEntry]
```

### Интерфейсы для Foundry (JAX Kernel)

**Foundry** получает агрегированные данные через UDF для калибровки моделей:

```python
# foundry/specs.py - калибровка механизмов на исторических данных
from polisyos.fabric.udf.engine import UDFEngine

def calibrate_tax_mechanism(udf: UDFEngine) -> TaxMechanism:
    """Калибровка налогового механизма на исторических данных."""
    # Запрос исторических макро-данных
    macro_request = DataViewRequest(
        view_type=DataViewType.PANEL,
        dataset_name="macro",
        metrics=["gdp", "government_balance", "avg_income"]
    )
    historical_data = udf.query(macro_request)

    # Калибровка параметров механизма
    # ... calibration logic ...

    return calibrated_mechanism
```

### Контракты из IR модуля

**Fabric** использует только контракты из `ir`, не имея зависимостей на логику:

```python
# fabric/udf/schema.py - реэкспорт типов из ir
from polisyos.ir.data_views import (
    AccessTier,      # Уровни доступа (public/internal/sensitive)
    DataFilter,      # Фильтры запросов
    DataViewRequest, # Запросы к данным
    DataViewType     # Типы представлений (PANEL/SNAPSHOT/NETWORK)
)

# fabric/schema.py - автономные Pydantic схемы
from pydantic import BaseModel, Field

class AgentRow(BaseModel):
    """Автономная схема агента - не зависит от ir типов."""
    agent_id: str = Field(..., max_length=64)
    # ... остальные поля
```

### Runtime Artifacts

**Fabric** генерирует артефакты, используемые во всех прогонах:

1. **Dataset Manifests**: Качество и метаданные датасетов
2. **Entity Resolution Maps**: Соответствия ID для аудита
3. **Reconciliation Reports**: Финансовые проверки
4. **UDF Schema**: Конфигурация безопасных запросов

### Workflow Integration

**Две трубы исполнения** (as-is архитектура):

#### Труба A: LangGraph Workflow
```
user_request → drafter → PolicyRequestIR → simulator_node → UDF + Foundry → artifacts
```

#### Труба B: Run Experiment Loop
```
UDF.query() → MockAgent → PolicyRequestIR → compile_policy → Foundry + Engine → persist
```

**Fabric** обеспечивает **UDF.query()** для обеих труб, предоставляя унифицированный доступ к данным независимо от workflow типа.

### Data Contracts & Schema Evolution

**Fabric** следует **Закону C** (контракты - единственный источник истины):

- Все артефакты имеют `schema_version`
- Миграции `vX → vY` через `common/migrations/`
- JSON Schema экспорт для валидации
- Pydantic v2 для runtime валидации

### Аудит и воспроизводимость (Закон D)

**Каждый прогон симуляции** фиксирует состояние Fabric:

```python
# fabric/io/db.py - сохранение метаданных прогона
def save_run_record(self, run_record: RunRecord):
    """Сохранение метаданных для воспроизводимости."""
    self.conn.execute("""
        INSERT INTO run_records (
            run_id, parent_run_id, seed, repro_mode, backend,
            python_version, platform, generated_at, schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_record.run_id, run_record.parent_run_id, run_record.seed,
        run_record.repro_mode, run_record.backend, run_record.python_version,
        run_record.platform, run_record.generated_at, run_record.schema_version
    ))
```

### Тестирование и контракты

**Fabric** имеет comprehensive тесты, проверяющие архитектурные границы:

```bash
# Тесты контрактов
pytest tests/contract/test_ir_contract.py     # IR контракты
pytest tests/contract/test_fabric_gates.py   # Fabric интерфейсы

# Интеграционные тесты
pytest tests/integration/test_workflow_smoke.py  # Полный workflow с Fabric

# Foundry интеграция
pytest tests/foundry/test_fiscal.py           # Fiscal с UDF данными
```

## Производительность и масштабируемость

### Оптимизации ingestion

**Эффективная обработка больших датасетов:**

- **Streaming validation**: Построчная валидация без загрузки всего файла в память
- **Parquet staging**: Колонный формат для промежуточного хранения
- **Batch operations**: Групповые вставки в базы данных
- **Parallel processing**: Независимая обработка разных типов данных

```python
# ingestion.py - оптимизированная валидация
def _validate_rows(df: pd.DataFrame, model: Type[BaseModel]) -> Tuple[pd.DataFrame, list[dict]]:
    """Память-эффективная валидация с streaming обработкой."""
    valid_rows = []
    rejects = []

    # Обработка по chunks для больших файлов
    chunk_size = 10000
    for start_idx in range(0, len(df), chunk_size):
        chunk = df.iloc[start_idx:start_idx + chunk_size]
        for idx, row in chunk.iterrows():
            # Валидация каждой строки отдельно
            data = row.to_dict()
            try:
                valid = model(**data).model_dump()
                valid_rows.append(valid)
            except ValidationError as exc:
                rejects.append({
                    "row_index": int(idx),
                    "errors": exc.errors(),
                    "raw": data
                })

    return pd.DataFrame(valid_rows), rejects
```

### Multi-backend storage стратегия

**Оптимальное использование каждого хранилища:**

| Хранилище | Use Case | Производительность | Масштабируемость |
|-----------|----------|-------------------|-------------------|
| **DuckDB** | Аналитические запросы, временные ряды | ⭐⭐⭐⭐⭐ | Миллионы строк |
| **Kùzu** | Графовые запросы, связи между агентами | ⭐⭐⭐⭐ | Тысячи узлов/ребер |
| **Parquet** | Хранение больших датасетов | ⭐⭐⭐⭐⭐ | Петабайты |

### UDF Query optimization

**Безопасность + производительность:**

- **Prepared statements**: Предкомпилированные SQL/Cypher запросы
- **Column pruning**: Выбор только необходимых колонок
- **Predicate pushdown**: Фильтры на уровне хранилища
- **Result caching**: Кэширование часто используемых запросов

```python
# udf/compiler.py - оптимизация запросов
def _compile_panel(self, req: DataViewRequest) -> DataViewPlan:
    """Компиляция PANEL запроса с оптимизациями."""
    table = self.ALLOWED_TABLES.get(req.dataset_name)
    if not table:
        raise ValueError(f"Unknown dataset: {req.dataset_name}")

    # Построение оптимизированного SQL
    select_cols = ", ".join(req.metrics)
    where_clauses = []

    for f in req.filters:
        if f.operator == "=":
            where_clauses.append(f"{f.column} = ?")
        elif f.operator == ">=":
            where_clauses.append(f"{f.column} >= ?")
        # ... другие операторы

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    sql = f"SELECT {select_cols} FROM {table} WHERE {where_sql} ORDER BY step"

    return DataViewPlan(
        request_id=str(uuid.uuid4()),
        view_type=req.view_type,
        dataset_name=req.dataset_name,
        table=table,
        sql=sql,
        params=[f.value for f in req.filters],
        access_tier=req.access_tier
    )
```

### Масштабирование данных

**Поддержка роста объема данных:**

- **Incremental loading**: Добавление данных без полной перезагрузки
- **Partitioning**: Разделение данных по времени/типам
- **Archival**: Автоматическое архивирование старых данных
- **Federated queries**: Запросы к распределенным хранилищам

### Memory management

**Эффективное использование памяти:**

- **Lazy loading**: Загрузка данных по требованию
- **Iterator patterns**: Потоковая обработка больших результатов
- **Garbage collection**: Явная очистка промежуточных объектов

```python
# io/db.py - оптимизированная загрузка агентов
def save_agents(self, run_id: str, step: int, agents_state):
    """
    Эффективное сохранение больших срезов агентов.
    ВНИМАНИЕ: Тяжелая операция (1M+ строк).
    """
    # 1. JAX массивы → NumPy (CPU) → Pandas
    # 2. Batch insert с chunking
    # 3. Memory cleanup после вставки

    chunk_size = 50000
    for i in range(0, len(agents_state), chunk_size):
        chunk = agents_state[i:i + chunk_size]
        # ... batch processing ...
```

### Benchmarking и профилирование

**Инструменты для анализа производительности:**

```bash
# Бенчмарки ingestion
python tools/benchmarks/bench_domain.py

# Профилирование UDF запросов
python tools/diagnostics/check_udf_perf.py

# Анализ качества данных
python tools/diagnostics/generate_ir_schema.py
```

### Производственные рекомендации

**Для больших deployment:**

1. **Hardware**: SSD хранилище, достаточная RAM (минимум 16GB)
2. **Data partitioning**: Разделение по времени/регионам
3. **Monitoring**: Отслеживание latency ingestion и query performance
4. **Backup strategy**: Регулярное резервное копирование manifests и схем
5. **Schema evolution**: План миграции при изменении контрактов

## Заключение

**Fabric** — это надежный фундамент Policy Engine, обеспечивающий:

- **Data integrity**: Строгая валидация и reconciliation
- **Performance**: Оптимизированные запросы и storage
- **Safety**: Безопасный доступ через UDF whitelist
- **Scalability**: Поддержка роста данных и нагрузки
- **Auditability**: Полная traceability всех операций

Модуль следует принципам архитектуры, обеспечивая чистое разделение ответственности между ingestion, storage, и query слоями, с четкими контрактами для интеграции с остальной системой.
