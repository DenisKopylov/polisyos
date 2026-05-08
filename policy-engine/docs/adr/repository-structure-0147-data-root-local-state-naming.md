# ADR-RSR-0147: Data Root Local State Naming

## Status

Accepted

## Date

2026-05-08

## Context

The repository has a single product root at `policy-engine/`, and inside that
root the canonical data surface is `data/`. The path
`data/policy-engine-local/` predates the final single-root decision and can look
like a nested second product root even though it is only an ignored local data
lake for raw extracts, curated materializations, and local databases.

Renaming the path now would churn local data commands, rsync excludes, data
policy tests, and developer working copies while providing little product
benefit. Removing it would also remove the documented local data lake home used
by Data Forge replay and acceptance workflows.

## Decision

1. Keep `data/policy-engine-local/` as an ADR-backed legacy local-state name.
2. Treat the name as a local data lake namespace inside the canonical `data/`
   root, not as a second product root and not as committed product data.
3. Keep only `data/policy-engine-local/README.md` commit-eligible. The
   `raw/`, `curated/`, and `databases/` children remain ignored local state.
4. Keep `architecture/policies/data.toml` as the source of truth for the local
   data lake path and cleanup commands.
5. Register the exception in `architecture/policies/directory_contracts.toml` and
   `architecture/asset_placement.toml` so source, fixture, and workspace tooling
   references have an explicit contract.
6. New committed fixtures must not use `data/policy-engine-local/`. Promote
   reusable data by reducing it to an allowlisted fixture, manifest, registry
   entry, test fixture under `tests/_data/`, or generated-artifact family.
7. A future rename is allowed only as a serialized data-root migration that
   updates data policy, workspace tooling excludes, documentation, and tests in
   the same change.

## Consequences

The repository keeps path compatibility for local Data Forge workflows without
weakening the single-root product policy. Reviewers can distinguish the local
lake from committed data because the exception is ADR-backed, machine-readable,
and documented at the path itself.

The cost is that the legacy name remains visible. That cost is bounded by the
contract: only local ignored lake contents and the explanatory README belong
there, and new fixture or product-data work must choose canonical committed
roots.

## Concrete Impact

- Contracts: `architecture/policies/directory_contracts.toml`,
  `architecture/asset_placement.toml`, `architecture/policies/data.toml`.
- Local path: `data/policy-engine-local/`.
- Owner: `team-data-forge`.
- Target phase: `6.3`.
- Rollback: reopen LM-014 and migrate the local lake to a new name with a
  synchronized update to data policy, tooling excludes, and documentation.

## Related Decisions

- Related: ADR-0146 Product Root Decision.
- Related: ADR-RSR-0131 Build Output and Cache Umbrella.
- Related: ADR-RSR-0137 Production Data and Fixtures Classification.
