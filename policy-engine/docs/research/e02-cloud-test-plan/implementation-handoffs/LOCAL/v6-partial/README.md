# V6 partial sibling-failure slice

Pinned G slice base: `93d6aa62a8d236667fdf322a5fc17962523b185e`; the shared candidate checkout is at admission checkpoint `9e89dddfbcc3d8c44a421cc1fc143ec84f3753ae`. Root owns all commits. No files were staged, committed, or published by this slice.

The positive regression is `tests/unit/runtime/quality/test_recursive_generation_cycle.py`. It uses a real default recursive controller, real successful N6/N5 leaf producers, a real FileSystemCAS result, and a controlled later N4 failure at depth two. The error boundary covers leaf execution and its post-run context/binding/validation steps. The failure is typed with separate branch and origin refs. It checks the successful CAS read under WMR/atom/outcome bindings, exact failure code/message, no promotion receipts, pending ancestors/later siblings, a removal-and-rehash refusal, a later-completed-sibling refusal, a budget-status alias refusal, and a syntactically valid missing CAS ref refusal.

The paired V1 served witness is green: `LOCAL/v1-v2/current-fresh-get-v5.log` exercises the actual served fixture through successful N5, later sibling failure, persisted V5 child run, authorized fresh GET, and post-read CAS corruption. The response resolves the real N5 result, retains the failed-sibling checkpoint after corruption, and reports the result ref as not established. `LOCAL/v1-v2/current-v5-history.log` also verifies V4 frozen history and V5 N5-lineage roundtrip/removal refusal. These are bounded controlled witnesses, not production-currentness or G closure receipts. A controller-generated budget-stop child plus fresh served V2 readback remains unverified.

The pre-v5 failure log truncates its `GenerationCycleRun` repr, so the old run's schema version is not directly visible there. Its v3 assignment is derived from the pre-v5 writer branch (v4 only when a source-custody limitation exists, otherwise current v3) and the controlled fixture's no-limitation path; the current v5 receipt directly asserts the parsed version and nested bindings.

## Deciding command receipts

All Python test commands set `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`, and `JAX_PLATFORMS=cpu`.

| Log | Command outcome | Interpretation |
|---|---|---|
| `pytest-recursive-partial-green.log` | PASS, 1 test | Earlier depth-two-origin checkpoint version: actual producer and CAS read passed, corrupt ref and hash-preserving marker removal refused. Subsequent test expansion added parent-path chronology checks and a budget-status alias control. |
| `pytest-recursive-partial.log` | FAIL during test setup | The first nested-graph revision omitted the failure leaf from `module_refs`; the controller correctly refused the node denominator. This was a test-input construction error; fixed by including every graph node. |
| `pytest-recursive-partial-final.log` | ERROR during collection | Import failed before test collection in `confidence_ledger._stable_deployment_snapshot` with `canonical_deployment_identity_invalid`. No assertion on the final expanded source was reached. |
| `pytest-neighbor-regressions.log` | FAIL, 17 tests | Two constructor/export denominator tests observed concurrent shared-tree additions. History census cases raised `JSONDecodeError` while parsing a tracked JSON input. P41 attribution is `not_established`: the exact failure command was not replayed at slice base with a proven zero intersection against its complete input denominator. |
| `ruff-check-final.log` | PASS | Ruff check for the two V6-owned Python files. |
| `ruff-format-final.log` | PASS | Ruff format check for the two V6-owned Python files. |
| `pytest-recursive-owner-current.log` | PASS, 3 tests | Replayed after the shared candidate advanced. Covers the real producer/CAS sibling-failure path plus owner/currentness adversarial controls. The command uses one BLAS/OpenMP thread. |
| `ruff-recursive-owner-current.log` | PASS | Current Ruff check for the two V6-owned Python files. |
| `ruff-format-recursive-owner-current.log` | PASS | Current Ruff format check for the two V6-owned Python files. |
| `../v1-v2/current-fresh-get-v5.log` | PASS, 1 served test | V1-owned fresh GET witness for the persisted successful V5 child run plus V3 sibling-failure checkpoint; exact command and assertions are recorded in that log. |
| `../v1-v2/current-v5-history.log` | PASS, 2 history tests | V1-owned history witness preserving V4's frozen wire and rejecting removal of current V5 N5 lineage. |

The initial successful test log predates the last validator/test additions and is not a PASS receipt for the final source. `pytest-recursive-owner-current.log` is the fresh focused receipt for the current V6-owned recursive source and test. The separate V1 receipts above cover the served fresh GET and versioned history boundary; owner authority/currentness outside the controlled fixture and a served budget-stop remain unestablished.

During current-source fixture setup, the controller refused two incomplete whole-leaf maps: first the later pending leaf lacked an explicit execution intent, then it lacked an N4 port. The V6 test now declares both for every graph leaf, including the leaf not reached after failure. These are observed and repaired current test-input mismatches; no P41 inherited attribution is claimed.

## P40 and remaining seam

The second V6 escape is the same sibling-failure preservation class at a deeper branch, not a new class. The source validator now checks the traversal prefix across ancestors: all earlier sibling subtrees on the path must be completed, all later sibling subtrees must remain pending, and the failure branch cannot contain completed descendants. The final removal probe also mutates a later sibling into a content-valid completed node while retaining the failure and successful producer markers; it must be rejected as `recursive_partial_later_sibling_not_pending`.

V2 still has `traversal_status='budget_stopped'` and `traversal_stop_reason='child_budget_exhausted'`; V3 has `traversal_status='failed'` and `traversal_failure_reason='independent_sibling_failure'`. The V3 test rejects a budget-status alias and the V2 type owns its literal status. A real controller-generated budget-exhausted child run and fresh served V2 readback remain unverified. The V1 owner must add the V3 checkpoint/history schema and an independently authorized fresh GET before B13 can advance beyond `consumer_missing`/`verification_missing`.
