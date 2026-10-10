# Native decomposition: `RunPolicyBlueprintRuntimeNode`

## Decision and boundary

Decompose the existing runtime in place while leaving the canonical class, `_SPEC`, import path, and module-level dependency aliases at `polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime`. The helpers receive the canonical module as their owner where the existing node/test contract monkeypatches module globals; this keeps those call sites late-bound. The workflow order remains input resolution → selection evaluation/persistence → benchmark and promotion evidence → funnel context → L0–L6 execution → final evidence/state/event projection.

Source base: commit `9e02a9f49c8b01026327a9f7c7e18711b13a96f2`, tree `881a950dccb7cdefacc636515aa7dd2bceadf928`. The candidate worktree was on that commit at entry. Other root/peer paths were already modified in the shared candidate and were left untouched.

The split is behavior-preserving. It introduces no thresholds, expiry/budget rules, authority changes, stage reordering, or new producer semantics. The currently shadowed local strategic-persistence implementation was unreachable because the later `_persist_runtime_strategic_artifacts` wrapper delegated to `c6c_runtime_support`; the dead duplicate was removed, and the effective wrapper remains exported at the canonical module path.

Pattern pass: P27/P31 apply because the canonical node is the single owner and a per-call-site rewrite would risk shimming it. P29/P38 apply because evidence is the real producer/importer tests and execution results, not module-name markers. P40 classification: decomposition is one complexity/ownership class; no second same-class escape was observed. The existing capability remains wired: the node produces persisted policy evaluation, benchmark/promotion evidence, work packets, and VOI reports; the workflow consumes them through the existing L0–L6 orchestrator; CAS and promotion-owner tests remain the behavioral controls. This change is internal and adds no public capability claim.

## Authorized footprint

- `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py` — canonical class/spec, stable aliases, and compact phase sequencing.
- `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_engine.py` — policy-runtime workflow engine, work-packet producer, session carrier, selection setup, and funnel advancement.
- `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_strategy.py` — candidate payload, calibration/correlation projections, and the effective strategic persistence wrapper.
- `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_benchmarks.py` — source-status and benchmark registration, phase D.4, evidence bundle, and funnel-context preparation.
- `src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_reporting.py` — stress report projection, funnel serialization, final evidence/state branch, and returned events.
- `tests/unit/scientist/nodes/builtins/decide/test_run_policy_blueprint_runtime.py` — canonical node identity and non-policy skip characterization.
- `release-fragments/unreleased/2026-10-09-scientist-blueprint-runtime-decomposition.toml` — internal release record.
- `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/blueprint-native-decomposition-9e02.md` — this decision and verification record.

`src/polisyos/scientist/nodes/README.md` is a required documentation companion owned by the root shared owner; it is not part of this writer's lease.

## API and consumer census

The canonical public class is still `RunPolicyBlueprintRuntimeNode`, with its canonical `__module__` path and original `_SPEC`. `_PolicyRuntimeWorkflowEngine` and `_resolve_replay_bundle_ref` also remain defined at their original canonical path because compliance audit policy names those FQNs. Existing direct imports remain at the canonical module for `_persist_policy_runtime_work_packet`, `_candidate_search_payload`, `_persist_runtime_strategic_artifacts`, `_resolve_policy_runtime_source_statuses`, `_merge_stress_test_reports`, `_run_and_register_phase_d4_challenge_suites`, `_serialize_funnel_outcome`, and the other helper aliases consumed by existing tests.

Existing consumers include `builtins/__init__.py`, `decide/__init__.py`, `scientist/orchestration/workflows/policy_design.py`, the compliance audit's canonical FQN checks, and the funnel Level 5 handoff documentation. Existing behavioral callers/tests include `test_policy_blueprint_runtime_guards.py`, `test_phase_d4_runtime_integration.py`, `test_policy_runtime_work_packets.py`, `test_fun_03.py`, and `test_phase_b_policy_runtime.py`. The new mirrored test invokes the actual `execute` method on its non-policy path.

## Verification

Before the source delta, the focused producer/consumer set collected 25 tests and returned 20 passed / 5 failed. The same command after extraction returned the same 20 passed / 5 failed, with the same failures: the strategic normalized-reference assertion differs only on `manifest_profile_sha256`, and four `test_fun_03` promotion cases reject the test fixture's non-finite `inf` while attaching `funnel_outcome` to the state journal. Since the complete target-module command was not replayed against the slice base with a zero changed-path intersection proof, P41 attribution is `not_established`; these are recorded as entry and post-delta reds rather than claimed inherited.

Complete command output is retained in `raw/baseline-focused-tests.txt` and `raw/post-refactor-focused-tests.txt`. The entry command collected 25 tests and returned 20 passed / 5 failed. The final command adds the new canonical-owner characterization and collected 26 tests, returning 21 passed / 5 failed / 2 warnings. All five failures match the entry failures: `test_runtime_strategic_helper_persists_normalized_contract_and_real_causal_component` differs on `manifest_profile_sha256`, and the four controlled `test_fun_03` cases reject the fixture's `inf` while attaching `funnel_outcome` to the state journal. No new failure appeared. Since the target-module command was not replayed against the slice base with zero changed-path intersection proof, P41 attribution remains `not_established`; these are not claimed inherited.

Two intervening attempts were non-product collection errors and remain retained: `raw/concurrent-support-wip-import-error.txt` records a peer's transient unleased import-order edit, and `raw/canonical-class-decorator-import-error.txt` records my temporary duplicate-decorator error while restoring canonical FQNs. Both were corrected before the final replay. The final characterization passed and asserts canonical `__module__` identities for the node, workflow adapter, and replay resolver. Configured Ruff, Ruff format check, py_compile, scoped diff check, and explicit Ruff C901 `max-complexity=12` pass on the final source; complete outputs are under `raw/`.

The final mechanism line counts are: canonical module 637; engine helper 384; strategy helper 165; benchmark helper 694; reporting helper 537. Each is below the 1,000-line cap, and the explicit C901-12 check passes across all five modules. The complexity registry and nearest README were left to their separate owners.
