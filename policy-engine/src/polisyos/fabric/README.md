# Polisyos Fabric: Unified Data Fabric

**Fabric** — это унифицированная система обработки и хранения данных для AI-driven симуляции экономической политики. Модуль обеспечивает полный жизненный цикл данных: от сырых CSV файлов до высокопроизводительных запросов через Unified Data Fabric (UDF), с автоматической оценкой качества данных, криптографически verifiable provenance tracking и support для внешних data connectors.

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
2. **Data Connectors System**: Protocol-based подключение к внешним источникам данных с federation, caching, quality assessment и resilience (Phase 2.1-2.5)
3. **Connector Federation**: Cross-connector composition и evidence aggregation для комплексных data pipelines
4. **Connector Caching**: CAS-based caching с invalidation, prefetching и intelligent proxy layer
5. **Data Quality Management**: Автоматическая оценка качества (completeness, consistency, freshness), reconciliation, dataset manifests, quality gates
6. **Data Transformation Pipeline**: ETL трансформации с aggregation, filtering, harmonization, imputation и validation
7. **Contract Evolution**: Schema evolution tracking, migration utilities и contract registry для API stability
8. **Type System**: Безопасная type coercion, dimensional data handling и unit conversion
9. **Data Contract Catalog**: Metric-level type safety с hash-locked bindings для Scientist agent
10. **Claims Processing System**: Извлечение, нормализация и разрешение конфликтов claims из документов
11. **Document Processing Pipeline**: Обработка различных форматов документов (PDF, HTML, plain text) с chunking и структуризацией
12. **World Model Materialization**: Восстановление и материализация модели мира из Fact Log с поддержкой множественных представлений
13. **Fact Log System**: Immutable хранение фактов в каноническом формате для audit trail
14. **Provenance Tracking**: W3C PROV-O compliant lineage tracking для полного audit trail
15. **Multi-Backend Storage**: Реляционное (DuckDB) + графовое (Kùzu) хранение данных
16. **Data Fitness Assessment**: Многоуровневая оценка пригодности данных для симуляции с threshold-based validation
17. **Entity Resolution**: Нормализация и дедупликация идентификаторов агентов
18. **Evidence System**: Криптографически verifiable доказательства происхождения данных
19. **Unified Data Fabric**: Безопасный компилируемый слой запросов с whitelist и privacy controls
20. **Materialization Engine**: Восстановление реляционных представлений из immutable фактов
21. **Quality Gate Validation**: Интеграция с governance system для блокировки низкокачественных данных

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
├── __init__.py              # Экспорт основного API (run_ingestion, catalog, connectors, claims)
├── _connector_bridge.py     # Мост для интеграции коннекторов с другими системами
├── claims/                  # Система обработки и верификации claims
│   ├── __init__.py          # Экспорт claims API
│   ├── canonicalize.py      # Канонизация и нормализация claims
│   ├── citations.py         # Управление цитатами и ссылками
│   ├── conflicts/           # Разрешение конфликтов claims
│   │   ├── __init__.py
│   │   ├── detect.py        # Обнаружение конфликтов
│   │   ├── key.py           # Ключи для группировки конфликтов
│   │   ├── policies.py      # Политики разрешения конфликтов
│   │   ├── resolve.py       # Логика разрешения
│   │   └── score_claims.py  # Оценка claims для разрешения
│   │   └── score_docs.py    # Оценка документов
│   │   └── types.py         # Типы для конфликтов
│   ├── errors.py            # Специфичные ошибки claims
│   ├── extraction.py        # Извлечение claims из текста
│   ├── extractor_registry.py # Реестр экстракторов claims
│   ├── normalize.py         # Нормализация claims
│   ├── persist.py           # Сохранение claims
│   └── types.py             # Основные типы данных claims
│   └── backends/            # Backend реализации экстракторов
│       ├── __init__.py
│       ├── explicit_lines_v1.py # Явные линии claims
│       ├── lex_norm_regex_v1.py # Лексическая нормализация
│       └── regex_numeric_v1.py  # Регулярные выражения для чисел
├── connectors/              # Phase 2.1+: Расширенная система коннекторов
│   ├── __init__.py          # Экспорт connector API и типов
│   ├── base.py              # SourceConnector Protocol, FetchRequest/Result
│   ├── capabilities.py      # Capability validation и decorators
│   ├── types.py             # Error hierarchy и supporting types
│   ├── discovery.py         # Plugin discovery via entry points
│   ├── pool.py              # ConnectionPool + lifecycle management
│   ├── registry.py          # ConnectorRegistry singleton для управления коннекторами
│   ├── cache/               # Система кэширования запросов
│   │   ├── __init__.py
│   │   ├── store.py         # CAS-based кэширование
│   │   ├── invalidation.py  # Инвалидация кэша
│   │   ├── policy.py        # Политики кэширования
│   │   ├── prefetch.py      # Предварительная загрузка
│   │   └── proxy.py         # Прокси для кэширования
│   ├── contracts/           # Контракты для коннекторов
│   │   ├── __init__.py
│   │   ├── evolution.py     # Эволюция контрактов
│   │   ├── inference.py     # Вывод схем
│   │   ├── registry.py      # Реестр контрактов
│   │   └── schema.py        # Схемы данных
│   ├── federation/          # Федеративные запросы
│   │   ├── __init__.py
│   │   ├── composer.py      # Композиция запросов
│   │   ├── evidence_aggregation.py  # Агрегация доказательств
│   │   ├── planner.py       # Планирование запросов
│   │   ├── ranker.py        # Ранжирование результатов
│   │   └── resolver.py      # Разрешение зависимостей
│   │   └── types.py         # Типы для федерации
│   ├── quality/             # Качество данных коннекторов
│   │   ├── __init__.py
│   │   ├── completeness.py  # Проверка полноты
│   │   ├── consistency.py   # Проверка консистентности
│   │   ├── freshness.py     # Проверка актуальности
│   │   ├── report.py        # Отчеты о качестве
│   │   └── validator.py     # Валидация качества
│   ├── reference/           # Ссылочные реализации
│   │   ├── __init__.py
│   │   ├── rest_json.py     # REST JSON коннектор
│   │   ├── sdmx.py          # SDMX коннектор
│   │   └── static_csv.py    # Статический CSV коннектор
│   ├── resilience/          # Устойчивость коннекторов
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py  # Circuit breaker pattern
│   │   ├── fallback.py      # Fallback механизмы
│   │   ├── rate_limiter.py  # Ограничение скорости
│   │   └── retry.py         # Повторные попытки
│   ├── testing/             # Тестирование коннекторов
│   │   ├── __init__.py
│   │   ├── contracts.py     # Тестовые контракты
│   │   ├── fixtures.py      # Тестовые данные
│   │   ├── harness.py       # Тестовый harness
│   │   └── simulator.py     # Симулятор коннекторов
│   └── transform/           # Трансформации данных
│       ├── __init__.py
│       ├── aggregator.py    # Агрегация данных
│       ├── filter.py        # Фильтрация
│       ├── harmonizer.py    # Гармонизация схем
│       ├── imputer.py       # Заполнение пропусков
│       ├── normalizer.py    # Нормализация
│       ├── pipeline.py      # Трансформационный pipeline
│       └── validator.py     # Валидация трансформаций
├── catalog/                 # Metric-level data contract catalog
│   ├── __init__.py          # Экспорт всех catalog компонентов
│   ├── binding.py           # MetricBinding - hash-locked ссылки на метрики
│   ├── contract.py          # DataContract модели и коллекции
│   ├── registry.py          # DataContractRegistry - реестр контрактов
│   ├── search.py            # MetricSearcher - fuzzy search с disambiguation
│   └── validate.py          # Валидация контрактов из JSON
├── docs/                    # Система обработки документов
│   ├── __init__.py          # Экспорт docs API
│   ├── backends/            # Backend реализации для разных форматов
│   │   ├── __init__.py
│   │   ├── pdf.py           # Обработка PDF документов
│   │   └── text_html.py     # Обработка HTML документов
│   │   └── text_plain.py    # Обработка plain text
│   ├── chunking.py          # Разбиение документов на chunks
│   ├── errors.py            # Специфичные ошибки обработки документов
│   ├── ingestion.py         # Загрузка документов в систему
│   ├── normalize.py         # Нормализация текстового содержимого
│   ├── structure.py         # Анализ структуры документов
│   └── types.py             # Типы данных для документов
├── provenance/              # W3C PROV-O provenance tracking система
│   ├── __init__.py          # Экспорт provenance компонентов
│   ├── core.py              # ProvenanceCoreGraph, Entity/Activity/Agent модели
│   └── export_provo.py      # Экспорт в PROV-O JSON-LD/N-Quads
├── world/                   # Модель мира и материализация данных
│   ├── __init__.py          # Экспорт world API
│   ├── ddl/                 # DDL скрипты для инициализации хранилищ
│   │   ├── duckdb_world.sql # DDL для DuckDB
│   │   └── kuzu_world.cypher # DDL для Kùzu
│   ├── materialize/         # Материализация реляционных представлений
│   │   ├── __init__.py
│   │   ├── duckdb.py        # Материализация в DuckDB
│   │   ├── errors.py        # Специфичные ошибки материализации
│   │   ├── kuzu.py          # Материализация в Kùzu
│   │   ├── projections.py   # Проекции данных
│   │   ├── rules.py         # Правила материализации
│   │   ├── sql.py           # Генерация SQL запросов
│   │   └── staging.py       # Staging area для материализации
│   └── store/               # Хранение и управление сегментами мира
│       ├── __init__.py
│       ├── emit.py          # Эмиссия данных в хранилища
│       ├── errors.py        # Специфичные ошибки хранения
│       ├── ids.py           # Управление идентификаторами
│       ├── persist.py       # Персистентность данных
│       ├── provenance.py    # Provenance для сегментов мира
│       ├── segments.py      # Управление сегментами
│       └── validate.py      # Валидация данных мира
├── ingestion.py             # Главный ETL pipeline с Fact Log и evidence
├── schema.py                # Pydantic модели данных (AgentRow, InteractionRow, MacroRow)
├── manifest.py              # Метаданные и качество данных (DatasetManifest, QualityMetrics)
├── registry.py              # Управление манифестами датасетов (ManifestRegistry)
├── config.py                # Правила нормализации и reconciliation
├── evidence.py              # Система доказательств (build_evidence_bundle, persist_evidence_bundle)
├── materializer.py          # Полная материализация из Fact Log (ensure_materialized, materialize_duckdb_from_fact_log)
├── segment_manifest.py      # Управление сегментами Fact Log (write_segment_manifest)
├── fact_writer.py           # Запись фактов в каноническом формате (build_fact, facts_from_dataframe)
├── trust.py                 # Политики доверия (two_pass_compare, persist_uncertainty_bounds, UncertaintyBounds)
├── quality.py               # Система оценки качества данных (QualityIndicators, QualityLevel, QualityThresholds)
├── fitness_report.py        # Отчеты о пригодности данных (DataFitnessReport, MetricFitness)
├── io/                      # Интерфейсы хранения данных
│   ├── __init__.py          # Экспорт адаптеров хранения
│   ├── db.py                # DuckDB адаптер (SimulationDB)
│   └── graph_store.py       # Kùzu графовый адаптер (GraphStore)
├── world_query.py           # Запросы к модели мира
├── demo_csv_ingestion.py    # Демо скрипт для ingestion CSV данных
├── connectors_ingestion.py  # Интеграция с коннекторами
├── fact_writer.py           # Запись фактов в каноническом формате
└── udf/                     # Unified Data Fabric - безопасный слой запросов
    ├── __init__.py          # Экспорт UDF компонентов
    ├── engine.py            # UDF движок с CAS интеграцией (UDFEngine)
    ├── compiler.py          # Безопасный компилятор SQL/Cypher (ViewCompiler)
    ├── plan.py              # Планы выполнения запросов (DataViewPlan)
    ├── config.py            # UDF конфигурация и whitelist (UdfSchema, load_udf_schema)
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

