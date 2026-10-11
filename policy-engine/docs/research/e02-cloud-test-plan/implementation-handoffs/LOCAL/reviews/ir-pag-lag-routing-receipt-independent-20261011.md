# Independent receipt-integrity review: IR PAG lag routing

## Verdict

**GO for a separate receipt commit, with the recorded scientific and runtime limits preserved.** The protected receipt binds to the source commit and remote readback, its three selected path hashes match the present files, and its focused test counts agree with the retained command and JUnit. This remains a source-worktree run, not installed-profile evidence or a temporal-PAG closure.

## Protected record and source binding

- Protected record: `LOCAL/ir-pag-lag-routing.json`, SHA-256 `71845738a114477db48912ddebaaac9a777c28f835856753a60f706d353c5401`.
- Source checkpoint: commit `8c42e13b76e13c0d1f81ab3b2b3e974c9e2cdf71`, tree `e1e4833c523f65dc07a8a9f751e8b08ae34dd460`, parent `e038ab5701f59841a0b30229e8edfcd8e303b64c`, on `origin/codex/e02-unified-local-20261009`. Local readback `LOCAL/raw/ir-pag-lag-source-checkpoint-20261011/readback.json` has SHA-256 `2dd003fc53434617cb80780b5ceb026d0cbc23ff0b1204ee5c805ec281c8ca3e`; remote readback `.../remote-readback.json` has SHA-256 `90200c6fe5dd8e626bac42e11548275e0f8723201de24a17cfda17ebb5489b52`. Both agree on commit, tree, and parent. Selected-footprint receipt `.../selected-footprint.json` has SHA-256 `cad8aa9a146aa4b385d8ef9e27d8796a10891614cfa159bbaeb6087c2820666d`.
- The three bound paths and current hashes are `src/polisyos/ir/analytics/causal_graph.py` (`270b6bdc2665256c4a28bc41a0597e19bee7c18dd14bbc434bfcf9091dad5f8a`), `tests/unit/ir/test_causal_graph_contract.py` (`ef692a674e5a934674e8d980975d79368c8a90a8a947e9fa3f0cf3022320d360`), and `tests/unit/foundry/methods/catalog/causal/test_discovery_reconciliation_limitations.py` (`22c2f446266127d2d7f7cee9a86ed07733bc3c0006aab0fe518ea271505b0e70`). All match the receipt's candidate hashes and commit readback. The last test's proposal had one extra empty EOF line; the receipt references the normalization record `LOCAL/raw/ir-pag-lag-controls-application-20261011/trailing-eof-whitespace-normalization.json` (`366c1f884a06844b4bcad58f5a51ee41b36088b3391ea4317f6fe8c0aece4a61`), which records that the test body was unchanged.

## Run evidence and current boundary

The combined command is `LOCAL/raw/batched-blocking-focused-20261010/promotion-two-current-refusals-and-ir-lag-routing-20261011/command.json`, SHA-256 `b558b19452fe5cd33f4d5a70d3a3e48217ef7c2fba8de32bc864ce603a9d0fce`. Its stdout hash is `3e976b655a27bb74489b50c9202231ec5269243f3aab2c2598afa8110fc95043`, stderr is empty, and JUnit hash is `1e640013008df61d6746e875098188392874fea71a09c0e2fefe941e9f216a2a`. JUnit reconciles to 48 passed, 0 failed, 0 errors, 0 skipped: 37 causal-graph contract tests and 9 discovery reconciliation tests, plus the 2 promotion selectors from the companion receipt. The command ran at `55ed8863a8cad50c8189dd9309f0a87e8761016b` with the worktree Python and `PYTHONPATH=src:.`; it records 6,160 input paths stable before and after. The command HEAD is neither the IR source commit `8c42…` nor the present audit HEAD `785944776c39722923c3a34d4ab7a3594dc03287`. Later S3 worktree edits were not part of this captured run. No installed-profile, full repository, or post-S3 rerun is claimed.

The implementation evidence is accurately bounded: it exercises the unordered endpoint-pair guard for mixed lagged/contemporaneous adjacency rows and a real discovery producer-to-persisted-report-to-fresh-reader route that preserves the static identification consumer's typed refusal for positive lag. The seeded VAR is a routing witness, not proof of a contemporaneous causal effect or temporal-PAG law.

The receipt leaves `formal_closures` empty. It records B218 as partial; B219 and B220 as no evidence; the temporal-PAG profile/consumer as `absent_unallocated`; and the external surface as `out_of_scope`. Those qualifications agree with the demonstrated chain and avoid inflating the run into a universal or installed capability claim.

## Pattern pass

Relevant register rows are P29 (real producer and persisted consumer evidence), P38 (distinguish static pair admission from temporal-PAG law), and P41 (the run's actual source base and environment). The receipt names the property tested, the source run, and the unallocated temporal consumer instead of treating a passing test count as a broader closure.
