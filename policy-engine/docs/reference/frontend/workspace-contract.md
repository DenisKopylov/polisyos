# Frontend Workspace Contract

Freshness: 2026-10-06
Owner: `team-frontend`
Source of truth: `pnpm-workspace.yaml`, workspace `package.json` files, and `architecture/frontend_workspaces.toml`

Workspace manager: `pnpm` via root `pnpm-workspace.yaml` and one root
`pnpm-lock.yaml`.

The JavaScript workspace is contract-first. Runtime consumers use HTTP,
OpenAPI snapshots, and generated clients/types rather than importing runtime
internals or reading runtime filesystem state.

## Workspaces

| Workspace | Owner | Build | Test | Drift |
| --- | --- | --- | --- | --- |
| `packages/runtime-api-client` | `team-runtime` | `corepack pnpm --filter @polisyos/runtime-api-client run build` | `corepack pnpm --filter @polisyos/runtime-api-client test`, `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify` | `corepack pnpm --filter @polisyos/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json`, `corepack pnpm --filter @polisyos/runtime-api-client run contracts:verify` |
| `apps/runtime-dashboard` | `team-frontend` | `corepack pnpm --filter @polisyos/runtime-dashboard run build`, `corepack pnpm --filter @polisyos/runtime-dashboard run typecheck` | `corepack pnpm --filter @polisyos/runtime-dashboard run test:components`, `corepack pnpm --filter @polisyos/runtime-dashboard run test:contracts` | `corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --openapi schemas/runtime_api_v1.openapi.json`, `corepack pnpm --filter @polisyos/runtime-dashboard run contracts:verify` |
| `apps/runtime-reference-shell` | `team-runtime` | `corepack pnpm --filter @polisyos/runtime-reference-shell run build` | `corepack pnpm --filter @polisyos/runtime-reference-shell test` | `corepack pnpm --filter @polisyos/runtime-reference-shell run check:architecture` |
| `packages/cli` | `team-frontend` | `corepack pnpm --filter @polisyos/cli run build` | `corepack pnpm --filter @polisyos/cli test` | `corepack pnpm --filter @polisyos/cli run lint` |
| `packages/atlas-ui` | `team-frontend` / `team-design` | No `build` script is declared; use `corepack pnpm --filter @polisyos/atlas-ui run typecheck` | `corepack pnpm --filter @polisyos/atlas-ui test` | `corepack pnpm --filter @polisyos/atlas-ui run check:architecture`, `corepack pnpm --filter @polisyos/atlas-ui run tokens:check` |

The two workspace globs in `pnpm-workspace.yaml` currently resolve five package roots: the two apps above and `packages/atlas-ui`, `packages/cli`, and `packages/runtime-api-client`. Including the product-root package, pnpm reports six workspace projects. Atlas UI's package manifest does not declare an `engines` field; the root workspace baseline remains Node `>=22 <23`.

The dashboard's `/` index route in `apps/runtime-dashboard/src/app/routes/routes.tsx` loads `ModeAwareHome`; its dashboard branch loads `features/dashboard/routes/DashboardPage.tsx`, which imports `Badge`, `Button`, `Card`, `EmptyState`, `MetricsSkeleton`, and `PanelSkeleton` from the public `@polisyos/atlas-ui` export. This is a real workspace consumer path, not a claim about Atlas UI product authority.

Root fan-out commands:

- `corepack pnpm build`
- `corepack pnpm test` (all package-local `test` scripts, including the full dashboard component suite)
- `corepack pnpm test:smoke` (workspace smoke/contract pass)
- `corepack pnpm lint`

## Generated Outputs

Committed generated outputs are registered in
`architecture/generated_artifacts.toml`:

- `packages/runtime-api-client/types.ts`
- `packages/runtime-api-client/canonicalRuntimeApiClient.ts` (public entrypoint)
- `packages/runtime-api-client/canonicalRuntimeApiClient.js` (public entrypoint)
- `apps/runtime-dashboard/src/api/types.ts`

The runtime client package owns the pinned `openapi-typescript` `7.13.0`
resolver. Its generator accepts the explicit `--openapi` input and writes only
the schema types and canonical client pair to an isolated `--output-root` when
one is supplied; the low-level raw pair is an ephemeral scratch handoff to the
canonicalizer. The dashboard generator accepts the same explicit input and
writes only its dashboard types output, preserving the downstream
normalization and formatting profile.

Atlas UI has a separate package-local design-token projection. Inputs live under `packages/atlas-ui/tokens/source/` and `packages/atlas-ui/tokens/modes/`; `packages/atlas-ui/src/tokens/project.ts` produces the five tracked files under `packages/atlas-ui/src/generated/`. The package exposes `tokens:check` for comparison and `tokens:generate` for write-mode regeneration; run `corepack pnpm --filter @polisyos/atlas-ui run tokens:generate` only when intentionally updating projections. Its generator validates against the external Design Tokens Community Group 2025.10 schema declared in that source. These projections are distinct from the four runtime API outputs listed above; the current `architecture/generated_artifacts.toml` does not enumerate the Atlas token files as a separate committed-output family.

Local outputs stay ignored under workspace-local `node_modules/`, product
`_build/{apps,packages}/...`, and product `_cache/{apps,packages}/...`.
Runtime dashboard outputs use `_build/apps/runtime-dashboard/{coverage,dist,output,playwright-report,storybook-static,test-results}`.
A local output can become committed only after it is promoted to a reviewed
baseline and registered as a generated artifact.

## Runtime Dashboard Subtree Contracts

| Subtree | Contract | Placement rule |
| --- | --- | --- |
| `apps/runtime-dashboard/src/app/` | App shell, providers, route registry, auth/session, offline/realtime, app-wide state | Feature routes register here; feature internals do not become app shell dependencies. |
| `apps/runtime-dashboard/src/features/` | Vertical feature modules | New features use `domain/`, `components/`, `routes/` or `route.tsx`, `hooks/`, optional `api/`, `state/`, tests/stories, and a public `index.ts`. |
| `apps/runtime-dashboard/src/shared/ui/` | Feature-agnostic UI primitives and patterns | Shared UI never imports from `features` or `app`; feature-specific UI stays under its feature. |
| `apps/runtime-dashboard/src/shared/charts/` | Shared charts, chart tokens, uncertainty renderers, and retained stories | Reusable chart primitives export through `index.ts`; feature-specific visualizations stay under features. |
| `apps/runtime-dashboard/src/api/` | HTTP transport, generated types, query keys, hooks, validators, streams | `types.ts` is generated from OpenAPI; features consume hooks and must not call backend internals directly. |
| `apps/runtime-dashboard/src/test/` | Test helpers, MSW handlers, accessibility helpers, contract fixtures | Production source must not import this subtree; API payload fixtures live under `contracts/fixtures/`. |

Local README/AUTHORING files in each subtree are the source of truth for
allowed file categories, generated-file policy, fixture placement, extension
points, and deprecation/shim handling.
