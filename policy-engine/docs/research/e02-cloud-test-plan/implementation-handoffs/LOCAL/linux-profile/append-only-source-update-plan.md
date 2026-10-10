# Append-only update of the existing Linux checkout

This is a read-only preparation plan for the next root-supplied C12 freeze. No new freeze SHA/tree has been supplied, so no Git refs, objects, source checkout, container files, or environment were changed. Current measured state and pins are in [append-only-source-update-current-state-7574c864-20261010.txt](raw/append-only-source-update-current-state-7574c864-20261010.txt).

Reuse only the existing worker bare store and attached checkout. The source stream is a Git bundle made from the host's own attached branch; it carries the new Git objects, not a source-tree copy. The host bare store remains the immutable record of the original 7574 import. On Linux, fetch the bundle into the existing shallow bare store, advance its branch ref with a compare-and-swap only after proving the new commit descends from 7574, then fetch from that bare store into the existing checkout and `merge --ff-only`. Preserve both existing `shallow` files as the single line `7574c864a605c50efc033b966807790cbd8d1781`.

This is the same transport class at a deeper boundary (`P40`): frozen source identity and physical object ownership must be proven from the objects actually consumed, not guessed from the command or the worktree. The closure uses the supplied committed SHA/tree, source ancestry and actual commit headers, an incremental Git bundle, exact base-ref compare-and-swap, fast-forward merge, unchanged shallow boundary, and post-update content pins. The existing checkout and three named volumes remain in place; there is no product capability claim or product test in this plan.

## Gate before any writes

Wait for the root to provide the exact `NEW_SHA` and `NEW_TREE`. Substitute them literally below; do not infer them from a mutable worktree. The host branch must still be attached to `codex/e02-unified-local-20261009` and have `HEAD == NEW_SHA`; `NEW_SHA^{tree}` must equal `NEW_TREE`; and `7574c864...` must be an ancestor of `NEW_SHA`. Read `git cat-file -p` headers for 7574 and every commit in the update range and save the ordered `tree` and `parent` lines. `git log --format=%P` is not acceptable for this proof: the worker is shallow, and its log view suppresses 7574's real parent `5e312037e180938aa643abccfd727a2a12b9a691`.

Before bundling, re-read all five Q2 inputs and compare to the pin set below, check the new commit's tracked primary-manifest bytes against that pin, and require all five app/DoWhy lock files to match the installed profile pins. Any changed manifest or lock is a stop for a fresh recipe/input decision before updating Linux. Do not copy or overwrite an input to make a mismatch pass. Measure `/scratch` free space and cgroup current/events/pressure before and after transfer. The last observed free scratch was 5,902,780 KiB; that is a snapshot, not a reserve guarantee.

Use `shasum -a 256` on the five host Q2 files and the capture hook, and compare with the complete pin list under “Post-update readback.” For the tracked manifest and all five lock/version files, hash the bytes read from `NEW_SHA` with `git show NEW_SHA:path | shasum -a 256`; stop if any expected hash differs. These checks bind source bytes to the frozen commit instead of the mutable host working tree.

## Exact update sequence once the root supplies the freeze

The following is a command recipe, not an executable helper. Run it only after root supplies `NEW_SHA` and `NEW_TREE` and grants this source update. `BUNDLE` must be an absent path under the ignored Linux-profile `raw/` directory. The dedicated container is `e02-local-worker-provision` through `colima-e02-local`; preserve its three existing named volumes and empty Git object-directory environment.

