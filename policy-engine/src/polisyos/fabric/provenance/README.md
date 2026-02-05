# Polisyos Fabric Provenance System

**Provenance** — стандартизированная система отслеживания происхождения данных на основе спецификации W3C PROV-O (Provenance Ontology). Модуль обеспечивает полный audit trail от сырых данных до результатов симуляций через структурированный граф provenance.

## Архитектурная роль

### Положение в Fabric экосистеме

Provenance система является ключевым компонентом **Data Lineage & Audit** слоя в Fabric:

```
Data Sources → Ingestion → Fact Log → Materialization → UDF Query → Results
     ↓           ↓          ↓            ↓           ↓          ↓
Provenance → Provenance → Provenance → Provenance → Provenance → Provenance
Tracking    Tracking    Tracking    Tracking    Tracking    Tracking
```

### Ключевые обязанности

1. **Lineage Tracking**: Отслеживание полного пути трансформации данных от источника до потребителя
2. **PROV-O Compliance**: Полная совместимость со стандартом W3C PROV-O
3. **Deterministic Identity**: Стабильная идентификация узлов и связей для CAS хранения
4. **Multi-format Export**: Экспорт в JSON-LD и N-Quads для разных потребителей
5. **Query Analysis**: Анализ зависимостей и происхождения результатов запросов
6. **Audit Trail**: Криптографически verifiable доказательства происхождения

## W3C PROV-O Спецификация

### Основные концепции PROV-O

PROV-O определяет три базовых типа сущностей:

#### Entities (prov:Entity)
Представляют данные или артефакты в любой момент времени:
- **Dataset**: Наборы данных (CSV, Parquet файлы)
- **Metric**: Вычисляемые метрики и показатели
- **Snapshot**: Срезы состояния на конкретный момент
- **Fact Segment**: Группы immutable фактов
- **Query Result**: Результаты выполнения запросов

#### Activities (prov:Activity)
Представляют действия или процессы, которые происходят в течение времени:
- **Ingest**: Загрузка и обработка сырых данных
- **Query**: Выполнение запросов к данным
- **ETL**: Трансформации и очистка данных
- **Validation**: Проверка качества и консистентности
- **Aggregation**: Агрегация и вычисление метрик
- **Simulation Step**: Шаги симуляции

#### Agents (prov:Agent)
Представляют сущности, ответственные за activities:
- **System**: Автоматизированные компоненты (Fabric, Scientist)
- **User**: Люди, инициирующие процессы
- **Model**: AI модели, принимающие решения
- **Scheduler**: Системы планирования задач

### PROV-O Relations

Спецификация определяет базовые отношения между сущностями:

- **`wasDerivedFrom`**: Связь происхождения (derived_entity ← source_entity)
- **`wasGeneratedBy`**: Связь генерации (entity ← activity)
- **`used`**: Связь использования (activity → entity)
- **`wasAttributedTo`**: Связь атрибуции (entity ← agent)
- **`wasAssociatedWith`**: Связь ассоциации (activity ← agent)
- **`actedOnBehalfOf`**: Делегирование ответственности (agent ← agent)

## Структура модуля

```
provenance/
├── __init__.py              # Экспорт всех компонентов
├── core.py                  # Базовые модели и ProvenanceCoreGraph
└── export_provo.py          # Экспорт в PROV-O форматы
```

## Ключевые компоненты

### 1. Core Models (`core.py`)

#### Entity Types
```python
class EntityType(Enum):
    DATASET = "dataset"
    METRIC = "metric"
    SNAPSHOT = "snapshot"
    FACT_SEGMENT = "fact_segment"
    QUERY_RESULT = "query_result"
    SIMULATION_STATE = "simulation_state"
```

#### Activity Types
```python
class ActivityType(Enum):
    INGEST = "ingest"
    QUERY = "query"
    ETL = "etl"
    AGGREGATION = "aggregation"
    SIMULATION_STEP = "simulation_step"
    VALIDATION = "validation"
    MERGE = "merge"
```

