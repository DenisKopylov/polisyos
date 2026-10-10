# V5 joined Search / policy-funnel engineering decision

Date: 2026-10-10. Scope: read-only inspection of the V5 source-bound Search/GP/MethodJob path and the current policy-funnel consumer. The parent supplied source anchor `00954ff / tree cf422`; I did not run Git commands to independently verify that anchor. I did not modify production source/tests, run pytest, start a browser/server, or run a numerical fit. This note is the only write in this task.

## Decision

There are two separate consumer gaps. The library Search receiver can already consume a persisted MethodJob score, and the controlled causal MethodJob test exercises that route with a sequence generator. It does not yet join that route to the configured native GP profile. More seriously, when the diagnostic MethodJob's actual-dispatch source packet is rejected, `SearchLoopRunner` still forwards its finite primary metric and asks `ChampionRegistry` to consider it. The local source-bound proof therefore does not currently gate the score at the Search consumer.

The production policy funnel is another, wider gap: it has no MethodJob/DataSnapshot scientific producer route and no typed consumer for a MethodJob evaluation. Its own `FunnelExecutedWorkPacket` counts a policy-evaluator invocation, not scientific draws. The safe narrow G choice is to admit a configured MethodJob result as a **candidate-grade research observation only**, in a separate typed field/ref, after fresh source-bound admission. It must not be converted to `ate`, `policy_value`, welfare, fiscal metrics, policy promotion, or a publishable effect. A policy-effect mapping is not present and cannot be inferred from a method name or metric name.

The recommended engineering choice is to close the internal producer/result/consumer route without claiming external scientific authority. If “default consumer” means every policy-funnel run must obtain a real MethodJob score, the current runtime has no default DataSnapshotRef, method profile, slot map, seed, or approved metric mapping from which to do that. That missing request/config contract must be selected and supplied by the actual source owner; inventing a default would be a P05/P10 authority leak.

## Original acceptance and existing status

**B157** (`B_r19_original.md@9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`, lines 4117–4128) requires direct L4 and L3→L4 on the same original request, matching effective full L4 config and allowed output, unchanged caller context, and a measurably cheaper L3. The existing controlled diagnostic fixture does this at the actual bootstrap loop with 80/40/80 measured draws on one persisted 40-row DataSnapshot, then persists and fresh-reads the MethodJob evaluation/work packet through SearchLoopRunner. Its nuisance and tau fit layers are patched. The separate native DR L3/L4 fit is gated and remains unrun. The original acceptance does not authorize treating a diagnostic ATE as a policy effect.

**B108** (`B_r19_original.md@9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5`, lines 2897–2914) requires an effective fiscal measurement across declared presence/null/alias/sign/unit semantics: missing is unavailable, explicit zero stays zero, and conflicts/non-finite/incompatible units are explicit. The local objective extractor preserves explicit zero and falls back from missing/null `gov_balance` to `budget_deficit`, but no fiscal owner-issued profile, source, measurement context, or conflict authority is supplied here. B108 remains limited.

The existing V5 composition receipt explicitly records the default policy path as `producer_missing` for scientific draws and `bridge_missing` for policy/data/effect mapping (`LOCAL/reviews/v5-composition.md@db08ce266e2d4dff9aa969074abe64ef946fbb01f6552f05da9f7ea9212f7610`, lines 7–22). The V5 receipt separately marks the default policy path and B108 owner input unresolved (`LOCAL/v5-search/receipt.md@23704000e350cea56b1f47eb28415f45c563bbb0f4a43e4bd87b3ce3c13eacbc`, lines 39–69, 120–185). This finding is the same B157 producer/quantity/consumer class one level deeper (P40), not a new class to repair instance by instance.

## Source path inventory

The configured native optimizer path is real: `BayesianCandidateGenerator` produces a measured `BayesianSourceProfile` from its fitted optimizer/corpus/context; `SearchLoopRunner` passes the generator output to `MethodJobBenchmarkEvaluator`; the evaluator calls canonical `compute.runner.run_job`, persists MethodResult/evidence and a typed `BenchmarkEvaluation`; the runner persists and consumes that evaluation and can attach the measured GP profile. `WarmStartBridge` already consumes source run evaluations, while profile-kind and fitted-profile checks distinguish configured native GP from an injected optimizer. The existing native GP test, however, scores with test-only `_V5ScoreMethod`; it is not a causal MethodJob or the policy funnel.

