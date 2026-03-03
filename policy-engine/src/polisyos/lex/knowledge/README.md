# knowledge

`polisyos.lex.knowledge` — read-only API к legal knowledge graph, построенному в `lex.batch`.

## Роль

Подсистема предоставляет единый доступ к:
- vector search по entities/facts/provisions;
- text и structured search по фактам;
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

Доменные модели extraction output, графовых строк и search results:
- `SPOCandidate`, `SPOExtractionResult`
- `LegalEntity`, `LegalFact`, `LegalProvision`
- `LegalSearchResult`, `LegalFactResult`, `LegalProvisionResult`

### `store.py`

`LegalKnowledgeStore`:
- открывает DuckDB в `read_only=True`;
- лениво загружает HNSW (`entities`, `facts`, `provisions`);
- выполняет vector/text/structured запросы;
- поддерживает graph traversal (`find_related_entities`).

### `search.py`

`LegalKnowledgeGraph` — high-level API:
- `search_entities`, `search_facts`, `search_provisions`
- `text_search`, `hybrid_search`
- `search_facts_by_action`, `search_facts_with_threshold`
- `get_norms_for_entity`, `find_related_entities`

Если задан `openai_api_key`, query embeddings строятся через OpenAI (`text-embedding-3-large` по умолчанию).

## Эксплуатационные заметки

- Обязателен `lex_knowledge_graph.duckdb`.
- HNSW/NPZ индексы опциональны: без них vector search вернет пустые списки, text/structured search останется рабочим.
- `hybrid_search` без embeddings автоматически деградирует в text-only.
- Для закрытия ресурса используйте `LegalKnowledgeGraph.close()`.

## Связи

- Upstream: `policy-engine/src/polisyos/lex/batch`.
- Re-export: `LegalKnowledgeGraph` доступен через `polisyos.lex`.
- Этот же DuckDB может использоваться мостом transport constraints (`lex.legal_evaluation.transport_constraints`).
