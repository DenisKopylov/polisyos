#!/usr/bin/env bash
set -eo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  final-source-linux-wave.sh transport SOURCE_CHECKOUT ATTACHED_BRANCH FROZEN_SHA FROZEN_TREE
  final-source-linux-wave.sh resume SOURCE_CHECKOUT ATTACHED_BRANCH FROZEN_SHA FROZEN_TREE
  final-source-linux-wave.sh preflight-resume SOURCE_CHECKOUT ATTACHED_BRANCH FROZEN_SHA FROZEN_TREE
  E02_ROOT_HEAVY_SLOT_GRANT=FROZEN_SHA final-source-linux-wave.sh q2 ATTACHED_BRANCH FROZEN_SHA FROZEN_TREE UNIQUE_ATTEMPT

transport starts a new clone only when all three destinations are absent.
resume validates and continues only the recorded root-created 7574c864 partial transport.
q2 requires the same freeze plus root's explicit serialized heavy-slot grant.
q2 runs the admitted current primary set x 3 profiles, then six selectors x 3.
The historical 100-ID subset remains required within the current 127-ID set.
The supplement reuses the primary wave's installed environment and wheels.
USAGE
  exit 2
}
die() { printf 'e02-final-linux: %s\n' "$*" >&2; exit 1; }
[[ $# -ge 1 ]] || usage
MODE=$1
shift

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd -P)
LOCAL_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd -P)
Q2_HOST="$LOCAL_DIR/q2-packaging"
Q2_REL='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging'
CONTAINER='e02-local-worker-provision'
CONTAINER_ID='88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6'
IMAGE_ID='sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f'
DOCKER=/opt/homebrew/bin/docker
REPO=/workspace/polisyos
RESUME_SHA='7574c864a605c50efc033b966807790cbd8d1781'
RESUME_TREE='9561394a619e21b92680d79a1aa812da6892967c'
RESUME_BRANCH='codex/e02-unified-local-20261009'

docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  "$DOCKER" --context colima-e02-local "$@"
}
check_sha() {
  [[ $1 =~ ^[0-9a-f]{40}$ ]] || die "$2 must be a full lowercase 40-character Git ID"
}
check_host_git_object_environment() {
  [[ -z ${GIT_ALTERNATE_OBJECT_DIRECTORIES:-} ]] || die "refusing nonempty host GIT_ALTERNATE_OBJECT_DIRECTORIES"
  [[ -z ${GIT_OBJECT_DIRECTORY:-} ]] || die "refusing nonempty host GIT_OBJECT_DIRECTORY"
}
check_source_freeze() {
  local source_checkout=$1 branch=$2 freeze_sha=$3 freeze_tree=$4
  check_host_git_object_environment
  check_sha "$freeze_sha" FROZEN_SHA
  check_sha "$freeze_tree" FROZEN_TREE
  git check-ref-format --branch "$branch" >/dev/null || die "invalid branch name"
  [[ -f "$source_checkout/.git" || -d "$source_checkout/.git" ]] || die "source checkout lacks Git metadata"
  [[ $(git -C "$source_checkout" symbolic-ref --short HEAD) == "$branch" ]] || die "source checkout detached or on another branch"
  [[ $(git -C "$source_checkout" rev-parse HEAD) == "$freeze_sha" ]] || die "source checkout HEAD differs from root freeze"
  [[ $(git -C "$source_checkout" rev-parse 'HEAD^{tree}') == "$freeze_tree" ]] || die "source tree differs from root freeze"
  [[ -z $(git -C "$source_checkout" status --porcelain=v1 --untracked-files=no) ]] || die "tracked source changes remain"
}
check_resume_source_attachment() {
  local source_checkout=$1 branch=$2 freeze_sha=$3 freeze_tree=$4 source_head manifest_sha
  check_host_git_object_environment
  [[ $branch == "$RESUME_BRANCH" && $freeze_sha == "$RESUME_SHA" && $freeze_tree == "$RESUME_TREE" ]] || die "resume source identity differs from the recorded freeze"
  [[ -f "$source_checkout/.git" || -d "$source_checkout/.git" ]] || die "source checkout lacks Git metadata"
  [[ $(git -C "$source_checkout" symbolic-ref --short HEAD) == "$branch" ]] || die "source checkout is detached or on another branch"
  [[ $(git -C "$source_checkout" rev-parse "$freeze_sha^{tree}") == "$freeze_tree" ]] || die "recorded frozen commit tree mismatch in attached source"
  source_head=$(git -C "$source_checkout" rev-parse HEAD)
  check_sha "$source_head" CURRENT_ATTACHED_HEAD
  git -C "$source_checkout" merge-base --is-ancestor "$freeze_sha" HEAD || die "recorded freeze is not an ancestor of the attached source branch"
  manifest_sha=$(git -C "$source_checkout" show "$freeze_sha:$Q2_REL/installed-wave-manifest.json" | shasum -a 256 | awk '{print $1}')
  [[ $manifest_sha == '1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277' ]] || die "frozen primary manifest Git blob SHA mismatch"
  printf 'source proof: freeze=%s tree=%s; attached branch=%s HEAD=%s descends from freeze; working-tree cleanliness is not asserted or consumed\n' \
    "$freeze_sha" "$freeze_tree" "$branch" "$source_head"
}
check_host_bare() {
  local host_bare=$1 branch=$2 freeze_sha=$3 freeze_tree=$4
  check_host_git_object_environment
  [[ -d "$host_bare" && ! -L "$host_bare" ]] || die "recorded host bare store is missing or not a real directory"
  [[ $(git --git-dir="$host_bare" rev-parse HEAD) == "$freeze_sha" ]] || die "host bare HEAD mismatch"
  [[ $(git --git-dir="$host_bare" rev-parse 'HEAD^{tree}') == "$freeze_tree" ]] || die "host bare tree mismatch"
  [[ $(git --git-dir="$host_bare" rev-parse --is-shallow-repository) == true ]] || die "host bare is not shallow"
  [[ $(git --git-dir="$host_bare" symbolic-ref --short HEAD) == "$branch" ]] || die "host bare branch mismatch"
  [[ $(cat "$host_bare/shallow") == "$freeze_sha" ]] || die "host bare shallow boundary mismatch"
  [[ $(git --git-dir="$host_bare" config --bool core.bare) == true ]] || die "recorded host store is not bare"
  git --git-dir="$host_bare" fsck --connectivity-only --no-reflogs HEAD >/dev/null || die "host bare connectivity check failed"
}
check_worker_git_state() {
  local worker_bare=$1 branch=$2 freeze_sha=$3 freeze_tree=$4
  docker_e02 exec -i "$CONTAINER" /bin/bash -s -- "$worker_bare" "$REPO" "$branch" "$freeze_sha" "$freeze_tree" <<'WORKER_GIT_CHECK'
set -euo pipefail
bare=$1
repo=$2
branch=$3
sha=$4
tree=$5
fail() { printf 'e02-git-state: %s\n' "$*" >&2; exit 1; }
[[ -z ${GIT_ALTERNATE_OBJECT_DIRECTORIES:-} ]] || fail "worker GIT_ALTERNATE_OBJECT_DIRECTORIES is nonempty"
[[ -z ${GIT_OBJECT_DIRECTORY:-} ]] || fail "worker GIT_OBJECT_DIRECTORY is nonempty"
[[ -d "$bare" && ! -L "$bare" ]] || fail "worker bare path is missing or not a real directory"
[[ -d "$repo" && ! -L "$repo" && -d "$repo/.git" && ! -L "$repo/.git" ]] || fail "attached checkout or Git directory is missing or indirect"
[[ $(stat -c '%u:%g:%a' "$bare") == '0:0:700' ]] || fail "worker bare root ownership/mode changed"
[[ $(stat -c '%u:%g' "$repo") == '0:0' ]] || fail "attached checkout is not owned by root"
[[ $(git --git-dir="$bare" rev-parse HEAD) == "$sha" ]] || fail "worker bare HEAD mismatch"
[[ $(git --git-dir="$bare" rev-parse 'HEAD^{tree}') == "$tree" ]] || fail "worker bare tree mismatch"
[[ $(git --git-dir="$bare" rev-parse --is-shallow-repository) == true ]] || fail "worker bare is not shallow"
[[ $(git --git-dir="$bare" symbolic-ref --short HEAD) == "$branch" ]] || fail "worker bare branch mismatch"
[[ $(cat "$bare/shallow") == "$sha" ]] || fail "worker bare shallow boundary mismatch"
[[ $(git -C "$repo" rev-parse HEAD) == "$sha" ]] || fail "attached checkout HEAD mismatch"
[[ $(git -C "$repo" rev-parse 'HEAD^{tree}') == "$tree" ]] || fail "attached checkout tree mismatch"
[[ $(git -C "$repo" rev-parse --is-shallow-repository) == true ]] || fail "attached checkout is not shallow"
[[ $(git -C "$repo" symbolic-ref --short HEAD) == "$branch" ]] || fail "attached checkout is detached or on another branch"
[[ $(cat "$repo/.git/shallow") == "$sha" ]] || fail "attached checkout shallow boundary mismatch"
[[ $(git -C "$repo" remote get-url origin) == "$bare" ]] || fail "attached checkout origin is not the existing worker bare store"
[[ -z $(git -C "$repo" status --porcelain=v1 --untracked-files=all) ]] || fail "attached checkout has unexpected visible changes"

alternates="$repo/.git/objects/info/alternates"
if [[ -e "$alternates" || -L "$alternates" ]]; then
  [[ -f "$alternates" && ! -L "$alternates" ]] || fail "alternates path is not a regular file"
  [[ $(wc -l < "$alternates") -eq 1 ]] || fail "alternates file must contain exactly one source"
  [[ $(cat "$alternates") == "$bare/objects" ]] || fail "alternates file points outside the exact worker bare store"
  storage_mode='validated-alternate'
else
  [[ -d "$repo/.git/objects" && ! -L "$repo/.git/objects" ]] || fail "attached checkout has no local object directory"
  object_counts=$(git -C "$repo" count-objects -v)
  pack_count=$(printf '%s\n' "$object_counts" | awk '$1 == "packs:" {print $2}')
  in_pack=$(printf '%s\n' "$object_counts" | awk '$1 == "in-pack:" {print $2}')
  [[ $pack_count == 1 && $in_pack == 24318 ]] || fail "independent checkout pack counts differ from the recorded object set"
  pack_file="$repo/.git/objects/pack/pack-eca2d35110939ce7c8404172a9fa95d0cf04e217.pack"
  [[ -f "$pack_file" && ! -L "$pack_file" ]] || fail "recorded independent object pack is missing or indirect"
  pack_sha=$(sha256sum "$pack_file" | awk '{print $1}')
  [[ $pack_sha == '202b7b6a927f44d35ea6c1b026715fc4977ef6e1328af375ae905b1f5cf747aa' ]] || fail "independent checkout pack SHA differs from the captured object store"
  storage_mode="independent-local-pack:${pack_sha}:${in_pack}-objects"
fi

git --git-dir="$bare" fsck --connectivity-only --no-reflogs HEAD >/dev/null || fail "worker bare connectivity check failed"
git -C "$repo" fsck --connectivity-only --no-reflogs HEAD >/dev/null || fail "attached checkout connectivity check failed"
printf 'worker Git identities pass; object-store mode=%s\n' "$storage_mode"
WORKER_GIT_CHECK
}
q2_copy_action() {
  local tracked=$1 exists=$2 regular=$3 symlink=$4 actual_sha=$5 expected_sha=$6
  if [[ $tracked == yes ]]; then
    if [[ $exists == yes && $regular == yes && $symlink == no && $actual_sha == "$expected_sha" ]]; then
      printf 'reuse-tracked\n'
    else
      printf 'refuse\n'
    fi
  elif [[ $exists == no ]]; then
    printf 'copy\n'
  elif [[ $regular == yes && $symlink == no && $actual_sha == "$expected_sha" ]]; then
    printf 'reuse-exact\n'
  else
    printf 'refuse\n'
  fi
}
copy_decision_self_test() {
  local expected='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
  local actual='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
  local cases=0
  expect_action() {
    local label=$1 wanted=$2
    shift 2
    local got
    got=$(q2_copy_action "$@")
    [[ $got == "$wanted" ]] || die "copy decision $label: expected $wanted, got $got"
    cases=$((cases + 1))
  }
  expect_action tracked-exact reuse-tracked yes yes yes no "$expected" "$expected"
  expect_action tracked-missing refuse yes no no no '' "$expected"
  expect_action tracked-changed refuse yes yes yes no "$actual" "$expected"
  expect_action tracked-symlink refuse yes yes yes yes "$expected" "$expected"
  expect_action ignored-absent copy no no no no '' "$expected"
  expect_action ignored-exact reuse-exact no yes yes no "$expected" "$expected"
  expect_action untracked-changed refuse no yes yes no "$actual" "$expected"
  expect_action untracked-symlink refuse no yes yes yes "$expected" "$expected"
  printf 'Q2 copy decision self-test passed: %d cases; no Git/Docker/filesystem changes\n' "$cases"
}
check_q2_inputs() {
  [[ -f "$Q2_HOST/raw/run.py" && -f "$Q2_HOST/raw/timeout_driver.py" ]] || die "Q2 runner/driver missing"
  [[ -f "$Q2_HOST/installed-wave-manifest.json" ]] || die "primary manifest missing"
  [[ -f "$Q2_HOST/raw/supplemental_run.py" && -f "$Q2_HOST/raw/supplemental-manifest.json" ]] || die "supplement driver/manifest missing"
  printf '%s  %s\n' \
    'a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0' "$Q2_HOST/raw/run.py" \
    '0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312' "$Q2_HOST/raw/timeout_driver.py" \
    '1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277' "$Q2_HOST/installed-wave-manifest.json" \
    '4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49' "$Q2_HOST/raw/supplemental_run.py" \
    'ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df' "$Q2_HOST/raw/supplemental-manifest.json" \
    | shasum -a 256 -c -
  printf '%s  %s\n' \
    '4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2' "$SCRIPT_DIR/sitecustomize.py" \
    | shasum -a 256 -c -
}
check_worker() {
  [[ $(docker_e02 inspect --format '{{.Id}}' "$CONTAINER") == "$CONTAINER_ID" ]] || die "dedicated worker container ID changed"
  [[ $(docker_e02 inspect --format '{{.Image}}' "$CONTAINER") == "$IMAGE_ID" ]] || die "dedicated worker image changed"
  [[ $(docker_e02 inspect --format '{{.State.Running}}' "$CONTAINER") == true ]] || die "dedicated worker is not running"
  [[ $(docker_e02 inspect --format '{{.HostConfig.Memory}}' "$CONTAINER") == 2306867200 ]] || die "worker memory cap changed"
  docker_e02 inspect --format '{{json .Config.Env}}' "$CONTAINER" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
guarded={"GIT_ALTERNATE_OBJECT_DIRECTORIES","GIT_OBJECT_DIRECTORY"}
bad=[entry for entry in rows if entry.partition("=")[0] in guarded and entry.partition("=")[2]]
if bad: raise SystemExit(f"worker Git object environment must be empty: {bad!r}")
print("worker Git object-directory environment is empty")
'
  [[ $(docker_e02 ps --format '{{.Names}}') == "$CONTAINER" ]] || die "another container is running in the dedicated daemon"
  docker_e02 inspect --format '{{json .Mounts}}' "$CONTAINER" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
actual={(r["Type"],r.get("Name",""),r["Destination"]) for r in rows}
expected={("volume","e02-local-uv-pythons","/opt/uv-python"),("volume","e02-local-uv-cache","/root/.cache/uv"),("volume","e02-local-uv-env","/scratch")}
if actual != expected: raise SystemExit(f"unexpected worker mounts: {sorted(actual)!r}")
print("worker mounts: only the three existing named uv volumes; no bind mounts")
'
}
worker_env_check() {
  docker_e02 exec "$CONTAINER" /bin/bash -lc '
set -euo pipefail
test "$(uv --version)" = "uv 0.9.21"
/scratch/root-venv/bin/python -c "import sys,importlib.metadata as m; assert sys.version_info[:2] == (3,14); assert m.version(\"hatchling\") == \"1.27.0\"; print(\"root\",sys.version.split()[0],\"Hatchling\",m.version(\"hatchling\"),\"pytest\",m.version(\"pytest\"))"
/scratch/dowhy-venv/bin/python -c "import sys,dowhy,importlib.metadata as m; assert sys.version_info[:2] == (3,12); assert dowhy.__version__ == \"0.14\"; print(\"worker\",sys.version.split()[0],\"DoWhy\",dowhy.__version__,\"pytest\",m.version(\"pytest\"))"
uv pip check --python /scratch/root-venv/bin/python
uv pip check --python /scratch/dowhy-venv/bin/python
printf "scratch="; df -Pk /scratch | tail -n 1
printf "cgroup-current="; cat /sys/fs/cgroup/memory.current
printf "cgroup-events:\n"; cat /sys/fs/cgroup/memory.events
printf "cgroup-pressure:\n"; cat /sys/fs/cgroup/memory.pressure
'
}
worker_lock_check() {
  docker_e02 exec -i "$CONTAINER" /bin/bash -lc "cd '$REPO' && sha256sum -c -" <<'LOCKS'
b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267  policy-engine/pyproject.toml
e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463  policy-engine/uv.lock
df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447  policy-engine/workers/dowhy-014/pyproject.toml
c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a  policy-engine/workers/dowhy-014/uv.lock
7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d  policy-engine/workers/dowhy-014/.python-version
LOCKS
}
verify_copy_hashes() {
  docker_e02 exec -i "$CONTAINER" /bin/bash -lc "cd '$REPO' && sha256sum -c -" <<'TOOL_HASHES'
a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py
0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py
1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-manifest.json
4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py
ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df  policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json
TOOL_HASHES
}
q2_input_action() {
  local rel=$1 expected_sha=$2 target="$REPO/$1"
  local tracked exists regular symlink actual_sha action frozen_blob_sha
  if docker_e02 exec "$CONTAINER" git -C "$REPO" ls-files --error-unmatch -- "$rel" >/dev/null 2>&1; then
    tracked=yes
  else
    tracked=no
  fi
  if docker_e02 exec "$CONTAINER" test -e "$target" >/dev/null 2>&1; then
    exists=yes
  elif docker_e02 exec "$CONTAINER" test -L "$target" >/dev/null 2>&1; then
    exists=yes
  else
    exists=no
  fi
  if [[ $exists == yes ]] && docker_e02 exec "$CONTAINER" test -f "$target" >/dev/null 2>&1; then
    regular=yes
  else
    regular=no
  fi
  if [[ $exists == yes ]] && docker_e02 exec "$CONTAINER" test -L "$target" >/dev/null 2>&1; then
    symlink=yes
  else
    symlink=no
  fi
  if [[ $regular == yes && $symlink == no ]]; then
    actual_sha=$(docker_e02 exec "$CONTAINER" sha256sum "$target" | awk '{print $1}')
  else
    actual_sha=''
  fi
  action=$(q2_copy_action "$tracked" "$exists" "$regular" "$symlink" "$actual_sha" "$expected_sha")
  case "$action" in
    reuse-tracked)
      frozen_blob_sha=$(docker_e02 exec "$CONTAINER" git -C "$REPO" show "$freeze_sha:$rel" | sha256sum | awk '{print $1}')
      [[ $frozen_blob_sha == "$expected_sha" ]] || die "tracked Q2 input's frozen Git blob SHA mismatch: $rel"
      ;;
    reuse-exact)
      docker_e02 exec "$CONTAINER" git -C "$REPO" check-ignore --quiet -- "$rel" || die "existing untracked Q2 input is not ignored: $rel"
      ;;
    copy)
      docker_e02 exec "$CONTAINER" git -C "$REPO" check-ignore --quiet -- "$rel" || die "missing untracked Q2 input is not ignored: $rel"
      ;;
    *) die "refusing unexpected, changed, non-file, or symlink Q2 input: $rel" ;;
  esac
  printf '%s\n' "$action"
}
preflight_q2_input() {
  local rel=$1 expected_sha=$2 action
  action=$(q2_input_action "$rel" "$expected_sha")
  printf 'Q2 input preflight: %s => %s\n' "$rel" "$action"
}
copy_q2_input() {
  local rel=$1 source=$2 expected_sha=$3 target="$REPO/$1" action actual_sha
  action=$(q2_input_action "$rel" "$expected_sha")
  case "$action" in
    reuse-tracked)
      printf 'reuse tracked frozen Q2 input: %s (%s)\n' "$rel" "$expected_sha"
      ;;
    reuse-exact)
      printf 'reuse exact ignored Q2 input without overwrite: %s (%s)\n' "$rel" "$expected_sha"
      ;;
    copy)
      docker_e02 cp "$source" "$CONTAINER:$target"
      actual_sha=$(docker_e02 exec "$CONTAINER" sha256sum "$target" | awk '{print $1}')
      [[ $actual_sha == "$expected_sha" ]] || die "copied Q2 input SHA mismatch: $rel"
      printf 'copied absent ignored Q2 input and verified: %s (%s)\n' "$rel" "$expected_sha"
      ;;
  esac
}
preflight_q2_layout() {
  docker_e02 exec -i "$CONTAINER" /bin/bash -s -- "$REPO/$Q2_REL/raw" <<'Q2_LAYOUT_CHECK'
set -euo pipefail
raw_dir=$1
[[ ! -L "$raw_dir" ]] || { echo "Q2 raw input directory is a symlink" >&2; exit 1; }
if [[ -e "$raw_dir" && ! -d "$raw_dir" ]]; then
  echo "Q2 raw input path is not a directory" >&2
  exit 1
fi
if [[ -d "$raw_dir" ]]; then
  for entry in "$raw_dir"/* "$raw_dir"/.[!.]* "$raw_dir"/..?*; do
    [[ -e "$entry" || -L "$entry" ]] || continue
    case "${entry##*/}" in
      run.py|timeout_driver.py|supplemental_run.py|supplemental-manifest.json) ;;
      *) printf 'unexpected Q2 raw path: %s\n' "$entry" >&2; exit 1 ;;
    esac
  done
