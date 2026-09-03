# Extraction-strength vocabulary split journal

## Task 1 — typed envelope and legacy absence adapter

### Capability state

This delivery is deliberately `contract_only`: it adds a strict, frozen v2
vocabulary envelope, an explicit one-way legacy-absence adapter, and semantic
contract tests. No v2 producer, persisted v2 artifact, orchestration bridge,
consumer migration, verification receipt, or external surface is present.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: collection failed with two expected `ImportError` failures because
`ClaimVocabularyAxisStatus` did not yet exist in
`polisyos.ir.analytics.literature`. This is the intended missing-contract
failure for C03--C06, rather than an environment or syntax failure.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: `17 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/ir/analytics/literature.py tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py
```

Result: `All checks passed!`.

### C03--C06 coverage

- C03: a strict v2 payload rejects generic `strength`; the named adapter retains
  the raw legacy label and the envelope survives JSON round-trip validation.
- C04: legacy `moderate` retains only `legacy_strength_label`; all four typed
  axes are null and all four statuses are `not_established`.
- C05: the adapter accepts no parent-study-design or record-confidence argument,
  so neither can fill a claim-level axis.
- C06: design and evidence axes may be supplied independently only as explicit
  typed candidates; neither derives the other, and a shared `rct` spelling is
  still rejected under generic `strength`.

The unactivated-scope test also confirms that `WorkRecord.causal_claims` stays
`list[dict]` and `CausalClaim.from_payload()` remains on its existing v1 path.

### Exclusions held

No changes were made to lineage, adjudication authority types, Runtime,
producers, stores, graph code, `docs/plans/active/`, or `production_data`.
No production-data read, hash, migration, producer run, or bound debt-checker
run occurred.

## Task 1 review-fix — strict legacy input and sidecar semantics

### Decision

The v2 envelope is explicitly a vocabulary sidecar, not a general occurrence
transport. Task 2 must embed it beside the original occurrence in a lossless
composite transport. The absence adapter now validates a frozen, strict exact
legacy contract with only `cause`, `effect`, `direction`, `strength`, and
`mechanism`; missing, unexpected, and rich fields fail rather than being
manufactured or silently dropped.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: collection failed with the expected `ImportError` for the absent
`LegacyFiveFieldClaimOccurrence` input contract. This was the intended
missing-contract failure, not environment or syntax noise.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py -q
```

Result: `18 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check src/polisyos/ir/analytics/literature.py tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py tests/unit/ir/test_literature_contract.py
```

Result: `All checks passed!`; `git diff --check` also passed.

### Review-fix coverage

- The adapter rejects missing legacy fields, arbitrary extra fields, and rich
  claim fields, and validates no manufactured empty required input.
- A deliberately disagreeing design/evidence pair and all four candidate axes
  survive JSON round trip; changing any one axis leaves the other three stable.
- `WorkRecord.causal_claims` rejects a v2 envelope, while exact legacy JSON and
  `WorkRecord` JSON remain v1-shaped with no implicit adapter.

## Task 2 — inactive composite, serializers, and store preparation

### Capability state

This is `implemented_but_not_orchestrated` preparation. The frozen
`ClaimOccurrenceVocabularyTransport` retains the complete non-vocabulary
occurrence beside Task 1's strict `VersionedClaimVocabularyEnvelope`; no v2
artifact is emitted by a producer or persisted by a live writer.

### RED evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py tests/unit/data_forge/domains/academic/batch/test_parser.py tests/unit/data_forge/mirror_contracts/test_llm_extractor.py tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py -q
```

Result: collection reported the expected missing transport and serializer
imports. Follow-up boundary tests failed for the intended reasons: the future
deterministic serializer silently accepted generic `strength`; the rich
serializer promoted omitted Pydantic defaults; the snapshot helper accepted
only an artificial legacy mapping; and the exact persistence constants/projector
did not exist. These were product-contract REDs, not environment failures.

### GREEN evidence

