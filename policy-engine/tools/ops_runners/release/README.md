# tools/ops_runners/release

Release-gate helpers for version checks, compatibility release readiness,
release notes, artifact sizing, canary execution, vulnerability report
evaluation, and snapshot staging.

Use the unified entry point:

```bash
polisyos-tools release --help
```

Operational rules:

- Release tools should be deterministic and safe to run repeatedly.
- Compatibility release gates are report-only in Phase 5.10; pass
  `--fail-on-contract-errors` only when validating the metadata contract shape.
- Phase 6.3 promotes the combined operability, release topology,
  compatibility, workflow-permission, OIDC, SBOM, provenance, and security
  checks through `polisyos-tools release check-operability-release-gates
  --fail-closed`.
- Snapshot/staging tools must declare their upstream dependencies in
  `tools.registry`.

- Prefer structured outputs and timing records for release evidence.
