# Docs — Document Processing Pipeline

Многоформатная система обработки документов: от сырых байтов до семантических chunks, готовых для извлечения claims.

## Pipeline

```
Raw Bytes → Ingestion → Normalization → Structure Analysis → Chunking → Claims (../claims/)
  (PDF/HTML/   ingest_    normalize_     structure_doc()    chunk_doc()
   text)     doc_bytes()    doc()
```

Каждая стадия возвращает типизированный Result и принимает Options для настройки.

## Структура

```
docs/
├── types.py        # DocSourceSpec, DocIngest/Normalize/Structure/ChunkResult + Options
├── errors.py       # DocNotReadyError, DocPipelineError, DocUnsupportedMimeError, DocValidationError
├── ingestion.py    # ingest_doc_bytes() — загрузка, MIME detection, backend dispatch
├── normalize.py    # normalize_doc() — encoding detection, text cleanup
├── structure.py    # structure_doc() — извлечение заголовков, разделов, иерархии
├── chunking.py     # chunk_doc() — семантическое разбиение на фрагменты
└── backends/       # Format-specific processors
    ├── pdf.py      # PDF: layout preservation, page extraction
    ├── text_html.py # HTML: tag stripping, structure extraction
    └── text_plain.py # Plain text: line-based processing
```

## API

```python
from polisyos.fabric.docs import (
    ingest_doc_bytes,    # Raw bytes → DocIngestResult
    normalize_doc,       # → DocNormalizeResult (clean text)
    structure_doc,       # → DocStructureResult (sections hierarchy)
    chunk_doc,           # → DocChunkResult (semantic chunks)
    DocSourceSpec,       # Source metadata (url, mime_type, etc.)
)
```

14 экспортов: 4 pipeline-функции + 4 Result-типа + 4 Options-типа + 4 error-типа.

## Стадии

### 1. Ingestion (`ingest_doc_bytes`)

Принимает сырые байты + `DocSourceSpec`. MIME-type detection → dispatch на backend (PDF/HTML/text). Результат: `DocIngestResult` с raw text и метаданными.

### 2. Normalization (`normalize_doc`)

Encoding detection, Unicode normalization, whitespace cleanup, character replacement. Результат: `DocNormalizeResult` с чистым текстом.

### 3. Structure Analysis (`structure_doc`)

Извлечение логической структуры: заголовки (H1-H6), разделы, иерархия. Для PDF — по layout/font size, для HTML — по тегам. Результат: `DocStructureResult` с деревом секций.

### 4. Chunking (`chunk_doc`)

Семантическое разбиение: учитывает границы секций и параграфов, контролирует размер chunks (min/max tokens), overlap для контекста. Результат: `DocChunkResult` со списком `DocFragment`.

## Backends

Pluggable через `backends/__init__.py`:

| Backend | Форматы | Особенности |
|---------|---------|-------------|
| `pdf.py` | PDF | Layout preservation, page-aware extraction |
| `text_html.py` | HTML | Tag-aware structure, table extraction |
| `text_plain.py` | Plain text | Line-based, paragraph detection |

## Связи

- **claims/** — основной потребитель: получает DocMeta и chunks для extraction
- **world/store** — persist_doc_meta(), persist_doc_fragment() для материализации
- **provenance** — каждая стадия генерирует provenance records
- **CAS** (core) — хранение нормализованного текста и метаданных