### 1. Data Connectors System (`connectors/`)

**Phase 2.1+: Расширенная система коннекторов** - унифицированный интерфейс для подключения к внешним источникам данных с capability-based security, protocol compliance validation, кэшированием, федерацией и качеством данных.

#### SourceConnector Protocol
```python
class MyConnector(SourceConnector[list[dict]]):
    connector_id: ClassVar[str] = "myorg.mydata"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH | ConnectorCapability.CATALOG_BROWSE
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle: ...
    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[list[dict]]: ...
```

#### Расширенные компоненты:
- **Cache System (`cache/`)**: CAS-based кэширование с политиками инвалидации и prefetch
- **Contracts (`contracts/`)**: Эволюция контрактов и вывод схем данных
- **Federation (`federation/`)**: Композиция запросов к множественным источникам
- **Quality (`quality/`)**: Оценка полноты, консистентности и актуальности данных
- **Resilience (`resilience/`)**: Circuit breaker, fallback и rate limiting
- **Testing (`testing/`)**: Тестовые harness и симуляторы коннекторов
- **Transform (`transform/`)**: Pipeline трансформаций (агрегация, фильтрация, гармонизация)

#### Capability System
Поддержка 15+ capabilities: FULL_FETCH, STREAMING, DATE_RANGE_FILTER, SCHEMA_INTROSPECTION, FRESHNESS_CHECK, CUSTOM_QUERY, etc. С runtime validation через `@requires_capability` decorator.

#### Registry & Pool Management
```python
registry = ConnectorRegistry.get_instance()
registry.register(MyConnector)
handle = await registry.get_connection("myorg.mydata")
```

