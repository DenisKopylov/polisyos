# Shared Charts

Owner: `team-frontend`
Last updated: 2026-05-05

## Purpose

`src/shared/charts` owns reusable chart primitives, uncertainty renderers,
accessibility helpers, palettes, and chart-level stories/tests for the runtime
dashboard.

## Public API

Import through `src/shared/charts/index.ts`. Feature modules should not deep
import implementation-only chart helpers unless they are promoted to the index.

## Internal Layout

| Path | Role |
| --- | --- |
| `*.tsx` | Reusable chart components. |
| `*.test.ts(x)` | Component and token tests. |
| `*.stories.tsx` | Story fixtures retained for visual review. |
| `patterns/` | Shared SVG/pattern helpers. |
| `theme.ts`, `types.ts` | Shared chart tokens and types. |

## Extension Points

New reusable chart families export from `index.ts`. Feature-specific chart
composition belongs under the owning feature module.

## Tests

Use colocated Vitest tests and Storybook stories when visual states are part of
the contract.

## Operability Links

- `docs/brand/ATLAS_DESIGN_SYSTEM.md`
- `docs/compliance/A11Y_CONTRAST.md`
- `apps/runtime-dashboard/README.md`

## Known Shims/Deprecations

Palette, token, and component renames require story/test coverage plus a
release note when visual baselines change.
