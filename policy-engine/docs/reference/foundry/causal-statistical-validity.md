# Foundry Causal And Statistical Validity

Owner: `team-foundry`
Source of truth: `src/polisyos/foundry/validation/causal_validity.py`
Primary tests: `tests/unit/foundry/validation/test_causal_validity.py`,
`tests/unit/scientist/validation/test_policy_grounding_matrix.py`

This page defines the offline benchmark evidence contract for
`causal_statistical_validity_report_ref`. The report is intentionally separate
from runtime method defaults: it proves that representative method families can
recover deterministic fixtures and fail closed on invalid causal evidence before
those methods are promoted into default policy recommendation paths.

## Artifact Contract

The report payload uses schema
`policyos.foundry.causal_statistical_validity.v1` and artifact kind
`foundry.causal_statistical_validity_report`.

Required top-level fields:

| Field | Meaning |
| --- | --- |
| `status` | `pass`, `warn`, or `fail`, recomputed from benchmark cases. |
| `ref_key` | Always `causal_statistical_validity_report_ref`. |
| `benchmark_suite_id` | Deterministic offline suite id. |
| `deterministic` | `true` for checked-in synthetic fixtures. |
| `method_defaults_changed` | `false`; benchmarks do not alter runtime defaults. |
| `method_families` | Declared contracts for covered Foundry families. |
| `cases` | Normalized benchmark case diagnostics. |
| `issues` | Blocking or warning quality failures. |
| `blocking_issue_count` | Count of `severity == "fail"` issues. |

## Covered Families

Each family declares expected assumptions, input shape, estimand, uncertainty
type, minimum sample diagnostics, and failure modes.

| Family | Estimand | Uncertainty | Main assumptions |
| --- | --- | --- | --- |
| `difference_in_differences` | `ATT` | `cluster_bootstrap_ci` | parallel trends, stable composition, no anticipation |
| `synthetic_control` | `ATT` | `placebo_permutation_interval` | convex hull overlap, pre-treatment fit, no interference |
| `regression_discontinuity` | `LATE` | `robust_bias_corrected_ci` | continuity at cutoff, no sorting, bandwidth robustness |

These entries describe the offline benchmark artifact contract. A declared
procedure or historical fixture result does not establish that the corresponding
runtime estimator provides calibrated inference on admitted production data.

## Staggered DiD Runtime Admission

The runtime owner is
`src/polisyos/foundry/methods/catalog/causal/did.py`, exposed through the registered
`causal.inference.did.staggered@1.0.0` method. Its current admission contract uses a
dense panel with finite outcomes and cohort starts expressed as integer panel
period indices; `-1` denotes a never-treated unit. This timing convention is an
input precondition. The bounded admission checks described here do not establish
validation of every possible raw `treatment_timing` representation.

`anticipation` must be a nonnegative Python or NumPy integer period count.
Booleans, fractions, strings, `None`, NaN, infinity and negative values produce an
`INPUT_INVALID` report before cohort cells are constructed. The baseline for an
observed cohort beginning at period `g` is `g - 1 - anticipation`. If any requested
observed cohort has no such pre-baseline, the method refuses the entire requested
cohort set with `ASSUMPTION_FAILED` and records `missing_baseline_groups`; it does
not report an ATT for a silently reduced subset. In particular, a cohort beginning
at period zero is unsupported even when another cohort has a valid baseline.

The declared control rule is either `never_treated` or `not_yet_treated`. The latter
requires a control's treatment start to be later than the evaluated period plus
the anticipation window, or to be `-1`. A requested cohort-time cell without
admissible controls also refuses the request. Missing-baseline refusals have no
point estimate. Their typed report remains a refusal after the real dispatcher,
`persist_causal_effect_report`, filesystem CAS storage and
`load_causal_effect_report` readback; its uncertainty envelope has
`gate_eligible=False`. This consumer check covers the bounded registered-method
and persisted-report path. Full Scientist node and frozen production-plan replay
remain separate verification obligations.

### Scientific Evidence Boundary

The deterministic regression panels in
`tests/unit/remediation/test_cau_02.py` establish the admission and control-selection
properties above, including a mixed unsupported/supported cohort request and a
known supported contrast with ATT equal to 5. They do not establish parallel
trends, no anticipation or independent-unit admission on real data.

Even a supported staggered panel currently produces an `ASSUMPTION_FAILED` report
with reason `staggered bootstrap coverage and null calibration are not
established`. It can carry a descriptive point estimate and a unit-multiplier
percentile interval in `method_params`, while inferential confidence interval and
p-value remain absent. The descriptive interval is not a calibrated confidence
interval or null distribution, and its envelope remains ineligible for a gate.
Multi-cohort coverage, serial dependence, power and admitted cohort/unit records
remain with the causal methodology and data owners. Historical offline benchmark
contracts and results retain their original scope.

### Backend And Verification Scope

The E02 baseline uses Python 3.14. Its canonical dependency markers exclude
DoWhy and EconML; skipped native tests are unrun backend obligations. Adapter
recorders, successful imports of other libraries and synthetic panels do not
supply a positive witness for either excluded backend.

The bounded CAU reference run used real `statsmodels==0.14.6` and `patsy==1.0.2`
in a separate analytics environment after the original environment failed
collection because statsmodels was absent. Its standard-DiD covariance reference
does not calibrate staggered inference or validate production assumptions. The
original collection error, native skips, source SHA, environment and complete
executed-test denominator are retained in the
[cohort-admission handoff](../../research/e02-cloud-test-plan/implementation-handoffs/F/cau-cohort-admission.json).
Use that receipt's exact native command with the required real dependencies;
optional backend verification needs its supported reference environment.

## Benchmark Cases

Golden fixtures live in `tests/_golden/foundry/causal_validity/cases.json`.
The suite covers:

- known-answer synthetic recovery within declared tolerance;
- placebo checks that must degrade or fail instead of producing confident
  non-zero recommendations;
- negative-control outcomes with the same fail-closed posture;
- sensitivity batteries;
- power and sample adequacy checks;
- missingness stress;
- uncertainty calibration against target empirical coverage.

## Scientist Gate

`build_policy_grounding_matrix_report(...)` accepts an optional
`causal_statistical_validity_report`. A failing report becomes a blocking
quality failure only when the final policy contains a major `causal` or
`numerical` claim with Foundry method refs. This keeps unrelated final policy
artifacts from failing on benchmark evidence they do not rely on, while still
blocking major causal or numeric claims when sensitivity, power, missingness, or
calibration evidence fails.

## Verification

```bash
uv run pytest tests/unit/foundry/validation/test_causal_validity.py tests/unit/scientist/validation/test_policy_grounding_matrix.py -q
```
