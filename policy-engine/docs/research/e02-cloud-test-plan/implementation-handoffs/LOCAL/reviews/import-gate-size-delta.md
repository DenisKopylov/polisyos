# Independent review: package-import gate size extraction

## Scope and result

Scoped review passes for the three-file extraction. It moves the existing module-size ratchet implementation out of the canonical package-import gate, keeps the original Finding class and the wrapper/report route, and reduces the gate checker from 1,627 to 1,564 physical lines under the existing 1,580 ceiling. I found no blocking behavioral regression in this delta.

This is a new review class relative to the preceding docs-freshness/baseline-admission work: physical source-size overage. P40 bucket: NEW. The generic size denominator contains the new helper, which is only 72 logical lines; no second escape in this class was found. No G closure IDs are proposed.

The reviewed boundary is candidate worktree /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos, branch codex/e02-unified-local-20261009, at base HEAD 9e02a9f49c8b01026327a9f7c7e18711b13a96f2, tree 881a950dccb7cdefacc636515aa7dd2bceadf928, parent 68b8ac5c32e03309ad888cb3799ad1c574fbdca7. The code under review is later uncommitted worktree content; this packet does not claim an immutable source commit.

Exact changed-path hashes at review time:

- policy-engine/tools/quality/validation/check_package_import_gates.py — d511a5097e67b25046e7daa4c8431562136b77b4403e47dfcc79e7ae8add9766
- policy-engine/tools/quality/validation/package_import_size_ratchet.py — cbdd75148067f17fd41b2331be708cc39bf21f8a3fb5bcab1311512a6387dacf
- policy-engine/tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py — 078a94e931c315b59ee2d469ae39d5aa67451bf3384370d4c5eb0be6e282b8e4

The author decision packet is policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/import-gate-module-size-repair.md @ c3d470b2c455287cceeae4b689f2c7a2bca70d301a1104ee197e350258b37e73.

## Property and code review

The canonical checker remains the CLI and report owner. Its existing _check_module_size_ratchet entrypoint now delegates to the extracted module with finding_factory=Finding. Finding remains defined in check_package_import_gates.py; the helper does not introduce a competing result type. The report builder still calls the same entrypoint for the same summary key, and dump_json/run_cli/main are unchanged. A runtime probe confirmed emitted objects retain class module tools.quality.validation.check_package_import_gates and their original four-field as_dict shape.

The extraction preserves the prior ratchet logic: same TOML path, budget iteration, missing-module finding, nonblank/noncomment logical counter, current_lines and report_only_limit_lines predicates, detail strings, and zero fallback in as_int. The moved read_toml/date_is_after helpers retain their prior behavior and are re-exported under the existing private aliases used by the canonical checker. A repository search found no caller of the removed private _count_lines name. The unchanged architecture/module_size_budget.toml SHA-256 is 07fb68f704cd4f11b7fa57683ea4ee41371319529e4248de27ab136b9caf2682 at both the slice base and current worktree; no budget, threshold, owner, or target date changed.

The physical count is measured from the actual checker source, not a marker: base was 1,627 lines and current is 1,564 against the unchanged 1,580 report-only ceiling. The five focused tests include the physical ceiling, both ratchet thresholds, a missing budgeted path, and logical-line counting with blank/comment lines.

The generic validation-tooling contract uses the complete tools/quality/validation/**/*.py pattern and enumerates members with architecture_report_only_contracts._validation_tooling_paths. A Git-object-to-worktree census found 198 Python files at the exact base and 199 currently; the only added member is tools/quality/validation/package_import_size_ratchet.py, and there were no removed paths. The new helper is present in the generic denominator at 72 logical lines, below the 1,000-line warning threshold. The checker is itself a budgeted member and its logical count falls from 1,476 to 1,421.

