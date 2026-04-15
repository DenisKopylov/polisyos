# Scientist Agent Search And Reasoning
Related reference: [Workflows](workflows.md), [Reliability scorecard](reliability-scorecard.md).

WS-3C adds an offline-gated search-and-reasoning framework around the existing
Scientist DAG executor and Reflexion baseline. The intent is to make advanced
reasoning available for evaluation without silently turning expensive or
experimental policies on by default.

## Agent Reasoning

The supervisor/worker contour now executes planned worker envelopes as a
dependency DAG. `WorkerTaskEnvelope.depends_on_task_ids` is converted into
topological tiers through the shared Scientist DAG sorter, then each tier runs
under the existing bounded semaphore. Downstream workers are blocked with typed
dependency errors when an upstream worker fails or is missing.

`polisyos.scientist.agent.reasoning` exposes two deterministic trajectory
surfaces:

- `TreeOfThoughtPlanner` runs bounded beam search over structured
  `ReasoningAction` expansions.
- `LATSAgentSearch` runs a lightweight LATS / MCTS loop over agent actions.

Both return `ReasoningSearchReport` with:

- gate status;
- selected action path;
- node-level scores, visits, and value means;
- bounded node counts and depth metrics.

By default both policies return `offline_gated`. They require
`ReasoningPolicyGate(enabled=True, offline_validation_ref=...)` before they run.

## Optimization Policies

`polisyos.scientist.search.strategies.advanced_policy` provides the WS-3C policy
toolkit:

- `ASHAScheduler` for asynchronous successive halving;
- `BOHBSampler` for BOHB-style elite resampling;
- `CMAESExplorer` for bounded evolutionary exploration;
- `GaussianProcessCheapStageSurrogate` as a dependency-light RBF surrogate;
- `LearnedVOIPolicy` and `LearnedRoutingPolicy` for offline-trained routing;
- `ExplicitConstraintPropagator` for blocker/warning constraints before
  expensive stages;
- `PopulationBasedTrainingScheduler` for exploit/explore search updates.

`AdvancedSearchPolicyConfig` and `build_advanced_search_policy_report(...)`
make offline gating explicit. Experimental policies require an
`offline_validation_ref` before they are eligible for default enablement.

## Evaluation Harness

`polisyos.scientist.agent.eval_harness` now includes
`compare_agent_eval_reports(...)`, which compares a candidate policy against the
current Reflexion-only baseline. Default enablement requires:

- candidate release gates pass;
- candidate lift is non-negative or above configured threshold;
- a persisted offline validation artifact is referenced.

This produces `AgentPolicyComparisonReport`, the handoff artifact expected by
runtime config reviews. The report now carries an explicit `rollout_status`
(`offline_gated`, `release_gated`, or `default_enable_eligible`) so rollout
posture stays machine-readable instead of being inferred from booleans alone.

`build_advanced_search_policy_report(...)` also exposes an explicit
`rollout_status` (`baseline_only`, `offline_gated`, or
`default_enable_eligible`) for the BOHB/ASHA/CMA-ES/learned-routing bundle.

## Current Default Policy

The default runtime policy remains conservative:

- Reflexion and existing DAG-backed supervisor/worker orchestration are allowed;
- Tree-of-Thought and LATS/MCTS are offline-gated;
- BOHB, ASHA, CMA-ES, learned VOI/routing, GP surrogates, and PBT are
  available as configurable policies but not default-on.

## Regression Evidence

Primary regression coverage lives in:

- `tests/scientist/agent/test_reasoning.py`
- `tests/scientist/agent/test_eval_harness.py`
- `tests/scientist/agent/test_supervisor.py`
- `tests/scientist/search/strategies/test_advanced_policy.py`
- `tests/scientist/search/strategies/test_controller_batch.py`
