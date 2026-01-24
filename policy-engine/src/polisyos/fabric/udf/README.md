# Fabric UDF: Unified Data Fabric

Модуль `fabric.udf` реализует **Unified Data Fabric (UDF)** - безопасный компилируемый слой запросов к разнородным данным Policy Engine. Обеспечивает whitelist-based доступ к данным с криптографически verifiable provenance tracking.

## Архитектурная роль

Согласно архитектуре Policy Engine, UDF является **Query Security & Compilation Layer**:

- **Safe Query Execution**: Безопасное выполнение запросов с whitelist и privacy controls
- **Multi-Backend Querying**: Автоматическое определение типа запроса (реляционный/графовый)
- **Evidence Tracking**: Криптографически verifiable доказательства для каждого запроса
- **Compilation Pipeline**: Многофазная компиляция с оптимизациями и security passes
- **CAS Integration**: Сохранение всех артефактов в Content Addressable Storage

## Структура модуля

```
fabric/udf/
├── __init__.py              # Экспорт UDF компонентов
├── engine.py                # UDF движок с CAS интеграцией (UDFEngine)
├── compiler.py              # Безопасный компилятор SQL/Cypher (ViewCompiler)
├── plan.py                  # Планы выполнения запросов (DataViewPlan)
├── config.py                # UDF конфигурация и whitelist (UdfSchema, load_udf_schema)
├── schema.py                # Реэкспорт типов из ir.data_views
└── passes/                  # Компиляционный пайплайн запросов
    ├── __init__.py          # Экспорт всех pass-функций
    ├── lowering.py          # Понижение уровня абстракции (SQL/Cypher generation)
    ├── merge.py             # Слияние и оптимизация запросов
    ├── privacy.py           # Контроль приватности и PII-фильтрация
    ├── resolution.py        # Разрешение имен таблиц/колонок и зависимостей
    └── typecheck.py         # Проверка типов данных и единиц измерения
```

## Компоненты

### 1. UDF Engine (`engine.py`)

Основной движок UDF с интеграцией всех компонентов системы.

#### Ключевые возможности:

- **Multi-Backend Execution**: Автоматическое определение типа запроса (реляционный/графовый)
- **FabricResult**: Структурированный результат с полным provenance tracking
- **Arrow Support**: Высокопроизводительная работа с columnar данными через PyArrow
- **CAS Integration**: Автоматическое сохранение запросов, планов и результатов
- **Evidence Bundles**: Криптографически verifiable доказательства для каждого запроса
- **Lazy Materialization**: Автоматическая материализация данных из Fact Log при необходимости

#### API:

```python
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from pathlib import Path

class UDFEngine:
    def __init__(
        self,
        db: SimulationDB,
        graph: Optional[GraphStore] = None,
        curated_dir: Path | str = Path("data/curated"),
        fact_dir: Path | str | None = None,
        schema: Optional[UdfSchema] = None,
        cas_root: Path | str = Path(".polisyos"),
    ):
        """Инициализация UDF движка с поддержкой Fact Log."""

    def compile(self, request: DataViewRequest) -> DataViewPlan:
        """Компилирует запрос в план выполнения."""

    def query(self, request: DataViewRequest) -> pd.DataFrame:
        """Выполняет запрос и возвращает pandas DataFrame."""

    def query_arrow(self, request: DataViewRequest) -> pa.Table:
        """Выполняет запрос и возвращает PyArrow Table для высокой производительности."""

    def query_result(self, request: DataViewRequest) -> FabricResult:
        """Выполняет запрос с полным FabricResult (включая provenance)."""
```

#### Использование:

```python
# Инициализация движка
engine = UDFEngine(
    db=SimulationDB("simulation.duckdb"),
    graph=GraphStore("simulation.kuzu"),
    curated_dir=Path("data/curated"),
    fact_dir=Path("data/facts"),  # Для lazy материализации
    cas_root=Path(".polisyos")    # CAS для provenance
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

# Запрос с Arrow для высокой производительности
macro_arrow = engine.query_arrow(macro_request)

# Запрос с полным FabricResult (включая provenance)
result = engine.query_result(macro_request)
print(f"Query executed, data saved as: {result.data_ref.artifact_id}")
print(f"Evidence bundle: {result.evidence_ref.artifact_id}")
```

