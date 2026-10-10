# 7574 partial Linux transport: storage finding and safe resume

Captured 2026-10-10. This note records the existing root-created partial transport only. No source was recopied, no store was recreated, and no product test or build ran.

## Frozen source and failure boundary

The frozen source identity is branch `codex/e02-unified-local-20261009`, commit `7574c864a605c50efc033b966807790cbd8d1781`, tree `9561394a619e21b92680d79a1aa812da6892967c`. The recorded attempt is [actual-transport-7574c864-20261010](raw/actual-transport-7574c864-20261010/): command JSON SHA-256 `67030c22a3bcec8e712916a5252f2632d67d37b293275181021630d30b34b944`, stdout `84e8d4e405846c8cc568dbde928381ff94a64a5dceb9299125679b8f0b644ba7`, stderr `dff18f886a4e8dd966e916fdfec84c5db607cece6f5040f922c7bb0c4df9645a`. The captured argv names this exact source and freeze and exits 1 at the old unconditional read of `/workspace/polisyos/.git/objects/info/alternates`, which is absent. It fails after the three stores pass commit/tree/shallow/branch and worker tracked-clean checks, before runner inputs or the child-output hook are copied.

The host checkout now has later uncommitted C12 edits. Resume consumes only the committed 7574 Git object/tree and the five individually pinned Q2 files plus the separate pinned capture hook; it does not consume working-tree files, uncommitted changes, or later descendant commit contents. Its source proof requires the expected attached branch, the exact tree for commit 7574, that commit to be an ancestor of attached HEAD, and the frozen primary-manifest Git blob hash. Host working-tree cleanliness is neither asserted nor used.

## Read-only store inspection

