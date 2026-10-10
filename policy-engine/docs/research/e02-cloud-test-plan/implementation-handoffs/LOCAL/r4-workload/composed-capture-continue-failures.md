# Opt-in continuation after captured pytest failures

This is an unapplied patch proposal. The capture wrapper remains unchanged. No product command, pytest process, heavy fit, or runtime test was run for this artifact.

- Candidate wrapper: docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py at SHA-256 894300665556ef644ffffb67ab2dc0508ff4e7f8d840bf256bb199c885889087.
- Patch artifact: docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-capture-continue-failures.patch at SHA-256 e96685bc529d6eca048c77bd3955b2cab5d2518f1f3ff519172a5ad74674f9de.
- Intended queue: one full 19-command base invocation followed by its 11-command supplement invocation; no same-plan resume or output reuse is introduced.

The explicit --continue-command-failures option defaults off. Without it, the queue retains stop-at-first-non-success behavior. With it, continuation is eligible only after a pytest command exits 1 and its parsed JUnit cases independently reconcile to a nonempty, complete set of PASS/FAIL/ERROR cases whose actual failure/error count explains the unchanged command FAIL/ERROR status.

Before any command, the wrapper freezes the canonical SHA-256 of the selected product-venv profile: interpreter executable/prefix/base prefix, compatibility package versions, and the full installed-distribution name/version inventory. That digest is included in the generated input-manifest hash and run manifest. Each command now re-reads the selected interpreter through the existing package_versions + validate_product_python_profile path immediately before launch and after capture, retaining both full observations, hashes, match flags, and read errors in the command receipt. A pre-command mismatch/refusal prevents launch. An after-command profile read failure or mismatch is a stopping integrity outcome; if that same command's JUnit showed FAIL/ERROR, pytest_result_status and failed_command_ids preserve that observed test failure while the final command status indicates the profile drift. The continuation gate also recomputes the receipt profile digests and requires both observations to equal the frozen digest.

Continuation additionally requires the same root-pinned commit, tree, plan, input manifest, complete raw-source manifest, wrapper/plugin hashes, passing source identity before and after, fresh exact plan-derived output roots, complete pre-metadata and final output inventories whose hashes match captured stdout/stderr/JUnit, passing module-origin receipts, and complete required child streams. Failures remain FAIL/ERROR when the integrity profile remains stable; all unexecuted commands remain UNRUN. A completed queue with test failures is SELECTED_RANGE_COMPLETE_WITH_FAILURES and returns nonzero. Signals, non-1 exits, launch errors, timeouts, skips, invalid/incomplete JUnit, identity drift, profile read failures/mismatch, incomplete output capture, and module-origin failures stop the queue.

## Harmless oracle to run after patch review/application

Use a fresh temporary two-command synthetic queue that exercises the wrapper's real main loop, with no scientific backend or production tests. The first ordinary pytest command should use controlled fixtures with one passing case and one deliberately failing assertion, yielding exit 1 and a complete JUnit report. The second command should be a harmless passing pytest fixture that writes a unique marker into its own declared output root.

Positive assertions:

1. The first command's status and pytest_result_status remain FAIL; the full capture and both before/after profile observations match the frozen profile; its continuation decision is CONTINUE.
2. The second command executes and writes its marker.
3. The final receipt is SELECTED_RANGE_COMPLETE_WITH_FAILURES, lists the first command in failed_command_ids, preserves the first FAIL and second PASS, and returns nonzero.
4. No scientific fit, fixture data, or candidate authority is involved.

For the profile falsifier, use an isolated harness with package_versions replaced by harmless in-memory profile fixtures: keep the initial/frozen profile and source/tool/plan/input identities unchanged, then change one installed distribution version in only the post-command observation. Assert the receipt records the changed inventory, the status stops the queue, the second marker command remains UNRUN, and the failure continuation decision is REFUSED. Repeat with an unavailable/malformed post-command profile and with a changed pre-command profile; the first command must not launch in the pre-command case. Do not mutate the real virtualenv.

Also run the identity/output falsifiers: make the first command's after-run source identity fail, and separately make its required output inventory incomplete. In each case the second command must not execute. With the option omitted, the same fully captured ordinary pytest failure must still stop before the second command. Collection/unsupported-profile, skip, signal/unknown-status, and non-1 exit cases must remain stop conditions.

These are acceptance instructions only; none of the oracle cases has been executed. The patch makes no claim that its behavior has passed.

## Applied-wrapper oracle prepared (not executed)

The root applied the continuation patch. The current candidate bytes are:

- Wrapper: docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py SHA-256 4896e0126cc742987358068d1220b338bd57ee9c5f8ec570b954feb40598654e.
- Pytest origin plugin: docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_pytest_origin_plugin.py SHA-256 02e43a40767d23f2e042ea8d1d0c4db3585b3697de38db50e79e6e8136175352.
- Harmless oracle: docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_continuation_oracle.py SHA-256 b027dac7f29015425e2b88e2986d6c56dd898cf8265b219ccd097fef176e3c9c.

The oracle builds separate temporary product-shaped roots and runs tiny synthetic pytest subprocesses through the real wrapper main, command selector, run_one, output checks, JUnit classifier, origin plugin, and continuation decision. Only source/Git/input admission and the selected-interpreter/package-inventory profile are supplied by synthetic callbacks; no checkout package, product test, production environment, or scientific workload is used. Its cases cover opt-in continuation with final nonzero status and a second-command marker, default stop, post-command source-identity drift, incomplete output inventory, post-command runtime-profile drift, and pre-command profile mismatch. It retains each temporary plan, command stdout/stderr, JUnit, metadata, events, and completion receipt under its printed temporary root.

The oracle has not been run, as directed; these are test instructions and expected assertions, not a behavior receipt. The root should run it through the reviewed capture process before treating continuation behavior as verified.