**Ключевые возможности:**
- **Protocol Compliance**: Runtime валидация через `validate_protocol_compliance()`
- **Capability-based Security**: Проверка доступных операций на этапе исполнения
- **Deterministic Caching**: Стабильные ключи для Content Addressable Storage
- **Federated Queries**: Композиция данных из множественных источников
- **Quality Assurance**: Автоматическая оценка качества получаемых данных
- **Resilience Patterns**: Circuit breaker, retry и fallback механизмы
- **Connection Pooling**: Управление жизненным циклом соединений
- **Error Hierarchy**: Специфичные ошибки (RateLimitError, SchemaError, etc.)
- **Async Support**: Асинхронные операции для высокопроизводительного доступа

### 2. Data Contract Catalog (`catalog/`)

Metric-level система контрактов для обеспечения type safety и предотвращения hallucination имен метрик:

#### Data Contracts
```python
class DataContract(BaseModel):
    """Канонический контракт для метрики."""
    metric_id: str           # Уникальный ID (us.macro.gdp_nominal)
    display_name: str        # Человекочитаемое имя
    description: str         # Подробное описание
    dtype: DataType          # Тип данных (int, float, string, etc.)
    unit: str | None         # Единицы измерения
    granularity: Granularity # Временная/сущностная гранулярность
    dimensions: List[str]    # Измерения для slicing
    pii_tier: PIITier        # Уровень приватности
    source_system: str       # Система-источник
    # ... provenance, aliases, lifecycle fields
```

#### Metric Bindings
```python
@dataclass(frozen=True)
class MetricBinding:
    """Hash-locked ссылка на метрику для Scientist агента."""
    metric_id: str
    unit: str | None
    dtype: str
    dimensions: tuple[str, ...]
    pii_tier: str
    contract_hash: str       # SHA-256 hash контракта
```

**Ключевые возможности:**
- **Type Safety**: Предотвращение hallucination имен метрик через валидированные контракты
- **Hash Locking**: Tamper-evident bindings с обнаружением изменений контрактов
- **Search & Disambiguation**: Fuzzy поиск с human-in-the-loop disambiguation при низкой уверенности
- **PII Classification**: 5-уровневая классификация приватности (none/low/medium/high/critical)
- **Schema Evolution**: Lifecycle management с deprecation и supersession

#### Registry & Search
```python
class DataContractRegistry:
    """Реестр контрактов с кэшированием и валидацией."""
    def get(self, metric_id: str) -> DataContract
    def get_binding(self, metric_id: str) -> MetricBinding
    def validate_binding(self, binding: MetricBinding) -> DataContract

class MetricSearcher:
    """Поиск метрик с disambiguation."""
    def search(self, query: str) -> SearchResponse  # Fuzzy search
    def resolve(self, query: str) -> MetricBinding  # Exact resolution
```

**Интеграция с Scientist:**
- Scientist получает MetricBinding только после валидации контракта
- Hash checking предотвращает silent contract drift
- Disambiguation UI для ambiguous queries
- Integration с UDF для type-safe queries

### 3. Claims Processing System (`claims/`)

Комплексная система для извлечения, нормализации и разрешения конфликтов claims из документов:

#### Архитектура Claims Processing
- **Backend Registry**: Плагинируемая система экстракторов (explicit lines, regex patterns, lexical normalization)
- **Canonicalization**: Приведение claims к каноническому формату с нормализацией
- **Conflict Detection**: Обнаружение противоречий между claims с confidence scoring
- **Conflict Resolution**: Политики разрешения конфликтов (majority vote, source priority, temporal precedence)
- **Citation Management**: Связывание claims с источниками и контекстом

#### Ключевые возможности
- **Multi-format Support**: Поддержка различных форматов claims (explicit, implicit, probabilistic)
- **Confidence Scoring**: Оценка уверенности для каждого claim
- **Conflict Resolution Policies**: Настраиваемые стратегии разрешения противоречий
- **Citation Tracking**: Полная traceability к исходным документам
- **Incremental Processing**: Постепенная обработка больших коллекций документов

#### Integration с другими компонентами
```python
from polisyos.fabric.claims import ClaimsProcessor, ConflictResolver

# Обработка документа и извлечение claims
processor = ClaimsProcessor()
claims = processor.extract_from_document(document)

# Разрешение конфликтов
resolver = ConflictResolver()
resolved_claims = resolver.resolve(claims, policy="majority_vote")
```

### 4. Document Processing System (`docs/`)

Система обработки документов различных форматов для извлечения структурированной информации:

#### Поддерживаемые форматы
- **PDF Documents**: Текстовое извлечение с layout preservation
- **HTML Documents**: Парсинг структуры и контента
- **Plain Text**: Обработка неструктурированного текста

#### Pipeline обработки
1. **Ingestion**: Загрузка документов с метаданными
2. **Normalization**: Приведение к единому формату и кодировке
3. **Chunking**: Разбиение на семантически связанные фрагменты
4. **Structure Analysis**: Извлечение структуры документа (заголовки, разделы, таблицы)
5. **Content Extraction**: Извлечение ключевой информации и entities

#### Ключевые возможности
- **Adaptive Chunking**: Интеллектуальное разбиение документов на chunks
- **Metadata Preservation**: Сохранение структуры и форматирования
- **Format Detection**: Автоматическое определение типа документа
- **Quality Assessment**: Оценка качества извлеченного контента
- **Incremental Processing**: Поддержка больших документов через streaming

### 5. World Model System (`world/`)

Система материализации и управления моделью мира из Fact Log с поддержкой множественных представлений:

#### Архитектура World Model
- **DDL Management**: Автоматическая инициализация схем хранилищ (DuckDB, Kùzu)
- **Materialization Engine**: Инкрементальная материализация реляционных представлений
- **Projections**: Множественные проекции данных для разных use cases
- **Staging Area**: Промежуточное хранение для сложных трансформаций

#### Компоненты материализации
- **DuckDB Materializer**: Реляционная материализация для аналитических запросов
- **Kùzu Materializer**: Графовая материализация для сетевого анализа
- **Projection Rules**: Правила трансформации фактов в реляционные таблицы
- **Validation**: Проверка целостности материализованных данных

#### Ключевые возможности
- **Incremental Updates**: Материализация только новых фактов
- **Multi-view Support**: Различные представления данных для разных потребителей
- **Schema Evolution**: Автоматическая адаптация к изменениям в Fact Log
- **Performance Optimization**: Оптимизированные индексы и структуры хранения
- **Data Validation**: Проверка консистентности материализованных данных

#### Integration с Fact Log
```python
from polisyos.fabric.world.materialize import WorldMaterializer

# Материализация модели мира из Fact Log
materializer = WorldMaterializer()
materializer.materialize_from_fact_log(
    fact_dir=Path("data/facts"),
    target_store="duckdb",
    incremental=True
)
```

### 6. Provenance System (`provenance/`)

**W3C PROV-O compliant система отслеживания происхождения данных** для полного audit trail от сырых данных до результатов симуляций.

