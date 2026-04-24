# ADR-0082: ABM bridge adaptive tolerance (2-sigma variance) + NON_LINEAR_DIVERGENCE at phase transitions

## Status

Proposed

## Date

2026-02-28

## Context

The ABM bridge compares agent-based simulation outputs against SCM-predicted causal
effects to validate structural assumptions. The current comparison uses a fixed
tolerance (5% relative error), which is too tight for ABM runs near phase transitions
(e.g., tipping points in opinion dynamics, threshold effects in epidemiological models)
where small parameter perturbations produce large outcome swings. This causes spurious
`ABM_INCONSISTENT` failures that block the pipeline unnecessarily. Conversely, the
fixed tolerance is too loose for well-behaved linear regimes, letting genuine
inconsistencies pass undetected.

## Decision

1. Replace the fixed 5% tolerance with an adaptive tolerance derived from the ABM's
   own output variance: `tolerance = max(base_tol, 2 * sigma_hat)` where `sigma_hat`
   is the standard deviation across ABM replications.
2. Introduce a `NON_LINEAR_DIVERGENCE` outcome status (alongside `CONSISTENT` and
   `INCONSISTENT`) that fires when the ABM-SCM discrepancy exceeds the adaptive
   tolerance but the ABM's coefficient of variation also exceeds 0.5, indicating
   a phase-transition regime.
3. `NON_LINEAR_DIVERGENCE` is treated as a soft warning, not a hard gate: the pipeline
   continues but the `ABMAlignmentReport` is flagged for human review.
4. The `base_tol` parameter defaults to 0.02 (2%) and is configurable per
   `ProblemFrame` to allow domain-specific tuning.
5. All tolerance computations are logged in the `ABMAlignmentReport` for
   reproducibility and audit.

## Consequences

### Positive

- Eliminates spurious failures near phase transitions without loosening checks in
  linear regimes.

- `NON_LINEAR_DIVERGENCE` gives analysts a clear signal to investigate non-linearity
  rather than a binary pass/fail.

- Adaptive tolerance scales automatically with the number of ABM replications.

### Negative

- Requires a minimum number of ABM replications (>=10) to estimate sigma reliably;
  fewer replications fall back to the fixed base tolerance.

- The 2-sigma threshold is a heuristic; edge cases with heavy-tailed ABM outputs
  may need a robust variance estimator (MAD).

- Adds a third outcome status that downstream governance passes must handle.
