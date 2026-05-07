# PolisyOS Atlas Control Room

Frontend redesign concept for `runtime-dashboard`.

## What changed

The current frontend is organized as a set of runtime utility pages. This concept reframes the product around four operator workflows:

1. `Command Center`
   A high-signal overview for runs, governance pressure, evidence freshness, and operator queue.
2. `Scenario Composer`
   A decision-first launch flow that blends natural-language input, intervention design, evidence lanes, and launch controls.
3. `Decision Workspace`
   A single operating view for verdict, narrative rationale, distribution impact, governance passes, and provenance.
4. `Evidence Fabric`
   A unified data/provenance surface that replaces fragmented sources, artifact, and data utility views.

## Visual direction

- Editorial control room instead of generic admin dashboard
- Sandstone and paper backgrounds with graphite structure
- Teal for progress / approval, ember for risk / blockers, gold for ambiguity
- Large compressed headlines, mono utility labels, rounded glass panels
- Fewer tables, more ranked cards, action queues, and decision summaries

## Files

- `index.html`
  The static high-fidelity concept board.
- `styles.css`
  The visual system and all layouts.

## Exported boards

Rendered PNGs live in `_build/docs/explanation/runtime-redesign/playwright/`:

- `polisyos-command-center.png`
- `polisyos-scenario-composer.png`
- `polisyos-decision-workspace.png`
- `polisyos-evidence-fabric.png`
- `polisyos-mobile-concepts.png`

## Figma import map

If you open Figma manually, import the PNGs as separate frames in this order:

1. `01 Command Center`
2. `02 Scenario Composer`
3. `03 Decision Workspace`
4. `04 Evidence Fabric`
5. `05 Mobile Pulse`
6. `06 Mobile Brief`

## Recommended implementation direction

- Keep the current route coverage but regroup navigation around workflows, not backend subsystems
- Make `/runs/:runId` the center of gravity for decision review
- Merge `/sources`, `/data`, and part of `/artifacts` into one evidence/data fabric flow
- Turn `/launch` into a scenario composition workspace with strong previews and governance posture
