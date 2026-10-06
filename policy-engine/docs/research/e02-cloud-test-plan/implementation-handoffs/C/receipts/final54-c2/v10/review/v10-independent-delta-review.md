# Independent final C54 v10 delta review

**Scope.** Reviewed only the v10 delta requested: canonicalized source-input locators/replayability and the generic declared-verdict-summary consistency check. This is not a fresh semantic review of all 54 rows.

## Immutable cut and source replay

- JSON: `C54-final-20261006-v10.json`, SHA-256 `38db6cac4195f210425502bd4c7fdf2884ccdb5ae42ef87170d17020a6358dcc` (322,414 bytes).
- Markdown: `C54-final-20261006-v10.md`, SHA-256 `be86d1688acde9d3589536ab8ea2518fe2c65899bf25254743792dffe5ef4fd8` (176,581 bytes).
- Compared with the preserved v9 cut, all top-level content outside `input_receipts` is byte-semantically identical, including all 54 rows and verdicts. The v10 input fields point the inventory and reviewed source archive at canonical package paths, retain separate raw-capture provenance, and record the decompressed source hash.
- Source replay through `build_c54_final_adjudicated.py` exited 0 and regenerated both exact v10 outputs. Generator stdout SHA-256 `55a7533556d2a4eaeb36ad3aa62f6a0dc344fbc9fa12a48c2471403f1f0275d8`. It verified the gzip SHA `aa8c96a3dbf38874c750cf0dfdfc94de9be93925dee5ac193a2b37d595579639`, decompressed source SHA `8636e42db8fda1bb9df617cf718ae7e20d39eb11b40639d5ee6471a28160871a`, inventory SHA `530f61eb0c356a9aa65b99154b233b19aadc09bde3f8f307a85a1f27965d16da`, pinned source commit/tree `48af851db5c0e802c92d9b30226acbc4436c69ba` / `84b6416c9cc84a975ceb2d5d4cd5a8a4f6b3d9e2`, pinned base commit/tree `198076863e143dea9f89f02734b13d50dae3eed5` / `2b754a92c27959e2e747738d47ed0b419f3b6dd8`, and R210 manifest SHA `de65e06eb5b03268d5a4b8b6592660be15fb7fb21d77e0ebec0ab88e6e8f00e2`. The generator explicitly reads pinned commits and checks the base ancestry; it does not bind to caller `HEAD`.

## Generic count-alias control

The canonical validator (`validate_c54_final_bookkeeping.py`, SHA-256 `2007b122baf8c14ae4c52c678156bf09cae716909c8e95561d2119d38e227a33`) passes the exact cut. It derives row verdict counts and recursively discovers every nested integer map whose keys are among the allowed verdict labels. The current two aliases are `/final_verdict_counts_derived_from_all_54_rows` and `/final_adjudication/counts`; both match the 54-row result of 31 closed, 9 limited, 14 held.

A copy-only negative control changed only `/final_adjudication/counts/closed` from 31 to 30 and ran without the whole-cut SHA pin. The validator exited 1 with `declared verdict summary differs from the complete row set` at that pointer. The mutated copy SHA is `9f39d9e239563f5a5c6aef00db9c64e0ab96926745a0460faba6daf1ee10ffcd`; stderr SHA is `25fa9197c311adfea6735020a10af34537a811f01af80abfab96fb900cdf68bb`.

This was the same summary-binding consistency class one level deeper (P40), not a new product defect. The generic alias discovery plus mutation control closes this delta.

## Validator result and boundary

Canonical checker exit 0/stdout SHA-256 `ef9a01fa01a8afbb8396e31cf77156acc2307600804898247d85982ef0157d52` confirms 33 C bundles, 54 findings, 59 criteria, 210 receipt entries, 282 resolved RFC 6901 pointers, and 31/9/14 final verdicts. It validates source line spans and hashes, receipt locators/tree/blob/size/hash, the 7-file R210 nested manifest, historical-state rows, and the current Markdown denominator. No semantic row/verdict changes appeared in v10.

The canonical gzip and TSV files exist at the package paths with the declared hashes, and the generator replay used them. At review time, the package files were still untracked in this worktree (`git status` showed the final C package as `??`); therefore this review confirms the candidate package and exact bytes, not post-commit branch readback. Root must commit the package and verify the final branch tree before reporting it delivered.

## Preserved evidence

- Exact validator output: `canonical-validator-final.stdout.json` (SHA-256 `ef9a01fa01a8afbb8396e31cf77156acc2307600804898247d85982ef0157d52`); stderr is empty.
- Count-control mutated JSON and full failure traceback: `final-adjudication-count-drift.json` and `final-adjudication-count-drift.stderr.txt`.
- Exact generator replay output: `../final54-review-v9/source-replay-v10/generator.stdout.json`, generated JSON/Markdown, and empty stderr.
