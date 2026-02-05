# IR World: Семантическая модель мира и событий

**World** - семантическая модель мира Policy Engine, определяющая события, утверждения, конфликты и их разрешение. World предоставляет унифицированную модель для представления эволюции мира во времени с provenance tracking, quality assessment и trust evaluation.

**Обновлено**: документация актуализирована для отражения текущего состояния на 2026-02-05, включая полную реализацию семантической сети с событиями (WorldEvent), утверждениями (Claim), разрешением конфликтов (ConflictSet), документами (DocFragment) и качественной оценкой.

## Архитектурная роль

World определяет семантическую модель для представления знаний и эволюции мира в Policy Engine:

```
Raw Data → Events → Claims → Conflicts → Resolution → Knowledge Base
     ↓         ↓         ↓         ↓           ↓            ↓
 Provenance  Quality   Trust    Validation  Consensus   Queryable
```

### Положение в системе

- **Входящие зависимости**: Citations, Kernel (base models)
- **Исходящие зависимости**: Core (использует для семантической сети), Fabric (запросы к world данным)
- **Принцип**: "World как семантическая сеть" - унифицированная модель знаний

## Структура модуля

```
world/
├── __init__.py          # Экспорт всех world компонентов
├── abi.py               # ABI интерфейсы и типы (EdgeKind, NodeKind)
├── claim.py             # Модель утверждений (Claim)
├── conflict.py          # Разрешение конфликтов (ConflictSet, ConflictResolution)
├── doc.py               # Документные фрагменты (DocFragment, DocMeta)
├── event.py             # События мира (WorldEvent, ProvActivity)
├── ids.py               # Генерация детерминированных ID для world объектов
├── predicates.py        # Предикаты world графа
├── quality.py           # Качество и валидация (QualityReport, QualityIssue)
└── trust.py             # Оценки доверия (TrustAssessment, TrustTier)
```

## Основные компоненты

### 1. События мира (`event.py`)

#### WorldEvent - события в мире

```python
from polisyos.ir.world import WorldEvent, EventKind, ProvActivity, ProvAgent

class WorldEvent(KernelModel):
    """Событие в семантической модели мира."""

    schema_version: str
    event_id: str
    event_kind: EventKind
    timestamp: datetime
    activity: ProvActivity
    agent: ProvAgent
    target_objects: list[WorldObjectRef]
    generated_objects: list[WorldObjectRef]
    invalidated_objects: list[WorldObjectRef]
    metadata: dict[str, Any]
```

**Типы событий (EventKind):**
- `FETCH_DOC`: Получение документа
- `NORMALIZE_DOC`: Нормализация документа
- `EXTRACT_CLAIMS`: Извлечение утверждений
- `DETECT_CONFLICTS`: Обнаружение конфликтов
- `RESOLVE_CONFLICTS`: Разрешение конфликтов
- `SIMULATE`: Симуляция
- `VALIDATE`: Валидация

#### Provenance tracking

```python
# Деятельность (что произошло)
activity = ProvActivity(
    activity_type=ProvActivityType.EXTRACT_CLAIMS,
    description="Extracted claims from regulatory document"
)

# Агент (кто выполнил)
agent = ProvAgent(
    agent_type=ProvAgentType.MODEL,
    agent_id="gpt-4-extractor",
    name="GPT-4 Claim Extractor"
)

# Событие
event = WorldEvent(
    event_id="event_001",
    event_kind=EventKind.EXTRACT_CLAIMS,
    timestamp=datetime.now(),
    activity=activity,
    agent=agent,
    target_objects=[doc_ref],
    generated_objects=[claim_refs],
    invalidated_objects=[],
    metadata={"confidence": 0.85}
)
```

### 2. Утверждения (`claim.py`)

#### Claim - утверждения о состоянии мира

```python
from polisyos.ir.world import Claim, ClaimSourceKind

class Claim(KernelModel):
    """Утверждение о факте или состоянии мира."""

    schema_version: str
    claim_id: str
    predicate_id: str              # Предикат (has_income, located_in, etc.)
    subject_id: str | None         # Субъект утверждения
    subject_text: str | None       # Текстовое описание субъекта
    value_text: str               # Текстовое значение
    value_decimal: Decimal | None # Числовое значение
    unit_id: str | None           # Единица измерения
    confidence: Decimal           # Уверенность (0-1)
    source_kind: ClaimSourceKind  # Тип источника
    citations: list[CitationRef]  # Ссылки на источники
    source_artifacts: list[str]   # ID артефактов-источников
    jurisdiction: str | None      # Юрисдикция
    valid_from: datetime | None   # Время начала действия
    valid_to: datetime | None     # Время окончания действия
```