#### PROV-O Data Model
Полная реализация W3C PROV-O спецификации:
- **Entities**: Dataset, Metric, Snapshot, Fact Segment, Query Result
- **Activities**: Ingest, Query, ETL, Validation, Simulation Step, Aggregation
- **Agents**: System, User, Model, Scheduler

#### ProvenanceCoreGraph
Легковесная внутренняя модель для быстрого анализа:
```python
graph = ProvenanceCoreGraph(graph_id="query_run_001")
graph.add_entity(ProvenanceEntity(entity_id="dataset_001", entity_type=EntityType.DATASET, ...))
graph.add_derivation("query_result", "dataset_001")  # PROV-O wasDerivedFrom
```

#### Экспорт в стандарты
- **JSON-LD**: Для семантического веба и linked data
- **N-Quads**: Для загрузки в RDF triple stores

**Ключевые возможности:**
- **Deterministic IDs**: SHA256-based стабильные идентификаторы для CAS
- **Complete Lineage**: Отслеживание полного пути трансформации данных
- **Audit Trail**: Криптографически verifiable provenance chain
- **Multi-format Export**: JSON-LD и N-Quads для разных потребителей
- **Integration с FabricResult**: Каждый результат запроса включает provenance

### 7. Data Ingestion Pipeline (`ingestion.py`)

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

### 8. Схемы данных (`schema.py`)

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

### 9. Data Quality & Manifests (`manifest.py`, `registry.py`)

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

### 10. Entity Resolution (`ingestion.py`, `config.py`)

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

### 11. Reconciliation (`ingestion.py`, `config.py`)

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
- В warn-only режиме (`reconciliation_strict=False`) несоответствия логируются и не блокируют ingestion

### 12. Storage Adapters (`io/`)

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

### 13. Unified Data Fabric (`udf/`)

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
        fact_dir: Path | str | None = None,
        schema: Optional[UdfSchema] = None,
        cas_root: Path | str = Path(".polisyos"),
    ):
        self.db = db
        self.graph = graph if graph else GraphStore()
        self.fact_dir = Path(fact_dir) if fact_dir else self._resolve_fact_dir(curated_dir)
        self.manifests = ManifestRegistry(curated_dir)
        self.schema = schema or load_udf_schema(curated_dir / "udf_schema.json")
        self.compiler = ViewCompiler(self.manifests, self.schema)
        self.cas = FileSystemCAS(Path(cas_root))

    def compile(self, request: DataViewRequest) -> DataViewPlan
    def query(self, request: DataViewRequest) -> pd.DataFrame
    def query_arrow(self, request: DataViewRequest) -> pa.Table
    def query_result(self, request: DataViewRequest) -> FabricResult
    def _execute(self, plan: DataViewPlan, *, as_arrow: bool = False)
```

**Ключевые возможности:**
- **Multi-Backend Execution**: Автоматическое определение типа запроса (реляционный/графовый)
- **FabricResult**: Структурированный результат с полным provenance tracking
- **Arrow Support**: Высокопроизводительная работа с columnar данными через PyArrow
- **CAS Integration**: Автоматическое сохранение запросов, планов и результатов в Content Addressable Storage
- **Evidence Bundles**: Криптографически verifiable доказательства для каждого запроса
- **Lazy Materialization**: Автоматическая материализация данных из Fact Log при необходимости

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

### 14. Data Quality Assessment System (`quality.py`, `fitness_report.py`)

Комплексная система оценки качества данных для обеспечения пригодности данных к симуляциям экономической политики.

#### Quality Indicators (`QualityIndicators`)
Объективные метрики качества данных, вычисляемые из датасетов:

```python
@dataclass
class QualityIndicators:
    """Качественные метрики датасета или метрики."""

    metric_id: str
    missingness: float          # Доля пропущенных значений (0.0-1.0)
    staleness_days: int         # Дней с момента последнего обновления
    coverage: float             # Покрытие ожидаемых записей (0.0-1.0)
    row_count: int              # Общее количество строк
    schema_drift: bool = False  # Изменение схемы с baseline
    outlier_ratio: float = 0.0  # Доля выбросов (IQR-based)
    computed_at: datetime       # Время вычисления
    computation_method: str     # Метод вычисления ("pandas"/"duckdb")
```

**Ключевые метрики:**
- **Missingness**: Доля null значений - основной индикатор полноты данных
- **Staleness**: Актуальность данных - время с последнего обновления
- **Coverage**: Географическое/временное покрытие относительно ожидаемого
- **Schema Drift**: Изменения структуры данных со времени baseline
- **Outlier Ratio**: Доля статистических выбросов для числовых колонок

#### Quality Levels (`QualityLevel`)
Упорядоченная классификация качества с семантикой для принятия решений:

```python
@total_ordering
class QualityLevel(Enum):
    EXCELLENT = "excellent"    # Отличное качество - полное доверие
    GOOD = "good"             # Хорошее качество - высокая уверенность
    ACCEPTABLE = "acceptable" # Приемлемое качество - допустимо для MVP
    POOR = "poor"             # Плохое качество - требует внимания
    UNUSABLE = "unusable"     # Непригодное качество - блокирует использование
```

**Правила переходов:**
- EXCELLENT: missingness ≤ 1%, staleness ≤ 7 дней, coverage ≥ 99%
- GOOD: missingness ≤ 5%, staleness ≤ 30 дней, coverage ≥ 95%
- ACCEPTABLE: missingness ≤ 10%, staleness ≤ 60 дней, coverage ≥ 85%
- POOR: Любые значения хуже acceptable с некоторыми компенсациями
- UNUSABLE: Недостаточно строк или критические проблемы

#### Quality Thresholds (`QualityThresholds`)
Настраиваемые пороги для разных профилей валидации:

```python
@dataclass(frozen=True)
class QualityThresholds:
    """Конфигурируемые пороги качества для разных профилей."""

    missingness_excellent: float = 0.01    # 1% для excellent
    missingness_good: float = 0.05         # 5% для good
    missingness_acceptable: float = 0.10   # 10% для acceptable
    missingness_poor: float = 0.20         # 20% для poor

    staleness_excellent: int = 7           # 7 дней
    staleness_good: int = 30               # 30 дней
    staleness_acceptable: int = 60         # 60 дней
    staleness_poor: int = 90               # 90 дней

    coverage_excellent: float = 0.99       # 99%
    coverage_good: float = 0.95            # 95%
    coverage_acceptable: float = 0.85      # 85%
    coverage_poor: float = 0.70            # 70%

    min_row_count: int = 10                # Минимум строк
    schema_drift_penalty: int = 2          # Штраф за schema drift
    outlier_ratio_warning: float = 0.05    # Предупреждение о выбросах

    @classmethod
    def for_profile(cls, profile: str) -> "QualityThresholds":
        """Возвращает пороги для профиля: 'fast', 'mvp', 'strict'."""