```sh
source_checkout=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
branch=codex/e02-unified-local-20261009
base=7574c864a605c50efc033b966807790cbd8d1781
new_sha='ROOT_SUPPLIED_FULL_40_HEX_SHA'
new_tree='ROOT_SUPPLIED_FULL_40_HEX_TREE'
bundle="$source_checkout/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/e02-source-update-$new_sha.bundle"

cd "$source_checkout"
test -z "${GIT_ALTERNATE_OBJECT_DIRECTORIES:-}"
test -z "${GIT_OBJECT_DIRECTORY:-}"
test "$(git -C "$source_checkout" rev-parse --is-shallow-repository)" = false
test "$(git -C "$source_checkout" symbolic-ref --short HEAD)" = "$branch"
test "$(git -C "$source_checkout" rev-parse HEAD)" = "$new_sha"
test "$(git -C "$source_checkout" rev-parse "$new_sha^{tree}")" = "$new_tree"
git -C "$source_checkout" merge-base --is-ancestor "$base" "$new_sha"
test ! -e "$bundle"
git -C "$source_checkout" cat-file -p "$base"
for commit in $(git -C "$source_checkout" rev-list --reverse --topo-order "$base..$new_sha"); do
  printf 'COMMIT %s\n' "$commit"
  git -C "$source_checkout" cat-file -p "$commit" | sed -n '/^tree /p;/^parent /p'
done

while read -r expected path; do
  actual=$(git -C "$source_checkout" show "$new_sha:$path" | shasum -a 256 | awk '{print $1}')
  test "$actual" = "$expected"
done <<'SOURCE_LOCK_PINS'
b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267 policy-engine/pyproject.toml
e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463 policy-engine/uv.lock
df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447 policy-engine/workers/dowhy-014/pyproject.toml
c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a policy-engine/workers/dowhy-014/uv.lock
7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d policy-engine/workers/dowhy-014/.python-version
SOURCE_LOCK_PINS
manifest_path=policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json
test "$(git -C "$source_checkout" show "$new_sha:$manifest_path" | shasum -a 256 | awk '{print $1}')" = 26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6
test "$(git -C "$source_checkout" rev-parse "$new_sha:$manifest_path")" = 0e714774f27236b54353913527ebfbd1ff8f1965
shasum -a 256 -c - <<'HOST_INPUTS'
c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py
7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py
26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json
4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py
ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json
4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py
HOST_INPUTS
```

For every SHA emitted by `rev-list`, capture the actual `tree` and ordered `parent` headers using `git -C "$source_checkout" cat-file -p "$commit"`; save this output with the update receipt. Next create and verify the incremental bundle from the committed branch tip (which the checks above bind to `new_sha`):

```sh
git -C "$source_checkout" bundle create "$bundle" "refs/heads/$branch" "^$base"
git -C "$source_checkout" bundle verify "$bundle"
git -C "$source_checkout" bundle list-heads "$bundle"
bundle_sha=$(shasum -a 256 "$bundle" | awk '{print $1}')
printf 'bundle_sha256=%s\n' "$bundle_sha"
```

For worker commands, define the dedicated Docker wrapper exactly as used by the existing profile:

```sh
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}

worker_bare=/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git
worker_checkout=/workspace/polisyos
worker_bundle=/scratch/e02-source-update-$new_sha.bundle
container=e02-local-worker-provision
```

Before `docker cp`, re-read the worker bare/checkout HEAD, branch, origin, and one-line shallow files and require both HEADs and both shallow boundaries equal `base`; require the checkout tracked/visible-untracked status clean; verify the exact container ID `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`, image `sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`, only the three existing named uv volumes, and no bind mounts; ensure the destination bundle does not exist. Recheck empty container `GIT_ALTERNATE_OBJECT_DIRECTORIES` and `GIT_OBJECT_DIRECTORY` and `/scratch` headroom/cgroup state. Copy the bundle once, verify its SHA-256 in the container, and run `git --git-dir="$worker_bare" bundle verify "$worker_bundle"`. If bundle verification fails against the existing shallow boundary, stop; do not unshallow or replace the checkout.

