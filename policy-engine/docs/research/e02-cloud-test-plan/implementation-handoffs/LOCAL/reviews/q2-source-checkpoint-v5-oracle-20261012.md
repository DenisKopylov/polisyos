# Q2 source checkpoint V5 independent oracle — 2026-10-12

## Decision

**GO on the V4→V5 post-commit message-reader delta and the V5 preflight controls.** V5 reads the stored commit message bytes from the actual raw Git commit object, so it removes the V4 `%B` formatting-terminator mismatch. The V5 source-intake, exact-eight path, source-hash, branch/base/index, and commit-readback guards remain unchanged except for the message-reader call. V4 remains blocked for commit mode; V5 is the reviewed replacement.

This GO is bounded. No commit mode was invoked. The check establishes that the reader and the unchanged postcondition contract agree with real Git message bytes; it does not certify a future source commit, source-freeze authority, runtime/test health, or a receipt SHA. Root must create a new exact V9 intake for the final eight preimages, with source bytes and modes independently approved/read back, before using V5. Source availability is not runtime green.

## Frozen target and state

- V5 helper: `LOCAL/raw/commit_checkpoint_force_source_v5.py` @ SHA-256 `5970403f752fae1d2a783ebe97fc6cf2d30b645af25f9dc48329e453ab121bdd`.
- V4→V5 patch: `LOCAL/raw/q2-checkpoint-author-v5-20261012/v4-to-v5.patch` @ `d9dc5d4ca9e6b643087a69a4f2a6bc412cd632c7b8226b861608d713f8e71913`.
- Current baseline read before and after probes: branch `codex/e02-unified-local-20261009`, HEAD `d24fdfc9d79ea109b4aa102cc6856a3cd8985583`, tree `d9f977e7bd6c568f4a0e3f83195d9241a3e68f9a`, empty index.
- The valid intake used for dry-run is the old-preimage baseline control @ SHA-256 `00892a62310d9d896969e805425823f8be7ad366ad7721f23bd953987f3e8fb0`. It is not the V9-final source intake.

## Exact delta and preserved controls

The complete V4→V5 diff adds `raw_commit_message_body(repo, revision)`, which runs `git cat-file commit <revision>`, finds the first commit header/body separator, requires that separator, and returns the bytes after it. The only call-site change replaces `git show -s --format=%B` with this raw-body reader. I independently compared the frozen files: `validate_intake`, `check_git_state`, `validate_sources`, `validate_commit_readback`, and `parse_arguments` are byte-identical; `main` differs only at the message-reader call. V5 contains no Python `assert` dependence in the changed path; the `require` guard remains active under optimization.

## Real-Git message witness

On the actual d24 Git object, the stored raw body is 76 bytes, SHA-256 `2b812523d33f73a6b0a86cf203c2704cafcd08b6a98c2848c9ee77f4ab27c27f`. `git show -s --format=%B` returns 77 bytes, exactly the stored body plus a formatting LF; `git show -s --format=format:%B` returns the 76 stored bytes. V5's `raw_commit_message_body` returns those same 76 bytes. V4's expected check is stored message text plus its one commit-terminating LF, so `%B` is a deterministic false mismatch while V5's raw body is an exact match.

I independently repeated the real-object probe in ordinary Python, `python3 -O`, and `PYTHONOPTIMIZE=1`. All three runs returned the same raw-body SHA and accepted the raw message comparison while confirming that `%B` does not match it. This tests the actual current Git object and actual helper reader; no fake Git implementation or simulated command output was used.

## Adversarial controls and limits

My V5 dry-run matrix used the prior author baseline intake and generated 50 JSON intake cases (one exact valid case plus 49 malformed, partial, duplicate, extra, renamed, misclassified, wrong-hash, wrong-base/branch, malformed-JSON, traversal, and symlink cases). Each case ran in ordinary Python, `-O`, and `PYTHONOPTIMIZE=1`: 150 invocations total, all expected outcomes matched. The exact canonical supplemental-manifest row was required and remained force-classified. The same eight source preimages still match the V4 baseline capture (6 `.py`, 1 `.md`, 1 `.json`); this proves only preimage stability, not V9 approval.

The V5 author also recorded a 23-case × 3-mode synthetic postcondition matrix (69 invocations, zero failures), including a positive readback and negative branch/HEAD/parent/path/index/blob/message cases. I inspected the matrix summary and verified that the `validate_commit_readback` function itself is unchanged from V4; this matrix is corroborating author evidence, not my independent execution. My direct test instead binds the new reader to the actual Git object, and my V5 preflight matrix independently re-exercises the entire input surface.

The V4 post-commit `%B` defect is a new P40 message-presentation class and V5 closes it structurally by reading stored commit bytes. The earlier P40 optimized-interpreter enforcement fix remains intact. P37 still limits what this helper establishes: its supplied intake digest and source SHAs are integrity evidence, not approval. P38 mode binding also remains outside the V5 delta: the helper does not bind/read back file modes. The final exact V9 intake must bind each approved source's path, bytes, and mode; the external manifest and independent/root readback provide the approval evidence.

## Evidence index

My read-only evidence is preserved at `LOCAL/reviews/raw/q2-source-checkpoint-v5-oracle-20261012/`:

- `actual-git-body-probe.json` @ `50c78970e7e27b90418b7e2c3b85c4efd8614d43d3333c528b5ce8d309d02bbb`.
- `v5-git-body-mode-matrix.json` @ `b2220c6868a518b414d69a871e2ae250e484157c65a39962743630fb9d79c8e4`.
- `dry-run-matrix.json` @ `1df66b3cce3bdfe2b49665ea519bce6f05fa5eb7e35ea8d4025dc604c9f20c37`; runner `run_v5_preflight_matrix.py` @ `6fb0006db523bd0e490a53650e115a08b87aa6749d728845697eda332f7803e6`.
- `control-delta-static.json` @ `0d3cff48b37a8113e8c1f02f6b7549bb6e103ef6a38d7d7cd560ce205f621689`.
- `source-preimage-crosscheck-v5.json` @ `4767dfecfd1a4204ac30358784ad7af701efd9e73468c81aace37d620b16f7a1`.

Author-side corroborating records are `LOCAL/raw/q2-checkpoint-author-v5-20261012/message-transport-summary.json` @ `1c22c2b8b61b4856643f96fc994a776905a79680de5af6a3d003322b3856dbe5` and `LOCAL/raw/q2-checkpoint-author-v5-20261012/postcommit/postcommit-readback-summary.json` @ `bb3142836bdf926705c9e032fd0033584f49419b089e966d520b4ec28b2a0895`. The V4 commit-mode blocker and real-Git framing witness remain recorded in `LOCAL/reviews/q2-source-checkpoint-v4-postcommit-readback-addendum-20261012.md` @ `e01e6d94b54e29ffb24dcc2a9f0ff8023100a9714eaf47540a11b0cae49300a7`.

No source, index, branch, or commit was changed; no commit-mode call was made.

- `post-probe-final-state.json` records final branch/index/source readback and confirms that no V5 helper output directory was created.
