# Architecture Gates

- Owner: team-architecture
- Purpose: gate source contracts and lifecycle indexes for repository, package/import, compatibility-release, operability-release, structure-remediation, and report-only quality gates.
- Source index: `architecture/gates/index.toml`
- Taxonomy index: `architecture/index.toml`
- Local verification: `uv run pytest tests/repo_quality/architecture/test_architecture_taxonomy_closure.py -q`

Gate contracts live here when they define a command, promotion check, or
fail/report lifecycle. Domain contracts that a gate reads stay in their owning
taxonomy directory, for example `architecture/packages/**`,
`architecture/imports/**`, `architecture/public_surface/**`,
`architecture/tests/**`, `architecture/baselines/**`,
`architecture/policies/**`, `architecture/exceptions/**`, or
`architecture/tooling/**`.

Top-level gate-specific TOML files are not canonical. Add a new gate source
contract under this directory and add each gate ID to `index.toml` with its
source contract and command.