**Типы источников (ClaimSourceKind):**
- `DOC`: Документы
- `DATASET`: Наборы данных
- `SIMULATION`: Результаты симуляции
- `EXPERT`: Экспертные оценки
- `DERIVED`: Выводные утверждения

#### Примеры утверждений

```python
# Факт о доходе
income_claim = Claim(
    claim_id="income_john_2024",
    predicate_id="has_income",
    subject_id="person_john",
    value_decimal=Decimal("50000"),
    unit_id="uah",
    confidence=Decimal("0.95"),
    source_kind=ClaimSourceKind.DOC,
    citations=[tax_return_citation],
    valid_from=datetime(2024, 1, 1),
    valid_to=datetime(2024, 12, 31)
)

# Факт о локации
location_claim = Claim(
    claim_id="company_loc",
    predicate_id="located_in",
    subject_id="company_xyz",
    value_text="Kyiv, Ukraine",
    confidence=Decimal("1.0"),
    source_kind=ClaimSourceKind.DERIVED
)
```

### 3. Разрешение конфликтов (`conflict.py`)

#### ConflictSet - набор конфликтующих утверждений

```python
from polisyos.ir.world import ConflictSet, ConflictKind, ConflictResolution

class ConflictSet(KernelModel):
    """Набор конфликтующих утверждений."""

    schema_version: str
    conflict_set_id: str
    conflict_kind: ConflictKind
    claim_ids: list[str]           # ID конфликтующих утверждений
    key: str                       # Ключ конфликта (предикат + субъект)
    resolution: ConflictResolution | None
    metadata: dict[str, Any]
```

**Типы конфликтов (ConflictKind):**
- `VALUE_MISMATCH`: Разные значения для одного факта
- `UNIT_MISMATCH`: Разные единицы измерения
- `DEFINITION_MISMATCH`: Разные определения понятий
- `TEMPORAL_MISMATCH`: Временные несоответствия
- `DUPLICATE`: Дублирующиеся утверждения

#### ConflictResolution - разрешение конфликта

```python
class ConflictResolution(KernelModel):
    """Результат разрешения конфликта."""

    resolution_id: str
    resolved_claim_ids: list[str]      # ID разрешенных утверждений
    rejected_claim_ids: list[str]      # ID отклоненных утверждений
    consensus_claim: Claim | None      # Согласованное утверждение
    resolution_method: str            # Метод разрешения
    confidence: Decimal               # Уверенность в разрешении
    resolver_agent: ProvAgent         # Агент разрешивший конфликт
    timestamp: datetime
```

### 4. Документные фрагменты (`doc.py`)

#### DocFragment - фрагменты документов

```python
from polisyos.ir.world import DocFragment, DocMeta

class DocFragment(KernelModel):
    """Фрагмент документа с метаданными."""

    schema_version: str
    fragment_id: str
    doc_source_id: str
    doc_version_id: str
    content: str
    content_type: str               # "text", "html", "markdown", etc.
    locator: FragmentLocator       # Точное расположение в документе
    metadata: dict[str, Any]
    extracted_at: datetime
    quality_score: Decimal | None
```

#### DocMeta - метаданные документа

```python
class DocMeta(KernelModel):
    """Метаданные документа-источника."""

    schema_version: str
    doc_source_id: str
    title: str | None
    authors: list[str]
    publication_date: date | None
    jurisdiction: str | None
    doc_type: str                   # "law", "regulation", "report", etc.
    language: str
    source_url: str | None
    metadata: dict[str, Any]
```

### 5. Качество и валидация (`quality.py`)

#### QualityReport - отчеты о качестве

```python
from polisyos.ir.world import QualityReport, QualityIssue, QualityIssueSeverity

class QualityReport(KernelModel):
    """Отчет о качестве данных или процесса."""

    schema_version: str
    report_id: str
    scope: QualityScope
    target_object_id: str
    issues: list[QualityIssue]
    overall_score: Decimal | None
    generated_at: datetime
    assessor_agent: ProvAgent
```

