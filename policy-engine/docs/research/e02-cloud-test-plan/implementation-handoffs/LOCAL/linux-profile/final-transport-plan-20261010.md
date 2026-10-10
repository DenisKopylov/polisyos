# Final-source Linux transport and consumer-wave plan

Captured 2026-10-10. Preparation only: no source transport, checkout, build, package install, product test, or cleanup was performed.

## Freeze and current worker

Root has not supplied final source inputs. The inspected host branch is **codex/e02-unified-local-20261009**, candidate HEAD **7b1b50dd1b36d8a67927775e68560eaf4842dbe1**, tree **9bad8150d5efa1d2186f0188041de81ef13f15bf**, with tracked WIP. These are not execution identities. The script requires root's exact attached branch, full SHA, and tree, and fails on mismatch or tracked source edits.

The isolated e02-local worker was checked only with its dedicated COLIMA_HOME, dedicated DOCKER_CONFIG, and explicit colima-e02-local Docker context. Existing container e02-local-worker-provision is running on image digest ghcr.io/astral-sh/uv@sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f. It has only the existing named uv-pythons, uv-cache, and /scratch volumes; no source, host bind, or production mount. It remains 2 CPUs, configured 3 GiB VM RAM, and 2,306,867,200-byte (2,200 MiB) container memory limit. No other container is running.

The data disk is 12 GiB; see [capacity-growth-receipt-20261010.md](capacity-growth-receipt-20261010.md) for device/partition/filesystem identities. Current /scratch: 12,277,956 KiB total, 4,664,312 used, 7,010,204 free (6.685 GiB). Cgroup current 289,017,856 B; memory event counters and pressure averages zero. Existing profiles: uv 0.9.21, app Python 3.14.0/Hatchling 1.27.0/pytest 9.0.2, DoWhy Python 3.12.12/DoWhy 0.14/pytest 9.0.2. Read-only pip checks passed for 161 and 52 packages. /workspace/polisyos does not exist. Remeasure after transport and immediately before root grants a heavy slot; free bytes are not a capacity guarantee.

The installed environment recipes match these current hashes; the prepared script rejects a changed freeze lock instead of silently reusing them:

~~~text
policy-engine/pyproject.toml                   b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267
policy-engine/uv.lock                          e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463
policy-engine/workers/dowhy-014/pyproject.toml  df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447
policy-engine/workers/dowhy-014/uv.lock         c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a
policy-engine/workers/dowhy-014/.python-version 7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16
~~~

## Transport and Q2

Prepared script: [final-source-linux-wave.sh](raw/final-source-linux-wave.sh), SHA-256 **4638c05015d80b0b39a09755fd383a179191169ecd23c68ab18f250e2659c35d**. `bash -n` and its isolated `self-test-copy-decisions` mode passed. The self-test exercised eight tracked/ignored, exact/missing/changed/symlink decisions without Git, Docker, or filesystem changes. The transport and Q2 modes have not been run.

After root supplies the final four inputs:

~~~sh
source_checkout=/absolute/path/root-supplies-at-freeze
freeze_branch=ROOT_SUPPLIED_ATTACHED_BRANCH
freeze_sha=ROOT_SUPPLIED_FULL_40_CHARACTER_SHA
freeze_tree=ROOT_SUPPLIED_FULL_40_CHARACTER_TREE
bash /absolute/path/to/LOCAL/linux-profile/raw/final-source-linux-wave.sh \
  transport "$source_checkout" "$freeze_branch" "$freeze_sha" "$freeze_tree"
~~~

Transport makes one shallow bare file-URL clone of the attached branch, checks commit/tree/shallow boundary, copies that Git object store into the existing worker at /scratch/e02-$freeze_sha.git, and creates one attached --shared checkout at /workspace/polisyos. It verifies branch attachment, exact SHA/tree, shallow status, clean tracked files, and the object alternates link. It does not move host HEAD, synthesize history, reset, mount source, change Docker defaults, or clean existing paths. Any occupied destination is a hard stop.

