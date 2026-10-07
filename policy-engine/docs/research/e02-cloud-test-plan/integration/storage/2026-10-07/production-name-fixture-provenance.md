# Production-named fixture layout: source trace and bounded claim

The pre-cleanup metadata walk observed 37 non-followed `authority/repo/production_data` directory names beneath A full-queue pytest `basetemp`/`pytest-basetemp`. It used `os.walk(..., followlinks=False)` and excluded symlink directories before enumerating these paths; only direct child names (`canonical`) and directory inode/device were captured. No nested payload was traversed, hashed or copied for this census. The later external Trash cleanup prevents a new inspection of these historical members.

Pinned source: `93d62af8eb037fa37cb0254ad38285507b26a86a`.

- `policy-engine/tests/integration/core_runtime/test_e02_empirical_member_intake.py`: `_four_ratio_rows` creates four literal rows and `_activate_scenario` calls the fixture/authority producer.
- `policy-engine/tests/unit/data_forge/domains/catalog/knowledge/test_overlay.py`: `_scenario_with_raw_rows` calls `_real_epoch_scenario` with the provided fixture rows.
- `policy-engine/tests/unit/runtime/quality/test_acquisition_executor.py`: `_authority` creates an isolated catalog fixture and a synthetic source/rights authority, then calls `_write_l5(repo_root)`. `_write_l5` creates parent directories and writes a literal schema/coverage/trust JSON.
- `policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py`: `DEFAULT_L5_MEASUREMENT_REGISTRY` resolves to `production_data/canonical/local_data_20260501/ukraine_server_support_20260410/runtime_calibration_internals/calibration/d2/measurement_registry.json`. This explains why the fixture creates a production-named directory, without reading the real production tree.

Established: the test factory constructs that named fixture layout and the metadata paths match its isolated pytest scope. **Not established:** independent complete payload provenance for every nested historical member, or absence of any additional member below those 37 directories. The cleanup report therefore makes no such set-level zero claim. The actual primary production-data path was outside every transferred workspace/cache/log/archive path and was not followed or moved. No production/data-dependent finding is closed by this source trace.