From `policy-engine/`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/src" /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m pytest tests/unit/data_forge/domains/academic/knowledge/test_claim_occurrence_vocabulary_transport.py tests/unit/data_forge/domains/academic/batch/test_parser.py::test_future_deterministic_claim_serializer_keeps_abstract_basis_without_legacy_label tests/unit/data_forge/domains/academic/batch/test_parser.py::test_future_deterministic_claim_serializer_rejects_a_generic_strength_label tests/unit/data_forge/mirror_contracts/test_llm_extractor.py::test_future_llm_claim_serializer_keeps_named_candidate_axes_separate tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_rich_claim_serializer_preserves_metadata_and_does_not_borrow_record_confidence tests/unit/data_forge/domains/academic/batch/test_article_extractor_stage.py::test_rich_claim_serializer_keeps_omitted_pydantic_defaults_absent tests/unit/data_forge/domains/academic/batch/test_graph_builder_skg_tables.py::test_graph_writer_inactive_preflight_uses_the_shared_vocabulary_admission_callable tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_span_writer_inactive_preflight_reuses_the_graph_vocabulary_boundary tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_splits_only_exact_legacy_claim_occurrences tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_revalidates_an_actual_future_composite tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_rejects_rich_generic_strength_before_copy tests/unit/data_forge/domains/academic/batch/test_best_snapshot.py::test_snapshot_copy_preflight_rejects_a_duplicated_typed_vocabulary_key tests/unit/data_forge/domains/academic/batch/test_claim_vocabulary_contract.py::test_existing_v1_work_record_and_causal_claim_paths_are_not_activated -q
```

Result: `27 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/policy-engine/.venv/bin/python -m ruff check [Task-2 source and test paths]
git diff --check
```

Result: both passed. `uv run polisyos-tools architecture guardrails check` was
started but did not complete after several minutes and was terminated; it is
not pass/fail evidence.

### Task 3 activation handshake

- Shared frozen transport and mechanical re-admission owner:
  `ClaimOccurrenceVocabularyTransport` and
  `admit_candidate_claim_vocabulary` in `knowledge/types.py`.
- Future-only serializers: `serialize_deterministic_claim_occurrence_vocabulary`,
  `serialize_llm_claim_occurrence_vocabulary`, and
  `serialize_rich_claim_occurrence_vocabulary`.
- Both writer seams are the exact same callable:
  `graph_builder.preflight_candidate_claim_vocabulary` and
  `skg_store.preflight_candidate_claim_vocabulary` alias
  `admit_candidate_claim_vocabulary`. Snapshot copy preflight is
  `preflight_claim_occurrence_vocabulary_copy`; it re-admits a future composite
  and only adapts an exact legacy five-field occurrence.
- Exact inactive persistence layout: discriminator
  `claim_vocabulary_schema_version="2.0"`; ordered sidecar columns are
  `design_family_hint`, `design_family_hint_status`, `evidence_strength`,
  `evidence_strength_status`, `claim_extraction_confidence`,
  `claim_extraction_confidence_status`, `source_basis`, `source_basis_status`,
  `legacy_strength_label`, and `record_extraction_mode`. The pure
  `candidate_claim_vocabulary_store_values` re-admits before returning only
  those values and never returns generic `strength`.
- No-activation proof: `WorkRecord.causal_claims`, legacy parser/LLM append and
  JSONL, `_to_work_record` v1 output, graph DDL/batches/inserts,
  `_infer_edge_strength`, direct span ingest loop, and snapshot assembly/copy
  calls were not changed; the preflight tests call only inactive helpers.

### Pattern pass and exclusions

P01/P02 remain intentionally open until the atomic bridge and consumers land.
P04/P10/P15 are addressed locally by typed absence, independent candidate
axes, and no generic-label laundering. P27 is avoided by consuming Task 1's
sidecar rather than introducing another vocabulary DTO; P29/P33/P38 are covered
with runtime boundary falsifiers rather than source-marker tests.

No authority, receipt, publication, ranking, evaluator, Runtime, Foundry
catalogue, `docs/plans/active/`, or `production_data` path changed. The bound
debt checker was not run.
