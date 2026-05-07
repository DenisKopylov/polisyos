# ADR-0119: JavaScript Monorepo Workspace

## Status

Proposed

## Date

2026-04-18

## Context

The repository contains browser apps, a generated runtime API client, and a
reference shell. Generated outputs and `node_modules` can dominate the local
tree. JavaScript workspaces need workspace-level dependency and codegen
discipline while keeping apps and publishable libraries in distinct topology
lanes.

## Decision

Use the product root as the pnpm workspace root and split JavaScript workspaces
by role:

```text
apps/
|-- runtime-dashboard/
`-- runtime-reference-shell/
packages/
|-- cli/
`-- runtime-api-client/
```

Generated clients/types are registered artifacts with codegen commands and
freshness gates. Apps live under `apps/`; publishable or reusable JavaScript
libraries live under `packages/`. Build outputs, coverage, storybook, and
Playwright reports remain ignored/local or CI artifacts. `frontend/` is retained
only as a contributor handoff path that points to the active workspace roots.

## Consequences

- Frontend dependencies and generated clients become explicit.
- The dashboard can consume shared packages instead of local drift.
- Apps and libraries have predictable package boundaries.
- Old `frontend/*` workspace paths must not be used for active source.

## Phase 0 Implementation Note

Repository SOTA Phase 0 registered the current product-root `packages/` tree as
committed frontend/devx source on 2026-05-02. That placement is a transitional
contract superseded by the `apps/*` and `packages/*` workspace layout above.

## Phase 2.7 Implementation Note

Repository Best-in-Class Phase 2.7 moved active JavaScript workspaces to
`apps/*` and `packages/*` on 2026-05-05. `pnpm-workspace.yaml`,
`architecture/frontend_workspaces.toml`, generated runtime API client commands,
CI workflows, and contributor docs now use those roots.
