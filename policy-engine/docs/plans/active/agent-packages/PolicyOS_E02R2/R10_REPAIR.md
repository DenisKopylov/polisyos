# R10 — string artifact IDs at the signature boundary

**Property.** The public CAS signature verifier accepts a canonical artifact ID as
either `ArtifactID` or `str`. It normalizes a valid string before snapshot and
signature reads. Malformed strings return a typed `ERROR` without reading CAS.
All later integrity, signer, revocation, and identity checks remain the existing
verifier's responsibility.

**Change.** `FileSystemCAS.verify_signature` now parses `str` with the canonical
`ArtifactID` model and delegates with the typed value. The malformed-ID result
preserves the supplied string. The full source/test diff was reviewed before
integration in the independent scratch review
`/Users/deniskopylov/.codex/scratch/e02-r2-r10-independent-patch-review-20260925.md@sha256:51e9c4d2d2994269665584adde499297073ab7345cfcd7defe28a536f6f83938`.

**Behavioral receipts.** All JUnit artifacts below were written outside the
production-data tree. They use the integration checkout, the canonical
`production_data` symlink, Python 3.14, and the same explicit pytest flags.

| Check | Complete JUnit outcome | Receipt |
|---|---:|---|
| Test-first string witness, before source change | 1 failed / 1 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/red.junit.xml@sha256:a45b2a3b03670130c2f1d3166b049b790102917b12011f2e07355ac4919b8d25` |
| Entire touched CAS-signing file, after repair | 17 passed / 17 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/green.junit.xml@sha256:9d2fcbcddeb7c86e2a03c0d49fa0f3f99d1d33dfdc98336ab291fb341c56a5a5` |
| Remove normalization, keep annotation and result markers | 1 failed / 1 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/mutant.junit.xml@sha256:b6ded952313650e49dae77283989ee6273d260c7fa1639fb4064d6f11e0c0139` |
| Restore normalization | 1 passed / 1 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/restored.junit.xml@sha256:f61ee5eae2bfab3a8fea3b98775a86997c1d0fa1071ac93367cbde726f1fd333` |
| Four named Appendix-B string-ID consumers | 4 passed / 4 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/consumers.junit.xml@sha256:3f31b2a0ad1ffc32229dfcf38bb840237866e53f465962ab41bcc7eafefbdbfd` |
| Entire design-axis value-choice consumer file | 48 passed / 48 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/design-axes.junit.xml@sha256:5f166b2c6777f869338231226a1fdad5f302a09083410aca64c88f70c7c989fb` |
| Two whole human-decision consumer files | 79 passed / 79 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/human.junit.xml@sha256:904559c389dd6a13235099978035730eef9e15540d2c5c8c526ab291aa8ef5c2` |
| Promotion-safety and acquisition-admission files | 20 passed / 20 | `/Users/deniskopylov/.codex/scratch/e02-r2-r10-tdd-20260925/quality.junit.xml@sha256:71b5003be3716b91c017344c4e96362d6a2fede102e8dbcfe7afc64d9e7182ab` |

`ruff check` on the two changed Python files and `git diff --check` exited 0.
The 48-case design-axis file had 15 failing cases at the pre-repair E02 and
Phase-0 heads, while both earlier bases passed; see the complete four-base
receipt in `BASELINES.md`. This repair now passes the entire file on the current
head. The historical old-head two-cell normative bridge remains `UNRUN` after the
principal-directed SIGINT; R10 does not claim to resolve R1/R2 or that baseline.

**P37/P38.** The public-boundary predicate is recomputed by the canonical
`ArtifactID` parser, then the existing snapshot/signature verifier. It is not a
caller assertion. Previously the method annotation accepted only the typed form
while production passed raw strings: the marker (`sha256:` ID) looked correct,
but the snapshot loader needed `.hex`. The removal probe shows that simply
retaining the widened annotation and status strings does not preserve behavior.

**Remainder.** This does not change CAS manifest-profile conflicts (R9), source
currentness (R2), or the guarded-store bypass noted under R13. The full touched
file P41 comparison and final repository gates remain closeout work.

## R10 candidate whole-file boundary result (2026-10-01)

Candidate `codex/e02-r2-r9-publication@fdac2ae1209e6a80a72f8ab90aa974916624c229` passes three complete files, 47/47. The bounded property is public identity normalization before the existing signature transaction lease: malformed identities return typed `ERROR` without CAS reads; valid strings reach the leased verifier as `ArtifactID`. The no-scope malformed controls and selected-view control pass. This is candidate evidence only; the current marker-retaining removal probe remains pending, integration replay is unrun, four-base P41 is unrun, and R10 remains `partial`. See [the indexed baseline result](BASELINES.md#r10-candidate-whole-file-boundary-result-2026-10-01).

The consulted [architecture recommendation reference](ARCHITECTURE_REFERENCE.md) presents E02-ARCH-02/05 as proposals about preserving selected-view identity and binding signature reads to the admitted store. They are not adopted contracts. This local `FileSystemCAS` candidate does not establish a broader backend, tenant, or authority capability.

## Current integrated replay at `b4d771b` (2026-10-01)

**Current result.** Root’s exact-head readback reports all three complete R10 files passing, 47/47; see [the deciding receipt](R10_TRANSACTIONAL_BOUNDARY_RECEIPT.md#fresh-integrated-replay-at-b4d771b-2026-10-01) and its indexed outputs. This verifies the integrated whole-file cohort only.

**Supersession and residual.** The earlier “fresh integrated replay remains UNRUN” and candidate “removal probe pending” wording above is historical. The candidate `fdac2ae` marker-retaining removal probe completed with five malformed-input failures and one valid-string control pass; it was not rerun at `b4d771b`. Integrated removal, full four-base P41, broader guarded/served consumers, other backends, and authority closure remain open; R10 stays `partial`.

**Historical scope.** The earlier 48-case design-axis pass is a separate historical result; its cited JUnit does not establish the execution head, and the `b4d771b` 47-case replay does not include that file. The caller census of 5,444 tracked source/test Python files and 50 call sites is pinned at `62ad51e3b48e644c37fe28e17c1d1e30be3e7560`, not a current whole-tree census. Neither claim is promoted by this replay.
