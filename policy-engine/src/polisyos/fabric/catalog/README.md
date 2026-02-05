# Data Contract Catalog

**Catalog** — это metric-level система контрактов для обеспечения type safety и предотвращения hallucination имен метрик в AI-driven симуляциях экономической политики.

## Архитектурная роль

Catalog решает критическую проблему **metric identity** в контексте AI-driven симуляций:

### Проблематика
- **Scientist Agent** может "галлюцинировать" несуществующие имена метрик
- Отсутствие type safety на уровне отдельных метрик (только датасеты)
- Невозможность безопасной эволюции схем данных
- Отсутствие provenance tracking для отдельных метрик

### Решение
```
Raw Query → Fuzzy Search → Disambiguation → Validated Binding → Type-Safe Usage
     ↓             ↓              ↓              ↓              ↓
  "GDP"    →  "us.macro.gdp_nominal"  →  MetricBinding  →  UDF Query
```

### Положение в архитектуре
Catalog находится на границе между **IR** (контракты) и **Runtime** (Fabric):

```
Scientist (AI) ←→ Catalog ←→ Fabric (Data)
     ↑               ↑              ↑
   Queries      Bindings       Storage
```

## Принципы дизайна

### 1. Source of Truth (Единственный источник истины)
- **DataContract** — каноническое определение метрики
- Только валидированные контракты могут использоваться в симуляциях
- JSON-based контракты хранятся в `data/curated/data_contracts.json`

### 2. Hash-Locked Bindings (Защищенные привязки)
- **MetricBinding** — immutable ссылка на контракт с hash verification
- Предотвращает silent contract drift
- Scientist получает binding только после валидации

### 3. Human-in-the-Loop Disambiguation
- Fuzzy search с confidence scoring
- Disambiguation UI при низкой уверенности
- Предотвращает silent incorrect assumptions

### 4. Privacy-by-Design
- 5-уровневая PII классификация (none/low/medium/high/critical)
- Access tiers для Scientist queries
- Audit logging для sensitive данных

## Структура модуля

```
catalog/
├── __init__.py          # Экспорт всех компонентов
├── contract.py          # DataContract модели и коллекции
├── binding.py           # MetricBinding - hash-locked ссылки
├── registry.py          # DataContractRegistry - управление контрактами
├── search.py            # MetricSearcher - поиск с disambiguation
└── validate.py          # Валидация контрактов из JSON
```

## Ключевые компоненты

### 1. Data Contract (`contract.py`)

Каноническая модель метрики с полным метаданными:

#### DataContract Model
```python
class DataContract(BaseModel):
    # Identity
    metric_id: str           # us.macro.gdp_nominal
    display_name: str        # "Nominal GDP"
    description: str         # Подробное описание

    # Type information
    dtype: DataType          # int/float/string/boolean/datetime/array/json
    unit: str | None         # "USD", "percent", etc.
    granularity: Granularity # tick/daily/monthly/quarterly/yearly/agent/aggregate

    # Structure
    dimensions: List[str]    # ["region", "sector"] для slicing
    valid_range: tuple[float, float] | None  # Валидационные границы

    # Provenance
    source_system: str       # "bea.gov"
    source_table: str        # "gdp_quarterly"
    source_column: str       # "nominal_gdp"
    jurisdiction: str        # "US"

    # Privacy
    pii_tier: PIITier        # none/low/medium/high/critical

    # Search
    aliases: List[str]       # ["GDP", "nominal gdp"]
    tags: List[str]          # ["macro", "economic"]

    # Lifecycle
    deprecated: bool         # Устаревшая метрика?
    superseded_by: str       # Замена, если deprecated
```

#### Data Types & Granularities
```python
class DataType(str, Enum):
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    ARRAY = "array"
    JSON = "json"

class Granularity(str, Enum):
    TICK = "tick"
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    AGENT = "agent-level"
    AGGREGATE = "aggregate"
```

#### Privacy Tiers
```python
class PIITier(str, Enum):
    NONE = "none"           # Публичные данные
    LOW = "low"             # Агрегируемые, без индивидуального exposure
    MEDIUM = "medium"       # Требует k-anonymization (k>=5)
    HIGH = "high"           # Ограниченный доступ, требуется аудит
    CRITICAL = "critical"   # PII/PHI, требуется explicit consent
```

### 2. Metric Binding (`binding.py`)

Hash-locked immutable ссылка для Scientist агента:

```python
@dataclass(frozen=True, slots=True)
class MetricBinding:
    metric_id: str
    unit: str | None
    dtype: str
    dimensions: tuple[str, ...]
    pii_tier: str
    contract_hash: str       # SHA-256[16] хэш полного контракта

    @classmethod
    def from_contract(cls, contract: DataContract) -> MetricBinding:
        # Создание binding с hash verification
        contract_json = contract.model_dump_json()
        contract_hash = hashlib.sha256(contract_json.encode()).hexdigest()[:16]
        return cls(...)
```