```sh
docker_e02 exec -i "$container" /bin/bash -s -- "$worker_bare" "$worker_checkout" "$branch" "$base" <<'WORKER_PREFLIGHT'
set -euo pipefail
bare=$1; repo=$2; branch=$3; base=$4
test "$(git --git-dir="$bare" rev-parse HEAD)" = "$base"
test "$(git --git-dir="$bare" symbolic-ref --short HEAD)" = "$branch"
test "$(cat "$bare/shallow")" = "$base"
test "$(git -C "$repo" rev-parse HEAD)" = "$base"
test "$(git -C "$repo" symbolic-ref --short HEAD)" = "$branch"
test "$(cat "$repo/.git/shallow")" = "$base"
test "$(git -C "$repo" remote get-url origin)" = "$bare"
test -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)"
test ! -e "$bare/objects/info/alternates"
test ! -e "$repo/.git/objects/info/alternates"
test -z "${GIT_ALTERNATE_OBJECT_DIRECTORIES:-}"
test -z "${GIT_OBJECT_DIRECTORY:-}"
df -Pk /scratch
cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.events /sys/fs/cgroup/memory.pressure
WORKER_PREFLIGHT
test "$(docker_e02 inspect --format '{{.Id}}' "$container")" = 88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6
test "$(docker_e02 inspect --format '{{.Image}}' "$container")" = sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f
test "$(docker_e02 inspect --format '{{.State.Running}}' "$container")" = true
test "$(docker_e02 inspect --format '{{.HostConfig.Memory}}' "$container")" = 2306867200
test "$(docker_e02 ps --format '{{.Names}}')" = "$container"
docker_e02 inspect --format '{{json .Mounts}}' "$container" | python3 -c '
import json,sys
actual={(r["Type"],r.get("Name",""),r["Destination"]) for r in json.load(sys.stdin)}
expected={("volume","e02-local-uv-pythons","/opt/uv-python"),("volume","e02-local-uv-cache","/root/.cache/uv"),("volume","e02-local-uv-env","/scratch")}
if actual != expected: raise SystemExit(f"unexpected worker mounts: {sorted(actual)!r}")
'
docker_e02 inspect --format '{{json .Config.Env}}' "$container" | python3 -c '
import json,sys
guarded={"GIT_ALTERNATE_OBJECT_DIRECTORIES","GIT_OBJECT_DIRECTORY"}
bad=[x for x in json.load(sys.stdin) if x.partition("=")[0] in guarded and x.partition("=")[2]]
if bad: raise SystemExit(f"nonempty Git object environment: {bad!r}")
'
docker_e02 test ! -e "$worker_bundle"
```

```sh
docker_e02 cp "$bundle" "$container:$worker_bundle"
test "$(docker_e02 exec "$container" sha256sum "$worker_bundle" | awk '{print $1}')" = "$bundle_sha"
```

Import only to `FETCH_HEAD` in the existing worker bare store, then compare-and-swap its branch ref from the exact old SHA. The lack of a leading `+` on all fetch refspecs matters. No `--depth`, `--unshallow`, `--update-shallow`, reset, checkout, clone, or rebase is allowed.

```sh
docker_e02 exec -i "$container" /bin/bash -s -- "$worker_bare" "$worker_checkout" "$worker_bundle" "$branch" "$base" "$new_sha" "$new_tree" <<'WORKER_UPDATE'
set -euo pipefail
bare=$1; repo=$2; bundle=$3; branch=$4; base=$5; new_sha=$6; new_tree=$7
git --git-dir="$bare" bundle verify "$bundle"
git --git-dir="$bare" fetch --no-tags "$bundle" "refs/heads/$branch"
test "$(git --git-dir="$bare" rev-parse FETCH_HEAD)" = "$new_sha"
git --git-dir="$bare" merge-base --is-ancestor "$base" FETCH_HEAD
git --git-dir="$bare" update-ref "refs/heads/$branch" "$new_sha" "$base"
test "$(git --git-dir="$bare" rev-parse HEAD)" = "$new_sha"
test "$(cat "$bare/shallow")" = "$base"

git -C "$repo" fetch --no-tags origin "refs/heads/$branch:refs/remotes/origin/$branch"
test "$(git -C "$repo" rev-parse "refs/remotes/origin/$branch")" = "$new_sha"
git -C "$repo" merge-base --is-ancestor HEAD "refs/remotes/origin/$branch"
git -C "$repo" merge --ff-only "refs/remotes/origin/$branch"
test "$(git -C "$repo" rev-parse HEAD)" = "$new_sha"
test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$new_tree"
test "$(cat "$repo/.git/shallow")" = "$base"
git --git-dir="$bare" fsck --connectivity-only --no-reflogs HEAD
git -C "$repo" fsck --connectivity-only --no-reflogs HEAD
WORKER_UPDATE
```

`worker_bare` and `worker_checkout` above denote the existing paths `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git` and `/workspace/polisyos`. The `update-ref` compare-and-swap is only for the bare store's symbolic branch (which cannot be fetched into as the checked-out `HEAD`); its expected old value is the frozen base, after `merge-base --is-ancestor` proves the proposed move is forward. The attached checkout itself advances through the ordinary `merge --ff-only`.

