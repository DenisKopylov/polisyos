# Hardlink alias preservation audit

Observed 2026-10-27T21:55:44.389135+00:00 at /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos.

All 18 named aliases currently differ from their overlay’s declared Git base, and all contain the corresponding later canonical HEAD bytes. This proves divergence from the declared snapshot baseline. It does not independently establish the bytes each alias actually held at creation, which tests consumed it, or damage elsewhere in the handover.

Each old inode has nine distinct regular-file names and reports link count nine. Those names exhaust its current hardlink count at observation. Each canonical file now has a separate inode and link count one; the earlier admission receipt recorded link count ten before separation.

| Group | Old device / inode | Current alias SHA-256 | Declared base SHA-256 | Declared base Git blob |
|---|---|---|---|---|
| legal | 16777232 / 175370864 | f9b09c09587f19284033176c272db4fc80cb91fe6473057758b367d266d14ec0 | 39fd4ab0fa6ff467f64277b0efadd157761eed15bb63048de90cb22149feca72 | 531c8701dede62a8f2ac479e557024ec20d317fc |
| debug | 16777232 / 183806813 | 1103515eb71f5224cdf598959979c5f3b165bdce7a07b54ad28e37146595ea1c | 03dc65b582b939e11fbf3961d3b09f42fbb2d8c59d03ce7f83ff55874bae8ab8 | 0cc7a51465fe1ff84db397a6d1b7c9e12f8af29a |

The declared snapshot base is cf6a076a8415dc4092cfd3d4e9c8862f81c15a9a. The handover execution base dad68b70b2321001631fc90aa160eec9656f79b1 has the same Legal blob but debug SHA-256 a8c2581e2101b5632b6350d465a4dba0f1a3996d6c99e399e2646884901c6bc3; it is a later version, not the declared October 17 overlay base.

The build receipts declare the base and three unrelated dirty-path exceptions. The v1 overlay has an owner-generation erratum; v2 and v3 declare pinned bases. The v4–v8 and r4 scripts describe hardlink inheritance and bounded replacements; the v5 build script survives but its receipt is missing. The R3/R4 manifests contain 57, 57, and 58 changed-path entries with neither target. The R3 builder selects postimages and deletions, not every overlay member, so list absence does not prove the original bytes. Git blob content and present inode/bytes were recomputed; original per-alias historical bytes remain not_established.

## Exact alias paths

Legal inode 175370864

- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-r4/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v2/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v3/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v4/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v5/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v6/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v7/tests/unit/data_forge/legal_batch/test_embed_local.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v8/tests/unit/data_forge/legal_batch/test_embed_local.py

Debug inode 183806813

- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-r4/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v2/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v3/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v4/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v5/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v6/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v7/tests/unit/runtime/http/test_debug_api.py
- policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-scholar-six-root-impl-736104d-20261017-r3/candidate-overlay-v8/tests/unit/runtime/http/test_debug_api.py

## Scope and evidence

The complete Git changed-path set from dad68 to a323 contains 50 paths, all currently regular files. Fresh lstat found none with more than one hardlink after canonical isolation; this says nothing about historical link counts for the other paths.

The handover untracked-copy manifest and transfer-entry registry each contain 5,435 regular-file rows. Complete row inspection found none naming these tests or this overlay; ignored RAW originals are outside that denominator. The handover verification is a transfer-metadata check, not a whole-RAW integrity check.

Discovery used exact basename enumeration in local RAW trees with production data and environment directories excluded. Handoff RAW traversal reported permission errors in b05 and intentionally unreadable prepared-b scratch directories. No scan-wide absence is asserted. The 18 named paths were re-read, hashed, and reconciled against inode link counts. This proof does not cover other inodes, later writes, outputs, symlinks, or whole-handover integrity.

Selected execution scripts contain Path.write_bytes calls for the test paths. In-place writes to a shared inode propagate to hardlinks, but the selected records do not establish a complete per-write inode timeline. Source receipts, Git identities, individual alias observations, and their current SHA-256 pins are in the companion JSON.

## Conditional recovery recipe

1. No restoration was performed. Preserve current alias bytes and metadata and confirm ownership, intended baseline, and any later overlay-specific changes before writing.
2. Immediately before any action, recheck all exact paths, device/inode/link counts, hashes and current canonical isolation; stop on drift.
3. Read the two exact tracked paths from Git commit cf6a into separate scratch files and verify blob IDs, SHA-256 and lengths against this receipt. The dad68 debug blob is a different version.
4. The cf6a bytes are the declared intended baseline; no independent creation-time hash for each alias was located. Adjudicate unknown or intentional later changes with the owner rather than restoring automatically.
5. If restoration is explicitly adopted, preserve evidence first and atomically replace each approved alias with a new inode, preserving mode. Do not write in place to the shared inode or alter canonical source, the index, HEAD or refs.
6. Re-read and hash each destination, verify canonical isolation and bytes, and retain a per-path receipt. Preserve pre-repair originals until separately authorized disposition.

No restoration was performed. Only this report and its JSON companion were created; no aliases, canonical source, recovery data, index, HEAD, refs, or product tests were changed.
