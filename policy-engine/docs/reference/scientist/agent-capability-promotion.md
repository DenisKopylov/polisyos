# Agent Capability Promotion

Related references: [Scientist](index.md), [Agent search and reasoning](agent-search-reasoning.md), [Deep research evidence](deep-research-evidence.md), [Frontier runtime](frontier-runtime.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/agent/runtime_capabilities.py`, `src/polisyos/scientist/agent/promotion.py`, `src/polisyos/scientist/agent/tool_contracts.py`, `src/polisyos/scientist/agent/supervisor_eval.py`, `src/polisyos/scientist/frontier_runtime.py`, `tests/unit/scientist/agent/test_promotion.py`, `tests/unit/scientist/agent/test_runtime_capabilities.py`, `tests/unit/scientist/agent/test_tool_contracts.py`, `tests/unit/scientist/agent/test_supervisor_eval.py`, and `tools/ci/check_scientist_best_in_class_phase1_4.py`

Phase 1.4 makes agentic runtime promotion a single read-only surface. It does
not turn on tree search, LATS, learned routing, learned VOI, supervisor swarms,
same-model fan-out, provider-native search, or deep research by default.

The report also emits typed `AgentPromotionCoverageRecord` entries so one
surface accounts for tool loop behavior, supervisor behavior, search,
Reflexion baseline comparisons, context/memory behavior and provider behavior:
`tool_loop`, `supervisor`, `search`, `reflexion`, `context_memory`,
`provider_behavior`. Missing context/memory and provider eval refs are surfaced
as `missing_context_memory_eval_ref` and `missing_provider_behavior_eval_ref`,
ready for later LLM/provider validation without calling those systems during
Phase 1.4 tests.

## Capability Registry

`AgentCapabilityId` is the stable list of agentic capability families that must
appear exactly once in every `AgentCapabilityPromotionReport`.

| Capability id | Default rule | Current owner | Initial frontier status |
| --- | --- | --- | --- |
| `tool_loop` | default only with transcript/order/schema tests | `agent/tools/tool_loop.py`, `agent/tools/registry.py` | `offline_gated` |
| `supervisor_worker` | shadow first, then offline validated | `agent/supervisor.py`, `agent/workers.py` | `offline_gated` |
| `deep_research_subgraph` | non-default until citation/faithfulness evals pass | `scientist/evidence/**`, Scholar search tools | `offline_gated` |
| `tree_of_thought` | offline-gated until lift beats baseline | `agent/reasoning.py`, `agent/eval_harness.py` | `offline_gated` |
| `lats_mcts` | offline-gated until lift beats baseline | `agent/reasoning.py`, `agent/eval_harness.py` | `offline_gated` |
| `learned_routing` | shadow only until calibration and regret tests pass | `search/strategies/advanced_policy.py` | `experimental_not_wired` |
| `learned_voi` | shadow only until calibration and regret tests pass | `search/strategies/advanced_policy.py` | `experimental_not_wired` |
| `same_model_fanout` | allowed only with budget + citation + consistency checks | `agent/supervisor.py`, `agent/workers.py` | `offline_gated` |

The registry is static and does not inspect feature flags. Runtime rollout is
reported by `AgentCapabilityPromotionReport`.

## Promotion Report

`AgentCapabilityPromotionReport` covers all capability ids and uses
`FrontierCapabilityStatus` as the rollout vocabulary. Report-level promotion
evidence uses typed `ArtifactRef` values:

- `offline_validation_ref`;
- `benchmark_pack_ref`;
- capability-specific eval refs such as supervisor handoff, citation
  faithfulness, budget, and consistency evidence.

Free-form strings from older reports can be read as input context, but they do
not unlock default enablement in the Phase 1.4 report.

Default enablement is target-specific. A report may cover all capabilities while
requesting default enablement for only `tool_loop`, for example. Requested
capabilities are named in `default_enable_capability_ids`; non-requested
capabilities remain visible with their blockers but do not block that specific
promotion decision.

## Evidence Inputs

Phase 1.4 reads existing surfaces instead of replacing them:

| Input | Role in promotion |
| --- | --- |
| `ToolContractSummary` | Checks JSON Schema shape, response caps, timeout policy and structured tool errors. |
| `SupervisorPromotionEvaluation` | Checks handoff eval refs, delegation success, quorum consistency, citation coverage and budget violations. |
| `AgentPolicyComparisonReport` | Compares candidate reasoning/search behavior against the Reflexion-only baseline. |
| `ReasoningPolicyGate` | Keeps `tree_of_thought` and `lats_mcts` offline-gated until an explicit trajectory eval exists. |
| `AdvancedSearchPolicyReport` | Records learned routing and learned VOI rollout posture; both remain shadow-only in Phase 1.4. |
| Deep research/citation refs | Gate `deep_research_subgraph` until source support and faithfulness evals exist. |

## Default-Enable Rules

- Missing `offline_validation_ref` blocks default enablement.
- Missing `benchmark_pack_ref` blocks default enablement.
- `tool_loop` is blocked by open tool schemas, missing response caps, missing
  timeout policy, or missing structured error taxonomy.
- `supervisor_worker` is blocked without a supervisor handoff eval.
- `deep_research_subgraph` is blocked without both deep-research and
  citation/faithfulness eval refs.
- `tree_of_thought` and `lats_mcts` are blocked without a `ReasoningPolicyGate`
  and a passing comparative policy report.
- `learned_routing` and `learned_voi` remain shadow-only until calibration and
  regret tests are promoted in a later phase.
- `same_model_fanout` is blocked without budget and citation-consistency evals.

## Frontier Projection

`project_agent_promotion_to_frontier_statuses(...)` returns a map from every
`AgentCapabilityId` to `FrontierCapabilityStatus`.
`summarize_agent_promotion_frontier_status(...)` gives dashboards a single
frontier-compatible summary status without importing the agent package.

## Validation

```bash
uv run pytest tests/unit/scientist/agent/test_runtime_capabilities.py tests/unit/scientist/agent/test_tool_contracts.py tests/unit/scientist/agent/test_supervisor_eval.py tests/unit/scientist/agent/test_promotion.py -q
uv run python tools/ci/check_scientist_best_in_class_phase1_4.py --require-passing
```
