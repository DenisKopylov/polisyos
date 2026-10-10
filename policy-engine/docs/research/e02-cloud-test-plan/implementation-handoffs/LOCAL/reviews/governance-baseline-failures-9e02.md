# Governance baseline failures at 9e02a9f

## Classification first

**P40 bucket: SAME class, deeper downstream consumers.** The five red assertions are not five independent policy-rule defects. They are separate real consumer paths that all depend on one shared Core-CAS-to-IR-store bridge. The second and later examples widen the required mechanism to the shared optional-artifact resolver; they do not justify another per-pass patch or weakening test expectations. The one-in-memory-boundary counterfactual below is the falsifier: adapting the pass context store made all five existing scenarios pass while keeping their expected policy outcomes unchanged.

This is an **actual runtime bridge defect**, not evidence of missing fixture fields, a stale normative expectation, or an intended new governance rule. Independent code assessment only; no formal G acceptance or closure is claimed.

## Evidence boundary

Reviewed source: commit `9e02a9f49c8b01026327a9f7c7e18711b13a96f2`, tree `881a950dccb7cdefacc636515aa7dd2bceadf928`. The worktree was at that exact HEAD when the baseline suite ran. The six test files in the command below still have no diff from that commit. The shared worktree has since acquired declared peer edits to `run_governance.py`, `run_normative_arbitration.py`, and `resolve_transport.py`, plus other unrelated work. Those later working-tree contents are not the 9e02 baseline and were excluded from this diagnosis; no current incomplete peer file is treated as a baseline defect.

The complete baseline output and command are retained at:

- [`raw/governance-baseline-9e02/focused-tests.log`](raw/governance-baseline-9e02/focused-tests.log), SHA-256 `e8b3a19c113a7d44cc2b8b49d4e6ff7f0ffa9ca40d7c6a84a19aa58922c1c60d`
- [`raw/governance-baseline-9e02/focused-tests.command.txt`](raw/governance-baseline-9e02/focused-tests.command.txt), SHA-256 `34a115941935fceac082cae91ab9b37fb45f1473934a4b4a50afb29cf68b2879`
- [`raw/governance-baseline-9e02/focused-tests.exit.txt`](raw/governance-baseline-9e02/focused-tests.exit.txt), exit `1`, SHA-256 `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`
- [`raw/governance-baseline-9e02/ir-store-adapter-counterfactual.log`](raw/governance-baseline-9e02/ir-store-adapter-counterfactual.log), SHA-256 `91661bd217b773d78f68b126b410a37cd4b193a279245abb8d4e83dcc4b3f461`

Command, from `policy-engine/` with that checkout's `.venv`:

```text
PYTHONPATH=src .venv/bin/python -m pytest -q --tb=short tests/unit/scientist/nodes/test_normative_arbitration_node.py tests/unit/scientist/nodes/test_run_governance_normative.py tests/unit/scientist/nodes/builtins/governance/test_run_governance_claims.py tests/integration/test_human_gate_audit.py tests/unit/scientist/governance/human_review/test_governance_integration.py tests/unit/runtime/quality/test_workspace_spine_repair_gates.py
```

Result: 32 collected, **5 failed / 27 passed**, exit 1. Two Python 3.14 Torch deprecation warnings were also emitted. Exact failure names and assertions are in the raw log.

## What fails and why

1. `test_run_governance_rejects_on_explicit_normative_right_violation` expects `reject`, receives `needs_revision`.
2. `test_run_governance_marks_needs_revision_when_policy_prefers_baseline` does not receive `NORMATIVE_POLICY_REJECTS_PROPOSAL`.
3. `test_run_governance_keeps_warning_only_for_partial_model_when_proposal_selected` does not receive `NORMATIVE_MODEL_PARTIAL`.
4. `test_run_governance_strict_literature_blocker_rejects_and_requests_review` expects `human_gate`, receives `reject`.
5. `test_run_governance_strict_transportability_passes_after_transport_node` expects `approve`, receives `reject`.

At `src/polisyos/scientist/nodes/builtins/governance/run_governance.py:1042-1063`, `_run_governance_checks` builds `PassContext.state` with `"_store": ctx.store`, the raw Core CAS. In the exact source, `src/polisyos/scientist/governance/passes/_artifact_resolution.py:81-94` retrieves that value and passes it directly to `load_model(store, normalized_ref)` without an IR adaptation. Its callers include:

- normative result: `passes/normative_arbitration_pass.py:148-162`;
- human-review causal graph: `passes/human_review_pass.py:85-99`;
- refutation causal report: `passes/refutation_pass.py:120-134`;
- SUTVA causal report: `passes/sutva_check_pass.py:117-131`;
- also cross-graph profile and distributional report through `passes/cross_graph_evidence_pass.py:185-199` and `passes/equity_pass.py:141-160`.

