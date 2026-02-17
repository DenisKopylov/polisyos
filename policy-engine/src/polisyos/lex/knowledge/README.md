# knowledge

`polisyos.lex.knowledge` — read-only слой доступа к legal knowledge graph, построенному `lex.batch`.

## Назначение

Подсистема дает единый API для:
- vector search по сущностям, фактам и provisions;
- text/structured search по фактам;
- graph traversal между юридическими сущностями.

## Архитектура

```text
DuckDB (lex_knowledge_graph.duckdb)
  + HNSW/NPZ indexes
      -> LegalKnowledgeStore (store.py)
          -> LegalKnowledgeGraph (search.py)
```

## Ключевые модули

### `types.py`

Доменные модели:
- extraction output (`SPOCandidate`, `SPOExtractionResult`);
- graph rows (`LegalEntity`, `LegalFact`, `LegalProvision`);
- search results (`LegalSearchResult`, `LegalFactResult`, `LegalProvisionResult`).

### `store.py`

`LegalKnowledgeStore`:
- подключается к DuckDB в `read_only=True`;
- лениво загружает HNSW индексы (`entities`, `facts`, `provisions`);
- выполняет vector/text/structured запросы;
- поддерживает graph traversal (`find_related_entities`).

### `search.py`

`LegalKnowledgeGraph`:
- high-level API над `LegalKnowledgeStore`;
- умеет `hybrid_search` (vector + text score fusion);
- при наличии `openai_api_key` строит query embeddings (`text-embedding-3-large` по умолчанию).

## Основные методы API

- `search_entities(query)`
- `search_facts(query)`
- `search_provisions(query)`
- `text_search(query)`
- `hybrid_search(query)`
- `search_facts_by_action(action_canon)`
- `search_facts_with_threshold(metric)`
- `get_norms_for_entity(entity_id)`
- `find_related_entities(entity_id)`

## Зависимости и данные

- Источник данных: outputs из `policy-engine/src/polisyos/lex/batch`.
- Обязателен DuckDB файл (`lex_knowledge_graph.duckdb`).
- HNSW/NPZ индексы optional: без них vector search вернет пустой результат, text/structured search продолжат работать.

## Связь с другими директориями

- Upstream: `policy-engine/src/polisyos/lex/batch`.
- Re-export: `LegalKnowledgeGraph` доступен через `polisyos.lex`.
