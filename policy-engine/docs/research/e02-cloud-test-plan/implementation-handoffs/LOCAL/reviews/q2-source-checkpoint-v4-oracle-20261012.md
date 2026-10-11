# Q2 source checkpoint V4 independent oracle — 2026-10-12

## Verdict

**GO, bounded to the helper's mechanical source-intake preflight and checkpoint-authoring controls.** The V4 helper pins the branch, base commit and base tree; requires an empty index; enforces an exact, unique eight-path source boundary with a fixed 5-force/3-normal partition; binds candidate bytes to the supplied intake; and rejects the tested malformed, incomplete, duplicate, extra, renamed, or dishonest inputs in ordinary Python and optimized execution.

This is **not** source-freeze approval, an independent acceptance gate, proof that Q2 runtime/tests are green, or a source publication receipt. Do not infer any of those authorities from a valid intake SHA or this dry-run. The canonical intake used here is an author baseline-control packet, not the final V9 source freeze. The later source checkpoint still requires the exact external V9 manifest, independent/root byte and mode readback, and a newly prepared intake over the approved eight source preimages.

## Frozen target and baseline

- Helper: `LOCAL/raw/commit_checkpoint_force_source_v4.py` @ SHA-256 `5804178a9fa0059c18fd262fd5e039fd84883159f9f977465c1759a23f25413a`.
- Intake: `LOCAL/raw/q2-checkpoint-author-v4-20261011/v4-dry-run-intake.json` @ SHA-256 `00892a62310d9d896969e805425823f8be7ad366ad7721f23bd953987f3e8fb0`.
- Pinned base: `d24fdfc9d79ea109b4aa102cc6856a3cd8985583`, tree `d9f977e7bd6c568f4a0e3f83195d9241a3e68f9a`, on `codex/e02-unified-local-20261009`; the index was empty. The authorized `6580b9b5… → d24fdfc9…` delta consists of the three LA032 receipt/review files listed in the raw base-state record and has no Q2 source/index overlap.
- The intake's own digest is an integrity witness: V4 recomputes it over the supplied JSON bytes. It is not a trusted approval key, and V4 does not pin an independently approved intake digest or approve the candidate source SHAs. Its field name `approved_complete_footprint` does not change this authority boundary.

## Source-byte preimages checked

All eight files were regular, non-symlink worktree files; each measured SHA-256 matched the intake. The three normal paths resolved to base Git blobs and were not ignored. The five force paths were absent from the base and ignored. The required canonical supplemental manifest is explicitly one of those five force paths.

