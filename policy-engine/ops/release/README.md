# Release Operations

`ops/release/` owns operational release policy baselines. Release evidence and
release fragments still live in the product-level `release/` and
`release-fragments/` directories; this directory defines the checks and rules
that govern them.

## Baselines

- `release-fragment-policy.toml` defines accepted fragment roots, fields, and
  fragment types.
- `commit-policy.toml` defines fail-closed branch, PR, commit-message, and
  evidence expectations.

## Verification

Repository SOTA Phase 5 wires these release baselines into the fail-closed
closeout contract through `polisyos-tools workspace repository-sota-closeout`.
