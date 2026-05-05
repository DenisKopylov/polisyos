# Security Operations

Security-as-code configuration lives here. Phase 5 repository hygiene gates use
these files together with `architecture/topology.toml` and
`architecture/generated_artifacts.toml`.

Fail-closed baseline gates:

1. gitleaks for committed-secret detection.
2. trufflehog for deeper historical scans when required.
3. OSV scanner for dependency vulnerability checks.
4. CycloneDX SBOM generation for release artifacts.
5. Manifest/log redaction scans for unredacted secrets or restricted PII.

Repository SOTA Phase 5 keeps these gates machine-checkable through the
baseline contracts and closeout command:

- `secrets-baseline.toml` links gitleaks and trufflehog policy.
- `osv-scanner.toml` lists Python and frontend lockfile inputs.
- `sbom.toml` lists release SBOM inputs and output location.
