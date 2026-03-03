# corpus

`polisyos.lex.corpus` готовит юридический корпус в CAS/fact log для downstream-подсистем `lex.normpack` и `lex.legal_evaluation`.

## Роль

Подсистема отвечает за:
- ingest правового документа и обогащение `DocMeta.props.lex`;
- выделение юридической структуры (provisions/fragments);
- построение индексов версий для выбора активной редакции документа.

## Поток

```text
raw bytes
  -> ingest_legal_doc_bytes
  -> (optional) normalize/structure/chunk via fabric.docs
  -> build_legal_structure
  -> build_version_index
  -> resolve_active_version (on demand)
```

## Ключевые модули

### `ingest.py`

- Обертка над `fabric.docs` ingest pipeline.
- Обновляет `DocMeta.props.lex` (`schema_version`, `corpus`, jurisdiction/language/date поля, `ingest.pipeline`).
- Поддерживает merge-политику: `merge_lex` или `overwrite_lex`.
- Пишет world facts/events и возвращает `LexIngestResult`.

### `structure.py`

- Требует `DocMeta.normalized_ref`, иначе `LexNotReadyError`.
- Ruleset-ы: `UA`, `RU`, `EN`.
- Извлекает иерархию `article -> part -> point -> subpoint` (параграфы опциональны).
- Пишет `DocFragment`, `ProvisionIndexV1` (`lex.corpus.provision_index`) и обновляет `DocMeta.lex` ссылкой `provision_index_ref`.

Типовые quality issues:
- `no_articles_detected`
- `duplicate_article_number:*`
- `non_monotonic_articles`

### `versioning.py`

`build_version_index`:
- читает `DOC_HAS_VERSION` и `WORLD_ARTIFACT_ID` из fact log;
- собирает `VersionIndexV1` (`lex.corpus.version_index`);
- пишет `DocSourcePropsV1` (`lex.corpus.doc_source_props`) и pointer-факты.

`resolve_active_version`:
- primary path: через `version_index_ref`;
- selection: `effective window -> published_at -> deterministic id fallback`;
- при отсутствии pointer возвращает `LexNotReadyError`.

### `index.py`

Типы и persist/load helpers для:
- `ProvisionIndexV1`
- `VersionIndexV1`
- `DocSourcePropsV1`

## Связи

- `polisyos.fabric.docs` и `polisyos.fabric.world` — ingest/provenance.
- `polisyos.core.artifacts` — CAS persistence.
- `polisyos.ir.world` / `polisyos.ir.citations` — доменные модели.
- Upstream для `policy-engine/src/polisyos/lex/normpack`.
