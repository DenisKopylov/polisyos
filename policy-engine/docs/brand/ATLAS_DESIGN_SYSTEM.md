---
title: PolicyOS Atlas Design System - v4 Reference
status: superseded-as-canonical
owner: team-design
created: 2026-04-29
last_reviewed: 2026-07-16
disposition: retained-current-v4-reference
superseded_by: ./ATLAS_SOURCE_OF_TRUTH.md
retained_for: DS2 comparison and DS4 migration
---

# PolicyOS Atlas Design System

**Status:** Transitional live v4 baseline; superseded as a governing source by [Atlas Source-Of-Truth](./ATLAS_SOURCE_OF_TRUTH.md)

**Source archive:** `PolicyOS Atlas Design System-4.zip`, received 2026-04-29

**Production root:** `policy-engine/apps/runtime-dashboard/`

**Reference token file:** `docs/brand/atlas-v4/colors_and_type.css`

**Adoption record:** `docs/brand/ATLAS_V4_ADOPTION.md`

This document adapts the Atlas v4 archive into the current production reality.
It is retained as dated v4 rationale and DS2/DS4 migration evidence. The live
code remains the operational production baseline until strangled item by item;
the surface constitution, Revision 2 master plan, and DS0 decision now own
normative and execution authority.

## 1. Product Context

Atlas is the PolicyOS runtime shell for causal policy simulation, evidence
review, and governance operations. It is used by policy analysts and operators
who need dense information, clear provenance, and audit-grade decision packets.

The core workflows are:

1. **Command Center** - active runs, governance pressure, evidence freshness,
   operator queue, and system posture.
2. **Scenario Composer** - intervention design, evidence lanes, counterfactual
   setup, and launch controls.
3. **Decision Workspace** - verdict, rationale, uncertainty, fairness,
   governance passes, and provenance.
4. **Evidence Fabric** - source health, lineage, freshness, schemas, quality,
   and artifacts.

The UI should feel like an editorial control room: rigorous, calm, legible,
and operational. It should never feel like a marketing site, a generic SaaS
dashboard, or a decorative science demo.

## 2. Retained v4 Production Baseline

Current implementation anchors:

- `apps/runtime-dashboard/src/styles.css` - Tailwind v4 theme tokens,
  density hooks, typography scale, motion scale, and base app rules.
- `apps/runtime-dashboard/src/styles/theme-light.css` - light Atlas theme.
- `apps/runtime-dashboard/src/styles/theme-dark.css` - canonical warm dark
  Atlas theme.
- `apps/runtime-dashboard/src/shared/ui/` - production UI primitives.
- `apps/runtime-dashboard/src/shared/brand/` - Atlas wordmark, Janus mark,
  EvidenceSigil, and the 10-radical glyph alphabet.
- `apps/runtime-dashboard/public/atlas/` - shipped SVG brand assets.
- `docs/brand/GLYPH_SPECIFICATION.md` - glyph vocabulary contract.
- `docs/adr/ADR-045-glyph-alphabet-limit-10.md` - closed glyph alphabet.
- `docs/adr/ADR-047-atlas-v4-dark-theme-canonicalization.md` - dark theme
  decision.

The v4 archive is retained only as a reference baseline. The repo-local copy of
its token contract lives in `docs/brand/atlas-v4/colors_and_type.css`. DS2 must
adjudicate v15 against these live counterparts; this page cannot admit either
source.

## 3. Content Fundamentals

Atlas copy is analytical and operator-grade. It should be terse, domain
specific, and written in neutral declarative language.

Rules:

- Use domain terms directly: intervention, evidence bundle, governance pass,
  run, decision packet, scenario, counterfactual, provenance, confidence.
- Use sentence case for normal labels and headings.
- Use uppercase only for mono eyebrows, compact status pills, and narrow
  control labels.
- Keep panel titles short: 1-4 words.
- Format every number through product formatters. Do not show raw floats,
  unrounded percentages, or unformatted durations.
- Avoid first-person UI framing. Prefer `Decision queue` over `Your queue`.
- Avoid marketing language, emoji, and decorative filler copy.

Locale posture:

