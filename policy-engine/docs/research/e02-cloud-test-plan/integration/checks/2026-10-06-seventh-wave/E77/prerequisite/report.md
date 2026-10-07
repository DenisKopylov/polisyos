# Bounded DoE dependency overlay prerequisite

**Outcome:** the lock-pinned dependency overlay is prepared under this ignored `_build` area and imports successfully with the existing G Python 3.14.3 environment. The DoE selector was **not run**; B16 still owns the active local test slot, so G can schedule the test only after that slot is free. Package imports establish dependency availability, not DoE test correctness or numerical-property closure.

## Source and install

G remained on `codex/e02-integration` at `127dc7ab8365d29eb656fe32c0c894f6cc971286`. The candidate E source `70c4a14fc872f5ef66437d958ba63884ecdda168:policy-engine/uv.lock` and G's current `policy-engine/uv.lock` have the same SHA-256: `e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463`. The table below records the exact wheel URLs, hashes, and sizes read from that lock:

| Distribution | Wheel | Lock SHA-256 | Wheel bytes |
|---|---|---|---:|
| SALib 1.5.2 | `salib-1.5.2-py3-none-any.whl` | `6f4b6bebc1eeed1d081c8f951fa8c2ad7b0cd8a7159d206af48ef137cc806c43` | 780,059 |
| multiprocess 0.70.19 | `multiprocess-0.70.19-py314-none-any.whl` | `e8cc7fbdff15c0613f0a1f1f8744bef961b0a164c0ca29bdff53e9d2d93c5e5f` | 160,318 |
| dill 0.4.1 | `dill-0.4.1-py3-none-any.whl` | `1e1ce33e978ae97fcfcff5638477032b801c46c7c65cf717f95fbc2248f79a9d` | 120,019 |

The exact URL pins are in `1800-doe-prerequisite/requirements.txt`. The installer was uv 0.10.6 and invoked with `--target`, `--no-deps`, `--require-hashes`, `--only-binary :all:`, and the G Python 3.14.3 interpreter. `UV_CACHE_DIR` pointed to `1800-doe-prerequisite/uv-cache` and `TMPDIR` to `1800-doe-prerequisite/tmp`; no global cache or environment setting was changed. The command, cwd, and environment overrides are captured in `1800-doe-prerequisite/command.json`. Full stdout, stderr, and exit status are retained as `stdout.txt`, `stderr.txt`, and `install-result.json`: exit status 0, elapsed 0.685 s, stderr empty. uv reports all three exact direct wheels installed.

The `--require-hashes` install used the lock hashes as its artifact check. uv produced installed dist-info and `direct_url.json`; these metadata URLs retain the exact wheel source, while `direct_url.json` itself does not encode the lock hash. Each installed `RECORD` is present and its listed file hashes/sizes were checked against the target files: SALib 61/61 hashed entries, multiprocess 55/55, and dill 56/56; no missing files or mismatches. The full per-module metadata, origins, RECORD hashes and entry checks are in `runtime-profile-attempt2.stdout.txt`.

## Runtime profile and limits

With overlay prepended to the G venv, imports of `SALib`, `multiprocess`, `dill`, `numpy`, `scipy`, `pandas`, and `matplotlib` all exited 0. The first profile attempt exited 1 because its harness canonicalized the venv's Python symlink to the base interpreter, omitting venv site-packages; stderr records `ModuleNotFoundError: numpy`. The corrected second attempt kept the `.venv/bin/python` symlink and succeeded in 2.092 s. Both commands and outputs are retained; this was a harness-path correction, not a package import failure.

| Module | Version | Import origin |
|---|---|---|
| SALib | 1.5.2 | `1800-doe-prerequisite/overlay/SALib/__init__.py` |
| multiprocess | 0.70.19 | `1800-doe-prerequisite/overlay/multiprocess/__init__.py` |
| dill | 0.4.1 | `1800-doe-prerequisite/overlay/dill/__init__.py` |
| NumPy | 2.3.5 | G `.venv/lib/python3.14/site-packages/numpy/__init__.py` |
| SciPy | 1.16.3 | G `.venv/lib/python3.14/site-packages/scipy/__init__.py` |
| pandas | 2.3.3 | G `.venv/lib/python3.14/site-packages/pandas/__init__.py` |
| matplotlib | 3.10.8 | G `.venv/lib/python3.14/site-packages/matplotlib/__init__.py` |

Runtime profile and RECORD verification command/output/status are in `runtime-profile-attempt2-command.json`, `runtime-profile-attempt2.stdout.txt`, `runtime-profile-attempt2.stderr.txt`, and `runtime-profile-attempt2-result.json`. No test selector, production data, or SALib sampling/analyzing operation was run.

The measured unique-inode allocated footprint across only the task's `overlay`, `uv-cache`, and `tmp` roots is **7,462,912 bytes** (6,571,792 logical bytes), below the 30 MiB cap. Before install those exact three roots had zero files/bytes. Final per-root counts and totals are in `footprint-final.json`; `tmp` remains empty. This includes no claim about the global disk or unrelated caches.

All outputs are ignored by `policy-engine/.gitignore` (`_build/`). The tracked tree and refs were not changed; the branch remained at the G HEAD above. This report is also ignored.
