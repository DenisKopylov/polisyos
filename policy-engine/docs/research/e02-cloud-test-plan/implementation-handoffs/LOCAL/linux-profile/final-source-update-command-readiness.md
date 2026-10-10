# Final-source Linux update command readiness

Read-only preparation, 2026-10-10. No Git refs, source bytes, environments, worker files, or Q2 outputs were changed. No transfer or product test ran. The final source SHA/tree are still pending; keep both command variables unset until root supplies the exact committed freeze.

## Existing Linux worker and baseline

The append-only base is commit 13e411da7d9e505856fc336b3d25fd0aabdb1f66, tree 8d8c4082febf1676dd86084106f3266d8b2131a3, on codex/e02-unified-local-20261009. Its actual commit parent is 25219d0692c1c54b99f9d40b5c53a6956e2f4e2e. The previous receipt and raw header comparison are in linux-source-update-13e411da-20261010-receipt.md and raw/actual-update-13e411da-20261010/05-parent-header-comparison.stdout.txt.

Read-only inspection confirmed the existing attached worker checkout and bare ref are both at that SHA/tree and branch. Origin remains /scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git; both shallow files remain exactly the single boundary 7574c864a605c50efc033b966807790cbd8d1781. The checkout has no tracked changes. The original bare store is root-owned mode 700. Preserve the current directories and refs.

The dedicated Docker profile is COLIMA_HOME=/Users/deniskopylov/.colima-e02-local, DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local, binary /opt/homebrew/bin/docker, explicit context colima-e02-local. Container e02-local-worker-provision is running with ID 88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6, image sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f, and 2,306,867,200-byte memory cap. Its only mounts are the three existing named volumes: e02-local-uv-pythons at /opt/uv-python, e02-local-uv-cache at /root/.cache/uv, and e02-local-uv-env at /scratch; no bind mount was present.

At this read, /scratch was 12,277,956 KiB total, 5,772,396 KiB used, and 5,902,120 KiB available. Cgroup current was 1,345,363,968 bytes; high/max/OOM counters and pressure averages were zero. These are point-in-time measurements; measure again before copy and after update. No cleanup is part of this plan.

## Current Q2-helper review

The current local helper raw/final-source-linux-wave.sh has SHA-256 86ca3a0dab8ba5187f14ef925724b5e9114b84f0ab9152d3e5b2a2e44cf8ef60. Its Q2 worker preflight reads the attached checkout origin, requires the exact receipted local bare path, validates root ownership/mode, bare status, requested SHA/tree/branch, retained 7574 shallow boundary, and no bare alternates before creating the run directory. A network or HTTPS origin fails the exact-path guard; a missing origin makes git remote get-url origin fail under set -e; a wrong SHA/tree/branch fails its equality guard. Those checks are textually before the run-root existence check and mkdir. No negative behavioral probes were run. Before the eventual Q2 body, separately verify positive exact-origin admission and rejection of HTTPS origin, absent origin, wrong SHA/tree/branch, symlink, non-bare, wrong owned path, and alternates without creating a run directory or entering the package/test driver.

At this helper hash, Q2 input pins are run.py c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf, timeout driver 7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073, primary manifest 26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6, supplement driver 4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49, and supplement manifest ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df. The current files match these hashes; the recipe file hash is e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e. Reconcile the final frozen helper, current runner/manifest, and recipe pins before transferring; a mismatch is a stop, not a reason to override the gate.

## Exact update recipe after final SHA/tree are supplied

Use the host's existing attached branch and one absent incremental-bundle path under ignored LOCAL/linux-profile/raw/. This is an ordinary Git bundle from the committed branch tip, not a worktree copy. The Linux bare path and attached checkout remain unchanged. These commands are a recipe only and were not run.

~~~sh
source_checkout=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
branch=codex/e02-unified-local-20261009
base=13e411da7d9e505856fc336b3d25fd0aabdb1f66
base_tree=8d8c4082febf1676dd86084106f3266d8b2131a3
new_sha=ROOT_SUPPLIED_FULL_40_CHARACTER_SHA
new_tree=ROOT_SUPPLIED_FULL_40_CHARACTER_TREE
bundle="$source_checkout/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/e02-source-update-$new_sha.bundle"

docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}
container=e02-local-worker-provision
worker_bare=/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git
worker_checkout=/workspace/polisyos
worker_bundle=/scratch/e02-source-update-$new_sha.bundle
~~~

### 1. Freeze-bound host preflight and bundle

Run only after root supplies the full new SHA/tree and the candidate checkout is attached at that exact committed freeze. Recheck the final Q2 input/manifest and five Python lock/version pins before bundling; the full pin block is in append-only-source-update-plan.md. Stop if final code or Q2 input pins differ from the current reviewed helper/recipe.

