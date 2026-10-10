# Linux readiness for frozen source 9de48feb

Read-only readiness against source freeze `9de48febba1ef18c8e1252dc027cb0d89b88abc3`, tree `d524ed13bdbcf6b7e65b838ca2a42f70df15d5c9`, branch `codex/e02-unified-local-20261009`. No Docker/VM command, source transfer, build, package install, product test, or Git mutation was run for this note. Root owns the worker update and the single heavy-test slot.

## Frozen source and current worker receipt

The attached host checkout was read back at the supplied branch/SHA/tree. The source is a descendant of worker base `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, tree `8d8c4082febf1676dd86084106f3266d8b2131a3`, whose actual parent header is `25219d0692c1c54b99f9d40b5c53a6956e2f4e2e`. The base-to-freeze range contains 22 commits; the last commit’s actual parent is `492c8690afeb9481dbf22058f6acbbd477ebdc85`. A read-only `git merge-base --is-ancestor` passed. Use `git cat-file -p` for the base and each range commit when capturing the update; do not use `%P` as parent-header evidence. The checkout has pre-existing untracked LOCAL receipts, but no tracked changes; the bundle below is built from the committed branch ref only.

The complete latest worker inspection is `LOCAL/linux-profile/raw/final-owned-worker-inspect-20261010/stdout.txt` (8,869 bytes, SHA-256 `fbfd2bd991c8f5420443c7288373ee0262935c29cdf6d3b133bdcf87300aebc8`); `command.json` records the explicit `colima-e02-local` Docker context and that same output hash. It confirms the target container is running: `e02-local-worker-provision`, ID `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`, image `sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`, Linux/ARM64, `NanoCpus=2000000000`, and memory cap `2306867200` bytes. Its only mounts are named volumes `e02-local-uv-pythons:/opt/uv-python`, `e02-local-uv-cache:/root/.cache/uv`, and `e02-local-uv-env:/scratch`; there is no host bind or production mount. The inspect receipt is a point-in-time container inspection; it does not contain current cgroup pressure/current, `/scratch` free space, or the running-container list. Recheck those read-only before the later slot. The Q2 wrapper also requires this container to be the sole running container in the dedicated Docker context; the inspect receipt alone does not establish that predicate.

The immediately preceding append-only update receipt, `LOCAL/linux-profile/linux-source-update-13e411da-20261010-receipt.md`, records the same worker/container identity, attached checkout and bare ref at base 13e, retained shallow boundary `7574c864a605c50efc033b966807790cbd8d1781`, no alternates, and the locked environments: uv `0.9.21`, root CPython `3.14.0` / Hatchling `1.27.0`, DoWhy CPython `3.12.12` / DoWhy `0.14`. It reports `uv pip check` passing for 161 root and 52 worker distributions. Those are last-read environment measurements, not refreshed by the inspect-only stdout. The five frozen lock/version files still match:

```text
policy-engine/pyproject.toml                  b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267
policy-engine/uv.lock                         e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463
policy-engine/workers/dowhy-014/pyproject.toml df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447
policy-engine/workers/dowhy-014/uv.lock        c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a
policy-engine/workers/dowhy-014/.python-version 7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d
```

## Append-only host-to-worker source update

The current worker bare and attached checkout are to be reused in place: bare `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git`, checkout `/workspace/polisyos`, origin equal to that bare path, branch `codex/e02-unified-local-20261009`. Keep the shallow boundary at the original `7574…` commit. Do not make a new clone, source mount, reset, rebase, force ref update, unshallow, or cleanup.

The host command below creates one ordinary incremental bundle from the committed branch ref. Capture its full argv/stdin/stdout/stderr/exit in a new ignored receipt directory before proceeding. The bundle destination must be absent, not a symlink, and on the same existing host checkout; its exact path is freeze-bound:

```sh
set -euo pipefail
source_checkout=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
branch=codex/e02-unified-local-20261009
base=13e411da7d9e505856fc336b3d25fd0aabdb1f66
base_tree=8d8c4082febf1676dd86084106f3266d8b2131a3
freeze_sha=9de48febba1ef18c8e1252dc027cb0d89b88abc3
freeze_tree=d524ed13bdbcf6b7e65b838ca2a42f70df15d5c9
bundle="$source_checkout/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/e02-source-update-$freeze_sha.bundle"
test "$(git -C "$source_checkout" symbolic-ref --short HEAD)" = "$branch"
test "$(git -C "$source_checkout" rev-parse HEAD)" = "$freeze_sha"
test "$(git -C "$source_checkout" rev-parse 'HEAD^{tree}')" = "$freeze_tree"
test "$(git -C "$source_checkout" rev-parse "$base^{tree}")" = "$base_tree"
test "$(git -C "$source_checkout" rev-parse --is-shallow-repository)" = false
test -z "$(git -C "$source_checkout" status --porcelain=v1 --untracked-files=no)"
git -C "$source_checkout" merge-base --is-ancestor "$base" "$freeze_sha"
test "$(git -C "$source_checkout" rev-list --count "$base..$freeze_sha")" = 22
test ! -e "$bundle" && test ! -L "$bundle"
git -C "$source_checkout" cat-file -p "$base"
for commit in $(git -C "$source_checkout" rev-list --reverse --topo-order "$base..$freeze_sha"); do
  printf 'COMMIT %s\n' "$commit"
  git -C "$source_checkout" cat-file -p "$commit" | sed -n '/^tree /p;/^parent /p'
