# Scientist Phase 3 Acceptance

Related references: [Causal validity bundle](causal-validity.md), [Governance accountability](governance-accountability.md), [Agent search and reasoning](agent-search-reasoning.md).

This page is the repo-tracked acceptance surface for Task 4 of
`SCIENTIST_AUDIT_REMEDIATION_PLAN.md`. The closure claim is intentionally
scoped: the default Scientist path is claim-closed, while non-default frontier
methods remain explicitly gated with machine-readable rollout statuses.

## Closure Matrix

| Workstream | Claim-closed surface | Machine-readable status |
|------------|----------------------|-------------------------|
| `WS-3A` | `scientist.causal_validity_bundle` persists shared confidence and sensitivity sections, plus ICP / proximal / recoverability / PAG diagnostics on the default path. | `payload["causal_validity"]["content"]["capability_matrix"]` and `payload["diagnostics_summary"]` keep experimental and skipped checks explicit. |
| `WS-3B` | `scientist.governance_accountability_artifact` unifies calibration, fairness, adaptive thresholds, tail risk, model card, datasheet, and escalation policy. | Threshold registry entries, `risk_weighted_verdict`, `requires_human_review`, and explicit missing-evidence gaps make governance posture auditable. |
| `WS-3C` | Agent/search evaluation is compared against the Reflexion-only baseline before any default enablement. | `ReasoningPolicyGate.status_for(...)`, `AdvancedSearchPolicyReport.rollout_status`, `AgentPolicyComparisonReport.rollout_status`, and `FrontierRuntimeReport.capabilities[*].status` make rollout posture explicit. |

## Comparative Evidence

| Surface | Evidence |
|---------|----------|
| Old vs new causal default path | [causal-validity-acceptance.md](causal-validity-acceptance.md) documents the pre/post surface and the synthetic plus semi-synthetic eval pack. |
| Governance accountability artifact | [governance-accountability.md](governance-accountability.md) documents the unified artifact contract and missing-evidence behavior. |
| Candidate vs Reflexion baseline | `compare_agent_eval_reports(...)` emits `AgentPolicyComparisonReport` with deltas, blockers, `offline_validation_ref`, and `rollout_status`. |
| Advanced search policy readiness | `build_advanced_search_policy_report(...)` emits `rollout_status`, offline-gate state, blockers, and capability-level statuses. |

## Regression Proof

- `tests/scientist/test_causal_evaluation_node.py`
- `tests/scientist/test_decision_packet_node_v3.py`
- `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py`
- `tests/scientist/governance/test_accountability.py`
- `tests/scientist/governance/test_calibration_validation.py`
- `tests/scientist/nodes/test_build_policy_output_bundle.py`
- `tests/ukraine_data/test_builders.py`
- `tests/scientist/agent/test_reasoning.py`
- `tests/scientist/agent/test_eval_harness.py`
- `tests/scientist/search/strategies/test_advanced_policy.py`
- `tests/scientist/test_frontier_runtime.py`

## Reproduce

```bash
uv run pytest tests/scientist/test_causal_evaluation_node.py -q
uv run pytest tests/scientist/test_decision_packet_node_v3.py -q
uv run pytest tests/foundry/methods/catalog/causal/test_validity_eval_pack.py -q
uv run pytest tests/scientist/governance/test_accountability.py tests/scientist/governance/test_calibration_validation.py -q
uv run pytest tests/scientist/nodes/test_build_policy_output_bundle.py tests/ukraine_data/test_builders.py -q
uv run pytest tests/scientist/agent/test_reasoning.py tests/scientist/agent/test_eval_harness.py tests/scientist/search/strategies/test_advanced_policy.py tests/scientist/test_frontier_runtime.py -q
```

## Claim Discipline

- Default-path causal, fairness, calibration, and reasoning claims are accepted only when the corresponding artifact/report exists.
- Missing evidence is surfaced as typed gaps or gated statuses, not silently filled in.
- Frontier methods that are still research-only remain explicitly non-default and non-claiming until a separate rollout approval lands.
