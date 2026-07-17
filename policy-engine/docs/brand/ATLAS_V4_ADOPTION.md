---
title: Atlas v4 Adoption Record
status: superseded-as-canonical
owner: team-design
created: 2026-04-29
last_reviewed: 2026-07-16
disposition: retained-historical-adoption-record
superseded_by: ./ATLAS_SOURCE_OF_TRUTH.md
retained_for: DS2 counterpart evidence and ADR-047 history
---

# Atlas v4 Adoption Record

**Date:** 2026-04-29

**Status:** Dated v4 evidence; superseded as a governing source by [Atlas Source-Of-Truth](./ATLAS_SOURCE_OF_TRUTH.md)

**Historical source archive:** `/Users/deniskopylov/Downloads/PolicyOS Atlas Design System-4.zip` (non-replayable local provenance; DS2 must not use it as evidence)

**Reference token file:** `docs/brand/atlas-v4/colors_and_type.css`

**Retained v4 reference:** `docs/brand/ATLAS_DESIGN_SYSTEM.md`

**Dark theme ADR:** `docs/adr/ADR-047-atlas-v4-dark-theme-canonicalization.md`

This record explains what was accepted from the Atlas v4 archive, what already
existed in production, and which differences are intentional. The rule is
simple: production and the v4 reference must agree, or the difference must have
an explicit decision here. Its local-download source path is a known replay
defect; DS2 compares the repo-local reference and live code, not that path.
ADR-047 remains in force until an ADR-process change supersedes it.

## 1. Adoption Summary

Accepted:

- The v4 archive is adopted as a reference kit for Atlas visual foundations.
- The repo-local `docs/brand/atlas-v4/colors_and_type.css` is the frozen v4
  token comparison target.
- The production light theme remains aligned with the v4 warm sandstone palette.
- The 10-radical glyph alphabet remains canonical.
- Buttons, badges, cards, type, shadows, and color references are exposed in
  Storybook through `AtlasV4Reference.stories.tsx`.
- Token drift is enforced through `design:atlas-v4`.

Not accepted as-is:

- The v4 archive's blue graphite dark theme.
- The archive's blue `--chart-secondary`.
- Static prototype spacing beyond production's density-aware scale.
- Display/hero type tokens for runtime screens.
- Any prototype JSX from `ui_kits/dashboard/` as production code.

## 2. Token Decisions

| ID  | Token(s)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Production decision                                                                                                                                                 |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D01 | `--panel`, `--panel-strong`, `--surface`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Light theme uses slightly stronger white glass than the archive to preserve contrast in real runtime panels and dense cards.                                        |
| D02 | `--chart-secondary`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Archive blue is rejected. Production uses a teal/graphite mix so the palette remains limited to Atlas signal colors and neutrals.                                   |
| D03 | `--color-ci-50`, `--color-ci-80`, `--color-ci-95`, `--color-bounds-fill`, `--color-bounds-stroke`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Production uses `color-mix(...)` so confidence bands follow the active theme and semantic accent token instead of fixed rgba values.                                |
| D04 | `--color-waterfall-positive`, `--color-waterfall-negative`, `--color-waterfall-total`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Production routes waterfall colors through chart/semantic aliases so theme changes and accessibility checks remain centralized.                                     |
| D05 | `--space-1`, `--space-2`, `--space-3`, `--space-4`, `--space-5`, `--space-6`, `--space-7`, `--space-8`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Production keeps density-aware spacing only for runtime surfaces. Static prototype spacing tokens are reference-only.                                               |
| D06 | `--radius-card`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Production keeps cards at `24px` instead of the archive's `22px` to match the existing Atlas component contract.                                                    |
| D07 | `--radius-shell`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | The archive shell radius remains a prototype reference. Production shell geometry is component-owned until there is a single shell component contract.              |
| D08 | `--shadow-panel`, `--rim-light`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Production may use direct theme values instead of archive aliases, and routes rim light through theme variables so dark mode can use a warmer, lower-contrast edge. |
| D09 | `--font-serif`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Serif is allowed only in citation/prose treatments. It is not a runtime theme token because dense UI stays Manrope plus IBM Plex Mono.                              |
| D10 | `--text-5xl`, `--text-display`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Display scale is reference-only for public/export artifacts. Runtime Atlas screens stop at `--text-4xl` unless a page-specific design review adds a larger token.   |
| D11 | `--tracking-tighter`, `--tracking-tight`, `--tracking-snug`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Production uses less aggressive heading tracking and omits `--tracking-snug`; compact operational panels need safer wrapping.                                       |
| D12 | `--paper`, `--sand`, `--ink`, `--graphite`, `--slate`, `--line`, `--canvas`, `--teal`, `--ember`, `--gold`, `--teal-soft`, `--ember-soft`, `--gold-soft`, `--panel`, `--panel-strong`, `--surface`, `--shell-border`, `--shell-glass-start`, `--shell-glass-end`, `--shell-glass-base`, `--page-gradient-start`, `--page-gradient-mid`, `--page-gradient-end`, `--page-glow-teal`, `--page-glow-ember` in dark theme                                                                                                                                                                                                                                                  | Production keeps warm dark as canonical and rejects the archive's blue dark palette. See ADR-047.                                                                   |
| D13 | `--accent`, `--success`, `--warning`, `--danger`, `--button-primary-start`, `--button-primary-end`, `--button-primary-text`, `--chart-grid`, `--chart-axis`, `--chart-primary`, `--chart-alert`, `--chart-neutral`, `--chart-secondary`, `--color-governance-review`, `--color-ci-50`, `--color-ci-80`, `--color-ci-95`, `--color-bounds-fill`, `--color-bounds-stroke`, `--color-confidence-high`, `--color-confidence-medium`, `--color-confidence-low`, `--color-waterfall-positive`, `--color-waterfall-negative`, `--color-waterfall-total`, `--rail-active-bg`, `--rail-hover-bg`, `--rail-link`, `--focus-ring`, `--shadow-panel`, `--rim-light` in dark theme | Dark theme semantic tokens are recalibrated for warm-dark contrast, not copied from the archive's light aliases. See ADR-047.                                       |

