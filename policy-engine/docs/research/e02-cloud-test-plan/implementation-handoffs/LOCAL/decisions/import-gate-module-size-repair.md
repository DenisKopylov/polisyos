# Package-import gate module-size repair

Status: scoped extraction complete; ready for parent review. Source boundary supplied by root: `9e02a9f49c8b01026327a9f7c7e18711b13a96f` (tree `881a950dccb7cdefacc636515aa7dd2bceadf928`). No Git operations were run.

## Property and P40 bucket

The source file must fit the existing 1,580 physical-line ceiling recorded for `tools/quality/validation/check_package_import_gates.py`, while the public fail-closed package-import CLI retains the same finding model, summary keys, JSON shape, and logical-line ratchet semantics. This is a NEW class relative to the preceding docs-freshness work: a physical module-size overage, not the earlier baseline-admission class. The extraction widens one shared helper boundary and does not change the registry, limit, deadline, or the gate's logical-line predicate.

Before extraction, the checker was 1,627 physical lines, against 1,580. Its existing logical counter returned 1,476 lines and `_check_module_size_ratchet` emitted no finding. The physical-ceiling test reproduced `1627 <= 1580` as false; see `LOCAL/raw/import-gate-module-size-repair/physical-ceiling-red.stdout@ac2aecbde21bd7756bd04954595fd2b7391eee165e317acd385c665fc49a86f6` (stderr was empty; exit record is `physical-ceiling-red.exit@4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`). Baseline module-size behavior controls passed before extraction: current-budget growth and logical-line counting; see `base-behavior.*`.

## Change and exact footprint

The canonical checker remains the public CLI owner. One adjacent module, `tools/quality/validation/package_import_size_ratchet.py`, now holds the module-size ratchet and its shared TOML, integer, date, and logical-line helpers. The canonical checker injects its original `Finding` dataclass into the extracted ratchet, preserving the model's original module identity and serialized shape. The checker is now 1,564 physical lines. The module-size registry and gate command are unchanged.

Changed source and tests:

- `tools/quality/validation/check_package_import_gates.py`
- `tools/quality/validation/package_import_size_ratchet.py`
- `tests/repo_quality/architecture/test_repository_best_in_class_phase6_1_import_gate_conversion.py`

No README, release fragment, module-size budget, generator, or other checker was changed.

## Evidence

The deciding bounded regression command ran five tests: current-budget growth, report-only-limit growth, missing budgeted module, logical-line counting, and the physical ceiling. Result: **5 passed**. Full stdout, stderr, and exit code are in `LOCAL/raw/import-gate-module-size-repair/final-focused-tests.*` (stdout SHA-256 `bd5201fad773316bbfda2cfee7833ff2d8db356db81550c537f47ba44de0ed2d`; stderr empty; exit SHA-256 `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`). Ruff check and format check passed for the three changed paths; full outputs are in `final-ruff-check.*` and `final-ruff-format.*`. A direct post-change probe reports 1,564 physical lines, 1,421 logical lines, and no module-size finding for the canonical checker; see `final-ratchet-probe.*`.

The existing full `build_report` integration test was started with the focused cases but stopped after 47.71 seconds under the no-heavy-suite constraint. Its complete interruption output is retained in `post-extraction-tests.*`; it is not claimed as passing. No full CLI/native suite result is claimed; root may include it in the requested final wave.
