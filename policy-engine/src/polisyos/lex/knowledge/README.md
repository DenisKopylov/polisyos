# Knowledge (`polisyos.lex.knowledge`)

`polisyos.lex.knowledge` дает read-only surface над legal knowledge graph,
построенным Data Forge legal batch: typed entity/fact/provision models,
DuckDB-backed search store и high-level retrieval API для downstream legal,
policy и search flows.

## Роль в системе

- **Зависит от:** Data Forge generated DuckDB/HNSW artifacts
- **Используется в:** `polisyos.lex`, `polisyos.lex.legal_evaluation`, downstream search and retrieval tooling
- Пакет изолирует query logic от batch-пайплайна и от прямой работы с DuckDB/HNSW файлами.

## Ключевые концепции

- **Typed graph models** — `LegalEntity`, `LegalFact`, `LegalProvision` и search result models нормализуют retrieval output.
- **Read-only store** — `LegalKnowledgeStore` открывает DuckDB в `read_only=True` и лениво подключает optional vector indexes.
- **Hybrid retrieval** — text, structured и vector search могут комбинироваться через `LegalKnowledgeGraph`.
- **Graph traversal** — API умеет искать related entities и нормы, а не только keyword matches.
- **Content-bound vector queries** — `LegalKnowledgeGraph` передает Store текст, live local encoder и immutable requested generation snapshots. Store заново разрешает текущий selector, сверяет requested inventory с выбранным поколением, проверяет веса/tokenizer и сам строит нормализованный вектор.
- **Graceful degradation** — `hybrid_search()` использует text-only результат при отсутствии поддержанного профиля; прямые vector paths возвращают пустой список без encoder. Старый OpenAI key/model label не доказывает совместимость.
- **Chronology owner query** — `LegalKnowledgeStore` enumerates the complete
  `lex_amendments` denominator before applying sparse valid/effect and
  knowledge/admission cutoffs. Missing valid/effect carriers stay in the
  receipt as `amendment_valid_effect_window_unresolved`; transaction time is
  never substituted for owner semantics.

## Public API

| Type/Function                                                  | Description                                             |
| -------------------------------------------------------------- | ------------------------------------------------------- |
| `LegalKnowledgeGraph`                                          | High-level read-only API over the legal knowledge graph |
| `LegalQueryProfile` (`knowledge.store`)                         | Required immutable generation-intent type for vector requests |
| `LegalEntity`, `LegalFact`, `LegalProvision`                   | Canonical graph record types                            |
| `LegalSearchResult`, `LegalFactResult`, `LegalProvisionResult` | Typed result envelopes for retrieval                    |
| `search_legal_knowledge`                                       | Lex-owned grounded-fact CLI/search route                |

Для векторного поиска передавайте `query_encoder` с теми же локальными
weights/tokenizer и device, которыми построено выбранное поколение, и
`query_profile=(LegalQueryProfile.from_generation(selected_ref), ...)`.
`selected_ref` — существующий `EmbeddingGenerationRef` от canonical resolver,
зафиксированный как intent конкретного request/profile; implicit refresh из нового
selector не допускается. Только запрашиваемая таблица должна иметь ровно один
snapshot: empty/absent sibling tables не блокируют её поиск. `from_generation()`
замораживает intent, а не удостоверяет модель: Store проверяет текущие bytes и
принадлежность независимо. `embedding_model` внутри immutable inventory snapshot
задаёт desired model этого request; старый constructor `embedding_model` остаётся
deprecated compatibility label и не участвует в admission. Missing/malformed/unpaired/stale profile вызывает
`LegalQueryProfileError`; `hybrid_search()` сохраняет text fallback. Перед новой
generation нужен новый request snapshot, даже если assets и corpus не изменились.

Controlled fixture profile доказывает механизм pairing, но не production corpus,
качество semantic distances или legal authority. Поддержка model identity ограничена
canonical trusted encoder/library/config; digest weights/tokenizer не удостоверяет
произвольно подменённый `encode` callable. Production caller должен локально связать
actual effective request profile, generation/assets и live encoder provider.

Поколения
с rule version `policyos.legal.embedding.v1` не допускаются к vector search;
их нужно заново построить, чтобы записать текущую query-совместимость.

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-10-08
- Files: 5 Python files
- Exports: 11 lazy exports in `__init__.py`
- Notable delta: extraction payloads moved to `polisyos.data_forge.domains.legal.contracts`; Lex keeps runtime graph/search result models.

## Candidate multilingual assurance

`multilingual_assurance.py` extends Lex semantic evaluation with finite candidate rendition/action
comparison, content-bound CAS readback, empty-holder refusal and append-only invalidation. It reuses
`core.artifacts` integrity and strict Ed25519 verification; no signing or legal-equivalence authority
is produced. `locale_census.py` measures catalogue structure only and has an independently allocated
tool-side parser; exact agreement cannot establish translation quality. Named RTL source-content
pack `IL-Hebr` retains every WP-12 evidence slot empty and admits no locale or jurisdiction.
