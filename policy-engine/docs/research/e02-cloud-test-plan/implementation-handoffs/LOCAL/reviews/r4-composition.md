# R4 shared MethodJob admission: independent composition review

Review date: 2026-10-09. Read-only review at `HEAD=80f043c0c007ca14dfd4927f980e391f4fcdc62a`; the shared worktree is dirty and R4 source is uncommitted. Exact current-byte SHA-256 pins are below. This review does not accept a B56 closure.

**Decision: limited candidate evidence, with one generic shared-pool escape.** Runtime configuration pins one process-local shared executor, and the traced `ControlWorker → run_experiment → causal node → run_job → MethodBackend → MethodDispatcher` path uses it. The synthetic route records actual dispatch activity, actual folds, final state links, and fresh tenant-enforced CAS reads. Production capacity and roster remain `not_established`; the full post-reference-fix cap-1/cap-2/removal matrix is still pending.

## Finding and P40 bucket

**F1 — callback re-entry bypasses the aggregate cap (P38; same aggregate-admission class one level deeper).** `run_shared_executor_sync` executes inline whenever `_SharedExecutor.is_current_worker()` is true. That marker is also set for `Future` callbacks. Late callbacks run in their registering threads, and concurrent late callbacks on one completed future share one `_slot_held` reservation. They are therefore treated like physical workers even though those threads occupy no executor worker.

I reproduced the divergent case with a capacity-1 executor: two threads concurrently register late callbacks on one completed future; each callback invokes `run_shared_executor_sync` around a barrier-held dispatch. The complete probe output was `{'capacity': 1, 'callbacks_alive': [False, False], 'peak_inline_dispatches': 2, 'errors': []}`. The existing `test_late_callback_refuses_nested_work_under_new_full_workers` exercises `executor.submit` and passes; it does not exercise the helper’s inline branch. The actual canonical Runtime test invokes `MethodBackend` from ControlWorker caller threads, so this probe does not show that its specific route enters from a late callback. It does falsify an unqualified claim that every MethodBackend dispatch in the process observes the configured aggregate cap.

P40 bucket: this is the **same aggregate-cap class at the next mechanism boundary**, not a new workload class. Treat it as the second escape in that class; do not add a call-site patch. Either widen admission so the inline branch distinguishes an actual executor worker from an external late-callback thread, or declare the bounded residual: callback-originated and recursively nested MethodBackend calls are outside the demonstrated cap. The smallest absent closure capability is a physical-worker identity or callback-aware reservation in the inline helper. Falsifier: rerun the barrier probe above at caps 1 and 2 and require peak inline dispatches to stay within cap; also retain the real ControlWorker route and removal negative.

## Composition and evidence

| Property | Source/test evidence | Review result |
|---|---|---|
| One process profile is resolved before Runtime service composition | `create_runtime_api_app` forwards capacity/revision; `RuntimeContainerConfig` requires both or neither; `RuntimeServiceContainer.build` configures the singleton; `configure_shared_executor_profile` holds one lock and rejects conflict. | Correct candidate-only process owner. Same-process second Runtime with a different profile is refused; no second pool is created. Host fallback is bounded to 4–32 CPU-derived workers and remains explicitly candidate-only. |
| Real MethodJob dispatch reaches the common choke point | `MethodBackend.run` wraps only `MethodDispatcher.dispatch` in `run_shared_executor_sync`; result/evidence CAS writes happen after dispatch returns. Integration test uses two Runtime containers sharing the configured executor and calls their actual `ControlWorker.dispatch_once` paths. | Aggregate bound is on active dispatches, not the full job/CAS lifetime. The traced route is representative of the requested runtime path; the executor is also shared with generic work, so availability/fairness is not established. |
| Context and tenant scope survive the dispatch bridge | `_SharedExecutor.submit` captures `contextvars.copy_context`; MethodBackend’s default store enables ambient ownership; the integration test uses two tenant/cell scopes and fresh ownership-enforced CAS instances. | Cross-scope result/evidence ownership and readback are checked. The unit owner test also proves a different tenant cannot read the result/evidence. This is candidate isolation evidence, not production authorization. |
| All folds run once and outputs survive capacity changes | Integration wrapper instruments the actual TMLE fold function and checks expected versus observed `(study, repeat-seed, fold)` identities; current TMLE source executes the fold list serially. | Raw pre-reference-fix profile receipt reports cap 1/2/removal dispatch peaks `1/2/2`, two completed jobs, and `12/12` folds in each profile. That proves the removal control measures real dispatch, not executor configuration. It does not measure peak RSS, elapsed time, or wait duration required by the original B56 acceptance. |
| Current result/evidence refs bind to the final node state | Causal materialization revalidates refs through canonical `ArtifactRef` and compares artifact ID, kind, media type, and selected manifest-profile digest. Readback validates refusal content and manifest lineage. Targeted typed/structured/malformed/foreign-ref tests passed. | The prior subclass-equality defect is closed at the identity consumer. The post-fix cap-1 child output contains both `causal_node_status=ok`, linked result/evidence refs, and fresh owner-scoped reads. Its outer test still failed on the then-stale `success` literal; the source predicate is now corrected to `ok`, but has not been rerun. Cap 2 and removal are pre-fix receipts only. |
| Cancellation preserves occupied physical capacity | `_SharedFuture` releases only after the worker wrapper and callbacks finish; queued cancellation cancels the queue entry. Unit tests cover queued cancellation, running worker reservations, callback reservation, and shutdown lock ordering. | No cancellation over-admission was found for physical worker tasks. Running Python calls remain cooperative; cancellation cannot stop a running method. The synchronous MethodBackend itself has no per-job cancellation interface. |

