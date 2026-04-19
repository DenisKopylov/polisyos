# Security Operations

Security-as-code configuration lives here. Phase 5 repository hygiene gates use
these files together with `architecture/topology.toml` and
`architecture/generated_artifacts.toml`.

Planned gates:

1. gitleaks for committed-secret detection.
2. trufflehog for deeper historical scans when required.
3. OSV scanner for dependency vulnerability checks.
4. CycloneDX SBOM generation for release artifacts.
5. Manifest/log redaction scans for unredacted secrets or restricted PII.
