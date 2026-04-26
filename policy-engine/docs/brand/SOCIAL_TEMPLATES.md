# Social Templates

OG/social cards are deterministic previews for explicitly shareable PolicyOS
URLs. They never render raw source evidence.

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
