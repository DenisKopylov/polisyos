# Uncertainty Language

> Seven visual patterns for rendering epistemic state in PolicyOS charts and
> prose. Uncertainty is a first-class object; this spec defines how it looks,
> where it applies, and the anti-patterns that are not permitted.

- Status: Foundation (Phase 1.0)
- Date: 2026-04-22
- Owner: Denis Kopylov
- Authoritative ADR: [ADR-043](../adr/ADR-043-provenance-law.md)
- Related: [GLYPH_SPECIFICATION](GLYPH_SPECIFICATION.md), [A11Y_CONTRAST](A11Y_CONTRAST.md), [MOTION](MOTION.md)

## 1. Why a language

PolicyOS already has primitives that _render_ uncertainty: `ConfidenceDial`,
`ForestPlot`, `GradedErrorBar`, `UncertaintyDisplay`. They are not wrong, but
they are independent — each component encodes the same underlying distinction
(point-estimate vs interval vs identified set vs counterfactual spread) in a
slightly different visual idiom. The result: an analyst must re-learn each
component.

The seven patterns below collapse those idioms into one grammar. Every new
chart component must adopt the patterns instead of inventing its own.

## 2. The seven patterns

### P1. Identified region — solid

A region rendered as a solid fill with `fill-opacity: 0.18` of
`var(--teal-vibrant)` on a `var(--paper)` canvas, border `var(--teal)` stroke
1px. Used for identified sets, point estimates with an explicit confidence
bound, or any quantity where the lower and upper bounds are _known_ in the
formal sense.

**Applies to:** `ForestPlot` (CI bounds), `UncertaintyBand` (identified region
of a time series), `QuantileDotplot` (identified quantiles).

**Anti-pattern:** using P1 for regions whose bounds are _modelled under an
assumption_. That is P2.

### P2. Estimated region — hatched 45°

A region rendered with SVG pattern-fill: 45° hatching, line spacing `4px`,
stroke `1px` `var(--slate)` at `0.4` opacity, background `var(--paper)`. The
region is still bounded by a `var(--slate)` 1px stroke at 0.8 opacity. Used
for intervals produced under modelling assumptions that are stated but not
refuted (e.g. bootstrap CI, Bayesian credible interval).

