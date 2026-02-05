# Document Processing System

**Document Processing System** — это многоформатная система обработки документов для извлечения структурированной информации из PDF, HTML и plain text файлов. Система обеспечивает полный pipeline от загрузки сырых документов до семантического chunking с сохранением provenance и evidence tracking.

## Архитектурная роль

Document Processing System является фундаментом для обработки неструктурированных данных в Fabric:

### Положение в экосистеме Fabric

```
Raw Documents → Ingestion → Normalization → Structure Analysis → Chunking → Claims Extraction
      ↓              ↓              ↓              ↓              ↓              ↓
   ingestion.py   normalize.py   structure.py   chunking.py   claims/       backends/
```

### Ключевые обязанности

1. **Multi-format Document Ingestion**: Загрузка и первичная обработка документов различных форматов
2. **Text Normalization**: Приведение документов к единому текстовому формату с кодировкой и очисткой
3. **Structure Analysis**: Извлечение логической структуры (заголовки, разделы, таблицы)
4. **Intelligent Chunking**: Семантическое разбиение документов на связанные фрагменты
5. **Metadata Management**: Управление метаданными документов и provenance tracking
6. **Evidence Generation**: Создание криптографически verifiable доказательств обработки

## Структура модуля

```
docs/
├── __init__.py              # Экспорт основного API
├── types.py                 # Основные типы данных (DocSourceSpec, *Result, *Options)
├── errors.py                # Специфичные ошибки обработки документов
├── ingestion.py             # Загрузка и первичная обработка документов
├── normalize.py             # Нормализация текста и кодировки
├── structure.py             # Анализ логической структуры документов
├── chunking.py              # Семантическое chunking документов
├── backends/                # Backend реализации для разных форматов
│   ├── __init__.py
│   ├── pdf.py               # Обработка PDF документов
│   ├── text_html.py         # Обработка HTML документов
│   └── text_plain.py        # Обработка plain text документов
```

## Ключевые компоненты

### 1. Document Ingestion (`ingestion.py`)

Первичная загрузка и обработка документов с валидацией:

#### Процесс ingestion
1. **Source Validation**: Проверка спецификации источника документа
2. **Format Detection**: Автоматическое определение MIME типа
3. **Size Validation**: Проверка ограничений на размер файла
4. **CAS Storage**: Сохранение сырых данных в Content Addressable Storage
5. **Metadata Generation**: Создание метаданных документа

#### Основные функции
```python
from polisyos.fabric.docs import ingest_doc_bytes, DocIngestOptions, DocSourceSpec

# Спецификация источника
source_spec = DocSourceSpec(
    canonical_url="https://www.bea.gov/economic_report.pdf",
    license="public-domain",
    retrieved_at=datetime.now(),
    jurisdiction="US",
    language="en",
    title="Economic Report 2024",
    publisher="Bureau of Economic Analysis"
)

# Загрузка документа
result = ingest_doc_bytes(
    doc_bytes=pdf_content,
    source_spec=source_spec,
    options=DocIngestOptions(enforce_max_bytes=50 * 1024 * 1024)  # 50MB limit
)

print(f"Document ingested: {result.doc_version_id}")
print(f"CAS reference: {result.raw_ref}")
```

### 2. Text Normalization (`normalize.py`)

Приведение документов к единому текстовому формату:

#### Поддерживаемые форматы
- **PDF**: Извлечение текста с сохранением структуры (опционально, требует зависимостей)
- **HTML**: Извлечение видимого текста с удалением разметки
- **Plain Text**: Нормализация кодировки и форматирования

#### Нормализация включает:
- **Encoding Detection**: Автоматическое определение кодировки (UTF-8, Latin-1, etc.)
- **Newline Normalization**: Приведение различных типов переводов строк
- **Whitespace Handling**: Опциональная очистка trailing whitespace
- **Content Validation**: Проверка на readable content

```python
from polisyos.fabric.docs import normalize_doc, DocNormalizeOptions

# Нормализация документа
normalize_result = normalize_doc(
    ingest_result=result,
    options=DocNormalizeOptions(
        encoding_order=["utf-8", "utf-8-sig", "latin-1"],
        normalize_newlines=True,
        strip_trailing_whitespace=True,
        html_extract_mode="visible_text_v1"
    )
)

print(f"Normalized text length: {len(normalize_result)}")
```

### 3. Structure Analysis (`structure.py`)

Извлечение логической структуры документа:

#### Алгоритмы анализа
- **Anchors Algorithm**: Использование заголовков и структурных элементов как anchors
- **Heading Detection**: Автоматическое обнаружение иерархии заголовков
- **Section Extraction**: Выделение семантически связанных разделов

#### Возможности
- **Hierarchical Structure**: Построение иерархии разделов документа
- **Anchor Points**: Создание точек привязки для навигации
- **Content Classification**: Классификация типа контента в разделах
- **Metadata Extraction**: Извлечение метаданных из структуры

```python
from polisyos.fabric.docs import structure_doc, DocStructureOptions

# Анализ структуры
structure_result = structure_doc(
    normalize_result=normalize_result,
    options=DocStructureOptions(
        algorithm="anchors_v1",
        max_heading_len=160,
        min_section_chars=200,
        include_full_document_anchor=True
    )
)

print(f"Found {len(structure_result.fragment_ids)} structural fragments")
```

