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



## R9 fixture correction — phase-3 current-head replay at edb2e04e (2026-10-01)

**Discrepancies first.** The first phase-3 driver invocation is a separate UNRUN, not a product red: it failed during harness revision-map admission before the first test-job call, created no JUnit, and started no test body. Receipt: /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/attempt-1-unrun.json@sha256:168b9767fc83c92d600fd278b1445179842ea1b9749425aacf295748faf56888. The corrected runner then executed five whole files at the single current integration head edb2e04e855f6d4e6ee43de058c6f8ee29139340. JUnit contains 128 cases: 119 passed, two failed, seven errored; aggregate exit 1. The nine nonpassing outcomes have two observed roots: one public-export failure plus seven setup errors share claim_root_issuance_content_mismatch; one design-axes failure raises p20_normative_generation_history_invalid. Ownership of these current-head reds is UNRESOLVED pending the required four-base replay. Do not label them inherited or a new defect from this single-head run.

The earlier phase-1 result remains its separate historical cut above (43 cases, 42 pass, one fail); phase-3 does not replace it. This phase is not the four-base P41 matrix and does not cover the full original 58-file R9 cohort. The runner records the fixed cohort as 58, expanded roster as 60, five selected files and 55 expanded-roster files not selected. Of the six changed test consumer files in the fixture candidate, five were exercised; test_normative_generation_bridge.py remains outside this five-file replay. The complete current roster reconciliation and broader matrix remain UNRUN.

The test-only candidate was integrated from 8be1479cc99d8099324978040e70933e61cff8fb as edb2e04e855f6d4e6ee43de058c6f8ee29139340. The integration readback confirms branch codex/e02-r2, exact head, and all seven frozen candidate paths matching committed hashes (7/7): /Users/deniskopylov/.codex/scratch/E02R2_R9_FIXTURE_EDB2E04_READBACK_20261001.json@sha256:8bb15bae1cd4b819502149b67e00287c88608b1d74184fb5da0f4eaf116c22ea. That readback preceded broker admission; this supplement records the later phase-3 result separately.

V3 static review is GO for this exact seven-path test/helper candidate, not runtime evidence: /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_FIXTURE_CORRUPTION_V3_STATIC_DELTA_REVIEW_20261001.md@sha256:755c864fae1ceb38613a3d2d87e005f2323fa0b600942df9c5e66cac850dcbf3. The candidate patch is /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_FIXTURE_CORRUPTION_CANDIDATE_FREEZE_V3/candidate.patch@sha256:de3681a72b147f6ae614ff5e28f8e0a3cdfb28a4d5ae7113ea44565c26735ffd. The shared test helper performs out-of-band signature-sidecar corruption only after an authorized fixture publication; production FileSystemCAS.put_signature remains immutable. Across six test files the candidate covers eight corruption cases and one unsigned-hint-preserving control. The control changes unsigned signer hints before the first authorized publication and verifies that signed statement/signature bytes remain unchanged.

The exact seven-path write set is: policy-engine/tests/_helpers/artifacts.py; policy-engine/tests/unit/runtime/http/test_normative_generation_bridge.py; policy-engine/tests/unit/runtime/http/test_public_decision_verification.py; policy-engine/tests/unit/runtime/http/test_public_decision_verification_routes.py; policy-engine/tests/unit/runtime/http/test_public_export.py; policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py; and policy-engine/tests/unit/scientist/governance/continuous/test_published_signature_custody.py. The current phase-3 wave exercised five of the six test consumer files; test_normative_generation_bridge.py remains outside this replay. The static AST census covers all 2,748 tracked test Python files with zero parse errors, but is not a whole-file runtime denominator: /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_FIXTURE_CORRUPTION_CANDIDATE_FREEZE_V3/put_signature_ast_census.json@sha256:90a936f9cc8a09e438e55745f6e309003d2f1c7d6fe63e72c64ce1f3c5f368c1.

### Five whole-file outcomes

