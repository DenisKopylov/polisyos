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

## Current DiD diagnostic provenance

The preceding family table describes the offline benchmark contract. The
dedicated runtime DiD producers separately record descriptive pretrend evidence
and its current-input basis. They do not use an offline benchmark pass or
diagnostic non-rejection to establish identification on an admitted real panel.

Computed Standard and Staggered DiD reports include `diagnostic_contract` and
`diagnostic_binding` in `method_params`. The contract binds the complete outcome
array, binary treatment membership and `time_treatment`, and the complete typed
diagnostic list under the group-mean linear HC1/normal profile. The diagnostic
window follows the supplied `time_treatment`; this descriptive contrast is not
a proof that every staggered cohort has untreated potential-outcome parallel
trends. The existing Standard warning diagnostic is included in the projection.

This binding is separate from the staggered fixed scalar `target_contract`.
Changing only `time_treatment` can change a testable diagnostic to `not_testable`
while leaving cohort timing, eligible periods, theta_sel and its inference
unchanged. Matching scalar-target markers therefore cannot validate that
diagnostic. The internal typed `_diagnostic_contract` seam on the existing
dedicated method recomputes the full result from the current panel. A consuming
validator must compare both contract metadata and the actual typed
`report.diagnostics` against this projection. Recomputing a hash of an offered
diagnostic alone is not an independent check.

Insufficient preperiods and missing groups retain `not_testable`, no statistic
or p-value, and `passed=False`. Standard DiD with no preperiod remains
`INPUT_INVALID` before diagnostic computation. Historical reports and output
aliases remain readable; current-input validation requires recomputation or
refusal when their diagnostic contract is missing or stale. All diagnostic
dispositions explicitly retain `identification_authority=False`.

Native NumPy and independent Statsmodels HC1 checks verify this finite
descriptive profile. Python 3.14 optional DoWhy/EconML marker exclusions are not
backend witnesses. Current-input diagnostic custody, numerical SUCCESS and an
actual Runtime identification admission are distinct properties; the last
requires its canonical verifier and admitted inputs.
