# Linux wave readiness delta

Read-only refresh for the existing isolated E02 Linux worker. The checkout remains mutable; no final source identity was supplied in this task. No source was cloned, copied, mounted, or tested. The only active Docker context used for inspection was `colima-e02-local`; the default context was not queried or changed.

## Current runner and budgets

The dedicated context resolves to `colima-e02-local`. Its only running worker is `e02-local-worker-provision`, container `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`, from `ghcr.io/astral-sh/uv@sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`. Its mounts are only the three existing named volumes: `e02-local-uv-pythons` at `/opt/uv-python`, `e02-local-uv-env` at `/scratch`, and `e02-local-uv-cache` at `/root/.cache/uv`. `/workspace/polisyos` is absent. No host source or production mount is present.

The container is limited to 2 CPUs (`cpu.max` `200000 100000`) and 2,200 MiB cgroup memory. At the refresh, `memory.current` was 1,629,184,000 bytes, leaving 646.289 MiB below that cap; guest `MemAvailable` was 2,572,908 KiB, with no swap. `memory.events` had zero `high`, `max`, `oom`, and `oom_kill`; memory PSI averages were 0.00. `/scratch` had 3,052,512 KiB free (2.911 GiB), 61% used. The container root and `/scratch` report the same 7.8 GiB backing filesystem, so budget both source transport and wave output against that one capacity. Do not run the heavy wave from this snapshot; remeasure immediately before transfer and again before the one-slot run.

Host `df -k /` in the latest lightweight capture reported 18,458,236 KiB available (17.603146 GiB); earlier exact post-provision snapshots were 18,471,188 KiB (17.615498 GiB) and 18,450,456 KiB (17.595726 GiB). Human-readable `df -h` rounded those values to 18 GiB. They are below an 18 GiB reserve. See the corrected [host environment note](browser-core-host-env.md); do not use the rounded display as proof that the reserve is met. The host has 16 GiB RAM and 8 CPUs.

## Existing locked Linux environments

The existing application interpreter is `/scratch/root-venv/bin/python`: CPython 3.14.0, Hatchling 1.27.0, pytest 9.0.2, FastAPI 0.128.6, httpx 0.28.1, and lifelines 0.30.3. `uv pip check` passed for 161 distributions. The existing worker is `/scratch/dowhy-venv/bin/python`: CPython 3.12.12, DoWhy 0.14, Statsmodels 0.15.0, and pytest 9.0.2; `uv pip check` passed for 52 distributions. Both are already provisioned from their locked profiles; do not create or sync another environment. The actual `uv` executable is `/usr/local/bin/uv`, version 0.9.21; Git is 2.47.3. `ruptures` is absent from both profiles and is not needed by the prepared witnesses.

The first health-check attempt named `/opt/uv/uv`, which does not exist in this image. That captured command returned 127 before running `pip check`. `command -v uv` returned `/usr/local/bin/uv`; rerunning `uv pip check --python /scratch/root-venv/bin/python` and the equivalent worker command passed. The complete failed and corrected captures are both retained; only the corrected checks establish environment health.

## Freeze-gated single-source transport

The commands below are prepared only. Run them only after root supplies the final attached checkout, branch, full commit SHA, and tree SHA, and releases the source-transfer/run slot. Paths must be new; if a path already exists, inspect and either verify/reuse its exact identity or stop—never overwrite or clean it. Current host free space is below 18 GiB, so the host bare-clone step also needs a fresh exact disk measurement and root's capacity decision. The shallow clone must be an ordinary Git clone of the actual frozen branch; no synthetic commit/history or source archive will substitute for it.

On the host, after setting the four root-supplied values:

```sh
set -euo pipefail
source_checkout=/absolute/path/root-supplies-at-freeze
freeze_branch=ROOT_SUPPLIED_ATTACHED_BRANCH
freeze_sha=ROOT_SUPPLIED_FULL_COMMIT_SHA
freeze_tree=ROOT_SUPPLIED_FULL_TREE_SHA
host_bare="${TMPDIR%/}/e02-${freeze_sha}.git"

git -C "$source_checkout" status --short --branch
git -C "$source_checkout" symbolic-ref --short HEAD
git -C "$source_checkout" rev-parse HEAD
git -C "$source_checkout" rev-parse 'HEAD^{tree}'
test ! -e "$host_bare"
git clone --bare --depth=1 --single-branch --no-tags --branch "$freeze_branch" \
  "file://$source_checkout" "$host_bare"
test "$(git --git-dir="$host_bare" rev-parse HEAD)" = "$freeze_sha"
test "$(git --git-dir="$host_bare" rev-parse 'HEAD^{tree}')" = "$freeze_tree"
test "$(git --git-dir="$host_bare" rev-parse --is-shallow-repository)" = true
```