| Whole-file test | Outcome | JUnit receipt path@sha256 |
|---|---:|---|
| policy-engine/tests/unit/runtime/http/test_public_decision_verification_routes.py | 7/7 passed | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_public_decision_verification_routes-0cd5134f62d8.junit.xml@sha256:10d6f57c6c8e2fee269efa78d987d5b007fe784de4121205b42b9488f2ecc46a |
| policy-engine/tests/unit/runtime/http/test_public_decision_verification.py | 55/55 passed | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_public_decision_verification-4a2891dc49d1.junit.xml@sha256:04a414b90839ce0c8e0d50b641ac0945d0846b87d121a69ae8328bdfad4826b8 |
| policy-engine/tests/unit/runtime/http/test_public_export.py | 1 failed, 7 setup errors | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_public_export-a8fab95a64ac.junit.xml@sha256:9b0b516128f6d4e0f910ef48f6f6135743c01207b3c51dbb09c97e212fde5794 |
| policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py | 48/49 passed, 1 failed | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_design_axes_value_choice_provenance-ab5609c83219.junit.xml@sha256:aa0d719164b57a14f3b870c9e358173ea95d914bbee8a1026df9b16eeb3c6217 |
| policy-engine/tests/unit/scientist/governance/continuous/test_published_signature_custody.py | 9/9 passed | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_published_signature_custody-3497ddca7ee4.junit.xml@sha256:87761fdf773ec032b3af1cc80d66c57ff861bd0f36a19ee6ca9d2c754e15aaaa |

The public-export failure is test_http_publication_relocates_selected_manifest_profiles; its assertion receives the same typed ClaimLedgerIssuanceNonReceipt code as the seven fixture-setup errors. The seven errors fail before their test bodies at the shared claim-ledger initialization. The design-axes failure is test_generation_source_reader_replays_historical_schema_by_its_manifest, which raises P20NormativeChoiceError: p20_normative_generation_history_invalid. These are observed outcomes, not causal attribution. Coverage reconciliation also rules out a pass-to-fail claim here: the two failing identities, test_http_publication_relocates_selected_manifest_profiles and test_generation_source_reader_replays_historical_schema_by_its_manifest, are absent at all old refs. The seven setup-error identities below belong to test_public_export.py, which is missing at the Execution and E02 bases; they have no passing outcome at those refs. Independent review records this exact boundary: /Users/deniskopylov/.codex/scratch/e02-r9-fixture-doc-delta-edb2-phase3-20261001-v2/INDEPENDENT_REVIEW_20261001.md@sha256:887c88afa5fdf8fd8594e2e3828bb5de9bae9e0cfc2cd6cc72344a4f2600bf72.

The seven main-only setup-error identities in test_public_export.py, all lacking an Execution/E02 file outcome, are:

- tests.unit.runtime.http.test_public_export::test_public_decision_projection_is_custody_bound
- tests.unit.runtime.http.test_public_export::test_first_governed_public_signature_is_custody_bound
- tests.unit.runtime.http.test_public_export::test_governed_http_rejects_foreign_tenant_body_and_unappointed_source
- tests.unit.runtime.http.test_public_export::test_governed_http_rejects_a_candidate_ledger_source
- tests.unit.runtime.http.test_public_export::test_governed_http_corruption_removes_public_content_and_custody_membership[signature]
- tests.unit.runtime.http.test_public_export::test_governed_http_corruption_removes_public_content_and_custody_membership[source]
- tests.unit.runtime.http.test_public_export::test_governed_http_rejects_invalid_mandate_signature_before_issuance

They are not pass-to-fail evidence at those bases. The two failing identities identified above were added after all old refs. This run therefore establishes no claim that all nine current-head nonpassing outcomes are regressions. Reviewer reconciliation: /Users/deniskopylov/.codex/scratch/e02-r9-fixture-doc-delta-edb2-phase3-20261001-v2/INDEPENDENT_REVIEW_20261001.md@sha256:887c88afa5fdf8fd8594e2e3828bb5de9bae9e0cfc2cd6cc72344a4f2600bf72.


### Frozen inputs, origin, and postflight

The corrected run preflight is PASS at the exact branch/head, with 73 declared current-source inputs and no source-input drift: /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/preflight.json@sha256:2a83c821979f675c5ba950c1ae5ee3966e4eb65b87d23cae6ebc5d073e0c3d69. The source-input manifest is /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-source-inputs.json@sha256:1f63c1dcbc2d275647e4daa7b8ab2715e6605e7ca4b5e4ac51a2131492a5fb4e.

