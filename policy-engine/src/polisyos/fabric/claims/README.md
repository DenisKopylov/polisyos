# Claims Processing System

**Claims Processing System** — это комплексная система для извлечения, нормализации и разрешения конфликтов claims из документов. Система обеспечивает структурированную обработку текстовых данных с извлечением фактов, разрешением противоречий и построением надежной базы знаний для симуляций экономической политики.

## Архитектурная роль

Claims Processing System играет ключевую роль в обработке неструктурированных данных:

### Положение в экосистеме Fabric

```
Documents → Claims Extraction → Normalization → Conflict Resolution → Fact Log
     ↓              ↓                     ↓              ↓              ↓
   docs/         backends/           canonicalize/   conflicts/      persist/
```

### Ключевые обязанности

1. **Document Claims Extraction**: Извлечение фактов из текстовых документов различных форматов
2. **Claims Normalization**: Приведение claims к каноническому формату с унификацией единиц измерения
3. **Conflict Detection**: Обнаружение противоречий между claims из разных источников
4. **Conflict Resolution**: Автоматическое разрешение конфликтов с использованием политик и confidence scoring
5. **Citation Management**: Связывание claims с источниками и контекстом для traceability
6. **Evidence Generation**: Создание криптографически verifiable доказательств происхождения claims

## Структура модуля

```
claims/
├── __init__.py              # Экспорт основного API
├── types.py                 # Основные типы данных (ClaimCandidate, ExtractResult, etc.)
├── errors.py                # Специфичные ошибки обработки claims
├── extraction.py            # Основной pipeline извлечения claims
├── extractor_registry.py    # Реестр экстракторов claims
├── normalize.py             # Нормализация claims
├── canonicalize.py          # Канонизация идентификаторов и единиц измерения
├── citations.py             # Управление цитатами и ссылками
├── persist.py               # Сохранение claims в Fact Log
├── backends/                # Backend реализации экстракторов
│   ├── __init__.py
│   ├── explicit_lines_v1.py # Явные линии claims (claim: predicate = value)
│   ├── lex_norm_regex_v1.py # Лексическая нормализация с regex
│   └── regex_numeric_v1.py  # Regex для числовых значений
└── conflicts/               # Система разрешения конфликтов
    ├── __init__.py
    ├── types.py             # Типы для конфликтов и разрешения
    ├── detect.py            # Обнаружение конфликтов
    ├── key.py               # Генерация ключей для группировки конфликтов
    ├── policies.py          # Политики разрешения конфликтов
    ├── resolve.py           # Логика разрешения конфликтов
    ├── score_claims.py      # Оценка claims для ранжирования
    └── score_docs.py        # Оценка документов для разрешения
```

## Ключевые компоненты

### 1. Claims Extraction Pipeline (`extraction.py`)

Основной pipeline для извлечения claims из документов:

#### Процесс извлечения
1. **Document Preparation**: Загрузка и нормализация документа
2. **Chunking**: Разбиение документа на семантически связанные фрагменты
3. **Backend Selection**: Выбор подходящего экстрактора на основе типа документа
4. **Claims Extraction**: Извлечение candidates из каждого chunk
5. **Evidence Generation**: Создание доказательств происхождения

#### Основные функции
```python
from polisyos.fabric.claims import extract_claims_from_doc, ClaimExtractOptions

# Извлечение claims из документа
result = extract_claims_from_doc(
    doc_meta=doc_meta,
    options=ClaimExtractOptions(
        extract_mode="structure_then_chunks",
        max_claims_per_chunk=10,
        build_evidence=True
    )
)

print(f"Извлечено {len(result.claim_ids)} claims")
```

### 2. Backend Extractors (`backends/`)

Плагинируемая система экстракторов для различных форматов claims:

#### Explicit Lines Backend (`explicit_lines_v1.py`)
Извлекает claims из явных деклараций в формате:
```
claim: GDP(current_year) = 25000000000 [USD]
claim: unemployment_rate = 5.2 [percent]
```

#### Lexical Normalization Backend (`lex_norm_regex_v1.py`)
Использует регулярные выражения с лексической нормализацией для извлечения структурированных данных.

#### Regex Numeric Backend (`regex_numeric_v1.py`)
Специализирован на извлечении числовых значений с единицами измерения.

#### Регистрация новых backends
```python
from polisyos.fabric.claims.extractor_registry import ExtractorRegistry

registry = ExtractorRegistry.get_instance()
registry.register("custom_extractor", custom_extract_function)
```

### 3. Claims Normalization (`normalize.py`, `canonicalize.py`)

Приведение извлеченных claims к каноническому формату:

