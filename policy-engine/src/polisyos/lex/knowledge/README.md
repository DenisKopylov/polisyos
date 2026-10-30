# Knowledge (`polisyos.lex.knowledge`)

`polisyos.lex.knowledge` provides a read-only surface over the legal knowledge graph
built by the Data Forge legal batch: typed entity/fact/provision models, a
DuckDB-backed search store, and a high-level retrieval API for downstream legal,
policy, and search flows.

## Role in the system

- **Depends on:** Data Forge-generated DuckDB/HNSW artifacts
- **Used by:** `polisyos.lex`, `polisyos.lex.legal_evaluation`, downstream search, and retrieval tooling
- The package isolates query logic from the batch pipeline and direct access to DuckDB/HNSW files.

## Key concepts

- **Typed graph models** — `LegalEntity`, `LegalFact`, `LegalProvision`, and search-result models normalize retrieval output.
- **Read-only store** — `LegalKnowledgeStore` opens DuckDB with `read_only=True` and lazily connects optional vector indexes.
- **Hybrid retrieval** — text, structured, and vector search can be combined through `LegalKnowledgeGraph`.
- **Graph traversal** — the API can find related entities and norms, not only keyword matches.
- **Content-bound vector admission** — `LegalQueryProfile` freezes the requested generation ID and full inventory bytes. Before encoding or native HNSW search, the Store resolves the current selector, verifies current projected members and matrix/index contents, and checks the recomputed live model state and installed runtime profile. Strict identity hashes only views of contiguous CPU `torch.Tensor` storage or C-contiguous NumPy arrays; it refuses other array-like values without conversion. The bounded candidate claim assumes a trusted process: no concurrent external model/runtime mutation during a lease, and no mutation of callable globals or closure state while the profile is admitted. The handle lock serializes owner leases but does not make pre/post hashes atomic against mutation and restoration; untrusted in-process plugins are outside scope.
- **Explicit text fallback** — `hybrid_search_with_status()` returns results with the typed outcome from that same invocation, so concurrent consumers cannot exchange refusals through shared graph state. The list-returning `hybrid_search()` remains available and keeps `query_profile_error` as a legacy latest-call diagnostic. Direct vector methods raise `LegalQueryProfileError`; a missing vector result cannot be mistaken for an empty successful query.
- **Chronology owner query** — `LegalKnowledgeStore` enumerates the complete
  `lex_amendments` denominator before applying sparse valid/effect and
  knowledge/admission cutoffs. Missing valid/effect carriers stay in the
  receipt as `amendment_valid_effect_window_unresolved`; transaction time is
  never substituted for owner semantics.

## Public API

| Type/Function                                                    | Description                                                   |
| ---------------------------------------------------------------- | ------------------------------------------------------------- |
| `LegalKnowledgeGraph`                                            | High-level read-only API over the legal knowledge graph       |
| `LegalKnowledgeStore`                                            | Read-only owner store for typed legal queries and evaluations |
| `LegalQueryProfile`, `LegalQueryInput`, `LegalQueryProfileError` | Immutable request intent and typed refusal for vector queries |
| `LegalEntity`, `LegalFact`, `LegalProvision`                     | Canonical graph record types                                  |
| `LegalSearchResult`, `LegalFactResult`, `LegalProvisionResult`   | Typed result envelopes for retrieval                          |
| `search_legal_knowledge`                                         | Lex-owned grounded-fact CLI/search route                      |

Full reference: [docs/reference/lex/](../../../../docs/reference/lex/index.md)

Vector callers pass a `query_runtime_material_owner` and the immutable profile snapshot
captured when the request selected its generation:
`query_profile=(LegalQueryProfile.from_generation(selected_ref), ...)`.
The profile is request intent, not evidence of currentness; the Store independently
reconciles the selected inventory against the database's complete projected member
set, the saved matrix, and HNSW vectors. Exactly one profile must match the queried
table. A new selector requires a fresh request profile, even when the corpus and
encoder assets are unchanged.