The host bare store is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/e02-7574c864a605c50efc033b966807790cbd8d1781.git`. It is shallow at exactly the frozen SHA, attached to the expected branch, and `git fsck --connectivity-only --no-reflogs HEAD` exits 0. Its root is owned by host uid/gid 501:20, mode 755; its object store is on device 16777231. `du -sk` reports 197524 KiB. The one pack is `pack-eca2d35110939ce7c8404172a9fa95d0cf04e217.pack`, 193865125 bytes, SHA-256 `202b7b6a927f44d35ea6c1b026715fc4977ef6e1328af375ae905b1f5cf747aa`.

The existing worker bare store is `/scratch/e02-7574c864a605c50efc033b966807790cbd8d1781.git`. Its root is uid/gid 0:0, mode 700, inode 430936 on device 64785; its shallow file contains only the frozen SHA, its branch/ref and tree match, and connectivity fsck exits 0. `du -sk` reports 190212 KiB. Its pack has the same filename, byte count, and SHA-256 as the host pack; its inode is 430963 on device 64785. The adjacent `.idx` and `.rev` hashes also match the host files.

The existing attached checkout is `/workspace/polisyos`. Its root is uid/gid 0:0, mode 755, inode 430971. It is attached to the expected branch and has the exact commit, tree, and one-entry shallow boundary. `origin` points to the existing worker bare path. Its tracked and visible untracked status is clean, and connectivity fsck exits 0. There is no `objects/info/alternates` file. Its local object directory holds one pack with 24318 objects, 185.53 MiB. That pack has the same filename, byte count, and SHA-256 as the worker bare pack (`202b7b6a927f44d35ea6c1b026715fc4977ef6e1328af375ae905b1f5cf747aa`); the measured inodes/devices differ, but that is descriptive only and is not a guard. Whole-checkout `du -sk` is 917044 KiB.

The dedicated worker remains container `e02-local-worker-provision`, ID `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`, image `sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`, with only the three existing named uv volumes and no bind mounts. No other container is running. The `/scratch` filesystem has 5902944 KiB available; cgroup current is 1339486208 bytes and OOM/high/max counters are zero.

Host Git is 2.49.0; worker Git is 2.47.3. The [Git clone documentation](https://git-scm.com/docs/git-clone) says `--shared` on a local repository sets up an alternates file and starts the clone without its own objects. This actual `git clone --shared --single-branch --branch ...` instead yielded a fully populated local object store on another device with no alternates. The cause is not established. The repair recognizes the resulting measured mode; it does not label this checkout shared or infer storage from the command line.

## Inputs and current boundary

All five current Q2 host inputs pass their pinned hashes, as did the captured transport preflight. In the worker checkout the primary manifest is tracked and present with the expected hash. `raw/run.py`, `raw/timeout_driver.py`, `raw/supplemental_run.py`, and `raw/supplemental-manifest.json` are ignored paths and absent. The checkout-local `raw/` directory is absent. The child-capture directory and `sitecustomize.py` target are absent. The five locked pyproject/uv files pass their existing SHA checks.

This is the same transport class one level deeper (`P40`), not a new runtime-semantics class: the earlier mechanism treated the requested `--shared` mode as proof that an alternates file existed. The closure checks the actual object database. For this known independent mode it requires empty `GIT_ALTERNATE_OBJECT_DIRECTORIES` and `GIT_OBJECT_DIRECTORY`, no alternates file, the captured local pack name/count/SHA, and successful connectivity checks. If an alternates file exists, it must be one regular line pointing exactly at the existing worker bare object directory. Filesystem device or inode comparison is not used to decide independence.

## Guarded script behavior

[final-source-linux-wave.sh](raw/final-source-linux-wave.sh) now has three distinct paths:

- `transport` remains a new-clone path and still refuses any existing destination. After cloning, it validates exact Git identity and accepts either one regular alternates file naming only the existing worker bare object directory, or an independent local store with no alternates, the captured local pack name/count/SHA, and successful connectivity checks.
- `preflight-resume` is read-only and bound to this known partial transport. It checks the committed source/branch attachment proof without requiring a clean host worktree, the captured failed-attempt hashes, ownership/container/mount identity, both existing bare/checkout Git stores, lock hashes, all five input states, and hook path before printing readiness.
- `resume` repeats those checks and continues in the same stores. It does not clone, reset, delete, move HEAD, fetch, or change the source checkout. It preflights every overlay target before writing, reuses exact tracked/ignored bytes, copies only absent pinned ignored files, and verifies hashes. The hook follows the same absent-or-exact rule.

The repaired script SHA-256 is `cc17a395e38fee53d67fe3c4fb6c69ac56bcaed63c91abca705cd462cc589ffb`. `bash -n` and the eight-case no-write copy-decision self-test pass. Two negative host-environment probes also reject nonempty `GIT_ALTERNATE_OBJECT_DIRECTORIES` and `GIT_OBJECT_DIRECTORY` before Git or Docker; their receipt is [git-object-env-guard-probes-7574c864](raw/git-object-env-guard-probes-7574c864/probes.json) (SHA-256 `f5778614faa57be69b48734bd92b4241c2ec4bf3715e214e7ed21aed786a80f5`). Read-only Docker-backed `preflight-resume` exits 0; its receipt is [preflight-resume-7574c864-20261010-q1delta](raw/preflight-resume-7574c864-20261010-q1delta/) (`stdout.txt` SHA-256 `8dab3af1e597234d82c5fa4542af2cec5b3fda52a1b24e8ffa75b1dad00ab9e6`). It verifies the attached branch and frozen tree/manifest, empty Git object-directory environment, exact worker object store and connectivity, existing worker mounts and locks, and the five pinned inputs plus hook. It classifies four ignored files and the hook as absent/copyable, and the tracked primary manifest as exact/reusable. No `resume` ran and no input or hook was copied. The host checkout was at the exact freeze SHA during this preflight and had unrelated uncommitted C12 edits; the source verifier did not assert or consume them.

Read-only preflight command for that review:

~~~sh
source_checkout=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos
branch=codex/e02-unified-local-20261009
freeze_sha=7574c864a605c50efc033b966807790cbd8d1781
freeze_tree=9561394a619e21b92680d79a1aa812da6892967c
bash "$source_checkout/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/final-source-linux-wave.sh" \
  preflight-resume "$source_checkout" "$branch" "$freeze_sha" "$freeze_tree"
~~~

The mutating overlay step is separately named `resume` and has not been invoked. The planned later source advance for the C12 fingerprint correction is separate: no fetch or fast-forward is included here, and the later freeze must be explicitly supplied before any source update.