If a command fails after the bare ref moves, preserve that append-only state and report both refs, shallow files, and receipt; never restore the old head. The official [`git bundle` documentation](https://git-scm.com/docs/git-bundle) describes revision-excluded bundles and prerequisites. [`git fetch`](https://git-scm.com/docs/git-fetch) documents non-forced refspec updates and refusal to fetch directly into the checked-out branch, which is why the bare ref uses a verified compare-and-swap and the attached checkout uses a fast-forward merge.

Run the following only after the fast-forward. It binds the tracked manifest to `NEW_SHA`, rechecks all external input and lock bytes, and confirms the ignored files remain ordinary ignored files; it makes no writes:

```sh
docker_e02 exec -i "$container" /bin/bash -lc "cd '$worker_checkout' && sha256sum -c -" <<'PINS'
c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py
7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py
26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json
4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py
ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json
b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267  policy-engine/pyproject.toml
e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463  policy-engine/uv.lock
df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447  policy-engine/workers/dowhy-014/pyproject.toml
c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a  policy-engine/workers/dowhy-014/uv.lock
7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d  policy-engine/workers/dowhy-014/.python-version
PINS

docker_e02 exec -i "$container" /bin/bash -s -- "$worker_checkout" "$new_sha" <<'MANIFEST_VERIFY'
set -euo pipefail
repo=$1
new_sha=$2
cd "$repo"
manifest=policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json
git ls-files --error-unmatch -- "$manifest" >/dev/null
got=$(git show "$new_sha:$manifest" | sha256sum | awk '{print $1}')
test "$got" = 26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6
printf 'frozen-primary-manifest-content-sha256=%s\n' "$got"
for p in \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py \
  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json; do
  test -f "$p" && test ! -L "$p" && git check-ignore --quiet -- "$p"
done
MANIFEST_VERIFY

docker_e02 exec "$container" /bin/bash -lc '
set -euo pipefail
test "$(uv --version)" = "uv 0.9.21"
/scratch/root-venv/bin/python -c "import sys,importlib.metadata as m; assert sys.version_info[:2] == (3,14); assert m.version(\"hatchling\") == \"1.27.0\"; print(\"root\",sys.version.split()[0],\"Hatchling\",m.version(\"hatchling\"))"
/scratch/dowhy-venv/bin/python -c "import sys,dowhy; assert sys.version_info[:2] == (3,12); assert dowhy.__version__ == \"0.14\"; print(\"DoWhy\",sys.version.split()[0],dowhy.__version__)"
uv pip check --python /scratch/root-venv/bin/python
uv pip check --python /scratch/dowhy-venv/bin/python
'
```

The tracked manifest hash must equal `26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6`; on mismatch stop and rebind the wave recipe. The separate capture hook is freeze-scoped: only before a later authorized wave, preflight `/scratch/e02-child-capture/$new_sha/sitecustomize.py` as absent or exact and then copy the same `4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2` bytes. Do not reuse the old freeze-specific hook path for a different SHA.

## Post-update readback; no tests/builds here

Read back both worker refs, branch attachment, new tree, exact unchanged shallow files, clean tracked status, connectivity, bundle SHA, and all parent headers. Read back all five Q2 file hashes below and require the primary manifest also matches the Git blob/content at `NEW_SHA`; require the four ignored runner files remain ignored, regular files, and unchanged. The separate child-capture path is freeze-scoped: for a later authorized wave, preflight `/scratch/e02-child-capture/$new_sha/sitecustomize.py` as absent or exact before copying the same pinned hook there. Do not reuse the old freeze-specific hook path for a different SHA.

Then recheck the five lock pins and the existing runtime versions/`uv pip check`; do not sync/install if any lock differs. Root runtime is Python 3.14.0 with Hatchling 1.27.0; DoWhy worker is Python 3.12.12 with DoWhy 0.14. This source-update plan does not run product tests, builds, the Q2 wave, LA029, B212, or DFK.

```text
c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py
7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py
26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json
4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py
ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json
4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py

b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267  policy-engine/pyproject.toml
e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463  policy-engine/uv.lock
df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447  policy-engine/workers/dowhy-014/pyproject.toml
c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a  policy-engine/workers/dowhy-014/uv.lock
7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d  policy-engine/workers/dowhy-014/.python-version
```

Acceptance is the supplied SHA/tree in both existing Linux repos, recorded actual source parent headers, `7574` still the sole shallow boundary, successful connectivity, unchanged pinned inputs/locks, and a complete readback receipt. The full next source SHA/tree remains pending root freeze; this plan does not authorize executing the update.
