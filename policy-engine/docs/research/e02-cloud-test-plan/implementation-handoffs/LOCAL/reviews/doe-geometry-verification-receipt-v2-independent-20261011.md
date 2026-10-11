# Independent delta review: DOE verification receipt v2

**Disposition: GO for the corrected, bounded source and verification receipt.** This delta review compares v2 with the retained command records and source readbacks. It does not rerun tests or imports. GO applies to receipt accuracy and the stated focused checks only; it is not a whole-native-gate pass or finding closure.

## Delta from v1

V2 is LOCAL/doe-geometry-deferred-edge-verification-v2.json, SHA-256 01df3d6009a595b26a30e8688773a7c88756186628169e8c5ce06b490f845b4f. V1 remains unchanged at 81359e93e93c25110ba2cae4fc067b88cb4484f7a4369bcaf98a2c9d7a9d7ade. V2 corrects the source branch to codex/e02-unified-local-20261009 and explains the 3f01 → d7 / 6776 → f701 sequence using the retained I001 and blank-line readbacks. It recognizes 3f01 as the actual original patch postimage captured by the 133-test run. It does not characterize that source as missing, unreproduced, or semantically unknown.

The per-command binding now distinguishes the 133-test original-patch run from the final-source checks: only stability.py matches final bytes in the first run; geometry.py, the import-boundary test, and stability.py all match final bytes in the 26-test run and Ruff check. The v2 limitation explicitly says the 133 selectors were not rerun together on the final import-order bytes. This resolves the material v1 metadata error without overstating the combined receipts.

## Readback and deciding receipts

Candidate bba2140a4ed71276e01e999fb0f7f634a4e147aa (tree a068273c0782d8a0ec06f441d5f442c70ea0e3e6, parent 702a206d82d573b77fa6614f7a3e80231bf75c12) is an ancestor of current HEAD edf9bbac35635727a500dad8bcc30ab5f6bfc13c (tree 4414307d06261987720aba50f558f9d426bf7a56). The DOE source paths remain unchanged at current HEAD. Their final SHA-256 values match the source checkpoint and remote readback: geometry d7f74707c58196860f6fcc9275e17a6619e0caed638b2ee5cc8a23d859d9c82d; stability 7fd7e45f609235578c1da873a638c7704dc370b4944b68b6e66f50bb60979a0b; import-boundary test f7016515b60de100ded2b3291d7cc58dc752944ca052000cd6ca55f93d4700fb. The remote readback records the same candidate tree and all three hashes.

- The original-patch command record is SHA-256 8075772d29ec8cb50500eb79d2bc857b3540ff52936d48bb79b27d1d3bebd496. It exited 0 in 33.189 seconds; JUnit reports 133 passed, no failures/errors/skips, and 3 warnings. Its 6,164-entry before/after inventory is unchanged. The source snapshot binds geometry 3f01bcbca1… and test 6776e1af… to the original patch, with stability 7fd7e45f… already matching final. The full command outputs and 711 fixture files are retained in the cited raw directory.
- The final-source focused command record is SHA-256 76b13013e763364f1b7a8cb5cf40ab95706fa61e2dbe8cd475795c6af0efabbb. It exited 0 in 3.670 seconds; JUnit reports 26 passed, no failures/errors/skips, and 1 warning. Its changed-path snapshot matches all three final candidate hashes; the 6,164-entry before/after inventory is unchanged. stdout, stderr, and JUnit are retained.
- The final-source Ruff command record is SHA-256 eb1f87e81d972bde1fbc5c29f9a70ffbc62f42a8959d1e41979626fce5b1113a. It exited 0 in 0.04257 seconds with seven targets and zero diagnostics; all three DOE paths bind to final hashes. JSON stdout and stderr are retained. This is Ruff check evidence, not a format check.

V2 records that import-alias multiset, non-import AST, and comment comparisons between the original patch and final geometry/test bytes are equal. This supports the bounded staged account; it does not convert the 133-test run into a final-source rerun. I did not independently rerun those comparisons.

## Limits retained

V2 leaves whole_native_gate.status as UNRUN_AFTER_REPAIR, has no closure IDs, and does not classify the historical SCC/dispatch findings as inherited. Those limits are correct. No full-native-gate result, scientific capability claim, or formal closure is established by these receipts.