The complementary controlled MethodJob path already exists in `test_methodjob_execution_work_packets.py`: its immutable-in-test source is a 40-row DataSnapshot and `b157_source_bound` BenchmarkSuite, the registered method is `DRLearnerEstimator`, its exact inputs are `X`, `treatment`, and `outcome`, and its typed work packet binds result/evidence, suite/data refs, seed, effective config, actual dispatched array fingerprints and measured bootstrap counts. Its SearchLoop integration uses `SequenceCandidateGenerator`, not native GP. The synthetic fixture is diagnostic only; it is not external policy data.

A complete walk of `src/polisyos/**/*.py` (.py file-type denominator: 2,748) found zero `SearchLoopRunner(` and zero `MethodJobBenchmarkEvaluator(` construction sites. The only current production runtime is therefore not wired to these APIs. `DefaultFabricPort.snapshot` can materialize a typed DataSnapshot from a DataViewRequest, but neither the policy runtime benchmark context nor `build_runtime_funnel_context` passes a DataSnapshotRef or a MethodJob plan into the policy funnel.

The default runtime instead constructs `ProductionPolicyEvaluationBackend` and drives L3/L4 through `_PolicyRuntimeWorkflowEngine` over existing metrics/reports. The persisted `FunnelExecutedWorkPacket` is explicitly a one-invocation observation, with actual draw fields null. The orchestrator fresh-reads that packet and binds its own policy vector, candidate, stage, run and requested configuration, but it does not read a `BenchmarkEvaluation` or `MethodJobExecutionWorkPacket`.

There is a direct Search-consumer falsifier to close before claiming even the library source-bound score path is safe. At `autotune/runtime.py:1009–1043`, the runner validates a work packet only when status is already `available`. If the evaluator returns `rejected` after the real dispatcher used same-length `X_alternative`, the evaluation's finite metric remains intact. Lines 1044–1093 then retrieve and return that metric, and lines 1074–1079 call `ChampionRegistry.consider_promotion`. The existing controlled test proves the evaluator detects the swap, but it stops before asserting what the Search receiver does with the rejected evaluation. Thus a false source-binding proof currently changes no score. Property = score admitted only from the actual source-bound dispatch; current predicate = finite configured metric (plus a conditional packet check only for status `available`); divergent case = actual array swap with unchanged field map and row count, packet status rejected, finite metric still emitted.

## Minimal closeable bridge

First extend the existing Search receiver's intake as one structural rule, not a per-test patch: for an explicitly source-bound evaluation configuration, score availability requires fresh CAS resolution and successful reconciliation of the MethodJob result/evidence and actual-work packet with the current candidate, suite, DataSnapshot/DataRef, run/evaluation/attempt, seed, effective method profile, actual dispatch binding and measured count. If the required packet is absent, rejected, unreadable, or mismatched, make the primary metric unavailable and non-promotable **before** it reaches the search objective or promotion registry. Preserve current optional non-source-bound benchmark behavior. Keep the source result typed and candidate-status explicit; do not trust the packet's inline metric or a candidate's self-label.

Then join the two already-existing producer legs with one controlled integration test in the existing MethodJob fixture owner: configured `BayesianCandidateGenerator` (native profile captured from the actual fit), existing `MethodJobBenchmarkEvaluator`/DRLearner MethodJob, that exact DataSnapshot and suite, actual loop counters, persisted BenchmarkEvaluation/result/evidence/work packet, fresh reader, SearchLoop result, and WarmStartBridge source→target. Keep the injected-optimizer path separately graded. A real native run is required for that positive and belongs only in the serialized numerical slot after the source freeze; no such run was made here. Until that fit completes, report the native positive as UNRUN. The prior bounded 80/40/80 MethodJob witness remains patched-fit evidence and must not be relabeled native.

Required removal probe: keep the candidate, declared `X → X` map, source row count, requested/effective draw config, generator/profile declarations, and method result markers unchanged; at the actual dispatch boundary substitute `X_alternative` of the same shape/count. The evaluator already produces a rejected packet. The repaired Search receiver must then suppress the primary score, prevent promotion, and retain a rejected/limited evaluation state after fresh reread. Also remove/alter the persisted result while keeping the ref and profile shape: fresh admission must refuse. The positive control on the unmodified arrays must show the score is present only after the same reader admits the real result and packet. This is P29/P32/P37/P38 behavior, not a constructor/marker test.

