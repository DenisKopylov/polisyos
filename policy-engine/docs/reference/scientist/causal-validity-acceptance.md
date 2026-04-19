# Scientist WS-3A Acceptance Report
Related reference: [Causal validity bundle](causal-validity.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/causal/**`, `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`, and the cited Scientist/Foundry regression tests on this page

This report is the repo-tracked acceptance surface for WS-3A claim closure on
the default Scientist path. Instead of a notebook-only artifact, the acceptance
evidence is expressed as deterministic tests plus a concise comparison of the
old and new default paths.

## Old vs New Default Path

| Surface | Before WS-3A | After WS-3A claim-closed default path |
|--------|---------------|----------------------|
| Default causal output | primary `CausalEffectReport` and uncertainty envelope | primary report + envelope + optional sensitivity artifact + `scientist.causal_validity_bundle` |
| Sensitivity visibility | method-local / optional metadata | explicit `decision_packet.payload["sensitivity"]` section |
| Confidence visibility | estimator-specific only | shared `confidence` surface in causal-validity bundle |
| Selection-bias / graph checks | not surfaced on default path | recoverability and PAG refinement statuses recorded when inputs exist |
| Multi-domain diagnostics | not surfaced on default path | ICP invariance status recorded when domain labels exist |
| Frontier posture | implicit gaps | capability matrix marks unsupported items as `experimental_not_wired` |

## Eval Pack

The baseline eval pack is intentionally small but CI-friendly:

| Dataset family | Coverage | Evidence |
|---------------|----------|----------|
| Synthetic binary-treatment confounding | E-values, Rosenbaum gamma, benchmarked sensitivity summary | `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py::test_ws3a_synthetic_sensitivity_eval_pack_reports_robust_effect` |
| Synthetic multi-domain invariance | ICP-style invariance stability on a domain-stable mechanism | `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py::test_ws3a_synthetic_icp_eval_pack_accepts_stable_domains` |
| Semi-synthetic latent-confounding with proxies | proximal bridge estimate with finite interval and strong proxy diagnostics | `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py::test_ws3a_semi_synthetic_proximal_eval_pack_yields_finite_interval` |

Additional regression evidence for default-path orchestration and decision
artifacts:

- `tests/scientist/test_causal_evaluation_node.py`
- `tests/scientist/test_decision_packet_node_v3.py`
- `tests/scientist/backtesting/test_distributional.py`
- `tests/foundry/methods/catalog/causal/test_treatment_effects.py`

## Statistical Correctness Hotfixes Included

- sensitivity metrics now surface E-values and explicit robustness summaries on
  the default decision path
- honest-HTE confidence metadata is preserved in the causal-validity bundle for
  forest estimators
- IPW now reports a Hajek-centered estimate with influence-based interval
  diagnostics instead of the old fragile HT-only path
- Ljung-Box diagnostics now compute a p-value rather than relying on a rough
  threshold heuristic
- bootstrap CI helpers now ignore non-finite draws and reject empty effective
  samples

## How To Reproduce

```bash
uv run pytest tests/scientist/test_causal_evaluation_node.py -q
uv run pytest tests/scientist/test_decision_packet_node_v3.py -q
uv run pytest tests/scientist/backtesting/test_distributional.py -q
uv run pytest tests/foundry/methods/catalog/causal/test_treatment_effects.py -q
uv run pytest tests/foundry/methods/catalog/causal/test_validity_eval_pack.py -q
```

## Explicit Experimental Statuses

These capabilities remain intentionally marked experimental in the
`capability_matrix` so the runtime can be honest about what is still gated:

- anchor regression
- Bayesian causal discovery
- neural causal discovery
- causal representation learning

That means WS-3A is claim-closed on the default path while still making the
non-default frontier backlog explicit and non-claiming.
