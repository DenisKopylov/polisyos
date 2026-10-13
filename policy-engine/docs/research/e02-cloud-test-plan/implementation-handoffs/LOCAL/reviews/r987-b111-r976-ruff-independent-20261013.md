# R987 — Independent delta review of R976 B111 Ruff companion

**Verdict: GO for the root’s focused native replay of this test-only candidate. This does not close B111; `closure_ids=[]`.**

## Source and packet identity

This review is qualified to branch `codex/e02-unified-local-20261009`, HEAD `dae174623baca79449638758ada159ab7ebdaefb`, tree/index `0e7846a9576e698150de7e613d424dc72d5dd43a`, and current root frame `root-author-source-frame-r979-20261013.json` (`c6a383910bad5f1ccb7ed4b6d017d5d6f6b2447bda86d605b3837816577e114c`). The relevant test path is still the R948 preimage (`5acc212f70d5bf9f908a9f1651f7de39f7eb189c12e7f333f75c20057d77b24d`, 35,323 bytes); `pareto.py` remains `a17a8590e44a445a54f3649564f675514c6f2468ce2b6cad5de40ceb913a2716` (28,861 bytes). Both hashes agree with the current frame’s postimages.

R976 cumulative patch SHA-256 is `c5950a8faa1996192790db99d3918fda39689434de12ff54e89218f949305941`; its delta from R954 is `cc6277022a46240ab63f79b3aae9b5ffcf1ae3cb5c1733ed366dea4412ea6db9`. The R976 manifest is `359657d53862dab60b51568c9d9ab5bfb9cbf28252978aeebd7206bda3bfa2b5`, and the virtual postimage is `e35c95f7c5e12db1e5d81e9767cf096f40b48a16d940e67646a946f04ea7df46` (36,439 bytes). R963’s prior independent review and its C420 block are pinned at Markdown SHA-256 `80ddc0973cd74ee53df6656c4f8a18c1f660f9fbc562cd8bf76a4f4148f1d34c` and JSON SHA-256 `187835d9a33430acda00ef3bf66783d807be002405ffeb05389c5f0e3fd77836`.

## Delta review

The exact R976 delta from R954 changes only the two helper-call line wraps to Ruff’s formatted form and replaces the constant-valued reference-point comprehension with `dict.fromkeys(coordinate_ids, -1.0e308)`. It does not change imports, assertions, error expectations, or the existing wrong-key negative control.

The semantic basis from R954 remains intact. `coordinate_ids` come from a produced front’s complete typed coordinate schema, not from metric labels. The producer’s schema rejects duplicate coordinate IDs. For the same ordered sequence of string keys and the same immutable finite float constant, `dict.fromkeys` produces the same key/value mapping and insertion order as the comprehension. The wrong-key `{"acc", "speed"}` refusal remains separately asserted, while the negative-infinity and overflowing-finite cases still use the producer-derived coordinate IDs. This fixes R963’s C420 without weakening the test oracle or a production predicate.

P40 bucket: **NEW tooling/lint-conformance defect**, distinct from R954’s semantic field-basis defect. R976 widens the correction across the full virtual test file by formatting the adjacent helper calls along with replacing the flagged expression.

## Independent checks and limits

I confirmed the cumulative patch applies in dry-run mode and reconstructed its postimage to the declared SHA-256. On that exact virtual candidate, configured Ruff check and format check both pass when run from the declared `policy-engine/` cwd with `ruff.toml` and the repository-relative test filename. Ruff check prints “All checks passed!”; format check exits 0 with no output.

One initial independent Ruff invocation from the repository root reported I001. That invocation used a different cwd/config-resolution context than the packet’s declared command; rerunning with the recorded `policy-engine/` cwd passed. The noncanonical invocation is not used as the candidate’s deciding check.

No pytest, product imports, runtime execution, or source/Git writes were performed. The root’s focused native test replay is still required. The broader B111 criterion remains not adjudicated: this candidate covers the numeric hypervolume controls, not the entire status, persistence, denominator, registry, and consumer property. `closure_ids=[]`.
