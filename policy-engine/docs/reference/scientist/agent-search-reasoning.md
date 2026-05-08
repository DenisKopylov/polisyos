# Scientist Agent Search And Reasoning

Related references: [Workflows](workflows.md), [Reliability scorecard](reliability-scorecard.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/agent/reasoning.py`, `src/polisyos/scientist/agent/eval_harness.py`, `src/polisyos/scientist/methods/search/strategies/advanced_policy.py`, `tests/unit/scientist/agent/test_reasoning.py`, `tests/unit/scientist/agent/test_eval_harness.py`, and `tests/unit/scientist/search/strategies/test_advanced_policy.py`

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/agent/reasoning.py`, `src/polisyos/scientist/agent/eval_harness.py`, `src/polisyos/scientist/methods/search/strategies/advanced_policy.py`, `tests/unit/scientist/agent/test_reasoning.py`, `tests/unit/scientist/agent/test_eval_harness.py`, and `tests/unit/scientist/search/strategies/test_advanced_policy.py`.

This page documents the optional L6 reasoning/search rollout surface. These
capabilities do not become part of the default Scientist runtime just because
the classes exist; rollout posture is encoded directly in their report models.

## Tree Reasoning Surface

`polisyos.scientist.agent.reasoning` currently exposes:

| Symbol                  | Current role                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| `ReasoningPolicyGate`   | Feature gate for tree reasoning.                                                               |
| `TreeOfThoughtPlanner`  | Deterministic beam-search planner over `ReasoningAction`s.                                     |
| `LATSAgentSearch`       | Deterministic lightweight LATS/MCTS search over structured actions.                            |
| `ReasoningSearchReport` | Persistable trajectory report with gate state, selected path, node stats, and bounded metrics. |

## Default Reasoning Posture

`ReasoningPolicyGate()` defaults to:

- `enabled=False`
- `offline_validation_ref=None`
- `allowed_modes={"tree_of_thought", "lats_mcts"}`

That means both `TreeOfThoughtPlanner` and `LATSAgentSearch` return
`ReasoningStatus.OFFLINE_GATED` unless the gate is both enabled and backed by
an `offline_validation_ref`.

## Advanced Search Policy Surface

`polisyos.scientist.methods.search.strategies.advanced_policy` currently exposes the
WS-3C policy toolkit:

- `ASHAScheduler`
- `BOHBSampler`
- `CMAESExplorer`
- `GaussianProcessCheapStageSurrogate`
- `LearnedVOIPolicy`
- `LearnedRoutingPolicy`
- `ExplicitConstraintPropagator`
- `PopulationBasedTrainingScheduler`

These are summarized through `AdvancedSearchPolicyConfig` and
`build_advanced_search_policy_report(...)`.

## Current Rollout Semantics

### `AgentPolicyComparisonReport`

`compare_agent_eval_reports(...)` produces:

| Rollout status            | Current meaning                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------- |
| `offline_gated`           | Missing `offline_validation_ref`, regardless of candidate quality.                  |
| `release_gated`           | Offline validation ref exists, but release-gate thresholds or candidate lift fail.  |
| `default_enable_eligible` | Offline validation ref exists and the candidate passes the release-gate thresholds. |

Release-gate thresholds currently come from `AgentReleaseGateConfig` defaults:

| Metric                       | Default threshold |
| ---------------------------- | ----------------: |
| `task_success_rate`          | `>= 1.0`          |
| `citation_coverage`          | `>= 0.85`         |
| `search_precision_proxy`     | `>= 0.60`         |
| `invalid_tool_call_rate`     | `<= 0.0`          |
| `reflexion_recovery_rate`    | `>= 0.50`         |
| candidate lift over baseline | `>= 0.0`          |

### `AdvancedSearchPolicyReport`

`build_advanced_search_policy_report(...)` currently distinguishes:

| Rollout status            | Current meaning                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------- |
| `baseline_only`           | No experimental search policy is requested; only baseline-safe `constraint_propagation` may be enabled. |
| `offline_gated`           | At least one experimental policy is requested without the required offline validation gate.             |
| `default_enable_eligible` | Experimental policy requested and the offline gate is satisfied.                                        |

Important nuance: `constraint_propagation` is enabled by default in
`AdvancedSearchPolicyConfig`, but it does not by itself promote the rollout
status beyond `baseline_only`.

## Starter Eval Harness

`run_starter_eval_harness(...)` currently builds a local proxy suite over four
case families:

- `tool_calling`
- `search`
- `swarm`
- `reflexion`

An optional `provider_contract` case is added only when live-provider smoke
verification is requested.

## What Is Default Today

| Surface                                                                   | Current default                                                                                                      |
| ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Reflexion / existing agent orchestration                                  | Available.                                                                                                           |
| Tree-of-Thought                                                           | Offline-gated.                                                                                                       |
| LATS/MCTS                                                                 | Offline-gated.                                                                                                       |
| BOHB / ASHA / CMA-ES / learned VOI / learned routing / GP surrogate / PBT | Available as configurable policies, but not default-on.                                                              |
| Explicit constraint propagation                                           | Enabled in the advanced-policy config, but treated as baseline-safe rather than a default-on experimental promotion. |

## Validation

```bash
uv run pytest tests/unit/scientist/agent/test_reasoning.py tests/unit/scientist/agent/test_eval_harness.py -q
uv run pytest tests/unit/scientist/agent/test_supervisor.py tests/unit/scientist/search/strategies/test_advanced_policy.py tests/unit/scientist/search/strategies/test_controller_batch.py -q
```