For the policy funnel, reuse the typed MethodJob artifacts but add a distinct typed candidate-observation reference to `FunnelStageResult`/outcome and an orchestrator fresh-reader. It must be separate from `FunnelExecutedWorkPacket` and separate from `simulation_metrics`. The reader should resolve `BenchmarkEvaluation`, its manifest and the method result/evidence/work packet; recompute metric/unit and candidate/run/stage/attempt/source bindings from those artifacts; and preserve native-vs-injected profile provenance. If required evidence is absent or mismatched, return a typed unavailable/rejected observation and leave policy evaluation/promotion unchanged. Do not route the method's `ate` through `policy_runtime_metrics._apply_policy_value_metrics`: that function maps any incoming `ate` to `policy_value` and falls back to zero if no causal report. A typed separate candidate score is the only bounded integration that avoids inventing policy semantics.

## G choice: score semantics

1. **Candidate-grade method objective (recommended engineering choice):** the explicitly selected BenchmarkSuite/PromotionPolicy names the exact candidate-search metric and unit; a fresh-admitted MethodJob result can update the GP's candidate-search observations and be reported as a research-only candidate score. It cannot update policy utility, causal effect, fiscal balance, L3/L4 policy verdict, or a published/promotion claim. The typed status stays limited/diagnostic; the score is not policy authority. This requires the source owner to pass the exact DataSnapshot, input maps, method/version/params, method seed, candidate/run/evaluation/attempt IDs and selected profile. It does not make the controlled synthetic benchmark externally current.
2. **Policy-effect/utility mapping (not selected):** mapping `ate` to policy effect/value or using it to approve/reject requires a governed estimand and candidate intervention binding, outcome/population/unit/sign semantics, data-owner source and time profile, causal validation/calibration, and an authority/promotion rule. None are supplied by the current API. Adding this by metric-name convention would change scientific law and authority.
3. **No bridge (not recommended for V5 completion):** keep the library and policy-funnel routes separate. This retains `bridge_missing` and does not satisfy the named joined-consumer requirement.

The external B108 fiscal owner/profile remains a separate input and must not be supplied from the synthetic DataSnapshot, a fixture, or `simulation_metrics`.

## Capability labels and acceptance

- Native GP + actual MethodJob + source-bound Search consumer: artifacts and individual producers exist; **joined native verification missing** until a real GP profile and real MethodJob are consumed together. Source-bound Search intake is currently **consumer_missing** for rejected-packet score admission (the rejected packet does not suppress the score).
- Policy-funnel scientific work producer: **producer_missing** on the default path; its invocation packet is not a scientific draw producer.
- Policy-funnel MethodJob/result bridge: **bridge_missing**; its context lacks the typed source/method request and its fresh reader does not consume MethodJob result artifacts.
- Policy-effect mapping/currentness: **not_established**, not inferred; the candidate-only G choice can close an engineering observation path without changing authority.
- B108 owner fiscal source/profile: **producer_missing / bridge_missing**, status remains limited.
- External API/dashboard: **surface_out_of_scope** for this engineering slice unless the selected product surface is explicitly assigned.

Acceptance should require the true native SearchLoop + MethodJob positive through fresh CAS, injected-vs-native profile separation, the same-shape actual-dispatch input swap that suppresses score/promotion, missing/tampered result refusal, and a policy-funnel typed candidate observation that never enters policy metrics or promotion. Do not claim B157 policy closure until the default path also receives an actual source-bound scientific plan and a valid G decision. P40 disposition: this is the second view of the same producer/quantity/consumer class; widen the source-bound intake and typed bridge across the whole route once, rather than adding another requested-count or marker-only patch.

## Read set (current SHA-256)

