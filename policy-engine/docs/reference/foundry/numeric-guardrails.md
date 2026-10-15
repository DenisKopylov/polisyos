# Foundry Numeric Guardrails

Owner: `@foundry-owners`
Source of truth: `src/polisyos/foundry/runtime/numeric.py` and its implementation owner `src/polisyos/foundry/execute/_internal/numeric/__init__.py`.
Source inspection pin: `c35222b3dcf103338175cf300c5fe9487e6416f3`.
Evidence level: implementation sources inspected at this pin; the selected tests below were not run for this docs-only review.

This note documents shared numeric helpers and selected caller-specific
invariants. It does not claim that every caller uses these helpers or that a
finite numerical result validates a scientific model or policy effect.

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

## Verification anchors

- Non-finite runtime guards: `tests/unit/foundry/runtime/test_nan_guard.py`
- Hessian envelopes: `tests/unit/foundry/calibration/test_hessian.py`
- Distributional metrics: `tests/unit/foundry/analysis/test_distributional.py`
- Actor-critic numerics: `tests/unit/foundry/agent_sim/test_actor_critic_numerics.py`
- Fiscal precision: `tests/unit/foundry/execute/mechanisms/test_fiscal_precision.py`