#### Agent Types
```python
class AgentType(Enum):
    SYSTEM = "system"
    USER = "user"
    MODEL = "model"
    SCHEDULER = "scheduler"
```

#### PROV-O Relations
```python
class RelationType(Enum):
    WAS_DERIVED_FROM = "wasDerivedFrom"
    WAS_GENERATED_BY = "wasGeneratedBy"
    USED = "used"
    WAS_ATTRIBUTED_TO = "wasAttributedTo"
    WAS_ASSOCIATED_WITH = "wasAssociatedWith"
    ACTED_ON_BEHALF_OF = "actedOnBehalfOf"
```

### 2. Provenance Entities

#### ProvenanceEntity
```python
@dataclass(frozen=True, slots=True)
class ProvenanceEntity:
    entity_id: str              # Уникальный ID сущности
    entity_type: EntityType     # Тип сущности
    label: str                  # Человекочитаемое имя
    created_at: datetime        # Время создания
    attributes: dict[str, Any]  # Дополнительные атрибуты
```

#### ProvenanceActivity
```python
@dataclass(frozen=True, slots=True)
class ProvenanceActivity:
    activity_id: str                # Уникальный ID активности
    activity_type: ActivityType     # Тип активности
    label: str                      # Человекочитаемое имя
    started_at: datetime            # Время начала
    ended_at: datetime | None       # Время окончания
    query_hash: str | None          # Хэш запроса (для query activities)
    etl_step_id: str | None         # ID ETL шага
    code_artifact_ref: str | None   # Ссылка на код
    parameters: dict[str, Any]      # Параметры выполнения
```

#### ProvenanceAgent
```python
@dataclass(frozen=True, slots=True)
class ProvenanceAgent:
    agent_id: str                # Уникальный ID агента
    agent_type: AgentType        # Тип агента
    label: str                   # Человекочитаемое имя
    metadata: dict[str, str]     # Метаданные агента
```

#### ProvenanceEdge
```python
@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    source_id: str              # ID исходного узла
    target_id: str              # ID целевого узла
    relation: RelationType      # Тип отношения PROV-O
    timestamp: datetime | None  # Время создания связи
```

### 3. ProvenanceCoreGraph

Основной класс для работы с графом provenance:

```python
@dataclass
class ProvenanceCoreGraph:
    graph_id: str
    entities: dict[str, ProvenanceEntity] = field(default_factory=dict)
    activities: dict[str, ProvenanceActivity] = field(default_factory=dict)
    agents: dict[str, ProvenanceAgent] = field(default_factory=dict)
    edges: list[ProvenanceEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = field(default_factory=dict)
```

#### Методы построения графа

```python
# Добавление узлов
def add_entity(self, entity: ProvenanceEntity) -> None
def add_activity(self, activity: ProvenanceActivity) -> None
def add_agent(self, agent: ProvenanceAgent) -> None

# Добавление PROV-O отношений
def add_derivation(self, derived_id: str, source_id: str, timestamp: datetime | None = None) -> None
def add_generation(self, entity_id: str, activity_id: str, timestamp: datetime | None = None) -> None
def add_usage(self, activity_id: str, entity_id: str, timestamp: datetime | None = None) -> None
def add_attribution(self, entity_id: str, agent_id: str, timestamp: datetime | None = None) -> None
def add_association(self, activity_id: str, agent_id: str, timestamp: datetime | None = None) -> None
```

#### Аналитические методы

```python
# Поиск предков (источников) сущности
def get_ancestors(self, entity_id: str, max_depth: int = 10) -> set[str]

# Поиск активности, которая сгенерировала сущность
def get_generating_activity(self, entity_id: str) -> str | None

# O(1) поиск узлов
def get_entity(self, entity_id: str) -> ProvenanceEntity | None
def get_activity(self, activity_id: str) -> ProvenanceActivity | None
def get_agent(self, agent_id: str) -> ProvenanceAgent | None
```

