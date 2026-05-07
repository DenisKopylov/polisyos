# Motion Specification

> Duration tokens, easing curves, state-transition rules, and reduced-motion
> fallbacks for the PolicyOS interface. Motion is **restrained by default**
> and carries semantic meaning when present.

- Status: Foundation (Phase 1.0)
- Date: 2026-04-22
- Owner: Denis Kopylov
- Token source: `apps/runtime-dashboard/src/styles.css` (under `@layer base`)
- Related: [GLYPH_SPECIFICATION](GLYPH_SPECIFICATION.md), [UNCERTAINTY_LANGUAGE](UNCERTAINTY_LANGUAGE.md)

## 1. Philosophy

1. **Motion is a semantic signal, not decoration.** A transition exists only
   if it communicates causality, continuity, or state change that would be
   harder to read without it.
2. **Reduced motion is a first-class path.** Every animated component ships
   a `prefers-reduced-motion: reduce` branch, and the test suite exercises
   both.
3. **Durations are discrete.** We publish four canonical durations; custom
   in-between values are banned.
4. **Easing is discrete.** Three canonical easings; everything else is
   banned.

## 2. Duration tokens

The existing `--motion-fast / --motion-moderate / --motion-slow` in
`styles.css` are kept as legacy aliases; the four tokens below are canonical
going forward.

| Token    | CSS variable                 | Value   | Usage                                                                                               |
| -------- | ---------------------------- | ------- | --------------------------------------------------------------------------------------------------- |
| Instant  | `--motion-duration-instant`  | `80ms`  | State toggles that feel wrong with animation (checkbox, radio, focus ring appearance)               |
| Fast     | `--motion-duration-fast`     | `160ms` | Hover fills, button press, small-distance translation (< 8px)                                       |
| Moderate | `--motion-duration-moderate` | `240ms` | Panel expand/collapse, popover entry, tab underline slide                                           |
| Slow     | `--motion-duration-slow`     | `360ms` | Full-page transitions, drawer entry, large distance or multi-property (translate + opacity + scale) |
| HOP      | `--motion-duration-hop`      | `500ms` | Hypothetical outcome plot frame cycle (Phase 1.2, P6)                                               |

Existing aliases map as follows (left unchanged):

```css
--motion-fast: 160ms; /* = --motion-duration-fast */
--motion-moderate: 180ms; /* historical; new code uses --motion-duration-moderate (240ms) */
--motion-slow: 240ms; /* historical; new code uses --motion-duration-slow (360ms) */
```

Phase 1.4 will migrate components off the aliases; Phase 1.0 only declares
the new tokens.

## 3. Easing tokens

| Token      | CSS variable               | Curve                        | Usage                                                    |
| ---------- | -------------------------- | ---------------------------- | -------------------------------------------------------- |
| Standard   | `--motion-ease-standard`   | `cubic-bezier(0.2, 0, 0, 1)` | Default for enter, exit, and in-place changes            |
| Emphasised | `--motion-ease-emphasised` | `cubic-bezier(0.3, 0, 0, 1)` | For sheet entry, modal entry, long-distance translations |
| Linear     | `--motion-ease-linear`     | `linear`                     | Progress bars, transport indicators, HOP cycling         |

**No `ease-in`, no spring curves, no bounce.** Anticipatory or overshoot
motion is banned.

## 4. State-transition inventory

The following state changes are motion-eligible in Wave 1 and Wave 2. If a
state change is not in this table, it must not animate.

| State change                               | Token                        | Ease         | Properties                                       |
| ------------------------------------------ | ---------------------------- | ------------ | ------------------------------------------------ |
| Button hover → pressed                     | `--motion-duration-fast`     | `standard`   | `background-color`, `box-shadow`                 |
| Checkbox checked toggle                    | `--motion-duration-instant`  | `standard`   | `opacity` of check glyph only                    |
| Focus ring appearance                      | `--motion-duration-instant`  | `standard`   | `box-shadow`                                     |
| Popover / tooltip entry                    | `--motion-duration-fast`     | `standard`   | `opacity` (0→1), `translate-y` (4px→0)           |
| Popover / tooltip exit                     | `--motion-duration-instant`  | `standard`   | `opacity` (1→0)                                  |
| Tab underline slide                        | `--motion-duration-moderate` | `standard`   | `transform: translateX`                          |
| Accordion expand                           | `--motion-duration-moderate` | `standard`   | `height` via Radix token                         |
| Drawer / sheet entry                       | `--motion-duration-slow`     | `emphasised` | `transform: translateX`, `opacity`               |
| Modal entry                                | `--motion-duration-slow`     | `emphasised` | `opacity`, `scale` (0.96→1)                      |
| Modal exit                                 | `--motion-duration-moderate` | `standard`   | `opacity`, `scale` (1→0.96)                      |
| Toast entry / exit                         | `--motion-duration-moderate` | `standard`   | `opacity`, `translate-y`                         |
| Page route transition                      | `--motion-duration-moderate` | `standard`   | `opacity` only (no translate)                    |
| Chart enter on mount                       | `--motion-duration-slow`     | `standard`   | `opacity` (0→1); data does **not** animate       |
| Uncertainty region reveal                  | `--motion-duration-moderate` | `standard`   | `opacity` (0→1); fill pattern does **not** morph |
| HOP frame cycle (P6)                       | `--motion-duration-hop`      | `linear`     | `opacity` cross-fade between sample lines        |
| Glyph intent change                        | `--motion-duration-moderate` | `standard`   | `color` only — geometry never animates           |
| Time scrubber cursor move (B1, Phase 2.1)  | `--motion-duration-instant`  | `linear`     | `transform: translateX` on scrubber thumb        |
| Provenance hover highlight (B2, Phase 2.2) | `--motion-duration-fast`     | `standard`   | `stroke-width`, `opacity` on lineage edges       |

