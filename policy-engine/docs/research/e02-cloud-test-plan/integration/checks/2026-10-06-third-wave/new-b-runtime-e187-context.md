# B retry runtime bounded G wave

Pinned candidate: `e1871506fcebc47d6572891b323ddf1f2083a3c9`, tree `edc05c3489f0e2e44c7c81ccbfb854539c9bdc50`, parent `23a2fdadbc8e6ffa8464c28942d218fc07da241b`. Exact full-tree `git archive` is at `../candidates/new-b-runtime-e187`; all **13,750** tracked blobs, paths, and modes matched Git. No `.git`, `.venv`, `node_modules`, or tracked production-data directory was copied. G stayed clean on `## codex/e02-integration...origin/codex/e02-integration` with HEAD `0346fc656a45ff2cd43d37126992d8ddbb739d10`.

Disk free was 29.207 GiB before archive materialization, 28.753 GiB after, and 28.694 GiB after the wave. The sole prescribed pytest wave ran against the isolated project root with G's existing Python 3.14.3 / pytest 9.0.2 environment and candidate `src` first on `PYTHONPATH`; no packages or production data were added. Exact argv/environment and imported module paths/hashes are in `new-b-runtime-e187-command.json` and `new-b-runtime-e187-preflight.json`. Candidate `retry.py` and `common/async_tools.py` imports resolve inside the archive. All runtime/test source hashes and import origins stayed stable pre/post.

Command selectors were exactly:

```text
pytest -o addopts= -q tests/unit/common/test_async_tools.py tests/unit/scientist/orchestration/engine/test_retry.py tests/unit/remediation/test_run_03.py
```

The captured outcome is **FAIL: 159 passed, 6 failed, 12 skipped, 0 errors**, with 37 deprecation warnings. Pytest time was 15.270s, measured wall 16.556s, and `RUSAGE_CHILDREN.ru_maxrss` was 166,838,272 bytes. All 12 skips are Linux-only subreaper or RLIMIT descriptor oracles on macOS; they are SKIP, not PASS. The six failures are all variants of `test_real_process_preserves_control_exception_without_retry`: sync/async × `SystemExit`, `KeyboardInterrupt`, and unsupported `SystemExit`. Each observed `NodeTimeoutError(code=node.timeout)` after one attempt instead of the expected control outcome. These tests specify a 0.5s runtime timeout. Failure attribution is **not established**: no exact slice-base replay was run, and the failures are not reclassified as platform skips or inherited red.

The independent review remains authoritative on bounded claims: B14/B24/B40/LA-057 are LIMITED; Linux supervisor/FD acceptance and workflow absolute-deadline producer forwarding remain outside this macOS wave. Although the selected file contains a bounded async case and an unbounded thread cancellation case, it does not include the specific adversarial unbounded real async-node cancellation case described in `new-B-runtime-review.md`. No extra selectors or rerun were added. No finding closure is claimed.

Two initial harness attempts failed before pytest started because the local runner used a duplicated project-root cwd; the successful run followed a path correction. They did not touch candidate source. Their setup history is recorded in `new-b-runtime-e187-context.json`; the final complete test logs are `new-b-runtime-e187.stdout`, `.stderr`, and `.junit.xml`. The local slot is now free.