The integration test bypasses only the separately owned causal-evaluation safety gate to isolate compute admission. Its result remains candidate/legacy-shadow and establishes no scientific safety, admissibility, or promotion authority. The cap-1/cap-2 equality assertion is present in the corrected harness, but the post-reference-fix matrix has not run. The exact B56 criterion remains limited: its original card treats the 15/60 worker example as configuration arithmetic, not measured overload, asks for preserved folds/results/provenance, and calls for time, memory, active-worker, and wait measurements. Source: `B_r19_original.md@198076863e143dea9f89f02734b13d50dae3eed5` lines 1409–1423, original blob `d800082eebfc12eaf647b0c0257c4f06e135d25a`.

## Verification performed

Lightweight tests only; no numerical native fits were started by this review:

- `.venv/bin/python -m pytest -q tests/unit/common/test_async_tools.py` — exit 0.
- `.venv/bin/python -m pytest -q tests/unit/runtime/http/test_shared_executor_composition.py` — exit 0.
- `.venv/bin/python -m pytest -q tests/unit/scientist/compute/test_runner_polyglot.py::test_method_job_results_follow_ambient_tenant_ownership tests/unit/scientist/compute/test_runner_polyglot.py::test_competing_method_jobs_share_the_configured_physical_executor` — exit 0 (three cases including capacities 1 and 2).
- `.venv/bin/python -m pytest -q tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_contract_matches_branch_state_ref_identity tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_contract_normalizes_structured_branch_state_ref tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_contract_fails_closed_on_malformed_structured_ref tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_contract_rejects_nonemitted_ref_identity tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py::test_causal_output_refusal_readback_binds_actual_manifest` — exit 0 (12 cases).

Read native receipts without rerunning them: post-fix cap-1 stdout SHA-256 `cce40590cf82b1278142c0fd3e5b98cba77b5923c9ea305ed6c07dbe6de93e26`; pre-fix cap-1/cap-2/removal stdout SHA-256 `70865647589c5ea88f54a2770ee4360ef414019358f5d7778080e36b3f1c9e70`. The first contains complete cap-1 child output but ends in the stale outer `success` versus actual `ok` assertion; the second predates the ref-identity fix. Both are evidence only for their stated boundary.

`P41`: the corrected full native command was not replayed from the designated base during this read-only review. The old status-literal red is attributable to the recorded harness assertion; whether the corrected cap-1/cap-2/removal matrix is green remains `not_established`, not inherited or cleared.

## Exact read pins

SHA-256 values identify the exact on-disk bytes reviewed in the shared dirty worktree (not committed source claims):

