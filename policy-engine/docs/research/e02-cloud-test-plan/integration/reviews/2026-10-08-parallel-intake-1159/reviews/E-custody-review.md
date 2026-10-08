# E/C09 custody review

Read-only custody review of carrier `02a75f2b7a4846bcf5b6a8f301d2d4d20b9a99b2` (tree `2432fcdc1ecade9b88fdf1f0d76175d4fbf678a5`), source handoff and publication packet. The pinned source chain is base `6d470eb884c31a8b19ee06058881cf0deaa492f5` → MC recipe-label implementation `66134569f999951e8eefef737424f12aeba24616` → runtime `adb66080e3ac64d73b3faa85d693a47c6c284427` (tree `f2c1f993052c25586420d07c766b868f632fbf39`) → final candidate `b3df9b6d84c67b48e91ea9227cadb89f5010b2a2` (tree `9d6577fe7dfc4e238f106e2f0bd22815e1d57e4e`). `adb` is the parent of `b3`; the `adb..b3` commit changes only `policy-engine/tests/unit/scientist/governance/test_calibration_validation.py`. At both commits, `policy-engine/src`, `schemas`, and `architecture` trees are identical (`914a174c…`, `1ba0cf66…`, `56317572…`); the MC test file is unchanged through `b3`.

## Packet and archive integrity

The complete carrier suffix census is 200 paths: 78 JSON, 44 TXT, 22 lock, 15 Python, 11 blob, 9 gzip, 8 XML, 4 diff, 4 stderr, 3 stdout, 1 Markdown, and 1 patch. The three artifact manifests contain 181 direct references (40 interval-admission, 117 mean-error, 24 interval-consumer-basis); every referenced committed byte count and SHA256 matches (0 mismatches).

I decompressed and parsed the full archive-member index in memory; no archive was extracted. All eight stored gzip files, decoded tar streams, member sets, and every member payload size/SHA256 agree with the index: 2,075 members, 6,209,000 payload bytes, 1,035,810 stored archive bytes and 9,390,080 decoded tar bytes; 0 mismatches.

| Archive | Stored bytes | Decoded tar bytes | Members | Payload bytes |
|---|---:|---:|---:|---:|
| author-interval | 132,320 | 1,699,840 | 553 | 825,037 |
| author-final | 194,936 | 2,529,280 | 767 | 1,288,508 |
| author-law | 3,150 | 20,480 | 9 | 9,383 |
| publication | 745 | 10,240 | 8 | 825 |
| review-baseline | 144,887 | 1,105,920 | 187 | 845,018 |
| review-661 | 389,282 | 3,194,880 | 514 | 2,459,335 |
| review-adb | 164,599 | 798,720 | 33 | 760,629 |
| review-b3 | 5,891 | 30,720 | 4 | 20,265 |

## Deciding runs and exact selectors

The author’s `author-final.tar.gz/affected.execution.json` is 3,337 bytes, SHA256 `671c49d5d2f29c11bf26d36284f4171c1f21b594e6b1c8c41e6ea8cfb207dfc5`; source `adb660…` / tree `f2c1…`; JUnit confirms 54 PASS, 2 FAIL, 0 ERROR, 0 SKIP (56), return code 1. The archived command and all selection arguments are:

```text
/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python -m pytest -q -p source_origins
  tests/unit/scientist/methods/backtesting/test_interval_basis.py
  tests/unit/scientist/governance/test_interval_basis_promotion.py
  tests/unit/calibration/test_forecast_interval_basis.py
  tests/unit/scientist/governance/test_calibration_leaderboard.py
  tests/unit/scientist/methods/backtesting/test_temporal.py
  tests/unit/scientist/governance/test_backtest_matrix.py
  tests/unit/scientist/governance/test_calibration_validation.py
  tests/unit/remediation/test_frc_02_bridge.py::test_persisted_backtest_report_readback_produces_neutral_empirical_interval_hit_evidence
  tests/unit/remediation/test_frc_02_bridge.py::test_observed_comparisons_change_empirical_admission_with_same_nominal_confidence
  tests/unit/remediation/test_frc_02_bridge.py::test_nominal_confidence_without_observations_is_not_empirical_evidence
  tests/unit/remediation/test_frc_02_bridge.py::test_persisted_self_attested_projection_cannot_override_observed_bounds
  tests/unit/remediation/test_frc_02_owner.py::test_real_ets_owner_persists_content_bound_predictive_evidence
  tests/unit/remediation/test_frc_02_owner.py::test_same_ets_shape_uses_held_out_observations_for_suitability
  tests/unit/foundry/uncertainty/test_mean_estimator_error.py::test_observed_input_recipe_label_survives_actual_mc_and_fresh_cas
  tests/unit/foundry/uncertainty/test_mean_estimator_error.py::test_weighted_empirical_draw_axis_and_iid_marker_do_not_launder_profile
  tests/unit/foundry/uncertainty/test_mean_estimator_error.py::test_qmc_rows_do_not_become_iid_mean_error
  tests/unit/foundry/uncertainty/test_mean_estimator_error.py::test_adaptive_sampling_does_not_use_fixed_iid_formula
  tests/unit/foundry/uncertainty/test_mean_estimator_error.py::test_unknown_dependency_refuses_before_draws_and_withholds_mean_error
  --basetemp=/dev/shm/e02-orch03-20261008/c09-scratch/phase2-final/affected-bases
  --junitxml=/dev/shm/e02-orch03-20261008/c09-scratch/phase2-final/affected.junit.xml
  -o cache_dir=/dev/shm/e02-orch03-20261008/c09-scratch/phase2-final/affected-cache
```

