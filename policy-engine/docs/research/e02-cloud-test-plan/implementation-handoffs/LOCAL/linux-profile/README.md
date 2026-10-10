# E02 local Linux profile

The separate clean macOS host environment for the future browser/API fixture run is documented in [browser-core-host-env.md](browser-core-host-env.md); its complete local command receipt is under `raw/browser-core-install-receipt/`.

Provisioned a local ARM64 Linux runner for the E02 B212/F, LA-029, and DFK follow-up. The VM and Docker context are isolated from any pre-existing Colima or Docker state. No source checkout, production path, or credential was mounted. No repository tests were run.

## Profile and health

Host is `arm64` macOS with 16 GiB RAM. Host disk had 37 GiB free after VM/toolchain setup and 24 GiB at the final dependency-health check. Homebrew installed Colima 0.10.3, Lima 2.2.1, and Docker CLI 29.9.0. The runtime files are under `/Users/deniskopylov/.colima-e02-local`; Docker client state and the profile context are under `/Users/deniskopylov/.docker-e02-local`. Always set both environment variables and use `/opt/homebrew/bin/docker`; `/usr/local/bin/docker` remains the pre-existing broken Docker Desktop symlink.

The successful start command was:

```sh
COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
/opt/homebrew/bin/colima start --profile e02-local --runtime docker \
  --arch aarch64 --vm-type vz --cpus 2 --memory 3 --disk 8 \
  --mount=none --activate=false --ssh-config=false --port-forwarder=none
```

Colima status reports macOS Virtualization.Framework, ARM64, and Docker. The guest is Ubuntu 24.04.4 LTS. It reports 2 CPUs and 2.8 GiB visible RAM (3 GiB configured, no swap). Docker reports `linux aarch64`, server 29.5.2. Docker context listing shows `colima-e02-local` without `*`; the existing `default` remains selected. Profile YAML has `autoActivate: false`, `mounts: null`, `sshConfig: false`, and `portForwarder: none`; `findmnt -t virtiofs` returned no host mounts.

The requested `--disk 8` is the Colima data disk: it is mounted at `/mnt/lima-colima-e02-local`; after both locked environments, 3.3 GiB remains free. Colima separately created its default 20 GiB root filesystem, currently 864 MiB used. If “8 GiB disk” means aggregate root plus data capacity, recreate this profile with an explicit smaller root disk before testing. Host disk remained above the requested 18 GiB reserve.

Docker system usage after toolchain preparation: one 205.4 MiB image and three volumes totaling 158.6 MiB. Volumes are `e02-local-uv-cache`, `e02-local-uv-pythons`, and `e02-local-uv-env`; they belong to the isolated Colima daemon.

## Linux Python toolchain

Pulled the official Astral Debian-slim uv image for `linux/arm64` and retained it by digest:

```text
ghcr.io/astral-sh/uv:0.9.21-debian-slim
ghcr.io/astral-sh/uv@sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f
```

`uv --version` reports `uv 0.9.21`. Its persistent Python install volume contains CPython 3.12.12 and 3.14.0, both executed successfully on Linux ARM64. The worker lock accepts `==3.12.*`; the app `.python-version` says `3.14` and the root lock uses the `==3.14.*` family. An attempt to install 3.14.7 with uv 0.9.21 returned `No download found for request: cpython-3.14.7-linux-aarch64-gnu`; therefore the historical 3.14.7 Linux receipt is not reproduced. DoWhy’s current lock includes AArch64 Linux wheels for NumPy 2.4.6, SciPy 1.15.3, sparseDiffPy 0.6.1, and Statsmodels 0.15.0. The full frozen worker and root dependency profiles have now succeeded for Python 3.12.12 and 3.14.0 respectively.

The repository's documented worker recipe is `uv sync --project workers/dowhy-014 --python 3.12 --frozen`. To install its exact locked environment without source code, only the checked-in worker `pyproject.toml`, `uv.lock`, `.python-version`, plus the root `pyproject.toml`, `uv.lock`, and the lock-referenced `odfpy` wheel were copied into `/recipes` in the isolated `e02-local-worker-provision` container. No source checkout or production path is mounted. The copied recipe SHA-256 values were read back inside the container and match the host values recorded below. The successful recipe-only command was:

