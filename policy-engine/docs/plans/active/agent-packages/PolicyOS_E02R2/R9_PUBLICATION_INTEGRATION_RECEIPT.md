# R9 publication integration checkpoint (2026-10-01)

## Discrepancies and verdict

The R9 publication mechanism is integrated; its post-integration runtime verdict
is **UNRUN**. Candidate evidence is bounded to 37 cases: two complete Python
files and one served-route selector. The full 58-file Python denominator,
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
