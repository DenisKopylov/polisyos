# A wave-2 evidence admission (read-only)

Reviewed against the immutable receipt bundle `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/A/continuation-20261007-progress.json@1590f35b6817c46af484de818ba227517c5a8d1b` and wave-2 handoffs/checks/source reviews at the same metadata commit. G worktree was `codex/e02-integration` at `9806442ddb47d624a2940bac75d9d6248e934c48` (tree `4a1caafc…`), clean before report; the A code candidates are Git objects but not G ancestors. No tests, installs, refs, or tracked files were changed.

## A denominator and prior evidence

The pinned progress reconciliation gives A **13 bundles, 34 unique findings, 35 original criterion occurrences** (31 B-r19 and 4 LA-r09). LA-046 is two distinct occurrences in REQ-01 and ACQ-01 over one physical source block; retain both. Full set and exact source bindings are in the progress file’s `denominator_and_reconciliation.A_slice.complete_13_bundle_inventory`, and original source pins are `source_pins`. Whole-queue denominator is 127 bundles / 282 findings / 291 source-block occurrences. Historical source states are partial 31, open 1, closed 1, held 1; `source_closure_now=not_adjudicated` for every A row. The carried outcomes (open 4, limited 27, closed 2, held 1) are provisional, not adjudications by these receipts.

A owns ACQ-01 (B12, LA-046); CYC-01 (B01–03); CYC-02 (B04, B05, B08); CYC-03 (B09, B27, B28); CYC-04 (B10–11); CYC-05 (B15, B29–30); EMP-01 (B16, B31, B33); REP-01 (LA-033); REQ-01 (LA-045, LA-046); SEL-01 (B34–36); SIM-01 (B06–07); SIM-02 (B18, B20, B22); SIM-03 (B19, B21, B23, B25–26). These two handoffs carry `closure_ids=[]`; they do not update source status or finding outcome.

Do not reuse old checks as fresh candidate checks. The 418/203/326 aggregates are FAIL at respectively `b379d01f`, `7cdac9c5`, `4c4e37d0` (not the new candidates). The 217/217 affected and 106/106 SIM/CYC receipt is at frozen candidate `6f1e` (`A/numeric-scalar-validation/frozen-owner-delta-6f1e/`); it remains useful historical evidence, but not a check of the changed N8/model-revision source at `069ce`/`01e465`.

## New candidate evidence

**N8 objective intake (`CYC-02`, B04/B05/B08 context):** handoff base `4ca1b0ef…` / tree `946428cd…`; candidate `069ceaa7af2dba02f1cb303a251a03c3095b6bbc` / tree `6d47aefc…`. The full base-to-candidate footprint is 1 source + 4 test files. Source commit `e1b970bb…` changes `runtime/quality/generation_cycle.py`: the value-intake resolver now takes candidate/problem, recomputes candidate/outcome/atom identities and gives them to the persisted N5 CAS reader; `simulation_value_execution_context` and `FoundryValuePort` pass those values. The candidate is a co-resident composition: its source file also contains the initial B09 model-revision commit `69c647bc…`, so the N8 test receipt does not isolate N8 from that source delta.

The exact deciding receipt `wave2/checks.json#n8-objective-candidate-069ce-valid` is **5/5 PASS** (four named selectors; unknown/fatal blocker test is parameterized). Its complete copied outputs (receipt, stdout/stderr, origin, JUnit) match the recorded byte lengths and SHA-256 values. The R1 property-removal probe at `5b27a5dd…` is **EXPECTED_FAIL 1/1**: removing N5 binding makes the real Foundry recomputation assertion fail. This is a valid negative-control red, not a candidate regression or closure by itself. Independent source review (`wave2/source-reviews.json`) is bounded-GO, reviewer not author; reviewer tests are UNRUN.