## 3. Asset Decisions

| Area                   | Decision                                                                                                                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Wordmark and mark SVGs | Production assets in `public/atlas/` remain canonical. The archive variants match the intent but are not copied over unless a visual diff proves a production asset is stale. |
| Glyph SVGs             | Production glyph implementation in `src/shared/brand/Glyph.tsx` remains canonical because it enforces size, intent, stroke style, diacritics, and accessibility labels.       |
| Prototype previews     | Archive `preview/*.html` files are treated as reference boards only. Production reference is Storybook.                                                                       |
| Dashboard JSX kit      | Archive `ui_kits/dashboard/*.jsx` files are concept material for later tracks, not accepted runtime components.                                                               |

## 4. Storybook Adoption

Phase 3.0 adds a single Atlas v4 review surface:

- `src/shared/ui/tokens/AtlasV4Reference.stories.tsx`

It includes:

- color swatches for core and semantic tokens,
- type scale and mono/label examples,
- shadow and glass samples,
- all 10 glyph radicals,
- button variants,
- badge variants,
- card and metric-card references.

Existing component stories remain canonical for component-level API examples.

## 5. Drift Check Contract

Run:

```bash
npm --prefix policy-engine/apps/runtime-dashboard run design:atlas-v4
```

The check compares:

- v4 reference: `docs/brand/atlas-v4/colors_and_type.css`
- production light: `apps/runtime-dashboard/src/styles.css` +
  `apps/runtime-dashboard/src/styles/theme-light.css`
- production dark: `apps/runtime-dashboard/src/styles.css` +
  `apps/runtime-dashboard/src/styles/theme-light.css` +
  `apps/runtime-dashboard/src/styles/theme-dark.css`

Failure policy:

- Missing production token: fail unless listed in this document.
- Changed token value: fail unless listed in this document.
- Allowlisted difference not mentioned in this document: fail.
- New reference token without a production match or adoption decision: fail.
- Missing Phase 3.0 artifact or Storybook reference category: fail.

The check intentionally verifies the full canonicalization contract, not only
raw token equality. It asserts the design-system doc, adoption record,
dark-theme ADR, reference CSS, Storybook reference, package script and
production theme files are present and linked.

## 6. Follow-Up Queue

- Add visual snapshot coverage for `AtlasV4Reference.stories.tsx` after the
  current visual baseline is refreshed.
- Decide whether `--radius-shell` should become a production shell token during
  shell-layout consolidation.
- Decide whether citation/prose surfaces should expose a formal serif token or
  continue using component-scoped typography.
- Revisit display-scale tokens only for public viewer, publication, or export
  tracks, not for runtime dashboard surfaces.