`derive_encoder_identity` recomputes loaded weights, configuration, and tokenizer assets. It
cannot attest an arbitrary replacement of the encoder's `encode` callable. Legacy user-supplied
encoders therefore remain candidates only. A `LegalRuntimeMaterialOwner` is the narrow positive
path: it resolves the exact named local model revision and supported installed runtime, derives an
owner-issued handle, and binds the recomputed material digest into each Legal generation rule. The
shared store checks that binding after request, selected-generation, and projected-member checks,
then captures and invokes the checked owner method under its lease. Entity, fact, and provision
vector methods use this same gate.

The v2 owner profile remeasures named parameters and buffers, module training/configuration state,
tokenizer state, effective encode settings, and the installed runtime both before and after every
leased encode. CPU tensor bytes are streamed from contiguous storage views; unsupported layouts
refuse instead of copying weights. Generic state-dictionary identities used by other producers
remain unchanged and do not acquire the Legal owner's runtime meaning.

The selected-generation GET remains an immutable request-intent snapshot; it does not claim model or
deployment currentness. A controlled owner may return vector results only when its recomputed
material matches the producer's persisted binding. HTTP POST reports `search_mode` and
`vector_refusal_code`; when the runtime or generation binding is unavailable or mismatched, its
existing hybrid route returns actual text results with the typed refusal. Direct vector methods raise
`LegalQueryProfileError` and do not fall back to text. Historical generations remain readable and
vector-refused; they are never rewritten. This local controlled profile does not establish L01/L02
production selection, deployment currentness, reuse permission, G status, or legal authority. The
same-assets callable-swap and matched-removal witness tests the executable behavior boundary.

A historical flat NPZ/HNSW pair has no selected, content-bound generation and is not
reused for a current vector query. An incremental rebuild projects the current database
members and publishes a selected generation; callers then obtain a fresh request snapshot.
Changed projected text or withdrawn members make the previous generation inadmissible.

The portable regression uses a locally generated SentenceTransformer fixture and a test-only
reduced distribution root. It exercises the owner, producer, selected reader and HTTP search
with their checks enabled, but does not establish production model provenance, a full production
runtime closure, source-law verification, issuer authority, or legal currentness.

## Current State

- Last updated: 2026-10-09
- Files: 8 Python files
- Exports: 15 lazy exports in `__init__.py`
- Notable delta: extraction payloads moved to `polisyos.data_forge.domains.legal.contracts`; Lex keeps runtime graph/search result models.

## Candidate multilingual assurance

`multilingual_assurance.py` extends Lex semantic evaluation with finite candidate rendition/action
comparison, content-bound CAS readback, empty-holder refusal and append-only invalidation. It reuses
`core.artifacts` integrity and strict Ed25519 verification; no signing or legal-equivalence authority
is produced. `locale_census.py` measures catalogue structure only and has an independently allocated
tool-side parser; exact agreement cannot establish translation quality. Named RTL source-content
pack `IL-Hebr` retains every WP-12 evidence slot empty and admits no locale or jurisdiction.

The semantic-epoch bridge persists each verified amendment row as canonical owner JSON with a
selected CAS profile. `amended_doc_ref` remains a typed hash of the owner-held document ID string;
it is checked against the row and never materialized or treated as document content. Missing
external legal-source bytes remain a limitation of that evidence chain.

The semantic-epoch adapter validates an amendment ref as `lex.amendment` from its canonical source
row before codec dispatch. A same-ID `l5.schema_regime` ref is refused before CAS admission. The
document identifier stays an identity token, not document content.

Every `ArtifactRef` field in the typed amendment receipt is checked against its source-row role;
the snapshot graph rejects unregistered ref paths. The document ref is still only an identity token,
so this bridge establishes no document-byte evidence or legal authority.
