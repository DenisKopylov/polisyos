# Foundry Frontier Methods

This page documents the WS-9 frontier additions that close the highest-value
catalog gaps after runtime hardening.

## What This Page Covers

The WS-9 surface adds runnable method families for:

- proximal causal inference with proxy-based latent-confounding adjustment;
- unconditional distributional treatment effects and QTE-style summaries;
- network-aware heterogeneous effects under interference;
- neural tabular and graph ML baselines for nuisance and representation work;
- mean-field and heterogeneous-shock policy simulation helpers;
- public-finance and policy-evaluation primitives, including a lightweight
  foundation-model policy analysis path.

These methods are exposed through the regular Foundry catalog and inherit the
same metadata, registry, dispatcher, and advisor surfaces as the rest of the
platform.

## Dependency-Ordered Coverage

| WS-9 sequence | Method surface | Primary FQNs |
|---------------|----------------|--------------|
| 1. Proximal causal inference | Proxy-based latent-confounding adjustment | `causal.proximal.proximal_bridge@1.0.0` |
| 2. SBI and neural nuisance bridge | Neural tabular/graph/self-supervised frontiers | `ml.deep.ft_transformer@1.0.0`, `ml.deep.tabnet@1.0.0`, `ml.graph.graph_conv@1.0.0`, `ml.self_supervised.masked_autoencoder@1.0.0` |
| 3. QTE / distributional causal effects | Transport-weighted unconditional QTE summaries | `causal.distributional.unconditional_qte@1.0.0` |
| 4. Interference and network-aware CATE | Heterogeneous direct effects with exposure spillovers | `causal.interference.network_cate@1.0.0` |
| 5. Mean-field / heterogeneous-shock agents | Aggregation and fixed-point policy simulators | `policy.agent_sim.mean_field_equilibrium@1.0.0`, `policy.macro.krusell_smith_lite@1.0.0` |
| 6. Policy macro and public finance | Sufficient-statistics welfare, multipliers, optimal tax, policy analysis | `policy.welfare.sufficient_statistics_welfare@1.0.0`, `policy.macro.fiscal_multiplier@1.0.0`, `policy.public_finance.optimal_linear_tax@1.0.0`, `policy.evaluation.foundation_model_policy_analysis@1.0.0` |

## Runtime Posture

- All WS-9 methods register through the normal lazy family bootstraps in
  `polisyos.foundry.methods.catalog.*`.
- The new causal and policy methods run on the NumPy stack by default so they
  remain available in lean environments.
- `foundation_model_policy_analysis` defaults to a TF-IDF embedder and upgrades
  to `sentence_transformer` only when that backend is explicitly requested and
  available.
- The frontier ML methods are intentionally documented as higher-cost,
  `frontier_trainable`-style surfaces rather than being presented as equivalent
  to low-risk production defaults.

## Runnable Example

The repository ships a lightweight walkthrough script:

- `tools/demos/run_foundry_ws9_frontier_demo.py`

Run it from the repo root:

```bash
python3 tools/demos/run_foundry_ws9_frontier_demo.py
```

The script exercises one causal, one ML, and one policy frontier method and
prints JSON-safe summaries that can be used as a smoke check during local
evaluation.

## Reference Modules

::: polisyos.foundry.methods.catalog.causal.frontier

::: polisyos.foundry.methods.catalog.ml.frontier

::: polisyos.foundry.methods.catalog.policy.frontier
