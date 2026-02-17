# Lex

`polisyos.lex` — юридический слой `policy-engine`: от подготовки нормативного корпуса до проверки легальности и what-if анализа изменений норм.

Пакет состоит из двух контуров:
- online-контур комплаенса: `corpus -> normpack -> legal_evaluation -> simulator`;
- offline-контур графа знаний: `batch -> knowledge`.

## Роль в системе

`lex` связывает:
- `polisyos.fabric` (docs/claims/world facts);
- `polisyos.ir` (модели `DocMeta`, `Claim`, `NormPack`, `PolicySpec`, `ComplianceIssue`);
- `polisyos.core` (CAS, contracts, component registry, governance passes).

Результат каждого шага фиксируется в CAS и/или fact log с provenance-событиями.

## Архитектура директории

```text
lex/
  api.py                # публичный фасад
  __init__.py           # lazy-экспорт API/типов/simulator/knowledge
  types.py              # dataclass-модели запросов/результатов
  errors.py             # LexError + подтипы
  artifacts.py          # безопасная загрузка CAS payload
  factlog.py            # чтение world fact segments (parquet)
  common.py             # общие утилиты (ISO dates, collapse ws, latest value)

  corpus/               # ingest/structure/version indexes
  normpack/             # сборка NormPack из corpus + claims
  legal_evaluation/     # legal report + change proposals
  simulator/            # diff/impact анализ NormPack изменений
  batch/                # offline pipeline XML -> legal knowledge graph
  knowledge/            # read-only search API по графу знаний
```

## Основные потоки

```text
Compliance flow:
raw doc bytes
  -> ingest_legal_doc_bytes
  -> build_legal_structure
  -> build_version_index / resolve_active_version
  -> assemble_norm_pack
  -> evaluate_legality
  -> (optional) propose_changes

Simulation flow:
old/new NormPack -> diff_norm_packs -> NormImpactAnalyzer.analyze

Knowledge flow:
XML corpus -> lex.batch (parse/structure/spo/graph/embed)
          -> DuckDB + HNSW indexes
          -> LegalKnowledgeGraph (hybrid/vector/text search)
```

## Публичный API

Через `polisyos.lex.api` (и lazy-реэкспорт в `polisyos.lex`) доступны:
- `ingest_legal_doc_bytes`
- `build_legal_structure`
- `build_version_index`
- `resolve_active_version`
- `assemble_norm_pack`
- `evaluate_legality`
- `propose_changes`

Также из `polisyos.lex` доступны:
- simulator-инструменты (`NormPackMutator`, `diff_norm_packs`, `NormImpactAnalyzer`);
- knowledge API (`LegalKnowledgeGraph`);
- типы запросов/результатов `lex.types`.

## Подсистемы

- `corpus`: [corpus/README.md](corpus/README.md)
- `normpack`: [normpack/README.md](normpack/README.md)
- `legal_evaluation`: [legal_evaluation/README.md](legal_evaluation/README.md)
- `simulator`: [simulator/README.md](simulator/README.md)
- `batch`: [batch/README.md](batch/README.md)
- `knowledge`: [knowledge/README.md](knowledge/README.md)

## Точки расширения

- `polisyos.norm_pack_providers` — внешние `NormPackProvider`.
- `polisyos.lex_evaluators` — внешние legal evaluators.
- `polisyos.lex_extractors` и `polisyos.scholar_extractors` — extractors для norm claims.

## Ключевые артефакты и форматы

- `lex.corpus.provision_index`
- `lex.corpus.version_index`
- `lex.corpus.doc_source_props`
- `lex.norms.claim_set`
- `lex.norm_pack`
- `lex.legal_report`
- `lex.change_proposal`
- `lex.norm_diff`
- `lex.norm_impact_report`
- (offline) `lex_knowledge_graph.duckdb`, `lex_*_embeddings.npz`, `lex_*_index.hnsw`

## Эксплуатационные особенности

- Большинство шагов использует `warnings`/`quality_issues` вместо раннего падения.
- `normpack.select_sources` умеет fallback-выбор активной версии через facts, если version index еще не построен.
- `evaluate_legality` перед запуском bootstrap-ит evaluator registry; встроенный backend — `lex.eval.simple_v1@1.0.0`.
