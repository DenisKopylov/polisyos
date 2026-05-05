# Foundry Frontier Methods

This page maps the Phase 5 and Phase 6 frontier tracks from the Foundry
remediation plan to current catalog surfaces. It is intentionally explicit
about runtime posture: a frontier method can be shipped and still carry higher
operational cost, optional dependencies, or research-gated interpretation.

Freshness: 2026-04-17
Owner: `@foundry-owners`
Source plan: `docs/plans/active/FOUNDRY_REMEDIATION_PLAN.md`, D1-L3 section in `docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/foundry/methods/catalog/causal/frontier.py`, `src/polisyos/foundry/methods/catalog/ml/frontier.py`, `src/polisyos/foundry/methods/catalog/policy/frontier.py`, `src/polisyos/foundry/methods/catalog/bayesian/frontier.py`, linked tests, and the frontier demo script

## Phase Coverage

| Source phase | Frontier meaning                                                                                                                                                                         |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 5      | Bayesian, UQ, and calibration frontier: posterior sampling and SBI are tracked in ADRs and catalog metadata; current docs do not claim production HMC/NUTS beyond shipped code evidence. |
| Phase 6      | Causal, ML, agent-sim, and policy frontier: runnable catalog additions live behind normal registry, dispatcher, tests, and demo commands.                                                |

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