```

**Профили порогов:**
- **FAST**: Либеральные пороги для быстрой итерации (missingness_acceptable=20%)
- **MVP**: Сбалансированные пороги для стандартной валидации
- **STRICT**: Строгие пороги для production/регуляторных требований (missingness_acceptable=5%)

#### Data Fitness Report (`DataFitnessReport`)
Человекочитаемые отчеты о качестве данных для принятия решений:

```python
@dataclass
class DataFitnessReport:
    """Отчет о пригодности данных для симуляции."""

    run_id: str
    profile: str = "mvp"
    metrics: List[MetricFitness] = field(default_factory=list)
    overall_passed: bool = True
    summary: str = ""
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def add_metric(self, fitness: MetricFitness) -> None:
        """Добавить оценку качества метрики."""

    def generate_summary(self) -> str:
        """Сгенерировать ASCII summary для логов."""

    def generate_markdown_summary(self) -> str:
        """Сгенерировать Markdown summary для документации."""
```

#### Metric Fitness (`MetricFitness`)
Оценка пригодности отдельной метрики с объяснениями:

```python
@dataclass
class MetricFitness:
    """Оценка пригодности одной метрики."""

    metric_id: str
    indicators: QualityIndicators
    level: QualityLevel
    fail_reasons: List[str] = field(default_factory=list)
    profile_used: str = "mvp"

    @property
    def passed(self) -> bool:
        """Прошла ли метрика quality gate."""
        return self.level.is_passing()
```

**Функции оценки качества:**
- `compute_quality_indicators()`: Вычисление из pandas DataFrame
- `compute_quality_from_duckdb()`: Вычисление напрямую из DuckDB (для больших датасетов)
- `get_cached_quality_indicators()`: Получение предвычисленных индикаторов из catalog

### 15. Quality Gate Validation (`scientist/governance/passes/quality_gate_pass.py`)

Интеграция системы качества данных с governance framework для блокировки низкокачественных данных перед симуляцией.

#### QualityGatePass
Validator pass, который оценивает качество данных и блокирует выполнение при обнаружении проблем:

```python
class QualityGatePass(ValidatorPass):
    """
    Валидирует качество данных перед выполнением симуляции.

    Поведение по профилям:
    - FAST: Пропускается (не входит в pass_ids)
    - MVP: Пропускается (не входит в pass_ids)
    - STRICT: Запускается и блокирует на POOR/UNUSABLE качестве
    """

    def __init__(
        self,
        *,
        force_run: bool = False,
        critical_metrics: list[str] | None = None,
    ) -> None:
        self._force_run = force_run
        self._critical_metrics = critical_metrics

    def validate(self, ctx: PassContext) -> List[ComplianceIssue]:
        """Выполнить валидацию качества данных."""
```

**Логика валидации:**
1. **Определение метрик**: Извлечение списка метрик из evidence bundle или явного списка
2. **Получение индикаторов**: Вычисление или получение из кэша quality indicators
3. **Оценка пригодности**: Применение threshold-based scoring для каждой метрики
4. **Формирование отчета**: Создание DataFitnessReport с детальными объяснениями
5. **Блокировка проблем**: Генерация ComplianceIssue для низкокачественных данных

#### Поведение по профилям
- **FAST**: Полностью пропускается для быстрой итерации
- **MVP**: Пропускается для баланса скорость/качество
- **STRICT**: Блокирует на POOR и UNUSABLE качестве

#### Типы проблем качества
- **QUALITY_UNUSABLE**: Метрика имеет UNUSABLE уровень (BLOCKER)
- **QUALITY_POOR**: Метрика имеет POOR уровень (BLOCKER в STRICT, WARNING в других)
- **INDICATORS_UNAVAILABLE**: Невозможно вычислить индикаторы (WARNING)

#### Интеграция с governance
QualityGatePass интегрируется в validation pipeline scientist модуля:

```python
# scientist/governance/profiles.py - включение quality gate
@dataclass
class ValidationProfile:
    @classmethod
    def strict(cls) -> "ValidationProfile":
        return cls(
            level=ProfileLevel.STRICT,
            pass_ids=["budget", "evidence", "quality", ...],  # Включает quality
            thresholds={"quality_missingness_acceptable": 0.05}
        )
```

**DataFitnessReport** прикрепляется к PassContext state для использования в DecisionPacket.

### 16. Fact Log System (Фактовая система)

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
Полноценная система восстановления реляционных представлений из immutable Fact Log:

```python
def load_fact_manifests(fact_dir: Path) -> list[FactSegmentManifest]:
    """Загрузка всех манифестов сегментов Fact Log."""