- `src/polisyos/scientist/methods/autotune/runtime.py@dc6c497f104533621d649632329b033c41a69cfadbaad0361ab69fc0b4c7b2fa`
- `src/polisyos/scientist/methods/autotune/bayesian_generator.py@c7d31383d6a1ff19d01d63e0a6763c432ce342cc7ccf333a910b0a352aabbd3d`
- `src/polisyos/scientist/methods/autotune/execution_work.py@de7ee6dc44d83b3f2b8eaea9f8850978b81ac11e1fd30d20a4a399f2501fc7f5` (source-bound typed dispatch/work packet owner)
- `src/polisyos/scientist/adapters/fabric_bridge.py@729648c0d5a46bce9799ba647530da02f9ad9e6a909fd7971303b53075e2a240`
- `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_benchmarks.py@202fd486a09a610fcd681af45c2b24f43a511d9bdf5767e7256aa53899508ff2`
- `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_engine.py@15f508608cbb931226d24efb111c2e325ed1a83d4cef1ae6cf492f74beea66ff`
- `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_metrics.py@5d22b2a417550453cac7da39a441c227f03a29ba8493a4c4145a126fb9691ff8`
- `src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py@c97671fbd57c8b410fb8a352b294db62265bf3fd513abf93abc8c5c5ffe4a992`
- `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py@a737d7056956730665c6f7eedd258bb427e12b09a847746138d65d40d9173a81`
- `src/polisyos/scientist/methods/search/funnel/types.py@aaaff554a58b48a529b7b1628d33692ddee238ce4de3e2cfd09d57ad6c3b15e4`
- `src/polisyos/scientist/methods/search/funnel/orchestrator.py@21af5bc3689d51f8306c56bce0b04ba4fdf0609b8246646c4a821109a9bd83fe`
- `tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py@2138d3634704b4ff94aee12d906f914c5d66f33c0cdc805f007ba6249f501904`
- `tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py@07f83cc7360e5be0c253d59ade9e563571f35c96f3f8e25964edd46c68bb0b06`
- `docs/reference/policy-design-case-failure-patterns.md@a64956e284b411276a16a612afffb1fb42daf03ffef8f7ef1c3f3f9bc25d0349` (P01/P02/P05/P10/P12/P14/P27/P29/P31/P32/P37/P38/P40/P41)


## Red-only Search consumer patch queued

The test-only unified patch is `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-search-rejected-packet-red-test-20261010.patch@b5383e4d15ecc5da97ad72f1da6ccf76f90c2356bc87ab5aaa2b4eefb2627fa3`. It targets the current test file `tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py@07f83cc7360e5be0c253d59ade9e563571f35c96f3f8e25964edd46c68bb0b06` and the current receiver `src/polisyos/scientist/methods/autotune/runtime.py@dc6c497f104533621d649632329b033c41a69cfadbaad0361ab69fc0b4c7b2fa`; the root-supplied source-before-changes anchor remains `00954ff`. The patch adds a focused actual `SearchLoopRunner` case using the existing immutable 40-row CAS DataSnapshot/Suite fixture. At the real `compute_runner.run_job` dispatch seam it substitutes `X_alternative` while leaving the declared slot map and row count intact, uses the already-controlled lightweight nuisance/tau layers, fresh-reads the persisted evaluation, and confirms the packet reader refuses the mismatch. The intended first red is that `simulation_results` still contains `ate`; a green implementation must suppress that score and keep promotion false.

Root-run command after applying only this test patch (not run by this worker):

```sh
cd policy-engine
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py::test_search_loop_rejects_score_after_source_bound_dispatch_swap -q
```

Input tuple: `DataSnapshot` → `scientist.method_dataset` with 40 rows, X as the declared feature and same-shape `X_alternative = X + 0.25`, alternating binary treatment, outcome `1 + X + 0.4*treatment`; `BenchmarkSuite(b157_source_bound, method_job)`; diagnostic candidate `b157_diagnostic`; DRLearner MethodJob; `bootstrap_draws=40`, seed 17, two cross-fit folds, one repeat; actual call wrapped at `compute_runner.run_job`. The test patches the nuisance and tau fit layers, so it does not run native GP, native DR nuisance fitting, a global fit, or the B157 native 80/40/80 witness. Wall time is unmeasured. This artifact is test-only: production receiver implementation and the native GP + MethodJob + CAS/Search joined positive remain queued until this red is captured and root sequences the source patch.


## Consumer implementation and joined-native patch queued

The unapplied unified patch is `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-search-source-admission-and-native-join-20261010.patch@f9e2b34ba355d8100a67d8605bcedc9e9f4e7faed410501e0c7849f3580fc1b8`. It is generated against the current root-applied red test and exact source files: `src/polisyos/scientist/methods/autotune/runtime.py@dc6c497f104533621d649632329b033c41a69cfadbaad0361ab69fc0b4c7b2fa` and `tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py@ad06c7defcf325e890ec0fb8923e5f976004e7e137bf2aeadbc2f833819bce42`. The parent’s captured red is under `LOCAL/raw/v5-search-rejected-packet-red-verification-20261010/`; its `pytest.stdout` SHA-256 is `05a07a81a4ffd96d2f0b53ff54317c954b13a0864f45d88ff765159bab13d888`. That run failed only at the consumer assertion: the rejected same-shape X dispatch still emitted finite `ate=1.0`; fresh packet admission had already refused the swapped dispatch.