The checkout's attached branch, tracked cleanliness, commit, and tree must agree with root's freeze evidence before cloning. The `file://` transport makes the depth request explicit. Verify the bare result before moving it. Then use only the dedicated Docker client/context:

```sh
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}

docker_e02 context show
docker_e02 exec e02-local-worker-provision \
  sh -c 'test ! -e /workspace/polisyos && test ! -e "$1"' \
  sh "/scratch/e02-${freeze_sha}.git"
docker_e02 cp "$host_bare" \
  "e02-local-worker-provision:/scratch/e02-${freeze_sha}.git"
docker_e02 exec e02-local-worker-provision mkdir -p /workspace
docker_e02 exec e02-local-worker-provision \
  git clone --shared --single-branch --branch "$freeze_branch" \
  "/scratch/e02-${freeze_sha}.git" /workspace/polisyos
```

Read the attached checkout back before any test:

```sh
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos status --short --branch
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos status --porcelain=v1 --untracked-files=no
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos symbolic-ref --short HEAD
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos rev-parse HEAD
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos rev-parse 'HEAD^{tree}'
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos rev-parse --is-shallow-repository
docker_e02 exec e02-local-worker-provision \
  cat /workspace/polisyos/.git/shallow
docker_e02 exec e02-local-worker-provision \
  cat /workspace/polisyos/.git/objects/info/alternates
docker_e02 exec e02-local-worker-provision \
  git -C /workspace/polisyos cat-file -e "$freeze_sha^{tree}"
```

Branch, clean tracked status, `HEAD`, tree, and the shallow boundary must match the supplied freeze; the alternates file must point to the retained `/scratch/e02-${freeze_sha}.git/objects`. Keep that bare store for the checkout's full lifetime. Both Python profiles use the same `/workspace/polisyos` tree. No bind mount is needed.

The Q2 helper is outside the frozen Git archive, so transport its current runner and manifest separately while preserving its relative layout. Their current local inputs are `raw/run.py` (77,787 bytes, SHA-256 `5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932`), `installed-wave-manifest.json` (6,943 bytes, SHA-256 `ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7`), and `installed-wave-recipe.md` (SHA-256 `e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e`). These identities were re-read and verified against the current LOCAL files; they are independent of the not-yet-supplied source SHA/tree.

```sh
q2_local=/absolute/path/to/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging
test "$(shasum -a 256 "$q2_local/raw/run.py" | awk '{print $1}')" = \
  5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932
test "$(shasum -a 256 "$q2_local/installed-wave-manifest.json" | awk '{print $1}')" = \
  ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7
docker_e02 exec e02-local-worker-provision \
  sh -c 'test ! -e /scratch/e02-q2-handoff && mkdir -p /scratch/e02-q2-handoff/raw'
docker_e02 cp "$q2_local/raw/run.py" \
  e02-local-worker-provision:/scratch/e02-q2-handoff/raw/run.py
docker_e02 cp "$q2_local/installed-wave-manifest.json" \
  e02-local-worker-provision:/scratch/e02-q2-handoff/installed-wave-manifest.json
docker_e02 exec e02-local-worker-provision sha256sum \
  /scratch/e02-q2-handoff/raw/run.py \
  /scratch/e02-q2-handoff/installed-wave-manifest.json
docker_e02 exec e02-local-worker-provision \
  sh -c 'printf "%s  %s\n%s  %s\n" "$1" "$2" "$3" "$4" | sha256sum -c -' sh \
  5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932 \
  /scratch/e02-q2-handoff/raw/run.py \
  ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7 \
  /scratch/e02-q2-handoff/installed-wave-manifest.json
```

