# ADR-042: Janus-Atlas Dual Brand

## Status

Approved

## Date

2026-04-22

## Context

PolicyOS today ships a single brand mark — the Atlas glyph — which lives
in the top rail, favicon, marketing, and login screen. As the platform
adds primitives that do not fit the "atlas of evidence" metaphor
(time-as-primitive, provenance-on-hover, counterfactual layer), the Atlas
mark alone is misleading: it promises a map, not a gated bi-directional
engine.

The visual-language phase (Phase 1.1 of the design plan) needs a second
brand artefact that expresses the **bi-directional, gated** character of
the engine — the Janus face — without replacing Atlas. Replacing Atlas
would cost recognition equity and force the landing page and
marketing surface to re-identify.

The question is therefore not "which mark" but "what roles do the two
marks play, and where does each appear?"

Options considered:

1. **Replace Atlas with Janus.** Rejected: kills recognition built up in
   existing user communications and in git history references.
2. **Two marks with no layering rule.** Rejected: leads to both marks
   appearing on the same screen — design review already sees this as
   clutter.
3. **Dual brand with explicit role separation.** Accepted — see Decision.

## Decision

1. PolicyOS maintains **two** brand artefacts:

   - `AtlasBrand` — the existing mark. Continues unchanged as an API
     surface for consumers (`<AtlasBrand size={24 | 32 | 48} />`).
   - `JanusGlyph` — a new gated-engine mark, introduced in Phase 1.1
     (`<JanusGlyph size={16 | 24 | 32} variant="mark" | "line" |
"serif-punctuation" intent={…} inverted={…} />`).
2. The two marks **never appear on the same viewport**. Role assignment:

   - Atlas: marketing surfaces, landing page, login, favicon on
     unauthenticated routes, email signatures, external documents.
   - Janus: product chrome (top rail, side rail, sigil bar on decision
     packets), favicon on authenticated routes, in-product typographic
     punctuation `)·(`.
3. The Janus line variant `)·(` is permitted inline in prose as the
   `PolicyPropositionMark` — the typographic signature of a policy
   proposition. No other glyph carries this role.
4. Favicon alternation is implemented by swapping `<link rel="icon">`
   in the `<head>` based on route authentication state.
5. Recognition of the updated Atlas mark is gated by a repository-backed
   recognizability evidence sheet plus a 16 px visual-regression baseline,
   not by an untracked ad hoc blind test.

Source of truth:

- `apps/runtime-dashboard/src/shared/brand/JanusGlyph.tsx`
- `apps/runtime-dashboard/src/shared/brand/AtlasBrand.tsx`
- `apps/runtime-dashboard/public/atlas/logo-janus.svg`
- `apps/runtime-dashboard/public/atlas/favicon.svg`

## Consequences

- Existing consumers of `<AtlasBrand />` are unaffected (API unchanged).
- A new ESLint rule in `eslint-plugin-local` forbids `<AtlasBrand />` in
  files under `src/features/**` and forbids `<JanusGlyph />` in files
  under `src/app/marketing/**`; this encodes the role separation.

- Design review gains a new checklist item: "Are both brands present on
  the same viewport? If so — block."

- Marketing collateral regenerations (Phase 1.1, week 3) touch landing
  page assets only; in-product chrome is unaffected by Atlas edits.

## Concrete impact

Files created or modified in Phase 1.1:

- New: `apps/runtime-dashboard/src/shared/brand/JanusGlyph.tsx`
- New: `apps/runtime-dashboard/src/shared/brand/JanusGlyph.test.tsx`
- New: `apps/runtime-dashboard/src/shared/brand/JanusGlyph.stories.tsx`
- New: `apps/runtime-dashboard/public/atlas/logo-janus.svg`
- New: `apps/runtime-dashboard/public/atlas/favicon.svg`
- Modified: `apps/runtime-dashboard/public/atlas/logo-mark.svg`
- Modified: `apps/runtime-dashboard/public/atlas/logo-mark-inverse.svg`
- Modified: `apps/runtime-dashboard/src/app/providers/RouteIconProvider.tsx`
  (favicon alternation)

- New ESLint rule:
  `apps/runtime-dashboard/eslint-plugin-local/rules/brand-role-separation.js`

## Related Decisions

- Related: [ADR-045](ADR-045-glyph-alphabet-limit-10.md) — the ten
  radicals are a separate alphabet from the two brand marks and do not
  count against this rule.

- Related: [ADR-046](ADR-046-authored-text-registry.md) — the
  AuthoredText registry is a textual analogue of the dual-brand role
  separation.
