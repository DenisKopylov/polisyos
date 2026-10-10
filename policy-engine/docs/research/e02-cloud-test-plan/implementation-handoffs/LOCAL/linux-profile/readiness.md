# Linux frozen-source readiness

Status: **prepared, not admitted to execution**. Root reports mutable candidate HEAD `9e02a9f49c8b01026327a9f7c7e18711b13a96f2` with tree `881a950dccb7cdefacc636515aa7dd2bceadf928`; an import-gate repair remains before source freeze. These are root-reported candidate identities, not a freeze. The published source 24 prefix `68b8ac5c` is earlier context. The final attached branch/SHA/tree and runner input binding remain pending. Do not substitute the candidate or any earlier receipt.

No source clone/copy, build, test, container recreation/configuration, or mount was performed. A separately authorized package addition to the existing app environment is recorded below. No Git command was run. Host-side writes are limited to the local `LOCAL/linux-profile` notes and `raw/` receipts; the guest-side change is confined to the existing app environment and uv cache. The ordinary source transport and test commands below are future commands, not executed commands.

## Existing Linux profile

- Existing VM/profile: Colima `e02-local`, ARM64 Ubuntu 24.04.4, 2 CPUs, 3 GiB configured RAM, no host mounts. Docker context is `colima-e02-local`; container is `e02-local-worker-provision` (`88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`), image `ghcr.io/astral-sh/uv@sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`.
- Existing runtimes: uv `0.9.21`, app Python `3.14.0` at `/scratch/root-venv/bin/python`, worker Python `3.12.12` at `/scratch/dowhy-venv/bin/python`, DoWhy `0.14`. Their frozen environment recipes remain the root/worker `pyproject.toml` and `uv.lock`; hashes are below and matched in the container. No extra worker environment is needed for the prepared Q2 invocation when the existing worker interpreter is supplied.
- The app `pyproject.toml` requires `hatchling>=1.27.0`; the current author-final Q2 runner requires exactly `1.27.0`. That exact distribution is now installed in the existing app environment. The final root freeze still must bind the runner and recipe inputs before any build.
- Read-only path checks found `/workspace/polisyos`, `/scratch/e02-frozen.git`, `/scratch/e02-q2-runs`, `/scratch/ukraine-artifacts`, and `/tmp/dfk-mini` absent. `findmnt` inside the container showed only the isolated Docker volumes and standard system mounts; no host source or production data is mounted.

## Hatchling provisioning receipt

The existing `/scratch/root-venv` lacked Hatchling; the `policy-engine/pyproject.toml` build-system requirement and current author-final runner require Hatchling `1.27.0`. I used the existing uv `0.9.21` and app environment only. The first exact-pin offline attempt failed because Hatchling was absent from the uv cache and made no environment changes. The network fallback pinned Hatchling `1.27.0` and succeeded, but its resolver selected `pathspec 1.1.1`, which differs from the app lock’s `pathspec 0.12.1`. I then restored the lock-pinned `pathspec 0.12.1` with an exact network-pinned command. An offline reconcile first confirmed that the locked pathspec wheel was absent from cache, so the final network invocation pinned all five package versions below:

```sh
uv pip install --offline --python /scratch/root-venv/bin/python 'hatchling==1.27.0'
uv pip install --python /scratch/root-venv/bin/python --index-url https://pypi.org/simple 'hatchling==1.27.0'
uv pip install --python /scratch/root-venv/bin/python --index-url https://pypi.org/simple \
  'hatchling==1.27.0' 'packaging==25.0' 'pathspec==0.12.1' \
  'pluggy==1.6.0' 'trove-classifiers==2026.9.21.13'
```

The final exact package set was:

```text
hatchling==1.27.0
packaging==25.0                 # app uv.lock
pathspec==0.12.1                # app uv.lock
pluggy==1.6.0                   # app uv.lock
trove-classifiers==2026.9.21.13 # required by Hatchling; not in app uv.lock
```

The final app freeze differs from the pre-install freeze by exactly three distributions: Hatchling `1.27.0`, pathspec `0.12.1`, and trove-classifiers `2026.9.21.13`. The 158-package app environment now contains 161 packages; all previously locked versions are unchanged. `uv pip check --python /scratch/root-venv/bin/python` passed (`Checked 161 packages; All installed packages are compatible`). The root and worker `pyproject.toml`/`uv.lock` SHA-256 values matched before and after provisioning. The worker remains Python `3.12.12` with DoWhy `0.14`; no worker packages or environments changed. Complete command streams, statuses, and both full app freezes are in `LOCAL/linux-profile/raw/`; `hatchling-provision.SHA256SUMS` covers only this install’s bounded receipt files, not the VM disk images or older provisioning logs. No source build, package build, test, or source transport was performed.

## Source identity and one-checkout transport

