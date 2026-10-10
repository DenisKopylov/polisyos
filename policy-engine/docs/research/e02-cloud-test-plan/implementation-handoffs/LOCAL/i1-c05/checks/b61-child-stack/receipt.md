# B61 child-side stack diagnostic

One timed selector case ran with the frozen replay environment (`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, candidate `.venv/bin/python` CPython 3.14.3) and the existing 30-second node deadline. The exact command is in `command.txt`; full pytest stdout, stderr, and JUnit are retained in `stdout.txt`, `stderr.txt`, and `pytest.xml`.

Result: pytest passed one case in 5.91 seconds (tool wall time 8.73 seconds). This did **not** reproduce the timed timeout. The child entered at PID 71832, parent PID 71786, process name `ForkProcess-1`, process start method `fork`, and exited normally. The child reached `child_exit` before the 3-second stack timer fired, so `child-stack.txt` contains entry/exit markers and **no Python traceback frames**. Do not treat this instrumented pass as confirmation of the uninstrumented behavior or of a fix.

`runtime-input.jsonl` records the parent and child runtime, start methods, PIDs, input `ArtifactRef`, source path and source hash, and pre-run source hashes. `sourcehashes-after.txt` reproduces the same hashes for `retry.py`, `_activity_worker.py`, `serialization.py`, and `test_skg_snapshot_replay.py`, confirming those source/test bytes did not change during this diagnostic. The only instrumentation is the local pytest plugin `i1_c05_child_trace.py`, which wraps the actual supervisor target and installs child-only `faulthandler.dump_traceback_later(3.0, repeat=True)`; it does not wrap or instrument parent stacks.

No cause is established by this run. The saved uninstrumented failure remains the only failure evidence; obtaining a child stack requires a reproduction that stays active long enough for the child timer to fire.
