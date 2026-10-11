# Independent review: Q1 Search/Autotune composition receipt

**Receipt assessment: partial pending one source-snapshot qualification.** The source commit, branch/remote readbacks, retained command outputs, and the receipt's 86-path comparison are internally consistent. The 33-pass composed run and the one-pass corruption control bind the Q1 source/test footprint represented in the commit. The earlier 31-pass output is from a stable but different intermediate test snapshot, so it must be labeled historical rather than exact-candidate evidence.

## Exact target and readbacks

Reviewed `LOCAL/q1-search-autotune-composition-verification-v1.json` (SHA-256 `645ae47b07a5b6555e9eba2eaa7e1a760eefe88191277dc556f96211b19c16a4`, 47,000 bytes). The checkout is on `codex/e02-unified-local-20261009`, at candidate `c3f3f7d3ff2970daa44356535511ef1e84a2c1cd`, tree `4f5a90ba5627615d80effc8e1a7e4c96e6b56bb7`, parent/base `7296a02065fbdac778dae241b137182179667625`. `git ls-remote origin refs/heads/codex/e02-unified-local-20261009` returned the same candidate. The current worktree has separately declared peer edits; I used the committed tree and retained input maps for this review and changed nothing.

I independently matched all 21 receipt footprint paths against `git show <candidate>:<path>`; every candidate SHA matched. The local source readback at `LOCAL/raw/q1-v6-source-checkpoint-20261011/readback.json` has the receipt SHA `f0c957a8270a1f479a4ae58bea72b2a4e4c6d86b75a1bb336f36ebf993bf24ea`. Its sibling `remote-readback.json` has SHA `0bb1e5bbb080509b2d4317a09cf275ae8f017ca79bea1c534c00c0fc8b82c924`; its 21 verified paths exactly equal the implementation footprint and it records the same candidate/tree/parent.

## Run evidence and the one qualification

I verified the retained command-record hashes and output hashes, parsed each retained JUnit file, and compared the complete before/after input maps. The before and after maps are identical for each run.

| Run | Recorded HEAD | Captured input denominator | Result read from JUnit/stdout | Candidate-footprint check |
|---|---|---:|---|---|
| Four-module replay | base `7296a020…` | 6,168: 6,158 `.py`, 5 `.pyi`, 3 `.toml`, 1 `.ini`, 1 `.lock` | 31 tests, 0 failures/errors/skips | 19 Q1 footprint paths present; `tests/unit/remediation/test_srv_01.py` differs from candidate |
| Replay plus first-cold and dynamic-positive selector | base `7296a020…` | 6,169: 6,158 `.py`, 5 `.pyi`, 4 `.toml`, 1 `.ini`, 1 `.lock` | 33 tests, 0 failures/errors/skips | All 20 Q1 footprint paths present in the input map match the candidate; `README.md` is outside the runtime input map |
| Corrupt-field/missing-call/invalid-target control | candidate `c3f3f7d…` | 6,169 with the same type counts as run 2 | 1 test, 0 failures/errors/skips | All 20 present Q1 footprint paths match the candidate |
| Nineteen-path Ruff check | candidate `c3f3f7d…` | 19 explicit Python targets; retained command map has 22 inputs | exit 0; stdout is `[]` | Candidate command is pinned to the committed target list |

The one mismatch in run 1 is concrete: its captured `test_srv_01.py` SHA is `7ac1c50454509327d83309ba8ef305e2364a4d20d7b5d22d648a2bef09f4dc1f`; the candidate SHA is `3ce515607042c32a0f3e8a07021a5c1176b124f78747d989851fb3c35c297459` (base SHA `cf5f4f6963200a848c8f3a41159afa8bfe80439f85f2d0a5440e6f910f446d5d`). The retained command record contains the earlier file hash but not those intermediate file bytes, so the 31-pass output cannot be inspected as the exact committed test source. The added `.toml` in run 2 is `architecture/imports/dynamic.toml`, which is in the candidate footprint and matches the candidate SHA. The run-2 33-pass output is therefore the relevant candidate-bound composed run.

For the run-2 6,169-path map, I recomputed comparison against the candidate tree: 6,083 matches and 86 mismatches, exactly the same paths and SHA pairs recorded in the main receipt. All 86 are `.py` paths and none intersects the 21-path Q1 footprint. This is a material scope boundary, but it is already explicitly disclosed in the receipt: the capture is the broader composed worktree, not a claim that every captured companion is present in this partial candidate commit. The receipt correctly keeps final common freeze and whole-candidate/native-green pending.

Retained evidence pointers (the main receipt records each command/stdout/stderr SHA):

- 31-pass run: `LOCAL/raw/batched-blocking-focused-20261010/q1-v6-real-funnel-autotune-canonical-import-consumers-20261011/`; command record SHA `89c9ba444ea1bfcb8058e69afa166e2228a9008373e60c4f705041e5761acdd8`; JUnit SHA `fcc924b88f29f417dd511d9630a32ab7d3cc1778641b24b85a114bffcd294b71`.
- 33-pass run: `LOCAL/raw/batched-blocking-focused-20261010/q1-v6-dynamic-v3-first-cold-and-composed-consumers-20261011/`; command record SHA `1e9a872ba2f94fc91a726f5348b00f750865187ec89346ee937cf079d23ff873`; JUnit SHA `ff18b69e1a41e6232700ad9fdf7eb6cb1a3f5de2c0a1d881814780c08be3461a`.
- 1-pass semantic control: `LOCAL/raw/batched-blocking-focused-20261010/q1-v6-dynamic-v3-corrupt-field-removal-controls-20261011/`; command record SHA `d172aa38c98a7a4864a8b2896fa0fa9f19728c34e0f9b81e519d4d59f294a908`; JUnit SHA `68482f30d812e2c6f0bca2855acea054fd8ce9ee8491822ce71217d5785c9c16`.
- Ruff: `LOCAL/raw/batched-blocking-focused-20261010/q1-v6-dynamic-v3-final-nineteen-paths-ruff-20261011/`; command record SHA `fd03c02d06e1b12ca6f5c6ee5c8299cb5ca3b0399625cd76331b8d52e5f91a92`.

## Review disposition and limits

The narrow correction needed is to label the 31-pass result as an earlier captured snapshot and distinguish it from candidate-bound results. The 33-pass run, 1-pass negative control, and Ruff result are the exact-source outcomes supported by these records. I did not rerun tests or alter the main receipt.

**P40: SAME_CLASS_DEEPER, bounded.** This is another source-snapshot-to-candidate linkage distinction, not a new product defect. The discriminator is the per-run input hash map versus the committed footprint. The bounded residual is the 31-pass pre-final test snapshot; the falsifier for any claim that it is candidate evidence is the changed `test_srv_01.py` hash above. Do not add per-file exceptions or treat it as a second implementation repair.

This receipt review does not assess whole Search capability correctness or native repository readiness. `closure_ids` is empty, `formal_g_adjudication` is `not_adjudicated`, and the receipt holds the historical LA-021 closure pending the separate CAN Core/IR and profile/history evidence. No G acceptance or closure is implied. I ran no tests, imports, Ruff, or builds; the checks here were read-only Git/object, hash, JSON, and retained-output reconciliation.
