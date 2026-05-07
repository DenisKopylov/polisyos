# Apps

`apps/` contains JavaScript application workspaces that consume the Runtime API
through HTTP, OpenAPI snapshots, and generated clients.

Current apps:

- [`runtime-dashboard/`](runtime-dashboard/README.md) - the main React/Vite
  operator UI.
- [`runtime-reference-shell/`](runtime-reference-shell/README.md) - the static
  API diagnostics shell.

Shared JavaScript packages live under [`../packages/`](../packages/). Workspace
ownership and drift commands are registered in
[`../architecture/frontend_workspaces.toml`](../architecture/frontend_workspaces.toml).
