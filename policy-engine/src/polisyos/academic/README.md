# Academic (`polisyos.academic`)

`polisyos.academic` is the offline academic knowledge-graph stack. It combines OpenAlex-based
topic selection, staged extraction/publishing, and a read-only SKG query layer for literature,
causal evidence, and parameter priors.

## Role in System

- **Depends on:** `batch_common`, `core.canon`, and `ir.analytics` for snapshot layout, stable ids, and evidence contracts.
- **Used by:** `scientist`, `fabric`, and the academic runtime/query path.
- **Boundary function:** separates batch graph construction from read-only knowledge access.

## Key Concepts

- **OpenAlex selection** - topic-driven harvesting starts with cataloged topic files and selection heuristics.
- **Fulltext-first extraction** - `resolve_extract` streams eligible papers, uses lazy JSONL reads, and keeps one extraction call per paper.
- **DuckDB + HNSW** - the built graph supports both deterministic table lookup and semantic search.
- **Canonical variables** - `knowledge` owns canonicalization, runtime aliasing, and transportability-aware selection.
- **Trust scoring** - `trust.py` and batch adjudication turn design signals into usable literature confidence.

## Public API

- `batch/README.md`
- `knowledge/README.md`
- `openalex/README.md`
- package helpers in `trust.py`

## Current State

- Last updated: 2026-04-03
- `resolve_extract.py` now uses a lazy JSONL index and bounce/backpressure control for paper dispatch.
- `claim_adjudicator.py` and `runtime_canonical_registry.py` both expanded their policy heuristics and canonical alias coverage.
