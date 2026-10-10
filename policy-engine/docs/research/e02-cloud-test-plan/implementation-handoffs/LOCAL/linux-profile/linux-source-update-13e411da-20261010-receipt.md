# Linux source update receipt: 13e411da

The append-only source update completed on the existing isolated Linux worker. This receipt supersedes the earlier plan's stale introductory sentence that said no new freeze had been supplied. It records the actual source and worker state; no product tests or builds were run.

## Frozen source and transfer

- Host source checkout: branch `codex/e02-unified-local-20261009`, HEAD `13e411da7d9e505856fc336b3d25fd0aabdb1f66`, tree `8d8c4082febf1676dd86084106f3266d8b2131a3`. The attached host repository is full/non-shallow and had no tracked working-tree or index changes. Three unrelated untracked LOCAL notes were present; the bundle was made from the committed branch ref.
- Base: `7574c864a605c50efc033b966807790cbd8d1781`, tree `9561394a619e21b92680d79a1aa812da6892967c`, actual parent header `5e312037e180938aa643abccfd727a2a12b9a691`.
- The ordered update range contains three commits and the base-to-freeze diff contains 12 paths. Host and Linux `cat-file -p` tree/parent headers matched for the base and all three commits; see raw stage 1 and stage 5 outputs.
- The transfer bundle was created from the host branch ref with base `7574...` as its prerequisite. SHA-256: `0941a74dc1a2e7c7a111bd28437d8003fca57cc92a096c8f70b4e2910befd770`; size: 35,190 bytes. Host and Linux bundle verification passed.
- Existing bare ref advanced by compare-and-swap from `7574...` to `13e411...`. The existing attached checkout fetched that branch and fast-forwarded to the same SHA/tree. No reset, rebase, clone, force update, unshallow, or cleanup occurred.

## Linux state read back

- Dedicated container: `e02-local-worker-provision`, ID `88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`, image `sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`, Docker context `colima-e02-local`.
- The worker retained only its three existing named volumes: `e02-local-uv-pythons` at `/opt/uv-python`, `e02-local-uv-cache` at `/root/.cache/uv`, and `e02-local-uv-env` at `/scratch`; no bind mount was present.
- Bare HEAD/ref and attached checkout HEAD/tree/origin-tracking ref all resolve to `13e411da...`. The checkout status is clean.
- Both shallow files remained byte-exact single-line `7574c864...`. Neither Git object store has an alternates file or dangling alternates symlink, and both Git object-directory environment variables were empty. Connectivity-only `git fsck` passed for both stores.
- The primary manifest remained SHA-256 `26f415a50704a8f555be7c10676e5f427178b150152630140e22b8df054086c6`, Git blob `0e714774f27236b54353913527ebfbd1ff8f1965`. The four ignored Q2 inputs remained regular ignored files with their frozen hashes: `run.py` `c8604c1d0f130cbdb11b4b30814e226df61cc272cf8f2f5a10fa0aeae378d4bf`; `timeout_driver.py` `7c3413ea3735a8d9732431cd9ca1a3b16e8ac735c2d82a9614479379fa33b073`; `supplemental_run.py` `4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49`; `supplemental-manifest.json` `ae2854d95dd2a36283f9bc2a2fcdd24caf0b8712bca92a811ff401112fb4e7df`. These four runner inputs are absent from the frozen Git tree. The capture hook's host input hash was `4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2`; this source update did not copy or rebind it.
- All five app/DoWhy lock and Python-version pins matched the freeze and worker files: app `pyproject.toml` `b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267`, app `uv.lock` `e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463`, DoWhy `pyproject.toml` `df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447`, DoWhy `uv.lock` `c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a`, DoWhy `.python-version` `7b55f8e67b5623c4bef3fa691288da9437d79d3aba156de48d481db32ac7d16d`.
- Existing tool profiles still report uv 0.9.21, root Python 3.14.0/Hatchling 1.27.0, and DoWhy Python 3.12.12/DoWhy 0.14. `uv pip check` passed for 161 root-environment packages and 52 DoWhy-environment packages.
- After transfer, `/scratch` had 5,902,120 KiB available; cgroup current was 1,345,560,576 bytes, OOM/event counters were zero, and pressure averages were zero. Container memory limit remained 2,306,867,200 bytes.
- No production mount, dependency install, package build, Q2 wave, LA029, B212, DFK, or product test ran.

## Captured command and output files

The ignored raw directory below retains each actual `bash -s` argv and full stdin in its JSON, plus complete stdout, stderr, and exit status. All six stages exited 0. Their SHA-256 values bind the captures.

`LOCAL/linux-profile/raw/actual-update-13e411da-20261010/`

| Stage | command.json SHA-256 | stdout SHA-256 | stderr SHA-256 |
|---|---|---|---|
| Host preflight and bundle | `4522f4b31e5f0717495c8c602d0559a3fc9d0e805c44b40c6fffd7f9a423cb8c` | `35e2fb5752303538a392bd3152654bf58c5b3ad986fbd854de5aa7695c23d63c` | `7b5e63d8fa30b1f06a2132fc443310a6b2651e6bc281e08be82be094ad052d4a` |
| Worker copy and bundle verification | `a535863ab0babe00bb9d893d471ca1e243c219dfab61813981279d1fd52dc546` | `d66229c574806cb4496c638e24865b5bf1f619f691fdfa29d224844ca8598ddc` | `b51df571b15667f0a07df5aca4cf2dd5249a0ed2df65099d75025b8a9f7b8a31` |
| Bare CAS and checkout fast-forward | `92312978c50f931aca0a3cda09700257dbec9dc655d239b28697b6c33c427e08` | `815f3748041774c33d973091ecf10047c118610db86c55872d177f652d761fbf` | `77958899c9c858103a03752c34f0cea8aebc12b62c8efcf42b6cada1603ac64e` |
| Post-update refs, pins, and environment | `f26d04343523b661127b19a8322aa8264afc77b17e924c999af0447dae41b96d` | `e796ae56e72401dcf8c497618c442a90a7742927c166f1633511ae7a1d73c94d` | `6fa3c263f10692c2f129d19802d1be509684f9f2e1e3d6715493e165097a1650` |
| Host/Linux parent-header comparison | `93919a35e31c8486457098dab57337bebfd2595f92b1b4eaac533b1447485a18` | `458cd1c013e94d3a170025bfd6ba2b2029df27029290f1dd051e45725530afab` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Final lock-file content readback | `15b69e9deff7a935f24cd23c9ca351aa7c7081e5b8ff5bbbfa3a25a52e3aa0aa` | `6034c1a9903958ad406eb9ed3608e0ab4e2916aad0ac59b358a762ee5f02a71d` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The bundle file is retained both in that ignored raw directory and at `/scratch/e02-source-update-13e411da7d9e505856fc336b3d25fd0aabdb1f66.bundle` in the worker for reproducibility. No Git commit was made for this receipt.