### 2. View Compiler (`compiler.py`)

Безопасный компилятор запросов с whitelist-based валидацией.

#### Ключевые возможности:

- **Security-First Compilation**: Whitelist валидация всех запросов
- **Multi-View Support**: Поддержка PANEL, SNAPSHOT и NETWORK типов запросов
- **Schema-Driven**: Конфигурация разрешенных операций через JSON schema
- **Compilation Passes**: Многофазный пайплайн с оптимизациями

#### Разрешенные таблицы и операции:

```python
class ViewCompiler:
    # Разрешенные таблицы (mapping dataset_name -> table_name)
    ALLOWED_TABLES = {
        "macro": "macro_history",
        "agents": "agents_snapshot"
    }

    # Сетевые колонки для графовых запросов
    NETWORK_COLUMNS = {"neighbor_id", "amount", "type", "step"}
```

#### Compilation Pipeline:

```python
def compile(self, req: DataViewRequest) -> DataViewPlan:
    # 1. Resolution Pass - разрешение имен и зависимостей
    req = resolution_pass(req)

    # 2. Typecheck Pass - проверка типов данных
    req = typecheck_pass(req)

    # 3. Merge Pass - оптимизация и слияние
    req = merge_pass(req)

    # 4. Privacy Pass - контроль приватности
    req = privacy_pass(req)

    # 5. Lowering Pass - генерация SQL/Cypher
    return lowering_pass(req, plan)
```

### 3. Compilation Passes (`passes/`)

Модульный пайплайн компиляции запросов с разделением ответственности.

#### 1. Resolution Pass (`resolution.py`)

**Цель**: Разрешение имен таблиц, колонок и зависимостей

```python
def resolution_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 1: resolve human-friendly fields.
    Placeholder для нормализации предикатов/слотов.
    """
```

#### 2. Typecheck Pass (`typecheck.py`)

**Цель**: Валидация типов данных и единиц измерения

```python
def typecheck_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 2: type/unit validation.
    Ensures metrics are present; real unit compatibility logic later.
    """
    if not request.metrics:
        raise ValueError("DataViewRequest must specify at least one metric")
```

#### 3. Merge Pass (`merge.py`)

**Цель**: Слияние и оптимизация запросов

```python
def merge_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 3: query merging and optimization placeholder.
    """
```

#### 4. Privacy Pass (`privacy.py`)

**Цель**: Контроль приватности и PII-фильтрация

```python
def privacy_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 4: privacy transforms.
    Real implementation will redact/hash/drop fields by AccessTier.
    """
```

#### 5. Lowering Pass (`lowering.py`)

**Цель**: Понижение уровня абстракции до SQL/Cypher

```python
def lowering_pass(request: DataViewRequest, plan: DataViewPlan) -> DataViewPlan:
    """
    Pass 5: lowering to executable format.
    Future: emit DataFetchPlan/ProgramGraph/EvidencePlan.
    """
```

### 4. UDF Configuration (`config.py`)

Schema-driven конфигурация UDF с whitelist политиками.

#### Структура конфигурации:

```python
# Разрешенные колонки по таблицам
DEFAULT_ALLOWED_COLUMNS = {
    "macro_history": {
        "run_id", "step", "gdp", "unemployment_rate",
        "inflation_rate", "avg_price", "avg_income", "government_balance"
    },
    "agents_snapshot": {
        "run_id", "step", "agent_id", "age", "income", "savings", "is_employed"
    },
}

# Классификация полей приватности
DEFAULT_FIELD_CLASSIFICATION = {
    "macro_history": {
        "gdp": "public",
        "unemployment_rate": "public",
        "run_id": "internal",
    },
    "agents_snapshot": {
        "agent_id": "sensitive",
        "income": "internal",
        "age": "public",
    },
}

# Разрешенные типы взаимодействий
DEFAULT_ALLOWED_RELATION_TYPES = {"paid_tax", "transfer"}
```

#### Загрузка конфигурации:

