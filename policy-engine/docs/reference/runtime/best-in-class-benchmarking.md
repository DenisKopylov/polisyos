# Best-In-Class Benchmarking Record

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/quality/policy_benchmarking.py`, `src/polisyos/runtime/quality/policy_design_case.py`, and `tests/unit/runtime/quality/test_policy_benchmarking.py`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Source and test-reference inspection only for this documentation update; the tests were not run.

`policyos.runtime.policy_design_case.best_in_class_benchmarking.v1` is the Wave 31
Policy Design Case record that makes "best in class" claims falsifiable.

The record is a runtime quality evidence contract, not dashboard copy. A passing record
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

The record and scorecard gate do not independently establish the truth of
benchmark inputs or authorize publication. Evidence provenance and any
publication decision remain with their respective owners.
