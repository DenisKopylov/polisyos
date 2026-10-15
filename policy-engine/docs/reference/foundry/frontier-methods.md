# Foundry Frontier Methods

This page maps frontier method families to catalog surfaces. Historical Phase
5/6 labels below are planning vocabulary, not release or capability statuses.
A frontier method can be registered and runnable while still carrying higher
operational cost, optional dependencies, or research-gated interpretation.

Historical freshness receipt: 2026-04-17 (an earlier documentation pass; not a
current verification receipt).
Owner: @foundry-owners
Historical planning context: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md` and the D1-L3 section of `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`.
Source of truth: `src/polisyos/foundry/methods/catalog/causal/frontier.py`, `src/polisyos/foundry/methods/catalog/ml/frontier.py`, `src/polisyos/foundry/methods/catalog/policy/frontier.py`, and `src/polisyos/foundry/methods/catalog/bayesian/frontier.py`.
Source inspection pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`.
Evidence level: implementation and listed test/demo sources were inspected at this pin; tests and demos were not run for this docs-only review.

Registry membership, method-specific tests, and the smoke demo establish only
their bounded method contracts. They do not compose an end-to-end policy
design, ground a predicted effect in observed outcomes, or authorize a
recommendation. See [Causal Engine](../../explanation/causal-engine.md) for the
implemented design-composition and grounding boundaries.

## Phase Coverage

| Historical plan label | Frontier meaning                                                                                                                                                                  |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 5               | Bayesian, UQ, and calibration frontier: posterior sampling and SBI are tracked in ADRs and catalog metadata; this page does not claim production HMC/NUTS beyond source evidence. |
| Phase 6               | Causal, ML, agent-sim, and policy frontier: catalog and smoke-demo surfaces have their own bounded registration, dispatch, and test contracts.                                    |

## Currently Exercised Frontier Coverage

This table is selective by design: it lists frontier rows with direct demo or
test anchors, not every frontier-tagged entry currently present in the method
snapshot.

| Sequence                                   | Method surface                                                           | Primary FQNs                                                                                                                                                                                               |
| ------------------------------------------ | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Proximal causal inference               | Proxy-based latent-confounding adjustment                                | `causal.proximal.proximal_bridge@1.0.0`                                                                                                                                                                    |
| 2. SBI and neural nuisance bridge          | Neural tabular, graph, and self-supervised frontiers                     | `ml.deep.ft_transformer@1.0.0`, `ml.deep.tabnet@1.0.0`, `ml.graph.graph_conv@1.0.0`, `ml.self_supervised.masked_autoencoder@1.0.0`                                                                         |
| 3. QTE / distributional effects            | Transport-weighted unconditional QTE summaries                           | `causal.distributional.unconditional_qte@1.0.0`                                                                                                                                                            |
| 4. Interference and network-aware CATE     | Heterogeneous direct effects with exposure spillovers                    | `causal.interference.network_cate@1.0.0`                                                                                                                                                                   |
| 5. Mean-field / heterogeneous-shock agents | Aggregation and fixed-point policy simulators                            | `policy.agent_sim.mean_field_equilibrium@1.0.0`, `policy.macro.krusell_smith_lite@1.0.0`                                                                                                                   |
| 6. Policy macro and public finance         | Sufficient-statistics welfare, multipliers, optimal tax, policy analysis | `policy.welfare.sufficient_statistics_welfare@1.0.0`, `policy.macro.fiscal_multiplier@1.0.0`, `policy.public_finance.optimal_linear_tax@1.0.0`, `policy.evaluation.foundation_model_policy_analysis@1.0.0` |

## Runtime Posture

- Frontier methods register through the normal lazy bootstraps in
  `polisyos.foundry.methods.catalog.*`.

- NumPy-backed frontier methods are preferred for lean local environments unless
  the method explicitly declares a heavier backend.

- `foundation_model_policy_analysis` defaults to a lightweight TF-IDF path and
  uses a sentence-transformer backend only when requested and available.

- Frontier ML rows should keep `frontier_trainable` or equivalent metadata when
  they are trainable/high-cost surfaces.

- Bayesian frontier claims should link to runtime tests or ADRs; until a
  production sampler is available, docs should not describe Bayesian passthrough
  behavior as production posterior inference.

## Runnable Demo

The lightweight Phase 6 smoke demo exercises one causal, one ML, and one policy
frontier method:

```bash
uv run polisyos-tools demos run-foundry-ws9-frontier-demo
```

The script is covered by
`tests/e2e/demos/test_run_foundry_ws9_frontier_demo.py`.

## Evidence Links

- Causal frontier tests:
  `tests/unit/foundry/methods/catalog/causal/test_frontier_methods.py`

- ML frontier tests:
  `tests/unit/foundry/methods/catalog/ml/test_frontier.py`

- Policy frontier tests:
  `tests/unit/foundry/methods/catalog/policy/test_frontier.py`

- Bayesian method tests:
  `tests/unit/foundry/methods/catalog/bayesian/test_methods.py`

- NumPyro Bayesian SCM ADR:
  [`docs/adr/0074-numpyro-bayesian-scm.md`](../../adr/0074-numpyro-bayesian-scm.md)

## Reference Modules

::: polisyos.foundry.methods.catalog.causal.frontier

::: polisyos.foundry.methods.catalog.ml.frontier

::: polisyos.foundry.methods.catalog.policy.frontier

::: polisyos.foundry.methods.catalog.bayesian.frontier