def ensure_materialized(
    fact_dir: Path,
    db: SimulationDB,
    *,
    force: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> None:
    """Обеспечение актуальной материализации с инкрементальными обновлениями."""

def materialize_duckdb_from_fact_log(fact_dir: Path, db: SimulationDB) -> None:
    """Полная материализация DuckDB таблиц из Fact Log сегментов."""
```

**Ключевые функции:**
- **Incremental Updates**: Инкрементальная материализация только новых сегментов
- **Schema Evolution**: Автоматическое создание и обновление схем таблиц
- **Type Inference**: Автоматическое определение типов колонок из фактов
- **Entity Resolution**: Применение entity resolution mapping при материализации
- **Progress Tracking**: Отслеживание прогресса через callback функции
- **Hash Verification**: Проверка целостности сегментов перед применением

**Преимущества архитектуры:**
- **Complete Audit Trail**: Полная история всех изменений данных
- **Reproducibility**: Восстановление любого состояния системы
- **Schema Evolution**: Безопасная миграция между версиями схем
- **Distributed Storage**: Поддержка распределенного хранения фактов
- **Data Lineage**: Полная traceability от сырых данных до результатов

### 17. Evidence System (`evidence.py`)

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

### 18. Trust System (`trust.py`)

Система политик доверия для источников данных и верификации качества:

#### Trust Policies
Определение уровней доверия к различным источникам данных:
- **Policy Definition**: JSON-based конфигурация политик доверия
- **Source Validation**: Проверка соответствия данных политике
- **Risk Assessment**: Оценка рисков использования данных

#### Основные функции:
```python
def two_pass_compare(
    optimistic_value: float,
    pessimistic_value: float,
    *,
    method: str = "two_pass_compare",
) -> UncertaintyBounds:
    """Двухпроходное сравнение значений с расчетом границ неопределенности."""

def persist_uncertainty_bounds(
    store: FileSystemCAS,
    bounds: UncertaintyBounds,
    *,
    schema_name: str = "fabric.uncertainty_bounds",
    schema_version: str = "1.0",
) -> UncertaintyBoundsRef:
    """Сохранение границ неопределенности в CAS."""
```

**Интеграция:** Используется в Fact Writer и Evidence Bundles для маркировки уровня доверия к данным. Поддерживает статистическую верификацию и сохранение результатов сравнения в Content Addressable Storage.

### 19. Provenance System (`provenance/`)

Стандартизированная система отслеживания происхождения данных на основе W3C PROV-O спецификации:

#### PROV-O Data Model
Система реализует полный PROV-O граф с тремя основными типами узлов:

```python
class ProvenanceEntity:
    """PROV-O Entity - данные или артефакты."""
    entity_id: str
    entity_type: EntityType  # DATASET, METRIC, SNAPSHOT, FACT_SEGMENT, etc.
    label: str
    created_at: datetime
    attributes: dict[str, Any]  # Дополнительные метаданные

class ProvenanceActivity:
    """PROV-O Activity - трансформации и действия."""
    activity_id: str
    activity_type: ActivityType  # INGEST, QUERY, ETL, VALIDATION, etc.
    label: str
    started_at: datetime
    ended_at: datetime | None
    query_hash: str | None  # Для query activities
    etl_step_id: str | None  # Для ETL steps
    code_artifact_ref: str | None  # Ссылка на код

class ProvenanceAgent:
    """PROV-O Agent - ответственные сущности."""
    agent_id: str
    agent_type: AgentType  # SYSTEM, USER, MODEL, SCHEDULER
    label: str
    metadata: dict[str, str]
```

#### PROV-O Relations
Полная поддержка W3C PROV-O отношений:

- **`wasDerivedFrom`**: Связь происхождения (derived_entity → source_entity)
- **`wasGeneratedBy`**: Связь генерации (entity → activity)
- **`used`**: Связь использования (activity → entity)
- **`wasAttributedTo`**: Связь атрибуции (entity → agent)
- **`wasAssociatedWith`**: Связь ассоциации (activity → agent)

#### ProvenanceCoreGraph
Минимальный внутренний граф provenance, всегда присутствующий в FabricResult:

```python
@dataclass
class ProvenanceCoreGraph:
    graph_id: str
    entities: dict[str, ProvenanceEntity]
    activities: dict[str, ProvenanceActivity]
    agents: dict[str, ProvenanceAgent]
    edges: list[ProvenanceEdge]

    # Методы построения графа
    def add_derivation(self, derived_id: str, source_id: str) -> None
    def add_generation(self, entity_id: str, activity_id: str) -> None
    def add_usage(self, activity_id: str, entity_id: str) -> None
    def add_attribution(self, entity_id: str, agent_id: str) -> None
    def add_association(self, activity_id: str, agent_id: str) -> None

    # Аналитические методы
    def get_ancestors(self, entity_id: str, max_depth: int = 10) -> set[str]
    def get_generating_activity(self, entity_id: str) -> str | None
```

#### Экспорт в PROV-O
Опциональный экспорт для STRICT validation или внешнего аудита:

```python
# Экспорт в JSON-LD для семантического веба
prov_jsonld = export_to_provo_jsonld(graph, base_uri="https://polisyos.io/provenance/")

# Экспорт в N-Quads для RDF triple stores
prov_nquads = export_to_provo_nquads(graph, base_uri="https://polisyos.io/provenance/")
```

**Ключевые возможности:**
- **Стандартизация**: Полная совместимость с W3C PROV-O спецификацией
- **Minimal Internal Model**: Легковесный ProvenanceCoreGraph для внутренней работы
- **Deterministic IDs**: SHA256-based генерация стабильных ID для CAS хранения
- **Query Lineage**: Отслеживание полного пути от сырых данных до результатов запросов
- **Multi-format Export**: JSON-LD и N-Quads для разных потребителей
- **Immutable Storage**: Сохранение в Content Addressable Storage для аудита

**Интеграция с Fabric:** Каждый FabricResult включает ProvenanceCoreRef, позволяя отслеживать происхождение всех данных в системе.

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
    db_path=Path("simulation.duckdb"),
    kuzu_path=Path("simulation.kuzu"),
    source="demo_dataset",
    license_name="MIT",
    reconciliation_tolerance=1e-4,
    reconciliation_strict=False
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

# Инициализация UDF движка с поддержкой Fact Log
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

# Запрос среза агентов (SNAPSHOT view)
agents_request = DataViewRequest(
    view_type=DataViewType.SNAPSHOT,
    dataset_name="agents",
    metrics=["agent_id", "age", "income", "savings"],
    filters=[DataFilter(column="step", operator="=", value=50)],
    access_tier=AccessTier.INTERNAL
)

agents_snapshot = engine.query(agents_request)

# Запрос с Arrow для высокой производительности
agents_arrow = engine.query_arrow(agents_request)
print(f"Arrow table: {agents_arrow.num_rows} rows, {agents_arrow.num_columns} columns")

# Запрос с полным FabricResult (включая provenance)
result = engine.query_result(agents_request)
print(f"Query executed, data saved as: {result.data_ref.artifact_id}")
print(f"Evidence bundle: {result.evidence_ref.artifact_id}")

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
from polisyos.fabric.materializer import (
    ensure_materialized,
    materialize_duckdb_from_fact_log,
    load_fact_manifests
)
from polisyos.fabric.io.db import SimulationDB

# Инициализация хранилища
db = SimulationDB("simulation.duckdb")
fact_dir = Path("data/facts")

# Просмотр доступных сегментов Fact Log
manifests = load_fact_manifests(fact_dir)
print(f"Found {len(manifests)} fact segments")

# Инкрементальная материализация (только новые сегменты)
def progress_callback(msg: str):
    print(f"Materialization: {msg}")

ensure_materialized(
    fact_dir,
    db,
    force=False,  # Только новые сегменты
    progress_callback=progress_callback
)

# Или полная материализация
materialize_duckdb_from_fact_log(fact_dir, db)

print("DuckDB materialized from Fact Log")
db.close()
```

### Работа с Data Contract Catalog

```python
from polisyos.fabric.catalog import (
    DataContractRegistry, MetricSearcher, DataContract,
    DataType, Granularity, PIITier
)
from pathlib import Path

# Инициализация registry
registry = DataContractRegistry(Path("data/curated"))

# Поиск метрик
searcher = MetricSearcher(list(registry))

# Fuzzy поиск с disambiguation
response = searcher.search("unemployment rate")
if response.needs_disambiguation:
    print("Ambiguous query. Options:")
    for result in response.results[:3]:
        print(f"  {result.contract.display_name}: {result.confidence:.0%}")
else:
    binding = response.best_match.binding
    print(f"Found: {binding.metric_id}")

# Exact resolution (raises on ambiguity)
binding = searcher.resolve("us.macro.unemployment_rate")

# Валидация binding (проверка hash)
contract = registry.validate_binding(binding)
print(f"Contract: {contract.display_name}, Unit: {contract.unit}")
```

### Создание Data Contracts

```python
from polisyos.fabric.catalog.contract import DataContract, DataContractCollection

# Создание контракта для метрики
contract = DataContract(
    metric_id="us.macro.gdp_nominal",
    display_name="Nominal GDP",
    description="Gross Domestic Product in nominal terms",
    dtype=DataType.FLOAT,
    unit="USD",
    granularity=Granularity.QUARTERLY,
    dimensions=["region", "sector"],
    valid_range=(0, None),  # Must be positive
    source_system="bea.gov",
    source_table="gdp_quarterly",
    source_column="nominal_gdp",
    jurisdiction="US",
    pii_tier=PIITier.NONE,
    aliases=["GDP", "nominal gdp", "gross domestic product"],
    tags=["macro", "economic", "gdp"]
)

# Сохранение коллекции контрактов
collection = DataContractCollection(
    schema_version="1.0",
    generated_at="2024-01-15T10:00:00Z",
    generated_by="scan_fabric.py",
    contracts=[contract]
)

import json
with open("data/curated/data_contracts.json", "w") as f:
    json.dump(collection.model_dump(), f, indent=2)
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

### Оценка качества данных

```python
from polisyos.fabric.quality import (
    compute_quality_indicators, QualityIndicators, QualityLevel, QualityThresholds
)
from polisyos.fabric.fitness_report import DataFitnessReport, MetricFitness
import pandas as pd

# Загрузка датасета
agents_df = pd.read_csv("data/curated/agents.csv")

# Вычисление quality indicators
indicators = compute_quality_indicators(
    df=agents_df,
    metric_id="agents_dataset",
    expected_row_count=10000,  # Ожидаемое количество строк
    last_updated=pd.Timestamp("2024-01-15"),  # Последнее обновление
)

print(f"Качество данных для {indicators.metric_id}:")
print(f"  Пропущенные значения: {indicators.missingness:.1%}")
print(f"  Устаревание: {indicators.staleness_days} дней")
print(f"  Покрытие: {indicators.coverage:.1%}")
print(f"  Количество строк: {indicators.row_count}")

# Оценка уровня качества
thresholds = QualityThresholds.for_profile("mvp")
level = indicators.overall_level(thresholds)
print(f"  Уровень качества: {level.value.upper()}")

# Получение объяснений проблем
if not level.is_passing():
    reasons = indicators.get_failure_reasons(thresholds)
    print("  Проблемы:")
    for reason in reasons:
        print(f"    - {reason}")
```

### Создание Fitness Report

```python
from polisyos.fabric.fitness_report import DataFitnessReport, MetricFitness

# Создание отчета о качестве данных
report = DataFitnessReport(run_id="simulation_run_001", profile="strict")

# Добавление оценки для каждой метрики
for metric_id, indicators in quality_indicators_dict.items():
    thresholds = QualityThresholds.for_profile("strict")
    fitness = MetricFitness.from_indicators(
        indicators=indicators,
        thresholds=thresholds,
        profile="strict"
    )
    report.add_metric(fitness)

# Генерация summary
summary = report.generate_summary()
print("Отчет о качестве данных:")
print(summary)

# Markdown версия для документации
markdown_report = report.generate_markdown_summary()
with open("data_quality_report.md", "w") as f:
    f.write(markdown_report)

print(f"\nОбщий результат: {'ПРОЙДЕНО' if report.overall_passed else 'НЕ ПРОЙДЕНО'}")
print(f"Прошло метрик: {report.passed_metrics}/{report.total_metrics}")
```

### Кастомные пороги качества

```python
from polisyos.fabric.quality import QualityThresholds

# Создание строгих порогов для production
strict_thresholds = QualityThresholds(
    missingness_acceptable=0.05,  # Максимум 5% пропусков
    staleness_acceptable=30,      # Максимум 30 дней устаревания
    coverage_acceptable=0.95,     # Минимум 95% покрытия
    min_row_count=1000,           # Минимум 1000 строк
)

# Или модификация существующих порогов
custom_thresholds = QualityThresholds.for_profile("mvp").with_overrides({
    "missingness_acceptable": 0.08,  # Более либеральный для нашего случая
    "staleness_acceptable": 45,      # Более долгий период приемлемости
})

# Использование кастомных порогов
indicators = compute_quality_indicators(df=my_data, metric_id="custom_metric")
level = indicators.overall_level(custom_thresholds)
print(f"Уровень качества с кастомными порогами: {level.value}")
```

### Работа с Data Connectors

```python
from polisyos.fabric.connectors import (
    SourceConnector, FetchRequest, FetchResult,
    ConnectorCapability, ConnectionConfig, ConnectionHandle,
    validate_protocol_compliance
)
from datetime import datetime, timezone

# Создание кастомного connector
class WorldBankConnector(SourceConnector[list[dict]]):
    connector_id = "worldbank.wdi"
    capabilities = (
        ConnectorCapability.FULL_FETCH |
        ConnectorCapability.DATE_RANGE_FILTER |
        ConnectorCapability.SCHEMA_INTROSPECTION
    )

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        # Реализация подключения к World Bank API
        return ConnectionHandle(connection_id="wb_api_v1")

    async def fetch(
        self, handle: ConnectionHandle, request: FetchRequest
    ) -> FetchResult[list[dict]]:
        # Реализация fetch логики
        return FetchResult(
            data=[{"country": "USA", "gdp": 25000000000000, "year": 2023}],
            evidence_ref=None,
            request_key=request.request_key
        )

# Валидация protocol compliance
violations = validate_protocol_compliance(WorldBankConnector)
if violations:
    raise ConfigurationError(f"Protocol violations: {violations}")

# Использование connector
connector = WorldBankConnector()
handle = await connector.connect(ConnectionConfig(api_key="your_key"))

request = FetchRequest(
    dataset_id="worldbank.wdi.GDP.MKTP.CD",
    date_start=datetime(2020, 1, 1, tzinfo=timezone.utc),
    date_end=datetime(2023, 12, 31, tzinfo=timezone.utc)
)

result = await connector.fetch(handle, request)
print(f"Fetched {len(result.data)} records")
print(f"Request key: {result.request_key}")  # Для CAS кэширования
```

### Работа с Provenance System

```python
from polisyos.fabric.provenance import (
    ProvenanceCoreGraph, ProvenanceEntity, ProvenanceActivity, ProvenanceAgent,
    EntityType, ActivityType, AgentType, export_to_provo_jsonld
)

# Создание provenance графа для запроса
graph = ProvenanceCoreGraph(graph_id="udf_query_001")

# Добавление сущностей
macro_data = ProvenanceEntity(
    entity_id="macro_dataset_v1",
    entity_type=EntityType.DATASET,
    label="Macroeconomic Dataset",
    created_at=datetime.utcnow()
)

query_result = ProvenanceEntity(
    entity_id="gdp_analysis_result",
    entity_type=EntityType.QUERY_RESULT,
    label="GDP Analysis Result",
    created_at=datetime.utcnow()
)

# Добавление активности
udf_query = ProvenanceActivity(
    activity_id="udf_query_exec",
    activity_type=ActivityType.QUERY,
    label="UDF Query Execution",
    started_at=datetime.utcnow(),
    query_hash="sha256:abc123..."
)

# Добавление агента
scientist_agent = ProvenanceAgent(
    agent_id="scientist_system",
    agent_type=AgentType.SYSTEM,
    label="PolicyOS Scientist Agent"
)

graph.add_entity(macro_data)
graph.add_entity(query_result)
graph.add_activity(udf_query)
graph.add_agent(scientist_agent)

# Установление PROV-O связей
graph.add_derivation("gdp_analysis_result", "macro_dataset_v1")  # wasDerivedFrom
graph.add_usage("udf_query_exec", "macro_dataset_v1")            # used
graph.add_generation("gdp_analysis_result", "udf_query_exec")    # wasGeneratedBy
graph.add_association("udf_query_exec", "scientist_system")      # wasAssociatedWith

# Анализ lineage
ancestors = graph.get_ancestors("gdp_analysis_result")
print(f"Result depends on {len(ancestors)} source entities")

# Экспорт в JSON-LD для аудита
prov_jsonld = export_to_provo_jsonld(graph, base_uri="https://polisyos.io/provenance/")
```

### Интеграция с Data Contract Registry

```python
from polisyos.fabric.catalog import DataContractRegistry
from polisyos.fabric.quality import get_cached_quality_indicators

# Загрузка registry с контрактами
registry = DataContractRegistry(Path("data/curated"))

# Получение предвычисленных quality indicators из контракта
for metric_id in ["us.macro.gdp", "us.macro.unemployment_rate"]:
    cached_indicators = get_cached_quality_indicators(metric_id, registry)
    if cached_indicators:
        print(f"Кэшированные индикаторы для {metric_id}:")
        print(f"  Missingness: {cached_indicators.missingness:.2%}")
        print(f"  Staleness: {cached_indicators.staleness_days} дней")
    else:
        print(f"Индикаторы качества для {metric_id} не найдены в кэше")
```

### Quality Gate Validation в Governance Pipeline

```python
from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass
from polisyos.scientist.governance.passes.base import PassContext
from polisyos.scientist.governance.profiles import ValidationProfile

# Создание quality gate pass
quality_pass = QualityGatePass(
    force_run=True,  # Принудительный запуск независимо от профиля
    critical_metrics=["agents", "macro"]  # Критические метрики для проверки
)

# Настройка контекста валидации
profile = ValidationProfile.strict()
ctx = PassContext(
    ir=None,
    state={
        "evidence_bundle": evidence_bundle,  # Из предыдущих шагов
        "catalog_registry": catalog_registry,  # Registry с контрактами
    },
    registry_bundle=None,
    profile=profile,
    run_id="validation_run_001"
)

# Запуск валидации качества
issues = quality_pass.validate(ctx)

# Проверка результатов
blockers = [issue for issue in issues if issue.severity.name == "BLOCKER"]
if blockers:
    print(f"Блокирующие проблемы качества: {len(blockers)}")
    for issue in blockers:
        print(f"  - {issue.message}")
        if issue.suggestion:
            print(f"    Совет: {issue.suggestion}")
else:
    print("Все проверки качества пройдены")

# Получение fitness report
if "data_fitness_report" in ctx.state:
    report = ctx.state["data_fitness_report"]
    print(f"Отчет качества: {report.passed_metrics}/{report.total_metrics} метрик прошло")
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
- **Claims Processing System**: Извлечение и разрешение конфликтов claims из документов с confidence scoring
- **Document Processing System**: Многоформатная обработка документов (PDF, HTML, plain text) с intelligent chunking
- **World Model System**: Материализация модели мира из Fact Log с поддержкой множественных представлений
- **Data Connectors System (Phase 2.1)**: Protocol-based подключение к внешним источникам с capability validation
- **Data Quality Assessment System**: Многоуровневая оценка пригодности данных (QualityIndicators, QualityLevel, QualityThresholds, DataFitnessReport)
- **Quality Gate Validation**: Интеграция с governance system для блокировки низкокачественных данных (QualityGatePass)
- **Data Contract Catalog**: Metric-level type safety с hash-locked bindings для Scientist агента
- **Provenance System**: W3C PROV-O compliant lineage tracking для полного audit trail
- **Fact Log System**: Полная интеграция с `ir.fact_log` для immutable хранения фактов
- **Evidence System**: Использование `core.contracts.fabric` и `core.artifacts` для verifiable доказательств
- **UDF Compilation Pipeline**: Многофазный компилятор с passes для security и optimization
- **Materializer Engine**: Полноценная система восстановления реляционных представлений из Fact Log с инкрементальными обновлениями
- **Trust Policies**: Многоуровневые политики доверия с статистической верификацией
- **CAS Integration**: Content Addressable Storage для всех артефактов и evidence bundles
- **Arrow Support**: Высокопроизводительная работа с columnar данными
- **Lazy Materialization**: Автоматическая материализация данных по требованию и evidence

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

# Новые компоненты
pytest tests/fabric/connectors/test_protocol_compliance.py  # Data Connectors
pytest tests/fabric/test_provenance_core.py    # Provenance Core модели
pytest tests/fabric/test_provenance_export.py  # PROV-O экспорт
pytest tests/fabric/test_catalog_contracts.py  # Data Contract Catalog
pytest tests/fabric/test_catalog_search.py     # Metric Search
pytest tests/fabric/test_catalog_registry.py   # Contract Registry

# Foundry интеграция
pytest tests/foundry/test_fiscal.py           # Fiscal с UDF данными
pytest tests/foundry/test_constraints_executor.py  # Constraints с данными Fabric

# Специфические тесты новых компонентов
pytest tests/contract/test_fabric_gates.py   # Evidence bundles и контракты
pytest tests/integration/test_catalog_scientist_integration.py  # Catalog + Scientist
pytest tests/integration/test_catalog_udf_integration.py  # Catalog + UDF
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
- **Claims Processing System**: Извлечение, нормализация и разрешение конфликтов claims из документов
- **Document Processing System**: Многоформатная обработка документов с intelligent chunking и structure analysis
- **World Model System**: Материализация и управление моделью мира с поддержкой множественных представлений
- **Data Quality Assessment System**: Комплексная оценка пригодности данных с QualityIndicators, QualityLevel и configurable thresholds
- **Quality Gate Validation**: Интеграция с governance system для блокировки низкокачественных данных перед симуляцией
- **Data Fitness Reports**: Человекочитаемые отчеты о качестве данных с детальными объяснениями проблем
- **Fact Log System**: Complete immutable audit trail с deterministic fact IDs
- **Evidence Bundles**: Cryptographically verifiable provenance tracking
- **Provenance System**: W3C PROV-O compliant lineage tracking для полного audit trail
- **UDF Compilation Pipeline**: Multi-phase compilation с security passes
- **Materializer Engine**: Полноценная incremental материализация реляционных представлений из фактов
- **Trust Policies**: Multi-tier trust validation с statistical verification
- **CAS Integration**: Content-addressable storage для всех артефактов
- **Arrow Support**: High-performance columnar data processing
- **FabricResult**: Structured results с complete provenance chain

Модуль следует принципам архитектуры (Законы A, B, C, D), обеспечивая чистое разделение ответственности между ingestion, storage, query и audit слоями, с четкими контрактами для интеграции с остальной системой.
