# Final plan retrieval and native docs delta review

Read-only static review on the current candidate checkout. No plan builder, tests, Git operation, or heavyweight work was run.

## Inputs read

- Final primary plan: `LOCAL/r4-workload/composed-mac-final-replay-plan-20261010-r2.json` — SHA-256 `ceff2fd9dc3f8706117e86f63a05ffc1e945958174717e4279ca65ecc8e58ed4`.
- Final supplement: `LOCAL/r4-workload/composed-mac-final-supplement-plan-20261010-r2.json` — SHA-256 `d1187408584f427a25dcb04ef62ea528756dd537ac62fcd9c207aad873c8cd02`.
- External consumer plan: `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` — SHA-256 `b3a9c247a7ae894035b81d334e16233de8c51ac2795567bcd9930b15c4d24c33`.
- Existing caller: `LOCAL/raw/prepare_final_wave_manifest.py` — SHA-256 `bf29fcee75c3234bb150368d77b36c67dd5a0c5716ff9cd62b55a1e4f4298ab0`.
- Manifest and supplement normalization source: `LOCAL/raw/composed_mac_capture.py` — SHA-256 `9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81`.
- Native closeout runner: `tools/devx/workspace/repository_sota_closeout.py` — SHA-256 `026fbd624e9e56cbb12f5dc59a7d2929cffca196e1272736c19e43daa9e32248`.
- Docs baseline evaluator: `tools/lib/docs_freshness.py` — SHA-256 `d902f2cca072a8c94b82c7c6e1eb14b924b42330fc39af34e9609eff1a81636a`.
- Current docs baseline: `architecture/exceptions/docs_freshness.toml` — SHA-256 `aaea4ef9cfa72d3e2b6a80c70f62ed91e0e33b03514568ffc0c1a1e8e1cc2bfe`.

## C05 supplement delta

The supplement is still `plan_only_not_receipt` with 11 commands. In `I1_C05_MATERIAL_CURRENTNESS_AND_PROFILE_CONSUMERS`, the selected module `tests/unit/data_forge/read_api/test_catalog_graph_builders.py` occurs once in `argv` and once in `selected_targets`; the normalizer requires those two lists to match exactly (`composed_mac_capture.py:1988–2005`). The path exists as a regular file (1,574 bytes), SHA-256 `6493a8ecfe49e718839387940aadea42d4c0c38b594425291b4fb8009dbaa343`.

This is included in the actual input derivation, not just the plan's description: supplement normalization derives `freeze_input_manifest.selected_test_paths` from pytest argv (`composed_mac_capture.py:1996–2005, 2028–2054`); `declared_local_source_paths` includes selected tests (`:1163–1184`); and `create_raw_source_manifest` consumes those declared paths for each explicit plan (`:1264–1318`). The selected test is therefore represented in both the execution selection and the planned source scan. The new selection remains `UNRUN`; this review does not claim test results.

## Native docs command semantics

The external plan keeps the named docs command as `uv run polisyos-tools validation check-docs-accuracy --repo-root .`; the current output bindings are all under its dedicated `tools/docs-accuracy/` directory (stdout, stderr, metadata; no JUnit). The corrected purpose describes the zero-count/past-date behavior without changing that route. The external plan remains an output-binding plan and `UNRUN`, not an execution receipt.

The ordinal claim is source-confirmed: `_run_fail_closed_subprocess_gates` declares and runs 17 commands in its `commands` list, then calls `_run_docs_freshness_gate` (`repository_sota_closeout.py:1350–1559`), making docs freshness the 18th child. The current baseline has `expires = "2026-06-30"` and `expected_violation_count = 0`. `_docs_freshness_contract_findings` only adds an expired-baseline finding when the expected count is not zero (`docs_freshness.py:47–54`); `_run_docs_freshness_gate` proceeds for expected count zero and invokes the validator (`repository_sota_closeout.py:1652–1687`). Its zero-count observation branch reports a failed check or nonzero observed violations, but does not add a baseline-expiry finding (`docs_freshness.py:77–96`). Thus the date is past, the existing zero-count route still runs, and its semantics match the corrected purpose. This does not establish that the command has run on the final frozen source.

## Manifest caller boundary

The existing caller accepts one `--plan` and repeated `--additional-plan` values. It rejects symlinked plan components and duplicate resolved paths, hashes every named plan before and after, passes the explicit plan list to `prepare_raw_source_manifest`, and verifies the resulting manifest readback. It does not hard-code or enforce a six-plan count; the final invocation must provide all six intended plans explicitly. No prepared manifest or final source freeze was produced in this review.

## Verdict and limits

GO for the two plan deltas reviewed: the added C05 test path is wired into both pytest selection and source-input derivation, and the docs-purpose correction is consistent with the actual 17-plus-one closeout sequence and zero-count evaluator. Keep the C12 real E5-to-HTTP positive witness marked UNRUN until its approved final-source execution. This is a static plan/source check, not a final freeze, runtime receipt, or production currentness claim.