The source patch treats every MethodJobEvaluator with nonempty DataSnapshot slot bindings as requiring source-bound admission, regardless of whether `capture_execution_work` is omitted, false, or true. Legacy score flow remains only for evaluators with empty DataSnapshot bindings. One helper fresh-reads the typed packet, reconciles the current candidate/suite/snapshot/run/evaluation/attempt, compares the packet’s exact method profile, bindings and seed with the configured evaluator, and compares any finite Search primary score and unit against the persisted MethodResult. Missing, unavailable, unreadable, rejected, source-mismatched, request-mismatched, and score-mismatched evidence removes the primary metric from the Search evaluation before objective, registry, or simulation-result projection and marks it non-promotable. Evaluators with empty DataSnapshot bindings retain their existing path. The positive controlled Search case asserts that an admitted source-backed score still reaches the receiver. Parameterized controls cover a missing packet ref, an unreadable ref, a metric substituted after the MethodResult was persisted, and both omitted and false `capture_execution_work`; for the latter two, the evaluator first returns a finite ATE and Search must suppress it before simulation-result projection or promotion.

The patch also queues a gated native join test at the existing numerical slot. It uses the configured `BayesianCandidateGenerator` (three native proposals to require an actual fitted GP profile), the actual DRLearner MethodJob over the immutable 40-row `b157_source_bound` DataSnapshot, typed work packets, fresh CAS reads, `TransferLearningManager` and `WarmStartBridge` source-to-target admission. The candidate coordinate is diagnostic plumbing only and is not bound to DRLearner inputs; this proves the native GP/MethodJob source-observation chain and warm-start profile path, not optimization efficacy, a policy effect mapping, or B108 fiscal authority. The native test is gated by `POLISYOS_RUN_NATIVE_METHODJOB_WORK=1` and was not run.

Root-owned queue after applying and reviewing this patch:

```sh
cd policy-engine
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py::test_search_loop_rejects_score_after_source_bound_dispatch_swap tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py::test_search_loop_suppresses_unreconciled_source_bound_score -q
```

Serialized native command (not run; includes the original same-input DR 80/40/80 witness and the actual fitted-GP joined Search/MethodJob/WarmStart witness):

```sh
cd policy-engine
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 POLISYOS_RUN_NATIVE_METHODJOB_WORK=1 uv run pytest tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py::test_native_source_bound_methodjob_direct_l4_matches_l3_to_l4 tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py::test_native_gp_methodjob_search_warm_start_fresh_reads_source_work -q
```

The patch is artifact-only: neither source nor test files were edited, and no new test, GP fit, or Git command was run by this worker. The policy-funnel B108/B157 G decision and any fiscal source/profile remain separate and unresolved; this slice only closes the library Search consumer admission path.


## Native patch receipt amendment

The current patch artifact supersedes the previously listed patch hash: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/v5-search-source-admission-and-native-join-20261010.patch@f9e2b34ba355d8100a67d8605bcedc9e9f4e7faed410501e0c7849f3580fc1b8`. The native join test now also fresh-reads the target warm-start MethodJob work packet and asserts its 40-row/40-completed-draw witness; it asserts the source SearchResult stage is present before retrieving its persisted evaluation. The original full-module scalar command is preferred after applying the patch:

```sh
cd policy-engine
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run pytest tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py -q
```

For the serialized native slot, enable the native marker and run the full MethodJob-work test module so its existing 80/40/80 witness and the new fitted-GP join execute together:

```sh
cd policy-engine
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 POLISYOS_RUN_NATIVE_METHODJOB_WORK=1 uv run pytest tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py -q
```

Neither command was run by this worker.


## P40 source-binding opt-out widening amendment

A second same-class deeper review found the earlier intake predicate still depended on the caller's `capture_execution_work` opt-in. A MethodJob with real DataSnapshot bindings could omit or set that flag false, produce a finite score with no packet, and bypass the source evidence admission gate. The mechanism is now widened across the full source-bound quantity: **nonempty DataSnapshot bindings alone require fresh work-packet admission**; only an evaluator with empty bindings stays on the legacy path. This is the second instance of the same producer/quantity/consumer class, not a new class and not another per-instance patch (P40). The controlled falsifier keeps the real DR MethodJob, same source refs/maps, and finite ATE while varying the capture flag omitted/false; the Search consumer must remove ATE, refuse promotion, and omit ATE from `simulation_results`. Existing missing-ref, unreadable-ref, score-tampering, and actual same-shape X-swap controls remain in the queued patch.

Updated unapplied patch SHA-256: `f9e2b34ba355d8100a67d8605bcedc9e9f4e7faed410501e0c7849f3580fc1b8`. The patch was validated against current source/test bytes in memory; it remains unapplied. No tests or fits were run by this worker.
