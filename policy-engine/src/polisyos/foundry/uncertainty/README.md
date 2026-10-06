# Uncertainty (`polisyos.foundry.uncertainty`)

`uncertainty` - propagation layer for mapping input uncertainty envelopes to
output metric uncertainty in Foundry simulations.

## Role in System

- **Depends on:** `polisyos.ir.analytics.uncertainty`, JAX
- **Used by:** Scientist uncertainty propagation nodes and calibration post-fit analysis
- Sits after execution and before downstream reporting/aggregation.

## Key Concepts

- **Dispatcher** - selects delta, Monte Carlo or auto propagation strategy.
- **Delta method** - Jacobian-based propagation for differentiable simulations.
- **Monte Carlo** - sampling-based propagation when analytic assumptions fail.
- **Aggregation** - envelope merging for multi-strategy or multi-run outputs.
- **Config-driven fallback** - strategy choice is explicit and inspectable.
- **Sampling admission** - `sampling_admission.py` rejects unsupported numeric
  ranges before any sampler/evaluator; missing multi-input dependence is unknown.
  Full Gaussian covariance preserves null spaces. Paired empirical laws require
  content-bound coordinate order and ordered row identity.
- **Mean planning** - `bounded_iid_mean` admits the canonical bounded indicator
  response over an explicit Uniform[0,1] law, uses independent pilot/main streams,
  and freezes a Bernstein main budget. Its numerical certificate is replayed from
  persisted law/response/seed bytes; it does not verify production source authority.
  Opaque callbacks cannot self-certify. Legacy adaptive settings execute the fixed
  maximum without optional peeking at predictive spread.
- **RQMC** - Sobol rounds to complete power-of-two nets per scramble. Mean error
  uses replicate mean variation; predictive output spread remains separate.

The Scientist node can configure the narrow indicator response with
`bounded_iid_mean.response_threshold`. It persists/reloads the result and
reconciles complete draw outcomes before publishing the candidate simulation.
General served simulation-evaluator and production-law custody remain separate
owner tasks. Uncertainty v1.1 read/replay and its wire schema are unchanged;
independent point/interval functionals and v2 law storage require IR ratification.

## Public API

| Type/Function                   | Description                                               |
| ------------------------------- | --------------------------------------------------------- |
| `PropagationConfig`             | Configures confidence and propagation strategy.           |
| `PropagationDispatcher`         | Selects and executes propagation strategies.              |
| `PropagationResult`             | Output record for a propagated metric envelope.           |
| `PropagationStrategy`           | Protocol for propagation implementations.                 |
| `QuasiMCSampler`                | Quasi-Monte-Carlo sampler for sampling-based propagation. |
| `aggregate_envelopes()`         | Combines multiple envelopes into one.                     |
| `compute_first_order_indices()` | Sensitivity helper for variance attribution.              |
| `extract_std()`                 | Extracts scale from a typed parametric fit or legacy interval. |

→ Full reference: [docs/reference/foundry/index.md](../../../../docs/reference/foundry/index.md)

## Current State

- Last updated: 2026-09-28
- Files: 13 Python files in this package
- Exports: 16 names declared in `__all__`
# Sampling consumer entrypoints

Scientist consumes `BoundedIndicatorResponse`, `reconcile_draw_outcomes`,
`sampling_content_digest` and `verify_mean_certificate` through the package
facade. These exports preserve the canonical sampling owner objects and its
recomputed denominator/certificate refusals. They do not establish a served
evaluator or institutional authority.

`admit_empirical_weights`, `empirical_cdf` and `admit_unit_uniform` expose the
same finite law admission used by sampling producers. Positive categories must
retain distinct representable CDF intervals, and inverse transforms use finite
coordinates in `[0, 1)`. These functions supply no joint law or source authority.