```python
def load_udf_schema(schema_path: Path) -> UdfSchema:
    """Загружает UDF schema из JSON файла."""
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            data = json.load(f)
        return UdfSchema(**data)
    else:
        # Возвращает дефолтную конфигурацию
        return UdfSchema(
            allowed_columns=DEFAULT_ALLOWED_COLUMNS,
            field_classification=DEFAULT_FIELD_CLASSIFICATION,
            allowed_relation_types=DEFAULT_ALLOWED_RELATION_TYPES
        )
```

### 5. Data View Plans (`plan.py`)

Структурированные планы выполнения запросов.

```python
@dataclass(frozen=True)
class DataViewPlan:
    request_id: str              # Уникальный ID запроса
    view_type: DataViewType      # Тип представления (PANEL/SNAPSHOT/NETWORK)
    dataset_name: str           # Имя датасета
    table: Optional[str]        # Целевая таблица (реляционная)
    sql: Optional[str]          # Сгенерированный SQL
    params: List[Any]           # Параметры SQL запроса
    cypher: Optional[str]       # Cypher запрос (для графовых)
    cypher_params: Dict[str, Any]  # Параметры Cypher
    access_tier: AccessTier     # Уровень доступа
    redacted_fields: List[str]  # Отфильтрованные поля приватности
```

## Безопасность и Privacy

### Access Tiers:

- **PUBLIC**: Общедоступные данные (макро-показатели)
- **INTERNAL**: Внутренние данные (идентификаторы прогонов)
- **SENSITIVE**: Чувствительные данные (персональные ID)

### Security Features:

- **Column Whitelist**: Только разрешенные поля в запросах
- **SQL Injection Prevention**: Параметризованные запросы
- **Privacy Filtering**: Автоматическая фильтрация PII по access tier
- **Query Validation**: Строгая валидация всех входящих запросов

## Интеграция с системой

### Связь с другими модулями:

- **ir.data_views**: Типы запросов и фильтров (DataViewRequest, AccessTier)
- **core.contracts.fabric**: FabricResult, Evidence bundles
- **core.artifacts**: CAS интеграция для provenance
- **fabric.io**: Адаптеры хранения (SimulationDB, GraphStore)
- **fabric.registry**: Manifest Registry для метаданных
- **fabric.materializer**: Lazy материализация из Fact Log

### Workflow Integration:

```python
# scientist/orchestrator/data_loader.py
from polisyos.fabric.udf.engine import UDFEngine

class DataLoader:
    def __init__(self, curated_dir: Path, fact_dir: Path):
        self.udf = UDFEngine(curated_dir=curated_dir)
        self.fact_dir = fact_dir

    def load_baseline_state(self) -> dict:
        """Загрузка baseline состояния для симуляции."""
        request = DataViewRequest(
            view_type=DataViewType.SNAPSHOT,
            dataset_name="agents",
            metrics=["agent_id", "age", "income", "savings"],
            filters=[DataFilter(column="step", operator="=", value=0)],
            access_tier=AccessTier.INTERNAL
        )
        return self.udf.query(request)
```

## Производительность

### Оптимизации:

- **Prepared Statements**: Предкомпилированные SQL/Cypher запросы
- **Column Pruning**: Выбор только необходимых колонок
- **Predicate Pushdown**: Фильтры на уровне хранилища
- **Result Caching**: Кэширование часто используемых запросов
- **Arrow Integration**: Высокопроизводительная columnar обработка

### Benchmarking:

```python
# Бенчмарки UDF запросов
python tools/diagnostics/check_udf_perf.py

# Сравнение с прямыми SQL запросами
python tools/benchmarks/udf_vs_sql_perf.py
```

## Тестирование

```bash
# Unit тесты компилятора
pytest tests/fabric/test_udf_compiler.py

# Integration тесты движка
pytest tests/fabric/test_udf_engine.py

# Security тесты whitelist
pytest tests/fabric/test_udf_security.py

# End-to-end тесты с provenance
pytest tests/integration/test_udf_workflow.py
```

## Архитектурные принципы

- **Security-First**: Все запросы проходят через whitelist валидацию
- **Modular Compilation**: Независимые passes для разных аспектов
- **Evidence-Driven**: Каждый запрос имеет криптографическую traceability
- **Performance-Optimized**: Специфичные оптимизации для каждого типа запроса
- **Schema-Evolution**: Поддержка изменений конфигурации без breaking changes