The five small Q2 inputs use this checkout-local handoff layout:

~~~text
/workspace/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/
  installed-wave-manifest.json
  raw/run.py
  raw/timeout_driver.py
  raw/supplemental_run.py
  raw/supplemental-manifest.json
~~~

This relative structure is required: timeout_driver loads run.py beside itself and the primary manifest two directories above; supplemental_run loads run.py beside itself, the primary manifest in the parent, and its manifest beside itself. These are local runner/test inputs, not a second source tree. The runner source preflight checks tracked edits only.

At inspected candidate HEAD 7b1b50d, the primary manifest is already tracked and its Git blob hashes to the pinned SHA below. Transport verifies the tracked file against both its frozen Git blob and expected content hash, then reuses it without overwrite. The other four inputs are ignored `raw/` files, absent from that commit. For each input the script checks the attached checkout's tracked/ignored state: it reuses exact known bytes already at the expected path, copies an absent ignored input and verifies it, and refuses changed, non-file, symlink, or non-ignored untracked targets. Thus the tracked-manifest case cannot trip an unconditional “target must be absent” check. Final-freeze state is checked again at transport time; this candidate observation does not bind the eventual freeze.

Copy-time content pins are:

~~~text
run.py                     5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932
timeout_driver.py          eaa9c3f2355b05e2f55753da4ba297ca6f137a9ba7f4699e456d4ad872339a0a
installed-wave-manifest    ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7
supplemental_run.py        1e43531fce5d5ceb643349612823366f42702258efca598dec1d20feb524637e
supplemental-manifest      614013d0c2f3761012782405dbb1aa67abe16e15c37e849939de94ae6dd24b57
~~~

The script's `self-test-copy-decisions` mode covers tracked exact reuse, tracked missing/changed/symlink refusal, absent ignored copy, ignored exact reuse, and changed/symlink untracked refusal. It makes no temporary files and has no transport side effects.

The primary recipe hash is e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e. Timeout driver pins runner and manifest; the supplement pins the same primary inputs. Changed inputs require reconciliation/review, never a bypass.

After source transport, root must admit the one serialized heavy slot. The script's q2 phase requires E02_ROOT_HEAVY_SLOT_GRANT equal to the full final SHA:

~~~sh
E02_ROOT_HEAVY_SLOT_GRANT="$freeze_sha" \
  bash /absolute/path/to/LOCAL/linux-profile/raw/final-source-linux-wave.sh \
  q2 "$freeze_branch" "$freeze_sha" "$freeze_tree" attempt-01
~~~

It passes existing /scratch/root-venv Python 3.14.0 and /scratch/dowhy-venv Python 3.12.12 to timeout_driver.py; no second worker environment is provisioned. Primary Q2 executes exactly 91 frozen baseline cases plus six dependency-profile and three installed-worker selectors = 100 collected/executed IDs for each of three profiles: source-wheel, rebuilt-sdist-wheel, rebuilt-gcp-archive-wheel. The first profile is measured without an arbitrary timeout; later timeouts require successful reconciliation of the preceding profile.

Only after a passing primary run receipt is parsed and bound to the freeze does the script invoke supplemental_run.py. It executes six additional selectors once per each of the same three profiles. The supplement validates the 100 primary IDs, receipts, assets and installed origins, then reinstalls each wheel sequentially into the primary run's existing consumer venv. No second consumer venv is created. It measures supplement profile 1 without a bound and later profiles at twice the last successful profile duration.

Direct driver streams and every package/test output remain under /scratch/e02-q2-runs/$freeze_sha/attempt-01. Neither runner has cleanup. The script refuses an existing attempt. Current run estimate was about 1.5 GiB with the existing worker supplied, but final bare pack, GCP archive, outputs, pytest temp, logs, and inode peak remain unbounded or unmeasured. The script reports disk and cgroup observations before/after. Root must review measured capacity/reserve before setting the heavy-slot grant.

