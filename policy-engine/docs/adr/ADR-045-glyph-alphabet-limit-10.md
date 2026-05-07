# ADR-045: Closed Glyph Alphabet — Ten Radicals

## Status

Approved

## Date

2026-04-22

## Context

Phase 1.1 of the design plan introduces ten semantic glyphs — the
_radicals_ — as the non-textual visual vocabulary of PolicyOS. The
radicals currently map onto a 29-term domain vocabulary while remaining
geometrically constrained (§
[GLYPH_SPECIFICATION](../brand/GLYPH_SPECIFICATION.md)) and
semantically scarce.

The risk we have observed across similar systems: the glyph alphabet
grows. A product-marketing need lands with "we want a glyph for X";
a domain-team request lands with "we need a distinct mark for Y". A
twenty-glyph alphabet loses recognition; a sixty-glyph alphabet
becomes a second font whose users cannot be trained.

The question is whether the alphabet is closed by construction, and
if so, how additions are gated.

Options considered:

1. **Open alphabet, best effort.** Rejected: entropy path.
2. **Fixed alphabet, additions require design review.** Rejected:
   review alone has not been a strong enough gate in similar systems.
3. **Fixed alphabet, additions require ADR that retires an existing
   radical.** Accepted — see Decision. This makes each new radical a
   governance event that forces the team to justify the radical being
   retired and carry the replacement through its own lifecycle.

## Decision

1. The PolicyOS glyph alphabet is **closed at ten radicals**. The
   canonical list and geometry live in
   [GLYPH_SPECIFICATION](../brand/GLYPH_SPECIFICATION.md).
2. Adding a radical requires a new ADR that:

   - names the incoming radical, its geometry, and the vocabulary
     term it serves;
   - names the outgoing radical being retired;
   - supplies a migration plan for all product surfaces that used the
     outgoing radical;
   - is reviewed by design-review and domain owners before approval.
3. A PR that introduces an 11th glyph is blocked at review and at
   CI (the test `pnpm test:glyph-vocabulary` fails if the
   specification and the vocabulary file diverge).
4. The **stroke-style modifier** (`solid / dashed / double`) and the
   **diacritic modifier** (`strict / assumed / scoped`) are not
   radicals; they are orthogonal dimensions of each of the ten.
   They do not count against the limit.
5. The **intent colour** (`default / verified / blocked / pending`)
   is also not a radical; it maps to the signal triad.
6. The **brand marks** (`AtlasBrand`, `JanusGlyph`) are not radicals;
   they are brand artefacts with their own roles
   ([ADR-042](ADR-042-janus-atlas-dual-brand.md)).

Source of truth:

- [GLYPH_SPECIFICATION](../brand/GLYPH_SPECIFICATION.md) — the canonical
  list and geometry.

- `apps/runtime-dashboard/src/shared/brand/glyph-vocabulary.ts` — the
  code-level mapping from domain term to radical.

- `apps/runtime-dashboard/public/atlas/glyphs/*.svg` — the ten
  SVG assets, one per radical.

## Consequences

- New domain concepts must either (a) reuse an existing radical with a
  stroke-style or diacritic modifier, (b) rely on prose and a
  ProvenanceStrip entry, or (c) go through the retire-and-replace
  ADR flow.

- The alphabet stays learnable. A new analyst can be trained on the ten
  in under an hour; a sixty-glyph alphabet is a second font.

- The product team may feel occasional friction when a domain request
  wants a unique mark; the ADR trail makes that friction productive.

- Marketing and documentation can reproduce the complete alphabet on a
  single page — this becomes part of the brand surface.

## Concrete impact

Files created or maintained by this ADR:

- Maintained: `policy-engine/docs/brand/GLYPH_SPECIFICATION.md` (the
  ten radicals).

- Maintained: `apps/runtime-dashboard/src/shared/brand/glyph-vocabulary.ts`.
- Maintained: the ten SVG files under
  `apps/runtime-dashboard/public/atlas/glyphs/`.

- New test: `apps/runtime-dashboard/src/shared/brand/glyph-vocabulary.test.ts`
  (parses the specification markdown, enumerates radicals, asserts
  parity with the vocabulary map).

- New lint rule: `eslint-plugin-local/rules/no-raw-emoji-in-jsx.js`
  (blocks Unicode radical characters from appearing as literals in
  JSX, forcing use of `<Glyph />`).

## Related Decisions

- Related: [ADR-042](ADR-042-janus-atlas-dual-brand.md) — the brand
  marks are not radicals and do not count against the limit.

- Related: [ADR-046](ADR-046-authored-text-registry.md) — the textual
  counterpart of visual scarcity: authored text has a bounded set of
  author kinds.
