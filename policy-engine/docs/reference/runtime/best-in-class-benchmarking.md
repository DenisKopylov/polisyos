# Best-In-Class Benchmarking Record

`policyos.runtime.policy_design_case.best_in_class_benchmarking.v1` is the Wave 31
Policy Design Case record that makes "best in class" claims falsifiable.

The record is runtime quality authority, not dashboard copy. A passing record
must bind the relevant claim ids to benchmark evidence for:

- external audit pass rate;
- human-team benchmark;
- reversal rate;
- retraction rate;
- calibration error;
- claim substantiation rate;
- triangulation coverage;
- operator time-to-root-cause.

Each metric carries an observed value, target value, direction, sample size,
runtime evidence ref, and runtime event ref. The record also consumes previous
Wave 30 run-cost and proportionality evidence through `run_cost_ledger_refs` and
`proportionality_evidence_refs`.

Scorecard gate:

- `policy_design_wave31_best_in_class_benchmarking`

Primary validator:

- `polisyos.runtime.quality.policy_benchmarking.validate_policy_benchmarking_record`

Negative control:

- best-in-class final major claims without a validated benchmarking record fail
  with `policy_design_best_in_class_benchmarking_record_missing`.
