# Release SBOM

This directory is the committed anchor for release SBOM outputs.

Canonical regeneration command:

```bash
uv run polisyos-tools security sbom --output release/sbom/
```

The authoritative artifact contract lives in
[`architecture/generated_artifacts.toml`](/Users/deniskopylov/polisyos/policy-engine/architecture/generated_artifacts.toml).