#### QualityIssue - проблемы качества

```python
class QualityIssue(KernelModel):
    """Конкретная проблема качества."""

    issue_id: str
    severity: QualityIssueSeverity
    category: str
    description: str
    suggested_fix: str | None
    metadata: dict[str, Any]
```

### 6. Оценки доверия (`trust.py`)

#### TrustAssessment - оценки доверия

```python
from polisyos.ir.world import TrustAssessment, TrustTier

class TrustAssessment(KernelModel):
    """Оценка доверия к источнику или утверждению."""

    schema_version: str
    assessment_id: str
    target_id: str                  # ID объекта оценки
    tier: TrustTier                 # Уровень доверия
    score: Decimal                  # Числовая оценка (0-1)
    factors: list[str]              # Факторы влияющие на доверие
    assessed_by: ProvAgent
    assessed_at: datetime
    valid_until: datetime | None
```

**Уровни доверия (TrustTier):**
- `VERIFIED`: Проверено
- `HIGH`: Высокий уровень доверия
- `MEDIUM`: Средний уровень доверия
- `LOW`: Низкий уровень доверия
- `UNTRUSTED`: Недоверенный

### 7. Детерминированные ID (`ids.py`)

#### Генерация стабильных идентификаторов

```python
from polisyos.ir.world import (
    artifact_id_to_world_id,
    claim_id_from_payload,
    conflict_set_id_from_key,
    doc_fragment_id,
    world_event_id_from_payload
)

# ID утверждения на основе содержимого
claim_id = claim_id_from_payload({
    "predicate_id": "has_income",
    "subject_id": "person_john",
    "value_decimal": "50000"
})

# ID события на основе payload
event_id = world_event_id_from_payload(event_data)

# ID набора конфликтов
conflict_id = conflict_set_id_from_key("has_income:person_john")
```

### 8. ABI и типы (`abi.py`)

#### EdgeKind и NodeKind - типы элементов графа

```python
from polisyos.ir.world import EdgeKind, NodeKind, RESERVED_WORLD_PREFIXES_V1

class NodeKind(str, Enum):
    CLAIM = "claim"
    EVENT = "event"
    DOC_FRAGMENT = "doc_fragment"
    CONFLICT_SET = "conflict_set"
    AGENT = "agent"
    ARTIFACT = "artifact"

class EdgeKind(str, Enum):
    DERIVED_FROM = "derived_from"
    CONFLICTS_WITH = "conflicts_with"
    RESOLVES = "resolves"
    CITED_BY = "cited_by"
    GENERATED_BY = "generated_by"
```

## Использование в коде

### Создание семантической сети

```python
from polisyos.ir.world import Claim, WorldEvent, ConflictSet
from polisyos.ir.world.ids import claim_id_from_payload

# Создание утверждений
claims = [
    Claim(
        claim_id=claim_id_from_payload({
            "predicate_id": "has_income",
            "subject_id": "person_john",
            "value_decimal": "50000"
        }),
        predicate_id="has_income",
        subject_id="person_john",
        value_decimal=Decimal("50000"),
        unit_id="uah",
        confidence=Decimal("0.95"),
        source_kind=ClaimSourceKind.DOC,
        citations=[citation]
    )
]

# Регистрация события извлечения
extraction_event = WorldEvent(
    event_id=world_event_id_from_payload(event_data),
    event_kind=EventKind.EXTRACT_CLAIMS,
    timestamp=datetime.now(),
    activity=ProvActivity(...),
    agent=ProvAgent(...),
    generated_objects=[claim.claim_id for claim in claims]
)

# Обнаружение конфликтов
conflicts = detect_conflicts(claims)
if conflicts:
    conflict_set = ConflictSet(
        conflict_set_id=conflict_set_id_from_key(f"{conflicts[0].key}"),
        conflict_kind=ConflictKind.VALUE_MISMATCH,
        claim_ids=[c.claim_id for c in conflicts],
        key=conflicts[0].key
    )
```

### Оценка качества

