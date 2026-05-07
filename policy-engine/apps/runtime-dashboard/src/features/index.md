# Generated Index: Dashboard Features

Owner: `team-frontend`
Last updated: 2026-05-05

## Feature Modules

| Feature | Role |
| --- | --- |
| `artifacts/` | Artifact inspection and reading views. |
| `auth/` | Authentication route surfaces. |
| `causal/` | Causal analysis panels and layouts. |
| `clerk/` | Clerk-style operator workflow shell. |
| `collaboration/` | Collaboration hooks and shared state. |
| `commandPalette/` | Command palette surface. |
| `composer/` | Scenario/composition workflow. |
| `dashboard/` | Main dashboard route. |
| `evidence/` | Evidence and provenance workflow. |
| `lex/` | Lex search and graph surfaces. |
| `platform/` | Platform settings and posture routes. |
| `runs/` | Run list, detail, compare, live, and route state. |
| `whatif/` | What-if scenario workbench. |

## Convention

Each retained feature should use `domain/`, `components/`, `routes/` or
`route.tsx`, `hooks/`, optional `api/`, `state/`, colocated tests, and a public
`index.ts`.
