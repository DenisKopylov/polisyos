# Developer Experience Tools

- Owner: team-devx
- Purpose: local workspace diagnostics, cleanup helpers, developer automation, and tool configuration support.
- Allowed contents: dev-only CLIs, workspace health checks, local cleanup utilities, and docs for supported developer workflows.
- Local verification: `uv run python -m tools.devx.workspace.doctor`
- Maintenance: tools here must be safe for local use and should expose module or CLI entry points rather than relying on direct script execution.
