# R2 — installed identity leaf boundary

Status: bounded currentness/identity repair; source-free N6 historical replay and
R2 class closure remain open.

The confidence-ledger owner now distinguishes a checkout with canonical lock
and loaded-code inputs from an installed package that has no appointed build
identity issuer. In the latter case `capture_loaded_deployment_identity()`
returns typed `not_established`; `inspect_packaged_deployment_identity()` returns
`UNRUN` with its input inventory and the unresolved issuer/census classes. A
self-attested manifest or present lock file cannot turn that state into an
authority admission. The existing checkout path still captures its loaded
identity. Historical candidate-source pin used for the leaf-overlay receipt:
`src/polisyos/runtime/quality/confidence_ledger.py@sha256:63b3c9bbde5faf530da1466a563e76833c6d29682612d86ea008e8a08c3d7e4d`. This pin is not the current a5141d432 source.

At the a514 read-only checkpoint, the same canonical owner was
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py@sha256:9a8945227abf9638f97740639ba9856e53ae08cf7b11cc7fd4ad064d280c62fd`. The integrated R2 owner at a877 is
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py@sha256:cc09224f8ad20e94fdcd4d7fc26021da3aee0ee4ee44c2798bb97752403be3b2`; it records typed loaded-identity reason codes, but the source-free issuer remains absent: no production build/deploy owner admits a signed exact-package manifest, canonical lock and complete N6 route-census artifact. Keep packaged currentness `UNRUN`; the checkpoint is `/Users/deniskopylov/.codex/scratch/e02-r2-loaded-manifest-owner-design-20260927/R2_IMPLEMENTATION_BLOCKER.md@sha256:3a2900be1f4cab2ed92c780d95f48d5719b129dc35919bc0181eff1bd6636453`. The R2 bounded integration commit `a877f8abc918ff46f6db2a3f0ae64fb4d07fe856` passed the complete history file 26/26. The complete generation-cycle file was 145/149; compared with 154, 148 identities had zero pass→fail, five fail→pass, four fail→fail, and one new passing removal/control case. The four remaining reds at a877 were one N9 issuer and three R13 local re-entry cases; the test-double case passed 1/1 in follow-on commit `782652222`, but no whole-file rerun at 782 is claimed. Receipt `/Users/deniskopylov/.codex/scratch/e02-r2-integrated-154407-20260928/R2_INTEGRATION_RECEIPT.md@sha256:064aac803a3091a2296d67606a0820bbd24e925d33be6b01dd1499b25ce85e29`; history JUnit `/Users/deniskopylov/.codex/scratch/e02-r2-integrated-154407-20260928/history/test.junit.xml@sha256:bf2fac94bb6a40e11f5de981c0972b0ab2b8a7a793c0f48753b0dff7b8b519e7`. Packaged strict currentness, positive N9 and exact four-base replay remain `UNRUN`; R2 remains partial. The earlier 8/8 leaf-overlay receipt remains historical.

The integrated focused run passed 8/8: five new installed-leaf overlay tests
and three existing loaded-identity controls. JUnit:
`/Users/deniskopylov/.codex/scratch/e02-r2-packaged-identity-candidate-20260926/R2_INTEGRATED.junit.xml@sha256:74bb827ec496ca11accd29e6a220e48e7d495255a72be934bcc719b8e8928b9b`.
The new test file is
`tests/unit/runtime/quality/test_confidence_ledger_packaged.py@sha256:86012e8bcf06feba7e954b6c18de80d9dc776e188817f56e49317157aa670693`.
Its marker-retaining guard-removal test makes a mutant return false
`established` currentness and turns red; the restored owner is green. The
property-preserving source-checkout control stays established. Ruff check of
the changed source and new test passed.

This is deliberately a **leaf overlay** witness. The test uses `python -S`,
identifies the installed confidence-ledger module's origin, and explicitly
draws dependencies from the checkout source. It reports every loaded
`polisyos` module origin; it does not claim ordinary installed-package import
or source-free historical replay. Independent reviews:
`/Users/deniskopylov/.codex/scratch/r2-packaged-identity-patch-review-20260926.md@sha256:b89403f7d987ce770c30ce71b74d27c3803c82bd30fdc9bd89a0bfa77ed05a84`;
`/Users/deniskopylov/.codex/scratch/e02-r2-packaged-identity-candidate-20260926/REVIEW-test_confidence_ledger_packaged_v2.md@sha256:1768c3b5c8f8038bb6c64787155d279e04f3a4118cb702986238f67eca876101`.

P37: the checkout loaded-code closure and lock inputs are recomputed by their
existing owner; installed build issuance, deployment admission, and the N6
strangle census are `not_established`/`UNRUN`. P38: the implementation proves
that absent installed identity cannot become current authority at the
confidence-ledger leaf. A normal installed `generation_cycle` import diverges:
its eager dependency graph still reaches a checkout-only snapshot before
historical replay. The exact cold-start experiment is a recorded NO-GO, not a
fix:
`/Users/deniskopylov/.codex/scratch/e02-r2-packaged-identity-candidate-20260926/R2_COLD_START_IMPORT_REVIEW.md@sha256:705124e5a556298129bd9e2a77eb5ce84248692654775f2ba0f6140d74d318ec`.

R2 still needs a dedicated historical consumer that preserves the complete
frozen model graph, a build-issued canonical deployment identity, and a
source/deploy-time N6 strangle census. Currentness must remain a typed epoch
question separate from byte-exact historical validity. The full four-base
replay of touched files and the ordinary source-free consumer witness are
`UNRUN` here. No manifest, receipt, trust-posture pin or epoch was restamped.