The Q2 runner itself enforces the supplied source commit/tree, attached clean checkout, Linux host, Python 3.14 + Hatchling 1.27.0 app environment, and existing Python 3.12 + DoWhy 0.14 worker. It runs the source wheel, rebuilt sdist wheel, and rebuilt GCP-archive wheel profiles with the 91 original plus nine declared consumers per profile. The recipe's prior measured payloads are 555,792,112 source bytes, 121,945,591 sdist bytes, and 15,146,001 bytes for each of the source and rebuilt-sdist wheels. Its ~1.5 GiB scratch reserve assumes the existing worker and includes one retained source snapshot and wave artifacts; the GCP archive and the extra bare/attached transport overhead were not measured by that estimate. Current `/scratch` has 2.911 GiB available, so take fresh disk readings after transport and before the one-slot Q2 command. The pinned image has no system `python3` (`python3 --version` returns not found); invoke the runner with the already-installed `/scratch/root-venv/bin/python` as shown below instead of creating another interpreter. The pinned helper/manifest/recipe hashes and complete selector criteria are in [the Q2 recipe](../q2-packaging/installed-wave-recipe.md).

After root releases the heavy slot, the runner command is:

```sh
docker_e02 exec e02-local-worker-provision \
  /scratch/root-venv/bin/python /scratch/e02-q2-handoff/raw/run.py \
  --repo /workspace/polisyos \
  --source-sha "$freeze_sha" --source-tree "$freeze_tree" \
  --app-python /scratch/root-venv/bin/python \
  --worker-python /scratch/dowhy-venv/bin/python \
  --output-root "/scratch/e02-q2-runs-${freeze_sha}"
```

Do not run Q2 concurrently with B212/F or another numerical wave. The output parent is unique to the freeze and the helper creates a fresh timestamped run directory without deleting prior evidence.

## Authentic Linux witnesses after freeze

Use the full command blocks and complete child-output capture setup already prepared in [`README.md`](README.md), after source identity checks:

- **B212/F:** from `/workspace/polisyos/policy-engine`, call `/scratch/root-venv/bin/python -m pytest -q` on `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py` with `-k 'test_real_worker_job_cas_fresh_python314_reader or test_real_estimate_point_only_survives_parent_cas_and_reader'`; set `E02_TEST_DOWHY_WORKER_PYTHON=/scratch/dowhy-venv/bin/python`. Keep the 3.14 parent CAS reader and 3.12 DoWhy 0.14 subprocess; the prepared expected outcome is 2 passed.
- **LA-029 / UKOPS:** run `tools/ops_runners/ukraine_data/validate_part_a.py` from the frozen checkout with `POLISYOS_SERVER_EXECUTION=1`, the real default server-only build requirement, `UV_PROJECT_ENVIRONMENT=/scratch/root-venv`, `UV_NO_SYNC=1`, and `UV_FROZEN=1`, passing `--workspace-root /workspace/polisyos/policy-engine --root /scratch/ukraine-artifacts`. Retain the nested C7 integration child output. Assert the typed gate manifest reports `passed`, `server_only=true`, `passed=true`, `skipped=false`, and the actual child command `uv run pytest -q tests/integration/test_c7_synthetic_full_pipeline.py`. Preserve the negative guard control without the marker; do not route around the Linux guard.
- **DFK invalid-byte Git filename:** use the real CLI `python -m tools.quality.validation.schema_fqn_census --repo-root "$DFK_REPO_ROOT"` against a fresh guest-native `/tmp` Git repository. Create exactly one tracked name `os.fsdecode(b"bad_\xff.json")` with content `b"{}\n"`, commit with per-command `git -c user.name=... -c user.email=...`, verify `git ls-files -z` equals `b"bad_\xff.json\0"`, and run the actual CLI under `/scratch/root-venv/bin/python`. Use a unique freeze/attempt path and require it to be absent before `mkdir`; never remove an existing path. The earlier prepared README block includes `shutil.rmtree(root)`; do not run that block unchanged. Expect JSON `complete_for_selected_local_text_inputs`, the same surrogateescaped selected/read path, one successful read, zero unreadable paths, and `read_receipt.complete_verdict=true`. Keep it on guest Linux storage, not an APFS bind mount.

All three Linux witnesses stay synthetic/minimal. They are still `verification_missing` until the exact frozen source passes the real consumers. Preserve stdout/stderr byte captures for both the parent commands and subprocesses; do not accept a status marker, a mocked consumer, or an exit code alone as the semantic receipt.

## Local receipts

Bounded machine captures, including the initial wrong-uv-path failure and corrected package checks, are under `raw/readiness-delta-20261010/`; `SHA256SUMS` covers all captured files. The Q2 runner, manifest, and recipe are cited by their paths and hashes above. The macOS browser-core environment is documented separately in [browser-core-host-env.md](browser-core-host-env.md); its rounded `df -h` display is not a capacity-threshold receipt.
