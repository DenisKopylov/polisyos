from __future__ import annotations

import importlib.util
import multiprocessing as mp
import sys
import tempfile
import time
from pathlib import Path

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.orchestration.engine.executor import _bind_retained_workflow_input
from polisyos.scientist.orchestration.engine.retry import (
    _build_spawn_timeout_task,
    _drain_result_sync,
    _join_worker_until,
    _owned_process_group_id,
    _typed_node_timeout_worker,
    _WorkerResultChannel,
)
from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_outcome
from polisyos.scientist.orchestration.engine.skg_snapshot import SNAPSHOT_INPUT_KEY
from polisyos.scientist.orchestration.engine.state_branching import branch_state


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


def main() -> None:
    test_path = Path("tests/unit/scientist/orchestration/engine/test_skg_snapshot_replay.py")
    spec = importlib.util.spec_from_file_location("skg_test_helpers", test_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("test helper module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (
        tempfile.TemporaryDirectory() as tmp,
        tenant_scope(None, tenant_id="retained-tenant", cell_id="retained-cell"),
    ):
        _, _, _, ctx, state, ref = module._workflow_fixture(Path(tmp))
        replay = state.model_copy(update={"inputs": {SNAPSHOT_INPUT_KEY: ref}})
        replay = _bind_retained_workflow_input(ctx, replay)
        node = ResolveParametersNode()
        branch = branch_state(
            replay, write_paths=node.spec.state_writes, enforce_write_scope=True
        ).state
        task = _build_spawn_timeout_task(node, ctx, branch, alias="resolve")
        context = mp.get_context("spawn")
        channel = _WorkerResultChannel(context)
        ready = context.Event()
        completed = context.Value("d", 0.0)
        authority = context.Value("b", True, lock=False)
        deadline = time.monotonic() + 30.0
        process = context.Process(
            target=_typed_node_timeout_worker,
            args=(task, channel, ready, completed, deadline, authority),
            daemon=True,
        )
        started = time.monotonic()
        process.start()
        channel.close_writer()
        group = _owned_process_group_id(process, ready, deadline=deadline)
        _emit(
            {
                "pid": process.pid,
                "group": group,
                "ready": ready.is_set(),
                "start_method": context.get_start_method(),
            }
        )
        try:
            status, payload = _drain_result_sync(
                process, channel, compute_deadline=deadline, completion_time=completed
            )
            _join_worker_until(process, deadline=time.monotonic() + 1.0)
            _emit(
                {
                    "status": status,
                    "payload_type": type(payload).__name__,
                    "exitcode": process.exitcode,
                    "elapsed_s": time.monotonic() - started,
                }
            )
            if status == "ok":
                outcome = deserialize_outcome(payload)
                _emit({"outcome": outcome.status, "run_id": outcome.state.run_id})
            else:
                _emit({"payload": payload})
        except BaseException as exc:
            _emit(
                {
                    "exception": type(exc).__name__,
                    "message": str(exc),
                    "exitcode": process.exitcode,
                    "alive": process.is_alive(),
                    "group": group,
                    "elapsed_s": time.monotonic() - started,
                }
            )
            raise
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2.0)
            channel.close()
            if process.pid is not None and not process.is_alive():
                process.close()


if __name__ == "__main__":
    main()
