# Release Operations

- Owner: `team-ops`
- Artifact type: `release-policy-contracts`

`ops/release/` owns operational release policy baselines. Release evidence and
release fragments still live in the product-level `release/` and
`release-fragments/` directories; this directory defines the checks and rules
that govern them.

## Baselines

- `release-fragment-policy.toml` defines accepted fragment roots, fields, and
  fragment types.
- `commit-policy.toml` defines fail-closed branch, PR, commit-message, and
  evidence expectations.
- `deployment-topology.toml` defines the contract-only deployment units for
  control plane, runtime API, data plane, frontend, CLI, and Python package
  artifacts.
- `promotion-gates.toml` defines the contract-only gates that later release
  automation can enforce for staging and production promotion.
- `architecture/operability_release_supply_chain_gates.toml` and
  `polisyos-tools release check-operability-release-gates --fail-closed`
  convert the Phase 6.3 operability, release topology, compatibility,
  workflow-permission, OIDC, SBOM, provenance, and release security checks into
  a blocking release gate.

Breaking runtime-state, API schema, IR schema, or persisted artifact changes
must satisfy `breaking_migration_runbook_docs` before staging can promote to
production.

## Verification

Repository SOTA Phase 5 wires these release baselines into the fail-closed
closeout contract through `polisyos-tools workspace repository-sota-closeout`.