#### Нормализация включает:
- **Unit Canonicalization**: Приведение единиц измерения к стандарту (USD, percent, etc.)
- **ID Canonicalization**: Нормализация идентификаторов агентов и предикатов
- **Value Parsing**: Парсинг числовых значений с поддержкой Decimal
- **Predicate Normalization**: Унификация имен предикатов

```python
from polisyos.fabric.claims import normalize_claims, ClaimNormalizeOptions

# Нормализация набора claims
normalized_result = normalize_claims(
    input_claims=extract_result,
    options=ClaimNormalizeOptions(
        normalize_units=True,
        parse_numeric=True,
        drop_invalid=True
    )
)
```

### 4. Conflict Detection & Resolution (`conflicts/`)

Система обнаружения и разрешения противоречий между claims:

#### Типы конфликтов
- **Direct Conflicts**: Прямая противоречия значений для одного предиката
- **Temporal Conflicts**: Противоречия в разные моменты времени
- **Source Conflicts**: Противоречия между разными источниками

#### Процесс разрешения
1. **Grouping**: Группировка claims по conflict keys
2. **Detection**: Обнаружение конфликтов в каждой группе
3. **Scoring**: Оценка confidence для каждого claim
4. **Resolution**: Применение политик для выбора наиболее надежного claim

#### Политики разрешения
```python
from polisyos.fabric.claims.conflicts import (
    detect_conflicts, resolve_conflicts, ConflictPolicy
)

# Обнаружение конфликтов
conflicts = detect_conflicts(claims_list)

# Разрешение с политикой majority vote
resolved = resolve_conflicts(
    conflicts,
    policy=ConflictPolicy.MAJORITY_VOTE
)
```

### 5. Citation Management (`citations.py`)

Система связывания claims с источниками и контекстом:

#### Функциональность
- **Fragment Linking**: Связь с конкретными фрагментами документа
- **Context Preservation**: Сохранение окружающего контекста
- **Source Attribution**: Атрибуция к документам и авторам
- **Temporal Tracking**: Отслеживание времени извлечения

### 6. Persistence (`persist.py`)

Сохранение обработанных claims в Fact Log:

#### Процесс сохранения
1. **Fact Generation**: Преобразование claims в facts
2. **Provenance Tracking**: Создание provenance записей
3. **Evidence Bundles**: Генерация доказательств
4. **Segment Creation**: Запись в Fact Log сегменты

## Основные типы данных

### ClaimCandidate
```python
@dataclass(frozen=True)
class ClaimCandidate:
    predicate_id: str              # Предикат (gdp, unemployment_rate)
    value_text: str               # Текстовое значение
    citation_fragment_id: str     # Ссылка на источник
    subject_id: str | None        # ID субъекта (опционально)
    subject_text: str | None      # Текст субъекта (опционально)
    value_decimal: Decimal | None # Числовое значение
    unit_id: str | None           # Единица измерения
    confidence: Decimal | None    # Уровень уверенности
    qualifiers: dict[str, Any]    # Дополнительные квалификаторы
    props: dict[str, Any]         # Расширенные свойства
```

### ExtractResult / NormalizeResult
```python
@dataclass(frozen=True)
class ClaimExtractResult:
    doc_source_id: str
    doc_version_id: str
    claim_ids: list[str]
    world_event_id: str
    evidence_ref: str | None
    world_segment_manifest: FactSegmentManifest
```

## Интеграция с системой

### Связь с Document Processing (`docs/`)

Claims Processing получает предобработанные документы от `docs/` модуля:

```python
from polisyos.fabric.docs import process_document
from polisyos.fabric.claims import extract_claims_from_doc

# Обработка документа
doc_result = process_document(pdf_file)

# Извлечение claims
claims_result = extract_claims_from_doc(doc_result.doc_meta)
```

### Связь с Fact Log

Обработанные claims сохраняются в Fact Log для дальнейшего использования:

```python
from polisyos.fabric.claims.persist import persist_claims_to_fact_log

# Сохранение claims в Fact Log
segment_manifest = persist_claims_to_fact_log(
    normalized_claims=normalized_result,
    fact_dir=Path("data/facts")
)
```

### Связь с World Model (`world/`)

Claims интегрируются в модель мира через материализацию:

```python
from polisyos.fabric.world.materialize import materialize_claims

# Материализация claims в реляционные таблицы
materialize_claims(
    claims=normalized_result,
    target_db=simulation_db
)
```

### Связь с Evidence System

Каждый шаг обработки claims сопровождается evidence:

