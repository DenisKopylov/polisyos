# Dashboard Feature Modules

Owner: `team-frontend`
Last updated: 2026-05-05

## Purpose

`src/features` contains vertical dashboard feature modules: routes, local
components, domain adapters, hooks, and state that belong to one operator
workflow.

## Public API

Each feature exports its public surface through `src/features/<feature>/index.ts`
and registers route metadata through the app route registry. Cross-feature
imports must use public feature barrels.

## Internal Layout

Feature modules use this convention:

| Path | Role |
| --- | --- |
| `domain/` | Feature-owned view models, adapters, and pure domain helpers. |
| `components/` | Feature-local UI components. |
| `routes/` or `route.tsx` | Route shells and loader-facing UI. |
| `hooks/` | Feature-local hooks that compose shared API hooks. |
| `api/` | Feature adapters only; generated API clients stay in `src/api/`. |
| `state/` | Feature-local Zustand or UI state. |

## Extension Points

Add a new feature under `src/features/<feature>/`, export it through
`index.ts`, and wire routes in `src/app/routes/routes.tsx`. Shared UI promotion
requires moving reusable pieces to `src/shared/ui/` or `src/shared/charts/`.

## Tests

Use colocated component/domain tests and `src/test/` helpers. Retain stories
only for reviewed visual states.

## Operability Links

- `apps/runtime-dashboard/src/README.md`
- `docs/reference/frontend/workspace-contract.md`
- `docs/how-to/onboarding/frontend-engineer.md`

## Known Shims/Deprecations

Route moves require route aliases or migration notes when URLs, workspace IDs,
or persisted state keys change.
