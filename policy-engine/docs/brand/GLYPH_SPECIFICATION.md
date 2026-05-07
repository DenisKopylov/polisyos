# Glyph Specification

> Geometric, stroke, and grammatical rules for the ten-radical PolicyOS glyph
> alphabet. Source of truth for all SVG assets under
> `apps/runtime-dashboard/public/atlas/glyphs/` and the
> `shared/brand/glyph-vocabulary.ts` map.

- Status: Foundation (Phase 1.0)
- Date: 2026-04-22
- Owner: Denis Kopylov
- Authoritative ADR: [ADR-045](../adr/ADR-045-glyph-alphabet-limit-10.md)
- Related: [COMPOSITION_RULES](COMPOSITION_RULES.md), [UNCERTAINTY_LANGUAGE](UNCERTAINTY_LANGUAGE.md)

## 1. Principles

1. **Ten radicals, no more.** The alphabet is closed. Additions require an ADR
   that retires an existing radical; the domain vocabulary is 18 terms (see
   `glyph-vocabulary.ts`), so each radical typically carries 1–2 terms.
2. **Monoline geometry.** All glyphs are drawn on a 5×5 unit grid, stroke
   `1.25u–1.5u`, `stroke-linecap="round"`, `stroke-linejoin="round"`. Fills are
   `none`, except single positional dots where the radical demands one.
3. **currentColor.** `stroke="currentColor"` always. No hard-coded hex. Tint
   is applied by the `intent` prop of `<Glyph />`, which sets `color` on the
   SVG host.
4. **No ornament.** No emboss, no gradient fill, no shadow inside the viewBox.
   The only permitted modulation is stroke style (solid / dashed / double)
   which carries semantic meaning.
5. **Legibility at 12px.** Every radical must survive render at 12px on a
   standard display. Sub-pixel antialiasing artefacts disqualify a glyph.

## 2. Grid and metrics

| Property             | Value                                               |
| -------------------- | --------------------------------------------------- |
| viewBox              | `0 0 24 24` (published asset)                       |
| Construction grid    | 5×5 unit, each unit = `4.8` SVG units               |
| Optical padding      | 2 SVG units on each side (glyph lives inside 20×20) |
| Default stroke-width | `1.5` (heavy), `1.25` (fine) — see §4               |
| Stroke linecap       | `round`                                             |
| Stroke linejoin      | `round`                                             |
| Fill                 | `none` on all strokes, `currentColor` on dots only  |
| Diacritic offset     | `2u` from the anchor point (see §5)                 |

Assets are sized responsively by `<Glyph size={12 | 14 | 16 | 24} />`. The
`12px` and `14px` sizes use the **fine** stroke variant; `16px` and `24px` use
the **heavy** variant. This is enforced by the component (not by separate
files) via CSS `stroke-width` override.

## 3. The ten radicals

Each radical has a canonical Unicode anchor (for documentation only — SVGs are
always used in UI; Unicode is never rendered in JSX — see
`eslint-rule-no-raw-emoji-in-jsx`).

| #   | Name              | Anchor | Vocabulary terms                             | Geometry                                                                                     |
| --- | ----------------- | ------ | -------------------------------------------- | -------------------------------------------------------------------------------------------- |
| 1   | `intervention`    | ⊙      | intervention, policy-action                  | Circle r=2u centred, solid dot r=0.5u centred                                                |
| 2   | `evidence`        | ▲      | evidence, observation, claim                 | Equilateral triangle, apex at (2.5u, 0.5u), base at y=4u                                     |
| 3   | `provenance`      | ⟿      | provenance, lineage, source-chain            | Horizontal tilde curve from (0.5u, 2.5u) to (4u, 2.5u), terminating arrowhead                |
| 4   | `transport`       | ⇄      | transport, generalisation, external-validity | Two horizontal arrows, upper pointing right at y=2u, lower pointing left at y=3u             |
| 5   | `counterfactual`  | ⋌      | counterfactual, hypothetical, what-if        | Two crossing diagonals (2.5u,0.5u)–(0.5u,4.5u) and (2.5u,0.5u)–(4.5u,4.5u)                   |
| 6   | `identifiability` | ≔      | identification, estimand, identified-set     | Two horizontal parallel lines at y=1.5u and y=3.5u, colon of two dots right of lines         |
| 7   | `reproducibility` | ⟳      | reproducibility, replay, re-run              | 270° arc r=1.75u centred, terminating arrowhead curling to origin                            |
| 8   | `governance-pass` | ◫      | governance-approved, compliant, ratified     | Square 4×4u centred, with a single vertical line at x=1.5u inside                            |
| 9   | `blocker`         | ⊘      | blocker, denied, legal-stop                  | Circle r=2u centred, diagonal line (0.5u,0.5u)–(4.5u,4.5u) through it                        |
| 10  | `freshness`       | ◷      | freshness, staleness, age-of-evidence        | Circle r=2u centred, radius from centre to (2.5u, 0.5u) and to (4u, 2.5u) forming a quadrant |