fi
Q2_LAYOUT_CHECK
  preflight_q2_input "$Q2_REL/raw/run.py" 'a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0'
  preflight_q2_input "$Q2_REL/raw/timeout_driver.py" '0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312'
  preflight_q2_input "$Q2_REL/installed-wave-manifest.json" '1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277'
  preflight_q2_input "$Q2_REL/raw/supplemental_run.py" '4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49'
  preflight_q2_input "$Q2_REL/raw/supplemental-manifest.json" 'ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df'
}
capture_hook_action() {
  local freeze_sha=$1 target_dir="/scratch/e02-child-capture/$1" target="/scratch/e02-child-capture/$1/sitecustomize.py"
  local exists regular symlink actual_sha action
  docker_e02 exec -i "$CONTAINER" /bin/bash -s -- "$target_dir" "$target" <<'HOOK_PREFLIGHT'
set -euo pipefail
directory=$1
target=$2
for candidate in /scratch/e02-child-capture "$directory"; do
  [[ ! -L "$candidate" ]] || { printf 'capture path is a symlink: %s\n' "$candidate" >&2; exit 1; }
  if [[ -e "$candidate" && ! -d "$candidate" ]]; then
    printf 'capture path is not a directory: %s\n' "$candidate" >&2
    exit 1
  fi
done
HOOK_PREFLIGHT
  if docker_e02 exec "$CONTAINER" test -e "$target" >/dev/null 2>&1; then
    exists=yes
  elif docker_e02 exec "$CONTAINER" test -L "$target" >/dev/null 2>&1; then
    exists=yes
  else
    exists=no
  fi
  if [[ $exists == yes ]] && docker_e02 exec "$CONTAINER" test -f "$target" >/dev/null 2>&1; then
    regular=yes
  else
    regular=no
  fi
  if [[ $exists == yes ]] && docker_e02 exec "$CONTAINER" test -L "$target" >/dev/null 2>&1; then
    symlink=yes
  else
    symlink=no
  fi
  if [[ $regular == yes && $symlink == no ]]; then
    actual_sha=$(docker_e02 exec "$CONTAINER" sha256sum "$target" | awk '{print $1}')
  else
    actual_sha=''
  fi
  action=$(q2_copy_action no "$exists" "$regular" "$symlink" "$actual_sha" '4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2')
  [[ $action != refuse ]] || die "refusing unexpected, changed, non-file, or symlink capture hook target"
  printf '%s\n' "$action"
}
preflight_capture_hook() {
  local action
  action=$(capture_hook_action "$1")
  printf 'capture hook preflight: %s\n' "$action"
}
copy_capture_hook() {
  local freeze_sha=$1 target_dir="/scratch/e02-child-capture/$1" target="/scratch/e02-child-capture/$1/sitecustomize.py"
  local action actual_sha
  action=$(capture_hook_action "$freeze_sha")
  case "$action" in
    reuse-exact) printf 'reuse exact capture hook without overwrite: %s\n' "$target" ;;
    copy)
      docker_e02 exec "$CONTAINER" mkdir -p "$target_dir"
      docker_e02 cp "$SCRIPT_DIR/sitecustomize.py" "$CONTAINER:$target"
      actual_sha=$(docker_e02 exec "$CONTAINER" sha256sum "$target" | awk '{print $1}')
      [[ $actual_sha == '4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2' ]] || die "copied capture hook SHA mismatch"
      printf 'copied absent capture hook and verified: %s\n' "$target"
      ;;
    *) die "unexpected capture hook action: $action" ;;
  esac
}
check_resume_receipt() {
  local source_checkout=$1 branch=$2 freeze_sha=$3 freeze_tree=$4 receipt="$SCRIPT_DIR/actual-transport-7574c864-20261010"
  [[ -d "$receipt" && ! -L "$receipt" ]] || die "recorded partial-transport receipt is missing"
  printf '%s  %s\n' \
    '67030c22a3bcec8e712916a5252f2632d67d37b293275181021630d30b34b944' "$receipt/command.json" \
    '84e8d4e405846c8cc568dbde928381ff94a64a5dceb9299125679b8f0b644ba7' "$receipt/stdout.txt" \
    'dff18f886a4e8dd966e916fdfec84c5db607cece6f5040f922c7bb0c4df9645a' "$receipt/stderr.txt" \
    | shasum -a 256 -c -
  python3 - "$receipt/command.json" "$SCRIPT_DIR/final-source-linux-wave.sh" "$source_checkout" "$branch" "$freeze_sha" "$freeze_tree" <<'RECEIPT_CHECK'
import json
import sys
from pathlib import Path

receipt_path, script_path, source_checkout, branch, freeze_sha, freeze_tree = sys.argv[1:]
receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
expected = ["bash", script_path, "transport", source_checkout, branch, freeze_sha, freeze_tree]
if receipt.get("argv") != expected or receipt.get("exit") != 1:
    raise SystemExit("captured transport failure is not the exact root-created partial attempt")
print("captured failed transport identity: exact argv and expected pre-overlay exit=1")
RECEIPT_CHECK
}
continue_transfer() {
  local branch=$1 freeze_sha=$2 freeze_tree=$3 host_bare=$4 worker_bare=$5 worker_q2="$REPO/$Q2_REL"
  preflight_q2_layout
  preflight_capture_hook "$freeze_sha"
  docker_e02 exec -i "$CONTAINER" /bin/bash -s -- "$worker_q2/raw" <<'Q2_RAW_DIR'
set -euo pipefail
directory=$1
[[ ! -L "$directory" ]] || { echo "Q2 raw input directory is a symlink" >&2; exit 1; }
if [[ -e "$directory" && ! -d "$directory" ]]; then
  echo "Q2 raw input path is not a directory" >&2
  exit 1
fi
mkdir -p "$directory"
Q2_RAW_DIR
  copy_q2_input "$Q2_REL/raw/run.py" "$Q2_HOST/raw/run.py" 'a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0'
  copy_q2_input "$Q2_REL/raw/timeout_driver.py" "$Q2_HOST/raw/timeout_driver.py" '0f6ae40c5fa0a9959718b6eb365c3fa3f4ad172fbae565702c3be357759be312'
  copy_q2_input "$Q2_REL/installed-wave-manifest.json" "$Q2_HOST/installed-wave-manifest.json" '1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277'
  copy_q2_input "$Q2_REL/raw/supplemental_run.py" "$Q2_HOST/raw/supplemental_run.py" '4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49'
  copy_q2_input "$Q2_REL/raw/supplemental-manifest.json" "$Q2_HOST/raw/supplemental-manifest.json" 'ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df'
  verify_copy_hashes
  copy_capture_hook "$freeze_sha"
  docker_e02 exec "$CONTAINER" /bin/bash -lc "du -sb '/scratch/e02-$freeze_sha.git' '$REPO'; git -C '$REPO' log -1 --format='HEAD=%H%nTREE=%T%nPARENTS=%P'; git -C '$REPO' status --short --branch"
  worker_lock_check
  worker_env_check
  printf 'transport inputs complete; no product test, build, install, source mount, or cleanup ran\n'
  printf 'host bare=%s\nworker bare=/scratch/e02-%s.git\nattached checkout=%s\n' "$host_bare" "$freeze_sha" "$REPO"
}