```sh
UV_CACHE_DIR=/root/.cache/uv \
UV_PYTHON_INSTALL_DIR=/opt/uv-python \
UV_PROJECT_ENVIRONMENT=/scratch/dowhy-venv \
uv sync --project /recipes/worker --python 3.12.12 --frozen --no-build
```

The first `--offline` attempt failed because `scikit-learn==1.9.1`'s locked `manylinux_aarch64` wheel was not yet cached. The online frozen command completed with 52 packages and no source builds. The root sync also completed with 158 packages; the only source build was the lock-pinned pure-Python `autograd-gamma==0.5.0` wheel (its sdist contains only Python package files and setuptools metadata, no native extension). `uv pip check` passed for both environments. The current worker env occupies 779 MiB, root env 1.1 GiB, uv cache 1.8 GiB, and managed Python install volume 181 MiB. The container is `e02-local-worker-provision` (`88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`), constrained to 2 CPUs and 2200 MiB memory, with the three named persistent uv volumes. After both profiles: 2 CPUs, 2.5 GiB available guest RAM, 3.3 GiB free on the isolated 7.8 GiB data disk, 18 GiB free on the VM root filesystem, and 24 GiB host disk free. The container's idle memory was 251.8 MiB. No tests have run.

The two actual worker consumers to run after that sync are in `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py`:

- `test_real_estimate_point_only_survives_parent_cas_and_reader` (B212): synthetic DGP, default seed 19, 100 rows; invokes the actual DoWhy worker while suppressing only its CI/SE accessors, persists/reopens the typed parent CAS report, retains the point estimate, and requires `numerical_failure` with absent interval/level plus a non-gate-eligible envelope.
- `test_real_worker_job_cas_fresh_python314_reader` (F): seed 19, 500 synthetic rows, JobSpec seed 13; invokes the actual worker via `run_job`, persists typed report/evidence to CAS, then GETs and validates them in a fresh Python 3.14 process. The selected-worker fixture accepts `E02_TEST_DOWHY_WORKER_PYTHON`; it sets `POLISYOS_DOWHY_WORKER_PYTHON` to the supplied absolute worker interpreter. Assertions bind DoWhy `0.14`, worker Python `3.12.*`, actual source ref/hash, report/evidence CAS contents, and the root reader's exact contract.

These are synthetic-only fixtures. No production inputs are needed. The worker protocol caps each JSON request and response at 8 MiB and each launch at 60 seconds. Keep the two tests and the rest of the numerical worker suite inside the one root-reserved heavy slot.

Expected consumer signals: B212 keeps a non-`None` point estimate in CAS despite the deliberately absent CI/SE, while confidence interval/level remain absent and the envelope is not gate eligible. F returns success, point estimate about `2.016134929864521`, a 95% interval about `[1.8265023190563892, 2.2057675406726527]`, and a fresh Python `3.14` reader confirms the persisted report/evidence while preserving `causal_identification_admission_not_established` as the gate-eligibility reason. The worker does not substitute a Python 3.14 or in-process scientific backend.

## Child-process output capture (prepared; not run)

The test consumer captures the DoWhy worker's stdout/stderr as bytes and the fresh Python 3.14 reader's streams as text. The ops runner retains only the last 5,000 stdout characters and 2,000 stderr characters in its typed manifest. To preserve every direct child stream without changing what callers receive, place this `sitecustomize.py` in scratch and add it to `PYTHONPATH` only for the frozen witness commands. It records complete `Popen.communicate()` streams to binary files plus command/return-code/hash metadata; the DoWhy worker JSON stdout returned to the application is unchanged. `subprocess.run` uses `Popen.communicate`, so this also records the UKOPS `uv run pytest` child and DFK Git children.