done
git -C "$source_checkout" bundle create "$bundle" "refs/heads/$branch" "^$base"
git -C "$source_checkout" bundle verify "$bundle"
git -C "$source_checkout" bundle list-heads "$bundle"
shasum -a 256 "$bundle"
```

Before advancing the existing checkout, read the worker's current refs, tree, shallow files, origin, owned bare mode, alternates, object-directory environment, clean status, disk, and cgroup stats. The previous 13e receipt says the four Q2 LOCAL inputs below existed in the worker as ignored files; the inspect-only stdout does not refresh them. Two now collide with paths added to the 9de Git tree: `raw/run.py` and `raw/timeout_driver.py`. Their **old** 13e worker-copy hashes were `c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf` and `7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073`. Before merge, verify those exact old bytes and preserve them under a new absent scratch evidence directory (no deletion); stop if either path differs, is indirect, or the backup destination exists. This prevents an ignored-file overwrite during the Git fast-forward from silently discarding the pre-freeze inputs.

```sh
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}
container=e02-local-worker-provision
worker_bare=/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git
worker_checkout=/workspace/polisyos
worker_bundle=/scratch/e02-source-update-$freeze_sha.bundle
legacy=/scratch/e02-q2-raw-before-13e-$freeze_sha
# Read-only inspect plus targeted worker checks; then preserve the two known colliding old inputs.
docker_e02 inspect --format 'id={{.Id}} state={{.State.Status}} image={{.Image}} memory={{.HostConfig.Memory}} mounts={{json .Mounts}}' "$container"
docker_e02 exec "$container" test ! -e "$legacy"
docker_e02 exec "$container" test ! -L "$legacy"
docker_e02 exec "$container" mkdir -m 700 "$legacy"
docker_e02 exec -i "$container" /bin/bash -s -- "$worker_checkout" "$legacy" <<'PRESERVE_OLD_Q2_INPUTS'
set -euo pipefail
repo=$1; backup=$2
raw="$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw"
for pair in \
  'run.py c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf' \
  'timeout_driver.py 7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073'; do
  set -- $pair; name=$1; expected=$2; source="$raw/$name"
  test -f "$source" && test ! -L "$source"
  printf '%s  %s\n' "$expected" "$source" | sha256sum -c -
  test ! -e "$backup/$name" && test ! -L "$backup/$name"
  cp -p -- "$source" "$backup/$name"
  printf '%s  %s\n' "$expected" "$backup/$name" | sha256sum -c -
done
PRESERVE_OLD_Q2_INPUTS

test ! -e "$worker_bundle" && test ! -L "$worker_bundle"
docker_e02 cp "$bundle" "$container:$worker_bundle"
docker_e02 exec "$container" sha256sum "$worker_bundle"
```

Compare the worker bundle hash to the host `shasum` before the update. Then run the compare-and-swap on the one existing bare ref and an ordinary fast-forward on the attached checkout. The below is the exact update argv/stdin shape; capture its complete output and preserve partial state if any stage fails. It intentionally leaves the old shallow boundary in place:

```sh
docker_e02 exec -i "$container" /bin/bash -s -- \
  "$worker_bare" "$worker_checkout" "$worker_bundle" "$branch" \
  "$base" "$base_tree" "$freeze_sha" "$freeze_tree" <<'APPEND_ONLY_UPDATE'
set -euo pipefail
bare=$1; repo=$2; bundle=$3; branch=$4; base=$5; base_tree=$6; new=$7; new_tree=$8
boundary=7574c864a605c50efc033b966807790cbd8d1781
for pair in "$bare:$base:$base_tree" "$repo:$base:$base_tree"; do
  path=${pair%%:*}; rest=${pair#*:}; sha=${rest%%:*}; tree=${rest#*:}
  if [[ $path == "$bare" ]]; then
    test "$(stat -c '%u:%g:%a' "$bare")" = '0:0:700'
    test "$(git --git-dir="$bare" rev-parse --is-bare-repository)" = true
    test "$(git --git-dir="$bare" symbolic-ref --short HEAD)" = "$branch"
    test "$(cat "$bare/shallow")" = "$boundary"
    test ! -e "$bare/objects/info/alternates" && test ! -L "$bare/objects/info/alternates"
    test "$(git --git-dir="$bare" rev-parse HEAD)" = "$sha"
    test "$(git --git-dir="$bare" rev-parse 'HEAD^{tree}')" = "$tree"
  else
    test -d "$repo" && test ! -L "$repo" && test -d "$repo/.git" && test ! -L "$repo/.git"
    test "$(git -C "$repo" symbolic-ref --short HEAD)" = "$branch"
    test "$(git -C "$repo" remote get-url origin)" = "$bare"
    test "$(cat "$repo/.git/shallow")" = "$boundary"
    test "$(git -C "$repo" rev-parse HEAD)" = "$sha"
    test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$tree"
    test -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=no)"
  fi