```python
from polisyos.ir.world import QualityReport, QualityIssue, QualityIssueSeverity

# Создание отчета о качестве
quality_report = QualityReport(
    report_id=quality_report_id_from_payload(report_data),
    scope=QualityScope.CLAIM_SET,
    target_object_id=claim_set_id,
    issues=[
        QualityIssue(
            issue_id="low_confidence",
            severity=QualityIssueSeverity.WARNING,
            category="confidence",
            description="Some claims have low confidence scores",
            suggested_fix="Review and validate low-confidence claims"
        )
    ],
    overall_score=Decimal("0.85"),
    generated_at=datetime.now(),
    assessor_agent=assessment_agent
)
```

### Оценка доверия

```python
from polisyos.ir.world import TrustAssessment, TrustTier

# Оценка доверия к источнику
trust_assessment = TrustAssessment(
    assessment_id=trust_assessment_id_from_payload(assessment_data),
    target_id=source_id,
    tier=TrustTier.HIGH,
    score=Decimal("0.92"),
    factors=[
        "official_government_source",
        "recent_publication_date",
        "peer_reviewed"
    ],
    assessed_by=assessment_agent,
    assessed_at=datetime.now(),
    valid_until=datetime.now() + timedelta(days=365)
)
```

## Архитектурные принципы

### Design Patterns

1. **Semantic Web**: World как граф знаний с типизированными отношениями
2. **Provenance Tracking**: Полное отслеживание происхождения данных
3. **Conflict Resolution**: Структурированное разрешение противоречий
4. **Quality Assurance**: Многоуровневая оценка качества и доверия
5. **Deterministic IDs**: Стабильные идентификаторы для reproducible систем

### Качество и надежность

- **Type Safety**: Полная типизация через Pydantic модели
- **Immutable Models**: Все модели неизменяемы после создания
- **Comprehensive Validation**: Строгая валидация всех связей и ссылок
- **Provenance Integrity**: Гарантия целостности цепочек происхождения

### Производительность

- **Efficient Graph Operations**: Оптимизированные операции с графом знаний
- **Lazy Loading**: Загрузка данных по требованию
- **Memory Efficient**: Минимальный overhead на метаданные provenance

## Расширяемость

### Добавление новых типов событий

```python
class EventKind(str, Enum):
    # Существующие...
    CUSTOM_ANALYSIS = "custom_analysis"
    EXTERNAL_VALIDATION = "external_validation"
```

### Расширение модели качества

```python
class CustomQualityIssue(QualityIssue):
    """Расширение с кастомными полями."""

    custom_metric: Decimal
    domain_specific_score: Decimal
```

## Тестирование

### Тестовые сценарии

```bash
# Unit-тесты World компонентов
pytest tests/unit/test_ir_world_*.py

# Contract-тесты семантической модели
pytest tests/contract/test_ir_world_semantics.py

# Интеграционные тесты
pytest tests/integration/test_world_core.py
pytest tests/integration/test_world_fabric.py
```

**Ключевые тестовые сценарии:**
- Создание и валидация всех типов объектов
- Генерация детерминированных ID
- Разрешение конфликтов
- Оценка качества и доверия
- Provenance tracking через цепочки событий
- Сериализация/десериализация без потерь

## Связанные компоненты

### Зависимости

**Входящие:**
- **Citations**: Ссылки на источники в утверждениях
- **Kernel**: Базовые модели и типы

**Исходящие:**
- **Core**: Использует World для построения семантической сети знаний
- **Fabric**: Запросы к world данным для анализа
- **Scientist**: Анализ world состояния для генерации политик

### Архитектурные контракты

```
Raw Data → World Events → Claims → Conflicts → Resolution → Knowledge Graph
     ↓           ↓           ↓         ↓           ↓            ↓
  Provenance  Quality    Trust   Validation  Consensus     Queryable
     ↓           ↓           ↓         ↓           ↓            ↓
   Core       Fabric    Scientist Foundry    Runtime      Analysis
```

**World в системе:**
```
Input:  Raw Data + Events
Process: Claim Extraction → Conflict Detection → Resolution
Output: Knowledge Graph + Quality Reports + Trust Assessments
```

---

**См. также:**
- [IR README](../README.md) - общая архитектура IR
- [Core](../../core/) - использование World для семантической сети
- [Fabric](../../fabric/) - запросы к world данным
- [Citations](../citations.py) - система цитирования