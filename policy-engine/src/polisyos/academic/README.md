# Academic

`polisyos.academic` — офлайн-контур построения academic knowledge graph (AKG/SKG) на базе OpenAlex и read-only API для извлечения литературы, causal evidence и параметрических prior-ов.

## Роль в системе

`academic` закрывает два связанных контура:

1. ingestion/pipeline:
`topics -> OpenAlex selection -> parsing/extraction -> dedup -> DuckDB graph -> embeddings/QC/publish`.
2. query/runtime:
`DuckDB + HNSW -> поиск работ, causal evidence, priors и transportability-aware выбор параметров`.

Пакет связывает:
- `polisyos.batch_common` (snapshot layout, manifests, QC helpers, thermal control);
- `polisyos.ir.analytics.*` (контракты литературы/контекста/transportability);
- `polisyos.core.canon.hashing` (stable hash/cache ключи);
- `polisyos.academic.openalex`, `polisyos.academic.batch`, `polisyos.academic.knowledge`.

## Архитектура директории

| Подпакет | Назначение | Документация |
|---|---|---|
| `batch/` | Стадийный pipeline от отбора OpenAlex работ до построения графа и публикации | [`batch/README.md`](batch/README.md) |
| `knowledge/` | Read-only API к DuckDB/HNSW, SKG query/selection/versioning, канонизация переменных | [`knowledge/README.md`](knowledge/README.md) |
| `openalex/` | Клиент OpenAlex, загрузка каталога тем и алгоритм topic-based selection | [`openalex/README.md`](openalex/README.md) |
| `trust.py` | Нормализация trust-score по дизайну исследования, цитируемости, свежести и sample size | этот файл |

## Основной поток данных

```text
relevant_topics_*.csv
    -> openalex.topic_catalog + openalex.selector
    -> batch/topic_select.py
    -> batch/harvester.py
    -> batch/parser.py
    -> batch/article_extractor.py OR batch/llm_extractor.py
    -> batch/dedup.py
    -> batch/graph_builder.py (+ SKG tables)
    -> batch/embedder.py
    -> batch/qc.py
    -> batch/publish.py
```

## Артефакты snapshot-а

Все stage output пишутся в `<snapshot_root>/academic`:
- `topic_selection/`:
  `topics_catalog.jsonl`, `selected_topic_works.jsonl`, `selected_global_works.jsonl`;
- `raw/<topic_id>__<slug>/<timestamp>/payload.jsonl` + raw manifest;
- `parsed/*.jsonl`, `extracted/*.jsonl`, `merged/all_records.jsonl`;
- `merged/topic_links.jsonl`, `merged/duplicates_report.csv`;
- `graph/scholar_knowledge.duckdb`;
- `ac_work_embeddings.npz`, `ac_work_index.hnsw`;
- `manifests/*.json`, `qc_report.json`, `publish/manifest.json`.

## Текущее состояние и особенности

- Источник тем по умолчанию:
  `/Users/deniskopylov/polisyos/relevant_topics_domain_files` (`--topics-dir` для override).
- В `run`-режиме `article_extract` имеет приоритет над `extract_llm`:
  при включенной `article_extract` стадия `extract_llm` помечается как skipped.
- `article_extract`/`extract_llm` не ломают pipeline при отсутствии `GONKA_API_KEY`:
  stage завершается с метриками skipped/deferred.
- При merge применен явный приоритет extraction mode:
  `article_extract > llm_enriched > deterministic`.

## Точки входа

- CLI pipeline:
  `python -m polisyos.academic.batch.cli run --snapshot-root <path>`.
- Stage-by-stage запуск:
  `python -m polisyos.academic.batch.cli <stage> --snapshot-root <path>`.
- Query API:
  `ScholarKnowledgeGraph`, `SKGQuery`, `ParameterSelector` (см. `knowledge/`).

## Тесты

Базовое покрытие расположено в:
- `policy-engine/tests/academic/batch`;
- `policy-engine/tests/academic/knowledge`;
- `policy-engine/tests/integration/test_phase0_quality_validation.py`.
