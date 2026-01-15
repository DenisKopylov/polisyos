# Polisyos Fabric: Unified Data Fabric

**Fabric** — это унифицированная система обработки и хранения данных для AI-driven симуляции экономической политики. Модуль обеспечивает полный жизненный цикл данных: от сырых CSV файлов до высокопроизводительных запросов через Unified Data Fabric (UDF).

## Архитектурная роль

Согласно [архитектурным принципам](../../../../../architecture.md) проекта, **Fabric** является ключевым компонентом **Runtime Backend**:

```
NL → LLM → IR (AST) → Compilation → Runtime (UDF + Foundry) → Artifacts
```

### Положение в графе зависимостей

- **Входящие зависимости**:
  - `ir` (контракты: `DataViewRequest`, `DataViewType`, `AccessTier`, `FactProvenance`, `FactLog` типы)
  - `core` (артефакты: `ArtifactRef`, `SchemaInfo`, `FileSystemCAS`, контракты: `EvidenceBundle`, `EvidenceStep`)
  - `common` (утилиты: `logger`)
- **Исходящие зависимости**: Предоставляет данные и инфраструктуру для `scientist` и `foundry`
- **Принцип**: Граф зависимостей направлен только внутрь (Закон A) - fabric зависит только от нижних уровней архитектуры

### Ключевые обязанности

1. **Data Ingestion Pipeline**: Полный ETL-конвейер от CSV до хранилищ с валидацией и evidence tracking
2. **Fact Log System**: Immutable хранение фактов в каноническом формате для audit trail
3. **Multi-Backend Storage**: Реляционное (DuckDB) + графовое (Kùzu) хранение данных
4. **Data Quality Management**: Автоматическая оценка качества, reconciliation, dataset manifests
5. **Entity Resolution**: Нормализация и дедупликация идентификаторов агентов
6. **Evidence System**: Криптографически verifiable доказательства происхождения данных
7. **Unified Data Fabric**: Безопасный компилируемый слой запросов с whitelist и privacy controls
8. **Materialization Engine**: Восстановление реляционных представлений из immutable фактов

## Технологический стек

### Хранение данных
- **DuckDB**: Аналитическая реляционная БД (макро-метрики, срезы агентов)
- **Kùzu**: Встраиваемая графовая БД (социально-экономические взаимодействия)
- **PyArrow/Parquet**: Эффективная передача данных между компонентами

### Обработка данных
- **Pydantic v2**: Строгая типизация и валидация структур данных
- **pandas**: ETL трансформации и анализ данных
- **hashlib**: SHA256 контроль целостности данных
- **PyArrow**: Эффективная передача данных между компонентами

### Fact Log & Evidence
- **Canonical JSON**: Детерминированная сериализация фактов
- **Immutable Storage**: Append-only хранение с provenance tracking
- **Trust Policies**: Многоуровневые политики доверия к источникам

### UDF (Unified Data Fabric)
- **Compilation Pipeline**: Многофазная компиляция запросов с оптимизациями
- **Security-First**: Whitelist-based SQL/Cypher, PII classification, access tiers
- **Schema-Driven**: JSON-конфигурация разрешенных операций и полей

## Структура модуля

```
fabric/
├── __init__.py              # Экспорт run_ingestion (главный API)
├── ingestion.py             # Главный ETL pipeline с Fact Log и evidence
├── schema.py                # Pydantic модели данных (AgentRow, InteractionRow, MacroRow)
├── manifest.py              # Метаданные и качество данных (DatasetManifest, QualityMetrics)
├── registry.py              # Управление манифестами датасетов
├── config.py                # Правила нормализации и reconciliation
├── evidence.py              # Система доказательств (EvidenceBundle, provenance tracking)
├── materializer.py          # Материализация из Fact Log в реляционные хранилища
├── segment_manifest.py      # Управление сегментами Fact Log
├── fact_writer.py           # Запись фактов в каноническом формате (build_fact, facts_from_dataframe)
├── trust.py                 # Политики доверия и верификации источников
├── io/                      # Интерфейсы хранения данных
│   ├── __init__.py          # Экспорт адаптеров хранения
│   ├── db.py                # DuckDB адаптер (SimulationDB)
│   └── graph_store.py       # Kùzu графовый адаптер (GraphStore)
└── udf/                     # Unified Data Fabric - безопасный слой запросов
    ├── __init__.py          # Экспорт UDF компонентов
    ├── engine.py            # UDF движок запросов (UDFEngine)
    ├── compiler.py          # Безопасный компилятор SQL/Cypher (ViewCompiler)
    ├── plan.py              # Планы выполнения запросов (DataViewPlan)
    ├── config.py            # UDF конфигурация и whitelist (UdfSchema)
    ├── schema.py            # Реэкспорт типов из ir.data_views
    └── passes/              # Компиляционный пайплайн запросов
        ├── __init__.py      # Экспорт всех pass-функций
        ├── lowering.py      # Понижение уровня абстракции (SQL/Cypher generation)
        ├── merge.py         # Слияние и оптимизация запросов
        ├── privacy.py       # Контроль приватности и PII-фильтрация
        ├── resolution.py    # Разрешение имен таблиц/колонок и зависимостей
        └── typecheck.py     # Проверка типов данных и единиц измерения
```

