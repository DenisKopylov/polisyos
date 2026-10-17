# Corpus (`polisyos.data_forge.domains.legal.corpus`)

`polisyos.data_forge.domains.legal.corpus` prepares the legal corpus for downstream legal
pipelines: document ingestion, structure extraction, and version-aware indexes
through which `normpack` and `legal_evaluation` resolve the active document
version instead of selecting one ad hoc by date or ID.

## Error ownership

Legal corpus workflows use the Data Forge legal exception hierarchy defined in
`../contracts.py`. These classes retain their existing stage, category, and
source/version metadata behavior, and remain separate from the runtime Lex
exception hierarchy.

## Role in the system

- **Depends on:** `polisyos.fabric.docs`, `polisyos.fabric.world`, `polisyos.core.artifacts`, `polisyos.ir.world`
- **Used by:** `polisyos.lex.normpack`, `polisyos.lex.legal_evaluation`, intervention and provenance flows
- The package produces canonical corpus artifacts: a provision index, version index, and document source properties.

## Key concepts

- **Ingestion wrapper** — `ingest_legal_doc_bytes()` enriches `DocMeta.props.lex`, records pipeline metadata, and writes world events.
- **Structure extraction** — `build_legal_structure()` builds the `article -> part -> point -> subpoint` hierarchy and publishes `ProvisionIndexV1`.
- **Temporal versioning** — `build_version_index()` and `resolve_active_version()` use an effective window instead of falling back to an arbitrary published version.
- **Index artifacts** — `ProvisionIndexV1`, `VersionIndexV1`, and `DocSourcePropsV1` remain the CAS-friendly surface between ingestion and normpack.
- **Quality issues** — duplicate articles, non-monotonic numbering, and missing structure remain explicit quality markers rather than being hidden by heuristic rewrites.

## Public API

| Type/Function                                            | Description                                                          |
| -------------------------------------------------------- | -------------------------------------------------------------------- |
| `ingest_legal_doc_bytes()`                               | Ingest legal document bytes and enrich Lex corpus metadata           |
| `build_legal_structure()`                                | Extract legal structure and persist `ProvisionIndexV1`               |
| `build_version_index()`                                  | Build `VersionIndexV1` and `DocSourcePropsV1` from fact-log evidence |
| `resolve_active_version()`                               | Resolve the active document version using temporal envelopes         |
| `ProvisionIndexV1`, `VersionIndexV1`, `DocSourcePropsV1` | Persistent corpus index artifacts                                    |
| `load_*()` / `persist_*()` helpers                       | CAS persistence helpers for corpus indexes                           |

Full reference: [docs/reference/lex/](../../../../../../docs/reference/lex/index.md)

## Current State

- Last updated: 2026-05-02
- Files: 5 Python files
- Exports: 15 symbols in `__init__.py`
- Notable delta: `versioning.py` now requires resolved temporal envelopes and no longer silently falls back to `published_at`
