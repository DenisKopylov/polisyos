# Datasets (`polisyos.datasets`)

`polisyos.datasets` is the dataset catalog stack. It owns staged catalog construction, the read-only
knowledge layer, and the lightweight metric-mapping helper that keeps PolicyOS variable names aligned
with external data sources.

## Role in System

- **Depends on:** `batch_common`, `fabric.connectors`, and the dataset registry/knowledge helpers.
- **Used by:** `scientist`, `fabric`, and transportability-oriented workflows.
- **Boundary function:** separates dataset catalog building from catalog querying and selection.

## Key Concepts

- **Batch build** - raw sources are normalized, merged, embedded, QCed, benchmarked, and published.
- **Knowledge layer** - read-only search and registry access live in `datasets.knowledge`.
- **Transportability support** - registry tables and observation alignments feed `P*(Z)`/proxy selection.
- **Metrics mapping** - `metrics_map.py` links PolicyOS canonical metrics to external dataset names.

## Public API

- `batch/README.md`
- `knowledge/README.md`
- `metrics_map.py`

## Current State

- Last updated: 2026-04-03
- The batch stack now carries observation-mode settings, richer benchmark metrics, and readiness gating tied to core ingest state.
- `datasets.knowledge.variable_alignment` continues to use the academic runtime canonical registry for name normalization.