## 4. Stroke weight

| Weight | Value                | Usage                                                            |
| ------ | -------------------- | ---------------------------------------------------------------- |
| Fine   | `stroke-width: 1.25` | Glyphs rendered at 12px or 14px; inline in prose; eyebrow strips |
| Heavy  | `stroke-width: 1.5`  | Glyphs rendered at 16px or 24px; chart annotations; buttons      |

The fine/heavy switch is a function of **rendered size, not semantic intent**.
Intent is carried by color and stroke style.

## 5. Diacritics (TrustView only)

Diacritics are used **exclusively** in the TrustView (Phase 2.6) and in
uncertainty overlays (Phase 1.2). They must never appear in default UI.

| Diacritic | Geometry                                                                                            | Semantic                                            |
| --------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `strict`  | Single horizontal bar of length `1.5u` placed `2u` above the radical's topmost point, stroke `1.25` | Claim holds under strict identification assumptions |
| `assumed` | Two short horizontal bars of length `1u` each, vertically stacked `2u` above, separated by `0.5u`   | Claim rests on a stated but untested assumption     |
| `scoped`  | Open parenthesis `(` to the left at `x = -1.5u`, closing `)` at `x = 6.5u`, stroke `1.25`           | Claim is scoped to a named sub-population           |

## 6. Stroke style as modifier

The `strokeStyle` prop of `<Glyph />` encodes epistemic status:

| Style    | SVG `stroke-dasharray`                    | Semantic                                  |
| -------- | ----------------------------------------- | ----------------------------------------- |
| `solid`  | (none)                                    | Observed in the data                      |
| `dashed` | `2 1.5` (units)                           | Hypothetical / counterfactual / estimated |
| `double` | Two concentric strokes, inner offset `1u` | Proved / formally verified                |

Stroke style is orthogonal to intent (color). A `dashed` glyph can still be
`intent="verified"` — the combination reads as "hypothetical scenario that was
itself evidence-verified."

## 7. Intent (color) mapping

| Intent     | CSS var        | Used when                          |
| ---------- | -------------- | ---------------------------------- |
| `default`  | `var(--ink)`   | Neutral inline use                 |
| `verified` | `var(--teal)`  | Evidence or governance pass        |
| `blocked`  | `var(--ember)` | Blocker, rejection, guardrail trip |
| `pending`  | `var(--gold)`  | Review or pending-freshness        |

These four map 1:1 onto the signal triad + neutral. No additional intents are
permitted; PolicyOS does not have an "info blue" and will not acquire one.

## 8. Grammar

1. **Vocabulary is fixed.** Only terms in `glyph-vocabulary.ts` may map to a
   glyph. Adding a term without a mapped radical is a review-blocker.
2. **No stacking.** Glyphs do not combine to form compound symbols. Use two
   separate `<Glyph />` components with ProvenanceStrip spacing.
3. **One diacritic per glyph.** `strict + scoped` is not valid; a claim that
   is both strict and scoped uses `strict` and carries scope in prose.
4. **No inversion.** A glyph on a dark background uses `inverted` prop to
   lighten stroke color, but geometry never flips.
5. **No rotation.** Radicals are drawn in a canonical orientation. Rotation
   is not used as a modifier.

## 9. File and export conventions

- Files live in `apps/runtime-dashboard/public/atlas/glyphs/<name>.svg`.
- Each SVG is optimised with `svgo` (no `style` blocks, no `class` attributes,
  no inline `width`/`height`, preserve `viewBox`).

- The React component `<Glyph />` imports via `?react` and treats the SVG as
  a pure stroke map.

- `glyph-vocabulary.ts` is the single source of truth for
  `domainTerm → glyphName`. The test `pnpm test:glyph-vocabulary` parses this
  document and fails if a radical is added here but not wired up (or vice
  versa).

## 10. What is explicitly out of scope

- Maskots, illustrations, brand spot art.
- Emoji, dingbats, or Unicode decorative glyphs in product UI.
- Glyph animations beyond state transitions defined in
  [MOTION](MOTION.md) (`--motion-duration-moderate` fade is the only
  sanctioned change).

- More than ten radicals. Expanding the alphabet requires retiring an
  existing radical via ADR.