done
test -z "${GIT_ALTERNATE_OBJECT_DIRECTORIES:-}"
test -z "${GIT_OBJECT_DIRECTORY:-}"
git --git-dir="$bare" bundle verify "$bundle"
git --git-dir="$bare" fetch --no-tags "$bundle" "refs/heads/$branch"
test "$(git --git-dir="$bare" rev-parse FETCH_HEAD)" = "$new"
test "$(git --git-dir="$bare" rev-parse 'FETCH_HEAD^{tree}')" = "$new_tree"
git --git-dir="$bare" merge-base --is-ancestor "$base" FETCH_HEAD
git --git-dir="$bare" update-ref "refs/heads/$branch" "$new" "$base"
test "$(git --git-dir="$bare" rev-parse HEAD)" = "$new"
test "$(cat "$bare/shallow")" = "$boundary"
git -C "$repo" fetch --no-tags origin "refs/heads/$branch:refs/remotes/origin/$branch"
test "$(git -C "$repo" rev-parse "refs/remotes/origin/$branch")" = "$new"
git -C "$repo" merge-base --is-ancestor HEAD "refs/remotes/origin/$branch"
git -C "$repo" merge --ff-only "refs/remotes/origin/$branch"
test "$(git -C "$repo" rev-parse HEAD)" = "$new"
test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$new_tree"
test "$(git -C "$repo" symbolic-ref --short HEAD)" = "$branch"
test "$(git -C "$repo" remote get-url origin)" = "$bare"
test "$(cat "$repo/.git/shallow")" = "$boundary"
test -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)"
git --git-dir="$bare" fsck --connectivity-only --no-reflogs HEAD
git -C "$repo" fsck --connectivity-only --no-reflogs HEAD
for commit in $(git -C "$repo" rev-list --reverse --topo-order "$base..$new"); do
  printf 'COMMIT %s\n' "$commit"
  git -C "$repo" cat-file -p "$commit" | sed -n '/^tree /p;/^parent /p'
done
APPEND_ONLY_UPDATE
```

After update, re-read both stores independently and verify all Q2 input blobs, the attached branch/HEAD/tree/origin, no unexpected alternates, both shallow files at `7574…`, and connectivity. The source pins are current: tracked manifest SHA `1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277`, tracked runner SHA `a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0`, tracked timeout driver SHA `0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312`; ignored supplemental driver/manifest hashes `4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49` and `ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112af4e7df`. The Q2 recipe SHA is `8b56d6053cc02f5d81e990bd3e93214e5802bfcc98cc61dab57ceb99daf2ab96`; `final-source-linux-wave.sh` is `9241d6d695a27e673cd36f6416cfbf03fbc1c383368d642827d7380cfbc71d81`. The helper validates its own local pins, worker package/lock pins, exact owned bare path, and freeze. Its `q2` entrypoint verifies copied inputs; it does not call its internal `continue_transfer()` or the input-copy routine. Because current 9de tracks the three files above and the base receipt says the two supplemental inputs already exist at the exact unchanged hashes, the expected readback is: three frozen tracked files from Git; two ignored supplemental files reused only if their exact hashes/regular-file/ignore state pass. Do not overwrite a mismatched/unknown supplemental file. The hook stays separate until native consumers are authorized; host hook path/hash: `LOCAL/linux-profile/raw/sitecustomize.py`, `4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2`.

## Sequential Linux commands after root releases the slot

Use the existing dedicated profile only: `COLIMA_HOME=/Users/deniskopylov/.colima-e02-local`, `DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local`, `/opt/homebrew/bin/docker --context colima-e02-local`. No source bind mount. Recheck target/container list, disk, cgroup events and pressure before Q2. The latest measured `/scratch` availability in the 13e update receipt was 5,902,120 KiB; it is historical, not a current free-space guarantee. Keep the Q2, B212/F, LA029, and DFK commands sequential in the single root-controlled slot; use a new absent attempt directory, preserve all artifacts, and never clean a prior output.

### Q2 installed source/sdist/GCP consumers

The current Q2 inputs (verified from the frozen worktree) are the 127-ID primary consumer runner and its timeout driver, with the three profiles in this order: source wheel, rebuilt source-distribution wheel, rebuilt GCP-archive wheel. The `run.py` runner retains each profile’s full consumer stdout/stderr, collected IDs, JUnit, origin proof, and install/build receipts. The timeout wrapper leaves the first profile unbounded and derives later timeouts at 2x the immediately preceding successful profile; it records `timeout-calibration.json`. The supplemental runner follows the primary wave and runs six selectors for each of the same three profiles, reusing the installed environment/wheels. Expected primary: exactly 127 collected and executed IDs/profile, zero skips/failures/errors; historical 100-ID subset retained. Expected supplement: six tests/profile, zero skips/failures/errors.

After source update and an explicit root heavy-slot grant, the exact host invocation is:

```sh
E02_ROOT_HEAVY_SLOT_GRANT=9de48febba1ef18c8e1252dc027cb0d89b88abc3 \
  /bin/bash policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/final-source-linux-wave.sh \
  q2 codex/e02-unified-local-20261009 \
  9de48febba1ef18c8e1252dc027cb0d89b88abc3 \
  d524ed13bdbcf6b7e65b838ca2a42f70df15d5c9 final-01
