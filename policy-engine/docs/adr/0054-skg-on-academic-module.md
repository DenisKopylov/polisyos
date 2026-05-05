# ADR-0054: SKG Built on the Academic Module

## Status

Proposed

Status note (2026-05-02): superseded for code ownership by Data Forge; use
`polisyos.data_forge.domains.academic.knowledge` and
`polisyos.data_forge.read_api.academic`.

## Date

2026-02-28

## Context

The Scientific Knowledge Graph (SKG) aggregates causal evidence from academic literature.
It needs a module home in the codebase. Two options were considered: a standalone `skg/`
top-level package, or building SKG functionality on top of the existing `academic/` module
which already handles OpenAlex ingestion, article extraction, and scholarly knowledge queries.
A separate package would add import complexity and create an artificial boundary between
closely related concerns.

## Decision

1. SKG is implemented as sub-modules within `polisyos.academic.knowledge`, not as a separate
   top-level `skg/` package.
2. The key SKG components are: `skg_store.py` (DuckDB storage layer), `skg_versioning.py`
   (version tracking per ADR-0043), `skg_query.py` (query interface), and
   `canonical_seed.py` (initial variable/edge seeding).
3. The `academic.batch` pipeline writes to SKG via `skg_store`; the `academic.knowledge`
   layer reads from SKG via `skg_query`.
4. Import gates in `architecture/imports/policy.toml` ensure that SKG internals (store, versioning) are not
   directly accessed by modules outside `academic/`; other modules use the `skg_query` public
   API.
5. This decision may be revisited if SKG grows large enough to warrant extraction, but the
   import gate boundary makes future extraction straightforward.

## Consequences

### Positive

- Natural colocation: SKG lives next to its primary data source (OpenAlex/article extraction).
- No new top-level package means simpler dependency graph and import structure.
- Import gates provide a clean public API boundary that enables future extraction if needed.

### Negative

- The `academic/` module becomes larger and more complex, potentially harder to navigate.
- Developers unfamiliar with the codebase may not intuitively look in `academic/` for graph
  storage functionality.

- If non-academic knowledge sources contribute to SKG in the future, the module name becomes
  slightly misleading.
