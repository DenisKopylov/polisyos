# R4 native shared-admission attempt

Status: **pre-fix cap matrix plus post-fix cap-1 native evidence; not a B56 closure**. The cap-1 child completed and emitted its complete receipt; the wrapper test exited nonzero on an incorrect `success` status literal, corrected to the declared `NodeStatus` value `ok`. That corrected predicate has not been rerun; no cap-2 or removal replay was started.

The exercised target was `tests/integration/scientist/orchestration/workflows/test_r4_shared_study_admission.py::test_runtime_control_worker_shared_method_admission_and_removal_probe`. It ran two independent Runtime instances in one configured process scope through ControlWorker → strict Scientist mapper → `run_experiment` → workflow builder → causal node → `run_job` → `MethodBackend` → dispatcher → TMLE fitter. The test bypassed only the separate causal-evaluation safety admission to isolate compute admission; it makes no scientific safety, admissibility, promotion, or production-deployment claim.

Before its outer consumer assertion, each profile recorded two worker completions, two `run_experiment` entries, two MethodBackend/dispatcher entries, and all 12 expected actual fold identities (two studies × two repeats × three folds). The measured dispatcher peaks were 1 at cap 1, 2 at cap 2, and 2 after the Runtime admission bridge was removed. The removal control therefore demonstrated the aggregate-cap escape. Both studies' result and evidence artifacts reopened from tenant-enforced CAS with ownership claims matching the admitted scope. Saved result, report, envelope, and executed-fold projections matched between cap 1 and cap 2.

The pre-fix full route did **not** pass: the causal node failed with `output_not_emitted_current_attempt:causal_report_ref`, and the final result/evidence references were not linked into state. The branch-state producer wrapped canonical `ArtifactRef` models in a dynamic tracked subclass; Pydantic model equality rejected that current emitted reference against the base-class reference returned by MethodBackend. A microfix now normalizes typed or structured branch-state refs through the canonical `ArtifactRef` owner, then compares the existing full identity key (artifact id, kind, media type, selected manifest profile) at materialization and readback. It also compares refusal source identities and every declared `InputRef` field through validated canonical serialization, and it requires refusal manifest kind/media/schema/producer to match the expected artifact contract. Typed and structured branch-state positives pass; malformed structured refs fail with Pydantic validation rather than an attribute error; identity, header, and lineage negatives pass. Removing the JSON media-type guard made the real CAS wrong-media negative fail with `DID NOT RAISE`, confirming that the new guard carries the property. The focused 14-test micro-suite was followed by the authorized cap-1 full-route replay below.

Post-fix cap-1 native receipt: both actual Runtime workers completed successfully through ControlWorker → strict Scientist mapper → `run_experiment` → builder → causal node → `run_job` → MethodBackend → shared dispatcher → TMLE → CAS and final state. The candidate profile revision is `r4-native-method-cap-1-v1`; both worker futures returned `true`, two producers/submissions overlapped, both real dispatches ran on the shared worker, and the dispatcher peak was 1. The executed-set census was 12 expected/12 observed folds (six per study, from two repeats × three folds), with each study's causal node at status `ok`, no node error, result/evidence refs linked in final state, and fresh owner-enforced CAS reads classifying the input, result, and evidence as `admitted_scope`. Numerical values and complete report/envelope objects are in the retained JSON receipt; the previous cap-1/cap-2 result equality remains from the pre-fix native wave. The outer wrapper exited 1 only because a new harness predicate expected `success`; it now checks the declared `NodeStatus` literal `ok`. No second native run has yet occurred.

Post-fix cap-1 full stdout, including the complete profile receipt emitted before outer assertions:

`implementation-handoffs/LOCAL/raw/r4-workload/cap1-postfix-native-confirmation.stdout.txt` @ SHA-256 `cce40590cf82b1278142c0fd3e5b98cba77b5923c9ea305ed6c07dbe6de93e26` (native child completed; outer test failed on the corrected status-literal mismatch).

For the frozen cap-1/cap-2/removal replay, set `POLISYOS_R4_CAP1_DIAGNOSTIC_ONLY=0` and `POLISYOS_R4_RECEIPT_DIR=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r4-workload/final-freeze-20261009`. The harness writes each child stdout/stderr before parsing or parent assertions and preserves partial timeout streams. Its lightweight `test_r4_child_output_retention_writes_full_timeout_streams` check passed; no numerical profile was run after this harness change.

Pre-fix native raw stdout, including all child receipts and the final outer failure:

`implementation-handoffs/LOCAL/raw/r4-workload/cap1-cap2-removal-native-fixed.stdout.txt` @ SHA-256 `70865647589c5ea88f54a2770ee4360ef414019358f5d7778080e36b3f1c9e70`.

Canonical-reference micro-suite output (14 passed, 19 deselected):

`implementation-handoffs/LOCAL/raw/r4-workload/canonical-ref-microtest-v6.stdout.txt` @ SHA-256 `980f333ce5e21868f03378e377c7dc08fa0aecf49896bd733bf7e6820e0fa136`.

Media-guard property-removal probe (expected red: the real CAS wrong-media case was accepted when the guard was removed):

`implementation-handoffs/LOCAL/raw/r4-workload/canonical-media-guard-red.stdout.txt` @ SHA-256 `e09e9f2a8ff8e01d329366c5a1c400e09ffa87e63ab1294a9130bb9b4486a1e3`.

Production capacity/profile revision and deployed study roster remain `not_established`; B56 exact binding remains `closure_now=not_adjudicated`.
