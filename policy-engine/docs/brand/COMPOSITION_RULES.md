# Composition Rules

> Anti-patterns and adjacency constraints that protect the Atlas + Janus
> visual system from entropy. Read before any new screen, chart, or
> component composition.

- Status: Foundation (Phase 1.0)
- Date: 2026-04-22
- Owner: Denis Kopylov
- Enforced by: design review, `eslint-plugin-boundaries`, `dependency-cruiser`,
  and the tests listed in §7.

## 1. Core invariants (copied from the plan, §2)

These apply without exception. A PR that violates them is blocked.

- No mascot. Roles are filled by glyphs and the AuthoredText registry.
- Palette is sandstone + graphite. No blue introductions. No three-stop
  gradients.

- Signal triad is `teal = verified, ember = blocked, gold = pending`. New
  semantics find form inside the triad (pattern-fills, glyphs, diacritics).

- Atlas mark is not replaced by Janus. Janus is a second layer.
- No 3D renders, wax seals, heavy bevel or emboss.
- Ten radicals, no more. Alphabet is closed.
- No emoji anywhere, including CLI and system messages.
- OpenAPI contracts change additively with ≥ 2-release deprecation window.
- `eslint-plugin-boundaries` and `dependency-cruiser` rules are never
  disabled.

## 2. Adjacency: what can sit next to what

| Element A             | Element B           | Rule                                                                                                                                                    |
| --------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `<AtlasBrand />`      | `<JanusGlyph />`    | Only one of the two is visible per viewport. Janus takes over in product chrome; Atlas stays on marketing / login.                                      |
| `<Glyph />`           | `<Glyph />`         | Inline: separator is a single `var(--space-2)` (8px) gap. No bullet, no dot. In `ProvenanceStrip`, the strip handles spacing.                           |
| Chart                 | Chart               | Two charts side-by-side share at least one axis. If neither axis aligns, insert an explanatory divider (`<Divider label />`) — never rely on proximity. |
| `<EvidenceSigil />`   | `<Glyph />`         | Permitted; Sigil is always larger (≥ 48px) and owns its quadrant.                                                                                       |
| `<ProvenanceStrip />` | Title               | Strip goes above title (eyebrow position). Never inline with title. Never below.                                                                        |
| Dense numeric block   | Dense numeric block | Separate with `var(--space-4)` (16px) and at least one label. Never stack two unlabeled numeric rows.                                                   |
| Glyph                 | Text                | Glyph precedes text; use the `gap` prop of the enclosing flex, not a space character.                                                                   |
| Uncertainty region    | Uncertainty region  | Regions with different epistemic classes (P1 / P2 / P3) must not overlap on the same axis without an explicit legend.                                   |

## 3. Banned compositions

- **Atlas mark inside a chart.** The mark is never drawn inside data space.
  It belongs in chrome (header, footer, sigil bar).

- **Glyph inside a glyph.** No radical may be inscribed inside another
  radical. Use two glyphs and whitespace instead.

- **Gold next to ember in the same signal block.** Pending and blocked
  cannot co-occur on a single status pill — one is the current state.

- **Teal and ember in a two-color gradient.** The triad is discrete;
  gradients between signals are banned.

- **Glass-on-glass.** Two glass panels cannot overlap; the lower panel
  becomes a plain `--paper` or `--sand` surface.

- **Serif decoration inside mono blocks.** `Instrument Serif` never
  appears inside an `IBM Plex Mono` run; serif is for headings and
  `PolicyPropositionMark` only.

- **Dashed border as decoration.** Dashed strokes are reserved for the
  uncertainty language (P6 / counterfactual / hypothetical). A dashed
  divider in chrome is banned.

- **Inline emoji of any kind.** The ESLint rule
  `no-raw-emoji-in-jsx` covers decorative Unicode (⊙, ▲, etc.) — use
  `<Glyph />` instead.

- **Bullet lists with custom glyph markers.** Use a ProvenanceStrip or a
  plain disc bullet from the typography system, not radicals.

## 4. Density and spacing

- The base grid is `8px`. All padding and gap values snap to multiples
  of 4px (half-step allowed for icon alignment).

- Density modes (Phase 1.4) scale spacing tokens, not typography, not
  glyph stroke.

