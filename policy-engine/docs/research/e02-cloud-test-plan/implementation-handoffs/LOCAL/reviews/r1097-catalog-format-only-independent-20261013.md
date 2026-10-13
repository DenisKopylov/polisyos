# R1097 — independent review of the R1096 Catalog format-only delta

## Verdict

**GO for Root to apply this formatting-only delta and retain the Catalog test in the native replay.** This review leaves the R1073 behavioral verdict unchanged. It grants no capability closure or finding adjudication (`closure_ids=[]`).

## Exact delta and source boundary

The reviewed packet is `LOCAL/raw/r1096-catalog-target-format-only-20261013/`. Its manifest SHA-256 is `380cfbc61aff73a3c4d9c9a47a87019a30c34308963c0b5ba8029be113b629f5`; its delta patch is `e3d3b740fa2ba2fc8009fed24cebd7083d3ea00415b664cb34f78049c87ed320`. The preimage SHA-256 `c41f621399327f613970a9cf0c8b11bd87f3afa05bb3b01d240c31e97123a183` is exactly the R4/R1073 candidate; the postimage SHA-256 is `5638893c19a12ade9148cf8230c16d9e0def437f44fe1e1023ab72491a23367a`.

The patch changes only line wrapping for three existing assertions: the positive-path source-warning check, the test-local overlay-path lambda, and the stale-source warning check. It changes no imports, conditions, values, fixture setup, API calls, or assertions. Standard-library parsing yields equal full ASTs (without location attributes), and Ruff's formatter output for the preimage is byte-for-byte the supplied postimage. The target product test file is currently absent from the checkout; this review did not apply the candidate or patch.

Current source is branch `codex/e02-unified-local-20261009`, HEAD `9511169e1a7f6dbd4137de824905dfbff8992a3f`, tree `d6d48c83b5a60afdead8066253bc30cd216f5913`. I bound the R4 34-Python-input denominator to `root-author-source-frame-r1094-20261013.json` (SHA-256 `948808a5976991e620887ffdccaf20dbab38c2739006f265d092e260d142a7df`): 27 inputs match HEAD and seven match current frame postimages, with zero mismatches. The R1078 fixture-scope change is represented by that frame; it does not alter the three-line candidate delta.

## Static verification

Read-only checks against the stored pre/post artifacts produced:

- Ruff check on the postimage: exit 0, JSON `[]`.
- Ruff format check on the postimage: exit 0.
- Ruff format check on the preimage: exit 1 (the original formatting defect).
- Ruff formatter on the preimage: output exactly equals the postimage.
- Full AST comparison: equal.

No pytest, runtime imports, database access, or source/test writes were performed. The R1073 public HTTP behavior remains **UNRUN** until Root's native wave; formatting evidence does not change that status. Keep the R1073 limit that the HTTP stale case does not pin the exact `excluded_present` refusal reason, and retain the existing lower-level coverage controls in that wave.
