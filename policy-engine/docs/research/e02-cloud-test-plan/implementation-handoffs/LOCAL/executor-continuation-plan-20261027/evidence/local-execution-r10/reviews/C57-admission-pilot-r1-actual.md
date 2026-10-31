# C57 admission pilot r1: actual-run review

**Verdict: bounded GO for the seven-case pilot's stated admission and SQL-capacity witnesses.** This does not qualify the full C57 change, B56 cancellation semantics, or G/closure.

## Pinned run and source

- Source: `575432f281aeec5dbe89e906cd2545fcd2bc4087`, tree `8107f2cbbdbb39d0861134a0ff5f47b19025ef57`.
- Plan: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/root-ir-transport-composition-20261024-r1/g-native-priority-20261025-r1/deep-task-status-audit-20261027-r1/c57-admission-publication-pilot-r1-20261028.json`, SHA-256 `7aebb07af993f1daa8f2d08b0d60c8a41382b563ebff0bd2bc8a4becb4bf9b8b`.
- Audit: sibling `c57-admission-publication-pilot-r1-20261028/audit-result.json`, SHA-256 `3cf1b5f7cf912ff643611d7d757ef11cd342cf751203dc8f3fc3156221804641`.
- JUnit: sibling `pytest.xml`, SHA-256 `e91e90e17614236e88bae5d0ec022b6d5fef026aeac5cfa37b3681fba18890ba`; stdout SHA-256 `c9fc3925c5063f9f65550a74c02a3aa85a27197abe1e17a3fd4c2b049cf82e9e`.
- Source profile freeze SHA-256 `22f7409ba39736a316c97cb8ca0a8e04549b2bada38deea769419794059077f4`; loaded-source readset SHA-256 `0c389607977c75bd2ff93c78b685338e54772b9fe8ef04c723b81e7bb1cba679`.
- Root Git readback: parent `.../c57-admission-publication-pilot-r1-20261028-Git-readback.json`, SHA-256 `6c9e2afeb294176134fe0634b81a1372ede4b34d0bea31e387d9bd923b94c6fc`.

The exact JUnit result is **7 passed, 0 failed, 0 errors, 0 skipped**; outer wall time was 29.780 seconds, with maximum sampled process-tree RSS 1,083,883,520 bytes against a 2,415,917,904-byte cap. I independently matched all 1,815 readset entries to present, tracked worktree files with identical SHA-256 values (1,800 `src`, 15 `tests`, 0 `tools`), and all 14 frozen selected-input pins; no input mismatches. The Git readback binds the same source head/tree and reports zero Git/index/work mismatches. This readset covers the finite observed Python import set, not unimported source, native bytes, or external dependencies.

## What the pilot establishes

The five exact testcase IDs that failed in the pinned C37 JUnit are present and pass here. The two extra passing cases are `test_fast_worker_or_cancellation_cannot_be_overwritten_by_late_admission_progress[completed]` and `test_stalled_admission_cas_does_not_hold_other_job_cancellation`.

The completed-worker case patches the raw Store's `create_job` seam to run the real `ControlWorker.dispatch_once()` before the enqueue call resumes. It observes the completed job with all three admission diagnostic IDs already visible, and verifies that later progress remains unchanged. This is a direct witness for the **completed** branch of the publication/worker-claim race; the other worker-state parameters were not selected in this pilot.

The capacity case forces `inline_max_bytes=0`, waits at the actual `FileSystemCAS.put_json` provider call for a diagnostic payload, and checks that the pending admission job has no SQL rows yet. While that call is paused and before release, a separate Store on the same SQLite database cancels another job and reads back its verified cancelled state. The underlying CAS write runs after release. This supports the scoped property that admission CAS preparation does not hold the SQLite writer path in a way that blocks another job's SQL cancellation.

That cancellation assertion is **SQL control, not HTTP authorization**: the fixture calls test helper `_sql_cancel`, which creates a synthetic `cancellation_request_scope`; its own docstring says it is not an authorization witness. The separate authenticated-launch case exercises the service launch proof path, not the HTTP cancellation route. The pilot therefore proves neither route authorization for cancellation nor a physical stop or full B56 cancellation contract.

## Limits

- The pilot covers seven selected cases. All five former failing selectors pass. A later 183-case affected wave on the same source cut ran the full current C37 module cohort plus the C57 publication and event-log consumers; it recorded 176 pass, three failures, and four PostgreSQL skips. See [the independent broader-wave review](C57-composed-consumers-r1-actual-review.md.gz) for the two failure causes. The broader wave is not green.
- It exercises SQLite only. PostgreSQL, native stop/cancel behavior, all worker-state parameters, production currentness, HTTP cancellation authorization, the full B56 matrix, and downstream surface/G acceptance are not established here.
- The run plan explicitly disclaims new authority, physical-stop, production-currentness, and G/closure claims. The audit has no closure IDs.

Pattern pass: P29 (behavioral path exercised), P37/P38 (the bounded predicate and what the SQL witness actually tests are stated above), P40 (admission/claim and CAS/SQL capacity are separate same-class witnesses), and P41 (exact C37 selectors are compared with their pinned baseline run). No tests were rerun for this review.