The origin freeze contains 2,764 frozen input paths, including the complete 2,748 tracked test-Python support denominator; its receipt is /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/origin_freeze.json@sha256:49e0819faa90170f57efb1bf036a4375109023452d1495246da4820ce5bc0e08. All five per-file origin receipts pass. Each reports zero foreign origins and zero changed frozen inputs; exact per-file module/support denominators are below.
| Test file | Origin verdict and denominators | Origin receipt SHA-256 |
|---|---|---|
| policy-engine/tests/unit/runtime/http/test_public_decision_verification_routes.py | PASS; loaded modules 1,666; support modules 12; collected test modules 1; frozen inputs 2,764; foreign/changed 0/0 | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_public_decision_verification_routes-0cd5134f62d8.junit.origin.json@sha256:4928e853e54584a4bb3d993314edd39d62ad81e0f8f710332b55901531e91268 |
| policy-engine/tests/unit/runtime/http/test_public_decision_verification.py | PASS; loaded modules 1,641; support modules 11; collected test modules 1; frozen inputs 2,764; foreign/changed 0/0 | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_public_decision_verification-4a2891dc49d1.junit.origin.json@sha256:adeafe45c7afddac0a32be8adcd80779beba863035ad7001f133a8706c3d773c |
| policy-engine/tests/unit/runtime/http/test_public_export.py | PASS; loaded modules 1,644; support modules 13; collected test modules 1; frozen inputs 2,764; foreign/changed 0/0 | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_public_export-a8fab95a64ac.junit.origin.json@sha256:40dabe92a7877c5c8e9a4b6b507ec3e11a09b277491683f820debc7fbd79919f |
| policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py | PASS; loaded modules 1,427; support modules 8; collected test modules 1; frozen inputs 2,764; foreign/changed 0/0 | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_design_axes_value_choice_provenance-ab5609c83219.junit.origin.json@sha256:120715e4b294f690b27e7a6381393f6134e1dc59ccf06b2ac559564268b3d2da |
| policy-engine/tests/unit/scientist/governance/continuous/test_published_signature_custody.py | PASS; loaded modules 1,055; support modules 9; collected test modules 1; frozen inputs 2,764; foreign/changed 0/0 | /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/cells/integration_head/test_published_signature_custody-3497ddca7ee4.junit.origin.json@sha256:9326ae7a63c5ebc81ce333b9ea75fbd74c44ab2da182edbb66f2811f6f05e460 |

Postflight is valid on branch codex/e02-r2 at the same head with empty current-source and complete-support drift lists. The deciding aggregate record is /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/results.json@sha256:2338b8ceaddfefd51df629e18756cb5afb06a7ce9ac5e209200b9d0d319afb63.

Resource postflight for the five sequential groups records a maximum of one active group, peak RSS 944,032 KiB, peak CPU 102.4%, minimum free system memory 43%, minimum free disk 11,347,992,576 bytes, and zero swap growth. This bounded wave remained above the 8 GiB disk floor and 30% free-memory guard. These measurements describe this five-file wave only.

The candidate remains a test-only correction: the helper models out-of-band sidecar corruption after authorized fixture publication and leaves production signature immutability unchanged. Static V3 review was GO for the exact seven-path candidate, but it is separate from this runtime result: /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_FIXTURE_CORRUPTION_V3_STATIC_DELTA_REVIEW_20261001.md@sha256:755c864fae1ceb38613a3d2d87e005f2323fa0b600942df9c5e66cac850dcbf3. Its complete tracked test-Python AST census is 2,748 files with zero parse errors; it is not the R9 whole-file denominator. Candidate patch: /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_FIXTURE_CORRUPTION_CANDIDATE_FREEZE_V3/candidate.patch@sha256:de3681a72b147f6ae614ff5e28f8e0a3cdfb28a4d5ae7113ea44565c26735ffd.

R9 remains partial. The selected current-head wave establishes neither a four-base ownership result nor full original-cohort coverage, and does not change ledger counts or publication authority.


