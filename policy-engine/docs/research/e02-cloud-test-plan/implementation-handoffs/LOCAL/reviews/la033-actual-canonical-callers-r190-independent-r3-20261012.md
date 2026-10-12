# Independent delta review — LA-033 actual canonical callers r190

**Verdict:** GO to commit the six-path internal caller/documentation change. No substantive source or behavior defect was found in the reviewed delta. This does not close LA-033: whole-item status remains LIMITED / NOT ADJUDICATED, capability verification_missing, closure_ids=[].

## Bound change and readback

The root application composes the frozen r2 candidate patch (SHA-256 fa55dd789de4af1f7ca90c538b4ab3f8c946bdb34767f7f130ab72f4bb3e6a0c) onto its e635 virtual base. The composition receipt is LOCAL/raw/la033-root-canonical-callers-composition-r187-20261012/composition.json (SHA-256 c73f477e63ee02de8cd1cd3984aee358f78a05a485a3d2b7fc3e0cf3e45edee8), with net patch 61a03af0912531cb78d79eeb6104e2e9f802c7cffac10cdb6b924ea33b74fcf3 and application readback 3996cb18d0ebe5a22f80aa8a25ba0e9ab2452354f322777d721e969ee264f189.

The only follow-up delta, R189, reorders the new canonical imports in three of those same test files to satisfy Ruff’s import ordering. Its patch SHA-256 is 8633eb8bb54cb499deb28ccddcec591f3edd6802e1dcebb4215eaf14a7c9a854; readback SHA-256 is 45cc1523649f3c39b780b20ffee41f6c672b1b9d4fa304b284ae1affaa097db3. I verified each R189 preimage equals the corresponding R187 virtual postimage, and each final six-path worktree file matches the final SHA-256 in the root readbacks. Current HEAD remains ce60ac7ff4e8cf999866e2f94e86f0314e98b464, tree 60aa02e83c62b8335e5bf1317feaf06a5da97d3f; the index is empty. The change remains exactly five test import relocations plus the Runtime README ownership correction.

Independent AST comparison against the pinned e635 preimages confirms, for all five Python files, that the non-import module body is unchanged and the import bindings are equal after normalizing the old module path to the new path. R189 changes only ordering among those imports. No runtime source, API, compatibility shim, dynamic import contract, or benchmark implementation changed.

## Actual test and lint receipts

The actual-source R190 receipt ran six selected test files: the four unit caller files and the two unchanged compatibility-control files. Its JUnit contains 23 passed cases: 3 input-binding tests, 3 replay-runtime tests, 5 backend tests, 1 measurement test, 2 deterministic-compatibility tests, and 9 remediation tests. Pytest reports 22.03 seconds; the captured wall time is 25.643 seconds. The run’s recorded input snapshot contains 6,186 files before and after, with zero hash differences. Full stdout SHA-256 is 3ea33d0c192f482a2cf005ecdbecb394c9bf22e7cd73b559ae3669692afce16c; JUnit SHA-256 is a42c9cbfd61ef15ac13759e46ca7b4449a453a398c80a618c5daae225b08f4e6; command/readback metadata SHA-256 is 11fb9f99f4fd5522b613c078e62821522bf5ea21c061a409319b0207f80ebe3d. The recorded exit code is zero.

R192 ran Ruff on all five changed Python paths, including the C7 integration file; exit code is zero and stdout is an empty diagnostic list (SHA-256 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945). Ruff’s before/after path hashes are unchanged. This verifies import ordering and static lint for C7, not the C7 numerical pipeline.

## Correction to the earlier virtual-suite count

The earlier virtual collector output says 35 passed. That is not 35 distinct candidate test cases. The virtual harness registers a pytest_collect_file collector for each of four Python caller files while pytest’s built-in Python plugin also returns a module collector for each .py file. The hook is multi-result, and the built-in collector returns a normal module. In the retained output, each of those four files is counted exactly twice: 6 versus the actual 3 input-binding tests, 6 versus 3 replay-runtime tests, 10 versus 5 backend tests, and 2 versus 1 measurement test. Those 12 extra cases are duplicate collection of the same file, with the ordinary collector executing the unrewritten source and the custom collector executing the virtual rewrite. The two compatibility files contribute the same 11 cases in both receipts. Thus the virtual total is 24 caller executions plus 11 controls; the actual-source R190 total is 12 caller executions plus 11 controls, or 23. Treat 35 as a duplicated virtual-collector count, not as the actual applied-source result. This corrects my earlier r2 review’s unqualified mention of the 35-pass author run; R190 is the deciding actual-source receipt.

## Remaining LA-033 boundary

R190 did not select the C7 integration test, and no numerical C7 pipeline was run. The tests and imports show that first-party unit consumers and the preserved compatibility controls work on the actual source. They do not prove old persisted CAS import/export/replay/resume byte identity, installed wheel/sdist behavior, zero reflective or external consumers, or that the product compatibility module can be removed.

No G/API-release owner has decided permanent compatibility versus a dated retirement window. The prior local AST census is limited to its declared Python roots and import recognizers; it cannot establish external-use absence. Preserve the old Runtime facade and the current limited/not-adjudicated LA-033 disposition until the lifecycle decision and remaining retained-CAS/install/removal checks are complete.

## Review actions

No tests, lint, or numerical runs were executed by this reviewer. I inspected the frozen patch and R187/R189 deltas, read the R190 JUnit/stdout and R192 Ruff receipts, checked all six current file hashes against their readbacks, and compared the five test module ASTs statically. No source, test, index, or history writes were made.