```sh
mkdir -p /scratch/e02-child-capture
cat > /scratch/e02-child-capture/sitecustomize.py <<'PY'
import hashlib
import itertools
import json
import os
import subprocess
from pathlib import Path

_root = Path(os.environ["E02_CAPTURE_DIR"])
_root.mkdir(parents=True, exist_ok=True)
_lane = os.environ.get("E02_CAPTURE_LANE", "run")
_original_popen = subprocess.Popen
_sequence = itertools.count()


class _RecordedPopen(_original_popen):
    def __init__(self, *args, **kwargs):
        self._e02_key = f"{_lane}-{os.getpid()}-{next(_sequence):04d}"
        self._e02_command = args[0] if args else kwargs.get("args")
        self._e02_recorded = False
        super().__init__(*args, **kwargs)

    def communicate(self, input=None, timeout=None):
        stdout, stderr = super().communicate(input=input, timeout=timeout)
        if not self._e02_recorded:
            out_bytes = self._as_bytes(stdout)
            err_bytes = self._as_bytes(stderr)
            out_path = _root / f"{self._e02_key}.stdout.bin"
            err_path = _root / f"{self._e02_key}.stderr.bin"
            out_path.write_bytes(out_bytes)
            err_path.write_bytes(err_bytes)
            metadata = {
                "command": self._e02_command,
                "returncode": self.returncode,
                "stdout_bytes": len(out_bytes),
                "stderr_bytes": len(err_bytes),
                "stdout_sha256": hashlib.sha256(out_bytes).hexdigest(),
                "stderr_sha256": hashlib.sha256(err_bytes).hexdigest(),
                "text_mode": bool(getattr(self, "text_mode", False)),
                "encoding": getattr(self, "encoding", None),
                "errors": getattr(self, "errors", None),
            }
            (_root / f"{self._e02_key}.json").write_text(
                json.dumps(metadata, ensure_ascii=True, sort_keys=True, default=repr) + "\n",
                encoding="utf-8",
            )
            self._e02_recorded = True
        return stdout, stderr

    def _as_bytes(self, value):
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        return value.encode(
            getattr(self, "encoding", None) or "utf-8",
            errors=getattr(self, "errors", None) or "strict",
        )


subprocess.Popen = _RecordedPopen
PY
```

Run the B212/F consumers only after the source freeze grant. Replace `FROZEN_SOURCE_SHA` with the root-approved source/archive identity; each lane and retry gets its own durable capture directory, so prior evidence is never overwritten:

```sh
export E02_CAPTURE_RUN=/scratch/e02-child-capture/FROZEN_SOURCE_SHA/attempt-01/dowhy
mkdir -p "$E02_CAPTURE_RUN/logs"
cp /scratch/e02-child-capture/sitecustomize.py "$E02_CAPTURE_RUN/sitecustomize.py"
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs"
export E02_CAPTURE_LANE=dowhy
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src${PYTHONPATH:+:$PYTHONPATH}"
export E02_TEST_DOWHY_WORKER_PYTHON=/scratch/dowhy-venv/bin/python
cd /workspace/polisyos/policy-engine
set +e
/scratch/root-venv/bin/python -m pytest -q \
  -o cache_dir=/scratch/e02-pytest-cache-FROZEN_SOURCE_SHA-attempt-01-dowhy \
  --basetemp=/scratch/e02-pytest-tmp-FROZEN_SOURCE_SHA-attempt-01-dowhy \
  --benchmark-storage=file:///scratch/e02-benchmarks-FROZEN_SOURCE_SHA-attempt-01-dowhy \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py \
  -k 'test_real_worker_job_cas_fresh_python314_reader or test_real_estimate_point_only_survives_parent_cas_and_reader' \
  > "$E02_CAPTURE_RUN/dowhy.pytest.stdout" \
  2> "$E02_CAPTURE_RUN/dowhy.pytest.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$E02_CAPTURE_RUN/dowhy.exit"
exit "$status"
```

The expected B212/F pytest result is exit `0` and `2 passed`; the per-test assertions described above are the substantive controls. Apply the same capture setup to LA-029 and DFK. Save direct parent stdout/stderr separately from each child’s `.stdout.bin`/`.stderr.bin` files, then hash every file under that run’s capture directory; do not rely on the manifest's truncated notes or only the terminal summary.

