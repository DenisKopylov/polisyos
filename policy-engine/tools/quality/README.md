# Quality Tools

- Owner: team-quality
- Purpose: validation, testing, diagnostics, lint, and report tooling that enforce repository quality contracts.
- Allowed contents: quality gates, validation CLIs, test ratchet reporters, diagnostics helpers, and contract manifests.
- Local verification: `uv run pytest tests/repo_quality -q`
- Maintenance: gate behavior changes require matching repo-quality tests and updated architecture evidence.