## Ключевые компоненты

### 1. Data Ingestion Pipeline (`ingestion.py`)

Комплексный ETL-конвейер, обеспечивающий загрузку, валидацию и обработку данных с полным evidence tracking:

#### Основные функции:
- **`run_ingestion()`**: Оркестрация полного pipeline с evidence bundle созданием
- **`ingest_agents()`**: Загрузка агентов с entity resolution и записью в Fact Log
- **`ingest_interactions()`**: Загрузка взаимодействий с reconciliation и графовым хранением
- **`ingest_macro()`**: Загрузка макро-метрик с временными рядами

#### Расширенные этапы обработки:
1. **Валидация**: Pydantic v2 схемы с детальными ошибками валидации
2. **Трансформация**: Entity resolution, нормализация ID, reconciliation проверка
3. **Fact Log**: Запись immutable фактов с provenance и trust metadata
4. **Хранение**: Параллельная загрузка в DuckDB (реляционное) + Kùzu (графовое)
5. **Evidence**: Создание криптографически verifiable доказательств происхождения
6. **Манифесты**: Генерация метаданных качества и reconciliation отчетов

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

Безопасный слой запросов к разнородным данным с компиляторным пайплайном:

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
    def __init__(
        self,
        db: SimulationDB,
        graph: Optional[GraphStore] = None,
        curated_dir: Path | str = Path("data/curated"),
        schema: Optional[UdfSchema] = None,
        cas_root: Path | str = Path(".polisyos"),
    ):
        # Инициализация с multi-backend storage и CAS

    def compile(self, request: DataViewRequest) -> DataViewPlan
    def query(self, request: DataViewRequest) -> pd.DataFrame
    def query_arrow(self, request: DataViewRequest) -> pa.Table
    def query_result(self, request: DataViewRequest) -> FabricResult
    def _execute(self, plan: DataViewPlan, *, as_arrow: bool = False)