| Path | SHA-256 |
|---|---|
| `policy-engine/src/polisyos/common/async_tools.py` | `13fc1ebff288bfe4efabf482e9d6677843727d74730000d954384c0160744cda` |
| `policy-engine/src/polisyos/runtime/http/app.py` | `26fb16b010f651613162cdb4c3786577d79a73eb9af4479724878574828c6368` |
| `policy-engine/src/polisyos/runtime/http/container.py` | `7d498763dffad40244083b67b6ca3bb32a53d2ca01cab00e5bce21434312a077` |
| `policy-engine/src/polisyos/scientist/compute/runner.py` | `9f2d3fad636d5b1125d77afe584d568bee4ee13e9fce3ddeb73e7478d27dfd77` |
| `policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py` | `d5baee1836115d8757ae80e3c6f7d7ea6e7c9b831128685bd41c4447c1466744` |
| `policy-engine/src/polisyos/core/artifacts/manifest.py` | `fb1fb68e18b80ba83ee2aa6b94a011386ede96bc75c492123bb4de3bec45639d` |
| `policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py` | `cf8d32b9fd825fa2efdd169652de78164f714c7ad01f2d8fde387095111103a0` |
| `policy-engine/tests/unit/common/test_async_tools.py` | `51afb8365d95dc1cbbd2662ebbd74f53e743e1bec5df7b85e259f9058ce33251` |
| `policy-engine/tests/unit/runtime/http/test_shared_executor_composition.py` | `84c47ba003916d2989427578e858eaf7c3cd836d0cfb2b64f0af5327a4df35d5` |
| `policy-engine/tests/unit/scientist/compute/test_runner_polyglot.py` | `018b8b92d2b0ae04ff863b67d2d0fed4422671b7f9ab911636a58f830ed7a259` |
| `policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_run_causal_evaluation.py` | `83c1d54bdb5bcd931abe2b6f95fcc4a8630a26f0d45f668b616a960478604c0e` |
| `policy-engine/tests/integration/scientist/orchestration/workflows/test_r4_shared_study_admission.py` | `3544eb100db855100d8d8d8e28cbf85b024fc0b6c9cb33b1b154f6c889a72103` |
| `policy-engine/src/polisyos/common/README.md` | `c346b8ec6e05a4bfac7feb2b65311515eaa99bd8f4cdbe83c66610c4e591c12e` |
| `policy-engine/src/polisyos/scientist/compute/README.md` | `fc785d5c1b584509eace7494590131962f0cbfd284d234c9343916015349dec4` |
| `policy-engine/release-fragments/unreleased/2026-10-09-e02-r4-shared-method-admission.toml` | `b0e6bfb10979ba74283e87be35eea067e11917242128ea18a9063ff914850c70` |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/ready-paths.json` | `a7654cec9acf82eb307788b4f01adf4f05e099b5425aec5b9d7b1f9834f1a578` |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/options.md` | `426b96c149b212b02120ff33804994db823abc31e0daf74ac69b7d03fee7f78d` |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/decision.md` | `5bda39ac13aed2a533c26e21286cbb148dc33c2e4eb78d00c3995b2e4a226d30` |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/outputs/current-native-attempt.md` | `04c30faa47ccf575004eb90a208c477b4a09cb7a978dadc6e3db7efff377abd9` |
| `policy-engine/docs/reference/policy-design-case-failure-patterns.md` | `a64956e284b411276a16a612afffb1fb42daf03ffef8f7ef1c3f3f9bc25d0349` |

Additional criterion pins: original B56 file `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@d800082eebfc12eaf647b0c0257c4f06e135d25a`; current F summary `G-B56.md@a9e0df4b312732feda52123cee7eba6978133dc5` at base `80f043c0c007ca14dfd4927f980e391f4fcdc62a`.

## Delta review — late callback capacity fix

Reviewed 2026-10-09. This is a read-only review of the shared callback/helper fix only; it does not reopen the broader R4 or B56 decision.

**Decision: GO for this delta.** The prior F1 escape is closed at the common `run_shared_executor_sync` bridge. `_SharedExecutor.run_sync` now inlines only when the current thread is a physical pool worker. For a late callback thread, it temporarily clears the logical callback-active flag only while submitting one bounded pool job, restores that flag before waiting, and leaves direct callback `submit()` subject to the existing reentrancy guard. The submit path captures `contextvars.copy_context()` on the callback thread, so the tested owner scope reaches the worker. The complementary capacity-1 nested-worker test confirms a real worker still runs nested sync work inline on its own thread instead of queueing and waiting on itself.

The new barrier test measures simultaneous dispatch bodies at capacities 1 and 2, checks that callbacks run off-worker and dispatch bodies run on workers, and checks both distinct owner scopes survive. My focused replay passed all four cases in 0.45s. The retained complete `test_async_tools.py` suite reports 32 passed (stdout SHA-256 `09d5fffd970bbc9e660d8bc2d4e9d0cb8ddbb83f9321a7b69f2c1a18950a8000`). The retained property-removal control restores the former logical-marker decision while leaving the surrounding callback code in place and measures peak 2 at capacity 1 (stdout SHA-256 `fd27a1c52044b3b51497f09633f6b9ccf5d92591266ac0cbb1d070007fc4a9ff`); the retained focused green output is SHA-256 `b9023d9bbc048eaa3eb60bdac0d43446862cccecfb960767007588860f210fb3`.

Exact bytes reviewed: `policy-engine/src/polisyos/common/async_tools.py@cfa6393b0ceb193588f414ed69db0193b7f78f4e1d9159a6270e89a78898a03e`; `policy-engine/tests/unit/common/test_async_tools.py@1dba2e9e0d7b8cf518f9dc37eeba07e2ce13901e641f7ef00d3eb8b8e6e89a1d`. The prior review file bytes before this appendix were SHA-256 `f114bb24efc6f60aa3b2b84f82653c4bb5e18fbef5145a8ad4d94d9c14403099`.

This closes only the generic late-callback cap escape. It does not upgrade the candidate profile to production authority or establish a production capacity/roster. The current native cap-1 wrapper assertion and post-canonical-reference cap-2/removal matrix remain pending as recorded in `LOCAL/r4-workload/ready-paths.json`; no native fits were run in this delta review.
