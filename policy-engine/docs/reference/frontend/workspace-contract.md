# Frontend Workspace Contract

Freshness: 2026-05-03
Owner: `team-frontend`
Source of truth: `architecture/frontend_workspaces.toml`

Workspace manager: `pnpm` via root `pnpm-workspace.yaml` and one root
`pnpm-lock.yaml`.

`frontend/` is contract-first. Runtime consumers use HTTP, OpenAPI snapshots,
and generated clients/types rather than importing runtime internals or reading
runtime filesystem state.

## Workspaces

| Workspace | Owner | Build | Test | Drift |
| --- | --- | --- | --- | --- |
| `frontend/runtime-api-client` | `team-runtime` | `pnpm --filter @polisyos/runtime-api-client run build` | `pnpm --filter @polisyos/runtime-api-client test`, `pnpm --filter @polisyos/runtime-api-client run contracts:verify` | `pnpm --filter @polisyos/runtime-api-client run generate`, `pnpm --filter @polisyos/runtime-api-client run contracts:verify` |
| `frontend/runtime-dashboard` | `team-frontend` | `pnpm --filter @polisyos/runtime-dashboard run build`, `pnpm --filter @polisyos/runtime-dashboard run typecheck` | `pnpm --filter @polisyos/runtime-dashboard run test:components`, `pnpm --filter @polisyos/runtime-dashboard run test:contracts` | `pnpm --filter @polisyos/runtime-dashboard run generate:api`, `pnpm --filter @polisyos/runtime-dashboard run contracts:verify` |
| `frontend/runtime-reference-shell` | `team-runtime` | `pnpm --filter @polisyos/runtime-reference-shell run build` | `pnpm --filter @polisyos/runtime-reference-shell test` | `pnpm --filter @polisyos/runtime-reference-shell run check:architecture` |
| `packages/cli` | `team-frontend` | `pnpm --filter @polisyos/cli run build` | `pnpm --filter @polisyos/cli test` | `pnpm --filter @polisyos/cli run lint` |

Root fan-out commands:

- `pnpm build`
- `pnpm test` (all package-local `test` scripts, including the full dashboard component suite)
- `pnpm test:smoke` (workspace smoke/contract pass)
- `pnpm lint`

## Generated Outputs

Committed generated outputs are registered in
`architecture/generated_artifacts.toml`:

- `frontend/runtime-api-client/runtimeApiClient.ts`
- `frontend/runtime-api-client/runtimeApiClient.js`
- `frontend/runtime-dashboard/src/api/types.ts`

Local outputs stay ignored under workspace-local `node_modules/`, product
`_build/frontend/...`, and product `_cache/frontend/...`. Runtime dashboard
outputs use `_build/frontend/runtime-dashboard/{coverage,dist,output,playwright-report,storybook-static,test-results}`.
A local output can become committed only after it is promoted to a reviewed
baseline and registered as a generated artifact.
