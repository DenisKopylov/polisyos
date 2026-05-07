---
title: Design Wave 1 Release Notes
status: active
owner: denis-kopylov
created: 2026-04-22
last_verified: 2026-04-23
stability: final
---

# Design Wave 1 Release Notes

## Release Frame

- Release cut: `wave1-rc1`
- Snapshot date: `2026-04-22`
- Observation window: `2026-04-22` through `2026-05-06`
- Scope closed here: Phases `1.0` through `1.8` of
  [`DESIGN_BEST_IN_CLASS_PLAN.md`](./DESIGN_BEST_IN_CLASS_PLAN.md)

- Design changelog: [`CHANGELOG-DESIGN.md`](../../../CHANGELOG-DESIGN.md)
- Storybook snapshot manifest:
  [`docs/brand/storybook-wave1-snapshot/`](../../brand/storybook-wave1-snapshot/README.md)

- Wave 1 evidence bundle:
  [`EVIDENCE_BUNDLE.md`](../../brand/storybook-wave1-snapshot/EVIDENCE_BUNDLE.md)

- Immutable evidence workflow:
  [`design-wave1-evidence.yml`](../../../.github/workflows/design-wave1-evidence.yml)

Wave 1 closes the SOTA-gap program: brand foundations, uncertainty language,
accessibility, dark theme and density, reading-view prose, AI authorship
registry, and UA/RU typography. Closeout is recorded here against
repository-backed evidence, CI-verifiable artifacts, and generated contracts
rather than manual notes or one-off review rituals.

## Included Scope

| Phase | What landed                                                              | Primary evidence                                                                                                                                                                                                                       |
| ----- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `1.0` | Brand, motion, contrast, composition, typography specs and design ADRs   | [`docs/brand/`](../../brand/), [`docs/adr/ADR-042-janus-atlas-dual-brand.md`](../../adr/ADR-042-janus-atlas-dual-brand.md), [`docs/compliance/VPAT.md`](../../compliance/VPAT.md)                                                      |
| `1.1` | Janus mark, glyph vocabulary, evidence sigil, provenance strip           | [`public/atlas/`](../../../apps/runtime-dashboard/public/atlas/), [`src/shared/brand/`](../../../apps/runtime-dashboard/src/shared/brand/)                                                                                     |
| `1.2` | Uncertainty chart system and integrated showcase                         | [`src/shared/charts/`](../../../apps/runtime-dashboard/src/shared/charts/)                                                                                                                                                         |
| `1.3` | Accessibility audit pack, a11y runtime primitives, route/component gates | [`docs/compliance/A11Y_AUDIT_2026Q2.md`](../../compliance/A11Y_AUDIT_2026Q2.md), [`e2e/a11y/`](../../../apps/runtime-dashboard/e2e/a11y/)                                                                                          |
| `1.4` | Dark theme v2, high-contrast handling, density controls                  | [`src/app/providers/ThemeProvider.tsx`](../../../apps/runtime-dashboard/src/app/providers/ThemeProvider.tsx), [`src/app/providers/DensityProvider.tsx`](../../../apps/runtime-dashboard/src/app/providers/DensityProvider.tsx) |
| `1.5` | Reading-view monograph layout for decision packets                       | [`src/features/artifacts/reading-view/`](../../../apps/runtime-dashboard/src/features/artifacts/reading-view/)                                                                                                                     |
| `1.6` | AuthoredText registry and author timeline                                | [`src/shared/ui/authored-text/`](../../../apps/runtime-dashboard/src/shared/ui/authored-text/)                                                                                                                                     |
| `1.7` | ICU locales, currency/date/number formatters, UA/RU typography fixes     | [`src/i18n/`](../../../apps/runtime-dashboard/src/i18n/)                                                                                                                                                                           |
| `1.8` | Release notes, design changelog, Storybook archive, rollout manifest     | This document, [`CHANGELOG-DESIGN.md`](../../../CHANGELOG-DESIGN.md), [`docs/brand/storybook-wave1-snapshot/`](../../brand/storybook-wave1-snapshot/README.md)                                                                         |

## Storybook Closeout Snapshot

- Build command: `npm run build-storybook`
- Build date: `2026-04-22`
- Local static output:
  `_build/apps/runtime-dashboard/storybook-static/index.html`

- Archived story index:
  [`stories.index.json`](../../brand/storybook-wave1-snapshot/stories.index.json)

- Story count in archived index: `92`
- CI artifact contract: `wave1-evidence-manifest` publishes
  `wave1-evidence.json`; `wave1-storybook-static` publishes the immutable
  static Storybook build from the same run.

The Storybook snapshot is archived as a manifest-centric closeout pack rather
than a second full copy of static assets. The canonical generated site remains
in `_build/apps/runtime-dashboard/storybook-static/`; the archive folder stores the
review index, rollout manifest, and team-onboarding script required for Wave 1
closeout.

## Staging Rollout Profile

Wave 1 staging review should run with the entire design surface enabled.

- Canonical closeout manifest:
  [`staging-feature-flags.all_on.json`](../../brand/storybook-wave1-snapshot/staging-feature-flags.all_on.json)

- Accepted shorthand in the runtime dashboard: `all_on` and `all_off`
- Recommended env usage:
  `VITE_FEATURE_FLAGS_MANIFEST=all_on`

- Recommended remote-manifest usage:
  serve `staging-feature-flags.all_on.json` from the feature-flag endpoint

