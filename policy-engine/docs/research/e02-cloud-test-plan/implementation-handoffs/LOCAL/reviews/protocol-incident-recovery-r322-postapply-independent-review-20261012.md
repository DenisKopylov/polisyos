# Protocol Incident Recovery R322 — Post-Apply Independent Readback

Review date: 2026-10-12. This is a successor to [the pre-apply review](protocol-incident-recovery-r322-independent-review-20261012.md), preserving that review as written.

**Result: bounded recovery verified.** The root ran the guarded materialized apply once after the pre-apply conditional GO. I did not execute the wrapper. I independently matched its 70-entry readback against the R215 manifest and current worktree.

The readback at `guarded-recovery-readback.json@29a32fddff1c9097144d50a1407aff9eba75187f2fdc6321f0816e0785f161f1` has 70 unique paths. Each path and recorded original preimage agrees with the 70-entry R215 manifest, and a fresh hash walk of the current worktree agrees with every preimage, including expected absences. The file-type denominator remains 70 paths: 58 `.py`, 7 `.md`, 2 `.ts`, 2 `.toml`, and 1 `.json`.

`policy-engine/src/polisyos/core/artifacts/protocol.py` now hashes to `a55a20f86ef529f3d81326a617f68981e6f65b9d23d06984ed7fc123b7028c8e` and is byte-for-byte equal to `git show HEAD` at HEAD `b214e3f5364c6ce0c081d470da8f4e0ed2560de7`. The checkout remains on `codex/e02-unified-local-20261009`; the index is empty. The apply stdout has `diff_check_exit: 0`; stderr is empty.

The executed wrapper, `guarded_recovery.py@bfe86dc42ee84011e4b9ee557c88f156843539a982dcb3c4a2da33d31db8d01a`, binds both the resolved current directory and Git top-level to the intended checkout, and verifies the branch, HEAD, index, 70-row manifest hash, expected pre-apply source state, application-helper hash, and composition hash before invoking the materializer. Its post-run checks cover all 70 preimages and the protocol-to-HEAD byte comparison. The receipt identifies `apply_materialized_composition.py@838d86cef78cdaf985c8260352bb7caa7d681ed6318c82f07ae52c87939cb20f` as the application helper and `admit_unified_patch.py@60a37f5ad54c656311636a0e4379f1c1c8718ad66dfc384d19c17e2914e9ad43` as the materialization helper, resolving the earlier role ambiguity.

P35 is closed for this recovery by the complete path walk. P38's root-location gap is closed by the executed wrapper's exact physical-root and Git-top-level assertions. P40 remains classified as a NEW procedural class: the one-file restore completed through the exact-preimage materializer. This result does not certify E02 closure or R215 acceptance; the guarded receipt has no closure IDs. No tests or runtime imports were run.
