# corpus

`lex.corpus` готовит юридический корпус для последующих подсистем (`normpack`, `legal_evaluation`).

## Что делает

- принимает raw документ и доводит его до `DocMeta` с `lex.*` метаданными;
- строит структурную разметку норм (`ProvisionIndexV1`);
- строит индекс версий документа (`VersionIndexV1`) и указатель на него в `DocSourcePropsV1`.

## Модули

### `ingest.py`

Оркестрирует `fabric.docs` pipeline (`ingest -> normalize -> structure -> chunk`) и дополняет `DocMeta.props.lex` полями:
- `corpus=lex.corpus`
- `jurisdiction`, `language`
- `published_at`, `effective_from`, `effective_to`
- `source_url`

Особенность: поддерживает merge-политику (`merge_lex`/`overwrite_lex`) и пишет world event для обновления метаданных.

### `structure.py`

Строит иерархию положений из `normalized_ref`:
- уровни: `article -> part -> point -> subpoint` (+ `paragraph` опционально);
- ruleset'ы для `UA`, `RU`, `EN`;
- юрисдикция берется в порядке: `options.jurisdiction -> meta.jurisdiction -> meta.props.lex.jurisdiction`.

Выход:
- `DocFragment` артефакты;
- `ProvisionIndexV1`;
- обновленный `DocMeta` с `lex.provision_index_ref`.

Типовые quality issues: `no_articles_detected`, `duplicate_article_number:*`, `non_monotonic_articles`.

### `versioning.py`

- `build_version_index`: собирает версии через факты `DOC_HAS_VERSION` и метаданные документов, считает confidence и quality issues.
- `resolve_active_version`: выбирает активную версию по стратегии:
  1. `effective_from/effective_to`
  2. `published_at`
  3. детерминированный fallback по id.

Результат `build_version_index` также персистит `DocSourcePropsV1.version_index_ref`, который затем использует `normpack.select_sources`.

### `index.py`

Pydantic-модели и persist/load helpers для:
- `ProvisionIndexV1`
- `VersionIndexV1`
- `DocSourcePropsV1`

## Связь с другими директориями

- Читает/пишет через `polisyos.core.artifacts` (CAS).
- Пишет факты/события через `polisyos.fabric.world`.
- Использует модели `polisyos.ir.world.*` и `polisyos.ir.citations`.
- Является upstream для `policy-engine/src/polisyos/lex/normpack`.
