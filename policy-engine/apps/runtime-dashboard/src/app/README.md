# Runtime Dashboard App Shell

Owner: `team-frontend`
Last updated: 2026-05-05

## Purpose

`src/app` owns the dashboard shell: providers, route registration, auth/session
state, layout surfaces, offline coordination, realtime wiring, and app-wide
stores.

## Public API

Public app entrypoints are `App.tsx`, `routes/AppRouter.tsx`,
`routes/routes.tsx`, `providers/AppProviders.tsx`, and `workspaces.ts`.
Feature code imports app shell through documented route registration only.

## Internal Layout

| Path | Role |
| --- | --- |
| `auth/`, `authz/` | Session, authorization, and route gating. |
| `layout/`, `surfaces/` | Shell layout and app-level surfaces. |
| `offline/`, `realtime/` | Cross-feature runtime effects. |
| `providers/` | React context composition. |
| `routes/` | Route tree, loaders, prefetch, and search params. |
| `state/` | App-wide persisted UI stores. |

## Extension Points

New features register routes through `src/app/routes/routes.tsx` and workspace
metadata through `src/app/workspaces.ts`. Do not import feature internals from
shared UI or API modules.

## Tests

Use Vitest component tests near touched modules or under `src/test/` for
provider/router helpers. End-to-end journeys live under app-level `e2e/`.

## Operability Links

- `apps/runtime-dashboard/README.md`
- `docs/reference/frontend/workspace-contract.md`
- `docs/reference/api/index.md`

## Known Shims/Deprecations

Legacy route shells must keep redirects or route aliases only when documented
in `routes.public.ts` or release notes.