With the exact frozen source present as the attached Git checkout at `/workspace/polisyos` (containing `policy-engine/`) and its root/worker recipe hashes matching the inputs listed below, use the captured B212/F command above. It runs the root consumers with Python 3.14.0, launches the selected worker with Python 3.12.12, and keeps pytest temp/cache plus complete child stdout/stderr under separate scratch paths. The source is transported through the ordinary shallow-bare/attached-checkout path; no source bind mount is used.

## LA-029 and DFK Linux witnesses

LA-029's real Linux consumer is the ops entrypoint `tools/ops_runners/ukraine_data/validate_part_a.py`, which composes the domain `run_part_a_gate` with the ops-owned runner. Run it from the frozen Linux checkout with `POLISYOS_SERVER_EXECUTION=1`, the real default `require_server_for_build=True`, and a distinct scratch build root. It should emit a passed typed manifest after it launches the C7 synthetic integration test with `POLISYOS_RUN_INTEGRATION=1`. The scratch-only `sitecustomize.py` hook retains the nested `uv run pytest` output beyond the truncated notes in the manifest:

```sh
export E02_CAPTURE_RUN=/scratch/e02-child-capture/FROZEN_SOURCE_SHA/attempt-01/la029
mkdir -p "$E02_CAPTURE_RUN/logs"
cp /scratch/e02-child-capture/sitecustomize.py "$E02_CAPTURE_RUN/sitecustomize.py"
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs"
export E02_CAPTURE_LANE=la029
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src${PYTHONPATH:+:$PYTHONPATH}"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
cd /workspace/polisyos/policy-engine
set +e
POLISYOS_SERVER_EXECUTION=1 \
UV_PROJECT_ENVIRONMENT=/scratch/root-venv \
UV_NO_SYNC=1 UV_FROZEN=1 \
PYTEST_ADDOPTS='-o cache_dir=/scratch/e02-pytest-cache-FROZEN_SOURCE_SHA-attempt-01-la029 --basetemp=/scratch/e02-pytest-tmp-FROZEN_SOURCE_SHA-attempt-01-la029 --benchmark-storage=file:///scratch/e02-benchmarks-FROZEN_SOURCE_SHA-attempt-01-la029' \
/scratch/root-venv/bin/python tools/ops_runners/ukraine_data/validate_part_a.py \
  --workspace-root /workspace/polisyos/policy-engine \
  --root /scratch/ukraine-artifacts \
  > "$E02_CAPTURE_RUN/la029.manifest.stdout" \
  2> "$E02_CAPTURE_RUN/la029.manifest.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$E02_CAPTURE_RUN/la029.exit"
exit "$status"
```

Parse both typed manifests from the captured output and scratch root:

```sh
set -e
export E02_CAPTURE_RUN=/scratch/e02-child-capture/FROZEN_SOURCE_SHA/attempt-01/la029
/scratch/root-venv/bin/python - "$E02_CAPTURE_RUN/la029.manifest.stdout" \
  > "$E02_CAPTURE_RUN/la029.assert.stdout" \
  2> "$E02_CAPTURE_RUN/la029.assert.stderr" <<'PY'
import json
import hashlib
import os
import sys
from pathlib import Path

capture = Path(os.environ["E02_CAPTURE_RUN"])
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert summary["status"] == "passed"
assert summary["metrics"]["passed"] is True
assert summary["metrics"]["skipped"] is False
gate_path = Path(summary["outputs"][0]["path"])
assert gate_path.name == "part_a_gate_manifest.json"
gate = json.loads(gate_path.read_text(encoding="utf-8"))
assert gate["status"] == "passed"
assert gate["server_only"] is True
assert gate["passed"] is True
assert gate["skipped"] is False
assert gate["command"] == [
    "uv", "run", "pytest", "-q", "tests/integration/test_c7_synthetic_full_pipeline.py"
]
matches = []
for path in (capture / "logs").glob("la029-*.json"):
    meta = json.loads(path.read_text(encoding="utf-8"))
    if meta["command"] == gate["command"]:
        matches.append((path, meta))
assert len(matches) == 1
child_path, child = matches[0]
stem = child_path.name.removesuffix(".json")
stdout = (child_path.parent / f"{stem}.stdout.bin").read_bytes()
stderr = (child_path.parent / f"{stem}.stderr.bin").read_bytes()
assert len(stdout) == child["stdout_bytes"]
assert len(stderr) == child["stderr_bytes"]
assert hashlib.sha256(stdout).hexdigest() == child["stdout_sha256"]
assert hashlib.sha256(stderr).hexdigest() == child["stderr_sha256"]
print("la029_typed_manifest=passed; linux_server_marker=enabled")
PY
```

