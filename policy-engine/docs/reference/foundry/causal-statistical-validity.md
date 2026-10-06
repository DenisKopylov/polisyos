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

## Selected runtime profiles

The family table above describes the historical offline benchmark contract;
its labels do not establish the current estimator's inference law. The selected
staggered DiD target is `theta_sel = sum_g pi_g mean_{t in E_g} ATT(g,t)`.
`E_g` is fixed before fitting from each admitted cohort's post-periods and the
declared study horizon. `pi_g` is the estimated ever-treated cohort share; its
ratio influence term is part of the scalar unit influence function. Missing
cells, unsupported controls, insufficient bootstrap resolution or a degenerate
unit score do not produce successful inference. Anticipation excludes contaminated
controls; the input binds dense panel rows, unique unit IDs and treatment timing.

One iid Mammen multiplier per independent panel unit is shared across every
cell. The scalar centered studentized null test and closed pointwise interval
use the same finite-B-plus-one tail law. Consumers use `null_rejected` and the
integer `minimum_accepted_tail_count` against `null_tail_count`; the reported
`significance_level` is the exact decimal confidence-level complement. Recomputing
a decision from binary floating subtraction `p < 1 - confidence_level` can disagree
at a discrete endpoint. This is a large-independent-unit asymptotic profile,
without a small-cluster coverage or simultaneous-band guarantee. Synthetic
recovery does not identify parallel trends on an admitted real population.

The causal evaluator resolves the actual observational CAS source around its
existing MethodJob runner. For `dowhy_identify_estimate`, the parent binds this
source to the selected Python3.12/DoWhy0.14 worker; Python3.14 reads its persisted
strict response. The canonical output dematerializer projects historical
`report`/`envelope` ports to declared report/result/uncertainty slots. Raw dispatch
monitor warnings about these historical ports remain separate diagnostics.
The selected DiD consumer independently recomputes the target/data binding.

These numerical bindings grant no evaluation permission. The production node's
existing EvalSafety admission remains mandatory. Its current non-simulation
contract requires independently grounded real-world inputs and Runtime-issued
authority; a synthetic DGP cannot be relabelled to satisfy it. Numerical
MethodJob/CAS witnesses and blocked admission controls therefore do not establish
a successful production-node evaluation. The unavailable exact local admission
and source inputs are handed to G separately. TMLE's candidate/limited result
remains its own typed numerical profile; no successful causal report or interval
is manufactured for an unavailable EIF interval.
