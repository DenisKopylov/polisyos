# Academic Knowledge

`polisyos.academic.knowledge` — read-only слой поверх academic DuckDB/SKG, который предоставляет поиск работ, causal evidence, literature priors и transportability-aware выбор параметров.

## Роль в системе

Подпакет потребляет результаты `polisyos.academic.batch.graph_load` и используется как runtime API для:
- retrieval релевантной литературы;
- построения prior-ов для параметров;
- выборки causal/edge evidence из SKG;
- отбора параметров под target context.

## Модули и ответственность

| Модуль | Назначение |
|---|---|
| `types.py` | Контракты `WorkRecord`, `EstimateCandidate`, `ParameterPrior`, search/result модели |
| `store.py` | Низкоуровневый read-only доступ к DuckDB и HNSW индексу |
| `search.py` | High-level фасад `ScholarKnowledgeGraph` (hybrid search + priors + evidence lookups) |
| `skg_query.py` | Query API по SKG-таблицам (`ac_skg_*`), edge priors, parameter candidates |
| `parameter_selector.py` | `ParameterSelector` с transportability scoring через `ContextProfile` и causal graph |
| `variable_canonizer.py` | Детерминированная канонизация имен переменных + cache в DuckDB |
| `canonical_seed.py` | Seed словарь canonical variable namespace |
| `skg_store.py` | DDL/утилиты для SKG и confidence aggregation |
| `skg_versioning.py` | version manager и retraction handling для SKG |

## Публичные entry points

Через `polisyos.academic.knowledge` экспортируются:
- `ScholarKnowledgeGraph`;
- `SKGQuery`;
- `ParameterSelector`;
- `VariableCanonizer`;
- `SKGVersionManager`;
- типы из `types.py`.

## Ключевые сценарии

1. Поиск работ:
`ScholarKnowledgeGraph.find_relevant_works()` выполняет fusion `text_search + vector_search`.
2. Literature prior:
`get_parameter_prior(variable, domain, country)` агрегирует оценки с trust-weighted mean/std.
3. Causal evidence:
`find_causal_evidence(cause, effect)` и `get_mechanism_evidence(...)`.
4. SKG edge/parameter query:
`SKGQuery.query_parameters()`, `query_edge_priors()`, `query_prior_for_variables()`.
5. Context-aware выбор параметра:
`ParameterSelector.select_for_context(...)` с учетом transportability и evidence strength.

## Используемые таблицы

- Runtime tables:
  `ac_works`, `ac_parameter_estimates`, `ac_causal_claims`, `ac_boundary_conditions`, `ac_topic_selections`.
- SKG tables:
  `ac_skg_articles`, `ac_skg_variables`, `ac_skg_parameters`, `ac_skg_edges`, `ac_skg_versions`,
  `ac_skg_canonization_cache`.

## Особенности текущей реализации

- `store.py` всегда открывает DuckDB в `read_only=True`.
- Векторный поиск деградирует в text-only режим, если отсутствуют `ac_work_embeddings.npz`/`ac_work_index.hnsw`.
- `VariableCanonizer`:
  exact match -> cache -> fuzzy match -> slug fallback + pending review.
- `aggregate_edge_confidence()` в `skg_store.py` отдает приоритет сильной evidence + replication bonus.
- `SKGVersionManager.handle_retraction()` пересчитывает confidence edges, удаляет осиротевшие edges.

## Связи с другими директориями

- Вход данных: `polisyos.academic.batch.graph_builder`.
- Семантические контракты: `polisyos.ir.analytics.context`, `polisyos.ir.analytics.literature`,
  `polisyos.ir.analytics.transportability`, `polisyos.ir.analytics.parameters`.

## Проверки

- `policy-engine/tests/academic/knowledge`;
- часть проверок в `policy-engine/tests/academic/batch/test_skg_*`.