### 4. Intelligent Chunking (`chunking.py`)

Семантическое разбиение документов на связанные фрагменты:

#### Алгоритмы chunking
- **Character-based**: Фиксированный размер chunks с overlap
- **Paragraph-based**: Разбиение по естественным границам параграфов
- **Structure-aware**: Учет логической структуры документа

#### Параметры chunking
- **Chunk Size**: Размер chunks в символах
- **Overlap**: Перекрытие между chunks для контекста
- **Boundary Detection**: Автоматическое обнаружение границ
- **Minimum Size**: Минимальный размер chunk

```python
from polisyos.fabric.docs import chunk_doc, DocChunkOptions

# Семантическое chunking
chunk_result = chunk_doc(
    structure_result=structure_result,
    options=DocChunkOptions(
        algorithm="char_chunks_v1",
        chunk_size_chars=2000,
        overlap_chars=200,
        min_chunk_chars=200,
        boundary="paragraph"
    )
)

print(f"Created {len(chunk_result.chunk_fragment_ids)} chunks")
```

### 5. Backend Processors (`backends/`)

Специализированные процессоры для разных форматов документов:

#### PDF Backend (`pdf.py`)
- **Text Extraction**: Извлечение текста с layout preservation
- **Table Detection**: Обнаружение и извлечение таблиц
- **Image OCR**: Опциональная OCR обработка изображений
- **Metadata Extraction**: Извлечение PDF метаданных

#### HTML Backend (`text_html.py`)
- **Visible Text Extraction**: Извлечение только видимого текста
- **Structure Preservation**: Сохранение иерархии заголовков
- **Link Extraction**: Извлечение ссылок и навигации
- **Content Filtering**: Удаление boilerplate контента

#### Plain Text Backend (`text_plain.py`)
- **Encoding Handling**: Корректная обработка различных кодировок
- **Format Detection**: Определение типа plain text (markdown, structured, etc.)
- **Line Processing**: Обработка по строкам с сохранением форматирования

### 6. Metadata & Provenance

Все этапы обработки сопровождаются provenance tracking:

#### Provenance Integration
- **World Events**: Каждый шаг создает world event
- **Fact Segments**: Результаты сохраняются в immutable facts
- **Evidence Bundles**: Криптографические доказательства обработки
- **CAS References**: Все артефакты хранятся в Content Addressable Storage

## Основные типы данных

### DocSourceSpec
```python
@dataclass(frozen=True)
class DocSourceSpec:
    canonical_url: str | None = None      # Канонический URL документа
    official_id: str | None = None         # Официальный ID
    source_locator: str | None = None     # Локатор источника
    license: str | None = None            # Лицензия документа
    retrieved_at: datetime | None = None  # Время получения
    jurisdiction: str | None = None       # Юрисдикция
    language: str | None = None           # Язык документа
    source_type: str | None = None        # Тип источника
    title: str | None = None              # Заголовок
    publisher: str | None = None          # Издатель
```

### Pipeline Results
```python
@dataclass(frozen=True)
class DocIngestResult:
    doc_source_id: str                    # ID источника документа
    doc_version_id: str                   # ID версии документа
    raw_ref: str                         # CAS ссылка на сырые данные
    normalized_ref: str | None           # CAS ссылка на нормализованный текст
    structure_ref: str | None            # CAS ссылка на структуру
    chunks_ref: str | None               # CAS ссылка на chunks
    doc_meta_artifact_id: str            # ID метаданных документа
    world_event_id: str                  # ID world event
    world_event_artifact_id: str         # CAS ссылка на world event
    world_segment_manifest: FactSegmentManifest  # Манифест сегмента
```

## Интеграция с системой

### Связь с Claims Processing (`claims/`)

Document processing предоставляет предобработанные документы для извлечения claims:

```python
from polisyos.fabric.docs import ingest_doc_bytes, normalize_doc, chunk_doc
from polisyos.fabric.claims import extract_claims_from_doc

# Полный pipeline: документ → chunks → claims
ingest_result = ingest_doc_bytes(pdf_bytes, source_spec)
normalize_result = normalize_doc(ingest_result)
chunk_result = chunk_doc(normalize_result)

claims_result = extract_claims_from_doc(
    doc_meta=chunk_result.doc_meta_artifact_id,
    normalized_text=normalize_result,
    chunks=chunk_result.chunks
)
```

### Связь с World Model (`world/`)

Обработанные документы интегрируются в модель мира:

```python
from polisyos.fabric.world.materialize import materialize_doc_facts

# Материализация фактов документа в модель мира
materialize_doc_facts(
    doc_result=chunk_result,
    target_db=simulation_db
)
```

### Связь с Evidence System

Каждый шаг обработки создает evidence:

