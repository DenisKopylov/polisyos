# R1 worker transport harness widening

P40 bucket: same worker-process class, second escape. The failed Darwin cases came from the test's outer `fork` of a multithreaded pytest process; production spawn admission remains closed for custom node IDs.

The test now uses a top-level, importable child target and node from `tests/unit/scientist/orchestration/engine/runner/decimal_worker_transport.py`. The fresh child configures the selected serializer, patches registry discovery locally, calls the real `run_node_in_worker_sync`, checks exact Decimal values in the node, and returns the typed outcome. Darwin and other non-Linux hosts use a spawn outer test process; Linux retains the fork outer process and the existing timed custom-node route. The test keeps the 10-second outcome bound and process ancestry assertions.

Only code paths authored for this widening: `tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py` and `tests/unit/scientist/orchestration/engine/runner/decimal_worker_transport.py`. No production code or timeout admission contract changed.

Pre-change failure evidence remains at `LOCAL/raw/r1-patch-verification-20261010/` (pytest stdout SHA `fb9cec256cf64a4b2e42cb03dac421e366be19011832f1c2d5c960318be0790c`; stderr SHA `1cb41b9348084992f587a6f38d084951106be140c66afb081bd02796a1bd37c7`; JUnit SHA `70adbf4f5793e317cb6908b00317626389d92e6fc4929cadfe38872ee4fd68c7`). It records 85 passed / 2 failed; both codec cases stopped at `parent.poll(10.0)`, with the multithreaded-fork warning. No OOM was established.

Current source hashes: test `ea6579ebeafd7ef336ff2fe6af2cd3f5ceb87889952832c7185098226cde75ba`; helper `771810e0295d1a75c39d7a101ff3bb8f595bce6b85022bae12746744a78d74fe`. `ruff format`, `ruff check`, and `git diff --check` passed for the two code paths. Per author instruction, no tests or child processes were run; the focused execution remains pending independent review.
