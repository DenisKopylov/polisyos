# GY Foundry Breadth Audit Findings

Date: 2026-06-14
Scope: one representative direct Foundry method smoke per top family in the `172` pinned route-relevant envelope. This is explicitly separate from DAG-consumed truth.

## Method

The audit used the real `MethodRegistry` and `ensure_all_methods_registered()`, then invoked selected methods as:

```python
registry.get(fqn).pure_step(state, params)
```

No agents and no network fetches were used. Evidence is captured in `_build/.tmp/gy0-foundry-breadth/direct_family_smokes.json`.

## Registry And Route Envelope

The old census count is reproducible as a pinned-route filter, not as a broad metadata query.

| Envelope | Count | Families |
| --- | ---: | --- |
| Builtin registry, excluding dev-scan example | 389 | 17 top families |
| Live registry, including dev-scan example | 390 | builtin + `example` |
| Pinned route-relevant filter | 172 | `causal=151`, `forecasting=10`, `validation=4`, `ml=5`, `econometrics=1`, `survey=1` |
| Broad tag envelope | 232 | adds `bayesian=19`, broader `econometrics=26`, `microsim=6`, broader `ml=15` |

The route-relevant `172` should therefore remain a named curated filter: top family `causal` / `forecasting` / `validation`, exact family `ml.uncertainty`, exact tag `causal`, or method-name token `causal`.

## Direct Smokes

All six representative direct smokes passed.

| Family | Method | Result | Hash |
| --- | --- | --- | --- |
| causal | `causal.bounds.manski@1.0.0` | bounds emitted, `n_obs=40` | `sha256:51805880a4682c2bf1e68f0c49ad1e0e3ffc71e9026f5380bd9acce1559bdb65` |
| forecasting | `forecasting.univariate.theta@1.0.0` | forecast + uncertainty bundle emitted | `sha256:892aa0cceafcb09779551d3e93dfb8aae28bbd409b2ebd1420807d15779fbee5` |
| ml | `ml.uncertainty.conformal_prediction@1.0.0` | interval result, coverage `1.0` | `sha256:118ea4f1ad3ced65e4b439087039c5428f514f2d92fd434ac4fc45c42d85a057` |
| validation | `validation.probabilistic.normal_scores@1.0.0` | log score + CRPS emitted | `sha256:0b61a38524a75ecbfe3ec86fc9ebc8a7ff43be6fb07d7320611dc946157de279` |
| econometrics | `econometrics.high_dimensional.post_double_selection@1.0.0` | treatment effect emitted | `sha256:aee398df85af558259cfeb56e569f8b815e161455afa2da50381c260bddcac31` |
| survey | `survey.estimation.causal_frontier_fay_herriot@1.0.0` | SAE result + frontier diagnostics emitted | `sha256:1934b17b5629ea5bd846b2cea0bf76ba009d94e624e44882a3c0fc3f668365d3` |

## DAG Truth

The pinned DAG did not consume any of those method outputs. The prior DAG snapshot still shows:

- `build_method_catalog_snapshot`: `ok`
- `run_preflight`: `ok`
- `bind_foundry_inputs`: `ok`
- `run_data_plane_gate`: `ok`
- `run_hierarchical_policy_search`: `fail`
- `compile_foundry`: `skip`
- `run_simulation`: `skip`

The failure is still `node.invalid_state`: `verified_policy_option_rate` bounds collapse to `lower >= upper`.

## Plan Implications

Foundry should no longer be described as Manski-only at the direct producer layer. A better label is:

`direct_producer_smoked_but_route_consumer_blocked_upstream`

But this does not upgrade Foundry to DAG-consumed analytic truth. GY repair order remains: repair Lex first, then rerun the pinned DAG through `compile_foundry` and `run_simulation`, then govern Foundry outputs only if method refs, input bindings, output artifacts, and consumer surfaces carry provenance and status.

Validator: `tools/quality/validation/check_layer3_gy_foundry_breadth_audit.py`.