Note: current runtime keys are still legacy product-level flags
(`enableDarkMode`, `enableNarrativeView`, `enableAtlasV2`, and peers). Phase
`1.8` uses an explicit `all_on` rollout profile for staging review instead of
forcing a risky late rename to the future `design.wave{N}.phase{Y}` namespace.

## Anchor Artifact Matrix

Wave 1 closeout gates on anchor artifacts `1–4` and `7–10` from §7.

| Anchor                          | Evidence in repo                                                                                                                                                                                                                                                                                                    | Reproduction surface                                                                                                             | Status on `2026-04-23`                               |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `1. Updated favicon`            | [`public/atlas/favicon.svg`](../../../apps/runtime-dashboard/public/atlas/favicon.svg), [`logo-janus.svg`](../../../apps/runtime-dashboard/public/atlas/logo-janus.svg)                                                                                                                                     | Storybook `brand-janus--sizes` / browser favicon in `storybook-static`                                                           | Closed by visual and route-icon evidence             |
| `2. Decision packet cover page` | [`MonographLayout.tsx`](../../../apps/runtime-dashboard/src/features/artifacts/reading-view/MonographLayout.tsx), [`ProvenanceStrip.tsx`](../../../apps/runtime-dashboard/src/shared/ui/ProvenanceStrip.tsx), [`EvidenceSigil.tsx`](../../../apps/runtime-dashboard/src/shared/brand/EvidenceSigil.tsx) | Storybook `artifacts-reading-view-monograph-layout--default`, `brand-provenance-strip--default`, `brand-evidence-sigil--default` | Closed by Storybook and a11y evidence                |
| `3. Uncertainty showcase`       | [`src/shared/charts/`](../../../apps/runtime-dashboard/src/shared/charts/), [`UNCERTAINTY_LANGUAGE.md`](../../brand/UNCERTAINTY_LANGUAGE.md)                                                                                                                                                                    | Storybook `design-system-uncertainty--atlas-preview` plus chart stories                                                          | Closed by chart tests and Storybook evidence         |
| `4. WCAG 2.2 AA report`         | [`A11Y_AUDIT_2026Q2.md`](../../compliance/A11Y_AUDIT_2026Q2.md), [`VPAT.md`](../../compliance/VPAT.md)                                                                                                                                                                                                              | Compliance docs + `npm run test:a11y` evidence                                                                                   | Closed by internal engineering gate                  |
| `7. Density "Condensed"`        | [`DensityProvider.tsx`](../../../apps/runtime-dashboard/src/app/providers/DensityProvider.tsx), [`AppearanceSection.tsx`](../../../apps/runtime-dashboard/src/features/platform/settings/AppearanceSection.tsx)                                                                                             | Storybook `features-platform-appearancesection--default` with density toolbar set to `condensed`                                 | Closed by settings and Storybook evidence            |
| `8. Reading view`               | [`src/features/artifacts/reading-view/`](../../../apps/runtime-dashboard/src/features/artifacts/reading-view/)                                                                                                                                                                                                  | Storybook `artifacts-reading-view-monograph-layout--default`                                                                     | Closed by reading-view tests and authored prose lint |
| `9. AuthoredText mix`           | [`src/shared/ui/authored-text/`](../../../apps/runtime-dashboard/src/shared/ui/authored-text/)                                                                                                                                                                                                                  | Storybook `shared-ui-authoredtext--prominent-audit-rail` and register stories                                                    | Closed by authored registry and lint evidence        |
| `10. UA locale`                 | [`src/i18n/`](../../../apps/runtime-dashboard/src/i18n/), [`TYPOGRAPHY_UA_RU.md`](../../brand/TYPOGRAPHY_UA_RU.md)                                                                                                                                                                                              | Storybook `shared-text--ukrainian-typography`                                                                                    | Closed by locale catalogs and typography tests       |

## Acceptance Gate Status

| Criterion                                                    | Status                        | Notes                                                                                                                 |
| ------------------------------------------------------------ | ----------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Anchor artifacts `1–4`, `7–10` reproducible on staging       | Closed via repo evidence      | Storybook archive, rollout manifest, and linked stories are frozen in the evidence bundle                             |
| Wave 1 bug budget (`0 P0`, `<= 2 P1`, `<= 5 P2`) for 14 days | Observation opened            | Window runs from `2026-04-22` through `2026-05-06`; this note remains informational, not a missing artifact           |
| VPAT document signed                                         | Closed for engineering gate   | Versioned approval block and evidence bundle hash are recorded in [`VPAT.md`](../../compliance/VPAT.md)               |
| Storybook published for stakeholder review                   | Closed via immutable artifact | Closeout relies on the archived snapshot manifest and CI-published preview artifact referenced by the evidence bundle |

## Published Evidence Artifacts

The Wave 1 engineering gate is represented by the `design-wave1-evidence`
workflow. A green run publishes `wave1-evidence.json` with the run id, attempt,
git SHA, Storybook artifact name, Playwright artifact name, visual artifact
name, a11y status, OpenAPI sync status, and generation timestamp. Release
consumers should use that manifest as the immutable index for the artifact set.

## Observation Window

Track Wave 1 regressions in a single closeout watchlist from `2026-04-22`
through `2026-05-06`.

| Severity | Budget | Starting count |
| -------- | ------ | -------------- |
| `P0`     | `0`    | `0`            |
| `P1`     | `<= 2` | `0`            |
| `P2`     | `<= 5` | `0`            |

Any `P0`, more than `2` `P1`, or more than `5` `P2` issues during that window
re-opens Wave 1 closeout and blocks the Wave 2 gate.