```

`final-01` is only a proposed attempt name; require `/scratch/e02-q2-runs/9de48febba1ef18c8e1252dc027cb0d89b88abc3/final-01` to be absent before using it. Driver output/exit captures are under that directory’s `orchestration/` (`primary.stdout`, `primary.stderr`, `primary.exit`, `primary-run.path`, and the corresponding supplemental files). The primary run directory named by `primary-run.path` contains `run-receipt.json`, `timeout-calibration.json`, and three `consumer-runs/{source-wheel,rebuilt-sdist-wheel,rebuilt-gcp-archive-wheel}/consumer-suite.{stdout,stderr}.txt` plus JUnit, node-ID, origin and command receipts. The supplement path is recorded in `supplemental-run.path` and contains `supplemental-receipt.json` and six-test profile outputs. This one command performs both phases sequentially; do not concurrently run a native numerical test.

### B212/F, then LA-029, then DFK

For native commands, first bind a new absent per-freeze capture root `/scratch/e02-child-capture/9de48febba1ef18c8e1252dc027cb0d89b88abc3/attempt-01`. Copy the frozen hook from the host LOCAL path only after root authorizes native execution; require each destination absent or already a regular exact-hash file before copy/reuse. Hook SHA is `4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2`. Preserve direct parent streams separately from captured subprocess `.stdout.bin`/`.stderr.bin`/metadata. Each lane below runs in the existing container with the shown working directory and the locked paths `/scratch/root-venv/bin/python` (3.14.0), `/scratch/dowhy-venv/bin/python` (3.12.12, DoWhy 0.14), and `uv 0.9.21`.

**B212/F:** from `/workspace/polisyos/policy-engine`, run the actual two tests in `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py` with `-k 'test_real_worker_job_cas_fresh_python314_reader or test_real_estimate_point_only_survives_parent_cas_and_reader'`, using `E02_TEST_DOWHY_WORKER_PYTHON=/scratch/dowhy-venv/bin/python` and `PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src"`. Keep separate freeze/attempt pytest cache, basetemp, and benchmark-storage paths. Parent files: `$E02_CAPTURE_RUN/dowhy.pytest.stdout`, `.stderr`, `.exit`; child process files/JSON under `$E02_CAPTURE_RUN/logs/`. Expected: two passed. F persists the actual 3.12 DoWhy worker response/report/evidence in CAS then validates it in a fresh 3.14 reader; B212 retains the point estimate while refusing CI/SE and gate eligibility. Expected F estimate is about `2.016134929864521`, with interval about `[1.8265023190563892, 2.2057675406726527]`; B212 reports `numerical_failure`, non-null point estimate, and absent interval/level.

**LA-029 / UKOPS:** from `/workspace/polisyos/policy-engine`, call `/scratch/root-venv/bin/python tools/ops_runners/ukraine_data/validate_part_a.py --workspace-root /workspace/polisyos/policy-engine --root /scratch/ukraine-artifacts-9de48febba1ef18c8e1252dc027cb0d89b88abc3-attempt-01` with `POLISYOS_SERVER_EXECUTION=1`, `UV_PROJECT_ENVIRONMENT=/scratch/root-venv`, `UV_NO_SYNC=1`, `UV_FROZEN=1`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and distinct freeze/attempt pytest cache/basetemp/benchmark paths in `PYTEST_ADDOPTS`. Keep `PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src"` so the child-stream hook sees the actual nested `uv run pytest -q tests/integration/test_c7_synthetic_full_pipeline.py`; the ops runner sets `POLISYOS_RUN_INTEGRATION=1` on that child and uses the real server-only guard. Parent outputs: `la029.manifest.stdout`, `.stderr`, `.exit`; parse the emitted summary and its `part_a_gate_manifest.json` under the unique root, and bind the exact nested child `.stdout.bin`/`.stderr.bin` hashes. Require `status=passed`, `server_only=true`, `passed=true`, `skipped=false`, and the exact recorded C7 command. Also retain the no-marker guard control, which must raise `LocalExecutionBlockedError` before any subprocess; never disable or bypass the Linux guard.