The seven main-only setup-error identities, none comparable as pass-to-fail at Execution/E02, are: tests.unit.runtime.http.test_public_export::test_public_decision_projection_is_custody_bound; tests.unit.runtime.http.test_public_export::test_first_governed_public_signature_is_custody_bound; tests.unit.runtime.http.test_public_export::test_governed_http_rejects_foreign_tenant_body_and_unappointed_source; tests.unit.runtime.http.test_public_export::test_governed_http_rejects_a_candidate_ledger_source; tests.unit.runtime.http.test_public_export::test_governed_http_corruption_removes_public_content_and_custody_membership[signature]; tests.unit.runtime.http.test_public_export::test_governed_http_corruption_removes_public_content_and_custody_membership[source]; tests.unit.runtime.http.test_public_export::test_governed_http_rejects_invalid_mandate_signature_before_issuance. The two added failing identities above also have no old-ref outcome. This phase identifies nine current-head nonpassing outcomes; it does not establish that all nine are regressions.


## Bounded TypeScript workspace gate at edb2e04e (2026-10-01)

**Result: PASS, scoped to the recursive workspace typecheck.** From policy-engine, corepack pnpm -r --workspace-concurrency=1 --if-present run typecheck returned exit 0 in 18.558 seconds. The raw output says “Scope: 5 of 6 workspace projects” and shows all five package scripts passing; the recursive command excludes the root project. The dashboard script ran app, node, and tools configs; the receipt reports seven effective configs parsed with zero config diagnostics. All script invocations used --noEmit. This gate does not establish runtime behavior, Python tests, builds, lint, browser checks, or R9 closure.

The run set COREPACK_ENABLE_NETWORK=0 and invoked no install command. It reused the existing workspace dependencies: the pre/post snapshots record the same 152 node_modules symlink targets. The pre/post frozen set is unchanged at 1,342 tracked inputs / 11,954,525 bytes, same branch/head, clean status, and zero input or link mismatches. No .tsbuildinfo existed before or after.

Resource figures are sampled values, not continuous guarantees: pre-run was 46% free memory and 11,332,673,536 bytes free disk; the three in-run samples recorded lowest free memory 46% and lowest free disk 11,331,358,720 bytes; post-run was 47% free memory and 11,335,602,176 bytes free disk. Process-tree RSS sampling ran 35 times at 0.5-second intervals and recorded a peak sampled aggregate of 1,893,536 KiB (not an OS high-water mark). Wall time was 18.558 seconds. Receipts: /Users/deniskopylov/.codex/scratch/e02r2-tscheck-edb2-20261001/TS_TYPECHECK_RECEIPT.md@sha256:2d1a6cebdd7da426544f9ab1617088c7751d2fd1357464d30b5f3e787dadcf09; raw run/resource measurements /Users/deniskopylov/.codex/scratch/e02r2-tscheck-edb2-20261001/typecheck.run.json@sha256:071aaffe208032657fb0ba8a57a2a3949c91b7f20c30f6a6dfcedec7f3fae40f; command output /Users/deniskopylov/.codex/scratch/e02r2-tscheck-edb2-20261001/typecheck.raw.log@sha256:4b23b3445880d957e05cfb3ced3ffd337d9a8ab89377ee3b38817b6aa3323d07; input freezes before /Users/deniskopylov/.codex/scratch/e02r2-tscheck-edb2-20261001/input_freeze_pre.json@sha256:2855341b940528950425a7d620cf04ab8ddb34000ef71990b33cfa4e225577ce and after /Users/deniskopylov/.codex/scratch/e02r2-tscheck-edb2-20261001/input_freeze_post.json@sha256:db44eba8b0f9815c6c111ce57b1360837232682a92891ea605e11db8065a7259.

This independent gate passes TypeScript workspace checking at the same clean edb2 head. It does not resolve the single-head pytest attribution above or replace the required four-base P41 replay.


## R9 P41 two-file HOME-preserving four-base replay (2026-10-01)

**Discrepancies first.** This matrix covers two files across four refs: 8 requested cells, 6 whole-file executions, and 2 structural `MISSING/UNRUN` cells because `test_public_export.py` is absent from the exact E02 execution and E02-head trees. This is not the original 58-file R9 cohort or a full 434-module runtime closure. The earlier phase-3 five-file run used an isolated HOME and remains a separate historical cut; this matrix preserved the caller's HOME.

