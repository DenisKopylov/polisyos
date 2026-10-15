# Compliance evidence routing

Owner: `@platform-owners`
Source of truth: Current external review status is `not_established` by the dated records below; historical assessment records are `policy-engine/docs/compliance/A11Y_AUDIT_2026Q2.md` and `policy-engine/docs/compliance/VPAT.md`; contrast inputs are the dashboard style source and generator named in `policy-engine/docs/compliance/A11Y_CONTRAST.md`.

## Accessibility records

- [Accessibility audit packet](A11Y_AUDIT_2026Q2.md) is the internal pre-audit record dated 2026-04-22 for `@polisyos/runtime-dashboard@0.1.0`. Its DS11 projection index binds the body digest `0e4a0280ab30e1c69cb373d438906aa50d36bd9765ec36e533b6fea1a7df93f0` and limits its authority to the historical internal pre-audit. It cannot establish current conformance or external certification.
- [VPAT](VPAT.md) records the internal assessment dated 2026-04-23 for the same product version and evaluation scope. Its `Supports` entries describe that internal assessment; its external countersign notes are part of that dated record.
- [Contrast matrix](A11Y_CONTRAST.md) is generated from dashboard styles by `policy-engine/tools/design/check-contrast.ts`. It reports token-pair results, including exploratory pairs, and is not a product-wide accessibility assessment. Regenerate it from its source when the tokens change; do not edit the generated page by hand.

## Current external review status

As of 2026-10-14, current external accessibility review or countersign status is `not_established` by these records. The audit's Q2 2026 scheduled/pending fields are historical; they do not show whether the review later completed, was cancelled, or remains pending. Do not use either dated assessment as current external certification. Record any later review in a new dated, source-backed artifact with its product version, scope, reviewer, evidence, outcome, and limits; preserve the original audit body and DS11 bindings.

Source review was limited to repository documents and code at `8dd933600dd7a5a8a5b48432c6089d63b81ca641` on 2026-10-14. No dashboard checks, contrast generator, deployed product, or external auditor evidence were run or observed for this routing note.
