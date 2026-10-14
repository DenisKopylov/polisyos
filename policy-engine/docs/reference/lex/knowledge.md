# Lex Knowledge

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Freshness: 2026-10-14
Owner: `@lex-owners` for runtime reads and the local amendment-window receipt; `@data-forge-owners` for published legal graph and embedding-generation production.
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `src/polisyos/lex/knowledge/search.py`, `src/polisyos/lex/knowledge/store.py`, `src/polisyos/lex/knowledge/types.py`, `src/polisyos/data_forge/read_api/legal.py`, `src/polisyos/core/contracts/epoch.py`, `src/polisyos/runtime/quality/semantic_epoch.py`, and the named tests below.
Evidence level: source and named test behavior were inspected at the source pin; tests were inspected, not run for this documentation refresh. Local fixture checks do not establish official-source completeness or issuer authentication.

`LegalKnowledgeGraph` and `LegalKnowledgeStore` provide runtime read access to Data Forge's published legal graph. The DuckDB connection is opened read-only. Search matches, trust-tier filters, and vector similarity are retrieval signals; they do not verify an institution's act or turn candidate facts into legal authority.

## Search surfaces

| Surface | Entry points | Behavior and limits |
| --- | --- | --- |
| Vector search | `search_entities()`, `search_facts()`, `search_provisions()` | Requires a selected, complete, content-compatible local embedding generation and a compatible query profile/runtime bundle. A configured model label or API key alone does not admit vectors; unsupported requests raise a typed `LegalQueryProfileError`. |
| Hybrid fact search | `hybrid_search()` | Fuses vector and text results when vector admission succeeds. On typed vector refusal, returns the text results and retains the refusal on `query_profile_error`. |
| Text search | `text_search()` / `text_search_facts()` | Searches normalized fact text through DuckDB; it remains available without an admitted vector query. |
| Structured action search | `search_facts_by_action()` | Filters facts using the canonicalized legal action. This is a retrieval filter, not an official legal classification. |

The embedding admission path checks the selected generation against current graph members and its recorded encoder basis. See `src/polisyos/lex/knowledge/store.py` and `src/polisyos/data_forge/read_api/legal.py`; a present index file or a matching model name is not enough. The `grounded_fact` default trust filter is also a local graph field, not issuer authentication.

## Amendment-window receipt

`LegalKnowledgeStore.resolve_amendment_window_denominator()` is a local owner-side producer for semantic-epoch admission. It reads every row from the local `lex_amendments` table, derives amendment windows with the next amendment's start as the end, joins the local scope values from `lex_facts`, and returns a content-addressed owner snapshot plus a typed `LegalAmendmentWindowDenominatorReceipt`. It does not mutate the DuckDB source. Missing owner tables and unresolved or ambiguous inputs produce an unresolved receipt with failure codes; unresolved rows stay in the declared denominator rather than disappearing.

The query keeps three coordinates distinct: the valid-effect date, the visibility knowledge cutoff, and the purpose-admission cutoff. Each row is considered visible only when its local `created_at` is no later than both cutoffs. The valid-effect window is half-open (`effective_from <= valid_effect_date < effective_to`); an absent end is open-ended. This is separate from the inclusive active-version window described in [NormPack](normpack.md#time-identity-and-replay).

`LexEpochBoundaryOwnerAdapter` reloads the receipt's snapshot, admits the exact bytes into the task artifact store, checks the content address, reconciles the assessment set and computed denominator against those bytes, and persists the receipt before returning the boundary batch. The `independently_reconciled` label is bounded to the receipt versus that local owner snapshot. It does not establish that the local tables contain every institution-published amendment, nor does it authenticate an issuer.

## Reference

::: polisyos.lex.knowledge.search

::: polisyos.lex.knowledge.store

::: polisyos.lex.knowledge.types

## Code-inspected evidence

- Search admission and fallback: `src/polisyos/lex/knowledge/search.py`, `src/polisyos/lex/knowledge/store.py`, `tests/unit/remediation/test_emb_03.py::test_missing_and_mixed_intent_refuse_all_vector_tables_before_encode`, `tests/unit/remediation/test_emb_03.py::test_fresh_intent_still_requires_runtime_material_before_vector_search`, `tests/unit/remediation/test_emb_03.py::test_query_encoder_assets_must_match_before_encoding`, and `tests/unit/lex/test_knowledge_store_filters.py::test_legal_knowledge_store_hides_temporal_unknown_rows_for_as_of`.
- Local receipt and time cutoffs: `src/polisyos/lex/knowledge/store.py`, `src/polisyos/core/contracts/epoch.py::LegalAmendmentWindowDenominatorReceipt`, `tests/unit/lex/test_knowledge_store_filters.py::test_retroactive_row_differs_before_and_after_knowledge_cutoff`, `tests/unit/lex/test_knowledge_store_filters.py::test_missing_amendment_effective_window_stays_in_complete_denominator`, and `tests/unit/lex/test_knowledge_store_filters.py::test_unresolved_lex_window_partition_is_typed_and_verified`.
- Consumer-side snapshot reconciliation: `src/polisyos/runtime/quality/semantic_epoch.py::_verify_lex_snapshot`, `src/polisyos/runtime/quality/semantic_epoch.py::LexEpochBoundaryOwnerAdapter`, and the direct verifier calls in `tests/unit/lex/test_knowledge_store_filters.py::test_retroactive_row_differs_before_and_after_knowledge_cutoff`, `tests/unit/lex/test_knowledge_store_filters.py::test_missing_amendment_effective_window_stays_in_complete_denominator`, and `tests/unit/lex/test_knowledge_store_filters.py::test_unresolved_lex_window_partition_is_typed_and_verified`.
