# ADR-0079: Hybrid SCM with MechanismSource (DATA_FITTED / LITERATURE_PRIOR / HYBRID / DEFAULT)

## Status
Proposed

## Date
2026-02-28

## Context
Phase 10 fits SCM mechanisms from observational data, and Phase 15 assigns Bayesian
priors from the literature. These two sources of mechanism knowledge are currently
modelled as competing alternatives: a mechanism is either data-fitted or
literature-derived. In practice, many policy-relevant mechanisms benefit from both:
literature priors regularise small-sample estimates, while data updates shift the
posterior when evidence is strong. Without a formal hybridisation protocol, analysts
must manually choose one source per mechanism, losing information.

## Decision
1. Introduce a `MechanismSource` enum with four values: `DATA_FITTED`,
   `LITERATURE_PRIOR`, `HYBRID`, and `DEFAULT`.
2. `DATA_FITTED` mechanisms use MLE/MAP from `gcm_fit` (Phase 10 status quo).
3. `LITERATURE_PRIOR` mechanisms use the prior distribution from
   `LiteratureCausalPrior` without data updating (useful when n < 30).
4. `HYBRID` mechanisms use NumPyro (ADR-0074) to perform Bayesian updating: the
   literature prior is the prior distribution, observational data provides the
   likelihood, and the posterior becomes the fitted mechanism.
5. `DEFAULT` selects automatically: `HYBRID` when both a literature prior and
   sufficient data (n >= 30) exist; `LITERATURE_PRIOR` when only priors are
   available; `DATA_FITTED` otherwise.

## Consequences
### Positive
- Phases 10 and 15 become complementary rather than competing, reflecting the
  Bayesian ideal of prior + data = posterior.
- `DEFAULT` mode automates the selection, reducing analyst burden.
- `MechanismSource` is stored per-edge in the SCM spec, enabling fine-grained auditing.
### Negative
- `HYBRID` fitting is computationally more expensive than MLE (MCMC sampling).
- Prior-data conflict (strong prior vs. contradictory data) can produce bimodal
  posteriors that are hard to interpret; requires a diagnostic check.
- Adds a new axis of variation to the SCM spec, increasing the number of test
  configurations.
