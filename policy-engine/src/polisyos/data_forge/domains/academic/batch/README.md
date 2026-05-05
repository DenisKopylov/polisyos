# Academic Batch (`polisyos.data_forge.domains.academic.batch`)

`polisyos.data_forge.domains.academic.batch` is the staged pipeline that turns
OpenAlex-selected literature into an academic/SKG graph. It runs in a
fulltext-first mode, keeps extraction deterministic where possible, and writes
publish-ready DuckDB and manifest artifacts.

## Role in System

- **Depends on:** `data_forge.kernel`, `core.canon`, `ir.analytics`, and
  `data_forge.domains.academic.openalex`.
- **Used by:** `data_forge.domains.academic.knowledge` and downstream
  discovery / prior-selection workflows.
- **Boundary function:** separates build-time harvesting/extraction from read-only graph access.

## Key Concepts

- **Staged pipeline** - topic selection, harvest, parse, resolve/extract, merge/dedup, graph load/index, embed, QC, publish.
- **Extraction planning** - `AcademicBatchConfig` keeps the batch inputs and runtime knobs used by the staged pipeline.
- **Fulltext-first resolve** - `resolve_extract.py` streams eligible papers, uses a lazy JSONL index, and keeps dispatch backpressure bounded.
- **Deterministic publish gates** - publish only happens after QC and readiness thresholds are satisfied.
- **Graph materialization** - `graph_builder.py` writes both runtime tables and SKG tables.

## Public API

- configuration: `AcademicBatchConfig`, `ALL_STAGES`, `DEFAULT_RUN_STAGES`
- CLI: `run`, `topic-select`, `resolve-extract`, `graph-load`, `qc`, `publish`, `stats`, `search`, `prior`
- orchestration modules: `pipeline.py`, `resolve_extract.py`, `graph_builder.py`, `publish.py`, `qc.py`

## Current State

- Last updated: 2026-04-03
- Data Forge Phase 8 physically removed the old `polisyos.academic` namespace;
  this package is now the canonical implementation owner.
- `resolve_extract.py` now uses `_LazyJsonlDict` for the precomputed fulltext cache and adds bounded bounce/backpressure handling.
- `claim_adjudicator.py` now routes LLM adjudication through the multi-key pool and uses more explicit design-tier scoring.
