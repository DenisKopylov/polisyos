# Contrast Spec Index

This page is the Wave 1 contrast specification index. The canonical generated
artifact lives in [`../compliance/A11Y_CONTRAST.md`](../compliance/A11Y_CONTRAST.md).

Why two pages exist:

- `docs/compliance/A11Y_CONTRAST.md` is machine-generated from runtime theme
  tokens and is the only source of truth for the published matrix.

- `docs/brand/A11Y_CONTRAST.md` exists as a stable spec/index page for ADRs,
  plans, and generator rules. It must not duplicate or hand-maintain the
  matrix.

## Wave 1 contract

1. The contrast matrix is generated from runtime tokens, not written by hand.
2. Validation happens in `tools/design/check-contrast.ts`.
3. CI must fail if the generated compliance artifact drifts from token values.
4. Release notes and VPAT link to the compliance artifact, not to this page.
5. Dark-theme raw brand accents (`--teal`, `--gold`, `--ember`) are tracked in
   the matrix for observability, but they are not text-safe foreground defaults
   for body or small text.
6. Wave 1 enforcement closes only on the explicit required semantic text pairs;
   the full matrix remains visible so prohibited pairs stay auditable.

## Canonical references

- Generated matrix: [`../compliance/A11Y_CONTRAST.md`](../compliance/A11Y_CONTRAST.md)
- VPAT: [`../compliance/VPAT.md`](../compliance/VPAT.md)
- Motion spec: [`./MOTION.md`](./MOTION.md)
- Design evidence path: `docs/plans/active/DESIGN_BEST_IN_CLASS_PLAN.md`
