# R9 publication integration checkpoint (2026-10-01)

## Discrepancies and verdict

The R9 publication mechanism is integrated. Its first post-integration replay at
`9d99499fa093292ec06889747019708d118a9d3b` is **FAIL**: 42 pass and one fail
among 43 cases across three whole Python files. The failure is in signature
corruption setup before the verifier assertion. Candidate evidence remains
separately bounded to 37 cases: two complete Python files and one served-route
selector. Of the fixed 58-file Python denominator, 55 whole files remain UNRUN;
browser, workspace TypeScript checks and four-base attribution remain open.
The principal's temporary refusal applies to V2 production approvals; historical
signature reads and ordinary candidate work retain their separate semantics.

## Property and implementation

Reads of an affected publication surface must refuse while its owner operation
is pending, even when old owner claims and newly published bytes look complete.
The existing ownership owner requires the same durable intent to be committed
and independently recomputes exact member digests and expected claims from one
validated owner-index generation. A matching authorized retry under the common
artifact lease finishes the pinned operation. A read does not complete it.

The predicate is `recomputed` within the local filesystem owner. P38 limitation:
durability and lease correctness assume owner-controlled filesystem access;
this implementation does not establish cloud IAM, a deployed cross-host lease,
or a new institutional approval authority. A signature-only pending intent
denies that selector while preserving the committed blob/manifest and unrelated
candidate work. One digest representation is shared by producer and retry.

## Branch and evidence pins

- Candidate commits `1bb48af5df373b4263c29d705f178c06f310ddc6` and
  `70905e41f20f1b6e75445396bd202dcb611e9d8a` were integrated as
  `f34f17c137a1450105aa9068a29dff261c98a8d0` and
  `8298a843f2091f5c4416f9663816e7796081a740` on `codex/e02-r2`.
- Root read back all 73 candidate frozen inputs from that branch and disk:
  zero byte mismatches across the complete denominator; 57 changed paths.
  Receipt `/Users/deniskopylov/.codex/scratch/E02R2_R9_INTEGRATED_READBACK_8298_20261001.json@sha256:02bbcc9c76090786fa762f52d8e7b09f419d8ac31f37b54b596d57dbeb99f05d`.
- Candidate V9 JUnit: 37 pass, zero failures/errors/skips, exit 0; wall time
  28.16 seconds, peak RSS 1,047,576,576 bytes and zero swaps. Result
  `/Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_V9_COHORT_RESULT_20261001.md@sha256:df982bbea26a810ab69b827e7b12b4ed256ac710db215021b9ee4226c770cfe8`.
- Independent runtime-evidence review:
  `/Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_V9_RUNTIME_EVIDENCE_RECONCILIATION_20261001.md@sha256:252ed589c96cb48e30a54a4fac2cefc8cb48f2d50815623b29952bfc17f12e79`.

The served selector is
`tests.unit.runtime.http.test_public_decision_verification_routes::test_served_verifier_denies_signature_intent_and_counterfactual_tracks_gate`.
It observes invalid/unavailable evidence under the pending intent; removing only
the gate while keeping record markers exposes a verified public document.
Exact retry restores legitimate verification. The preserving control is
`tests.unit.core.artifacts.test_multi_tenant_shared_cas::test_signature_only_pending_publication_is_denied_and_exact_retry_recovers`.
The child-process witness
`tests.unit.core.artifacts.test_multi_tenant_shared_cas::test_second_process_reader_waits_on_the_canonical_root_stripe`
checks its own module origin explicitly.

Candidate origin drift was zero, but one helper alias was misclassified as a
foreign product module and its in-run content hash was not captured. The review
records that limitation; current helper bytes cannot retroactively prove it.
No finding status, register closure, receipt reissue or restamp follows from this
checkpoint. The next whole-file wave must capture current support-file hashes.

## First integrated replay — 2026-10-01

The whole files are `tests/unit/core/artifacts/test_multi_tenant_shared_cas.py`,
`tests/unit/runtime/quality/test_non_data_acquisition.py` and
`tests/unit/runtime/http/test_public_decision_verification_routes.py`. JUnit
enumerates 43 cases: 42 pass, one fail, zero errors or skips; the command exits 1
in 40.181 seconds. The sole red is
`tests.unit.runtime.http.test_public_decision_verification_routes::test_owned_run_packet_is_redacted_issued_and_publicly_verified`:
its deliberate signature overwrite calls immutable `put_signature` and raises
`ArtifactIntegrityError: immutable signature sidecar conflicts`. The verifier's
intended invalid-signature check is not reached. This is not a measured
four-base regression attribution, and changing the fault-injection mechanism
does not justify weakening that check or production signature immutability.

The origin inspection passes over 1,666 loaded product modules, 15 loaded test
support modules and three collected test modules. All 2,764 frozen inputs are
unchanged, with zero foreign origins; postflight branch, HEAD and tree match the
execution cut. Peak RSS is 1,030,352 KiB, peak CPU 102.6%, minimum free RAM 50%,
minimum disk 9,179,922,432 bytes, and swap growth zero. This proves this bounded
run's resource compliance, not a budget for every remaining suite.

Raw evidence is retained outside the test temporary directories:

- `/Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE1_20261001/r9-current-p1-20260930T233229Z-45671/phase1.junit.xml@sha256:46107f6de9f3e0163ab979782d2dee84d36fc438c373d282ae1e54f3e2d3b869`.
- `/Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE1_20261001/r9-current-p1-20260930T233229Z-45671/phase1.log@sha256:b658b1c8fe571c4ff0d16708594ca9fba3bcd6e91f9469ab6110d627d4e72a5a`.
- `/Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE1_20261001/r9-current-p1-20260930T233229Z-45671/phase1.origin.json@sha256:87533203d8854f7c90569426b204704cf335394de093a8388ea7ae5c4ef44f1c`.
- `/Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE1_20261001/r9-current-p1-20260930T233229Z-45671/results.json@sha256:8ebfba9445d2dd97a73188ad9ab4c687fb9e23eea617099d7917f94fefa72031`.

The next two whole-file jobs were prepared but not started when disk headroom
fell close to the 8 GiB floor. Their verdict is UNRUN, not a product failure.
The three-consumer fixture repair is separately leased in `WRITE_LEASES.md`;
its behavioral replay and independent review remain due. No finding closes here.