**DFK invalid-byte Git filename:** from `/workspace/polisyos/policy-engine`, use one fresh guest-native repo `/tmp/dfk-mini-9de48febba1ef18c8e1252dc027cb0d89b88abc3-attempt-01` and the real CLI `/scratch/root-venv/bin/python -m tools.quality.validation.schema_fqn_census --repo-root "$DFK_REPO_ROOT"`. Set `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and `PYTHONPATH="$E02_CAPTURE_RUN"` for the recorder. Build exactly one tracked file named `os.fsdecode(b"bad_\xff.json")` with bytes `b"{}\n"`; commit only with per-command `git -c user.name=... -c user.email=...`. The existing README fixture contains `shutil.rmtree(root)` and is unsafe to run verbatim. Correct it to fail closed if the unique root exists or is a symlink, then create it with `mkdir(exist_ok=False)`; do not delete/move a prior attempt. Capture fixture builder parent stdout/stderr and the CLI JSON stdout/stderr/exit separately. CLI and Git-child captures stay under `$E02_CAPTURE_RUN/logs/`; the receipt must bind the 10 child Git commands and their full stream hashes. Expected JSON: `complete_for_selected_local_text_inputs`, one tracked/selected/read UTF-8 path, zero unreadable/unsupported paths, `complete_verdict=true`, and the filename round-trips as the surrogateescaped `bad_\udcff.json`. Content is only three bytes (`{}\n`); no production corpus is read.

After every lane, retain a checksum manifest over that lane’s output files; never point a later attempt at an existing path. No selector, guard, output, or consumer may be replaced with a marker-only or mocked substitute.

## P40 and remaining gates

| Finding | P40 bucket | Required handling / falsifier |
|---|---|---|
| Old ignored `raw/run.py` and `raw/timeout_driver.py` copies occupy paths added as tracked files by the 9de freeze; the 13e base-to-freeze Git diff marks both `A`. | **Same transport/input-binding class one level deeper.** Earlier path-binding correction derived the owned bare path; this is the next physical input boundary. | Preserve and hash the two exact old bytes before advancing. After merge, read back the new tracked Git blobs and the two unchanged ignored supplemental inputs. The current helper has no standalone “sync inputs” CLI; its internal guarded copy routine is only called by `continue_transfer()`, while `q2` only verifies. Widen preflight/admission over all five exact inputs plus the capture hook, or keep this explicit bounded residual and stop on any mismatch. The falsifier is one run of the generic input action that must distinguish tracked frozen bytes, exact ignored bytes, missing ignored input, wrong bytes, symlink, and unignored path without starting a build/test. |
| The Q2 wrapper checks only `test ! -e "$run_root"` before `mkdir -p "$run_root/orchestration"`; a dangling symlink at the attempt path or a symlinked parent passes that proxy and can redirect retained output. | **New class: output-path confinement.** | Add path-component lstat/symlink rejection before creating outputs (including the attempt parent), then exclusive-create the attempt directory. Falsifier: dangling and ancestor symlinks refuse before any artifact is created; an unrelated outside sentinel remains unchanged. Do not launch the wave until the helper enforces this property. |
| DFK preparation in the older README calls `shutil.rmtree(root)` when the path exists. | **New class: destructive fixture namespace reuse.** | Replace with absent-only root admission and `mkdir(exist_ok=False)`. Falsifier: an existing sentinel path must cause refusal while its bytes remain untouched. Do not execute the unsafe block. |
| Latest `docker inspect` receipt is target-scoped and does not show current cgroup/disk or `docker ps`. | **Not established, not a defect finding.** | Root’s pre-wave read-only preflight must bind the one-container guard, cgroup current/events/pressure, and `/scratch` headroom. No cleanup is indicated. |

The older `final-wave-readiness.md` predates this freeze and should not supply its candidate SHA or old standalone-clone recipe. Current Linux remains `verification_missing` for B212/F, LA-029, DFK, and all Q2 profiles until their actual frozen consumers run and the receipts pass. No production currentness or payload claim follows from these synthetic/minimal Linux witnesses.

## Literal invocations and capture paths (recipes only)

These are the proposed host/guest argv bodies for root to execute only after the corresponding slot/phase is released. All paths are freeze- and attempt-scoped; each `test ! -e`/`test ! -L` is a stop-on-collision guard. Run the host wrapper and guest lanes serially. The commands were not executed here.

### Q2 wrapper invocation and outputs

On the host, use a fresh ignored command receipt directory so the wrapper’s complete outer streams are retained too:

```sh
set -euo pipefail
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}
freeze_sha=9de48febba1ef18c8e1252dc027cb0d89b88abc3
freeze_tree=d524ed13bdbcf6b7e65b838ca2a42f70df15d5c9
attempt=final-01
receipt=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/q2-$freeze_sha-$attempt
run_root=/scratch/e02-q2-runs/$freeze_sha/$attempt
test ! -e "$receipt" && test ! -L "$receipt"
mkdir -m 700 "$receipt"
docker_e02 exec e02-local-worker-provision test ! -L /scratch/e02-q2-runs
docker_e02 exec e02-local-worker-provision test ! -L "/scratch/e02-q2-runs/$freeze_sha"
docker_e02 exec e02-local-worker-provision test ! -e "$run_root"
docker_e02 exec e02-local-worker-provision test ! -L "$run_root"
set +e
E02_ROOT_HEAVY_SLOT_GRANT="$freeze_sha" \
  /bin/bash policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/final-source-linux-wave.sh \
  q2 codex/e02-unified-local-20261009 "$freeze_sha" "$freeze_tree" "$attempt" \
  > "$receipt/stdout.txt" 2> "$receipt/stderr.txt"