**Безопасность:**
- **Frozen dataclass**: Immutable после создания
- **Contract hash**: Обнаружение изменений в контракте
- **Type locking**: dtype/unit фиксированы в binding

### 3. Contract Registry (`registry.py`)

Управление контрактами с кэшированием и валидацией:

```python
class DataContractRegistry:
    def __init__(self, curated_dir: Path, filename: str = "data_contracts.json")

    def get(self, metric_id: str) -> DataContract
    def get_binding(self, metric_id: str) -> MetricBinding
    def validate_binding(self, binding: MetricBinding) -> DataContract

    def list_all(self) -> list[str]
    def __contains__(self, metric_id: str) -> bool
```

**Особенности:**
- **Lazy loading**: Контракты загружаются по требованию
- **Binding caching**: MetricBinding кэшируются для производительности
- **Hash validation**: Проверка соответствия binding текущему контракту

### 4. Metric Search (`search.py`)

Fuzzy поиск с human-in-the-loop disambiguation:

```python
class SearchResponse:
    results: List[SearchResult]    # Отсортированы по confidence (убывание)
    needs_disambiguation: bool     # Требуется ли уточнение?
    query: str                     # Исходный запрос
    total_candidates: int          # Всего кандидатов

class MetricSearcher:
    def search(self, query: str) -> SearchResponse
    def resolve(self, query: str) -> MetricBinding  # Raises on ambiguity
```

#### Search Algorithm
1. **Exact match**: Прямое совпадение с alias
2. **Fuzzy matching**: Jaccard similarity на токенах
3. **Confidence scoring**: Комбинированный score (similarity + substring/prefix boosts)
4. **Disambiguation logic**: Human clarification при низкой уверенности

#### Confidence Thresholds
- **High confidence (>0.7)**: Автоматическое разрешение
- **Medium confidence (0.5-0.7)**: Предложение опций для выбора
- **Low confidence (<0.5)**: Требование переформулировки запроса

### 5. Validation (`validate.py`)

Валидация контрактов из JSON файлов:

```python
def load_contract_collection(path: Path) -> DataContractCollection:
    """Загрузка и валидация DataContractCollection из JSON."""
```

**Валидационные правила:**
- Pydantic schema validation
- Unique metric_id constraints
- Valid regex patterns для metric_id
- Range validation для valid_range

## Интеграция с системой

### Workflow с Scientist Agent

```
1. User Query → 2. Fuzzy Search → 3. Disambiguation → 4. Validated Binding → 5. UDF Query

   "GDP rate"     SearchResponse     Human Selection    MetricBinding        DataViewRequest
   (ambiguous)    [results...]       "us.macro.gdp"     (hash-locked)         (type-safe)
```

### Интеграция с UDF

```python
# scientist/query_builder.py
from polisyos.fabric.catalog import DataContractRegistry, MetricSearcher

class QueryBuilder:
    def __init__(self, registry: DataContractRegistry):
        self.searcher = MetricSearcher(list(registry))
        self.registry = registry

    def build_query(self, natural_query: str) -> DataViewRequest:
        # 1. Разрешение natural language в binding
        binding = self.searcher.resolve(natural_query)

        # 2. Валидация binding (hash check)
        contract = self.registry.validate_binding(binding)

        # 3. Построение type-safe UDF запроса
        return DataViewRequest(
            dataset_name=contract.source_table,
            metrics=[binding.metric_id],
            access_tier=self._map_pii_to_access(contract.pii_tier)
        )
```

### Интеграция с Claims Processing

```python
# claims/processing.py - контракты для извлеченных claims
from polisyos.fabric.catalog import DataContractRegistry

def validate_claim_contracts(claims: list[ClaimCandidate], registry: DataContractRegistry):
    """Валидация извлеченных claims против контрактов."""
    for claim in claims:
        if claim.predicate_id in registry:
            contract = registry.get(claim.predicate_id)
            # Валидация типа данных, единиц измерения, etc.
            validate_claim_against_contract(claim, contract)
```

### Интеграция с Document Processing

```python
# docs/processing.py - метаданные документов в catalog
from polisyos.fabric.catalog.contract import DataContract

# Контракты для метаданных документов
doc_contract = DataContract(
    metric_id="doc.metadata.page_count",
    display_name="Document Page Count",
    description="Number of pages in processed document",
    dtype=DataType.INT,
    source_system="document_processor",
    pii_tier=PIITier.NONE
)
```

### Интеграция с Fabric Ingestion

```python
# fabric/ingestion.py - автоматическая генерация контрактов
from polisyos.fabric.catalog.contract import DataContract, DataContractCollection

def scan_and_generate_contracts(raw_dir: Path, curated_dir: Path) -> DataContractCollection:
    """Сканирование датасетов и генерация draft контрактов."""
    # Анализ CSV схем, типов данных, диапазонов
    # Генерация DataContract для каждой колонки
    # Сохранение в data_contracts.json
```