- Cards sit in a column grid of 4 / 8 / 12 columns at the three
  breakpoints; mixing column counts in a single row is banned.

- A panel's `--radius-panel` is `28px`; cards inside a panel use
  `--radius-card` (`24px`). Radius inside a card uses `--radius-sm`
  (`12px`). No intermediate values.

## 5. Layering

1. Canvas (`--canvas`).
2. Shell (`--sand` with glass treatment).
3. Panel (`--panel` at 0.82 alpha over shell).
4. Card (`--paper` on panel).
5. Inline elements (buttons, chips, glyphs) on card.
6. Tooltips, popovers, modals sit at `--z-popover` and above; they
   re-introduce `--paper` as their own card.

A chart's background is always the card it sits on — charts never paint
their own background.

## 6. Chrome rules

- Top rail uses `--graphite` background with light foreground tokens
  (`--sidebar-foreground`). No Atlas mark inside the rail; Janus glyph
  only.

- Bottom status / transport bar never carries a glyph for the signal
  triad — it uses a text chip (`verified`, `pending`, `blocked`) with
  an optional `<Glyph />` prefix at 14px.

- Footer is a single `<ProvenanceStrip density="compact" />` when the
  page has decision context; otherwise footer is empty.

## 7. Tests that enforce rules

| Rule                          | Enforced by                                                                                |
| ----------------------------- | ------------------------------------------------------------------------------------------ |
| No emoji in JSX               | `eslint-plugin-local/no-raw-emoji-in-jsx`                                                  |
| Glyph vocabulary completeness | `pnpm test:glyph-vocabulary`                                                               |
| Contrast matrix currency      | `contrast-matrix-is-current` CI job (see [A11Y_CONTRAST](A11Y_CONTRAST.md))                |
| Feature-slice boundaries      | `eslint-plugin-boundaries`, `dependency-cruiser`                                           |
| Motion fallbacks present      | `testing/motion.ts` helpers; every `.test.tsx` for an animated component covers both paths |
| No cross-gradient             | visual regression review + manual design review for any PR touching `gradients/`           |

## 8. Review rubric for new screens

1. Is the page built from existing `shared/ui` primitives, or does it
   introduce a new layout pattern? If the latter — ADR required.
2. Does every glyph map to a term in `glyph-vocabulary.ts`? If not —
   remove the glyph.
3. Does the screen use any uncertainty pattern? If yes — verify it
   matches one of P1–P7 in [UNCERTAINTY_LANGUAGE](UNCERTAINTY_LANGUAGE.md).
4. Does the screen carry decision context? If yes — a
   `<ProvenanceStrip />` sits in the eyebrow position; an
   `<EvidenceSigil />` is visible if there is a bundle hash to reference.
5. Are all contrast pairs in [A11Y_CONTRAST](A11Y_CONTRAST.md)? Pairs not
   listed must be added and regenerated in the same PR.
6. Does motion declare both `prefers-reduced-motion` branches?

## 9. Out of scope

- Copy conventions — see `docs/style-guide.md` for prose rules.
- Brand voice — owned by `docs/brand/UNCERTAINTY_LANGUAGE.md` for
  epistemic language and future `docs/brand/VOICE.md` (Phase 1.5).

- Domain vocabulary — owned by
  `frontend/runtime-dashboard/src/shared/brand/glyph-vocabulary.ts`.

## 10. Phase 2.7 Stacking Rules

Wave 2 primitives can appear on the same surface only in this order:

1. value or text;
2. uncertainty interval/method;
3. provenance cue;
4. counterfactual/scenario cue;
5. trust metadata.

If all five are present, the surface must collapse to an inspector affordance
instead of rendering five inline badges.

Additional anti-patterns:

- A `Quantity` must not show both a provenance popover trigger and an unrelated
  trust hash from another response.
- Counterfactual pattern and provenance status cannot share the same glyph.
- Dense tables use row-level trust inspection, not expanded metadata in every
  cell.
- Social/email/print templates must render from public summary payloads, never
  from raw source bodies.
- Categorical palettes are chart-only; they do not create new semantic status
  colors outside data series.

`tools/design/check-composition-rules.ts` enforces the highest-risk rules:
private raw-source rendering in social/email, forbidden motion shimmer, and
local hard-coded motion durations.
