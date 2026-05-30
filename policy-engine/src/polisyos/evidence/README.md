# Evidence (`polisyos.evidence`)

## Purpose

`polisyos.evidence` owns internal evidence-graph records that are shared across
Policy Design Case portfolio producers. It is not a public authority surface;
records here must be consumed by runtime or Scientist bridges before they can
affect claim closure, portfolio inspection, or projections.

## Where To Start

- [`portfolio/conflict_records.py`](portfolio/conflict_records.py): W8.E
  first-class conflict records and portfolio conflict index.
- [`portfolio/effective_independence_graph.py`](portfolio/effective_independence_graph.py):
  W8.F hard-collapse, feature-flagged graded dependence, scarcity path, and
  graph annotation over W4.B evidence portfolio lines.

## Boundary Notes

- Conflict records are authoritative only for conflict materialization.
- Conflict records may not be counted as positive support strength.
- Effective-independence graphs keep raw evidence counts diagnostic-only and
  preserve counterevidence mass separately from support.
- Downstream consumers must bind them through claim-registry `conflict_refs`
  / `effective_independence_refs` and portfolio indexes before using them as
  closeout or audit evidence.

## Last Updated

- Last updated: 2026-05-24
