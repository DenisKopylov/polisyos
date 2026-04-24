# ADR-0063: Mediator P*(z|x) conditional; covariate P*(z) marginal (Pearl & Bareinboim 2011)

## Status

Proposed

## Date

2026-02-28

## Context

When transporting causal effects across populations, the re-weighting strategy
depends on whether a variable acts as a mediator or a covariate. Pearl and
Bareinboim (2011) establish that mediators require conditional distributions
P*(z|x) from the target population, whereas covariates require only the marginal
P*(z). Conflating the two leads to biased effect estimates when population
distributions differ. The foundry's transport_check and parameter_transfer
modules need an explicit rule to select the correct distribution type.

## Decision

1. Classify every intermediate variable in the causal graph as either
   `mediator` or `covariate` during graph reconciliation.
2. For mediators, the transport layer fetches the conditional distribution
   P\*(z|x) from the target population dataset.
3. For covariates, the transport layer fetches the marginal distribution P\*(z)
   from the target population dataset.
4. The classification is stored on the graph edge metadata and verified by the
   `transportability_required_pass` governance check.

## Consequences

### Positive

- Correct distributional treatment of mediators vs. covariates eliminates a
  known source of bias in cross-population transport estimates.

- Explicit classification on graph edges makes the transport assumptions
  auditable in governance reports.

### Negative

- Misclassification of a variable (mediator vs. covariate) silently produces
  biased results; additional validation heuristics may be needed.

- Fetching conditional distributions requires richer target-population data
  than marginals alone, increasing data requirements for transport.
