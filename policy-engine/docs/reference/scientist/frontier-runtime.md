# Scientist Frontier Runtime

Related reference: [Agent Search And Reasoning](agent-search-reasoning.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/orchestration/engine/frontier_runtime.py`, compatibility shim `src/polisyos/scientist/frontier_runtime.py`, `src/polisyos/scientist/methods/search/{benchmark_registry.py,registry_contracts.py}`, and `tests/unit/scientist/search/{test_frontier_runtime.py,test_benchmark_registry.py}`

> Phase 4 runtime contract for frontier capabilities. The default path stays
> conservative: frontier methods remain feature-flagged until offline validation
> and benchmark packs show they are safe to evaluate outside the baseline path.

## Capability Statuses

| Status                   | Meaning                                                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `disabled`               | The feature flag is off and the capability cannot affect runtime behavior.                                                        |
| `offline_gated`          | The capability is wired enough to run offline, but it is blocked until validation and benchmark refs are present.                 |
| `available_offline`      | The capability has the evidence required for offline evaluation, but it is still not eligible to replace the baseline by default. |
| `experimental_not_wired` | The contract surface exists, but the runtime wiring or evaluation support is still incomplete.                                    |

## Current Families

- Causal frontier methods:
  - proximal causal inference
  - Bayesian causal discovery
  - neural DAG learners
  - causal representation learning
- Search / governance frontier methods:
  - adversarial scenario discovery
  - continuous governance loop

## Rollout Contract

Every frontier capability must publish:

- a capability id
- a feature flag
- a module path
- a method or artifact identifier
- an offline validation reference
- a benchmark pack reference
- an explicit baseline-replacement posture
- a rationale explaining why the capability is still gated

## D1 Frontier Evidence Map

Phase 4 frontier work is documentation-visible but non-default by design. A
capability can move from `offline_gated` to `available_offline` only when both
validation and benchmark refs are present; baseline replacement still needs an
explicit approval flag.

| Capability family                   | Runtime field                                                    | Evidence required before claim                                                                                |
| ----------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Proximal causal inference           | `enable_proximal_causal`                                         | `offline_validation_ref`, `benchmark_pack_ref`, and causal eval tests that keep proxy assumptions visible.    |
| Bayesian or neural causal discovery | `enable_bayesian_causal_discovery`, `enable_neural_dag_learners` | Dedicated eval pack, calibrated posterior or structural-recovery diagnostics, and benchmark registry entry.   |
| Causal representation learning      | `enable_causal_representation_learning`                          | Latent-factor validation pack and benchmark evidence before it can affect default causal reports.             |
| Adversarial scenario discovery      | `enable_adversarial_scenario_discovery`                          | Challenge bundle and governance outcome comparison against the baseline stress set.                           |
| Continuous governance loop          | `enable_continuous_governance_loop`                              | Drift, calibration, fairness, reissue, and benchmark evidence tied to the governance accountability artifact. |

## Benchmark Requirement

Frontier claims must cite `polisyos.scientist.methods.search.benchmark_registry` or a
stored benchmark pack reference before they cite SOTA readiness. If
`benchmark_pack_ref` is missing, `FrontierRuntimeReport.default_enable_eligible`
must remain false even when a feature flag is enabled.

## Default-On Rule

Frontier methods are not allowed to become default-on merely because they are
implemented. They must remain behind a feature flag until:

1. Offline validation exists.
2. A benchmark pack exists.
3. Baseline replacement is explicitly approved.

## Source Of Truth

- Runtime report builder:
  `polisyos.scientist.orchestration.engine.frontier_runtime`
- Frontier benchmark registry: `polisyos.scientist.methods.search.benchmark_registry`
- Runtime promotion gate: `polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime`
- Tests: `tests/unit/scientist/search/test_frontier_runtime.py`
- Related acceptance surfaces: [phase4-acceptance.md](phase4-acceptance.md), [remediation-status.md](remediation-status.md)