status=$?
set -e
printf '%s\n' "$status" > "$receipt/exit.txt"
```

Root grants the slot by setting the exact SHA variable; do not overlap the call with B212/F or any other heavy lane. Wrapper outputs are inside `$run_root/orchestration/`. On success, `primary-run.path` and `supplemental-run.path` identify the run directories; inspect `run-receipt.json`, `timeout-calibration.json`, and `supplemental-receipt.json`. The primary profile trees are `consumer-runs/source-wheel`, `consumer-runs/rebuilt-sdist-wheel`, and `consumer-runs/rebuilt-gcp-archive-wheel`; each has complete `consumer-suite.stdout.txt`, `consumer-suite.stderr.txt`, JUnit, collected IDs, origin proof, and command receipt. The supplemental directories carry their own streams and six-test JUnit. The proposed outer attempt `final-01` must remain unused before execution. Static review found a Q2 output-path P38: the helper tests only `-e` on the final attempt path and then uses `mkdir -p`; a dangling final symlink or symlinked ancestor can redirect artifacts. The root-side checks in the sample block are useful preflight, but the helper should enforce the same component checks itself before any directory creation. Treat the Q2 body as blocked until that exact guard is added/read back; do not rely on a marker or a separate unbound preflight.

### Native capture hook setup

The source update did not install the child recorder. After native execution is authorized, create the unique freeze parent only if absent, copy the host hook once, and verify bytes before using it:

```sh
set -euo pipefail
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}
freeze_sha=9de48febba1ef18c8e1252dc027cb0d89b88abc3
hook_host=policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py
hook_dir=/scratch/e02-child-capture/$freeze_sha
hook_guest=$hook_dir/sitecustomize.py
attempt_dir=$hook_dir/attempt-01
docker_e02 exec e02-local-worker-provision test ! -L /scratch/e02-child-capture
docker_e02 exec e02-local-worker-provision sh -c \
  'if [ -e /scratch/e02-child-capture ]; then test -d /scratch/e02-child-capture; else mkdir -m 700 /scratch/e02-child-capture; fi'
docker_e02 exec e02-local-worker-provision test ! -e "$hook_dir"
docker_e02 exec e02-local-worker-provision test ! -L "$hook_dir"
docker_e02 exec e02-local-worker-provision mkdir -m 700 "$hook_dir"
docker_e02 cp "$hook_host" "e02-local-worker-provision:$hook_guest"
docker_e02 exec e02-local-worker-provision sh -c \
  "printf '%s  %s\\n' '4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2' '$hook_guest' | sha256sum -c -"