What it proves: focused persisted N5 candidate/outcome/atom binding and mismatch/blocker/tamper refusal, including one actual N5/Foundry consumer case. It does **not** establish a full factual served route or empirical effect. B04 post-process reopen and a second permitted reader remain UNRUN; B05 fresh standard-default positive consumer remains pending; B08 is unchanged positive behavior, not a new candidate receipt. C/F observation and served-profile inputs remain unavailable/UNRUN. No closure for B04/B05/B08 follows.

**Same-candidate model revision (`CYC-03`, B09 actual mechanism; B27/B28 context):** base `e1b970bb…` / tree `955c992d…`; final tested candidate `01e465e25577eb285fefc06e4e8d3ce5dd430e86` / tree `fb676e7c…`. B09 source commits are `69c647bc…`, `5b27a5dd…`, `de0e1862…`; the independent review’s source blob at `de0e1862…` is identical to that at final candidate. The complete candidate footprint is 8 source + 7 test files. The later `01e465e…` commit adds recursive budget/frontier and checkpoint-readback paths to the same candidate; those additions are adjacent work, not extra B09 evidence. N8 commits/tests are ancestors of this tested candidate.

`model-revision-current-candidate-01e465` is **1/1 PASS** (41.389s). Its single served-job integration test creates synthetic N4/N5 inputs, proves same model basis stops before N5, changed admitted model semantics reuses the same candidate and executes N5 under the current job owner, compares the changed effect, serializes the receipt, reopens CAS, reconciles persisted N4/execution/context/N5, and rejects a rehashed fake N4 atom occurrence. Complete receipt/JUnit/stdout/origin outputs match recorded lengths and SHA-256. Independent source review for the B09 source blob is bounded-GO, reviewer not author; reviewer tests UNRUN.

This is narrow source/code evidence, not B09 closure: the test expressly binds the receipt to its in-memory run projection and asserts `source_history_binding == "not_established"`; there is no ordinary automatic history transition/follow-up validator, no factual L6 or empirical-currentness input. The B09 owner packet still records unresolved source/institution, C-admission and F-relevance ratifications **and a separate unimplemented A-owned generic same-candidate retry/recursion producer/consumer**. Do not turn the missing source profile into a Boolean/global switch. B27/B28 are context only. The final model receipt has `closure_ids=[]`.

The e1b970 baseline run records one real failed served job before the model-revision method existed. It is supporting historical red, not a strict matched removal control: the final integration test body changed, so do not claim a paired identical-test P41 reproduction. The source diff confirms the later `reenter_after_candidate_model_revision` mechanism is new; retain that test-baseline qualification.

## Admission and one bounded local slot

These candidates are suitable for **G’s bounded source/test admission**, not finding closure. If the final candidate is integrated, use the complete `01e465` ancestry and all test/API companions; do not cherry-pick only the source file. Check the actual integrated tree and rerun the two deciding selectors once after source freeze, in one shared A/C/G local compute slot (no production dataset is needed for these synthetic receipts):

```text
pytest -p e02_origin -o addopts= --import-mode=importlib --strict-markers -q \
  tests/unit/runtime/quality/test_value_gate.py::test_n8_intake_rejects_outcome_candidate_and_atom_mismatches \
  tests/unit/runtime/quality/test_value_gate.py::test_foundry_value_port_recomputes_actual_n5_outcome_and_atom_bindings \
  tests/unit/runtime/quality/test_value_gate.py::test_simulate_only_n8_rejects_unknown_or_fatal_n5_blocker_before_owner_gateway \
  tests/unit/runtime/quality/test_value_gate.py::test_simulate_only_n8_rejects_tampered_persisted_n5_reference_before_owner_gateway
pytest -p e02_origin -o addopts= --import-mode=importlib --strict-markers -q \
  tests/integration/runtime_quality/test_e02_candidate_model_revision.py
```

Retain exact tree, argv/env, full output, JUnit, and SHA receipts. Do not repeat the removal mutation unless the implementation changes. Reserve the broader affected suite for the frozen integration wave; the old 217/106 receipt is not a substitute. Keep finding verdicts (`closed|limited|held|open`) separate from check states (`PASS|FAIL|ERROR|SKIP|UNRUN`).
