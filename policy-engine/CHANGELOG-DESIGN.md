# Design Changelog

All notable design, brand, accessibility, typography, Storybook, and
presentation-system changes for PolicyOS are tracked in this file.

The format follows the spirit of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), but entries are
grouped by design wave and phase so release review can map directly back to
`docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md`.

## [Unreleased]

### Added

- Add Wave 1 closeout release notes in
  `release/design-wave1-release-notes.md`.

- Add the archival Storybook snapshot manifest in
  `docs/brand/storybook-wave1-snapshot/`, including a copied story index,
  staging `all_on` manifest, and onboarding recording script.

- Add feature-flag manifest shorthands `all_on` and `all_off` in
  `apps/runtime-dashboard/src/lib/featureFlags.ts` so staging and review
  environments can enable the full Wave 1 surface without enumerating every key
  by hand.

### Changed

- Raise the PWA precache size ceiling in
  `apps/runtime-dashboard/vite.config.ts` so `corepack pnpm run build-storybook`
  completes successfully for the Wave 1 review build.

- Establish a dedicated design changelog instead of mixing Wave 1 UI work into
  the engine-wide `CHANGELOG.md`.

### Wave 1 Summary

#### Phase 1.0 Foundations

- Publish the brand foundation pack in `docs/brand/`:
  `GLYPH_SPECIFICATION.md`, `UNCERTAINTY_LANGUAGE.md`, `A11Y_CONTRAST.md`,
  `MOTION.md`, `COMPOSITION_RULES.md`, and `TYPOGRAPHY_UA_RU.md`.

- Publish the governance and design ADR set in `docs/adr/`:
  `ADR-042`, `ADR-043`, `ADR-044`, `ADR-045`, and `ADR-046`.

- Publish compliance artifacts in `docs/compliance/`, including
  `VPAT.md` and the accessibility audit packet.

#### Phase 1.1 Visual Language

- Add Janus brand assets under `apps/runtime-dashboard/public/atlas/`,
  including `favicon.svg`, `logo-janus.svg`, `logo-mark.svg`,
  `logo-mark-inverse.svg`, and the glyph library in `public/atlas/glyphs/`.

- Add reusable brand primitives in `apps/runtime-dashboard/src/shared/brand/`
  with Storybook coverage for `Brand/Janus`, `Brand/Glyphs`, and
  `Brand/Evidence Sigil`.

- Introduce `ProvenanceStrip` as a first-class eyebrow/status component with a
  dedicated `Brand/Provenance Strip` Storybook track.

#### Phase 1.2 Uncertainty Visualization

- Add the uncertainty chart suite in
  `apps/runtime-dashboard/src/shared/charts/`, including `FanChart`,
  `UncertaintyBand`, `QuantileDotplot`, and `HypotheticalOutcomePlot`.

- Add Storybook coverage for chart-level uncertainty states and the integrated
  `Design System/Uncertainty` showcase, including dark-theme previews.

#### Phase 1.3 Accessibility

- Publish the internal accessibility audit packet in
  `docs/compliance/A11Y_AUDIT_2026Q2.md`.

- Expand route, component, keyboard, screen-reader, contrast, reduced-motion,
  and color-blind coverage across `apps/runtime-dashboard/e2e/a11y/`,
  `apps/runtime-dashboard/src/shared/a11y/`, and
  `apps/runtime-dashboard/src/test/a11y/`.

#### Phase 1.4 Dark Theme and Density

- Expand appearance controls and provider wiring for theme, contrast, and
  density selection.

- Add Storybook support for light, dark, and high-contrast preview modes plus
  comfortable, compact, and condensed densities.

#### Phase 1.5 Prose System

- Add the reading-view surface in
  `apps/runtime-dashboard/src/features/artifacts/reading-view/` with
  monograph layout, pull quotes, margin notes, reading-progress helpers, and
  print-minded prose tokens.

- Add `Artifacts/Reading View/Monograph Layout` Storybook coverage for the new
  decision-packet presentation layer.

#### Phase 1.6 AI Authorship Registry

- Add the authored-text registry in
  `apps/runtime-dashboard/src/shared/ui/authored-text/`, including
  `AuthoredText`, `AuthorshipProvider`, `AuthorBadge`, and the author registry.

- Add Storybook coverage for citation, human, drafter, formalizer, and critic
  registers, plus the prominent timeline rail.

#### Phase 1.7 UA/RU Typography and i18n

- Replace the previous message layout with JSON locale packs in
  `apps/runtime-dashboard/src/i18n/locales/`.

- Add locale-aware formatters and typographic helpers in
  `apps/runtime-dashboard/src/i18n/formatters/` and
  `apps/runtime-dashboard/src/i18n/typography/`, including quote-mark and
  non-breaking-space enforcement.

- Add the `Shared/Text` Ukrainian typography Storybook specimen for cyrillic
  review.

#### Phase 1.8 Wave 1 Closeout

- Publish the Wave 1 release notes and closeout checklist.
- Archive the Storybook story index for Wave 1 review and add an onboarding
  recording script for team handoff.
