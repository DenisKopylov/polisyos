# Packages

`packages/` contains shared or publishable JavaScript workspaces.

Current packages:

- [`runtime-api-client/`](runtime-api-client/README.md) - the generated JS/TS
  Runtime API client.
- [`cli/`](cli/package.json) - shared CLI-facing frontend utilities.

Application workspaces live under [`../apps/`](../apps/). Workspace ownership
and drift commands are registered in
[`../architecture/frontend_workspaces.toml`](../architecture/frontend_workspaces.toml).