- English is the default operational language.
- Ukrainian and Russian locales must keep formal bureaucratic register.
- Bureaucratic artifacts must use the locale-aware AST/rendering path described
  in `docs/brand/BUREAUCRATIC_RENDERING.md`.

## 4. Visual Foundations

### 4.1 Palette

Atlas uses warm neutrals plus three signal colors. The three signal colors are
semantic, not decorative.

| Role            | Canonical token | Light value              | Meaning                      |
| --------------- | --------------- | ------------------------ | ---------------------------- |
| Page paper      | `--paper`       | `#fbf8f2`                | Primary app background       |
| Muted sand      | `--sand`        | `#f4efe6`                | Muted surfaces and inputs    |
| Primary text    | `--ink`         | `#17191d`                | Main text                    |
| Rail graphite   | `--graphite`    | `#28333c`                | Sidebar and dense headers    |
| Muted text      | `--slate`       | `#40515f`                | Secondary labels             |
| Border line     | `--line`        | `rgba(23, 25, 29, 0.12)` | Hairlines and separators     |
| Success/action  | `--teal`        | `#115e57`                | Approved, running, primary   |
| Risk/blocker    | `--ember`       | `#92391d`                | Blocked, failed, destructive |
| Pending/warning | `--gold`        | `#6c5111`                | Ambiguous, review, pending   |

Signal rule:

- Teal means approved, live, verified, progressing, or primary action.
- Ember means blocked, rejected, failed, destructive, or disputed.
- Gold means pending, partial, ambiguous, warning, or review required.

Atlas does not add a fourth accent hue for product meaning. The v4 archive's
blue `--chart-secondary` is intentionally rejected in production; charts use a
teal/graphite mix instead.

### 4.2 Light Theme

The light theme is sandstone and paper with a graphite rail. Production keeps
the v4 palette, then slightly strengthens glass surfaces for runtime contrast:

- `--panel: rgba(255, 255, 255, 0.85)`
- `--panel-strong: rgba(255, 255, 255, 0.9)`
- `--surface: rgba(255, 255, 255, 0.58)`

Those values are intentional differences from the archive, not drift.

### 4.3 Dark Theme

The canonical dark theme is warm dark, not the v4 archive's blue graphite dark.
The accepted production dark theme uses brown-black paper, warm ink, and
on-dark variants for teal, ember, and gold:

- `--paper: #1d1917`
- `--canvas: #120f0e`
- `--ink: #f5efe2`
- `--slate: #bcae9d`

Rationale: warm dark preserves the Atlas editorial identity, avoids a generic
monitoring-dashboard feel, keeps signal colors consistent with the light theme,
and matches existing production review/a11y work.

### 4.4 Typography

Production type stack:

- `--font-sans`: Manrope, used for body, headings, metrics, controls.
- `--font-mono`: IBM Plex Mono, used for IDs, timestamps, eyebrows, status
  grammar, code-like facts.
- Serif citation styling is allowed only in reading/prose contexts. It is not
  a core runtime token and is not used for dense operational UI.

Scale:

- Body: `--text-base`, 1rem.
- Dense labels: `--text-xs` and `--text-2xs`.
- Page and panel headings: `--text-xl` through `--text-4xl`.
- v4's `--text-5xl` and `--text-display` are reference-only. Atlas is an app
  shell, not a landing page; hero-scale type is reserved for export/publication
  artifacts when explicitly designed.

### 4.5 Spacing, Radius, And Density

Production spacing is density-aware:

- `--space-2`: `calc(8px * var(--space-scale))`
- `--space-3`: `calc(12px * var(--space-scale))`
- `--space-4`: `calc(16px * var(--space-scale))`
- `--space-5`: `calc(24px * var(--space-scale))`

The archive's extra static spacing tokens are treated as prototype helpers.
Production must prefer density-aware tokens so comfortable, compact, and
condensed modes remain coherent.

Radius:

- Controls and badges use `--radius-pill`.
- Cards use `--radius-card`, currently `24px`.
- Panels and large framed tools use `--radius-panel`, currently `28px`.
- Generic page sections must not become floating cards.

### 4.6 Shadows And Glass

Shadow scale:

