# R1225 — independent S1 fallback semantic companion style-delta review

**GO for the style-only delta.** The root-formatted candidate preserves the reviewed R1185 test semantics exactly. This clears formatting readiness for this one test-file companion; runtime replay remains unrun, and this is not a test-pass or capability-closure claim.

## Bound source and candidate

Current branch `codex/e02-unified-local-20261009`, HEAD `691b0082846279f318c54a8e5618807a0d810698`, tree `eb4ab69bf76126a07a9585755aba68b7197ea75f`; source frame `root-author-source-frame-r1210-20261013.json` SHA-256 `31687de984b4625c20d358d57b031ef44c6fff5c03e38095655ef23f2e8c1779` (575 paths reported by that frame).

The only target is `tests/unit/runtime/quality/test_joint_simulation_horizon.py`. Its current bytes match the R1185/R1224 preimage SHA-256 `70a46ab90e9a6cd37221136aa95ea213275ed3639797414340dccfffeb04919f`. I reconstructed both virtual postimages in memory from that preimage: the previously reviewed R1185 semantic postimage is `178ab34ce960f8012d8a10306a3f1f6122b7934eea60bfdfbd638c2562eb97cc`; the R1224 root-formatted postimage is `11044da8d366bb630a4576530d485c4d72a5686b422e673c78f65fdc6e14847d`.

## Equivalence and quality evidence

The full-file ASTs compare equal with type comments enabled. Type-ignore tags and line positions also match, and the significant token stream (including comments) is identical. Thus R1224 changes layout only relative to the approved R1185 postimage.

The final virtual file retains the ordered fallback test with incompatible-first/later-compatible and compatible-first/short-circuit cases, the persisted-result and fresh `load_joint_simulation_result` comparisons, the all-candidates-rejected persisted refusal control, and the sibling shared-slot conflict test that asserts execution was not called. These are present in the same AST-equivalent final postimage reviewed semantically in R1199.

The root quality receipt `root-quality-r1093.json` (SHA-256 `06cce5e52f0a651a6d31c9b2e6f85e87881ad4825fea7f5bc0d46c02ee34e7ff`) records configured Ruff 0.14.10 `check` and `format --check` both exiting 0 for the exact postimage, each with `--stdin-filename tests/unit/runtime/quality/test_joint_simulation_horizon.py`. I verified the receipt metadata and bound postimage hash; I did not rerun Ruff or pytest.

## Scope

This review is limited to R1224's test-only style delta. Prior R1199 semantic review is `GO_SCOPED_NATIVE`, not a native execution receipt. The separate ABM2/R1214 workstream is not part of this test-one style disposition. No test/runtime replay, production source change, G adjudication, or capability closure is claimed. P40 remains the already-reviewed fallback-selection class; the style-only delta introduces no new semantic finding. `closure_ids=[]`.