The pass control is exit `0` and parsed manifest fields `status="passed"`, `server_only=true`, `passed=true`, `skipped=false`; the recorded command must be the real `uv run pytest -q tests/integration/test_c7_synthetic_full_pipeline.py`.

Prove the Linux marker still blocks execution when absent with this lightweight negative control; it imports the actual guard but never starts pytest:

```sh
set -e
export E02_CAPTURE_RUN=/scratch/e02-child-capture/FROZEN_SOURCE_SHA/attempt-01/la029
env -u POLISYOS_SERVER_EXECUTION \
  PYTHONPATH="/workspace/polisyos/policy-engine/src" \
  /scratch/root-venv/bin/python - \
  > "$E02_CAPTURE_RUN/la029.guard-control.stdout" \
  2> "$E02_CAPTURE_RUN/la029.guard-control.stderr" <<'PY'
import sys
from polisyos.data_forge.domains.ukraine.models import ServerConfig
from polisyos.data_forge.domains.ukraine.server import (
    LocalExecutionBlockedError,
    assert_server_execution_allowed,
)

try:
    assert_server_execution_allowed(ServerConfig(python_bin=sys.executable))
except LocalExecutionBlockedError as error:
    assert "POLISYOS_SERVER_EXECUTION=1" in str(error)
    print("linux_server_marker_guard=blocked_without_marker")
else:
    raise AssertionError("Linux server-only guard admitted execution without its marker")
PY
```

Do not use `tests/unit/remediation/test_udf_04.py` as the Linux witness: its subprocess recorder sets `require_server_for_build=False` and mocks the child command.

The current DFK test `test_dfk_01_cli_json_escapes_surrogate_filename_without_changing_value` monkeypatches `collect_census`; it checks JSON escaping, not filesystem or Git behavior. The minimal actual Linux fixture is a guest-native temporary Git repo containing a tracked raw-byte name `b"bad_\xff.json"` (10 filename bytes) with content `b"{}\n"` (3 bytes). Invoke the real `schema_fqn_census.collect_census` and CLI against that mini repo, then assert Git enumeration returns `os.fsdecode(b"bad_\xff.json")`, the output parses as JSON, and the selected path round-trips unchanged. The expected output is `complete_for_selected_local_text_inputs`, one tracked/selected/read path, zero unreadable paths, and a `read_receipt.complete_verdict` of `true`. Keep this fixture under the Linux container's `/tmp` overlay, not an APFS bind mount. Its path length is 10 raw bytes; the content is 3 bytes, and no production corpus is read. The frozen source invokes `python -m tools.quality.validation.schema_fqn_census --repo-root "$DFK_REPO_ROOT"` from the app root after creating and committing that fixture in its temporary repo. A direct `/bin/sh -c 'command -v git'` check in the pinned Debian-slim uv image exited 127. Git is now installed in the isolated container using the Git apt stanza from `Dockerfile.reproducible` (`apt-get update && apt-get install -y --no-install-recommends git`); the full Dockerfile was not reused because its Python 3.11 base violates the root Python 3.14 contract. The container reports Git 2.47.3.

The prepared guest-native DFK witness input is:

