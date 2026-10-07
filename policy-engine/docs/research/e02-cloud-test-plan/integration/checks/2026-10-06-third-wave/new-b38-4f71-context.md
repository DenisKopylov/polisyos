# B38 local verification context

Candidate `4f71e8bbd95225c8d857b2123f7f2fe9fcc5071d` (`d418a555e7883599a3c8c482f5b43a6c7b6f7a50`) was tested from an isolated `git archive` at `/Users/deniskopylov/.codex/worktrees/e02-integration-6971/polisyos/policy-engine/_build/e02-g-continuation-20261006/candidates/new-b38-4f71`. Git blob contents and modes matched for all 13,726 tracked entries (0 mismatches). The integration checkout remained clean at `0346fc656a45ff2cd43d37126992d8ddbb739d10` on `codex/e02-integration`.

Using the existing Python 3.14.3 G virtualenv, candidate `src` first in `PYTHONPATH`, and no dependency installs, two sequential selectors passed: `tests/unit/remediation/test_dur_02_process.py` (20 passed) and `tests/unit/runtime/http/test_control_plane_store.py -k completed_proof_publication` (20 passed, 39 deselected). Total wall time was 135.610 s; maximum child RSS was 1,020,952,576 bytes (about 973.7 MiB). Both runs emitted one non-failing `Unknown config option: cache_dir` warning.

The imported `control_plane_store` and `control_worker` modules resolved from the isolated candidate. Source hashes were stable before/after the wave. Disk free space was 28.671 GiB before archive, 28.216 GiB after archive/before tests, and 27.238 GiB after the wave.

`sqlalchemy` and `psycopg` were absent. These local unit/fixture checks do not cover PostgreSQL or production-data consumers, and do not close the finding. No files were moved to Trash or deleted.

Complete stdout/stderr, JUnit, exact commands, preflight imports/hashes, result JSON and the runner are retained beside this context. SHA-256 receipts:
- `new-b38-4f71-preflight.json` — 4718 bytes, `e94693ef61803534c1de54fb536c2be401fe0aa785cdf9c4a2599cc348c25d2e`
- `new-b38-4f71-command.json` — 3046 bytes, `e80f1ce3b4659cd183e04e064bef9e65c17a83993a6b5718dda54b6d4effee6b`
- `new-b38-4f71-result.json` — 9840 bytes, `e7b89691c49597395307e7b787c938cd9d3b150d4e9de77b971e7fc98dd06fbc`
- `new-b38-4f71-process.stdout` — 634 bytes, `e81c8b8547c7faf115fa11e3897fd6d1f0ab7b6871e3cb905f2feeb861bb5b6f`
- `new-b38-4f71-process.stderr` — 0 bytes, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `new-b38-4f71-process.junit.xml` — 3662 bytes, `e2f18faf4e64755b861d61041c49dc441e105b6a7148f5b3f068466ab9579935`
- `new-b38-4f71-proof.stdout` — 637 bytes, `352698985b06c26540294da60d7da7f715dd08b7cec67b33889b5623ef51fbd4`
- `new-b38-4f71-proof.stderr` — 0 bytes, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `new-b38-4f71-proof.junit.xml` — 3914 bytes, `304855c79e298a8fe7c7ef0dca230e59f04963ec5c56729e1d395cbea510ee27`
- `run-new-b38-4f71.py` — 5648 bytes, `af3052e2b688bd06b59da5c7644d6ef18309d6c3f16d644a527dcb2a7f310a05`
