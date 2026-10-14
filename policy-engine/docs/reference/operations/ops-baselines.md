# Ops Baselines

Historical freshness marker: `2026-05-03`; this is not a current verification date.
Owner: `team-platform`
Source of truth: `architecture/baselines/ops.toml`
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; TOML/source inspection only. External scanner, cloud billing, and service states were not checked.

Phase 5 promotes the non-Python operational baselines to fail-closed repository
contracts. Remaining exceptions must be owner-approved, time-bounded, and
recorded in the owning TOML contract.

| Baseline | Owner | Primary files |
| --- | --- | --- |
| Secrets | `team-security` | `ops/security/gitleaks.toml`, `ops/security/trufflehog.yaml`, `ops/security/secrets-baseline.toml` |
| OSV | `team-security` | `ops/security/osv-scanner.toml` |
| SBOM | `team-security` | `ops/security/sbom.toml`, `_build/release/sbom/` |
| OTel | `team-observability` | `ops/observability/otel/baseline.yaml` |
| SLO | `team-observability` | `ops/observability/slo/`, `ops/observability/prometheus/slo_*.yml` |
| Release fragments | `team-release` | `ops/release/release-fragment-policy.toml`, `release-fragments/` |
| Commit policy | `team-release` | `ops/release/commit-policy.toml` |
| Release topology | `team-release` | `ops/release/deployment-topology.toml`, `ops/release/promotion-gates.toml` |
| Runtime | `team-runtime` | `ops/runtime/runtime-contracts.toml` |
| Migrations | `team-platform` | `ops/migrations/README.md`, `ops/migrations/migration-contracts.toml`, `ops/migrations/db/*.sql`, `ops/migrations/{db,runtime_state,api_schemas,ir}/README.md` |
| Operability contracts | `team-ops` | `architecture/runtime_state_layout.toml`, `architecture/runbook_coverage.toml`, `architecture/component_observability.toml` |