The five MC recipe-label selector arguments above produced eight JUnit cases, all PASS: `test_observed_input_recipe_label_survives_actual_mc_and_fresh_cas` (`typed_normal`, `weighted_empirical`, `legacy_inferred`); `test_weighted_empirical_draw_axis_and_iid_marker_do_not_launder_profile`; `test_qmc_rows_do_not_become_iid_mean_error` (`sobol-False-1`, `sobol-True-2`); `test_adaptive_sampling_does_not_use_fixed_iid_formula`; `test_unknown_dependency_refuses_before_draws_and_withholds_mean_error`. The old 37-case MC receipt is historical and was not repeated.

The two actual failures are the calibration-validation runner selectors below. Both stop at real CAS manifest resolution because the old fixtures refer to absent shaped candidate refs (`sha256:aaaa…`, `sha256:bbbb…`); the resolver correctly refuses before job execution. Preserve the 2 FAIL result; it is a fixture mismatch, not proof of a product mechanism defect and not an inherited/P41 attribution.

`author-final.tar.gz/fixture-retry.execution.json` is 1,757 bytes, SHA256 `21c3c455852a2e1a1592c8961f677bc5393c7f059e236c78c5c3fab78ed21126`; source `b3df9b6…` / tree `9d6577…`; 2 PASS, 0 FAIL/ERROR/SKIP:

```text
/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python -m pytest -q -p source_origins
  tests/unit/scientist/governance/test_calibration_validation.py::test_calibration_validation_runner_executes_backtest_stress_leaderboard_and_lesson
  tests/unit/scientist/governance/test_calibration_validation.py::test_calibration_validation_runner_blocks_eligibility_on_missing_transport_and_interference
  --basetemp=/dev/shm/e02-orch03-20261008/c09-scratch/phase2-final/fixture-retry-bases
  --junitxml=/dev/shm/e02-orch03-20261008/c09-scratch/phase2-final/fixture-retry.junit.xml
  -o cache_dir=/dev/shm/e02-orch03-20261008/c09-scratch/phase2-final/fixture-retry-cache
```

This retry substitutes real synthetic CAS `put_json` artifacts of the expected existing kind/media in those two test fixtures; manifest and byte resolution are unchanged. It is not a 56-case run on `b3`. The handoff permits only qualified carry of the other 54 cases on unchanged source and inputs.

## Independent receipts, limits, and interruptions

- Independent 661 review: scoped GO; 18 ordinary observations and 4 retained-marker removal controls recorded as EXPECTED_FAIL; parent/child loaded-origin denominators 988/971, mismatches 0, 14 fresh child refs. This includes native C5b/ETS consumer paths and MC typed-Normal/weighted/inferred recipe controls, using synthetic fixture authority only. First two private harness attempts were ERROR/incomplete (reader import and `point_forecasts` field-name mistakes); third read the already-retained deciding outputs, not a numerical rerun.
- Independent adb forward review: 3 ordinary limited/complete/point controls PASS; removal of the recomputed-summary guard EXPECTED_FAIL; 862 parent/child loaded origins, mismatches 0, 4 fresh refs. It carries only the specific temporal-summary delta.
- Independent b3 forward review: GO for passive test-only forward; exact `adb..b3` footprint is the single calibration-validation test file. Retry source-origin receipt reports 971 loaded origins, 0 mismatch. No independent complete 56-case `b3` result.
- Initial author development run (19 cases: 15 PASS/3 FAIL/1 ERROR) retains test-fixture setup mistakes; the later 23-case pass predates additional cases. Baseline `ee0…` C5b/forecast/temporal failures plus setup error are preserved. These do not become a green result by proximity to the later bounded checks.
- Courier interruption: first stdlib-only packager was CPU-bound under host Python 3.14 before producing the first archive; interruption was preserved and no deciding output removed. Packaging retry under host Python 3.12 completed. This is transport harness interruption, not a product test result. A separate first remote-readback attempt read a stale tracking ref after a successful fetch; corrected explicit fetch/readback recorded with full output, no source mutation.

Publication’s ordinary push/fetch/ls-remote and remote byte verification PASS for candidate `b3df9b6…`: 24 direct artifacts, 8 archives, 2,075 members, 6,209,000 member bytes, 0 mismatch. That is transport custody only. The handoff explicitly says G source acceptance and formal finding closure were not issued (`closed_ids=[]`); authentic ordered-source currentness, scientific law/verifier admission, installed/production integration and broad G replay remain UNRUN/not established. No unique outputs or active environments were cleaned up.

This review read receipts and archive members in memory; it did not execute archived scripts, extract files, run tests, install packages, alter source or refs, or write tracked files. Raw diffs, origin inventories, and archive payloads were not copied into this report.
