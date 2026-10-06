# Checkpoint 10 affected-consumer test receipt

Candidate `acdc3536f93f085d665a7b53460935525373d015` (`ff7cc9e6bb2cb0d826d977e7298020ee7af6e5cc`) was tested from an isolated `git archive`. Every tracked entry matched by Git blob hash and file mode: 13777 blobs, 0 mismatches. The integration checkout remained clean on `codex/e02-integration` at the candidate SHA.

The complete `tests/unit/runtime/http/test_control_plane_store.py` selector passed: 59 passed, 0 failed, 0 errors, 0 skipped. Harness wall time was 22.841s; peak child RSS was 1,022,853,120 bytes. Pytest emitted one non-failing unknown `cache_dir` configuration warning.

The three B38 implementation/test paths have identical Git blobs at the B38 candidate and checkpoint 10. Runtime modules resolved from the isolated candidate; their source hashes were stable before and after the wave. The helper `tests._helpers.policy_design_case_projection` resolved to the primary checkout path during preflight, but its bytes match the archived candidate helper exactly (same SHA-256); this origin detail is retained in the JSON receipt.

Disk available: 26.005 GiB before archive, 25.548 GiB after archive/before test, and 25.630 GiB after test.

`sqlalchemy` and `psycopg` were absent. PostgreSQL-backed consumers were not run; these SQLite unit tests do not close the finding. No files were deleted or moved to Trash.

Complete logs and machine-readable evidence are listed with SHA-256 below.
- `checkpoint10-consumers-acdc-archive-verification.json` — 417 bytes, SHA-256 `ab3d4c9ff98bc1569a12787d899689bd5ff10525941da4872c8e76e863bfa57d`
- `checkpoint10-consumers-acdc-preflight.json` — 7952 bytes, SHA-256 `a1851d5a8e82750c8a8fd31763d6c6659f405e49b3434d6a29df8149d2cac77b`
- `checkpoint10-consumers-acdc-run-preflight.json` — 9194 bytes, SHA-256 `012209743762a5d3a8eb18b8299fe07c8dc20aa385291a60a002c56e84c47c45`
- `checkpoint10-consumers-acdc-command.json` — 2349 bytes, SHA-256 `a28cc3394ed2fbd91648fbcd39dec85a9b497853e1b9bfed95873ef7a2ea39cf`
- `checkpoint10-consumers-acdc-result.json` — 14120 bytes, SHA-256 `9cdb60f6aa4a291936688e5378c06e403526456cf9616f285c7af1b4fb27a50f`
- `checkpoint10-consumers-acdc.stdout` — 622 bytes, SHA-256 `8f6f12fa2bea61f1d83925c735a07e71bb8dfaa27409591bba00781b67c09e96`
- `checkpoint10-consumers-acdc.stderr` — 0 bytes, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `checkpoint10-consumers-acdc.junit.xml` — 10258 bytes, SHA-256 `33bf1e2c953aeff1239219b4ed48dcb6348f66a7b091c216cfa47629f1264920`
- `checkpoint10-consumers-acdc-b38-source-equivalence.json` — 976 bytes, SHA-256 `b405c6f3869f92b6948b25d0cbbe75018aeb4f7039296768f07375ba3e0eda4f`
- `run-checkpoint10-consumers-acdc.py` — 5964 bytes, SHA-256 `55399a4e31fc712c9d241872874b1eccadcefde9846f920ec83b880912e79bcb`
