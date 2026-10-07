Original local scratch locators in this review refer to the ignored `R/watch-20261007-2256/native-A` directory. Its recomputable harness/cleanup inventories remain local; complete deciding raw receipts are published under `outputs/native`, `outputs/api-check`, and `outputs/api-render`.

# Native-A harness review and cleanup intent

**Disposition:** attempt3 is a mixed, non-green result. Preserve the runner’s raw `ERROR_SOURCE_AFTER`, the 33 actual JUnit passes, and the one raw JUnit assertion failure. Independent read-only diagnosis classifies that single failure as LEX-input-limited: `build_credal_reference` could not obtain the required LEX input, so the served property is **UNRUN**, not established as a product bug.

## Attempts and current outcome

- The initial attempt stopped before pytest on the old prep-v1/v2 schema mismatch.
- Attempt2 passed the v2 prep and source-integrity gates, checked all 7,499 selected rows (165,980,819 bytes) and the origin audit, then correctly returned `ERROR_EMPTY_TEST_RUN` because the second compatibility selector referenced the wrong test file.
- Attempt3 used the corrected 18 selectors and collected 34 cases: 33 passed, one failed, none skipped. The raw failure is `test_served_candidate_value_fresh_get_with_candidate_only_substrate`, which expected a completed control job and observed `state=failed` / `_terminal_status=error`. The input attempt through `build_credal_reference` establishes that LEX was unavailable; therefore the served property is UNRUN/input-limited. Keep the raw JUnit failure, without diagnosing a product bug.
- Attempt3’s origin audit passed for 1,822 file modules and 9 namespace modules, with zero foreign origins.

## Harness and source-after assessment

The initial prep-schema and source-fidelity-name mismatches are corrected in the current runner. Actual source, architecture, per-file blob/mode, supplement, and attempt-1 preservation checks remain in place. Attempt3’s pre-run export passed. After pytest, the runner found nine extra `root.lock` files under candidate-local `.polisyos` and `.tmp` runtime paths and correctly recorded `ERROR_SOURCE_AFTER`.

These files do not contain source, CAS records, or input data. The exact writer in `polisyos/core/artifacts/ownership.py` initializes the transaction root with `AtomicFileWriter.write_once(root_lock_path, b"")`; lock acquisition opens that file and uses `fcntl.flock`. All nine observed extras have zero bytes, the SHA-256 of empty bytes, and zero allocated blocks. This is a real harness boundary defect: runtime coordination metadata escaped into the source export despite the “all test outputs outside” promise. It does not mean product source changed. All 7,499 manifest rows still match their Git blobs/modes, no expected rows are missing, and the full source subtree matches the pinned candidate tree.

Keep both conclusions. The raw `ERROR_SOURCE_AFTER` remains valid as an isolation finding, while it does not erase the 33 JUnit passes. The one raw assertion failure also remains in the receipt, but its served-property result is UNRUN because the required LEX input was unavailable. Do not rerun this wave; the separate API/negative slot is reserved.

## Production-data and provenance boundary

The manifest has zero `production_data` path-component entries and zero symlinks. Selected tests refer to production catalogs only through candidate-root missing-catalog checks and typed `repo://` references for unavailable data; static review found no production payload read. The environment removes `DATA`/`PROD` and credential-like variables, and the origin guard removes the live G editable roots. This is a path/origin guard rather than an OS filesystem sandbox.

## Native-Trash intent (no move performed)

The only proposed target is `policy-engine/_build/e02-g-continuation-20261006/R/watch-20261007-2256/native-A/candidate`. It is reproducible from the pinned candidate SHA/tree and protected by the local intake ref and published A delivery ref. The full source manifest, prep record, harness, and attempt receipts/JUnit/stdout/stderr/origin audit remain outside the target. Its recorded size was 178,996 KiB by `du -sk` (manifest payload 165,980,819 bytes); parent must refresh directory identity and handles before any future action.

**Current state: cleanup intent prepared; no move performed.** The parent reports that the separate API/negative slot is released. Fifteen generated candidate extras (12 empty lock files and three CAS outputs, 753 bytes total) were copied with their exact relative paths, hashes, and modes to `results/preserved-generated/`; see `preserved-generated-manifest.json`. API Python receipt remains `ERROR_SOURCE_AFTER`; the later API rendering receipt is `PASS` and confirms candidate extras unchanged and source integrity. Parent may move only this reproducible source export to native Trash after committing and remotely reading back the required proof, then performing fresh identity, handle, refs, and receipts checks. Same-volume Trash does not itself reclaim disk space; never empty it. No move or permanent deletion was performed.

The machine-readable evidence, exact nine lock paths, per-file identity data, attempt hashes, and cleanup intent are in the raw `outputs/native/receipt.json` and `outputs/api-check/receipt.json` (the local recomputable harness inventory/cleanup intent remains ignored).
