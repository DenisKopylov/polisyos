# E2.8 (Phase 16) — Lex Corpus MVP v1.0

Repo snapshot date: 2026-02-04

## Scope

- New package: `policy-engine/src/polisyos/lex/*`
- New package: `policy-engine/src/polisyos/lex/corpus/*`
- New tests: `policy-engine/tests/fabric/test_lex_corpus_phase16.py`

## Deliverables

### 1) Legal ingestion wrapper on top of Fabric Docs

`ingest_legal_doc_bytes(...)` now provides:

- input from manual/local bytes
- strict source identity via `canonical_url` or `official_id`
- pass-through to Fabric Docs ingest/normalize/(optional structure/chunk)
- Lex metadata merge into `DocMeta.props["lex"]`
- DocMeta re-persist + `emit_doc_meta_facts(...)` re-emit
- Lex audit event (`EventKind.VALIDATE`) with pipeline metadata
- world segment write through World Store only

### 2) Citation-grade legal structure

`build_legal_structure(...)` now provides:

- jurisdiction rulesets: `UA`, `RU`, `EN`
- deterministic tiered extraction:
  - Tier A: article
  - Tier B: part / point / subpoint
  - Tier C (optional): paragraph
- offsets in python slice semantics
- deterministic `fragment_id = doc_fragment_id(doc_version_id, locator, text_hash)`
- CAS artifact `lex.corpus.provision_index`
- DocMeta update with:
  - `structure_algorithm_id`
  - `provision_index_ref`
  - `structure_pipeline`
- Lex structure world event (`EventKind.STRUCTURE_DOC`)

### 3) Version index and active version resolution

`build_version_index(...)` now provides:

- world-fact scan from `fact_log_root/world/*.parquet`
- discovery of doc versions via `world.rel.doc.has_version`
- latest meta resolution via `world.artifact_id` (last `tx_time`, then `fact_id`)
- extraction of temporal fields from `DocMeta.props["lex"]`
- CAS artifact `lex.corpus.version_index`
- pointer artifact `lex.corpus.doc_source_props`
- pointer publication through `world.props_ref` on `doc.source`
- validation world event

`resolve_active_version(...)` now provides:

- deterministic active selection on `as_of` date
- pointer lookup via strategy or `world.props_ref`
- fallback fact log root convention: `Path(cas.root).parent`
- explain trace with candidate filtering and tie-break details

## Persistence model

Lex Corpus uses only:

- CAS artifacts
- world facts
- world events

No Lex-specific DB/storage layer is introduced.

## Artifact contracts

- `lex.corpus.provision_index` (`polisyos.lex.corpus.ProvisionIndex`, v1.0)
- `lex.corpus.version_index` (`polisyos.lex.corpus.VersionIndex`, v1.0)
- `lex.corpus.doc_source_props` (`polisyos.lex.corpus.DocSourceProps`, v1.0)

## Determinism guarantees

- Fragment IDs are stable for identical `(doc_version_id, locator, normalized_ref)`.
- Re-running legal structure on same normalized text yields identical `fragment_id` sets.
- Version index payload is deterministic for unchanged facts/CAS state.
- Active version resolution is deterministic with fixed tie-break policy.

## D1-L4 Validation Links

| Link type           | Current anchor                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Source plan phase   | D1-L4 Phase 0 citation/world ID determinism and Phase 4 corpus-to-world bridge                                                               |
| Contract tests      | `tests/contract/test_world_abi_contract.py`, `tests/fabric/test_lex_corpus.py`, `tests/fabric/test_docs_pipeline.py`                         |
| Schema snapshots    | `schemas/snapshots/ir/doc_meta.schema.json`, `schemas/snapshots/ir/doc_fragment.schema.json`, `schemas/snapshots/ir/world_event.schema.json` |
| Generated reference | [IR Schema Catalog](../reference/ir/schema-catalog.md), [JSON Schema Catalog](../reference/schemas.md)                                       |