## Linux-native B212/F, LA-029, DFK

Earlier prepared recipes are in [README.md](README.md); none ran on the final freeze. The complete child-output hook copied from its README section is [raw/sitecustomize.py](raw/sitecustomize.py), SHA-256 **4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2**. It captures complete Popen stdout/stderr bytes plus command and digest metadata. The transport phase copies this exact hook to /scratch/e02-child-capture/$freeze_sha/sitecustomize.py and verifies its hash. Each witness copies it to a new per-attempt folder, sets E02_CAPTURE_DIR only for that command, and never reuses a capture path.

B212/F run the two real consumers in tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py sequentially in one pytest process, with the actual 3.12.12 worker and fresh 3.14 reader:

~~~sh
E02_CAPTURE_RUN=/scratch/e02-child-capture/$freeze_sha/attempt-01/dowhy
test ! -e "$E02_CAPTURE_RUN"
mkdir -p "$E02_CAPTURE_RUN/logs"
cp /scratch/e02-child-capture/$freeze_sha/sitecustomize.py "$E02_CAPTURE_RUN/sitecustomize.py"
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs" E02_CAPTURE_LANE=dowhy
export E02_TEST_DOWHY_WORKER_PYTHON=/scratch/dowhy-venv/bin/python
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src"
cd /workspace/polisyos/policy-engine
/scratch/root-venv/bin/python -m pytest -q \
  -o cache_dir=/scratch/e02-pytest-cache-$freeze_sha-attempt-01-dowhy \
  --basetemp=/scratch/e02-pytest-tmp-$freeze_sha-attempt-01-dowhy \
  --benchmark-storage=file:///scratch/e02-benchmarks-$freeze_sha-attempt-01-dowhy \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py \
  -k 'test_real_worker_job_cas_fresh_python314_reader or test_real_estimate_point_only_survives_parent_cas_and_reader' \
  > "$E02_CAPTURE_RUN/dowhy.pytest.stdout" \
  2> "$E02_CAPTURE_RUN/dowhy.pytest.stderr"
~~~

Expected exit 0 and exactly two passing tests. B212 retains its point estimate in typed CAS while CI/SE and interval stay absent and the result remains non-gate-eligible. F invokes the actual worker, persists typed report/evidence CAS, and GETs/reconciles via fresh Python 3.14. These use synthetic data only.

LA-029 uses the real ops entrypoint and Linux server guard. The ops consumer sets POLISYOS_RUN_INTEGRATION=1 for its C7 child internally. Use a new artifact root and preserve the guard:

~~~sh
E02_CAPTURE_RUN=/scratch/e02-child-capture/$freeze_sha/attempt-01/la029
UKOPS_ROOT=/scratch/ukraine-artifacts-$freeze_sha-attempt-01
test ! -e "$E02_CAPTURE_RUN" && test ! -e "$UKOPS_ROOT"
mkdir -p "$E02_CAPTURE_RUN/logs"
cp /scratch/e02-child-capture/$freeze_sha/sitecustomize.py "$E02_CAPTURE_RUN/sitecustomize.py"
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs" E02_CAPTURE_LANE=la029
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
cd /workspace/polisyos/policy-engine
POLISYOS_SERVER_EXECUTION=1 \
UV_PROJECT_ENVIRONMENT=/scratch/root-venv UV_NO_SYNC=1 UV_FROZEN=1 \
PYTEST_ADDOPTS="-o cache_dir=/scratch/e02-pytest-cache-$freeze_sha-attempt-01-la029 --basetemp=/scratch/e02-pytest-tmp-$freeze_sha-attempt-01-la029 --benchmark-storage=file:///scratch/e02-benchmarks-$freeze_sha-attempt-01-la029" \
/scratch/root-venv/bin/python tools/ops_runners/ukraine_data/validate_part_a.py \
  --workspace-root /workspace/polisyos/policy-engine --root "$UKOPS_ROOT" \
  > "$E02_CAPTURE_RUN/la029.manifest.stdout" \
  2> "$E02_CAPTURE_RUN/la029.manifest.stderr"
