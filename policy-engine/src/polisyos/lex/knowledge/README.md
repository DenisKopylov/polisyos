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
- **Content-bound vector admission** — `LegalQueryProfile` freezes the requested generation ID and full inventory bytes. Before encoding or native HNSW search, the Store resolves the current selector, verifies current projected members and matrix/index contents, and checks live encoder assets.
- **Explicit text fallback** — `hybrid_search()` returns its text results when vector admission refuses and retains the typed reason in `query_profile_error`. Direct vector methods raise `LegalQueryProfileError`; a missing vector result cannot be mistaken for an empty successful query.
- **Chronology owner query** — `LegalKnowledgeStore` enumerates the complete
  `lex_amendments` denominator before applying sparse valid/effect and
  knowledge/admission cutoffs. Missing valid/effect carriers stay in the
  receipt as `amendment_valid_effect_window_unresolved`; transaction time is
  never substituted for owner semantics.

## Public API

| Type/Function                                                  | Description                                             |
| -------------------------------------------------------------- | ------------------------------------------------------- |
| `LegalKnowledgeGraph`                                          | High-level read-only API over the legal knowledge graph |
| `LegalQueryProfile`, `LegalQueryInput`, `LegalQueryProfileError` | Immutable request intent and typed refusal for vector queries |
| `LegalEntity`, `LegalFact`, `LegalProvision`                   | Canonical graph record types                            |
| `LegalSearchResult`, `LegalFactResult`, `LegalProvisionResult` | Typed result envelopes for retrieval                    |
| `search_legal_knowledge`                                       | Lex-owned grounded-fact CLI/search route                |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

Vector callers pass a local `query_encoder` and the immutable profile snapshot
captured when the request selected its generation:
`query_profile=(LegalQueryProfile.from_generation(selected_ref), ...)`.
The profile is request intent, not evidence of currentness; the Store independently
reconciles the selected inventory against the database's complete projected member
set, the saved matrix, and HNSW vectors. Exactly one profile must match the queried
table. A new selector requires a fresh request profile, even when the corpus and
encoder assets are unchanged.

`derive_encoder_identity` recomputes loaded weights, configuration, and tokenizer assets. It
cannot attest an arbitrary replacement of the encoder's `encode` callable. The current
`LegalQueryEncoderProvider` checks those assets but does not resolve an owner-controlled executable
runtime bundle. The shared store therefore refuses every loaded object with
`query_encoder_runtime_material_not_established` before calling `encode`, after it revalidates the
selected generation, request intent, projected members, and asset identity. The guard covers entity,
fact, and provision vector searches;
`hybrid_search()` returns text results while retaining the typed refusal, and direct vector methods
raise `LegalQueryProfileError`.

The selected-generation GET remains available for immutable request intent; it does not claim that a
runtime encoder is available. POST `/api/v1/control/lex/search` reports `search_mode` and
`vector_refusal_code`; a selected generation with no source-resolved runtime profile returns actual
text-search results with `query_encoder_runtime_material_not_established`. Historical generations
remain readable and are not rewritten. Restoring vector execution requires an owner-resolved runtime
material binding shared by the producer and fresh reader; asset hashes or object labels alone do not
supply that binding. The controlled same-assets callable-swap test is a falsifier for the refusal
property, not a production or legal-authority claim.

## Current State

- Last updated: 2026-10-09
- Files: 8 Python files
- Exports: 14 lazy exports in `__init__.py`
- Notable delta: extraction payloads moved to `polisyos.data_forge.domains.legal.contracts`; Lex keeps runtime graph/search result models.

## Candidate multilingual assurance

`multilingual_assurance.py` extends Lex semantic evaluation with finite candidate rendition/action
comparison, content-bound CAS readback, empty-holder refusal and append-only invalidation. It reuses
`core.artifacts` integrity and strict Ed25519 verification; no signing or legal-equivalence authority
is produced. `locale_census.py` measures catalogue structure only and has an independently allocated
tool-side parser; exact agreement cannot establish translation quality. Named RTL source-content
pack `IL-Hebr` retains every WP-12 evidence slot empty and admits no locale or jurisdiction.