```sh
export E02_CAPTURE_RUN=/scratch/e02-child-capture/FROZEN_SOURCE_SHA/attempt-01/dfk
export DFK_REPO_ROOT=/tmp/dfk-mini-FROZEN_SOURCE_SHA-attempt-01
mkdir -p "$E02_CAPTURE_RUN/logs"
cp /scratch/e02-child-capture/sitecustomize.py "$E02_CAPTURE_RUN/sitecustomize.py"
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs"
export E02_CAPTURE_LANE=dfk
export PYTHONPATH="$E02_CAPTURE_RUN${PYTHONPATH:+:$PYTHONPATH}"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
/scratch/root-venv/bin/python - <<'PY'
import hashlib
import json
import os
import subprocess
import shutil
from pathlib import Path

root = Path(os.environ["DFK_REPO_ROOT"])
if root.exists():
    shutil.rmtree(root)
root.mkdir()
def git(*args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)

git("init", "--quiet")
raw_name = b"bad_\xff.json"
name = os.fsdecode(raw_name)
with (root / name).open("wb") as stream:
    stream.write(b"{}\n")
git("add", "--", name)
git("-c", "user.name=E02 fixture", "-c", "user.email=e02-fixture@example.invalid",
    "commit", "--allow-empty", "-m", "raw filename fixture")
tracked = git("ls-files", "-z").stdout
assert tracked == raw_name + b"\0"
PY

cd /workspace/polisyos/policy-engine
set +e
/scratch/root-venv/bin/python -m tools.quality.validation.schema_fqn_census \
  --repo-root "$DFK_REPO_ROOT" \
  > "$E02_CAPTURE_RUN/dfk.cli.stdout.json" \
  2> "$E02_CAPTURE_RUN/dfk.cli.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$E02_CAPTURE_RUN/dfk.cli.exit"
RECEIPT_PATH="$E02_CAPTURE_RUN/dfk.cli.stdout.json" \
E02_CAPTURE_RUN="$E02_CAPTURE_RUN" \
/scratch/root-venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
import json
import os
from glob import glob

capture = Path(os.environ["E02_CAPTURE_RUN"])
assert (capture / "dfk.cli.exit").read_text().strip() == "0"
raw_stdout = Path(os.environ["RECEIPT_PATH"]).read_bytes()
assert raw_stdout.isascii()
assert b"bad_\\udcff.json" in raw_stdout
receipt = json.loads(raw_stdout)
assert receipt["result"] == "complete_for_selected_local_text_inputs"
assert receipt["selection"]["selected_paths"] == [os.fsdecode(b"bad_\xff.json")]
assert receipt["scanned_denominator"]["read_paths"] == [os.fsdecode(b"bad_\xff.json")]
assert receipt["scanned_denominator"]["selected_paths"] == 1
assert receipt["scanned_denominator"]["successful_byte_reads"] == 1
assert receipt["scanned_denominator"]["decoded_utf8_inputs"] == 1
assert receipt["read_receipt"]["complete_verdict"] is True
assert receipt["git_enumeration"]["complete_verdict"] is True
assert receipt["selection"]["selected_path_count"] == 1
assert receipt["git_enumeration"]["tracked_path_count"] == 1
assert receipt["git_enumeration"]["untracked_path_count"] == 0
assert receipt["git_enumeration"]["ignored_path_count"] == 0
assert receipt["selection"]["untracked_paths"] == []
assert receipt["selection"]["ignored_paths"] == []
assert receipt["selection"]["excluded_paths"] == []
assert receipt["unreadable_paths"] == []
assert receipt["unsupported_or_ambiguous_inputs"] == []
assert receipt["head"] is not None

def assert_captured(command, returncode, stdout_sha256, stderr_sha256):
    matches = []
    for path in glob(str(capture / "logs" / "dfk-*.json")):
        meta = json.loads(Path(path).read_text(encoding="utf-8"))
        if meta["command"] == command:
            matches.append((Path(path), meta))
    assert len(matches) == 1, (command, len(matches))
    path, meta = matches[0]
    stem = path.name.removesuffix(".json")
    stdout = Path(path.parent, stem + ".stdout.bin").read_bytes()
    stderr = Path(path.parent, stem + ".stderr.bin").read_bytes()
    assert meta["returncode"] == returncode
    assert hashlib.sha256(stdout).hexdigest() == stdout_sha256
    assert hashlib.sha256(stderr).hexdigest() == stderr_sha256

git_receipt = receipt["git_enumeration"]
for key in ("tracked", "untracked_nonignored", "ignored_nontracked", "working_tree_status"):
    item = git_receipt[key]
    assert_captured(item["command"], item["returncode"], item["stdout_sha256"], item["stderr_sha256"])
status = git_receipt["working_tree_status"]
assert_captured(status["prefix_command"], status["prefix_returncode"], status["prefix_stdout_sha256"], status["prefix_stderr_sha256"])
head = git_receipt["head"]
assert_captured(head["command"], head["returncode"], head["stdout_sha256"], head["stderr_sha256"])
children = sorted((capture / "logs").glob("dfk-*.json"))
assert len(children) == 10, [path.name for path in children]
for path in children:
    meta = json.loads(path.read_text(encoding="utf-8"))
    stem = path.name.removesuffix(".json")
    stdout = (path.parent / f"{stem}.stdout.bin").read_bytes()
    stderr = (path.parent / f"{stem}.stderr.bin").read_bytes()
    assert len(stdout) == meta["stdout_bytes"]
    assert len(stderr) == meta["stderr_bytes"]
    assert hashlib.sha256(stdout).hexdigest() == meta["stdout_sha256"]
    assert hashlib.sha256(stderr).hexdigest() == meta["stderr_sha256"]
PY
```

