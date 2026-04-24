# Knowledge (`polisyos.lex.knowledge`)

`polisyos.lex.knowledge` дает read-only surface над legal knowledge graph,
построенным в `lex.batch`: typed entity/fact/provision models, DuckDB-backed
search store и high-level retrieval API для downstream legal, policy и search
flows.

## Роль в системе

- **Зависит от:** batch-generated DuckDB/HNSW artifacts, `polisyos.lex.batch`
- **Используется в:** `polisyos.lex`, `polisyos.lex.legal_evaluation`, downstream search and retrieval tooling
- Пакет изолирует query logic от batch-пайплайна и от прямой работы с DuckDB/HNSW файлами.

## Ключевые концепции

- **Typed graph models** — `LegalEntity`, `LegalFact`, `LegalProvision` и search result models нормализуют retrieval output.
- **Read-only store** — `LegalKnowledgeStore` открывает DuckDB в `read_only=True` и лениво подключает optional vector indexes.
- **Hybrid retrieval** — text, structured и vector search могут комбинироваться через `LegalKnowledgeGraph`.
- **Graph traversal** — API умеет искать related entities и нормы, а не только keyword matches.
- **Graceful degradation** — при отсутствии embeddings `hybrid_search()` и vector paths деградируют до text/structured search.

## Public API

| Type/Function                                                  | Description                                             |
| -------------------------------------------------------------- | ------------------------------------------------------- |
| `LegalKnowledgeGraph`                                          | High-level read-only API over the legal knowledge graph |
| `LegalEntity`, `LegalFact`, `LegalProvision`                   | Canonical graph record types                            |
| `LegalSearchResult`, `LegalFactResult`, `LegalProvisionResult` | Typed result envelopes for retrieval                    |
| `SPOCandidate`, `SPOExtractionResult`                          | Typed SPO-layer payloads reused by search and audits    |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 4 Python files
- Exports: 9 lazy exports in `__init__.py`
- Notable delta: store/search/types now cover expanded fact/entity search surface and richer traversal helpers