```python
from polisyos.fabric.evidence import build_evidence_bundle

# Evidence bundle для document processing
evidence = build_evidence_bundle(
    sources=[WorldObjectRef(kind="doc.source", id=doc_source_id)],
    transforms=[
        EvidenceStep(id="ingest", description="Document ingestion"),
        EvidenceStep(id="normalize", description="Text normalization"),
        EvidenceStep(id="chunk", description="Document chunking")
    ],
    trust_policy_id="doc_processing_trust"
)
```

## Производительность и масштабируемость

### Оптимизации

**Memory Management:**
- Streaming обработка больших документов
- Chunk-based processing для контроля памяти
- Lazy loading нормализованного контента

**Parallel Processing:**
- Независимая обработка chunks
- Concurrent backend operations
- Batch processing для множественных документов

**Caching:**
- CAS-based storage всех артефактов
- Deduplication одинаковых документов
- Incremental processing для обновлений

### Масштабирование

**Текущее состояние:**
- Поддержка документов до 100MB
- Обработка до 10,000 chunks в одном документе
- Параллельная обработка множественных документов

**Расширения:**
- Distributed processing для очень больших документов
- GPU acceleration для text processing
- CDN integration для удаленных документов

## Безопасность и приватность

### Content Validation
- **Malicious Content Detection**: Проверка на вредоносный контент
- **PII Scanning**: Автоматическое обнаружение персональных данных
- **License Compliance**: Валидация лицензий документов

### Access Control
- **Document-level Permissions**: Контроль доступа к документам
- **Source Authorization**: Проверка источников документов
- **Audit Logging**: Полное логирование всех операций

### Data Protection
- **Encryption at Rest**: Шифрование хранимых документов
- **Secure Processing**: Безопасная обработка sensitive документов
- **Retention Policies**: Управление сроками хранения

## Тестирование

### Unit Tests
```bash
# Тесты компонентов обработки
pytest tests/fabric/docs/test_ingestion.py
pytest tests/fabric/docs/test_normalize.py
pytest tests/fabric/docs/test_chunking.py
```

### Integration Tests
```bash
# Полный pipeline обработки
pytest tests/integration/test_docs_processing.py

# Интеграция с claims
pytest tests/integration/test_docs_claims_integration.py
```

### Backend-specific Tests
```bash
# Тесты backend'ов
pytest tests/fabric/docs/backends/test_pdf.py
pytest tests/fabric/docs/backends/test_html.py
pytest tests/fabric/docs/backends/test_plain.py
```

### Benchmarking
```bash
# Производительность обработки
pytest tests/benchmarks/test_docs_processing_perf.py

# Масштабирование chunking
pytest tests/benchmarks/test_chunking_scalability.py
```

## Примеры использования

### Полный pipeline обработки документа

```python
from pathlib import Path
from polisyos.fabric.docs import (
    ingest_doc_bytes, normalize_doc, structure_doc, chunk_doc
)

# Загрузка PDF документа
pdf_path = Path("economic_report.pdf")
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

# 1. Ingestion с метаданными
source_spec = DocSourceSpec(
    canonical_url="https://bea.gov/reports/2024.pdf",
    license="public-domain",
    retrieved_at=datetime.now(),
    jurisdiction="US",
    language="en",
    title="Economic Report 2024",
    publisher="Bureau of Economic Analysis"
)

ingest_result = ingest_doc_bytes(pdf_bytes, source_spec)
print(f"Document ingested: {ingest_result.doc_version_id}")

# 2. Нормализация текста
normalize_result = normalize_doc(ingest_result)
print(f"Normalized text: {len(normalize_result.normalized_text)} chars")

# 3. Анализ структуры
structure_result = structure_doc(normalize_result)
print(f"Found {len(structure_result.sections)} sections")

# 4. Chunking для дальнейшей обработки
chunk_result = chunk_doc(structure_result)
print(f"Created {len(chunk_result.chunks)} chunks")
```

### Пакетная обработка документов

```python
from polisyos.fabric.docs import process_document_batch

# Обработка множественных документов
doc_specs = [
    (pdf_bytes1, source_spec1),
    (pdf_bytes2, source_spec2),
    (html_bytes3, source_spec3),
]

results = process_document_batch(
    doc_specs,
    options=DocProcessingOptions(
        normalize=True,
        structure=True,
        chunk=True,
        parallel=True,
        max_workers=4
    )
)

for result in results:
    print(f"Processed: {result.doc_version_id} -> {len(result.chunks)} chunks")
```

### Кастомный backend

```python
from polisyos.fabric.docs.backends import BaseDocBackend
from polisyos.fabric.docs.backends.registry import BackendRegistry

class CustomDocBackend(BaseDocBackend):
    def supports_mime(self, mime_type: str) -> bool:
        return mime_type == "application/vnd.custom"

    def normalize_to_text(self, content: bytes) -> str:
        # Кастомная логика извлечения текста
        return custom_text_extraction(content)

# Регистрация backend'а
registry = BackendRegistry.get_instance()
registry.register("custom", CustomDocBackend())
```

## Заключение

**Document Processing System** обеспечивает надежную и масштабируемую обработку документов различных форматов, предоставляя структурированные данные для дальнейшего анализа и извлечения claims. Система поддерживает полный provenance tracking, evidence generation и seamless интеграцию с остальными компонентами Fabric экосистемы.