~~~sh
test "$branch" = codex/e02-unified-local-20261009
test "$(git -C "$source_checkout" symbolic-ref --short HEAD)" = "$branch"
test "$(git -C "$source_checkout" rev-parse HEAD)" = "$new_sha"
test "$(git -C "$source_checkout" rev-parse "$new_sha^{tree}")" = "$new_tree"
test "$(git -C "$source_checkout" rev-parse "$base^{tree}")" = "$base_tree"
test "$(git -C "$source_checkout" rev-parse --is-shallow-repository)" = false
test -z "$(git -C "$source_checkout" status --porcelain=v1 --untracked-files=no)"
git -C "$source_checkout" merge-base --is-ancestor "$base" "$new_sha"
test ! -e "$bundle" && test ! -L "$bundle"
git -C "$source_checkout" cat-file -p "$base"
for commit in $(git -C "$source_checkout" rev-list --reverse --topo-order "$base..$new_sha"); do
  printf 'COMMIT %s\n' "$commit"
  git -C "$source_checkout" cat-file -p "$commit" | sed -n '/^tree /p;/^parent /p'
done
git -C "$source_checkout" bundle create "$bundle" "refs/heads/$branch" "^$base"
git -C "$source_checkout" bundle verify "$bundle"
git -C "$source_checkout" bundle list-heads "$bundle"
shasum -a 256 "$bundle"
~~~

Capture actual tree and ordered parent headers from cat-file for the base and every update commit. Do not use %P from git log as a substitute for actual headers. The bundle must name the actual branch ref and resolve to new_sha.

### 2. Verify the existing worker before copying

Remeasure the named container, mounts, /scratch free space, cgroup current/events/pressure, current Git refs, shallow files, origin, and clean checkout. Require the exact ID/image/cap and three named volumes above; no bind mounts; empty GIT_ALTERNATE_OBJECT_DIRECTORIES and GIT_OBJECT_DIRECTORY; an absent bundle destination; and both worker HEADs still exactly base/base_tree. Stop on any discrepancy.

~~~sh
docker_e02 inspect --format 'id={{.Id}} state={{.State.Status}} image={{.Image}} memory={{.HostConfig.Memory}} mounts={{json .Mounts}}' "$container"
docker_e02 exec -i "$container" /bin/bash -s -- "$worker_bare" "$worker_checkout" "$branch" "$base" "$base_tree" <<'WORKER_PREFLIGHT'
set -euo pipefail
bare=$1; repo=$2; branch=$3; base=$4; tree=$5
test -d "$bare" && test ! -L "$bare"
test "$(stat -c '%u:%g:%a' "$bare")" = '0:0:700'
test "$(git --git-dir="$bare" rev-parse --is-bare-repository)" = true
test "$(git --git-dir="$bare" rev-parse HEAD)" = "$base"
test "$(git --git-dir="$bare" rev-parse 'HEAD^{tree}')" = "$tree"
test "$(git --git-dir="$bare" symbolic-ref --short HEAD)" = "$branch"
test "$(git --git-dir="$bare" rev-parse --is-shallow-repository)" = true
test "$(cat "$bare/shallow")" = 7574c864a605c50efc033b966807790cbd8d1781
test ! -e "$bare/objects/info/alternates" && test ! -L "$bare/objects/info/alternates"
test -d "$repo" && test ! -L "$repo" && test -d "$repo/.git" && test ! -L "$repo/.git"
test "$(git -C "$repo" rev-parse HEAD)" = "$base"
test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$tree"
test "$(git -C "$repo" symbolic-ref --short HEAD)" = "$branch"
test "$(git -C "$repo" rev-parse --is-shallow-repository)" = true
test "$(cat "$repo/.git/shallow")" = 7574c864a605c50efc033b966807790cbd8d1781
test "$(git -C "$repo" remote get-url origin)" = "$bare"
test -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)"
test -z "$(printenv GIT_ALTERNATE_OBJECT_DIRECTORIES || true)"
test -z "$(printenv GIT_OBJECT_DIRECTORY || true)"
git --git-dir="$bare" fsck --connectivity-only --no-reflogs HEAD
git -C "$repo" fsck --connectivity-only --no-reflogs HEAD
df -Pk /scratch
cat /sys/fs/cgroup/memory.current
cat /sys/fs/cgroup/memory.events
cat /sys/fs/cgroup/memory.pressure
WORKER_PREFLIGHT
~~~

Compare inspect mount types/names to exactly the three named volumes above and inspect the container environment for empty Git object-directory variables. Require /scratch/e02-source-update-$new_sha.bundle to be absent before the single copy.