docker_e02 exec e02-local-worker-provision test ! -e "$attempt_dir"
docker_e02 exec e02-local-worker-provision test ! -L "$attempt_dir"
docker_e02 exec e02-local-worker-provision mkdir -m 700 "$attempt_dir"
```

The setup creates the one absent attempt parent before any lane. For each lane, require its `E02_CAPTURE_RUN` path absent and non-symlink, then use plain `mkdir` for the lane and `logs/`; copy the exact hook there only if the target is absent, and verify the same hash. If any lane or output path already exists, use a new attempt instead of reusing it. Do not use a `cp` that overwrites an existing capture file. The lane-specific copy lets Python load the hook through that lane’s `PYTHONPATH` while keeping stdout/stderr and metadata together.

### B212/F command

Run from `/workspace/polisyos/policy-engine` in the existing container after Q2 completes and root grants the same serialized slot:

```sh
set -euo pipefail
freeze_sha=9de48febba1ef18c8e1252dc027cb0d89b88abc3
attempt=attempt-01
E02_CAPTURE_RUN=/scratch/e02-child-capture/$freeze_sha/$attempt/dowhy
cache=/scratch/e02-pytest-cache-$freeze_sha-$attempt-dowhy
basetemp=/scratch/e02-pytest-tmp-$freeze_sha-$attempt-dowhy
bench=file:///scratch/e02-benchmarks-$freeze_sha-$attempt-dowhy
test ! -e "$E02_CAPTURE_RUN" && test ! -L "$E02_CAPTURE_RUN"
mkdir "$E02_CAPTURE_RUN"
mkdir "$E02_CAPTURE_RUN/logs"
test ! -e "$E02_CAPTURE_RUN/sitecustomize.py" && test ! -L "$E02_CAPTURE_RUN/sitecustomize.py"
cp -p "/scratch/e02-child-capture/$freeze_sha/sitecustomize.py" "$E02_CAPTURE_RUN/sitecustomize.py"
test "$(sha256sum "$E02_CAPTURE_RUN/sitecustomize.py" | awk '{print $1}')" = 4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs" E02_CAPTURE_LANE=dowhy
export E02_TEST_DOWHY_WORKER_PYTHON=/scratch/dowhy-venv/bin/python
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src${PYTHONPATH:+:$PYTHONPATH}"
cd /workspace/polisyos/policy-engine
set +e
/scratch/root-venv/bin/python -m pytest -q \
  -o "cache_dir=$cache" --basetemp="$basetemp" --benchmark-storage="$bench" \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py \
  -k 'test_real_worker_job_cas_fresh_python314_reader or test_real_estimate_point_only_survives_parent_cas_and_reader' \
  > "$E02_CAPTURE_RUN/dowhy.pytest.stdout" 2> "$E02_CAPTURE_RUN/dowhy.pytest.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$E02_CAPTURE_RUN/dowhy.exit"
```

The root test process is Python `3.14.0`; `E02_TEST_DOWHY_WORKER_PYTHON` selects the existing Python `3.12.12` / DoWhy `0.14` worker. Both worker JSON streams and the fresh 3.14 reader streams are recorded by the hook under `logs/`; expected pytest output is `2 passed`.

### LA-029 / UKOPS command and guard

Run only after B212/F finishes. The actual ops callback sets `POLISYOS_RUN_INTEGRATION=1` for its nested C7 `uv run pytest`; keep the public server-only gate enabled:

```sh
set -euo pipefail
freeze_sha=9de48febba1ef18c8e1252dc027cb0d89b88abc3
attempt=attempt-01
E02_CAPTURE_RUN=/scratch/e02-child-capture/$freeze_sha/$attempt/la029
artifact_root=/scratch/ukraine-artifacts-$freeze_sha-$attempt
cache=/scratch/e02-pytest-cache-$freeze_sha-$attempt-la029
basetemp=/scratch/e02-pytest-tmp-$freeze_sha-$attempt-la029
bench=file:///scratch/e02-benchmarks-$freeze_sha-$attempt-la029
test ! -e "$E02_CAPTURE_RUN" && test ! -L "$E02_CAPTURE_RUN"
test ! -e "$artifact_root" && test ! -L "$artifact_root"
mkdir "$E02_CAPTURE_RUN"
mkdir "$E02_CAPTURE_RUN/logs"
test ! -e "$E02_CAPTURE_RUN/sitecustomize.py" && test ! -L "$E02_CAPTURE_RUN/sitecustomize.py"
cp -p "/scratch/e02-child-capture/$freeze_sha/sitecustomize.py" "$E02_CAPTURE_RUN/sitecustomize.py"
test "$(sha256sum "$E02_CAPTURE_RUN/sitecustomize.py" | awk '{print $1}')" = 4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs" E02_CAPTURE_LANE=la029
export PYTHONPATH="$E02_CAPTURE_RUN:/workspace/polisyos/policy-engine/src${PYTHONPATH:+:$PYTHONPATH}"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
cd /workspace/polisyos/policy-engine
set +e
POLISYOS_SERVER_EXECUTION=1 \
UV_PROJECT_ENVIRONMENT=/scratch/root-venv UV_NO_SYNC=1 UV_FROZEN=1 \
PYTEST_ADDOPTS="-o cache_dir=$cache --basetemp=$basetemp --benchmark-storage=$bench" \
/scratch/root-venv/bin/python tools/ops_runners/ukraine_data/validate_part_a.py \
  --workspace-root /workspace/polisyos/policy-engine --root "$artifact_root" \
  > "$E02_CAPTURE_RUN/la029.manifest.stdout" 2> "$E02_CAPTURE_RUN/la029.manifest.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$E02_CAPTURE_RUN/la029.exit"
