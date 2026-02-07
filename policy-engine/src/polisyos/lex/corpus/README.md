# corpus

Управление корпусом юридических документов: загрузка, структурирование, версионирование.

## Модули

### ingest.py

Загрузка юридического документа в систему. Оркестрирует pipeline `fabric.docs`:

1. `ingest_doc_bytes()` → raw bytes в CAS
2. `normalize_doc()` (опционально) → очистка текста
3. `structure_doc()` (опционально) → выделение секций
4. `chunk_doc()` (опционально) → разбиение на чанки

После каждого шага обогащает `DocMeta.props.lex` свойствами: `effective_from`, `effective_to`, `jurisdiction`, `language`, `published_at`, `source_url`. Политика слияния: `merge_lex` (default) или `overwrite_lex`.

Каждый этап порождает `WorldEvent` с полным провенансом (agent, activity, inputs/outputs).

### structure.py

Парсинг нормализованного текста в иерархию правовых элементов:

```
Article → Part → Point → Subpoint → Paragraph
```

Алгоритм:
- Regex-based определение заголовков по юрисдикционным правилам (UA/RU/EN)
- Tier A: статьи (обязательный уровень)
- Tier B: части и пункты с подпунктами (`enable_tier_b`, default: true)
- Tier C: параграфы по пустым строкам (`enable_paragraphs`, default: false)

Результат: `DocFragment` артефакты + `ProvisionIndex` с citation labels на языке юрисдикции (напр. "Стаття 5, Частина 2, пункт 3").

Quality issues: `no_articles_detected`, `duplicate_article_number:N`, `non_monotonic_articles`.

### versioning.py

Построение временного индекса версий и резолюция актуальной версии.

**`build_version_index()`** — сканирует факты `DOC_HAS_VERSION` в fact log, собирает `effective_from/to` и `published_at` из DocMeta, рассчитывает confidence (1.0 / 0.7 / 0.3), обнаруживает `overlapping_effective_ranges`.

**`resolve_active_version()`** — трёхуровневый fallback:
1. Effective range: `effective_from <= as_of <= effective_to`
2. Published_at: `published_at <= as_of`
3. Deterministic id order (крайний fallback)

Tie-breaker: `effective_from → published_at → doc_version_id`.

### index.py

Pydantic-модели индексов и функции persist/load через CAS:

| Модель | Назначение |
|---|---|
| `ProvisionIndexV1` | Индекс правовых положений документа (статьи, пункты, подпункты) |
| `VersionIndexV1` | Индекс версий doc_source с temporal metadata |
| `DocSourcePropsV1` | Свойства doc_source с указателем на version_index |
| `ProvisionEntryV1` | Отдельное положение: anchor_path, offset, kind, citation_label |
| `VersionEntryV1` | Версия документа: published_at, effective_from/to, confidence |

Все модели наследуют `KernelModel`, используют `SchemaInfo` для версионирования и `frozen=True`.

## Зависимости

- `fabric.docs` — pipeline обработки документов
- `fabric.world` — запись фактов и мировых событий
- `ir.world.doc` — DocMeta, DocFragment
- `ir.citations` — AnchorKind, FragmentLocator
- `core.artifacts` — CAS, ArtifactID
- `pandas` — чтение parquet fact segments (versioning)