~~~

Expected exit 0; parse the typed summary and part_a_gate_manifest.json and require status=passed, server_only=true, passed=true, skipped=false. The captured child command must be exactly uv run pytest -q tests/integration/test_c7_synthetic_full_pipeline.py, and full child streams must reconcile to their hook metadata. Also retain README's no-marker negative control: when POLISYOS_SERVER_EXECUTION is unset, actual assert_server_execution_allowed raises LocalExecutionBlockedError before any pytest launch.

DFK's current unit test mocks collect_census, so use a tiny guest-native Git fixture with a unique, never-reused path. Do not run the old shutil.rmtree prototype; this command never deletes:

~~~sh
E02_CAPTURE_RUN=/scratch/e02-child-capture/$freeze_sha/attempt-01/dfk
DFK_REPO_ROOT=/tmp/dfk-mini-$freeze_sha-attempt-01
test ! -e "$E02_CAPTURE_RUN" && test ! -e "$DFK_REPO_ROOT"
mkdir -p "$E02_CAPTURE_RUN/logs"
cp /scratch/e02-child-capture/$freeze_sha/sitecustomize.py "$E02_CAPTURE_RUN/sitecustomize.py"
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs" E02_CAPTURE_LANE=dfk
export DFK_REPO_ROOT E02_CAPTURE_RUN
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
/scratch/root-venv/bin/python - <<'PY'
import os
import subprocess
from pathlib import Path

root = Path(os.environ["DFK_REPO_ROOT"])
assert not root.exists()
root.mkdir(mode=0o700)
def git(*args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)

git("init", "--quiet")
raw_name = bytes([98, 97, 100, 95, 255, 46, 106, 115, 111, 110])
name = os.fsdecode(raw_name)
(root / name).write_bytes(bytes([123, 125, 10]))
git("add", "--", name)
git("-c", "user.name=E02 fixture", "-c", "user.email=e02-fixture@example.invalid",
    "commit", "--allow-empty", "-m", "raw filename fixture")
assert git("ls-files", "-z").stdout == raw_name + bytes([0])
PY
cd /workspace/polisyos/policy-engine
/scratch/root-venv/bin/python -m tools.quality.validation.schema_fqn_census \
  --repo-root "$DFK_REPO_ROOT" \
  > "$E02_CAPTURE_RUN/dfk.cli.stdout.json" \
  2> "$E02_CAPTURE_RUN/dfk.cli.stderr"
~~~

The filename is exactly 10 raw bytes (bad_, FF, .json); content is 3 bytes ({} plus newline). Expected CLI JSON is complete_for_selected_local_text_inputs with one tracked/selected/read path equal to os.fsdecode of that byte name, one successful read, zero unreadable/unsupported paths, complete Git/read receipts, and JSON escaping the invalid byte as U+DCFF. Reconcile all fixture and CLI Git subprocess records with the captured stream files, sizes, and hashes. This retains one synthetic file and reads no production corpus.

## Pattern and acceptance

Relevant patterns: P29 (real consumer path), P35 (exact ID denominators), P37/P38 (actual freeze/receipt predicate, not candidate or exit-code proxy), P40 (DFK same-class deeper escape), P41 (red replay at the correct frozen source). B212/F and LA-029 remain verification_missing until the exact native consumers pass on final freeze. DFK is the same raw-byte filename class one level deeper; its smallest closer is the real Git/CLI fixture, falsified by a lost surrogateescaped path, unreadable file, incomplete receipt, or invalid JSON. Q2 and supplement remain pending final freeze, input review, capacity admission, and root's serialized heavy slot. No production currentness or E02 closure is claimed.

