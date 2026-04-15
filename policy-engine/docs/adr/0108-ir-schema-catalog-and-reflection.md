# ADR-0108: IR Schema Catalog and Reflection API

- Status: accepted
- Date: 2026-04-13
- Related: ADR-0005, ADR-0104, ADR-0107

## Context

IR surface area has grown beyond what tooling can safely understand via manual
grep or ad-hoc imports. Public/root facades, package facades, ABI snapshots,
and compatibility rules already exist, but they were split across:

- `polisyos.ir.__all__` and package-level `__all__`;
- `schemas/abi_models.py`;
- migration compatibility registry;
- hand-written docs pages in `docs/reference/ir/**`.

This left three gaps:

1. tooling could not enumerate all IR types and fields from one programmatic API;
2. docs drifted independently from runtime/export surface;
3. ABI snapshots and docs were updated by different workflows.

## Decision

We introduce a unified reflection layer in `polisyos.ir.schema_catalog` and use
it as the single source for generated IR reference pages.

The catalog:

- walks the importable `polisyos.ir` package tree;
- records type kind, module, current version, public status, export aliases,
  fields, IR refs, ABI snapshot linkage, and compatibility metadata;
- exposes stable tooling functions:
  `get_ir_schema_catalog()`, `list_ir_types()`, `get_ir_type()`,
  `inspect_ir_schema()`, and `enumerate_ir_exports()`.

`tools/diagnostics/gen_schema.py` now also regenerates/verifies:

- `docs/reference/ir/schema-catalog.md`
- `docs/reference/schemas.md`

This keeps ABI snapshots and reference docs synchronized through one build path.

## Consequences

### Positive

- Tooling can enumerate the full IR type surface without manual source scans.
- Docs and snapshot metadata now drift together instead of separately.
- Public/private status becomes queryable instead of implied by convention.
- Release review can inspect the same catalog used by docs/reference generation.

### Trade-offs

- Building the catalog imports the IR package tree, so reflection is not free.
- The generated reference page is large because it optimizes for completeness
  over hand-curated prose.

## Follow-up

- If the catalog becomes too expensive for CLI hot paths, we can cache a
  machine-readable export artifact in CI and reuse it for docs-only jobs.
