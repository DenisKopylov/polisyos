# Ops Baselines

Freshness: 2026-05-03
Owner: `team-platform`
Source of truth: `architecture/ops_baselines.toml`

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
| Runtime | `team-runtime` | `ops/runtime/runtime-contracts.toml` |
| Migrations | `team-platform` | `ops/migrations/README.md`, `ops/migrations/migration-contracts.toml`, `ops/migrations/*.sql` |