transport() {
  [[ $# == 4 ]] || usage
  local source_checkout branch freeze_sha freeze_tree host_bare worker_bare worker_q2
  source_checkout=$(cd -- "$1" && pwd -P)
  branch=$2
  freeze_sha=$3
  freeze_tree=$4
  check_source_freeze "$source_checkout" "$branch" "$freeze_sha" "$freeze_tree"
  check_q2_inputs
  check_worker
  host_bare="$SCRIPT_DIR/e02-$freeze_sha.git"
  worker_bare="/scratch/e02-$freeze_sha.git"
  worker_q2="$REPO/$Q2_REL"
  [[ ! -e "$host_bare" ]] || die "host bare destination exists; preserving it"
  docker_e02 exec "$CONTAINER" test ! -e "$worker_bare" || die "worker bare destination exists"
  docker_e02 exec "$CONTAINER" test ! -e "$REPO" || die "attached checkout destination exists"

  printf 'source checkout=%s\nbranch=%s\nfreeze SHA=%s\nfreeze tree=%s\n' "$source_checkout" "$branch" "$freeze_sha" "$freeze_tree"
  git clone --bare --depth=1 --single-branch --branch "$branch" "file://$source_checkout" "$host_bare"
  [[ $(git --git-dir="$host_bare" rev-parse HEAD) == "$freeze_sha" ]] || die "host bare HEAD mismatch"
  [[ $(git --git-dir="$host_bare" rev-parse 'HEAD^{tree}') == "$freeze_tree" ]] || die "host bare tree mismatch"
  [[ $(git --git-dir="$host_bare" rev-parse --is-shallow-repository) == true ]] || die "host bare is not shallow"
  [[ $(git --git-dir="$host_bare" symbolic-ref --short HEAD) == "$branch" ]] || die "host bare branch mismatch"
  du -sk "$host_bare"

  docker_e02 exec "$CONTAINER" mkdir -m 700 "$worker_bare"
  docker_e02 cp "$host_bare/." "$CONTAINER:$worker_bare/"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$worker_bare" rev-parse HEAD) == "$freeze_sha" ]] || die "worker bare HEAD mismatch"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$worker_bare" rev-parse 'HEAD^{tree}') == "$freeze_tree" ]] || die "worker bare tree mismatch"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$worker_bare" rev-parse --is-shallow-repository) == true ]] || die "worker bare is not shallow"
  docker_e02 exec "$CONTAINER" mkdir -p /workspace
  docker_e02 exec "$CONTAINER" git clone --shared --single-branch --branch "$branch" "$worker_bare" "$REPO"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$REPO" rev-parse HEAD) == "$freeze_sha" ]] || die "attached checkout HEAD mismatch"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$REPO" rev-parse 'HEAD^{tree}') == "$freeze_tree" ]] || die "attached checkout tree mismatch"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$REPO" rev-parse --is-shallow-repository) == true ]] || die "attached checkout is not shallow"
  [[ $(docker_e02 exec "$CONTAINER" git -C "$REPO" symbolic-ref --short HEAD) == "$branch" ]] || die "attached checkout is not attached to requested branch"
  check_host_bare "$host_bare" "$branch" "$freeze_sha" "$freeze_tree"
  check_worker_git_state "$worker_bare" "$branch" "$freeze_sha" "$freeze_tree"
  continue_transfer "$branch" "$freeze_sha" "$freeze_tree" "$host_bare" "$worker_bare"
}