The source checkout must be an ordinary attached checkout of the final commit, with the exact tree SHA supplied by the freeze. The Q2 runner’s preflight checks full 40-character commit and tree SHAs, exact `HEAD`, an attached branch, and zero tracked edits; it then runs `git archive` from that checkout. The checked-in source remains authoritative. No history is to be fabricated with `fast-import`, `commit-tree`, resets, or synthetic commits.

After root provides `SOURCE_CHECKOUT`, `FREEZE_BRANCH`, `FREEZE_SHA`, and `FREEZE_TREE`, the proposed transport is one host-side shallow bare clone and one reusable attached worker checkout. These commands are for the later freeze grant only:

```sh
source_checkout=/absolute/path/to/root-approved-frozen-checkout
freeze_branch=ROOT_SUPPLIED_ATTACHED_BRANCH
freeze_sha=ROOT_SUPPLIED_FULL_COMMIT_SHA
freeze_tree=ROOT_SUPPLIED_FULL_TREE_SHA
host_bare="${TMPDIR%/}/e02-${freeze_sha}.git"

git -C "$source_checkout" status --short --branch
git -C "$source_checkout" symbolic-ref --short HEAD
git -C "$source_checkout" rev-parse HEAD
git -C "$source_checkout" rev-parse 'HEAD^{tree}'

git clone --bare --depth=1 --single-branch --branch "$freeze_branch" \
  "file://$source_checkout" "$host_bare"
git --git-dir="$host_bare" rev-parse HEAD
git --git-dir="$host_bare" rev-parse 'HEAD^{tree}'
git --git-dir="$host_bare" rev-parse --is-shallow-repository
```

Only proceed if the source checkout and bare clone report the supplied full SHA and tree, the branch is attached, and the bare clone reports shallow. Copy that bare object store into the existing container’s persistent `/scratch` volume, then make one ordinary attached checkout which borrows its objects:

```sh
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}
docker_e02 cp "$host_bare" "e02-local-worker-provision:/scratch/e02-${freeze_sha}.git"
docker_e02 exec e02-local-worker-provision mkdir -p /workspace
docker_e02 exec e02-local-worker-provision \
  git clone --shared --single-branch --branch "$freeze_branch" \
  "/scratch/e02-${freeze_sha}.git" /workspace/polisyos
```

Before relying on that checkout, read back its full SHA, tree, attached branch, clean tracked status, and shallow boundary. Confirm that `.git/shallow` names `FREEZE_SHA` and that `.git/objects/info/alternates` resolves to the retained bare clone. Keep the bare object store for the lifetime of the checkout; do not prune or remove borrowed objects. If any output differs, stop and preserve the failure rather than synthesizing history or repairing refs.

The Q2 runner and manifest live under ignored `LOCAL/`, outside `git archive`. The author-final runner is a separate hashed input from the archived source. Copy only that runner plus the reconciled manifest into `/workspace/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/` after freeze; do not make a second checkout or source archive. Verify each input hash before and after copying. Root must bind the exact runner/manifest hashes to the final run before execution:

```text
Current author-final candidate `raw/run.py` SHA-256: 5d54bce877979e82e3a7f95d451b6f076fcc318037868e329f26908065d80932
Current author-final candidate `raw/run.py` bytes:   77,787
Current author-final candidate manifest SHA-256:     ab7cf774e1c6805e9b1812472e5b8357af1a6a43d50a994a7488f29442d06eb7
Current author-final candidate recipe SHA-256:       e496a95d395d860747ba8a457630551040c32a8442be1de12af975fd4d86410e
```

Superseded local candidate identities were runner `97405e3aeee0f0025c27e008d75f8ba8eff871f5c731621822dd345df6103161`, manifest `439583da0c8d29c0fe4ec292ae3e63c882279fa9bc0a88249ee23ffc8b9528dd`, and recipe `a0fac23b2c44ede88eb81808779c8926d1af2e6c260a19b282b7366410e1d660`. Earlier runner-only revisions `f5f07ec8…` and `5a1db8bf…` are superseded too. The hashes above are current candidate inputs but remain unbound until root seals the source and exact run inputs.

The exact current runner/manifest/recipe hash output is retained as `LOCAL/linux-profile/raw/q2-candidate-inputs-9e02a9f.sha256`; it binds this candidate observation only, not the final source freeze.

These are the current candidate recipe-file hashes, not a final source identity. Recompute and record them from the exact frozen checkout before using either interpreter profile:

```text
policy-engine/pyproject.toml:                     b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267
policy-engine/uv.lock:                            e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463
policy-engine/workers/dowhy-014/pyproject.toml:   df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447
policy-engine/workers/dowhy-014/uv.lock:          c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a
```

The runner hashes both itself and the manifest into its run receipt. The manifest’s asset baseline is commit prefix `077a572ff5880b3f50a85d3e3db6a232d277659a`; final-freeze source assets must be reconciled before running. The runner intentionally stops if any of the 11 declared force-included asset bytes/mappings differ. Do not copy or execute a runner until root binds the final author revision and manifest to the freeze.

## Bounded storage and memory

