# Lex

`polisyos.lex` — юридический слой policy engine.

Модуль отвечает за полный юридический контур:
- загрузка и структурирование нормативных документов;
- сборка нормативного пакета (`NormPack`) на дату и юрисдикцию;
- оценка соответствия PolicySpec этим нормам;
- what-if анализ изменений нормативного пакета.

## Роль в системе

Lex связывает три больших слоя проекта:
- `polisyos.fabric`: ingestion/normalization документов, extraction claims, world facts/events.
- `polisyos.ir`: доменные модели (`DocMeta`, `Claim`, `NormPack`, `PolicySpec`, `ComplianceIssue`).
- `polisyos.core`: CAS, contracts, component registry (entry points), governance passes.

Ключевой принцип: каждый этап персистит артефакты в CAS и фиксирует provenance через world fact log.

## Карта директории

```text
lex/
  api.py                # фасад публичного API
  __init__.py           # lazy-экспорт API, типов и simulator-помощников
  types.py              # dataclass/Pydantic типы запросов и результатов
  errors.py             # иерархия ошибок LexError
  artifacts.py          # безопасная загрузка CAS-артефактов (JSON, DocMeta)
  factlog.py            # чтение fact segments (parquet)
  common.py             # общие утилиты (ISO date, latest-by-subject, collapse ws)

  corpus/               # ingest -> structure -> version index
  normpack/             # сборка NormPack из корпуса и claims
  legal_evaluation/     # legality report + proposals
  simulator/            # mutate/diff/impact по NormPack
```

## Основные потоки

```text
raw bytes
  -> corpus.ingest_legal_doc_bytes()
  -> corpus.build_legal_structure()
  -> corpus.build_version_index() / resolve_active_version()
  -> normpack.assemble_norm_pack()
  -> legal_evaluation.evaluate_legality()
       -> (опционально) propose_changes()

parallel branch:
  old/new NormPack -> simulator.diff + simulator.engine -> impact report
```

## Публичный API

Экспортируется через `polisyos.lex.api` (и лениво реэкспортируется в `polisyos.lex`):
- `ingest_legal_doc_bytes`
- `build_legal_structure`
- `build_version_index`
- `resolve_active_version`
- `assemble_norm_pack`
- `evaluate_legality`
- `propose_changes`

Дополнительно из `polisyos.lex` доступны типы и инструменты simulator (`NormPackMutator`, `diff_norm_packs`, `NormImpactAnalyzer`).

## Подсистемы

- `corpus`: готовит юридический корпус и индексы (`provision_index`, `version_index`). Подробно: [corpus/README.md](corpus/README.md)
- `normpack`: собирает норм-пакет из выбранных версий документов и claims. Подробно: [normpack/README.md](normpack/README.md)
- `legal_evaluation`: выполняет rule-by-rule проверку и собирает legal report/proposals. Подробно: [legal_evaluation/README.md](legal_evaluation/README.md)
- `simulator`: анализирует последствия изменения норм до применения в проде. Подробно: [simulator/README.md](simulator/README.md)

## Точки расширения

- NormPack providers: entry points группы `polisyos.norm_pack_providers`.
- Legal evaluators: entry points группы `polisyos.lex_evaluators`.
- Claim extractors для normpack: bootstrap через component index (`scholar` и `lex` extractor groups).

## Ключевые артефакты

- `lex.corpus.provision_index`
- `lex.corpus.version_index`
- `lex.corpus.doc_source_props`
- `lex.norm_pack`
- `lex.legal_report`
- `lex.change_proposal`
- `lex.norm_diff`
- `lex.norm_impact_report`

## Эксплуатационные особенности

- Почти все этапы устойчивы к частично заполненным данным: вместо hard-fail часто возвращаются `warnings`/`quality_issues`.
- В `normpack.select_sources` есть fallback-резолюция активной версии через fact log, если индекс версий еще не построен.
- В `legal_evaluation` change proposals генерируются автоматически на основе `FAIL` findings и quality issues.