- `--shadow-xs`: small hairline lift.
- `--shadow-sm`: local control lift.
- `--shadow-md`: popovers and small overlays.
- `--shadow-lg`: large overlays.
- `--shadow-xl` / `--shadow-panel`: app shell and major panels.

Glass surfaces are warm, translucent, and restrained. Rim light is implemented
through production variables so dark theme can switch from white rim light to a
warmer low-contrast edge.

### 4.7 Motion

Motion is editorial, fast, and low-drama:

- `--motion-fast`: 160ms.
- `--motion-moderate`: 180ms.
- `--motion-slow`: 240ms.

Reduced motion must collapse nonessential animation. No bouncy physics or
decorative loops belong in Atlas runtime UI.

## 5. Component Primitives

### Buttons

Use `Button` from `src/shared/ui/Button.tsx`.

- Primary: teal gradient, high-emphasis launch or commit action.
- Ghost: ordinary navigation and secondary operations.
- Danger: destructive or blocking operation.
- Outline/secondary/link: compatibility variants for shadcn/Radix surfaces.

Buttons should use glyphs or utility icons when the action benefits from a
symbol, especially in dense toolbars.

### Badges

Use `Badge` from `src/shared/ui/Badge.tsx`.

- `ok`: approved, verified, live.
- `warn`: pending, review, partial, degraded.
- `fail`: blocked, rejected, failed.
- `neutral`: descriptive metadata.
- `info`: transport/live informational state.
- `outline`: low-emphasis label in constrained surfaces.

Badges are compact facts, not explanations.

### Cards And Panels

Use `Card` for repeated items, modals, and genuinely framed tools. Do not use
cards to wrap whole page sections. Do not nest cards inside cards.

Panels must preserve:

- warm glass background,
- subtle border,
- stable radius,
- restrained shadow,
- enough internal rhythm for scanning.

### Glyphs

Atlas uses a closed alphabet of 10 radicals. Domain concepts must resolve to
one of these radicals; expanding the alphabet requires an ADR.

| Radical           | Anchor | Domain                            |
| ----------------- | ------ | --------------------------------- |
| `intervention`    | `⊙`    | intervention, policy action       |
| `evidence`        | `▲`    | evidence, observation, claim      |
| `provenance`      | `⟿`    | provenance, lineage, source chain |
| `transport`       | `⇄`    | transport, external validity      |
| `counterfactual`  | `⋌`    | what-if, hypothetical             |
| `identifiability` | `≔`    | identification, estimand          |
| `reproducibility` | `⟳`    | replay, rerun                     |
| `governance-pass` | `⊡`    | compliant, ratified               |
| `blocker`         | `⊘`    | denied, legal stop                |
| `freshness`       | `◷`    | staleness, age of evidence        |

Use Lucide or utility icons only for generic commands such as close, copy,
expand, search, and download.

## 6. Storybook References

Phase 3.0 canonical reference stories live under:

- `src/shared/ui/tokens/AtlasV4Reference.stories.tsx`
- `src/shared/ui/tokens/DesignTokens.stories.tsx`
- `src/shared/brand/Glyph.stories.tsx`
- `src/shared/ui/Button.stories.tsx`
- `src/shared/ui/Badge.stories.tsx`
- `src/shared/ui/Card.stories.tsx`

The Atlas v4 reference story covers color, type, shadows, glyphs, buttons,
badges, and cards in one review surface.

## 7. Drift Control

Token drift is checked by:

```bash
npm --prefix policy-engine/apps/runtime-dashboard run design:atlas-v4
```

The check compares the v4 reference token file against production light and
dark theme tokens. Every accepted difference must be present in
`ATLAS_V4_ADOPTION.md`.

The broader polish gate includes it through:

```bash
npm --prefix policy-engine/apps/runtime-dashboard run design:polish
```

## 8. Design Laws

1. Prefer semantic tokens over raw colors in product components.
2. Keep teal, ember, and gold as the only product signal colors.
3. Treat time, provenance, uncertainty, and trust as first-class UI primitives.
4. Keep operational UI dense but readable; avoid decorative card-heavy pages.
5. Use Atlas glyphs for domain meaning and utility icons for generic actions.
6. Keep dark theme warm unless ADR-047 is superseded.
7. No token drift without a written adoption decision.
