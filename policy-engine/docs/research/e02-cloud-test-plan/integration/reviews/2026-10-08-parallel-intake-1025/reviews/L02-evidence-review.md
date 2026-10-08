# L02 evidence review

Pinned packet: 45c82745292baeeb5414b7367dde931872ee0417 (tree 7324a8e4e7f91a88682a188f5bcce37e91901a3a), parent/source candidate f00dd7661a8d3329fb1fa1b049decb0d1d2f277b (tree d9a4e73a0e85fa11f865bf643c1b63fbe66c2767). This is an evidence qualification, not code acceptance. I read the committed packet and receipts without running tests, installing packages, or accessing production inputs.

## Packet and admission

The packet directory contains 49 committed paths: the manifest plus its 48 payload entries. A complete walk reconciled every payload path against the tree; all 48 byte lengths and SHA-256 hashes match, with no unlisted or missing path. File-type denominator for those 49 paths: 28 JSON, 9 stdout, 9 stderr, 1 text, 1 XML, 1 gzip. The 17 prepared/*.json files are prepared inputs, not execution receipts.

The docs-only L02 commit adds the 49 packet files atop f00; its diff contains no source, test, config, generated, or release path. The admission records show create and immediate-create admitted, then resume admitted with complete_verdict=true and no findings. The worktree was created on codex/e02-L02-authentic-20261008 at f00, and identity output binds HEAD/tree/root exactly; attachment output records that branch and clean status. The one nonzero command in create is the expected show-ref --verify exit 1 while checking that the requested branch did not yet exist; resume has 76 commands and all exit 0.

## Mac execution and controls

mac-refusal/command.json records a 10.285 s, 180 s timeout, 537,165,824-byte peak child RSS run on Darwin arm64, App Python 3.14.0, using the existing primary venv and explicit PYTHONPATH into the admitted source checkout. It is source-imported G, not a wheel or installed consumer. The environment inventory has DoWhy absent (dowhy: null); it does not invoke the standalone worker. JUnit lists seven cases: the no-worker_execution_context witness and six unsupported-request cases. The lossless decompressed stdout hashes to the receipt's exact raw-output SHA and says 7 passed, 1 warning; the warning is pytest's nonfatal unknown cache_dir option.

Observed bounded results: no-context direct call yields NUMERICAL_FAILURE, backend_unavailable, null point; six unsupported requests yield INPUT_INVALID, null point and confidence. The fake-point control asserts imports resolve under the source tree, injects point 7.0 into the returned report while preserving status/capability, and gets the expected assertion rejection; restored genuine refusal passes. I independently hashed both imported product modules at f00; each matches the control's recorded SHA. This catches a marker-only proxy, but it is a returned-report mutation control, not removal of source resolution/backend validation. No L02 Mac source/backend-resolution removal-run receipt is present among the deciding mac-refusal outputs.

## Qualification and remaining boundary

P37: absence of the worker context is recomputed for this direct invocation. Whether a configured Mac worker exists or is absent is not_established: no worker resolver/executable launch was checked. P38: status/capability markers alone would accept a fake point; the point assertion rejects it. The actual DoWhy point-only response, interval/SE handling, parent CAS persistence, and independent reader are outside this Mac run.

The independent review calls this bounded_go_for_missing_context_refusal and expressly leaves B212 open/not adjudicated. closure_ids is empty and formal G closure is not adjudicated. The authentic producer positive remains UNRUN because the task-specific G composition and criterion-specific L01 input packet are unavailable. The packet's l02_mac_numeric is prepared_not_executed; its cited historical three-pass Linux Python 3.12 / DoWhy 0.14 profile is candidate-specific to F's earlier SHA, not a Mac result or this L02 run. A separate exact-profile replay of test_real_estimate_point_only_survives_parent_cas_and_reader, with source/input hashes and complete outputs, is still required for that B212 property.

No cloud execution is evidenced in this packet. The resource record says one light, one-thread Mac check only; no heavy/numeric/full-production run and no heavy-slot release from G. It records no Python backend install/restore and no production-data reads. Disk/scratch measurements are not a reservation for a heavy run. The first inline environment observer failed with IndentationError before observation; the corrected observer exited 0, so that is an observer/harness error, not product evidence.