The adapter contract is explicit: `src/polisyos/core/artifacts/ir_adapter.py:337-346` defines `ensure_ir_artifact_store()` to wrap Core stores for IR reads. Other exact-source governance consumers already use it at the point of IR loading: `passes/literature_gate_pass.py:134,160`, `passes/strategic_response_pass.py:337`, and `passes/transportability_required_pass.py:232,256,338`. The shared resolver omits the same bridge.

The fixtures are real persisted artifacts, not constructor-only models. The normative tests call `persist_normative_arbitration_result(_ensure_ir_artifact_store(store), ...)` and place its returned typed reference in `artifacts_index` (`tests/unit/scientist/nodes/test_run_governance_normative.py:203-226`). The literature integration case similarly persists a causal graph through the adapter and passes the returned ref into `RunGovernanceNode` (`tests/integration/test_human_gate_audit.py:133-158`). The transport integration case runs the real `RunTransportabilityNode`, verifies `status == "ok"`, then runs governance against its returned state (`test_human_gate_audit.py:294-301`). The selected typed evidence is present; the governance artifact consumer cannot load it through the raw store.

The observed downstream effects fit this one failure class: normative evidence is treated as invalid/missing so its rule-specific findings disappear; the strict literature gate cannot resolve the graph and does not request review; strict refutation/SUTVA consumers treat the causal report as invalid and the run rejects. A diagnostic from the baseline run recorded the loader exception as `AttributeError: 'dict' object has no attribute 'hex'`; the more important evidence is the source-level interface mismatch plus the discriminating counterfactual, not that exception string alone.

## Distinguishing counterfactual

Without changing files, I loaded the exact 9e02 `run_governance.py` and `resolve_transport.py` source into the process, then wrapped the runtime pipeline validation boundary to replace only `PassContext.state["_store"]` with `ensure_ir_artifact_store(raw_core_store)` for validation and restore the original state afterward. The unchanged test functions then produced:

```text
explicit-right reject ['NORMATIVE_RIGHT_VIOLATION', 'NORMATIVE_POLICY_REJECTS_PROPOSAL', 'claim_ledger_owner_not_established']
baseline-preference needs_revision ['NORMATIVE_POLICY_REJECTS_PROPOSAL', 'claim_ledger_owner_not_established']
partial-model approve ['NORMATIVE_MODEL_PARTIAL', 'claim_ledger_owner_not_established']
test_run_governance_strict_literature_blocker_rejects_and_requests_review PASS
test_run_governance_strict_transportability_passes_after_transport_node PASS
probe_exit=0
```

This is an actual producer → persisted CAS artifact → governance consumer test path. It falsifies “bad fixture” and “outdated expected assertion” explanations. The adapter wrapper was an in-process diagnostic, not a source patch or final verification of a committed repair.

## Repair boundary and required confirmation

Keep the shared `PassContext.state["_store"]` a Core store. It is also consumed by Core-oriented code: `passes/confidence_pass.py:272-278`, `passes/incentive_compatibility_pass.py:86-90`, and `scientist/governance/calibration.py:571-583` use the raw CAS surface; replacing `_store` globally with an IR wrapper risks changing that contract. The narrowest class-level correction is in `_artifact_resolution.py`: adapt the retrieved Core store immediately before invoking the generic IR `load_model` callback, using the established `ensure_ir_artifact_store` bridge. This fixes all helper callers at the common boundary and leaves Core-only consumers untouched. If the implementation chooses another boundary, it must preserve this same split and demonstrate it with real loaders.

After the repair is committed/frozen, rerun the exact six-file command above. Existing focused files for the six helper consumers are `tests/unit/scientist/governance/test_normative_arbitration_pass.py`, `test_human_review_pass.py`, `test_refutation_pass.py`, `test_sutva_check_pass.py`, `test_cross_graph_evidence_pass.py`, and `test_equity_pass.py`; the normative/human/refutation/SUTVA unit cases mainly cover invalid refs, so add valid persisted-ref positive coverage or rely on/extend the real `RunGovernanceNode` tests in `tests/unit/scientist/nodes/test_run_governance_normative.py` and `tests/integration/test_human_gate_audit.py`. Keep representative Core-only pass tests green, especially `tests/unit/scientist/governance/test_confidence_pass.py` or `test_confidence_issue_accumulation.py`, `test_incentive_compatibility_pass.py`, and `test_calibration_validation.py`. The positive test must assert consumed semantic output (normative finding, human-gate request, or strict verdict), not merely adapter presence or field markers. No full-suite, native, or heavy-fit run was part of this review.

## Independent verdict

The 9e02 baseline has a confirmed, material runtime artifact-bridge bug with high confidence. The specification/semantic expectations in the five red tests are supported by the persisted fixtures and the counterfactual. The code-quality repair target is the shared generic resolver boundary, not five expectation changes or a global store replacement. Formal G acceptance remains unadjudicated.
