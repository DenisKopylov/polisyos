# R1 timeout companion patch proposal

Prepared against base `13e411da7d9e505856fc336b3d25fd0aabdb1f66`. The unified diff is at `LOCAL/raw/r1-companion-patch-13e411da.patch` (SHA-256 `ffda36eb639a010b4f44eb1cb9137e0630d9e94b487a07dab5cdadddf3c885a6`). `git apply --check` passed read-only. The patch is not applied; no tests were run, per the preparation grant. The four target files were clean at preparation time.

The proposal keeps the singleton macOS spawn-timeout admission unchanged. It removes the generic async timeout assertion built on a custom MagicMock node and replaces that evidence with a real async workflow using canonical `ResolveParametersNode`, the retained selected SKG snapshot, and the existing CAS consumer. The new workflow test reads the produced bundle in the checkpoint callback, confirms the captured value `1.25`, then blocks that owned callback and expects the outer workflow deadline to cancel it with publication state `unknown` and operation `checkpoint`. The existing timed ResolveParameters/SKG replacement test remains the timed positive and asserts the actual consumer reads `1.25` while the live source is `9.75`.

The unsupported-timeout control gains a well-formed custom component ID (`scientist.node_custom_timeout_probe@1.0.0`). It requires the typed `timeout_worker_node_not_supported` refusal before process start, thread fallback, node-body marker, or CAS change. The custom journal and Decimal transport tests use `timeout_s=None` on macOS, where the generic custom-worker timed spawn contract is not admitted; Linux retains the existing `timeout_s=2.0` fork-backed route and Decimal process-ancestry checks. This does not claim timed macOS support for arbitrary custom workers and does not widen the allowlist.

P40 classification: same timeout-spawn admission class, deeper caller-surface coverage. The evidence is limited to an admitted canonical ResolveParameters worker and cancellation of an async checkpoint coroutine awaiting after that node completes. It does not establish hard cancellation of blocking synchronous callbacks or backend/native I/O already in progress, nor timed execution for arbitrary custom nodes on macOS; those IDs continue to receive the typed closed-admission refusal. Broader global deadline propagation across arbitrary workflow operations remains limited / G-decision-pending.

Authorized diff footprint (tests only):
- `tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py`
- `tests/unit/scientist/orchestration/engine/runner/test_activity_worker.py`
- `tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py`
- `tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py`

First later discriminating checks: the existing timed parameter of `test_real_workflow_selector_replays_saved_source_with_current_live_replacement`; the new `test_async_workflow_deadline_cancels_checkpoint_after_real_skg_node_completed`; all `test_spawn_timeout_refuses_unsupported_inputs_without_process_or_thread_fallback` cases; `test_remote_worker_wire_replays_only_declared_branch_operations`; and both backend cases of `test_real_worker_process_consumes_state_and_emits_exact_typed_outcome`. These remain unexecuted and require root’s later test wave.
