# Docs (`polisyos.fabric.docs`)

`docs` - document pipeline that turns raw source bytes into normalized document
artifacts and world segments for downstream claim and world flows.

## Role in System

- **Depends on:** `polisyos.core.artifacts`, `polisyos.fabric.world`
- **Used by:** `fabric.claims` and world materialization pipelines
- Ensures document ingestion is deterministic, structured and traceable.

## Key Concepts

- **Four-stage pipeline** - ingest, normalize, structure, chunk.
- **Artifact outputs** - every stage emits CAS-backed refs and doc metadata.
- **MIME handling** - text/plain and text/html are native; PDF is stubbed in core.
- **World events** - document stages emit deterministic world events for lineage.

## Public API

| Type/Function | Description |
|---|---|
| `DocSourceSpec` | Source specification for document ingestion. |
| `DocIngestResult` | Result of document ingestion. |
| `DocNormalizeResult` | Result of document normalization. |
| `DocStructureResult` | Result of document structure extraction. |
| `DocChunkResult` | Result of document chunking. |
| `ingest_doc_bytes()` | Ingests raw document bytes. |
| `normalize_doc()` | Normalizes raw bytes into text. |
| `structure_doc()` | Extracts sections and anchors. |
| `chunk_doc()` | Splits structured docs into chunks. |

→ Full reference: [docs/reference/fabric/index.md](../../../../docs/reference/fabric/index.md)

## Current State

- Last updated: 2026-04-03
- Files: 11 Python files
- Exports: 17
