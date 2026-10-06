"""Actual canonical head replacement cancellation; no source mutation."""

import asyncio
import json
import threading
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.orchestration.engine import checkpoint
from polisyos.scientist.orchestration.engine.state import ExperimentState
from tests.unit.scientist.orchestration.engine.test_workflow_deadline_custody import _events, _setup


async def main() -> None:
    root = Path("/tmp/e02-B-current-execution-state/checkpoint-deadline/entered-cancel-probe-cas")  # noqa: S108 - retained isolated oracle fixture
    store = FileSystemCAS(root)
    ctx, node, workflow, executor = _setup(store)
    executor._checkpoint_hook = checkpoint.CASCheckpointHook(
        store=store, run_dir=ctx.run.trace_path.parent
    )
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = checkpoint.os.replace

    def held(source: str | Path, target: str | Path) -> None:
        if Path(target).name != checkpoint.CHECKPOINT_HEAD_FILENAME:
            return original(source, target)
        entered.set()
        try:
            assert release.wait(5)  # noqa: S101 - executable evidence assertion
            return original(source, target)
        finally:
            finished.set()

    checkpoint.os.replace = held
    task = asyncio.create_task(
        executor.execute(workflow, ExperimentState(run_id="R_deadline", params={"seed": 7}))
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)  # noqa: S101 - executable evidence assertion
        task.cancel()
        try:
            await task
        except asyncio.CancelledError as exc:
            print(  # noqa: T201 - complete deciding stdout
                json.dumps(
                    {
                        "error": type(exc).__name__,
                        "message": str(exc),
                        "owner_operation": executor._workflow_publication_operation,
                        "caller_cancelling": task.cancelling(),
                        "head_at_return": (
                            ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HEAD_FILENAME
                        ).exists(),
                    }
                )
            )
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)  # noqa: S101 - executable evidence assertion
        for _ in range(500):
            if (ctx.run.trace_path.parent / checkpoint.CHECKPOINT_HISTORY_FILENAME).exists():
                break
            await asyncio.sleep(0.002)
        checkpoint.os.replace = original
    reopened = FileSystemCAS(root)
    head, dto = checkpoint.resolve_latest_checkpoint(reopened, "R_deadline")
    print(  # noqa: T201 - complete deciding stdout
        json.dumps(
            {
                "head_verified": reopened.verify(head.checkpoint_ref).ok,
                "history_matches": checkpoint.load_checkpoint_history(ctx.run.trace_path.parent)
                .entries[-1]
                .checkpoint_ref
                == head.checkpoint_ref,
                "state": dto.state["params"],
                "producer": node.calls,
                "outputs": len(ctx.run.run_manifest.outputs),
                "finalized": any(e["event"] == "RUN_FINALIZED" for e in _events(ctx)),
            }
        )
    )


asyncio.run(main())
