# Lex Knowledge

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Owner: `@lex-owners`
Source of truth: `src/polisyos/lex/knowledge/**`, `src/polisyos/lex/__init__.py`, and the current package facade documented on `docs/reference/lex/index.md`

The knowledge layer exposes read-only legal search over DuckDB tables and HNSW
vector indexes. It is the runtime search surface used by legal evaluation,
retrieval, and grounding workflows.

## Components

| API                   | Role                                                   |
| --------------------- | ------------------------------------------------------ |
| `LegalKnowledgeGraph` | High-level hybrid search facade                        |
| `LegalKnowledgeStore` | Read-only persistence adapter over DuckDB and indexes  |
| `lex.knowledge.types` | Search result, source-bundle, and SPO result contracts |

## Search Modes

| Mode                     | Entry point                                                  | Notes                                    |
| ------------------------ | ------------------------------------------------------------ | ---------------------------------------- |
| Hybrid/vector            | `search_entities()`, `search_facts()`, `search_provisions()` | Uses embeddings when configured          |
| Text search              | `text_search()`                                              | DuckDB `ILIKE` over normalized fact text |
| Structured action search | `search_facts_by_action()`                                   | Filters by canonicalized legal action    |

## Reference

::: polisyos.lex.knowledge.search

::: polisyos.lex.knowledge.store

::: polisyos.lex.knowledge.types
