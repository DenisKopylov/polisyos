# Independent review: net-ing registry cleanup test

- Candidate: `8580eb4a13cbd734e0a685069ea5bb16a1c5ee63`
- Tree: `267fef2e1a46aee7a7b2c1f6baaa00bf66e3cbd9`
- Parent: `13c0cde6bd8275d5b8d0deb73affa198325aa7c0`
- Delta: one added test, `policy-engine/tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py` (Git blob `0fcd3ad009d7e66d49075c64d0a4b7fa1d73fdff`; SHA-256 `e716a8b501dea4e88c805ff0b707e6bfe2084a735ee94d86d15c25e9691fc68c`). Product source is unchanged; `streaming.py` SHA-256 is `6137d75c6cf07c97077546da0ef6b60712090ec66839eb8dc9b9fee8524dd119`.

## Verdict

**GO for this bounded cleanup-owner regression test and the same-pool transfer property on the reviewed C source.** This is the same P40 cleanup-owner class, not a new class. The result is a C candidate recommendation only; it does not claim formal B87 closure, G integration admission, network-FD cleanup, or total physical-capacity guarantees.

## Property read

The test uses `process_stream_dataset`, the actual `EventStreamConnector` JSONL reader, distinct private `ConnectionPool`s, `FileSystemCAS`, and `CursorStore`. A sanitizer failure plus two controlled disconnect failures leaves the primary exception object intact and asserts the exact old pool and handle remain in the registry owner map (`test_net_ing_registry_cleanup.py:125-153`). It then runs a successful second dataset through a fresh JSONL file and pool. That run emits its expected row and closed checkpoint while disconnect history remains `[old, fresh]`; the registry still retains the exact old `(connector_id, pool)`, with its pending handle, `pending_permit=False`, and semaphore count 1 (`:159-201`). Public `registry.shutdown_async()` later retries the same old handle; the successful order is `[fresh, old]`, the pending owner and pool cleanup state clear, and the semaphore remains 1 (`:203-208`). The final cleanup in `finally` runs after the semantic assertions, so it cannot make these success assertions green.

The new test therefore distinguishes registry retention of a particular unresolved old pool/handle from mere presence of fields or a successful new session. Parent-reported removal control replaces `_retain_cleanup_owner` with an in-memory no-op and fails the exact retained-owner assertion while source/test bytes stay fixed. The raw removal output is in `focused-v3`; it was not rerun independently here.

The cleanup observation is at the connector handle boundary. `EventStreamConnector.disconnect` is a no-op for this local JSONL source, so this is not a socket/OS descriptor leak oracle. Direct sessions without a registry remain caller-owned. Keep B87 formally open until its owner/integration admission is recorded.

## Related, unchanged frontier witness

The existing `test_net_ing_current_frontier.py` distinguishes two cap behaviors. At cap 1, the restored two-row checkpoint is rejected at restore before `poll`, flush, commit, or CAS writes; checkpoint/cursor/index bytes, artifact IDs, and referenced predecessor content/manifests remain unchanged, with matching acquire/release counts. At cap 3, the real source resumes, rows/chunks/windows and contributor lineage match the deterministic source fixture, and a repeat produces no new chunk/window refs or rows. It does not establish full checkpoint-byte idempotency. This is independent evidence adjacent to the new cleanup test, not behavior added by this one-file delta.

## Independent execution

Exact target: `tests/unit/fabric/data_plane/test_net_ing_registry_cleanup.py`, run alone from `policy-engine` with system Python 3.14.0 / pytest 9.0.2, candidate `PYTHONPATH`, Hypothesis disabled, explicit async/benchmark plugins, isolated ignored basetemp/cache. Exit 0; stdout `pytest.stdout` SHA-256 `423b1d0e014eb1eab96f4420f7b344c2615be505dd574b756ac884826ca74f2d`; stderr empty. `run.json` records exact arguments, input hashes, interpreter, branch/tree before and after, and unchanged source/test hashes. This is an observed system environment, not a frozen/offline venv or installed-wheel receipt.
