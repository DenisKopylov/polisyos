# V4 post-commit message readback addendum — 2026-10-12

This addendum supplements the frozen V4 independent review at `LOCAL/reviews/q2-source-checkpoint-v4-oracle-20261012.md` (SHA-256 `c86356ae9bd805c36b55bc4f2c148da78d3332f9662e7776cad32f159bce7aa5`). It does not rewrite or retract that review's preflight matrix results. It changes the disposition for using V4 to create a source commit.

## Finding: V4 commit mode is BLOCKED

V4's post-commit readback will reject a correctly committed source capsule because it compares Git's pretty-format output to the stored commit body with the wrong newline framing. The commit is made before this check. Thus V4 can return a nonzero error **after moving HEAD**, leaving the intended eight-source commit in place without the helper's readback receipt. A failed process exit is not evidence that no commit occurred.

The source is concrete: `commit_checkpoint_force_source_v4.py` line 537 runs `git show -s --format=%B HEAD`, while line 419 requires `commit_message_bytes == (expected_commit_message + "\n").encode("utf-8")`. `expected_commit_message` is constructed without a trailing newline; the check expects exactly the stored body bytes, including its one terminating LF. Git's `%B` output also appends a pretty-format terminator LF.

## Read-only Git falsifier

Against the actual current branch commit `d24fdfc9d79ea109b4aa102cc6856a3cd8985583` (tree `d9f977e7bd6c568f4a0e3f83195d9241a3e68f9a`), `git cat-file commit` yields the stored body ending in one LF. `git show -s --format=%B` yields those same body bytes plus another LF; `git show -s --format=format:%B` yields exactly the stored body. The raw bytes and exact hashes are preserved under `LOCAL/reviews/raw/q2-source-checkpoint-v4-postcommit-addendum-20261012/`.

The observed body is `docs(e02): record demographic reader source and committed consumer evidence\n`. Therefore the `%B` output is that body followed by one additional LF. The actual d24 subject differs from V4's future checkpoint message, but this is a Git pretty-format framing behavior, not content-specific. Applying the same actual reader to V4's generated checkpoint message gives the deterministic mismatch with V4's one-LF expectation. **No commit-mode invocation was made.** The prediction is based on the real Git output plus the frozen helper's post-commit code, not a mock Git implementation.

## Classification and smallest closure

This is a **new P40 class** (stored commit-body vs pretty-format presentation framing), distinct from the previously closed optimized-interpreter enforcement class. It is a structural post-commit validation defect, not an isolated source-path escape. The smallest closure is to read the actual stored commit body, such as using and verifying `git show -s --format=format:%B` or parsing `git cat-file commit` after its header separator, then compare that exact body to the expected bytes. V5 must test the representation with actual Git and retain the existing full readback controls. Do not use V4 commit mode for the Q2 source write.

## Updated disposition

- **GO remains:** V4's dry-run preflight and its 150 ordinary/optimized adversarial probes establish the recorded mechanical intake controls.
- **BLOCK:** V4 must not author the Q2 source checkpoint commit until the V5 delta independently passes this real-Git falsifier and the existing guard-quantity controls.
- This finding does not change the separate authority limitation: the future V9 source freeze still requires external exact-manifest approval plus independent/root byte and mode readback. Source availability is not runtime green or a future receipt SHA.

## Deciding evidence

- Current-state/probe capture: `LOCAL/reviews/raw/q2-source-checkpoint-v4-postcommit-addendum-20261012/probe.json` @ SHA-256 `fa5e56f56dfc31aefc8c44ef8439fbcb55d172dbeb0504954c57b0217ff584c3`.
- Raw `git cat-file commit` output: `cat-file-commit.raw` @ `de9313dd878bf61447d6511d00321a30e508c2fd44ccd30fe3cb7625a01212c8`.
- Parsed stored body: `cat-file-body.raw` @ `2b812523d33f73a6b0a86cf203c2704cafcd08b6a98c2848c9ee77f4ab27c27f`.
- Actual `git show -s --format=%B` output: `show-percent-B.raw` @ `6d9e53880197421c456253562665a936942f07eb56fbf03eddc7b16fea3802cd`.
- Actual `git show -s --format=format:%B` output: `show-format-percent-B.raw` @ `2b812523d33f73a6b0a86cf203c2704cafcd08b6a98c2848c9ee77f4ab27c27f`.

The branch, HEAD, tree, and index were read-only; Q2 source preimages were not touched and commit mode was not invoked.
