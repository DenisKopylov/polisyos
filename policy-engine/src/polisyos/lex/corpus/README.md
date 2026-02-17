# corpus

`polisyos.lex.corpus` подготавливает юридический корпус в CAS/fact log для downstream-пайплайнов `lex.normpack` и `lex.legal_evaluation`.

## Что делает

- ingest правового документа и обогащение `DocMeta.props.lex`;
- структурирование норм в `ProvisionIndexV1` + `DocFragment`;
- построение `VersionIndexV1` и `DocSourcePropsV1` для выбора активных версий.

## Поток

```text
raw bytes
  -> ingest_legal_doc_bytes
  -> (optional in ingest) normalize/structure/chunk через fabric.docs
  -> build_legal_structure
  -> build_version_index
  -> resolve_active_version (on demand)
```

## Ключевые модули

### `ingest.py`

- Обертка над `fabric.docs` (`ingest`, опционально `normalize/structure/chunk`).
- Обновляет `DocMeta.props.lex`:
  - `schema_version=1.0`
  - `corpus=lex.corpus`
  - `jurisdiction`, `language`, `published_at`, `effective_from`, `effective_to`, `source_url`
  - `ingest.pipeline=lex.corpus.ingest_v1`
- Поддерживает merge-политику: `merge_lex` или `overwrite_lex`.
- Пишет world events/segments и возвращает `LexIngestResult`.

### `structure.py`

- Требует `DocMeta.normalized_ref`; иначе `LexNotReadyError`.
- Извлекает provision-иерархию:
  - `article -> part -> point -> subpoint`
  - `paragraph` опционально (`enable_paragraphs`)
- Ruleset'ы: `UA`, `RU`, `EN`.
- Пишет:
  - `DocFragment` артефакты и факты;
  - `ProvisionIndexV1` (`lex.corpus.provision_index`);
  - обновленный `DocMeta` с `lex.provision_index_ref`, `lex.structure_algorithm_id`, `lex.structure_pipeline`.

Типовые quality issues:
- `no_articles_detected`
- `duplicate_article_number:*`
- `non_monotonic_articles`

### `versioning.py`

- `build_version_index`:
  - читает факты `DOC_HAS_VERSION`;
  - поднимает актуальные `DocMeta` через `WORLD_ARTIFACT_ID`;
  - строит `VersionIndexV1` (`lex.corpus.version_index`);
  - пишет `DocSourcePropsV1` (`lex.corpus.doc_source_props`) и pointer-факты.
- `resolve_active_version`:
  - первичный путь через `version_index_ref`;
  - выбор версии: `effective window` -> `published_at` -> deterministic ID fallback;
  - при отсутствии pointer может вернуть `LexNotReadyError`.

### `index.py`

Типы и helpers persist/load для:
- `ProvisionIndexV1`
- `VersionIndexV1`
- `DocSourcePropsV1`

## Связи с другими директориями

- `polisyos.fabric.docs` и `polisyos.fabric.world` — ingest и provenance.
- `polisyos.core.artifacts` — CAS-персистенция.
- `polisyos.ir.world` / `polisyos.ir.citations` — доменные модели и идентификаторы.
- Upstream для `policy-engine/src/polisyos/lex/normpack`.