check_known_partial() {
  [[ $# == 4 ]] || usage
  local source_checkout branch freeze_sha freeze_tree host_bare worker_bare
  source_checkout=$(cd -- "$1" && pwd -P)
  branch=$2
  freeze_sha=$3
  freeze_tree=$4
  [[ $source_checkout == '/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos' ]] || die "resume is bound to the recorded source checkout"
  [[ $branch == "$RESUME_BRANCH" && $freeze_sha == "$RESUME_SHA" && $freeze_tree == "$RESUME_TREE" ]] || die "resume is bound to the recorded 7574c864 freeze"
  check_resume_source_attachment "$source_checkout" "$branch" "$freeze_sha" "$freeze_tree"
  check_q2_inputs
  check_resume_receipt "$source_checkout" "$branch" "$freeze_sha" "$freeze_tree"
  check_worker
  host_bare="$SCRIPT_DIR/e02-$freeze_sha.git"
  worker_bare="/scratch/e02-$freeze_sha.git"
  check_host_bare "$host_bare" "$branch" "$freeze_sha" "$freeze_tree"
  check_worker_git_state "$worker_bare" "$branch" "$freeze_sha" "$freeze_tree"
  worker_lock_check
}

resume() {
  check_known_partial "$@"
  local branch freeze_sha freeze_tree host_bare worker_bare
  branch=$2
  freeze_sha=$3
  freeze_tree=$4
  host_bare="$SCRIPT_DIR/e02-$freeze_sha.git"
  worker_bare="/scratch/e02-$freeze_sha.git"
  printf 'resuming the recorded root-created partial transport; existing Git stores will be reused in place\n'
  continue_transfer "$branch" "$freeze_sha" "$freeze_tree" "$host_bare" "$worker_bare"
}

preflight_resume() {
  check_known_partial "$@"
  preflight_q2_layout
  preflight_capture_hook "$RESUME_SHA"
  printf 'known partial transport preflight passed; no source copy or worker write ran\n'
}

q2() {
  [[ $# == 4 ]] || usage
  local branch freeze_sha freeze_tree attempt
  branch=$1
  freeze_sha=$2
  freeze_tree=$3
  attempt=$4
  check_host_git_object_environment
  check_sha "$freeze_sha" FROZEN_SHA
  check_sha "$freeze_tree" FROZEN_TREE
  git check-ref-format --branch "$branch" >/dev/null || die "invalid branch name"
  [[ $E02_ROOT_HEAVY_SLOT_GRANT == "$freeze_sha" ]] || die "root must grant the heavy slot using E02_ROOT_HEAVY_SLOT_GRANT=<full frozen SHA>"
  [[ $attempt =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "attempt must be a new simple directory name"
  check_q2_inputs
  check_worker
  docker_e02 exec "$CONTAINER" /bin/bash -lc "cd '$REPO' && test \"\$(git symbolic-ref --short HEAD)\" = '$branch' && test \"\$(git rev-parse HEAD)\" = '$freeze_sha' && test \"\$(git rev-parse 'HEAD^{tree}')\" = '$freeze_tree' && test -z \"\$(git status --porcelain=v1 --untracked-files=no)\"" || die "attached source checkout no longer matches freeze"
  worker_lock_check
  verify_copy_hashes
  worker_env_check

  docker_e02 exec -i -w "$REPO" \
    -e E02_FREEZE_SHA="$freeze_sha" \
    -e E02_FREEZE_TREE="$freeze_tree" \
    -e E02_FREEZE_BRANCH="$branch" \
    -e E02_ATTEMPT="$attempt" \
    "$CONTAINER" /bin/bash -s <<'WORKER_SCRIPT'
set -euo pipefail
repo=/workspace/polisyos
worker_origin=$(git -C "$repo" remote get-url origin)
expected_worker_bare=/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git
fail() { printf 'Q2 bare-store preflight: %s\n' "$*" >&2; exit 1; }
[[ "$worker_origin" == "$expected_worker_bare" ]] || fail "checkout origin differs from the receipted worker bare store"
worker_bare=$worker_origin
[[ -d "$worker_bare" && ! -L "$worker_bare" ]] || fail "receipted worker bare path is missing or indirect"
[[ $(stat -c '%u:%g:%a' "$worker_bare") == '0:0:700' ]] || fail "receipted worker bare ownership or mode changed"
[[ $(git --git-dir="$worker_bare" config --bool core.bare) == true ]] || fail "checkout origin is not configured as a bare store"
[[ $(git --git-dir="$worker_bare" rev-parse --is-bare-repository) == true ]] || fail "checkout origin is not a bare repository"
[[ $(git --git-dir="$worker_bare" rev-parse HEAD) == "$E02_FREEZE_SHA" ]] || fail "worker bare HEAD differs from the requested freeze"
[[ $(git --git-dir="$worker_bare" rev-parse 'HEAD^{tree}') == "$E02_FREEZE_TREE" ]] || fail "worker bare tree differs from the requested freeze"
[[ $(git --git-dir="$worker_bare" symbolic-ref --short HEAD) == "$E02_FREEZE_BRANCH" ]] || fail "worker bare branch differs from the requested branch"
[[ $(cat "$worker_bare/shallow") == 7574c864a605c50efc033b966807790cbd8d1781 ]] || fail "receipted worker shallow boundary changed"
[[ ! -e "$worker_bare/objects/info/alternates" && ! -L "$worker_bare/objects/info/alternates" ]] || fail "receipted worker bare store now depends on external objects"
handoff="$repo/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging"
root_python=/scratch/root-venv/bin/python
run_root="/scratch/e02-q2-runs/$E02_FREEZE_SHA/$E02_ATTEMPT"
primary_output="$run_root/primary-runs"
supplement_output="$run_root/supplement-runs"
test ! -e "$run_root" || { echo "retained Q2 attempt already exists: $run_root" >&2; exit 1; }
mkdir -p "$run_root/orchestration"
printf 'scratch-before='; df -Pk /scratch | tail -n 1
printf 'transport-bytes='; du -sb "$worker_bare" "$repo"
printf 'cgroup-current='; cat /sys/fs/cgroup/memory.current
printf 'cgroup-events:\n'; cat /sys/fs/cgroup/memory.events
printf 'cgroup-pressure:\n'; cat /sys/fs/cgroup/memory.pressure

if "$root_python" "$handoff/raw/timeout_driver.py" \
  --repo "$repo" --source-sha "$E02_FREEZE_SHA" --source-tree "$E02_FREEZE_TREE" \
  --app-python "$root_python" --worker-python /scratch/dowhy-venv/bin/python \
  --output-root "$primary_output" \
  > "$run_root/orchestration/primary.stdout" \
  2> "$run_root/orchestration/primary.stderr"; then
  primary_rc=0
else
  primary_rc=$?
fi
printf '%s\n' "$primary_rc" > "$run_root/orchestration/primary.exit"
if [[ $primary_rc != 0 ]]; then
  echo "primary Q2 failed; retained logs and run directory remain at $run_root" >&2
  exit "$primary_rc"
fi

primary_run=$("$root_python" - "$run_root/orchestration/primary.stdout" "$primary_output" "$E02_FREEZE_SHA" "$E02_FREEZE_TREE" <<'PY'
import json
import sys
from pathlib import Path

stdout_path, output_root = map(Path, sys.argv[1:3])
expected_sha, expected_tree = sys.argv[3:]
lines = [line for line in stdout_path.read_text(encoding="utf-8").splitlines() if line]
if len(lines) != 1 or not lines[0].startswith("Q2 frozen installed wave passed: "):
    raise SystemExit(f"primary driver output did not name one passing run: {lines!r}")
run = Path(lines[0].split(": ", 1)[1]).resolve(strict=True)
if run.parent != output_root.resolve(strict=True):
    raise SystemExit(f"primary run escaped output root: {run}")
receipt = json.loads((run / "run-receipt.json").read_text(encoding="utf-8"))
if receipt.get("status") != "pass":
    raise SystemExit("primary receipt is not status=pass")
if (receipt.get("source_sha"), receipt.get("source_tree")) != (expected_sha, expected_tree):
    raise SystemExit("primary receipt belongs to a different freeze")
if set(receipt.get("profiles", {})) != {
    "source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel"
}:
    raise SystemExit("primary receipt does not contain exactly three reviewed profiles")
print(run)
PY
)
printf '%s\n' "$primary_run" > "$run_root/orchestration/primary-run.path"

if "$root_python" "$handoff/raw/supplemental_run.py" \
  --repo "$repo" --source-sha "$E02_FREEZE_SHA" --source-tree "$E02_FREEZE_TREE" \
  --primary-run "$primary_run" --output-root "$supplement_output" \
  > "$run_root/orchestration/supplemental.stdout" \
  2> "$run_root/orchestration/supplemental.stderr"; then
  supplement_rc=0
else
  supplement_rc=$?
fi
printf '%s\n' "$supplement_rc" > "$run_root/orchestration/supplemental.exit"
if [[ $supplement_rc != 0 ]]; then
  echo "supplemental Q2 failed; retained logs and run directory remain at $run_root" >&2
  exit "$supplement_rc"
fi

supplement_run=$("$root_python" - "$run_root/orchestration/supplemental.stdout" "$supplement_output" "$E02_FREEZE_SHA" "$E02_FREEZE_TREE" <<'PY'
import json
import sys
from pathlib import Path

stdout_path, output_root = map(Path, sys.argv[1:3])
expected_sha, expected_tree = sys.argv[3:]
lines = [line for line in stdout_path.read_text(encoding="utf-8").splitlines() if line]
if len(lines) != 1:
    raise SystemExit(f"supplemental driver did not name exactly one run: {lines!r}")
run = Path(lines[0]).resolve(strict=True)
if run.parent != output_root.resolve(strict=True):
    raise SystemExit(f"supplemental run escaped output root: {run}")
receipt = json.loads((run / "supplemental-receipt.json").read_text(encoding="utf-8"))
if receipt.get("status") != "pass":
    raise SystemExit("supplemental receipt is not status=pass")
if (receipt.get("source_sha"), receipt.get("source_tree")) != (expected_sha, expected_tree):
    raise SystemExit("supplemental receipt belongs to a different freeze")
profiles = receipt.get("profiles", {})
expected_profiles = {"source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel"}
if set(profiles) != expected_profiles:
    raise SystemExit("supplemental receipt does not contain exactly three profiles")
for name, profile in profiles.items():
    expected_counts = {"tests": 6, "skipped": 0, "failures": 0, "errors": 0}
    if profile.get("status") != "pass" or profile.get("consumer", {}).get("counts") != expected_counts:
        raise SystemExit(f"supplemental profile did not reconcile six passing selectors: {name}")
print(run)
PY
)
printf '%s\n' "$supplement_run" > "$run_root/orchestration/supplemental-run.path"
printf 'primary_run=%s\nsupplemental_run=%s\n' "$primary_run" "$supplement_run"
printf 'scratch-after='; df -Pk /scratch | tail -n 1
printf 'cgroup-current='; cat /sys/fs/cgroup/memory.current
printf 'cgroup-events:\n'; cat /sys/fs/cgroup/memory.events
printf 'cgroup-pressure:\n'; cat /sys/fs/cgroup/memory.pressure
WORKER_SCRIPT
}

case "$MODE" in
  transport) transport "$@" ;;
  resume) resume "$@" ;;
  preflight-resume) preflight_resume "$@" ;;
  q2) q2 "$@" ;;
  self-test-copy-decisions) [[ $# == 0 ]] || usage; copy_decision_self_test ;;
  *) usage ;;
esac
