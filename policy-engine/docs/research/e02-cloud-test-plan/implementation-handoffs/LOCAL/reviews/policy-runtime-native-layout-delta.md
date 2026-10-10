# Policy runtime native-layout delta review

Review is read-only against source base `9e02a9f49c8b01026327a9f7c7e18711b13a96f2` and the candidate worktree at `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a` plus its current working changes. Scope is the policy-runtime support and blueprint-runtime decompositions, their focused tests, and release fragments. Unrelated concurrent worktree paths were not reviewed.

## Finding

No blocking behavior-preservation defect was found in the extraction. The support module retains its explicit `__all__` with the same 32 names and order. AST comparison found no signature drift for those exports. The canonical runtime types, `ProductionPolicyEvaluationBackend`, and `run_promotion_with_evidence` stay defined at `policy_runtime_support`; the blueprint `RunPolicyBlueprintRuntimeNode`, `_SPEC`, `_PolicyRuntimeWorkflowEngine`, and `_resolve_replay_bundle_ref` retain their canonical definitions and FQNs. `_PolicyRuntimeWorkflowEngine` and `_resolve_replay_bundle_ref` have identical ASTs to the base; `_SPEC` is identical.

The complete Python importer census walked `src/**/*.py` and `tests/**/*.py`: 5,585 files at the base and 5,621 in the candidate. For `policy_runtime_support`, baseline importers were 10 files / 15 import statements; candidate importers are 15 / 20. All 10 base importer files remain, with only the five adjacent implementation helpers added. For `run_policy_blueprint_runtime`, baseline importers were 6 / 9 and candidate importers are 7 / 10; all six original importers remain and the sole addition is the new characterization test. These counts use AST import statements, not text matches.

The blueprint node now sequences `prepare_runtime_session`, `prepare_runtime_benchmark_evidence`, `build_runtime_funnel_context`, `run_runtime_funnel`, and `finalize_runtime_session`. The helpers receive the canonical module as `owner` and resolve workflow dependencies on that owner at call time, preserving the existing monkeypatch seam. The extracted benchmark, engine, strategy, and reporting helper bodies that were moved intact match their base AST bodies. The support facade similarly delegates through canonical wrappers; dependency-sensitive calls pass facade-owned collaborators into the helper. This preserves existing patch points used by the support and runtime tests.

All mechanism modules remain under the 1,000-logical-line cap, counting nonblank noncomment lines as `architecture_report_only_contracts._count_lines` does:

| Module | Logical lines |
| --- | ---: |
| `policy_runtime_support.py` | 946 |
| `policy_runtime_artifacts.py` | 701 |
| `policy_runtime_metrics.py` | 400 |
| `run_policy_blueprint_runtime.py` | 590 |
| `policy_blueprint_runtime_benchmarks.py` | 666 |
| `policy_blueprint_runtime_engine.py` | 370 |
| `policy_blueprint_runtime_reporting.py` | 688 |
| `policy_blueprint_runtime_strategy.py` | 146 |

Ruff, Ruff format, and C901 with the repository’s explicit maximum complexity 12 passed over all eight modules and the two new characterization tests. A scoped independent pytest run passed 58 tests in 14.09 seconds, with two Torch `jit.script` Python 3.14 deprecation warnings:

```text
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -o addopts= -q -ra \
  tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support.py \
  tests/unit/scientist/nodes/builtins/decide/test_policy_runtime_support_decomposition.py \
  tests/unit/scientist/nodes/builtins/decide/test_run_policy_blueprint_runtime.py \
  tests/unit/scientist/search/test_policy_blueprint_runtime_guards.py \
  tests/unit/scientist/search/funnel/test_policy_runtime_work_packets.py \
  tests/unit/scientist/search/test_phase_d4_runtime_integration.py \
  tests/unit/remediation/test_fun_03.py
```

## Separate FUN-03 behavior delta

The reporting helper adds a new fail-closed behavior when the funnel outcome cannot be projected as finite canonical JSON. Finalization validates the projection before resolving the final evaluation and before the final evidence-bundle/VOI report projection and branched-state attachment. On refusal it returns `node.invalid_state` with the original state and previously produced refs. Benchmark evidence and funnel-stage work have already occurred by this point. The paired tests cover a non-finite objective and nested `NaN`/`±Infinity`, and a valid empty funnel still keeps its internal not-evaluated sentinel out of the public projection. This is a NEW projection-integrity behavior class, separate from the same-behavior module extraction, and is covered by the C12/FUN-03 work rather than treated as an extraction regression.

The blueprint release fragment’s compatibility sentence currently says artifact writes and event projection are preserved without qualifying this refusal branch. It should clarify that normal representable execution preserves them while a rejected projection returns the typed refusal before final projection/state attachment. The support release fragment records `public_surface_inventory_reviewed = false`; the explicit 32-name facade was checked here and is unchanged, with no generated/API surface change found.

## P40 disposition and documentation proposal

The decomposition finding is the same class across the facade, helper-module, and intra-module levels: behavior and canonical seams must survive extraction. The owner injection, unchanged export signatures, importer census, ordered phase calls, and behavioral tests close that class; no second-level escape was found, so no widening or residual is proposed. The non-finite projection refusal is a distinct NEW class, with a live-path falsifier in the focused tests.

Suggested addition to the nodes README (not edited in this review):

> The policy-runtime support facade and registered blueprint node keep their canonical import paths. `builtins/decide/policy_runtime_support.py` owns the public runtime contracts and delegates artifact/evidence and metric implementation to adjacent helpers; `run_policy_blueprint_runtime.py` owns the registered node while adjacent helpers implement selection, benchmark admission, funnel execution, and reporting. Import consumers from the canonical facade or node module; helper modules are internal.

