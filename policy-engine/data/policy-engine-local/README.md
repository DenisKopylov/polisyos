# Legacy Local Data Lake

Status: ADR-backed local-state naming exception.

`data/policy-engine-local/` is the ignored local data lake declared by
`architecture/policies/data.toml` and accepted by
`docs/adr/repository-structure-0147-data-root-local-state-naming.md`.

This path is not a second product root. It is a compatibility name inside the
canonical `data/` root for local raw extracts, curated materializations, and
developer databases.

Committed contents are limited to this README. Do not add product fixtures,
goldens, or reusable test data here; reduce and promote them through
`architecture/policies/data.toml`, `architecture/generated_artifacts.toml`,
`tests/_data/`, or another allowlisted fixture root.