## API Usage Examples

### Базовое использование

```python
from polisyos.fabric.catalog import DataContractRegistry, MetricSearcher

# Инициализация
registry = DataContractRegistry(Path("data/curated"))
searcher = MetricSearcher(list(registry))

# Поиск метрики
response = searcher.search("unemployment")
if response.needs_disambiguation:
    # Показать пользователю опции
    for result in response.results[:3]:
        print(f"{result.contract.display_name}: {result.confidence:.0%}")
else:
    # Использовать лучший результат
    binding = response.best_match.binding
    print(f"Resolved to: {binding.metric_id}")

# Direct resolution (для confident queries)
binding = searcher.resolve("us.macro.unemployment_rate")
```

### Работа с bindings

```python
# Получение binding из registry
binding = registry.get_binding("us.macro.gdp_nominal")

# Проверка hash integrity
contract = registry.validate_binding(binding)

# Использование в UDF запросе
request = DataViewRequest(
    view_type=DataViewType.PANEL,
    dataset_name="macro",
    metrics=[binding.metric_id],
    access_tier=AccessTier.PUBLIC if binding.pii_tier == "none" else AccessTier.INTERNAL
)
```

### Создание контрактов

```python
from polisyos.fabric.catalog.contract import DataContract, DataType, Granularity, PIITier

contract = DataContract(
    metric_id="us.agent.income_median",
    display_name="Median Household Income",
    description="Median income for households in USD",
    dtype=DataType.FLOAT,
    unit="USD",
    granularity=Granularity.YEARLY,
    dimensions=["region", "income_quintile"],
    valid_range=(0, None),
    source_system="census.gov",
    source_table="acs_5year",
    source_column="median_income",
    jurisdiction="US",
    pii_tier=PIITier.LOW,
    aliases=["median income", "household income", "income median"],
    tags=["demographics", "income", "household"]
)
```

## Производительность и масштабируемость

### Оптимизации

**Registry:**
- **Lazy loading**: Контракты загружаются по требованию
- **Binding caching**: MetricBinding кэшируются для повторных запросов
- **Hash memoization**: Contract hash вычисляется один раз

**Search:**
- **Alias indexing**: Reverse index для O(1) exact matches
- **Token-based similarity**: Эффективный fuzzy matching
- **Early termination**: Ограничение результатов для responsiveness

### Масштабирование

**Текущее состояние:**
- Поддержка 1000+ метрик без degradation
- Sub-second search response times
- Memory-efficient для больших коллекций

**Будущие оптимизации:**
- Embedding-based semantic search
- Distributed contract storage
- Real-time contract updates

## Безопасность и compliance

### PII Classification Framework

| Tier | Description | Access Control | Aggregation Required |
|------|-------------|----------------|---------------------|
| none | Public data | No restrictions | No |
| low | Aggregatable | Basic auth | Group by dimensions |
| medium | Sensitive | k-anonymization | k>=5 |
| high | Restricted | Audit logging | Explicit approval |
| critical | PII/PHI | Consent required | Individual approval |

### Audit Trail

- Все binding resolutions логируются
- Contract changes tracked с hash verification
- Access patterns monitored для compliance
- Provenance chain от raw data до Scientist usage

## Тестирование

### Unit Tests
```bash
# Тесты контрактов
pytest tests/fabric/test_catalog_contracts.py

# Тесты поиска
pytest tests/fabric/test_catalog_search.py

# Тесты registry
pytest tests/fabric/test_catalog_registry.py
```

### Integration Tests
```bash
# Полный workflow с Scientist
pytest tests/integration/test_catalog_scientist_integration.py

# UDF integration
pytest tests/integration/test_catalog_udf_integration.py
```

### Contract Validation
```bash
# Валидация data_contracts.json
python tools/validate_contracts.py data/curated/data_contracts.json

# Генерация draft контрактов из датасетов
python tools/scan_fabric.py --generate-contracts
```

## Заключение

**Data Contract Catalog** обеспечивает type safety для всей Fabric экосистемы:

- **Type Safety**: Предотвращение hallucination через validated bindings
- **Schema Evolution**: Безопасная миграция через contract versioning
- **Privacy Compliance**: Multi-tier PII classification и access control
- **Human Oversight**: Disambiguation UI для ambiguous queries
- **Auditability**: Complete provenance tracking от контракта до использования
- **Claims Integration**: Type-safe извлечение фактов из документов
- **Document Metadata**: Структурированные контракты для document attributes
- **World Model Schema**: Schema-compliant факты мира

Catalog является фундаментом для trustworthy AI-driven симуляций экономической политики, обеспечивая semantic consistency и data integrity на всех уровнях системы.