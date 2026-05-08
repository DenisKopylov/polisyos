# Polisyos Package

- Owner: team-platform
- Purpose: canonical import root for product modules and public facades exposed by the PolicyOS engine.
- Allowed contents: owned domain packages, public facade modules, runtime package metadata, and compatibility shims registered in architecture contracts.
- Local verification: `uv run pytest tests/contract -q`
- Maintenance: keep public imports aligned with `architecture/public_surface/contract.toml`; root facade additions require CODEOWNERS and contract coverage.
