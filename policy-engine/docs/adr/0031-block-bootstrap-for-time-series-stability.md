# ADR-0031: Block Bootstrap for Time-Series Causal Discovery Stability

## Status

Proposed

## Date

2026-02-28

## Context

Phase 6 PCMCI-based causal discovery operates on time-series data where
observations are temporally dependent. Stability assessment of discovered edges
requires bootstrap resampling, but standard i.i.d. bootstrap destroys the
temporal autocorrelation structure, producing overly optimistic stability
estimates.

Block bootstrap preserves temporal dependency by resampling contiguous blocks
of observations. The choice of block length affects the bias-variance trade-off
of the stability estimate.

## Decision

1. Use **block bootstrap** (circular variant) as the default resampling strategy
   for PCMCI stability assessment in `polisyos.foundry.methods.catalog.causal.pcmci_discovery`.
2. Minimum **100 bootstrap runs** for production stability estimates. Development
   and CI environments may use fewer (minimum 20) with a logged warning.
3. Block length defaults to **automatic selection** using the algorithm of
   Politis & White (2004) with the correction of Patton, Politis & White (2009),
   based on the data's autocorrelation structure.
4. Users may override block length via the method's configuration when domain
   knowledge suggests a specific temporal scale.
5. Stability scores below 0.5 across bootstrap runs flag the edge as unstable
   in `CausalGraphModel`.

## Consequences

### Positive

- Provides honest uncertainty quantification for temporal causal discovery,
  respecting the autocorrelation structure of time-series data.

- Automatic block length selection removes a difficult hyperparameter choice
  for non-expert users.

- Stability metadata integrates naturally with the `CausalGraphModel` edge
  confidence framework (ADR-0030).

### Negative

- Computational cost scales linearly with the number of bootstrap runs;
  100 runs on large datasets may require significant compute time.

- Automatic block length selection adds a dependency on spectral density
  estimation, which may fail on very short series.