| Whole file | E02 execution `78187878e` | E02 head `00d946c2b` | Main `5fd3ebcc1` | Integration `edb2e04e855f` |
|---|---:|---:|---:|---:|
| `policy-engine/tests/unit/runtime/http/test_public_export.py` | MISSING / UNRUN | MISSING / UNRUN | 7 passed | 7 setup errors, 1 failed |
| `policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py` | 48 passed | 33 passed, 15 failed | 48 passed | 48 passed, 1 failed |

All six JUnit files were parsed by full case identity and reconciled with the aggregate row identities and outcomes. The 15 `design_axes` identities that pass at E02 execution, fail at E02 head, and pass at main all pass again at integration (15/15 restored; none remain from that set). This outcome supports an E02 pass-to-fail regression classification for those cases; the proposed R10 causal link is not established by this matrix. Seven `public_export` identities pass at main and become shared-setup errors on integration, each with `claim_root_issuance_content_mismatch` before the test body.

The two integration-only failing identities are `tests.unit.runtime.http.test_public_export::test_http_publication_relocates_selected_manifest_profiles` and `tests.unit.runtime.quality.test_design_axes_value_choice_provenance::test_generation_source_reader_replays_historical_schema_by_its_manifest` (the latter reports `p20_normative_generation_history_invalid`). They are absent at the older refs and are not pass-to-fail evidence. The exact identity sets, all six complete JUnit path/hash/outcome entries, and cell presence are in the deciding aggregate /Users/deniskopylov/.codex/scratch/E02R2_R9_P41_TWO_FILE_HOME_REPLAY_20261001/runs/r9-p41-home-20261001T012910Z-69253/results.json@sha256:a365dfaf1603445ecc10dac6c6c20763d9efd9eedc89bbc85b9a53d3912bd96a and independent identity reconciliation /Users/deniskopylov/.codex/scratch/E02R2_R9_P41_ROOT_RECONCILIATION_20261001.json@sha256:4dba2e62fcba49b3849e96b18511cd7201204fd4681b85c9ebeaa2f84320eca3; do not infer causal ownership for the current-only failures from their outcome alone.

P41 admission states HOME was preserved without serializing its value; all six executed cells verify HOME preservation. All six origin receipts are hash-valid PASS with empty foreign-origin and changed-frozen-input sets. The four pinned checkouts were clean and matched their expected heads at freeze; the integration postflight is valid at the same branch/head. Receipts: preflight /Users/deniskopylov/.codex/scratch/E02R2_R9_P41_TWO_FILE_HOME_REPLAY_20261001/runs/r9-p41-home-20261001T012910Z-69253/preflight.json@sha256:fe75704c335225a7cf4a8d4096156eb102f5d8f3f8f6a6d938d8ed768306ff7b; four-ref freeze index /Users/deniskopylov/.codex/scratch/E02R2_R9_P41_BASE_FREEZES_20261001/index.json@sha256:11301f58c3d803a59edbb1c9bb7f56c0d344bd924c9143e4bcd0fd53596f43bb; aggregate /Users/deniskopylov/.codex/scratch/E02R2_R9_P41_TWO_FILE_HOME_REPLAY_20261001/runs/r9-p41-home-20261001T012910Z-69253/results.json@sha256:a365dfaf1603445ecc10dac6c6c20763d9efd9eedc89bbc85b9a53d3912bd96a. The earlier isolated-HOME phase-3 aggregate remains /Users/deniskopylov/.codex/scratch/e02-r9-transaction-prep-894631fca-20260930/R9_CURRENT_INTEGRATED_PHASE3_20261001/r9-p3-20261001T005803Z-61653/results.json@sha256:2338b8ceaddfefd51df629e18756cb5afb06a7ce9ac5e209200b9d0d319afb63. This six-cell wave sampled a minimum 44% free memory and 11,257,528,320 bytes free disk, with zero swap growth; those measurements describe only this run.

This bounded two-file replay does not complete R9's full consumer cohort, resolve the current-only failures, or change ledger status.
