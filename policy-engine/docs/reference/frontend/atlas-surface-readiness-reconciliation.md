# Atlas Surface-Readiness Reconciliation

Freshness: 2026-08-16
Owner: `team-frontend`
Producer: `apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.ts`
Canonical launcher: `apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs`

## Scope and authority

C10 is a repository-reconciliation observation. It is not browser, keyboard,
manual assistive-technology, maturity, promotion, publication, runtime, or
stable authority. Its C07 v1.1 receipt is exact for
`atlas_surface_readiness_reconciliation` and denies every other listed use,
including `stable`. C07 v1.0 remains readable.

The only persistence path is C08's existing Core CAS sequence: raw report,
verification payload, then receipt. The raw artifact is the exact UTF-8 Vitest
JSON bytes emitted for `src/app/routes/routes.test.tsx`; reconciliation facts,
the derived route-test receipt, and the result are payload/receipt fields, not
a C10 wrapper substituted for the runner report. Before any C10 CAS write, the
Python adapter strictly decodes those bytes, recomputes their SHA-256 and exact
five-assertion route receipt, hashes the fixed canonical source basis, and
independently recomputes the ledger/runtime reconciliation. C07/C08 then
resolves and content-binds the three persisted artifacts. C10 creates no second
CAS or adapter.

## Reconciliation rule

`atlas.surface-readiness-reconciliation@1.0.0` strictly parses the complete
canonical owner shapes and relevant vocabularies. Unknown `maturity`,
`readiness_state`, or chain state; missing/extra chain members; incomplete
ledger rows; and duplicate adoption/readiness identities fail closed rather
than falling out of a filter.

The owner-schema mirror is limited to its complete ten-field census:

- adoption root `as_of` is date-time; evidence-ref `as_of` and `decided_at` are
  dates; `audiences`, `consuming_surfaces`, and
  `next_adjudication.owner_slices` are unique arrays;
- readiness root `as_of`, `freshness.as_of`, and `updated_at` are date-times;
  `audiences` is a unique array.

This does not claim to mirror unrelated owner constraints, including the
adoption schema's stable `allOf` browser/AT condition.

Every `stable` row fails
`stable_evidence_reference_unresolved`, even with shaped browser/manual refs.
There is no `resolve_evidence` callback or stable-positive admission path in
C10: live stable admission remains `contract_only` until the contended typed,
subject-bound Core evidence consumer exists.

Every non-deprecated `implemented` row receives both
`implemented_negative_test_missing` and `implemented_semantic_test_missing`.
String values in `chain.negative_test` and `chain.semantic_test` are ledger
claims, not typed content-bound test evidence.

The sole deprecated exception is structural. C10 imports runtime `APP_ROUTES`,
requires exact `Navigate` type/props (`replace=true`, string target), and
derives exactly `/launch → /compose`, `/sources → /evidence`,
`/data → /evidence`, `/lex → /knowledge`, and `/health → /platform`. It never
admits source or test-marker text. The launcher itself runs the real route test
with Vitest JSON and `--maxWorkers=2`; a PASS requires process exit `0`, runner
success, one passed route-test result, and five exact passing redirect assertion
identities. A failed, missing, duplicate, or nonzero matrix is
`redirect_test_receipt_invalid`.

For C10 v1.1, TypeScript and Python require the exact evidence kind, subject,
rule/version, authority, producer/verifier identity, fixed command, computed
repository revision, `predicate_provenance=independently_reconciled`, and the
exact field-provenance basis. The six-item source basis is the adoption ledger
and schema, readiness ledger and schema, and `routes.tsx` plus
`routes.test.tsx`; both individual hashes and an ordered source-set hash bind
the current tree. `consumer_asserted`, `institutionally_supplied`, and
`not_established` fail closed. The raw-byte hash, derived route receipt,
canonical reconciliation, payload result, and receipt result must agree before
CAS writes.

## CI, current facts, and nonreceipts

The canonical workflow invokes only the launcher after dashboard/Python setup;
there is no neighboring, unbound route-test receipt. The launcher uses the
fixed `uv run --frozen python` adapter from the policy-engine root and an
isolated CAS. It exposes no controlled evidence, route, bridge, or interpreter
input to public CI. Pure reconciliation returns exit code `1` with named
findings for a negative input; the canonical launcher is receipt-proven only
for the live PASS path, not for a synthetic persisted negative invocation.

The complete canonical-owner census is adoption `233` / stable `0`; readiness
`261` / stable `0` / implemented `5`. The five implementations are exactly the
deprecated redirects above. Ledger line locators drift by two lines; this is a
diagnostic, not evidence. A green C10 receipt only reports this observation; it
does not grant stable admission.

Deferred exactly: no register, report, status, readiness, baseline, or
checker-family byte change. No browser lane, Playwright journey, visual lane,
dev server, external audit surface, or real typed stable evidence was produced.