Expected receipt shape for this one-file fixture: one tracked path, one selected/read UTF-8 file, no untracked or ignored candidates, no unreadable or unsupported inputs, a complete Git/read receipt, and the surrogateescaped filename represented in ASCII JSON as `bad_\\udcff.json`. The fixture commits locally using per-command `git -c` identity only, so census `HEAD` is available without changing global Git configuration or any external credentials. The complete raw stdout/stderr of fixture Git children and all CLI-internal Git children are in `logs/`; their metadata command arrays and byte hashes can be reconciled to `receipt["git_enumeration"]` before claiming the process evidence is complete.

The root-profile read-only `uv sync --dry-run --offline` plan for Python 3.14.0 with `--extra runtime --extra ml --group dev --no-install-project` selected the complete 158-package set printed by uv from the copied `policy-engine/uv.lock`. The same plan with `--no-build` stops at `autograd-gamma==0.5.0`, which has only the lock-pinned 3,952-byte source distribution, SHA-256 `f27abb7b8bb9cffc8badcbf59f3fe44a9db39e124ecacf1992b6d952934ac9c4`. Its exact sdist was downloaded, hash-verified, and inspected: setup.py uses setuptools package discovery and has no extension modules. The full root sync then succeeded with the frozen recipe and `--no-install-project`; no source/project files were needed. Exact command/output and the sdist inspection are retained in `raw/dependency-provision.log`.

After every witness run, preserve the direct parent streams, per-child binary streams, and metadata together, then write a checksum manifest outside the source mount:

```sh
find "$E02_CAPTURE_RUN" -type f ! -name SHA256SUMS -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$E02_CAPTURE_RUN/SHA256SUMS"
```

## P40 and source identity

- B212/F: same Linux worker compatibility class at a deeper candidate revision. An older source-specific receipt exists, but it does not prove this candidate. Current result: `verification_missing` until the exact frozen source runs both real consumers.
- LA-029: the declared Q0 Linux gate outcome remains `verification_missing`; the available unit test is a mocked local characterization, not the server-marker-on Linux gate.
- DFK: same class as the prior C06 raw-byte filename residual, not a new class. The shared Linux runner now exists, but the current test still fakes `collect_census`. The smallest closing capability is the guest-native Git/filename fixture above. Its falsifier is a run where the real CLI loses the surrogateescaped path, cannot open it, or emits non-JSON output.

This provision step started from branch `codex/e02-unified-local-20261009`, HEAD `9e89dddfbcc3d8c44a421cc1fc143ec84f3753ae`, parent `93d6aa62a8d236667fdf322a5fc17962523b185e`. At an earlier recipe re-read, the shared branch was at HEAD `8e69d23ee61a640621a487243a59107f0d1f232f`; the lock and recipe hashes below still match the copied files. Root later reported mutable candidate `80f043c0c007ca14dfd4927f980e391f4fcdc62a` atop receipt `021`; that candidate is superseded by the root-reported `9e02a9f49c8b01026327a9f7c7e18711b13a96f2` / tree `881a950dccb7cdefacc636515aa7dd2bceadf928`, which still awaits an import-gate repair and final freeze. I did not run Git or treat any mutable tip as a frozen identity. All test commands remain prepared-only. No source was mounted, copied, or modified. Once frozen, transfer only that exact source via the ordinary shallow-bare clone and attached `--shared` checkout described in `readiness.md`; do not bind-mount source or production data.