The full generic denominator also exposes 53 unbudgeted modules above 1,000 logical lines at both the base and current boundary; the over-warning total is 62 at both. The set difference is empty in both directions, so this delta adds no unbudgeted-over-warning path. I do not label the aggregate red P41-inherited: the changed checker is itself a member of that gate's complete input denominator, so the zero-intersection condition is not met. The broader generic gate is not claimed green.

## Behavioral controls and deciding outputs

From policy-engine, I independently ran these five focused cases:

    PYTHONPATH=src:. .venv/bin/pytest -q \
      tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase7_module_size_ratchet_rejects_growth \
      tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase7_module_size_ratchet_rejects_report_only_limit_growth \
      tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase7_module_size_ratchet_reports_missing_budgeted_module \
      tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase6_7_module_size_ratchet_counts_logical_code_lines \
      tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase6_7_import_gate_source_fits_declared_physical_line_ceiling

Result: exit 0, five passed. Full stdout is LOCAL/reviews/raw/import-gate-size-delta-focused.log @ 4d2df7a96ce4a667da3ccf295f2d16c728a65ed0e861a3baa919f7bb469b02b5.

The generic outside-selector test was also run independently:

    PYTHONPATH=src:. .venv/bin/pytest -q tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py::test_phase6_7_unbudgeted_large_validation_script_is_contract_error

Result: exit 0, one passed. It exercises the generic size contract on a large validation file not registered in the per-file module budget. Output is LOCAL/reviews/raw/import-gate-size-delta-generic-outside-selector.log @ 423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d.

The corrupt-threshold/property-removal control used a temporary two-logical-line module and budget markers current_lines=3, report_only_limit_lines=1. The real canonical wrapper emitted the exact report-only Finding with current=2 limit=1 and the original Finding class. With the extracted count_lines property monkeypatched to return zero while the same budget markers remained present, the wrapper emitted no finding; the existing expected-finding test detects that removal. The control exited 0. Output is LOCAL/reviews/raw/import-gate-size-delta-remove-property-control.log @ 5e03bea4112ceae0d7ec8b75d87c375903e926a65145a8144f1b9a12f95ee1de.

Complete denominator evidence:

- Base/current Git-object comparison: LOCAL/reviews/raw/import-gate-size-delta-baseline-vs-current.log @ 5341f25398e3d570a11b4ad2eafa4290b90e8eb75f3cb18d4361396ef06f4801.
- Complete source-path set comparison: LOCAL/reviews/raw/import-gate-size-delta-denominator-path-diff.log @ 5c38c2560ae4f24638a17efc0ff07befe8c022778e086341c8c77d5412651d7e.
- Current generic scope scan, including the 53 unchanged unbudgeted paths: LOCAL/reviews/raw/import-gate-size-delta-denominator.log @ 32dd732bcb96d4efd7709d065e44754917f9deb6669f88d78ad154bf5550f1d8.

Ruff check and format check were run with the product-local environment against all three changed paths:

    .venv/bin/python -m ruff check tools/quality/validation/check_package_import_gates.py tools/quality/validation/package_import_size_ratchet.py tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py
    .venv/bin/python -m ruff format --check tools/quality/validation/check_package_import_gates.py tools/quality/validation/package_import_size_ratchet.py tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py

Both exited 0. Outputs: LOCAL/reviews/raw/import-gate-size-delta-ruff-check.log @ 82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18 and LOCAL/reviews/raw/import-gate-size-delta-ruff-format.log @ eee76f865de5a9f2456950f710ae5d5f9b5bd0ea02aa54f614c5eed6642a0bfd.

## Remaining boundary

The full build_report/CLI integration test is UNRUN for this independent review. The author reports a prior attempt interrupted after 47.71 seconds; it did not pass. I did not rerun it under the no-heavy-suite instruction. This review establishes the helper behavior, real canonical wrapper behavior, Finding identity, generic denominator behavior, and unchanged source route, but not a full CLI/native acceptance result. The broader 53-path generic module-size debt and whole-candidate integration remain for root/G review. Formal G closure IDs: none.
