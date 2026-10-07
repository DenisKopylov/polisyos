# Independent E Morris analysis-count review

**Finding: bounded counterexample confirmed at candidate `70c4a14fc872f5ef66437d958ba63884ecdda168`, tree `3e654b07a3228d1b3d2d0bb2a3a91ae792068090`.** This is `SAME_CLASS_DEEPER` for the plan-budget/source-of-truth proxy, not a new finding ID: the existing cap admits a declared estimate, while the analysis consumer does not bind its supplied work count to that plan.

## Evidence check

- `attempt2` is a completed native `analyze_sensitivity` probe. Its script verifies the clean G branch/head, candidate tree, and byte equality of the four imported PolicyOS source modules to candidate Git blobs. I independently rechecked those blob IDs, archived file SHA-256 values, and tree. SALib 1.5.2 resolves from the existing overlay; the call is unmocked. Command/result/streams and their hashes agree with the saved environment receipt.
- The healthy control supplies two rows (one valid 1D, four-level Morris trajectory) for `y=2*x`; it is accepted with `mu_star[x]=2.0`, `total_runs=2`, matching estimated count. `sigma=NaN` and degrees-of-freedom warnings are expected for one trajectory; treat this only as the point-estimate/admission control.
- The discriminator supplies four finite, grid-valid rows: two complete trajectories `[0, 2/3]` and `[1/3, 1]`. It is accepted by the real analyzer with `mu_star[x]=2.0`, `total_runs=4`, `effective_run_count=4`, actual trajectory IDs `[0,1]`, although the admitted plan declares `n_trajectories=1`, `estimated_runs=2`, and `max_estimated_runs=2`.
- Source agrees with the witness: plan re-admission and `_validate_morris_plan_samples` check plan validity plus complete Morris geometry/grid; they do not compare supplied trajectory blocks with the plan count/cap. `analyze_sensitivity` passes the prepared arrays to SALib and derives actual run counts from input rows. This does not exercise `generate_sensitivity_samples` and proves no sampler overgeneration.
- Metadata is a visible plan/observation split, not automatically a false number: `n_trajectories` and `estimated_runs` remain declared-plan fields; `total_runs`, `original_total_runs`, `effective_run_count`, and trajectory IDs reflect the observed four rows. The unresolved contract is whether caller-supplied rows must match the plan (and its cap), or belong to a distinct explicitly named analysis-input profile.

## Scope and disposition

Attempt 1 is properly `UNRUN_RESOURCE_CEILING`: imports reached 174,096,384 bytes against 104,857,600; the analyzer was not called. Attempt 2 is a single bounded retry at 402,653,184 bytes, peak 173,948,928, completed in 2.357 seconds. Earlier setup-path errors are harness failures before project imports. No test suite or sampler was rerun here.

The separate 77-test generation/admission run remains PASS at the same source candidate; it covers mutable-plan re-admission, sampler/analyzer paths, refusal, and the explicit `allow_large_run` case, but has no valid over-cap caller-supplied-array discriminator. This evidence does not invalidate those tests, establish a global/server budget, or close B99.

Next E owner action: reconcile actual analysis rows/trajectory count with the plan/cap before analysis if that is the intended contract; otherwise explicitly scope the cap to generated designs and document the distinct supplied-analysis profile with observed counts. Do not invent a new Morris statistic or sampler rule. Reuse the control and four-row negative as the focused falsifier on the exact repaired source; keep the 77-test receipt and B99 closure decision separate.

Evidence: `R/1915-E-Morris-analysis-probe/attempts-index.md`, `attempt2/{report.md,probe.py,inputs.json,result.json,module-hashes.json,command.json,stdout.txt,stderr.txt,environment-before.json,environment-after.json}`; generation suite: `R/1845-DOE-checks/{test-command.json,test-result.json,stdout.txt}`. No tests, refs, environments, source, or tracked files were changed for this review.