## 5. Reduced-motion rules

All animated components **must** respect `prefers-reduced-motion: reduce`.

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

This default is declared once in `styles.css`. Per-component overrides are
required when an animation encodes information (e.g. HOP frames):

| Component                      | Reduced-motion fallback                                                           |
| ------------------------------ | --------------------------------------------------------------------------------- |
| `HypotheticalOutcomePlot` (P6) | Static layered render — all sample lines at `stroke-opacity: 0.12` simultaneously |
| Time scrubber (B1)             | Instantaneous jumps to target time, no tween                                      |
| Route transition               | Opacity change only, 0.01ms duration                                              |
| Toast                          | Appears instantly; still auto-dismisses with a static fade-out at 0.01ms          |
| Accordion                      | Snap open / closed; `height` jumps between 0 and measured                         |
| Modal                          | No scale, no fade; `display: block` / `none` only                                 |

## 6. Enter / exit direction rules

- Popovers, tooltips, drawers, and sheets enter **from the direction of their
  anchor**. A popover below a trigger enters with `translate-y` from `-4px`
  to `0`. A drawer from the right enters `translate-x` from `100%` to `0`.

- Route transitions never translate — opacity only. Horizontal slide is
  reserved for linear workflows (wizards); Wave 1 has none.

- Glyphs do not enter with motion. They either exist or they don't.

## 7. What we don't animate

- **Data values.** Axis ticks, bar heights, line paths, chart bounds do not
  tween. When data updates, the chart re-renders in place; any visual
  transition is limited to opacity fades on the axis labels if the axis
  domain changes (`--motion-duration-moderate`, `standard`).

- **Uncertainty regions.** Pattern fills never morph. A region's
  epistemic class (P1 → P2 → P3) does not cross-fade; the region
  cross-fades via opacity only.

- **Numerals.** Counting animations are banned. Numbers snap to their new
  value.

- **Skeletons.** Shimmer gradients are banned — skeletons are static.
- **Parallax.** Any of it.

## 8. Timing inspection in tests

Every component-level test that asserts animated behaviour must:

1. Render with `prefers-reduced-motion: no-preference` and assert the
   motion fires (e.g. via `framer-motion`'s reduced-motion override or
   inspecting computed styles after `requestAnimationFrame`).
2. Render with `prefers-reduced-motion: reduce` and assert the state
   change is instantaneous (no tween frames).

The helper `testing/motion.ts` exports `renderWithReducedMotion` and
`renderWithFullMotion` wrappers.

## 9. Out of scope

- 3D transforms (perspective, rotation around Y, Z).
- Physics-based springs (framer-motion `spring` or equivalent). All
  transitions are explicit cubic-bezier.

## 10. Phase 2.7 System Polish Addendum

Canonical runtime tokens now live in
`apps/runtime-dashboard/src/styles/motion.css`; reduced-motion and
forced-color fallbacks live in `apps/runtime-dashboard/src/styles/media.css`.
New components must use those files, not local one-off durations.

Additional Wave 2 rules:

- Temporal scrubber, provenance popovers, TrustInspector and compare panels must
  remain understandable with all transitions disabled.
- OG/email/print rendering must not depend on animation state.
- `SmallMultiples` uses no animated axis scaling; selected cells change via
  border/outline only.
- Motion lint blocks custom `transition-duration` values outside the canonical
  tokens unless the value is inside the legacy compatibility block.

### Forbidden Motion

- GSAP, Lottie, or any animation runtime beyond CSS transitions and
  framer-motion's `motion.*` primitives.
- Shimmer/skeleton motion that communicates loading without a textual loading
  state.
- Continuous chart morphing where the same comparison can be represented as a
  discrete state change.