Current-file SHA-256 inputs observed at provisioning:

```text
policy-engine/pyproject.toml                               b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267
policy-engine/uv.lock                                      e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463
policy-engine/vendor/wheels/odfpy-1.4.1-py2.py3-none-any.whl 1d1c3ea36a422d3c5cd4c2457ea0e0be59841d6c26d28bd3d5e43f060565d11b
policy-engine/workers/dowhy-014/uv.lock                    c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a
policy-engine/workers/dowhy-014/pyproject.toml              df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447
policy-engine/workers/dowhy-014/.python-version             7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d
```

Candidate consumer/fixture inputs re-hashed during this preparation turn (still mutable; these do not identify the eventual frozen archive):

```text
policy-engine/workers/dowhy-014/worker.py                                      27ca68b50842b8bf1b6396e5862cf4052c10d8d3359b60b65237d62551cde253
policy-engine/workers/dowhy-014/protocol.py                                    1a1d09c47883728c8fc8cf4d9ec8eb200340a5fadd28d531c6edd2be0d75c239
policy-engine/src/polisyos/foundry/methods/catalog/causal/_dowhy_worker.py     582ad243fec5406d577154b7bc1f97e03664cf01843e1fa6f23c3ea28746db56
policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py  5a479bc577181020b229be26415ece9453d5b54c5b83188ae39b5dbe21fc17ac
policy-engine/tools/ops_runners/ukraine_data/validate_part_a.py                1bc9bc1e7b01cdb1119e3f8ca5338ba33158e8c564bac82882c4f7e8cfe184c6
policy-engine/tools/quality/validation/schema_fqn_census.py                   33c80a668228b159526c45f3101e259a54fd74a6dd4d5c8f80cc2dfef6a02e12
policy-engine/tests/unit/remediation/test_dfk_01.py                            9058c7ecab448336f2d025cae3b5eedc0c7bc0966ad316cb0ead63be735d47e8
policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md
                                                                                 2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727
```

Moderate install/start/pull output is in the ignored `raw/` directory; SHA-256 references are retained alongside it:

```text
brew-install.log                 774527c44aae5b6b9ed48617c62730dbffd0f1f933ca157da13f67d8b1633646
colima-start-short-home.log       ae1e603ff899d342ceb2103aa6748a14b6e8e84df141f4d9c730b4b2523a40fe
colima-start.log                 b9c9114d69819d7b7c416f67e7e499e98f9b6e0ee2d328d31f3e3bfcb16d945f
uv-image-pull.log                528caf6d65776c210d39c945c30c1de24b1cde367f6950ee9bd0a6afd9a1f244
uv-python-312-install.log        bbabe80d96140de5f2d071de26fb4248d0a4b2ba4728abb7f0df10fb6a1118e0
uv-python-314-install.log        e55c4c35928518d8cadb77735406a4784146578b85ae36ac6eb521900616d2c3
uv-python-install.log            da4c45dc457e009f7793845bd8aa17b80dd5862651d9b402bbbb96ccd06cb84c
health-checks.log               b279bf43f7eb6eee0875f6bd32b3e893f68bc49360912f0c661288f508cae19a
dependency-provision.log        f0180d4b712e2d548b163e5801c7e6dc49d66bacbb7cd9dac9bfda5028023812
```

`colima-start.log` records a failed first attempt before VM creation: the nested worktree `COLIMA_HOME` exceeded Lima's 104-byte Unix socket path cap. The successful profile uses the shorter dedicated home path above. The installed Colima profile and Docker config do not use the failed path.

Official behavior references: [Colima configuration](https://colima.run/docs/configuration/) and [Astral uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/).