| Source path (repository-relative) | Candidate SHA-256 | Size | Intake class |
|---|---|---:|---|
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py` | `4593febfff4242f5e2004897ed929c97566feab4266b8984a6e23c94a48e37e2` | 2,229 | force |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-recipe.md` | `880dfacbaf6f7ff42dcf4db894d71de3acc2f56c773249a8453d36d507b169f4` | 13,924 | normal |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/q2-freeze-input-audit-v2-20261011.py` | `8cd4103d3b330dbe84fbb8c8e4aec92640800602fd83a4e586ba29933be9c997` | 47,297 | force |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py` | `a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0` | 83,214 | normal |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json` | `1acd43fa91682ca2d8eb8441f8da558d65e2920eb951e01fa693b562c4e9a5a7` | 2,148 | force |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py` | `4a80f59032665607ff139bf8ed8fbf73e05432f03297b3c82ff78d07d49e5f49` | 29,364 | force |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/test_timeout_driver.py` | `55e390d5214bf55f16e6558476f5883d5a85f7baa03ab80173ed292d734882e7` | 35,675 | force |
| `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py` | `ca718253aa63cb1c3ca6aaafd2b9a4e9cf638e921956d76d697d161c6d447203` | 26,616 | normal |

## Direct verification and control behavior

The final matrix ran 50 cases in each of three interpreters (ordinary, `python3 -O`, and `PYTHONOPTIMIZE=1`): 150 invocations total. In each mode the valid eight-path intake passed once and all 49 adversarial cases exited with argparse status 2 and a parser error, with no traceback. Probes include missing/duplicate/extra/renamed rows, duplicate/partial/extra approved footprints, omitted or misclassified canonical manifest, wrong force flags, malformed paths/types/hashes, false base/branch/reason/message, duplicate JSON keys, malformed JSON/UTF-8, NaN, bad CLI values, and intake symlink/traversal.

AST readback parsed the frozen helper with zero Python `assert` nodes and 94 explicit `require` call sites. In particular, the exact-eight and unique-set predicates remain active under `-O`; the dry-run branch returns before output directory creation, receipt writes, `git add`, or `git commit`. The 23 post-commit readback requirements were reviewed statically (including parent, changed-path set, empty index, candidate-to-blob hashes, and message), but commit mode was deliberately not invoked. No claim about a successful commit follows from this review.

The dry-run probe's accepted output was `source_intake_preflight_pass`, HEAD `d24fdfc9…`, 8 paths, 5 forced paths, and the supplied intake SHA. Final readback confirmed unchanged branch/HEAD/tree, empty index, unchanged eight source hashes, and no helper-created output directory. The evolving shared worktree has unrelated changes; status line counts are recorded only as evidence identifiers, not attributed to this probe.

## P37, P38 and P40 classification

- **P37 — gate predicate:** V4 recomputes intake-byte SHA, candidate source-byte SHA, exact path and force sets, base object existence, ignore state, and clean-index/base checks. It does not establish who approved those bytes. The caller supplies both the candidate hashes and the intake digest; a caller can recompute both after changing a source. Treating this helper's green result as V9 approval would therefore be `consumer_asserted`/`not_established`, and must fail closed for source-freeze acceptance. The external V9 manifest and independent/root readback supply that separate approval evidence.
- **P38 — mode proxy:** The artifact property needed for an exact source freeze includes Git mode where mode can change execution semantics. V4 measures source bytes and regular-file/non-symlink status; its intake, staged-byte check, and commit readback do not bind or compare mode. A same-byte `run.py` changed from `100644` to `100755` is a concrete divergent case: the helper's byte checks can remain green while execution semantics change. Current observation is all eight worktree modes `0644`, with the three base paths `100644`; the future exact intake/readback must bind modes. This is a bounded residual for helper mechanics, but blocks using V4 alone as a complete source-freeze proof.
- **P40 — finding class:** V4 closes the optimized-interpreter enforcement class structurally: validation uses explicit `require` checks rather than `assert`, and the same adversarial matrix is rerun under both optimized modes. This is a generic enforcement fix, not a one-case patch. The exact footprint remains a fixed eight-path contract; no count-only escape permits duplicate, renamed, or partial paths.

## Evidence index

All evidence is under `LOCAL/reviews/raw/q2-source-checkpoint-v4-oracle-20261012/` and is preserved alongside this note:

- `base-state.json` @ `109bec83ec2db3092c29413ed384fc7d1660c55423f5a9981e0cf910f7ae267e`.
- `source-preimages.json` @ `bc0dd53bb7d7afbfe17710af104035c8b3d3a121702819737020585da588048d`.
- `source-mode-observation.json` @ `818b2f73cd914c8e9b4a03dceebbf16f69bdce8843cd337528904f5cd3f686f8`.
- `static-guard-inventory.json` @ `6c372a3fee5e632387ddf6767399facb246acba069f20842618832406f4a1d60`.
- `dry-run-matrix.json` @ `ea8b1246b088ed9b4689afe0a2c21c02b60512128de9dfb0a0779f8fc9bbb59e`; compact outcome `dry-run-matrix-summary.json` @ `618d886b0ce3c8a150efa7510ec2a2c74603a37a42ade2227c25bbe33e37e067`.
- `post-probe-state.json` @ `91da75878b080a508542960d7cbfa40a29dbb265afd52664d0b164ab04fb8c62` and `final-readback.json` @ `af3fbce2381b36b9dc5066f506be62ddec10845b5a07dd9199be295c6ce0ba11`.
- Earlier V3/V4 byte cross-check `v3-v4-source-preimage-crosscheck.json` @ `60fb945ad98e07ea6779e6922fed8934a69f6525d8802ba2701226ae20b2fbde`.

The first harness attempt used two invalid `--name` slugs; it was retained as `dry-run-matrix-harness-mistake.json`. The corrected matrix above is the deciding run. No helper, source, index, branch, or commit mutation was performed. The helper's green preflight establishes source availability only; it does not establish runtime health or the future checkpoint's own receipt SHA.