#### Сериализация и хранение

```python
# Детерминированная сериализация для CAS
def compute_stable_id(self) -> str

# Конвертация в/из словаря для хранения
def to_dict(self) -> dict[str, Any]
@classmethod
def from_dict(cls, data: dict[str, Any]) -> ProvenanceCoreGraph
```

### 4. PROV-O Export (`export_provo.py`)

#### JSON-LD Export
Экспорт в W3C PROV-O JSON-LD формат для семантического веба:

```python
def export_to_provo_jsonld(
    graph: ProvenanceCoreGraph,
    base_uri: str = "https://polisyos.io/provenance/",
) -> dict[str, Any]
```

**Пример вывода:**
```json
{
  "@context": {
    "prov": "http://www.w3.org/ns/prov#",
    "polisyos": "https://polisyos.io/ns/provenance#",
    "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
    "used": {"@id": "prov:used", "@type": "@id"}
  },
  "@graph": [
    {
      "@id": "https://polisyos.io/provenance/entity/dataset_001",
      "@type": "prov:Entity",
      "rdfs:label": "Agents Dataset",
      "prov:generatedAtTime": "2024-01-15T10:00:00Z",
      "polisyos:entityType": "dataset"
    },
    {
      "@id": "https://polisyos.io/provenance/activity/ingest_001",
      "@type": "prov:Activity",
      "rdfs:label": "Data Ingestion",
      "prov:startedAtTime": "2024-01-15T10:00:00Z",
      "prov:endedAtTime": "2024-01-15T10:05:00Z"
    }
  ]
}
```

#### N-Quads Export
Экспорт в N-Quads формат для загрузки в RDF triple stores:

```python
def export_to_provo_nquads(
    graph: ProvenanceCoreGraph,
    base_uri: str = "https://polisyos.io/provenance/",
) -> str
```

**Пример вывода:**
```
<https://polisyos.io/provenance/entity/dataset_001> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/ns/prov#Entity> .
<https://polisyos.io/provenance/entity/dataset_001> <http://www.w3.org/2000/01/rdf-schema#label> "Agents Dataset" .
<https://polisyos.io/provenance/activity/ingest_001> <http://www.w3.org/ns/prov#used> <https://polisyos.io/provenance/entity/dataset_001> .
```

### 5. ProvenanceCoreRef

Легковесная ссылка на сохраненный граф provenance:

```python
@dataclass(frozen=True)
class ProvenanceCoreRef:
    graph_id: str      # ID графа
    stable_id: str     # Детерминированный ID для CAS
    artifact_id: str   # ID артефакта в CAS
```

## Примеры использования

### Построение графа provenance для ingestion pipeline

```python
from polisyos.fabric.provenance import (
    ProvenanceCoreGraph, ProvenanceEntity, ProvenanceActivity, ProvenanceAgent,
    EntityType, ActivityType, AgentType
)
from datetime import datetime

# Создание графа provenance
graph = ProvenanceCoreGraph(graph_id="ingestion_run_001")

# Добавление агентов
fabric_agent = ProvenanceAgent(
    agent_id="fabric_system",
    agent_type=AgentType.SYSTEM,
    label="Fabric Ingestion System"
)
graph.add_agent(fabric_agent)

# Добавление исходных данных
raw_data = ProvenanceEntity(
    entity_id="raw_agents_csv",
    entity_type=EntityType.DATASET,
    label="Raw Agents CSV",
    created_at=datetime.utcnow(),
    attributes={"source": "simulation_data.csv", "format": "csv"}
)
graph.add_entity(raw_data)

# Добавление активности ingestion
ingest_activity = ProvenanceActivity(
    activity_id="ingest_agents_001",
    activity_type=ActivityType.INGEST,
    label="Agents Data Ingestion",
    started_at=datetime.utcnow(),
    etl_step_id="entity_resolution",
    parameters={"entity_resolution": "enabled", "validation": "strict"}
)
graph.add_activity(ingest_activity)

# Добавление результатов
processed_data = ProvenanceEntity(
    entity_id="processed_agents",
    entity_type=EntityType.DATASET,
    label="Processed Agents Dataset",
    created_at=datetime.utcnow(),
    attributes={"row_count": 1500, "entity_resolution_applied": True}
)
graph.add_entity(processed_data)

# Установление PROV-O связей
graph.add_attribution("raw_agents_csv", "fabric_system")  # Кто создал сырые данные
graph.add_association("ingest_agents_001", "fabric_system")  # Кто выполнил ingestion
graph.add_usage("ingest_agents_001", "raw_agents_csv")  # Какие данные использовались
graph.add_generation("processed_agents", "ingest_agents_001")  # Что было сгенерировано
graph.add_derivation("processed_agents", "raw_agents_csv")  # Откуда произошли данные

print(f"Graph has {len(graph.entities)} entities, {len(graph.activities)} activities")
```

