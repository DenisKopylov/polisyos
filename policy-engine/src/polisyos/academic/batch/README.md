# Academic Batch

`polisyos.academic.batch` — staged pipeline построения academic/SKG графа из OpenAlex-литературы в режиме `fulltext-first` с одним LLM-вызовом на paper и deterministic publish gates.

## Роль в системе

Подсистема готовит данные для `polisyos.academic.knowledge`:
- отбирает релевантные работы по каталогам тем;
- извлекает параметры/causal claims/boundary conditions;
- материализует DuckDB таблицы (`ac_*` и `ac_skg_*`);
- строит локальный векторный индекс и выпускает publish manifest.

## Стадии (актуальный порядок)

`topic_select -> harvest -> parse -> resolve_extract -> merge_dedup -> graph_load -> graph_index -> embed -> qc -> publish`

| Стадия | Модуль | Вход | Основной выход |
|---|---|---|---|
| `topic_select` | `topic_select.py` | topic CSV (`relevant_topics_*.csv`) | `topic_selection/*.jsonl` |
| `harvest` | `harvester.py` | `selected_topic_works.jsonl` | `raw/<topic>/<ts>/payload.jsonl` |
| `parse` | `parser.py` | `raw/*/payload.jsonl` | `parsed/*.jsonl` (`WorkRecord`, deterministic extraction) |
| `resolve_extract` | `resolve_extract.py` | `selected_global_works.jsonl` | `resolve_extract_results.jsonl`, `raw_claim_candidates.jsonl`, `published_claims.jsonl`, `extracted/resolve_extract.jsonl` |
| `merge_dedup` | `dedup.py` | `extracted/*.jsonl` или `parsed/*.jsonl` | `merged/all_records.jsonl`, `topic_links.jsonl`, `duplicates_report.csv` |
| `graph_load` | `graph_builder.py` | `merged/all_records.jsonl` | `graph/scholar_knowledge.duckdb` |
| `graph_index` | `graph_builder.py` | DuckDB файл | вторичные индексы `ac_*` |
| `embed` | `embedder.py` | `ac_works` | `ac_work_embeddings.npz`, `ac_work_index.hnsw` |
| `qc` | `qc.py` | артефакты batch + DB | `qc_report.json` |
| `publish` | `publish.py` | все предыдущие stage outputs | `publish/manifest.json` |

## Ключевые модули

- `config.py`: `AcademicBatchConfig`, список `ALL_STAGES`, snapshot paths, runtime knobs.
- `pipeline.py`: async orchestration, stage metrics, thermal cooldown.
- `cli.py`: stage commands (`run`, `stats`, `search`, `prior`), alias-обработка стадий.
- `resolve_extract.py`: streaming orchestration, shared multi-key provider pool, one-call extraction contract, deterministic publish gates.
- `prompts/`: schema hints для extraction contract и auxiliary prompt fragments.
- `context_classifier.py`: базовая привязка extraction результата к `ContextProfile`.

## Resolve-extract semantics

- `parser.py` дает baseline `extraction_mode=deterministic`.
- `resolve_extract.py` делает:
  - concurrent fulltext fetch;
  - deterministic eligibility gate;
  - shared multi-key LLM scheduling;
  - один extraction call на paper;
  - raw claim persistence;
  - deterministic publish gating.
- В `dedup._merge_records()` применяется приоритет:
  `resolve_extract > article_extract > llm_enriched > deterministic`.
- `abstract_only` записи сохраняются только в raw/exploration artifacts и не должны попадать в published causal graph.

## DuckDB слой graph_load

`graph_builder.py` материализует:
- runtime tables: `ac_works`, `ac_parameter_estimates`, `ac_causal_claims`, `ac_boundary_conditions`,
  `ac_topics`, `ac_topic_selections`, `ac_article_extractions`, `ac_causal_claims_raw`, `ac_claim_adjudications`, `ac_ingest_errors`, `ac_runs`;
- SKG tables: `ac_skg_articles`, `ac_skg_variables`, `ac_skg_parameters`, `ac_skg_edges`, `ac_skg_versions`.

## CLI

```bash
python -m polisyos.academic.batch.cli run --snapshot-root <snapshot_root>
python -m polisyos.academic.batch.cli topic-select --snapshot-root <snapshot_root>
python -m polisyos.academic.batch.cli resolve-extract --snapshot-root <snapshot_root>
python -m polisyos.academic.batch.cli graph-load --snapshot-root <snapshot_root>
python -m polisyos.academic.batch.cli qc --snapshot-root <snapshot_root>
python -m polisyos.academic.batch.cli publish --snapshot-root <snapshot_root>
```

Операционные команды:
- `stats --db-path <duckdb>`;
- `search --db-path <duckdb> --query "..."`
- `prior --db-path <duckdb> --variable "<canonical_name>"`.

## Связи с другими пакетами

- `polisyos.academic.openalex`: topic catalog + OpenAlex API + selection.
- `polisyos.academic.knowledge`: типы `WorkRecord`, SKG schema helpers.
- `polisyos.batch_common`: manifests, QC infra, thermal helpers, snapshot paths.
- `polisyos.ir.analytics`: `ArticleExtractionResult`, `ContextProfile`, Evidence enums.

## Проверки

Релевантные тесты:
- `policy-engine/tests/academic/batch`;
- `policy-engine/tests/integration/test_phase0_quality_validation.py`.
