# Independent receipt-integrity review: Fabric ten bounded consumers

## Verdict

**GO for a separate receipt commit as bounded source/test evidence.** The protected receipt, source checkpoint, remote readback, selected path hashes, command record, JUnit, and retained output hashes reconcile. The consumer run exercised the candidate bytes in a source worktree whose HEAD was an ancestor, not a clean clone at the candidate commit. It is not an installed-profile run or formal G closure.

## Protected record and source binding

- Protected receipt: `LOCAL/fabric-ten-bounded-consumer-verification.json`, SHA-256 `0467608ff5b246383b2c8d1393866d1628fd3e8afc62d7dc23ca2343dd550680`.
- Source candidate: commit `347e61b84694986bf7fdc5adea0054326c05a213`, tree `685c8c655c47bd9fdedd085e52b1e81e71aa0c46`, parent/slice base `afa5e5cccd50889beb9f5a0424118a11f0b194a7`. Local readback `LOCAL/raw/fabric-ten-source-checkpoint-20261011/readback.json` is `7245f62f844b432d3a5a710d685241444f4eb1f2f719476a5daea469a9b4ea40`; remote readback is `.../remote-readback.json` (`71a3781c0c857db1064cc119ccd05be0dc5166eca83e21116fb1a1e53e5bddc4`) and verifies all ten candidate paths. Selected-footprint receipt `.../selected-footprint.json` is `a295bcffb7a7a874d99243a5725125e5b7a029857f206960f36418a5d0fff2ed`. Their candidate, tree, parent, and path set agree.
- I recomputed the current content hash for every path in the 10-path denominator; all 10 match. The mix is 3 product source files, 4 test files, and 3 tools files. The candidate commit is an ancestor of current audit HEAD `afd5f4aaf7da86e242c2b5cd46f9f85d8ea60dd8`.

## Consumer and lint run receipts

The pytest command record is `LOCAL/raw/batched-blocking-focused-20261010/fabric-quality-adapter-durable-real-consumers-20261011/command.json` (SHA-256 `fc50ae59c1ce7992dba2be329919b42b4ce9f34df4254c095b03e5651a685b27`). The 12 selected pytest nodes produced 32 cases. JUnit (`.../junit.xml`, `7cd53f1685cc4bb0078623466c9855456578a8340d70eae16257cabbdcdd7e33`) reports 32 passed, 0 failures, errors, or skips; recorded wall time is 81.564698 seconds. Stdout (`03c3e50ac9dcb13bc3c897fe9b62758da9e9a4c4cea32add504cc8792276a61e`) and empty stderr match the receipt.

Execution HEAD was `3bbb76a03a2e6896176de07b15dbf9df5a00e4e1`, while `candidate_commit_was_execution_head` is false. The recorded execution input inventory contains 6,163 paths and says pre/post maps are equal, no paths changed, and target candidate paths matched before and after. The raw command has the same HEAD, source-tree working directory, and output hashes. The environment uses `.venv/bin/python`, `PYTHONPATH=src:.`, `POLISYOS_RUN_INTEGRATION=1`, `PYTHONDONTWRITEBYTECODE=1`, and one-thread numerical-library caps. This binds the result to the source worktree and its captured candidate bytes; it does not establish installed module origins or a wheel/profile test.

The scoped behavioral evidence covers DuckDB safety/quality cases, source-contract selection and the real Wave 7 adapter/acquisition bridge, selected Fabric quality/SLO behavior, DFI facade/pipeline behavior, and DUR durable worker fencing. The receipt itself states the limits: `compute_quality_from_duckdb` has no production caller (`bridge_missing`); the source-contract tests do not establish CAS persistence round-trip; the injected-metrics case does not prove absence of a module-global lookup; and the observability tests do not establish an `__all__` ordering contract.

The three explicit `UNRUN` entries are also consistent with the source and command records: `tools/archive/migrate_to_trinity.py` imports an absent legacy migration module, `tools/ops_runners/experiments/run_msme_final_fresg_suite_v3.py` had no experiment run/output, and `tools/quality/diagnostics/check_setup.py` had no setup/bootstrap invocation. No runtime behavior for those paths is implied.

The bounded Ruff record is `LOCAL/raw/batched-blocking-focused-20261010/fabric-ten-canonical-ruff-20261011/command.json` (SHA-256 `656079a5b52d74fa4ab5afbfb7023bdcbe1e37b5415484053e859681068d3ed3`). It records zero diagnostics and 13 stable inputs, at execution HEAD `afa5e5cccd50889beb9f5a0424118a11f0b194a7`, not the source candidate commit. Its stdout and stderr are present and hash-match (`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` and the empty-stream SHA-256). The cited prior review exists at `LOCAL/reviews/fabric-quality-sql-adapter-focused-verification-20261011.md` (`1320f00697c9f8ac2f2914f46fd2b3844edfd098dac80b4b726116d342dd5f0f`).

## Boundary and pattern pass

`formal_closure_ids` is empty and `formal_g_acceptance` is false. The evidence supports only the listed bounded consumers. It does not establish a general Fabric quality-gate bridge, external/currentness semantics, or runtime behavior for the three unrun tools.

Relevant register rows are P29 (reconcile real command/JUnit and exact selected bytes), P38 (separate helper behavior from a production bridge), P40 (retain the declared I001 cohort boundary rather than repairing unrelated instances), and P41 (name the actual execution HEAD and source-input provenance). The recorded limits are material; the pass count alone would overstate the capability.