```

The outer summary is JSON in `la029.manifest.stdout`; its output path names `part_a_gate_manifest.json` under `$artifact_root`. Require outer/gate `status=passed`, `server_only=true`, `passed=true`, `skipped=false`, and the recorded exact child argv `uv run pytest -q tests/integration/test_c7_synthetic_full_pipeline.py`. Bind that unique child's `logs/la029-*.json`, `.stdout.bin`, and `.stderr.bin`; check byte lengths and hashes, because the typed manifest keeps only truncated stream excerpts.

After that positive consumer, run the actual guard without the server marker as a low-cost negative control; this invokes no child test and must refuse:

```sh
set -euo pipefail
E02_CAPTURE_RUN=/scratch/e02-child-capture/9de48febba1ef18c8e1252dc027cb0d89b88abc3/attempt-01/la029
set +e
env -u POLISYOS_SERVER_EXECUTION PYTHONPATH=/workspace/polisyos/policy-engine/src \
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
status=$?
set -e
test "$status" = 0
```

### DFK invalid-byte filename command

Run last, from `/workspace/polisyos/policy-engine`, with the same Python 3.14 root environment and a fresh guest-native repo. The construction below intentionally has no remove/rmtree branch:

```sh
set -euo pipefail
freeze_sha=9de48febba1ef18c8e1252dc027cb0d89b88abc3
attempt=attempt-01
E02_CAPTURE_RUN=/scratch/e02-child-capture/$freeze_sha/$attempt/dfk
DFK_REPO_ROOT=/tmp/dfk-mini-$freeze_sha-$attempt
test ! -e "$E02_CAPTURE_RUN" && test ! -L "$E02_CAPTURE_RUN"
test ! -e "$DFK_REPO_ROOT" && test ! -L "$DFK_REPO_ROOT"
mkdir "$E02_CAPTURE_RUN"
mkdir "$E02_CAPTURE_RUN/logs"
test ! -e "$E02_CAPTURE_RUN/sitecustomize.py" && test ! -L "$E02_CAPTURE_RUN/sitecustomize.py"
cp -p "/scratch/e02-child-capture/$freeze_sha/sitecustomize.py" "$E02_CAPTURE_RUN/sitecustomize.py"
test "$(sha256sum "$E02_CAPTURE_RUN/sitecustomize.py" | awk '{print $1}')" = 4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2
export E02_CAPTURE_DIR="$E02_CAPTURE_RUN/logs" E02_CAPTURE_LANE=dfk
export DFK_REPO_ROOT PYTHONPATH="$E02_CAPTURE_RUN${PYTHONPATH:+:$PYTHONPATH}"
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
/scratch/root-venv/bin/python - \
  > "$E02_CAPTURE_RUN/dfk.fixture.stdout" 2> "$E02_CAPTURE_RUN/dfk.fixture.stderr" <<'PY'
import os
import subprocess
from pathlib import Path
root = Path(os.environ["DFK_REPO_ROOT"])
if root.exists() or root.is_symlink():
    raise SystemExit(f"refusing existing DFK fixture path: {root}")
root.mkdir(parents=False, exist_ok=False)
def git(*args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
git("init", "--quiet")
raw_name = b"bad_\xff.json"
name = os.fsdecode(raw_name)
(root / name).write_bytes(b"{}\n")
git("add", "--", name)
git("-c", "user.name=E02 fixture", "-c", "user.email=e02-fixture@example.invalid",
    "commit", "--allow-empty", "-m", "raw filename fixture")
assert git("ls-files", "-z").stdout == raw_name + b"\0"
PY
cd /workspace/polisyos/policy-engine
set +e
/scratch/root-venv/bin/python -m tools.quality.validation.schema_fqn_census \
  --repo-root "$DFK_REPO_ROOT" \
  > "$E02_CAPTURE_RUN/dfk.cli.stdout.json" 2> "$E02_CAPTURE_RUN/dfk.cli.stderr"
status=$?
set -e
printf '%s\n' "$status" > "$E02_CAPTURE_RUN/dfk.cli.exit"
test "$status" = 0
```

The actual CLI JSON is `dfk.cli.stdout.json`; it should decode as ASCII JSON with the raw basename escaped as `bad_\\udcff.json`, while the parsed selected/read path equals `os.fsdecode(b"bad_\xff.json")`. Require `result=complete_for_selected_local_text_inputs`, one tracked/selected/successfully-read file, zero unreadable/unsupported inputs, a complete Git/read receipt, and `head` present. Reconcile every embedded Git command and the ten child JSON/stream captures under `logs/`. Keep fixture content exactly `b"{}\n"` (three bytes). After each lane, hash its output tree to a new `SHA256SUMS`; require that file absent first. Never reuse a capture or fixture path and never delete a prior attempt.