### Анализ lineage для результатов запроса

```python
# Поиск всех источников для конкретного результата запроса
result_entity_id = "query_result_abc123"
ancestors = graph.get_ancestors(result_entity_id, max_depth=5)

print(f"Result {result_entity_id} depends on {len(ancestors)} source entities:")
for ancestor_id in ancestors:
    entity = graph.get_entity(ancestor_id)
    if entity:
        print(f"  - {entity.label} ({entity.entity_type.value})")

# Поиск активности, которая сгенерировала результат
generating_activity = graph.get_generating_activity(result_entity_id)
if generating_activity:
    activity = graph.get_activity(generating_activity)
    print(f"Generated by: {activity.label} at {activity.started_at}")
```

### Экспорт для внешнего аудита

```python
# Экспорт в JSON-LD для семантического анализа
prov_jsonld = export_to_provo_jsonld(graph)

# Сохранение в файл
import json
with open("provenance_audit.jsonld", "w") as f:
    json.dump(prov_jsonld, f, indent=2)

# Экспорт в N-Quads для загрузки в triple store
prov_nquads = export_to_provo_nquads(graph)
with open("provenance_audit.nq", "w") as f:
    f.write(prov_nquads)
```

### Интеграция с FabricResult

```python
from polisyos.fabric.provenance import ProvenanceCoreRef

# В FabricResult provenance доступен через ссылку
@dataclass
class FabricResult:
    data_ref: ArtifactRef
    evidence_ref: EvidenceBundleRef
    provenance_ref: ProvenanceCoreRef  # Ссылка на полный граф provenance
    query_plan: DataViewPlan

# Загрузка полного графа provenance при необходимости
def analyze_query_lineage(result: FabricResult, cas: FileSystemCAS):
    # Загрузка графа из CAS
    graph_data = cas.load_artifact(result.provenance_ref.artifact_id)
    graph = ProvenanceCoreGraph.from_dict(graph_data)

    # Анализ lineage
    ancestors = graph.get_ancestors(result.data_ref.artifact_id)
    return {
        "source_entities": len(ancestors),
        "activities_involved": len(graph.activities),
        "agents_responsible": len(graph.agents)
    }
```

## Интеграция с Fabric экосистемой

### Связь с Evidence System
- **ProvenanceCoreGraph**: Внутренняя модель для быстрого анализа
- **Evidence Bundles**: Содержат ProvenanceCoreRef для полного lineage
- **CAS Storage**: Графы provenance хранятся immutable в Content Addressable Storage

### Связь с Claims Processing
- **Extraction Provenance**: Полный audit trail от документа до извлеченных claims
- **Normalization Tracking**: Provenance для всех трансформаций claims
- **Conflict Resolution**: Доказательства выбора между конфликтующими claims

### Связь с Document Processing
- **Ingestion Provenance**: От источника документа до нормализованного текста
- **Chunking Audit**: Доказательства семантического разбиения на chunks
- **Structure Analysis**: Provenance для извлеченных структурных элементов

