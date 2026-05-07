# ADR-047: Atlas v4 dark theme canonicalization

## Status

Approved

## Date

2026-04-29

## Context

The Atlas v4 design-system archive received on 2026-04-29 includes a strong
reference kit for color, type, spacing, radius, shadows, glyphs, and component
previews. Its light theme aligns closely with the production Atlas visual
language.

The archive also proposes a blue graphite dark theme:

- `--paper: #16202b`
- `--sand: #111821`
- `--ink: #eef5ff`
- `--teal: #5fd3ca`
- `--ember: #ff936b`
- `--gold: #d2b362`

Production already uses a warm dark theme:

- `--paper: #1d1917`
- `--canvas: #120f0e`
- `--ink: #f5efe2`
- `--slate: #bcae9d`

The dark-theme decision affects the full product identity, contrast checks,
charts, status colors, shell glass, exported screenshots, and future public
viewer surfaces. Treating the archive dark palette as an automatic replacement
would invalidate existing accessibility and visual-polish decisions.

## Decision

Atlas keeps the production warm dark theme as canonical.

The v4 archive's blue graphite dark theme is retained only as historical
reference material. It must not be copied into production runtime tokens unless
this ADR is superseded.

The v4 reference token file is stored at:

- `docs/brand/atlas-v4/colors_and_type.css`

Intentional dark-theme differences are documented in:

- `docs/brand/ATLAS_V4_ADOPTION.md`

The drift check must allow the documented dark-theme differences and fail on
undocumented token drift.

## Rationale

Warm dark preserves Atlas's editorial policy-system identity. It reads as the
same product in low-light mode rather than a separate blue monitoring console.

Warm dark also keeps the light-theme signal language intact:

- teal remains the positive/live/verified signal,
- ember remains the blocker/risk signal,
- gold remains the ambiguous/review signal.

The archive blue dark theme makes the product feel closer to a generic
infrastructure dashboard, increases the risk of accidental fourth-accent usage,
and weakens the continuity between runtime UI, decision packets, and
publication-grade artifacts.

## Consequences

Positive:

- Existing contrast, motion, and visual-polish work remains valid.
- Atlas keeps one cross-theme brand identity.
- Drift checks can distinguish accepted v4 adoption from rejected theme drift.
- Future Track F public/export surfaces inherit the same visual language.

Negative:

- The archive dark preview cannot be treated as a literal implementation guide.
- Some v4 token differences remain permanently allowlisted unless a future ADR
  revisits the theme.
- Designers must review dark surfaces against production Storybook instead of
  the archive preview HTML.

## Concrete Impact

- `docs/brand/ATLAS_DESIGN_SYSTEM.md` names warm dark as canonical.
- `docs/brand/ATLAS_V4_ADOPTION.md` lists all accepted dark-token
  differences.
- `tools/design/check-atlas-v4-token-drift.ts` verifies that every v4
  token mismatch has a documented decision.
- `apps/runtime-dashboard/src/styles/theme-dark.css` remains the production
  source of truth for dark theme tokens.

## Related Decisions

- ADR-042: Janus/Atlas dual brand system.
- ADR-043: Provenance law.
- ADR-044: Time as primitive.
- ADR-045: Glyph alphabet limit 10.
- ADR-046: Authored text registry.