### 3. Copy and advance append-only

Copy one incremental bundle into the existing worker. Verify its hash in the worker, then verify bundle prerequisites before fetching. The compare-and-swap moves only the existing bare branch ref from the exact 13e411 base. The attached checkout advances through an ordinary fetch and merge --ff-only. Both shallow files stay at 7574. No clone, checkout, reset, force refspec, unshallow, or deletion.

~~~sh
docker_e02 exec "$container" /bin/bash -lc "test ! -e '$worker_bundle' && test ! -L '$worker_bundle'"
docker_e02 cp "$bundle" "$container:$worker_bundle"
docker_e02 exec "$container" sha256sum "$worker_bundle"
~~~

Compare that hash to the host shasum result, then run:

~~~sh
docker_e02 exec -i "$container" /bin/bash -s -- "$worker_bare" "$worker_checkout" "$worker_bundle" "$branch" "$base" "$base_tree" "$new_sha" "$new_tree" <<'WORKER_UPDATE'
set -euo pipefail
bare=$1; repo=$2; bundle=$3; branch=$4; base=$5; base_tree=$6; new_sha=$7; new_tree=$8
test "$(git --git-dir="$bare" rev-parse HEAD)" = "$base"
test "$(git --git-dir="$bare" rev-parse 'HEAD^{tree}')" = "$base_tree"
test "$(git -C "$repo" rev-parse HEAD)" = "$base"
test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$base_tree"
git --git-dir="$bare" bundle verify "$bundle"
git --git-dir="$bare" fetch --no-tags "$bundle" "refs/heads/$branch"
test "$(git --git-dir="$bare" rev-parse FETCH_HEAD)" = "$new_sha"
test "$(git --git-dir="$bare" rev-parse 'FETCH_HEAD^{tree}')" = "$new_tree"
git --git-dir="$bare" merge-base --is-ancestor "$base" FETCH_HEAD
git --git-dir="$bare" update-ref "refs/heads/$branch" "$new_sha" "$base"
test "$(git --git-dir="$bare" rev-parse HEAD)" = "$new_sha"
test "$(cat "$bare/shallow")" = 7574c864a605c50efc033b966807790cbd8d1781
git -C "$repo" fetch --no-tags origin "refs/heads/$branch:refs/remotes/origin/$branch"
test "$(git -C "$repo" rev-parse "refs/remotes/origin/$branch")" = "$new_sha"
git -C "$repo" merge-base --is-ancestor HEAD "refs/remotes/origin/$branch"
git -C "$repo" merge --ff-only "refs/remotes/origin/$branch"
test "$(git -C "$repo" rev-parse HEAD)" = "$new_sha"
test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$new_tree"
test "$(git -C "$repo" symbolic-ref --short HEAD)" = "$branch"
test "$(git -C "$repo" remote get-url origin)" = "$bare"
test "$(cat "$repo/.git/shallow")" = 7574c864a605c50efc033b966807790cbd8d1781
test -z "$(git -C "$repo" status --porcelain=v1 --untracked-files=all)"
git --git-dir="$bare" fsck --connectivity-only --no-reflogs HEAD
git -C "$repo" fsck --connectivity-only --no-reflogs HEAD
for commit in $(git -C "$repo" rev-list --reverse --topo-order "$base..$new_sha"); do
  printf 'COMMIT %s\n' "$commit"
  git -C "$repo" cat-file -p "$commit" | sed -n '/^tree /p;/^parent /p'
done
WORKER_UPDATE
~~~

If anything fails after the bare ref compare-and-swap, preserve the append-only state and report both stores' refs, trees, shallow files, and full command output. Never move either ref backward. On the authorized execution, capture each stage's exact argv/stdin/stdout/stderr/exit in the ignored raw receipt directory, following the existing six-stage receipt protocol.

### 4. Post-update readback

Read back the bare store and attached checkout independently: branch, SHA, tree, origin, clean visible status, and connectivity. Require both shallow files to remain the old 7574 boundary. Compare the full commit tree/ordered-parent headers against host output. Recheck the five Q2 input hashes, primary manifest Git blob and content at new_sha, four ignored inputs' regular-file/ignore state, five Python lock/version pins, runtime versions, and uv pip checks using the readback commands in append-only-source-update-plan.md. A changed helper/input/lock pin is a stop for a fresh review, not an install or pin bypass.

The capture hook remains freeze-scoped. The old 7574 hook is not reused. Only after a separate native-test grant, preflight /scratch/e02-child-capture/$new_sha/sitecustomize.py as absent or exact, copy the existing pinned hook bytes (4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2), and verify its SHA. The source update plan does not run Q2, package builds, product tests, DoWhy, UKOPS, or DFK.
