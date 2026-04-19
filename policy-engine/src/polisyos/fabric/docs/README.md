# Docs (`polisyos.fabric.docs`)

`polisyos.fabric.docs` is the deterministic document pipeline that turns raw
source bytes into normalized document artifacts, structure metadata, chunks,
and world events.

Last updated: 2026-04-17.

## Purpose

Use this package when you need the first half of the document-to-claims flow:
ingest raw bytes, normalize them, extract structure, and create deterministic
chunk artifacts that downstream claim extraction can consume.

## Where to Start

- Read [__init__.py](./__init__.py) and [types.py](./types.py) for the exported
  document-pipeline surface.
- Read [ingestion.py](./ingestion.py), [normalize.py](./normalize.py),
  [structure.py](./structure.py), and [chunking.py](./chunking.py) for the
  four-stage pipeline.
- Read [backends/text_plain.py](./backends/text_plain.py),
  [backends/text_html.py](./backends/text_html.py), and
  [backends/pdf.py](./backends/pdf.py) for MIME-specific normalization
  behavior.
- Follow downstream links to [../claims/README.md](../claims/README.md) and
  [../world/README.md](../world/README.md), then read the docs-pipeline
  contract linked below.

## Public Entrypoints

| Entrypoint | Description |
|---|---|
| `DocSourceSpec` | Public source specification for document ingestion. |
| `ingest_doc_bytes()` | Persist raw bytes and emit the initial document provenance event. |
| `normalize_doc()` | Normalize raw bytes into canonical text. |
| `structure_doc()` | Extract sections, anchors, and structure metadata. |
| `chunk_doc()` | Produce deterministic chunk artifacts over structured text. |
| `DocIngestOptions`, `DocNormalizeOptions`, `DocStructureOptions`, `DocChunkOptions` | Stage-specific pipeline controls. |
| `DocIngestResult`, `DocNormalizeResult`, `DocStructureResult`, `DocChunkResult` | Result wrappers carrying artifact ids and world-event ids. |
| `DocPipelineError` and related errors | Typed failure surface for unsupported MIME, invalid payloads, and incomplete stage dependencies. |

## Depends On / Depended On By

- Depends on: `polisyos.core.artifacts`, `polisyos.fabric.world`,
  `polisyos.ir.world.doc`, and the backend modules in this package.
- Depended on by: `polisyos.fabric.claims`, `polisyos.scholar.orchestrator.enrich`,
  `polisyos.scholar.discover.*`, `polisyos.lex.corpus.ingest`, and
  `polisyos.lex.types`.

## Common Commands

Run from the repository root (`policy-engine/`).

- `rg -n "ingest_doc_bytes|normalize_doc|structure_doc|chunk_doc" src/polisyos/fabric/docs tests/fabric/test_docs_pipeline.py`
  Jump to the four-stage pipeline and its primary tests. Smoke-tested on
  2026-04-17.
- `rg -n "text/plain|text/html|pdf" src/polisyos/fabric/docs src/polisyos/fabric/docs/backends`
  Inspect MIME handling and backend selection. Smoke-tested on 2026-04-17.
- `rg --files src/polisyos/fabric/docs/backends | sort`
  Survey the currently shipped backend implementations. Smoke-tested on
  2026-04-17.

## Test / Verification Commands

Run from the repository root (`policy-engine/`).

- `uv run pytest tests/fabric/test_docs_pipeline.py tests/fabric/test_text_html.py -q`
  Docs pipeline and HTML backend smoke suite. Smoke-tested on 2026-04-17.
- `uv run pytest tests/fabric/test_claims_pipeline.py -q`
  Downstream integration check proving the emitted doc artifacts are consumable
  by the claims pipeline. Conceptual in this README refresh; not run in this
  pass.

## Reference Docs

- [Fabric data-plane reference](../../../../docs/reference/fabric/data-plane.md)
- [Fabric reference index](../../../../docs/reference/fabric/index.md)
- [E2.5 Fabric Docs Pipeline contract](../../../../docs/contracts/E2_5_FABRIC_DOCS_PIPELINE_V1_0.md)
- [Retained artifact recovery runbook](../../../../docs/runbooks/retained-artifact-recovery.md)
- [Fabric tests map](../../../../tests/fabric/README.md)
