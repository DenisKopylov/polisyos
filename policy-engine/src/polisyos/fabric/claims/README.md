# Claims — Claims Processing Pipeline

Система извлечения, нормализации и разрешения конфликтов фактов (claims) из документов. Обеспечивает pipeline от неструктурированного текста до валидированных фактов в Fact Log.

## Pipeline

```
Document → Extraction → Normalization → Conflict Detection → Resolution → Fact Log
  (docs/)    backends/    canonicalize     conflicts/detect    conflicts/   persist
                          + normalize       + key + score      resolve
```

## Структура

```
claims/
├── types.py               # ClaimCandidate, ClaimExtractResult, ClaimNormalizeResult, Options
├── errors.py              # ClaimNotReadyError, ClaimPipelineError, ClaimValidationError
├── extraction.py          # extract_claims_from_doc() — основной pipeline извлечения
├── extractor_registry.py  # Реестр pluggable extractors (ComponentRegistry-based)
├── normalize.py           # normalize_claims() — нормализация набора claims
├── canonicalize.py        # Канонизация ID и единиц (ID_PATTERN validation)
├── citations.py           # Связывание claims с фрагментами документа
├── persist.py             # Сохранение claims в Fact Log сегменты
├── backends/              # Pluggable экстракторы
│   ├── explicit_lines_v1  # claim: predicate = value [unit]
│   ├── lex_norm_regex_v1  # Лексическая нормализация + regex
│   └── regex_numeric_v1   # Числовые значения с единицами
└── conflicts/             # Обнаружение и разрешение противоречий
    ├── types.py           # ConflictSet, ResolutionResult, policies
    ├── detect.py          # detect_conflicts() — группировка + поиск противоречий
    ├── key.py             # Генерация conflict keys для группировки
    ├── policies.py        # Политики разрешения (majority vote, recency, etc.)
    ├── resolve.py         # resolve_conflicts() — применение политик
    ├── score_claims.py    # Confidence scoring для claims
    ├── score_docs.py      # Trust scoring для источников
    └── uncertainty_adapter.py  # Мост к IR UncertaintyEnvelope
```

## Ключевые типы

### ClaimCandidate

```python
@dataclass(frozen=True)
class ClaimCandidate:
    predicate_id: str             # "gdp", "unemployment_rate"
    value_text: str               # Текстовое значение
    citation_fragment_id: str     # Ссылка на фрагмент документа
    subject_id: str | None        # ID субъекта (агент, регион)
    value_decimal: Decimal | None # Числовое значение (если есть)
    unit_id: str | None           # "USD", "percent"
    confidence: Decimal | None    # Уверенность экстрактора
    qualifiers: dict[str, Any]    # Дополнительные квалификаторы
```

### ClaimExtractResult

Результат извлечения: `claim_ids`, `world_event_id`, `evidence_ref`, `world_segment_manifest`.

## Extraction

`extract_claims_from_doc()` — основной entrypoint:

1. Загрузка DocMeta и нормализованного текста из CAS
2. Выбор backend-экстрактора через `extractor_registry`
3. Извлечение candidates из каждого chunk
4. Генерация World Events и Facts
5. Запись Fact Log сегмента + evidence

Backend-экстракторы регистрируются через `ComponentRegistry` из `polisyos.core` с SemVer версионированием.

## Normalization

`normalize_claims()`:
- Канонизация ID (regex `^[a-z][a-z0-9_.]*$`)
- Унификация единиц измерения
- Парсинг числовых значений в Decimal
- Drop невалидных claims (опционально)

## Conflict Resolution

Двухфазный процесс:

1. **detect_conflicts()** — группировка claims по conflict key (subject + predicate + time), поиск расхождений значений. Создает `ConflictSet` с `ConflictKind` (value/temporal/source).

2. **resolve_conflicts()** — применение политики:
   - `score_claims.py` — confidence scoring отдельных claims
   - `score_docs.py` — trust scoring документов-источников
   - `policies.py` — стратегия выбора (majority vote, highest confidence, most recent)

## Связи

- **docs/** — поставляет DocMeta и нормализованный текст для extraction
- **world/store** — persist_claim(), emit_claim_facts() для материализации
- **Fact Log** (IR) — persist.py записывает claims как immutable Facts
- **provenance** — каждый шаг pipeline создает provenance записи
- **catalog** — валидация predicate_id и value types против DataContract
