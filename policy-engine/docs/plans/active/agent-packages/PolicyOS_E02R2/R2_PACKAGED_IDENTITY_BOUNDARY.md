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
identity. Source:
`src/polisyos/runtime/quality/confidence_ledger.py@sha256:63b3c9bbde5faf530da1466a563e76833c6d29682612d86ea008e8a08c3d7e4d`.

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
