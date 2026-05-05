# ADR-0119: Frontend Monorepo Workspace

## Status

Proposed

## Date

2026-04-18

## Context

`frontend/` contains a dashboard app, generated API client, and reference shell.
Generated outputs and `node_modules` can dominate the local tree. The frontend
needs workspace-level dependency and codegen discipline.

## Decision

Move toward a frontend workspace:

```text
frontend/
|-- package.json
|-- pnpm-workspace.yaml
|-- packages/
|   |-- api-client/
|   |-- shared/
|   `-- reference-shell/
`-- apps/
    `-- runtime-dashboard/
```

Generated clients/types are registered artifacts with codegen commands and
freshness gates. Build outputs, coverage, storybook, and Playwright reports
remain ignored/local or CI artifacts.

## Consequences

- Frontend dependencies and generated clients become explicit.
- The dashboard can consume shared packages instead of local drift.
- The workspace migration can happen after backend schemas stabilize.

## Phase 0 Implementation Note

Repository SOTA Phase 0 registered the current product-root `packages/` tree as
committed frontend/devx source on 2026-05-02. That placement is a transitional
contract for existing files, not a replacement for the target `frontend/`
workspace layout above.
