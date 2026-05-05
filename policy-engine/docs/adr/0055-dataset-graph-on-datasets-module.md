# ADR-0055: Dataset Graph Built on the Datasets Module

## Status

Proposed

Status note (2026-05-02): superseded for code ownership by Data Forge; use
`polisyos.data_forge.domains.catalog.knowledge` and
`polisyos.data_forge.read_api.catalog`.

## Date

2026-02-28

## Context

The Dataset Graph tracks variable availability, measurement quality, and temporal coverage
across ingested datasets for each context (country, region, institution). Like the SKG
decision (ADR-0054), this graph needs a module home. The `datasets/` module already handles
source registration, harvesting, normalization, and variable alignment -- all prerequisite
operations for building the Dataset Graph.

## Decision

1. The Dataset Graph is implemented within `polisyos.datasets.knowledge`, not as a separate
   top-level package.
2. Key components are: `registry.py` (variable-to-dataset mapping), `variable_alignment.py`
   (canonical variable alignment with SKG), and `proxy_resolver.py` (proxy variable
   identification and reliability scoring per ADR-0050).
3. The `datasets.batch` pipeline populates the Dataset Graph during source ingestion; the
   `datasets.knowledge` layer provides the query API consumed by transport analysis.
4. Import gates ensure that Dataset Graph internals are accessed only through the public
   `datasets.knowledge` API by external modules.
5. Symmetric with ADR-0054: both knowledge graphs live in their respective domain modules,
   and the transport layer federates across them at query time (ADR-0047).

## Consequences

### Positive

- Symmetric architecture with SKG (ADR-0054) makes the codebase predictable: each knowledge
  graph lives in its source domain module.

- Natural colocation with the harvesting and normalization pipeline that feeds the graph.
- Import gates provide the same extraction-ready boundary as the SKG module.

### Negative

- The `datasets/` module takes on additional responsibility beyond raw data management.
- Variable alignment between Dataset Graph and SKG must be kept consistent, requiring
  coordination between the two modules via the `variable_canonizer`.

- Future data sources that do not fit the current `datasets/` ingestion model may require
  architectural rethinking.
