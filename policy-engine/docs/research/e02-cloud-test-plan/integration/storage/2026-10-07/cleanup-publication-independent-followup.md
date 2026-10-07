# Independent delta review — storage correction at G 2f9c6f6

**Verdict: GO for this documentation delta.** Reviewed immutable `2f9c6f6cf9c088676e8aec74b8f5a3090b3fc22f` (parent `591359ab692207a6356d7773c07ce8db97f42a02`). Its exact two-file delta changes one README claim and adds `production-name-fixture-provenance.md`; no source or test paths changed. `git diff --check` passes and all ten local README links resolve. This supersedes the HOLD in `cleanup-publication-independent.md`; the other independent review findings carry forward unchanged.

## Source trace verified

The original finding asked how a pytest `authority/repo/production_data` directory could be attributed to the synthetic fixture. At pinned source `93d62af8eb037fa37cb0254ad38285507b26a86a`, the chain now documents and source confirms:

1. The empirical-member tests call `_activate_scenario`; their `_scenario_with_raw_rows` helper delegates to `_real_epoch_scenario` and the pinned acquisition-executor fixture. The four retained JUnit receipts report those empirical-member cases under `tests.integration.core_runtime.test_e02_empirical_member_intake`.
2. `_authority` sets `repo_root = tmp_path / "repo"` and calls `_write_l5(repo_root)` (test source lines 528–604). `_write_l5` joins `repo_root` with the imported `DEFAULT_L5_MEASUREMENT_REGISTRY`, creates its parent directories, and writes a literal schema/coverage/trust JSON (lines 494–525); it reads no production file.
3. At the same pinned commit, `acquisition_authority.py` defines that constant as `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/measurement_registry.json` (lines 73–77). This establishes why the factory creates a production-named directory inside each isolated pytest fixture repo. The test source SHA-256 matches the recorded inventory (`cd0e48bda966f5f4453371b1efac904a48c886300a3cc020586052f803f743a9`).

The exact directory inventory contains 37 entries across four pytest basetemp roots and records `canonical` as the immediate child name. The revised README and source-trace note now stop at the justified boundary: no nested payload was read, complete provenance for every nested historical member is `not_established`, and there is no claim of set-level absence. The actual production primary was independently verified outside the 83 moved source paths; this source trace makes no production-data finding closure.

No fresh test/data replay, file move, ref change, or tracked write was needed or performed. The follow-up review is ignored local evidence only.