### Связь с World Model
- **Materialization Provenance**: Audit trail для восстановления представлений
- **Fact Emission**: Provenance для каждого эмитированного факта мира
- **Projection Tracking**: Доказательства создания проекций данных

### Связь с UDF Engine
- **Query Provenance**: Каждый запрос генерирует provenance граф
- **Result Tracking**: FabricResult включает provenance для traceability
- **Security Audit**: Проверка доступа через provenance chain

### Связь с Fact Log
- **Fact Segments**: Каждый сегмент имеет provenance метаданные
- **Materialization**: Процесс материализации tracked через provenance
- **Audit Trail**: Полная история от фактов до результатов

### Связь с Trust System
- **Source Attribution**: Агенты provenance маркируют trustworthy источники
- **Risk Assessment**: Анализ provenance для оценки рисков
- **Compliance**: PROV-O стандарт для регуляторных требований

## Производительность и масштабируемость

### Оптимизации

**Deterministic ID Generation:**
- SHA256 хэширование канонического JSON для стабильных ID
- O(1) вставка и поиск узлов через dict
- Минимальный memory footprint через dataclass slots

**Incremental Graph Building:**
- Ленивое построение графа по мере необходимости
- BFS с depth limit для предотвращения бесконечных циклов
- Опциональная eager материализация для часто используемых графов

**Storage Optimizations:**
- Компактная сериализация для CAS хранения
- Опциональный экспорт только для внешних потребителей
- Delta encoding для incremental updates

### Benchmarking

```python
# Производительность построения графа
import time

start = time.time()
for i in range(1000):
    graph.add_entity(ProvenanceEntity(...))
    graph.add_activity(ProvenanceActivity(...))
    graph.add_derivation(f"entity_{i}", f"source_{i}")
end = time.time()

print(f"Built graph with 1000 entities in {end-start:.3f}s")
print(f"Average: {(end-start)/1000*1000:.1f}ms per entity")
```

### Масштабирование

**Large Graph Handling:**
- Chunked processing для больших графов
- Distributed storage через CAS federation
- Lazy loading для редко используемых ветвей

**Query Optimization:**
- Предварительно вычисленные индексы для частых запросов
- Cached ancestor lookups для популярных entities
- Parallel traversal для широких графов

## Тестирование и валидация

### Unit Tests
```bash
# Тестирование core моделей
pytest tests/fabric/test_provenance_core.py

# Тестирование PROV-O экспорта
pytest tests/fabric/test_provenance_export.py

# Интеграционные тесты
pytest tests/integration/test_fabric_provenance.py
```

### PROV-O Compliance
```python
# Валидация PROV-O структуры
def validate_prov_o_compliance(graph: ProvenanceCoreGraph) -> bool:
    # Проверка корректности отношений
    # Проверка temporal consistency
    # Проверка referential integrity
    pass
```

## Безопасность и приватность

### Data Protection
- **PII Handling**: Entity attributes могут содержать sensitive данные
- **Access Control**: Provenance graphs наследуют permissions от данных
- **Audit Logging**: Все операции с provenance логируются

### Cryptographic Integrity
- **Deterministic IDs**: Предотвращает tampering через hash-based identity
- **Immutable Storage**: CAS обеспечивает неизменность provenance
- **Signature Support**: Возможность цифровой подписи графов

## Заключение

**Provenance System** обеспечивает:

- **Стандартизированный Audit Trail**: Полная совместимость с W3C PROV-O
- **Deterministic Identity**: Стабильные ID для immutable хранения
- **Flexible Export**: Множество форматов для разных потребителей
- **Performance**: Оптимизированная структура для больших графов
- **Integration**: Глубокая интеграция со всеми компонентами Fabric

Модуль следует принципам архитектуры, обеспечивая trustworthy и auditable data lineage для критически важных симуляций экономической политики.