**Applies to:** `ForestPlot` (estimated intervals),
`HypotheticalOutcomePlot` (sample realisations' envelope),
`UncertaintyBand` (modelled forecast CI).

### P3. Assumed region — dotted field

A region rendered with SVG pattern-fill: dotted lattice, spacing `8px`, dot
radius `1px`, fill `var(--gold-vibrant)` at `0.5` opacity, background
`var(--paper)`. Used when the bounds rest on an assumption that the platform
has **explicitly flagged** (sensitivity analysis failed to refute; user must
read the accompanying justification).

**Applies to:** `GradedErrorBar` (assumed-bound grade), `FanChart` (outer
quantiles 10/90), any `UncertaintyPatterns` component.

### P4. Disputed marker — ember glyph

A single `<Glyph name="counterfactual" intent="blocked" />` rendered inside
the region with `absolute` positioning (centre or leader line to point).
Hover or focus reveals `{who, when, why}` of the dispute.

**Applies to:** `DisputedMarker` (new), `ForestPlot` (per-study override),
`PolicyDiff` (contested edges in Phase 2.3).

### P5. Quantile dots — Hullman

A stacked dot representation of a quantile distribution following Hullman et
al. (2018). Fixed at 20 dots per distribution unless density mode is
`compact` (10 dots) or `spacious` (50 dots). Dots use `var(--teal-vibrant)`
at `0.85` opacity; outlier dots (outside central 80%) carry a 1px stroke in
`var(--gold-vibrant)`.

**Applies to:** `QuantileDotplot`, `ForestPlot` (optional visualisation
toggle), any forecast distribution.

### P6. Hypothetical outcome plot — animated frames

Draw `n` sample realisations of a distribution, cycle through them at
`2Hz` (one frame every 500ms) with `--motion-ease-standard`. Each realisation
rendered as a thin line (`stroke-width: 1`, `stroke-opacity: 0.6`) over the
static `P2 estimated region`. With `prefers-reduced-motion: reduce`, the
component **must** fall back to a layered translucent static render (all
frames drawn with `stroke-opacity: 0.12`).

**Applies to:** `HypotheticalOutcomePlot` and only that component.

**Motion tokens:** duration `--motion-duration-hop: 500ms`, ease
`--motion-ease-standard`.

### P7. Epistemic gradient — fade

A colour fade from `var(--teal)` at 100% opacity (at the point estimate) to
`var(--teal-soft)` at 0% opacity (at the tail quantile). Encoded as
`linear-gradient` along the axis of uncertainty. Used for probability
densities where discrete bounds are less informative than the _shape_ of
belief.

**Applies to:** `FanChart` (inner gradient), `ConfidenceDial` (arc density),
`UncertaintyDisplay` (bar fill).

## 3. Pattern-fill accessibility

Patterns P2 and P3 serve double duty as color-blind-safe encodings of the
identified / estimated / assumed distinction. They are not optional
decoration.

| Pattern      | Hatch     | Spacing | Opacity    | Swatch test target                 |
| ------------ | --------- | ------- | ---------- | ---------------------------------- |
| P1 solid     | —         | —       | 0.18 fill  | Distinguishable from canvas at 3:1 |
| P2 estimated | 45° lines | 4px     | 0.4 stroke | Distinguishable from P1 at 3:1     |
| P3 assumed   | Dots      | 8px     | 0.5 fill   | Distinguishable from P2 at 3:1     |

All three must be distinguishable under Deuteranopia simulation (`axe-core`
CLI run with the deuteranopia filter). Verified by the test
`pnpm test:uncertainty-patterns:colorblind`.

## 4. Do / don't

### Do

- Use P1 only when the bounds are formally identified; when in doubt,
  demote to P2.

- Pair every uncertainty pattern with a text caption disclosing the
  quantile, the method (`bootstrap`, `Bayesian`, `analytic`), and the
  assumption class (`identified | estimated | assumed`).

- Render disputed markers above the fill layer, never inside it.

### Don't

- Don't use translucent gradient fills for assumed regions — they read as
  estimated and erase the assumption flag.

- Don't add a separate pink / orange / blue for a new uncertainty kind;
  every new kind must map to one of the seven patterns.

- Don't animate P1–P5 transitions on data load — reduced-motion users see
  visual flashing. Only P6 is animated, and only with fallback.

## 5. Components affected

The following components must adopt the patterns during Phase 1.2:

- `shared/charts/ConfidenceDial.tsx` → P7 (replace current fill).
- `shared/charts/ConfidenceGauge.tsx` → P1 + P2 (current / forecast).
- `shared/charts/ForestPlot.tsx` → P1 + P2 + P4.
- `shared/charts/GradedErrorBar.tsx` → P2 + P3 (by grade).
- `shared/charts/UncertaintyDisplay.tsx` → P7 (bar fill).

New components:

- `shared/charts/UncertaintyBand.tsx` → P1 / P2 / P3 based on
  `assumptionClass` prop.

- `shared/charts/FanChart.tsx` → P1 + P7 inside; P2 for outer fan.
- `shared/charts/QuantileDotplot.tsx` → P5.
- `shared/charts/HypotheticalOutcomePlot.tsx` → P6.
- `shared/charts/UncertaintyPatterns.tsx` → pure SVG pattern library
  exporting P1–P3 fills.

- `shared/charts/DisputedMarker.tsx` → P4.

## 6. SVG pattern references

The canonical SVG definitions for P2 and P3 live in
`apps/runtime-dashboard/src/shared/charts/patterns/` and are consumed
via `<defs>` blocks in the chart components. They are not inlined per-chart.

```xml
<pattern id="uncertainty-estimated"
         patternUnits="userSpaceOnUse"
         width="4" height="4"
         patternTransform="rotate(45)">
  <line x1="0" y1="0" x2="0" y2="4"
        stroke="var(--slate)"
        stroke-width="1"
        stroke-opacity="0.4" />
</pattern>

<pattern id="uncertainty-assumed"
         patternUnits="userSpaceOnUse"
         width="8" height="8">
  <circle cx="2" cy="2" r="1"
          fill="var(--gold-vibrant)"
          fill-opacity="0.5" />
  <circle cx="6" cy="6" r="1"
          fill="var(--gold-vibrant)"
          fill-opacity="0.5" />
</pattern>
```

## 6.5. Storybook links

These links assume local Storybook is running via `corepack pnpm run storybook` in
`apps/runtime-dashboard/`.

- [UncertaintyBand](http://localhost:6006/?path=/story/charts-uncertainty-uncertaintyband--identified-series)
- [FanChart](http://localhost:6006/?path=/story/charts-uncertainty-fanchart--identified)
- [QuantileDotplot](http://localhost:6006/?path=/story/charts-uncertainty-quantiledotplot--horizontal)
- [HypotheticalOutcomePlot](http://localhost:6006/?path=/story/charts-uncertainty-hypotheticaloutcomeplot--animated)

## 7. Out of scope

- Gradient-based encoding of _categorical_ (non-uncertainty) dimensions.
- Animated transitions between P1 and P2 as data refines.
- 3D volumetric renders of probability densities.
