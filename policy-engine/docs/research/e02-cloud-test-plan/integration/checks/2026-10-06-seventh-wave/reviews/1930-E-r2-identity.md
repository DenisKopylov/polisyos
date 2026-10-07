# E PR38r2 identity/transport review

**Disposition: identity and footprint GO, bounded to this exact continuation; no new product-source review is needed for the delta.** This does not accept historical code outside the reviewed unchanged source pins and does not close E findings.

## Immutable refs and ancestry

- Fetched topic `origin/codex/e02-E-continuation-20261006` = `e9cb425e4dfe888720f93eb84f1667f24a8a92c4`, tree `d884554723bb66e83f5df467fc95766fd90f7bda`. The committed primary handoff is `.../implementation-handoffs/E/continuation-20261006/pr38-r2/final-handoff-v2.json` (22,960 bytes, SHA-256 `b2745a726ffa29e6b56f2ec8dafa96ee8a86d0a978f96f1693e5bd78a0892bd2`); its README is 8,787 bytes, SHA-256 `bf90b8d42699c9ceaa21e1ba9d353b18b5d5afca07edf45a666d4aa986d240da`.
- `7dad1566e9bd289aa1385b149bfcb0bfaef60bf1` is an ancestor. The handoff pins original base `198076863e143dea9f89f02734b13d50dae3eed5` / tree `2b754a92c27959e2e747738d47ed0b419f3b6dd8`, numerical candidate `a9f78817c873be5b35a08155f2593b229d9fdbb6` / tree `c02e043c3e1c8222c28aa71187fa8db4e2fdeea7`, wave `ddcdfd9c220ba57e37c8abf52b976a7184c384f9`, and all-54 checkpoint `9954f394b470961d9e144a557f3cefeb9e0a67b6`.
- G HEAD `127dc7ab8365d29eb656fe32c0c894f6cc971286` is the second parent of a9 and an ancestor of e9. E can be transported append-only from G by ancestry; no rewrite is needed. The evidence sequence after numerical candidate a9 is `ddcdfd9` (wave), `9954f39` (all-54), then `e9cb425` (final handoff); only the last commit follows the all-54 checkpoint.

## Complete delta footprint and carry-forward

- `7dad..a9`: 139 paths (4 modified, 135 added): no `policy-engine/src` paths, one test path, 138 documentation/evidence paths. The sole test, `tests/unit/remediation/test_req_01_installed.py`, has identical blob `c05a7da95fffb1e4dc2550d11f7a33dfaab8ea89` at G `127dc7` and e9; it is already in G checkpoint11, not new E code.
- `a9..e9`: 335 added paths, all under the E PR38r2 handoff directory; zero product-source or `tests/` paths. The additions are closeout/publication/review companions, including handoff scripts/output; no canonical product writer changed. Thus `7dad..e9` has 474 paths overall (4 modified, 470 added), with zero product-source changes and only the already-G checkpoint11 test above.
- DoE source and its relevant tests are byte-identical at reviewed `70c4a14`, a9, and e9: `designs.py` blob `3596f6b9…`, `sampling.py` `a6487dd0…`, `analysis.py` `964c3c59…`, `morris_geometry.py` `8e75b7d9…`, `test_plan_runtime_admission.py` `6cdb769e…`, `test_morris_geometry.py` `a6ca3948…`. The prior Morris analysis residual recorded in `R/1920-Morris-independent.md` therefore carries forward unchanged; this docs-only publication does not repair it.

## Evidence roles, dispositions, and denominator

- Handoff state is `READY_REVIEWED_HANDOFF_NUMERICAL_HOLD_GLOBAL_FAIL_FINDING_PROPOSALS`, not a green full closeout. Frozen outputs remain 1,445 cases = 1,441 PASS / 4 FAIL / 0 ERROR / 0 SKIP; six numeric groups PASS and one FAIL; seven global gates FAIL. Ledger remains 49 partial / 4 held / 1 closed, with no finding updates. These are explicit limitations, not new failures introduced by the three docs commits.
- Publication custody distinguishes eight review records: six candidate-Git and two external-content-bound. The typed carrier is 7,951 bytes; the independent adapter binds the two external reviews. Canonical collector v4 validates only the six Git records, so it must not be cited as independently validating the external pair. Custody/`COMPLETE_BOUND` is not a numeric PASS or finding closure.
- Copy counts have distinct denominators: first-wave authoritative copies = 213 / 13,321,867 bytes (README and `corrected-wave-publication-validation.json`); final 54-record publication adds 18 / 3,617,955 bytes, giving independently verified total 231 / 16,939,822 bytes (`final-publication-independent/READY.json` and 231-element verified index). The 248 publication paths (228 + 20) are a path-footprint count, not copy records. I found no exact “308 copies/records” claim in the primary handoff, its final-publication review/READY/index, or validation; 308 remains unreconciled without the separate audit and its denominator.

No tests were run for this identity-only review. No refs, tracked files, or source were changed. This report is ignored under `policy-engine/.gitignore` (`_build/`).
