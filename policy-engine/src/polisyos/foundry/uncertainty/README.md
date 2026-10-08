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
- Files: 12 Python files in this package
- Exports: 12 names declared in `__all__`


## Conditional mean-estimator numerical error

The fixed random Monte Carlo path reports `mean_estimator_error` separately from
`mc_std` (outcome dispersion) and the existing outcome quantiles. A complete finite
corpus sampled from the implemented product of typed, nondegenerate Normal fits
can report sample-mean standard error `s / sqrt(n)` with `ddof=1`. The field is a
conditional numerical estimate: it assumes a fixed deterministic response and
finite response variance, which this callback API cannot verify. It cannot admit
an IID population, establish a confidence interval or promote a trust gate.

Legacy interval-inferred laws, posterior/empirical rows (including weighted rows
labelled `draw` or `iid`), unknown dependency, incomplete execution, fewer than two
finite outputs, adaptive stopping and pooled QMC rows report an unavailable mean
error. The G-based QMC producer does not retain independent scramble means; its
pooled rows cannot supply this IID formula. The existing sampling recipe, seed,
content hashes and requested/attempted/finite counts accompany the diagnostic.
Scientific source/law authority and served consumer admission remain separate.

The diagnostic persists in the existing uncertainty envelope metadata and reads
back through the maintained CAS reader. Existing outcome intervals, composition
profiles, `mc_std` and their gate semantics are unchanged by this additive field.

`sampling_law` describes the implemented input recipe; it names the typed-Normal
product only on that actual fixed-random input profile. Other carriers, inferred
laws, adaptive stopping and QMC paths keep a generic implemented-recipe label and
their actual `input_recipe_profiles` family/carrier fields. The diagnostic's
`supported_estimator_profile` is a separate eligibility profile, never an assertion
that unsupported actual inputs followed that law. Input metadata labels cannot
override these fields, and correcting them does not change any numerical estimator.
