# Lex

`polisyos.lex` — юридический слой `policy-engine`: от подготовки нормативного корпуса до оценки легальности, what-if анализа изменений норм и работы с legal knowledge graph.

## Роль в системе

`lex` связывает:
- `polisyos.fabric` (ingest документов, claims/world facts);
- `polisyos.ir` (типы `NormPack`, `PolicySpec`, `ComplianceIssue`, world-модели);
- `polisyos.core` (CAS, component registry, governance passes).

Основной принцип: каждый значимый шаг сохраняется в CAS и/или в fact log с provenance-событиями.

## Контуры

- Online-контур комплаенса: `corpus -> normpack -> legal_evaluation -> simulator`.
- Offline-контур графа знаний: `batch -> knowledge`.

## Архитектура директории

```text
lex/
  api.py                # фасад синхронного API
  __init__.py           # lazy-экспорт core API/типов + simulator/knowledge
  types.py              # dataclass-запросы/результаты
  errors.py             # LexError + подтипы
  artifacts.py          # безопасная загрузка CAS payload
  factlog.py            # загрузка world fact segments (parquet)
  common.py             # общие утилиты (ISO date, ws collapse, latest value)

  corpus/               # ingest, structure, version indexes
  normpack/             # сборка NormPack (provider/pipeline path)
  legal_evaluation/     # legal report + change proposals + transport constraints
  simulator/            # diff/impact анализ изменений NormPack
  batch/                # XML -> legal knowledge graph (offline)
  knowledge/            # read-only search API по legal graph
```

## Основные потоки

```text
Compliance:
raw bytes
  -> ingest_legal_doc_bytes
  -> build_legal_structure
  -> build_version_index / resolve_active_version
  -> assemble_norm_pack
  -> evaluate_legality
  -> (optional explicit) propose_changes

Simulation:
old/new NormPack -> diff_norm_packs -> NormImpactAnalyzer.analyze

Knowledge:
XML corpus -> lex.batch (parse/structure/spo/graph/embed)
          -> DuckDB + HNSW/NPZ indexes
          -> LegalKnowledgeGraph search API
```

## Публичный API

Через `polisyos.lex.api`:
- `ingest_legal_doc_bytes`
- `build_legal_structure`
- `build_version_index`
- `resolve_active_version`
- `assemble_norm_pack`
- `evaluate_legality`
- `evaluate_transport_constraints`
- `propose_changes`

Через lazy-реэкспорт `polisyos.lex`:
- core API (кроме `evaluate_transport_constraints`, он доступен через `polisyos.lex.api`);
- simulator-инструменты (`NormPackMutator`, `diff_norm_packs`, `NormImpactAnalyzer`);
- knowledge API (`LegalKnowledgeGraph`);
- типы запросов/результатов `lex.types`.

## Точки расширения

- `polisyos.norm_pack_providers` — внешние `NormPackProvider`.
- `polisyos.lex_evaluators` — внешние legal evaluators.
- `polisyos.lex_extractors` и `polisyos.scholar_extractors` — extractors для norm claims.

## Ключевые артефакты

- `lex.corpus.provision_index`
- `lex.corpus.version_index`
- `lex.corpus.doc_source_props`
- `lex.norms.claim_set`
- `lex.norm_pack`
- `lex.legal_report`
- `lex.change_proposal`
- `lex.norm_diff`
- `lex.norm_impact_report`
- offline graph bundle: `lex_knowledge_graph.duckdb`, `lex_*_embeddings.npz`, `lex_*_index.hnsw`

## Подсистемы

- `corpus`: [corpus/README.md](corpus/README.md)
- `normpack`: [normpack/README.md](normpack/README.md)
- `legal_evaluation`: [legal_evaluation/README.md](legal_evaluation/README.md)
- `simulator`: [simulator/README.md](simulator/README.md)
- `batch`: [batch/README.md](batch/README.md)
- `knowledge`: [knowledge/README.md](knowledge/README.md)

## Эксплуатационные особенности

- Большинство подсистем предпочитает `warnings`/`quality_issues` вместо раннего hard-fail.
- `normpack.select_sources` умеет fallback-выбор версии напрямую из фактов, если `version_index` еще не собран.
- `evaluate_legality` перед запуском всегда bootstrap-ит evaluator registry; встроенный backend — `lex.eval.simple_v1@1.0.0`.