Read-only VM and container measurements from this refresh:

| Location | Capacity / current availability | Use |
| --- | ---: | --- |
| VM root `/dev/root` | 19 GiB total, 18 GiB free | Separate VM filesystem; not Docker’s storage path |
| Colima data `/dev/vdb1` | 7.8 GiB total, 3.3 GiB free, 432,557 free inodes | DockerRootDir `/var/lib/docker` is `/dev/vdb1[/docker]`; container `/scratch` is the same disk. `findmnt` rounds available to 3.2 GiB; `df` reports 3.3 GiB. |
| Container CPU / memory cap | 2 CPUs; `memory.max=2,306,867,200` bytes | Existing isolated worker container |
| Container memory at read | `memory.current=2,221,060,096` bytes | `memory.max-current=85,807,104` bytes. `memory.stat`: `anon=491,520`, `file=2,025,316,352`, `inactive_file=1,930,760,192`, `active_file=94,556,160`, `slab=194,628,392` bytes; cache reclaimability is not established. |
| Container memory events / pressure | all `memory.events` counters are zero; cgroup PSI avg10/60/300 are `0.00` for `some` and `full` | Snapshot only; pressure totals are nonzero (`some=3,403`, `full=3,235`), and recheck before any heavy slot |
| VM-visible memory | 2.97 GiB total, 2.59 GiB `MemAvailable` from the earlier health receipt | Recheck immediately before any heavy slot |
| Host free-space report | Root reports 12 GiB | Separate host budget; do not sum it with or use it as guest `/dev/vdb1` capacity. No host cleanup or remeasurement was performed in this refresh. |

The prior Q2 preparation measured a 555,792,112-byte source snapshot, 121,945,591-byte source distribution, and 15,146,001-byte source/rebuilt-sdist wheels. Its estimate is about 1.5 GiB scratch when the existing worker environment is supplied. That estimate does not bound the bare clone’s packed object size or the GCP archive size, and it does not count the attached checkout’s roughly 530 MiB working tree. Docker checkout storage and Q2 output share the same 3.3-GiB-free data disk; the VM root’s 18 GiB free must not be counted as container capacity. Measure the final bare pack, checkout, and archive outputs before admitting the Q2 wave. Do not clean or prune caches/artifacts to make space. Current headroom is not sufficient evidence for a capacity claim. The exact container/VM mount and cgroup snapshot is retained under `LOCAL/linux-profile/raw/linux-capacity-*`; `linux-capacity.SHA256SUMS` hashes only those bounded receipts.

The two locked Python environments already occupy the shared data volume (root environment about 1.1 GiB, worker about 779 MiB, uv cache about 1.8 GiB, managed Python about 181 MiB, per the earlier receipt). Q2’s prepared recipe reuses the one root environment and one worker environment, creates one shared build-tools environment and one installed-consumer environment, installs each of three wheels sequentially into that same consumer environment, and retains one run directory. Supply `--worker-python /scratch/dowhy-venv/bin/python` to avoid a second worker profile environment. Do not create one venv per wheel/profile.

## Q2 and native Linux sequence

After final source freeze, runner-input hash reconciliation, capacity recheck, and explicit heavy-slot admission, the intended Q2 invocation is:

```sh
python3 /workspace/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py \
  --repo /workspace/polisyos \
  --source-sha "$freeze_sha" \
  --source-tree "$freeze_tree" \
  --app-python /scratch/root-venv/bin/python \
  --worker-python /scratch/dowhy-venv/bin/python \
  --output-root "/scratch/e02-q2-runs/$freeze_sha"
```

The Q2 run uses one frozen checkout for source wheel, sdist-rebuilt wheel, and GCP-archive-rebuilt wheel; it hashes/extracts the `git archive` stream once and hard-links unchanged members during archive extraction. The prepared selector replays the 91 original Q2 IDs plus the declared installed-consumer selectors for each of those three profiles. It is a single serialized compute-heavy wave, not a full backend or production-data run. Complete command/stdout/stderr and the runner/manifest hashes are retained in its unique run directory.

Use that same attached checkout for the existing Linux witnesses described in `README.md`: the B212 and F real DoWhy worker-to-CAS consumers use the existing Python 3.12.12 worker and fresh Python 3.14 reader; LA-029 uses the ops-owned `validate_part_a.py` path with its real `POLISYOS_SERVER_EXECUTION=1` guard and synthetic C7 integration; DFK creates only the native 10-byte `bad_\xff.json` Git path with a three-byte `{}` file under `/tmp`. Keep the marker-absent LA control and all worker/Linux guards intact. Keep all fixture, artifact, pytest cache, and receipt output under separate `/scratch` or `/tmp` paths. No production data mount is allowed.

No witness is run until root supplies the final freeze SHA/tree, exact runner/manifest inputs, and the heavy slot. The candidate source and current local runner hashes above are preparation evidence only; current verification state remains `verification_missing` for the Linux consumers and `verification_missing` for the frozen Q2 wave.
