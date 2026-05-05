# Foundry Numeric Guardrails

This note documents the WS-4 numeric invariants that are now enforced across
calibration, constraints, actor-critic math, distributional metrics, and fiscal
mechanisms.

## Domain epsilon policy

- `probability`: `1e-6`
- `positive`: `1e-8`
- `relative_loss`: `1e-8`
- `decimal`: `1e-12`
- `utility`: `1e-6`
- `percent_delta`: `1e-12`

These values are centralized in `polisyos.foundry.runtime.numeric` and should be used
instead of introducing ad hoc epsilons in downstream modules.

## Fail-closed behavior

- Calibration losses return `+inf` when predictions, targets, weights, or
  reduced losses become `NaN` or `Inf`.

- Constraint aggregation raises `ValueError` when state values, weights, or
  quantile parameters are non-finite or out of bounds.

- Decimal conversion rejects non-finite inputs before any `Decimal`
  materialization.

- Public fiscal entrypoints reject tax or subsidy rates outside `[0, 1]`.
- Hessian-derived calibration envelopes are published as
  `heuristic_range`, not statistical confidence intervals.

## Stable transform invariants

- Bounded bijectors use symmetric probability clipping and stable logit /
  softplus inverses.

- Hessian damping is applied before covariance inversion, and raw singular
  directions report `condition_number = inf`.

- Actor-critic continuous policies clip `log_std` to `[-20, 5]` before
  exponentiation, log-prob evaluation, and entropy calculation.

- CARA utility uses the `gamma -> 0` limit instead of dividing by zero.

## Economic metric semantics

- Positive, non-debt-like baselines keep the usual percent-change semantics.
- Zero, negative, and debt-like baselines use bounded symmetric percent delta:
  `200 * (after - before) / (abs(before) + abs(after) + eps)`.

- Classical Gini and Palma remain unavailable for negative-value inputs.

## Expected failure modes

- Invalid quantiles: `ValueError`
- Non-finite constraint inputs: `ValueError`
- Invalid fiscal rates: `ValueError`
- Non-finite calibration loss components: `+inf`
- Non-statistical Hessian envelopes: `heuristic_range`, `gate_eligible=False`
