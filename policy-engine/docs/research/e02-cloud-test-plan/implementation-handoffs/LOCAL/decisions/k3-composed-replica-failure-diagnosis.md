# K3 composed replica failure diagnosis

**Scope:** read-only diagnosis of the K3 run at frozen source commit `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, tree `8d8c4082febf1676dd86084106f3266d8b2131a3`. No tests were rerun and no product files were changed. The raw receipt describes one controlled local integration run, not production or native-backend currentness.

## Evidence and source binding

The run is `LOCAL/raw/composed-mac-current-source-20261010/k3_foundry_replicas_seeds_31_32_33/`. Its recorded command selected the complete `tests/integration/scientist/methods/backtesting/test_backtest_foundry_replicas.py` file; the JUnit contains five cases, three passed and two failed, with no timeout. `metadata.json` binds the command to the frozen commit/tree and records source identity before and after as the same commit/tree. The checked frozen source bytes match the checkout for the backtest orchestrator (`83a670a3…`), replica integration test (`5d883f66…`), Foundry bridge (`c65da189…`), workflow executor (`99566eea…`), and BacktestReport contract (`dba991d3…`).

Deciding local artifacts and SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| `junit.xml` | `7a57f62a09d31afafecea91a8a01bc840b0698fb918ba34165004ecdbba66374` |
| `stdout.bin` | `a888b9f1807627297bc38555d58d873a7f4cd95e989e6131eb7c25053f5fe9b4` |
| `metadata.json` | `275828b90bfb3a4cd48370ac68287ee49012119e08bc8094600f88b0887e8c0c` |
| `stderr.bin` | empty (`e3b0c442…`) |

JUnit failures are precisely:

1. `test_backtest_replays_only_masked_bindings_with_distinct_real_foundry_replicas`, assertion at test line 240.
2. `test_backtest_retains_failed_real_foundry_replica_and_fresh_report_readback`, assertion at test line 323.

## Finding 1: actual projection reason is correctly scenario-qualified

The success case reaches the real Foundry route for seeds 31, 32, and 33. The persisted cohort has three unique run IDs, `requested/started/foundry_execute/completed/failed = 3/3/3/3/0`, and each row records the matching seed and successful workflow status. The test also checks each captured input binding resolves to the masked snapshot with values `[1.0, 2.0]`, excluding `900.0` and `901.0`.

The report is intentionally degraded because a multi-run statistical projection is not configured: the per-scenario reason is `scientist_replica_projection_unsupported` and the effective mode is naive. `BacktestOrchestrator.run()` qualifies every scenario reason with `plan_id` before building the report (`src/polisyos/scientist/methods/backtesting/orchestrator.py`, around line 424). The persisted report therefore carries the exact value `masked_foundry_replicas: scientist_replica_projection_unsupported`. The test had already checked that fresh `load_backtest_report()` readback preserves the same reason list; it fails only because line 240 asks whether the bare, unqualified string is a list member. The sibling incomplete-cohort assertion already uses the scenario-qualified convention with `endswith`.

CAS readback confirms report artifact `sha256:0d1e65f04e9388175342159e1e21d63d3ad4ef7b2d32da5001a4e14256ef029a` links cohort artifact `sha256:7c298690ad1ff9265dae1d302943af169e9bfe7a60b17bb790381b2bf32cf8b6`. The cohort retains the three successful rows. This is an assertion/expected-value mismatch, not a failed producer, consumer, or projection behavior. The test should compare the exact qualified reason (or use the established suffix convention) while retaining the fresh-readback check; do not remove the `plan_id` qualification or weaken the property to an arbitrary substring.

## Finding 2: failure cause survives structurally, but the summary field masks it

The negative case injects `RuntimeError("controlled_foundry_replica_failure")` at the `DefaultFoundryPort.execute` seam for the middle request and delegates the other two to the real port. The call order and persisted run IDs show seeds 31, 32, and 33; the cohort retains the full requested denominator with `requested/started/foundry_execute/completed/failed = 3/3/3/2/1`. Seeds 31 and 33 completed and retain their simulation/metrics refs. Seed 32 is failed, has workflow status `fail`, and has a persisted workflow report.

The failure message is not absent from the durable chain. The fresh CAS reader resolves the failed replica’s workflow report (`sha256:7fcd5b42fcefe7e59d5497a24383a88de7984c85eab1fc23c32d9b76747e54b5`), whose failed `run_simulation` node records `code=node.exception`, `details.type=RuntimeError`, and `message=controlled_foundry_replica_failure`. The cohort’s `replicas[1].workflow_failures` copies that same alias/status/error, and the cohort manifest includes the workflow report as `replica_2_workflow_report`. The report artifact `sha256:f621bc12e991d7130f4269061643d86267abc7af125c06ff7bc78596a725a22b` links the cohort as `replica_cohort:masked_foundry_replicas`. Fresh `load_backtest_report()` and cohort reads occurred before the failing assertion.

The narrow defect is in the human-readable projection. `_BacktestReplicaFoundryPort.execute()` records the specific exception in its `failure` field (around line 193). The workflow executor serializes the original node error. The outer orchestrator extracts that structured node failure into `workflow_failures`, then raises `ValueError("scientist_workflow_status:fail")` before consulting the adapter failure. In the outer `except`, it assigns that wrapper to the local `failure` used for the warning and `_BacktestReplicaRecord.failure`; `replica_foundry.failure = replica_foundry.failure or failure` preserves the specific cause on the adapter, but the persisted row continues to use the generic local wrapper (around lines 675–753). Thus the actual cause is preserved in the typed nested field/report, while the row’s `failure` string and summary warning hide it. The failing test exposes that field-level inconsistency; it is not evidence that the failure or sibling outcomes were dropped.

The minimal source-level closure is one shared failure-projection choice at the replica-record emission boundary: when the adapter or the already-read workflow report contains a more-specific node cause, use that cause for the row’s `failure` and corresponding warning; retain `workflow_status` and `workflow_failures` independently, and use the synthesized workflow-status value only when no underlying cause is present. This derives from the actual captured error rather than recognizing the test’s literal message. The targeted negative test should continue to assert, through the fresh CAS reader, the exact failed row/cause, `workflow_status=fail`, all three seeds, two successful siblings, counts, and naive incomplete-cohort degradation. Existing unit coverage already expects the row failure to retain specific Foundry and report-validation errors (`tests/unit/scientist/methods/backtesting/test_backtesting.py`, around lines 1277 and 1400), so changing the integration assertion to inspect only an unrelated marker would weaken the existing field contract.

The report correctly falls back to naive predictions and carries `masked_foundry_replicas: scientist_replica_cohort_incomplete`; it does not treat two successful siblings as a complete three-run projection. This controlled exception proves bridge-level failure retention, not native Foundry numerical failure.

## P40 and pattern disposition

**P40 bucket: SAME_CLASS_DEEPER, within the already named B166/B170 backtest-to-real-runtime realization class.** The original criterion review states that B166 and B170 share this class and B170 is its second, deeper replica/failure-retention facet; the move was to widen the proof to real Foundry execution and fresh CAS report/cohort readback (`LOCAL/reviews/e-original-criteria.md`, its B166/B170 review and P40 sections). The present two reds are not two new rounds: the first is an incorrect unqualified reason assertion; the second is a deeper projection of failure detail within the same end-to-end path. Widen the single failure-presentation boundary once, or explicitly bound the `failure` field as a workflow-status summary and test the structured `workflow_failures` cause as the authoritative detail. Existing unit expectations favor the former; the available cause and shared producer seam make it feasible, so a residual is not presently justified.

Pattern pass: P04 (keep failed workflow status distinct from descriptive cause and degraded report status), P10/P29 (the actual run and persisted consumer were inspected), P38 (the test’s unqualified reason differs from the serialized scenario-qualified property; the durable summary also uses a status proxy where a captured cause exists), and P40 (same class deeper). The repo failure/repair register was reread at `docs/reference/policy-design-case-failure-patterns.md`.

**Current decision boundary:** no source correction or rerun was made in this diagnosis. If this path is repaired, the distinguishing control is one injected, distinctive Foundry exception with a surviving workflow failure report: the fresh-read replica record and report warning must preserve the cause, keep status `fail`, keep seeds 31/32/33 and both successful siblings, and keep the incomplete-cohort naive fallback. That falsifies a marker-only fix that merely changes the expected string while the emitted `failure` remains `ValueError: scientist_workflow_status:fail`.
