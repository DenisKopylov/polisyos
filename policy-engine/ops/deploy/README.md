# Deployment Operations

- Owner: `team-ops`
- Artifact type: `deployment-contracts`

`ops/deploy/` owns deployment support contracts that are not command
implementations.

Current contract source: `ops/release/deployment-topology.toml`.

Backlog: move provider-neutral deployment topology and environment contracts
here when Phase 5.6 splits release promotion policy from deployment topology.

Observability assets live under `ops/observability/`. Cloud packaging lives
under `ops/cloud/`. Docker and compose assets live under `ops/docker/`.
