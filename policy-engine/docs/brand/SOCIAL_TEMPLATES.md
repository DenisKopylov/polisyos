# Social Templates

This page is a design contract for a bounded share preview, not a deployed
social-card or public-publication service. At source snapshot
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, the dashboard contains an OG card
and HTML/SVG/PNG generation helpers, but the tracked-source walk finds them
consumed only by their test file. The capability state is
`implemented_but_not_orchestrated`: there is no production route or service
binding the helper to a publishable public record. The
[frontend surface map](../reference/frontend/current-surface-map.md) records
the source and test limits. The tests were inspected, not run.

If a successor consumer is admitted, OG/social cards may be deterministic
previews for explicitly shareable PolicyOS URLs. They never render raw source
evidence, and fixture text such as `verified` is not verification input.

## Card Contract

Each card includes:

- PolicyOS Runtime label;
- URL kind: run, compare or scenario;
- title;
- one key quantity;
- trust status;
- temporal scope;
- draft/verified state.

## Privacy Rules

- Input must be a public summary payload.
- Raw source snippets, private comments, hidden reviewer names and full lineage
  graphs are blocked.
- Hashes may be truncated, never removed when trust status is shown.

## Rendering Rules

- Fixed 1200 × 630 canvas.
- Satori renders the canonical SVG; `@resvg/resvg-js` produces PNG exports.
- Font stack is pinned to bundled `@fontsource/manrope` assets; no remote font
  fetch is allowed.
- No remote images.
- No gradients that encode status.
- Social text must remain legible at thumbnail size.