```python
# Evidence bundle включает:
# - Исходный документ
# - Параметры извлечения
# - Результаты нормализации
# - Решения по конфликтам
evidence_bundle = build_evidence_bundle(
    sources=[doc_artifact_ref],
    transforms=[extract_step, normalize_step, resolve_step]
)
```

## Производительность и масштабируемость

### Оптимизации

**Backend Selection:**
- Автоматический выбор оптимального экстрактора
- Кэширование результатов для повторяющихся документов
- Параллельная обработка chunks

**Memory Management:**
- Streaming обработка больших документов
- Chunk-based processing для контроля памяти
- Lazy loading нормализованных данных

**Conflict Resolution:**
- Efficient grouping algorithms
- Confidence-based early termination
- Batch processing для больших наборов claims

### Масштабирование

**Текущее состояние:**
- Поддержка документов до 100MB
- Обработка до 10,000 claims в одном pipeline
- Conflict resolution для 1,000+ конфликтов

**Расширения:**
- Distributed processing для очень больших документов
- GPU acceleration для regex matching
- ML-based confidence scoring

## Тестирование

### Unit Tests
```bash
# Тесты основных компонентов
pytest tests/fabric/claims/test_extraction.py
pytest tests/fabric/claims/test_normalize.py
pytest tests/fabric/claims/test_conflicts.py
```

### Integration Tests
```bash
# Полный pipeline
pytest tests/integration/test_claims_processing.py

# С документами
pytest tests/integration/test_claims_docs_integration.py
```

### Benchmarking
```bash
# Производительность извлечения
pytest tests/benchmarks/test_claims_extraction_perf.py

# Масштабирование conflict resolution
pytest tests/benchmarks/test_conflicts_resolution_perf.py
```

## Безопасность и приватность

### Data Protection
- **PII Detection**: Автоматическое обнаружение персональных данных
- **Access Control**: Уровни доступа к claims на основе источников
- **Audit Logging**: Полное логирование всех операций

### Cryptographic Integrity
- **Hash-based IDs**: Детерминированные идентификаторы claims
- **Evidence Chains**: Криптографическая верификация происхождения
- **Tamper Detection**: Обнаружение изменений в обработанных данных

## Примеры использования

### Полный pipeline обработки документа

```python
from pathlib import Path
from polisyos.fabric.docs import process_document
from polisyos.fabric.claims import (
    extract_claims_from_doc, normalize_claims, detect_conflicts, resolve_conflicts
)
from polisyos.fabric.claims.persist import persist_claims_to_fact_log

# 1. Обработка документа
doc_result = process_document(Path("economic_report.pdf"))

# 2. Извлечение claims
extract_result = extract_claims_from_doc(
    doc_meta=doc_result.doc_meta,
    options=ClaimExtractOptions(max_claims_per_chunk=50)
)

# 3. Нормализация
normalize_result = normalize_claims(
    input_claims=extract_result,
    options=ClaimNormalizeOptions(normalize_units=True)
)

# 4. Разрешение конфликтов
conflicts = detect_conflicts(normalize_result.claim_ids)
resolved_result = resolve_conflicts(conflicts, policy="majority_vote")

# 5. Сохранение в Fact Log
segment = persist_claims_to_fact_log(
    claims=resolved_result.resolved_claims,
    fact_dir=Path("data/facts")
)

print(f"Обработано {len(resolved_result.resolved_claims)} claims")
print(f"Создан сегмент Fact Log: {segment.segment_id}")
```

### Кастомный экстрактор

```python
from polisyos.fabric.claims.backends import BaseExtractor
from polisyos.fabric.claims.extractor_registry import ExtractorRegistry

class CustomExtractor(BaseExtractor):
    def extract(self, ctx, meta, normalized_text, options):
        # Кастомная логика извлечения claims
        claims = []
        # ... извлечение ...
        return claims

# Регистрация экстрактора
registry = ExtractorRegistry.get_instance()
registry.register("custom", CustomExtractor())
```

### Анализ качества claims

```python
from polisyos.fabric.claims.quality import assess_claims_quality

# Оценка качества извлеченных claims
quality_report = assess_claims_quality(
    claims=extract_result.claim_ids,
    source_document=doc_result.doc_meta
)

print(f"Средняя confidence: {quality_report.avg_confidence}")
print(f"Claims с низкой уверенностью: {len(quality_report.low_confidence_claims)}")
```

## Заключение

**Claims Processing System** обеспечивает надежное извлечение структурированной информации из неструктурированных документов, разрешение противоречий и интеграцию в систему симуляций экономической политики. Система поддерживает расширяемую архитектуру с плагинируемыми экстракторами, обеспечивает полную traceability через evidence system и масштабируется для обработки больших объемов документов.