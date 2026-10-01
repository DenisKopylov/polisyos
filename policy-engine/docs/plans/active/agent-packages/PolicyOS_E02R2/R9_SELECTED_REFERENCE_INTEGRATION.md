# R9 — selected-reference propagation integration

## Discrepancies and scope

Commit `1a55580ffa39a86ae511e548787e3af3c0b7ab48` integrates the reviewed selected-reference family on `codex/e02-r2`. It is a code delivery, not a current-head runtime PASS or anonymous-release closure. The corrected head-index runner stopped before pytest; its whole-file result remains UNRUN pending the existing four-base harness.

The property is that a typed reader resolves the exact selected manifest view, rather than treating blob equality as permission to read another view. Eleven existing production reader modules now carry the complete `ArtifactRef` through the existing CAS boundary. No hashed model, CAS owner, signature normalization, or V2 production-approval posture changes in this commit. The 22-path source/test denominator was walked completely and all branch bytes read back against the integration manifest.

## Evidence and predicate

- Exact integration packet: `/Users/deniskopylov/.codex/scratch/E02R2-R9-selected-ref-integration-20261001/integration_manifest.json@sha256:e710a4f89f019caaa9de01c0710cc60542b3920f33b39d9c590848dab5a6dd8e`; patch `r9_selected_ref_family_to_242a6e7.patch@sha256:8e271391226ca0168cc5bd6edee8f2d34caf1ae419ede116ae23f62cdaeb58a2` in that directory.
- Independent integration review: `INDEPENDENT_INTEGRATION_REVIEW.md@sha256:ea330a7e681e6effa26aa66b556b78b281730e2231ddf7483336107a5e113b94` in the same directory. AST, Ruff, and diff checks pass for all 22 changed Python paths; root read back 22/22 committed file hashes.
- Earlier candidate `944ffa0` behavioral evidence: 118 executed cases, 112 pass / 6 fail, plus two separate collection-error observations. Those results are not an integrated-head run. Their public-read and import-order failures remain separate from exact-view propagation.
- Marker-retaining removal probe: `/Users/deniskopylov/.codex/scratch/E02R2-R9-selected-ref-removal-probe-plugin-20261001/runs/selected-ref-removal-20261001T094814207737Z-85895/ROOT_READBACK.json@sha256:78532e2e552f95e80987e02e7705210630c3e87177409c233ea8b299b0983fb4`. The exact test is `tests.unit.runtime.http.test_public_export::test_governed_owner_rejects_removed_selected_view_and_keeps_tenant_reads`. Dropping the selector from three owner CAS reads produces the expected pytest failure; the valid selected-ref read precedes it. The later tenant-read assertion is not reached in the mutant. This probe belongs to its earlier candidate, not the integration head.

The selected-view predicate is recomputed by the supplied store's exact manifest resolver; ownership, integrity and pending-write gates remain on the existing read path. P38 boundary: an absent selected view with valid same-blob default bytes must refuse. P40 bucket: this is the existing selected-reference propagation class, widened across the complete claim/lifecycle owner family.

## Residual and next step

Anonymous public-read authority and the custody watcher require their own exact owner-bound read closure. The fresh public-export matrix records main's 7 pass versus integration checkpoint `bc909aed` 3 pass / 5 fail; test-definition changes require semantic attribution. The current selected-reference commit does not discharge that residual or adopt E02-ARCH-37. Production root/trust premises remain in `OPEN_PREMISES.md`; the accepted temporary V2 production-approval refusal stays in force.

Next: replay the corrected head-index file together with the touched CYC-02/CYC-05 files through the existing four-base harness; retain every red/UNRUN and source identity. Then implement the reviewed public-read closure slice under declared trust limitations. No ledger status is upgraded by this receipt.