```

**Новые возможности:**
- **FabricResult**: Структурированный результат с evidence и provenance
- **Arrow Support**: Эффективная работа с columnar данными
- **CAS Integration**: Автоматическое сохранение запросов, планов и результатов

#### Compilation Pipeline (`passes/`):
UDF использует последовательность компиляционных проходов для безопасной трансформации запросов:

1. **Resolution Pass** (`resolution.py`): Разрешение имен таблиц, колонок и зависимостей
2. **Typecheck Pass** (`typecheck.py`): Валидация типов данных и единиц измерения
3. **Merge Pass** (`merge.py`): Оптимизация и слияние запросов
4. **Privacy Pass** (`privacy.py`): Контроль приватности и PII-фильтрация
5. **Lowering Pass** (`lowering.py`): Понижение уровня абстракции до SQL/Cypher

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

### 8. Fact Log System (Фактовая система)

Immutable система хранения фактов для полного audit trail и воспроизводимости:

#### Fact Writer (`fact_writer.py`)
Преобразование DataFrame в канонические факты с deterministic ID generation:

```python
def build_fact(
    *,
    subject_id: str,
    predicate_id: str,
    object_value: Any = None,
    target_id: str | None = None,
    valid_time: Any = None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> Fact:
    """Создание факта с provenance, trust и legal metadata."""
```

```python
def facts_from_dataframe(
    df: pd.DataFrame,
    *,
    subject_field: str,
    predicate_value_map: dict[str, str],
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
) -> list[Fact]:
    """Преобразование DataFrame в список фактов."""
```

**Особенности:**
- **Deterministic IDs**: SHA256-based генерация уникальных ID фактов
- **Canonical JSON**: Детерминированная сериализация для consistency
- **Provenance Tracking**: Полная traceability от источника до использования
- **Trust Policies**: Многоуровневые политики доверия к источникам
- **Temporal Validity**: Поддержка valid_time для временных фактов
- **Legal Metadata**: Информация о юридических аспектах данных

#### Segment Manifests (`segment_manifest.py`)
Управление сегментами Fact Log с метаданными для эффективного хранения:

```python
def write_segment_manifest(manifest: FactSegmentManifest, manifest_path: Path) -> Path:
    """Запись манифеста сегмента с метаданными о фактах."""
```

**Структура сегментов:**
- Группировка фактов по времени/типу для эффективного доступа
- Метаданные: count, hash, schema_version, provenance info
- Append-only: новые факты только добавляются

#### Materializer (`materializer.py`)
Восстановление реляционных представлений из immutable Fact Log:

```python
def materialize_duckdb_from_fact_log(fact_dir: Path, db: SimulationDB) -> None:
    """Материализация DuckDB таблиц из Fact Log сегментов (placeholder)."""
```

**Текущий статус:** Placeholder реализация с логированием наличия сегментов. Полная реализация в разработке.

**Преимущества архитектуры:**
- **Complete Audit Trail**: Полная история всех изменений данных
- **Reproducibility**: Восстановление любого состояния системы
- **Schema Evolution**: Безопасная миграция между версиями схем
- **Distributed Storage**: Поддержка распределенного хранения фактов
- **Data Lineage**: Полная traceability от сырых данных до результатов

### 9. Evidence System (`evidence.py`)

Криптографически verifiable система доказательств происхождения данных:

#### Evidence Bundles
```python
def build_evidence_bundle(
    *,
    sources: list[ArtifactRef] | None = None,
    transforms: list[EvidenceStep] | None = None,
    trust_policy_id: str | None = None,
    notes: list[str] | None = None,
) -> EvidenceBundle:
    """Создание пакета доказательств для датасета."""
```

```python
def persist_evidence_bundle(
    store: FileSystemCAS,
    bundle: EvidenceBundle,
    *,
    schema_name: str = "fabric.evidence_bundle",
    schema_version: str = "1.0",
) -> EvidenceBundleRef:
    """Сохранение EvidenceBundle в CAS с versioning."""
```

**Компоненты:**
- **Sources**: ArtifactRef на исходные данные и конфигурации
- **Transforms**: EvidenceStep с описанием каждого шага обработки
- **Trust Policies**: ID политики для верификации уровня доверия
- **Notes**: Контекстная информация и дополнительные метаданные

**Интеграция с CAS:** Evidence bundles хранятся в Content Addressable Storage для immutable persistence.

### 10. Trust System (`trust.py`)

Система политик доверия для источников данных и верификации качества:

#### Trust Policies
Определение уровней доверия к различным источникам данных:
- **Policy Definition**: JSON-based конфигурация политик доверия
- **Source Validation**: Проверка соответствия данных политике
- **Risk Assessment**: Оценка рисков использования данных

**Интеграция:** Используется в Fact Writer и Evidence Bundles для маркировки уровня доверия к данным.

## API и использование

### Полный Ingestion Pipeline

```python
from pathlib import Path
from polisyos.fabric import run_ingestion

# Запуск полного pipeline ingestion с evidence tracking
run_ingestion(
    raw_dir=Path("data/raw"),
    staging_dir=Path("data/staging"),
    curated_dir=Path("data/curated"),
    fact_dir=Path("data/facts"),  # Новое: директория для Fact Log
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

### Работа с Fact Log системой

```python
from pathlib import Path
from polisyos.fabric.fact_writer import build_fact, facts_from_dataframe, write_fact_segment
from polisyos.fabric.segment_manifest import write_segment_manifest
from polisyos.ir.fact_log import FactProvenance, FactTrust

# Создание фактов из DataFrame
agents_df = pd.DataFrame({
    'agent_id': ['agent_001', 'agent_002'],
    'age': [30, 25],
    'income': [50000, 40000],
    'savings': [10000, 5000]
})

# Настройка provenance с trust policy
provenance = FactProvenance(
    source_artifact_id="agents_ingestion_run_001",
    transform_id="entity_resolution_v1",
    trust_policy_id="standard_trust",
    collected_at="2024-01-11T10:00:00Z"
)

# Преобразование DataFrame в факты с mapping полей
facts = facts_from_dataframe(
    df=agents_df,
    subject_field="agent_id",
    predicate_value_map={
        "has_age": "age",
        "has_income": "income",
        "has_savings": "savings"
    },
    provenance=provenance,
    trust_policy_id="standard_trust"
)

# Запись сегмента фактов
segment_path = write_fact_segment(
    facts=facts,
    segment_dir=Path("data/facts"),
    segment_id="agents_segment_001"
)

# Создание и запись манифеста сегмента
from polisyos.ir.fact_log import FactSegmentManifest
manifest = FactSegmentManifest(
    segment_id="agents_segment_001",
    fact_count=len(facts),
    schema_version="1.0",
    provenance=provenance
)
manifest_path = write_segment_manifest(manifest, Path("data/facts") / "manifests")

print(f"Записано {len(facts)} фактов в {segment_path}")
print(f"Манифест сегмента: {manifest_path}")
```

### Работа с Evidence Bundles

```python
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.core.contracts.fabric import EvidenceStep
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from pathlib import Path

# Создание пакета доказательств
evidence_bundle = build_evidence_bundle(
    sources=[
        ArtifactRef(
            artifact_id="raw_agents_csv",
            artifact_type="dataset",
            version="1.0"
        )
    ],
    transforms=[
        EvidenceStep(
            step_id="entity_resolution",
            description="Entity resolution and normalization",
            inputs=["raw_agents_csv"],
            outputs=["normalized_agents"],
            parameters={"normalization_rules": "v1"}
        ),
        EvidenceStep(
            step_id="validation",
            description="Pydantic validation",
            inputs=["normalized_agents"],
            outputs=["validated_agents"],
            parameters={"schema_version": "1.0"}
        ),
        EvidenceStep(
            step_id="fact_log_ingestion",
            description="Ingestion into Fact Log",
            inputs=["validated_agents"],
            outputs=["facts_segment_001"],
            parameters={"fact_count": 1500, "segment_id": "agents_segment_001"}
        )
    ],
    trust_policy_id="fabric_standard_trust",
    notes=[
        "Data collected from simulation run 001",
        "Entity resolution applied with confidence scoring",
        "All facts written to immutable Fact Log"
    ]
)

# Сохранение в CAS
cas = FileSystemCAS(Path(".polisyos"))
evidence_ref = persist_evidence_bundle(cas, evidence_bundle)

print(f"Evidence bundle created with {len(evidence_bundle.transforms)} steps")
print(f"Persisted as artifact: {evidence_ref.artifact_id}")
```

### Материализация из Fact Log

```python
from polisyos.fabric.materializer import materialize_duckdb_from_fact_log
from polisyos.fabric.io.db import SimulationDB

# Инициализация хранилища
db = SimulationDB("simulation.duckdb")

# Материализация из Fact Log
fact_dir = Path("data/facts")
materialize_duckdb_from_fact_log(fact_dir, db)

print("DuckDB materialized from Fact Log")
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
scientist → ir + fabric + foundry + runtime
fabric → ir + common (только контракты и утилиты)
foundry → ir + common (только типы и утилиты)
runtime → common (инфраструктура)
```

**Новые компоненты и связи:**
- **Fact Log System**: Интеграция с `ir.fact_log` для immutable хранения фактов
- **Evidence System**: Использование `core.contracts.fabric` и `core.artifacts` для verifiable доказательств
- **UDF Compilation Pipeline**: Многофазный компилятор с passes для security и optimization
- **Materializer Engine**: Восстановление реляционных представлений из Fact Log (в разработке)
- **Trust Policies**: Многоуровневые политики доверия для источников данных
- **CAS Integration**: Content Addressable Storage для всех артефактов и evidence

### Интерфейсы для Scientist (Orchestrator)

**Scientist** использует Fabric для загрузки baseline состояния, выполнения безопасных запросов и работы с evidence:

```python
# orchestrator/data_loader.py - загрузка начального состояния
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.registry import ManifestRegistry
from polisyos.fabric.evidence import build_evidence_bundle
from polisyos.fabric.materializer import materialize_duckdb_from_fact_log

class DataLoader:
    def __init__(self, curated_dir: Path, fact_dir: Path):
        self.udf = UDFEngine(curated_dir=curated_dir)
        self.manifests = ManifestRegistry(curated_dir)
        self.fact_dir = fact_dir

    def load_baseline_state(self) -> dict:
        """Загрузка baseline состояния агентов для симуляции."""
        request = DataViewRequest(
            view_type=DataViewType.SNAPSHOT,
            dataset_name="agents",
            metrics=["agent_id", "age", "income", "savings", "is_employed"],
            filters=[DataFilter(column="step", operator="=", value=0)],
            access_tier=AccessTier.INTERNAL
        )
        return self.udf.query(request)

    def ensure_materialized_state(self) -> None:
        """Обеспечение актуального состояния через материализацию."""
        # Материализация из Fact Log если необходимо
        from polisyos.fabric.io.db import SimulationDB
        db = SimulationDB()
        materialize_duckdb_from_fact_log(self.fact_dir, db)
        db.close()

    def build_evidence_for_run(self, run_id: str) -> EvidenceBundle:
        """Создание доказательств для прогона симуляции."""
        return build_evidence_bundle(
            sources=self.manifests.require("agents").to_artifact_ref(),
            transforms=[
                EvidenceStep(
                    step_id="baseline_loading",
                    description=f"Loading baseline state for run {run_id}",
                    inputs=["agents_manifest"],
                    outputs=[f"baseline_{run_id}"]
                )
            ],
            trust_policy_id="scientist_baseline_trust"
        )
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

**Fabric** генерирует артефакты, используемые во всех прогонах симуляции:

1. **Dataset Manifests**: Метаданные качества, схемы и статистика датасетов
2. **Entity Resolution Maps**: Соответствия raw/canonical ID с confidence scoring
3. **Reconciliation Reports**: Отчеты о финансовом балансе транзакций
4. **UDF Schema Configuration**: JSON-схемы разрешенных операций и полей
5. **Fact Segments**: Immutable факты в canonical JSON формате
6. **Segment Manifests**: Метаданные сегментов Fact Log (count, hash, provenance)
7. **Evidence Bundles**: Криптографически verifiable доказательства происхождения
8. **Query Plans & Results**: Компилированные планы запросов и их результаты в CAS
9. **Trust Policy Artifacts**: Определения политик доверия для источников

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

# Тесты компонентов Fabric
pytest tests/core_phase0/test_artifact_store.py  # Хранение артефактов
pytest tests/core_phase0/test_canon_json.py      # Канонический JSON

# Интеграционные тесты
pytest tests/integration/test_workflow_smoke.py  # Полный workflow с Fabric

# Foundry интеграция
pytest tests/foundry/test_fiscal.py           # Fiscal с UDF данными
pytest tests/foundry/test_constraints_executor.py  # Constraints с данными Fabric

# Специфические тесты новых компонентов
pytest tests/contract/test_fabric_gates.py   # Evidence bundles и контракты
# Fact Log тестируется через integration тесты
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
- **Fact Log Segmentation**: Разделение immutable фактов на сегменты для эффективного хранения
- **Lazy Materialization**: Материализация данных по требованию из Fact Log
- **Distributed Fact Storage**: Поддержка распределенного хранения фактов

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

- **Data integrity**: Строгая валидация, reconciliation и evidence tracking
- **Immutability**: Fact Log система для полного audit trail
- **Performance**: Оптимизированные запросы и multi-backend storage
- **Safety**: Безопасный доступ через UDF whitelist и privacy passes
- **Scalability**: Поддержка роста данных через сегментацию и материализацию
- **Auditability**: Полная traceability от сырых данных до симуляционных результатов
- **Schema Evolution**: Безопасная миграция через контракты и versioning
- **Reproducibility**: Восстановление любого состояния через Fact Log

**Новые возможности:**
- **Fact Log System**: Complete immutable audit trail с deterministic fact IDs
- **Evidence Bundles**: Cryptographically verifiable provenance tracking
- **UDF Compilation Pipeline**: Multi-phase compilation с security passes
- **Materializer Engine**: Lazy материализация реляционных представлений из фактов
- **Trust Policies**: Multi-tier trust validation для источников данных
- **CAS Integration**: Content-addressable storage для всех артефактов
- **Arrow Support**: High-performance columnar data processing

Модуль следует принципам архитектуры (Законы A, B, C, D), обеспечивая чистое разделение ответственности между ingestion, storage, query и audit слоями, с четкими контрактами для интеграции с остальной системой.
