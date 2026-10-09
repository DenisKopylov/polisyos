"""Importable spawn target for bounded-worker late-write tests."""

from __future__ import annotations

from typing import Any


def run_delayed_timeout_task_after_release(
    task: Any,
    authority_active: Any,
    deadline_monotonic: float,
    started: Any,
    release: Any,
    result_sender: Any,
) -> None:
    """Delay the real typed timeout worker until the parent chooses authority."""
    started.set()
    if not release.wait(timeout=10.0):
        result_sender.send(("error", "parent did not release the test worker"))
        result_sender.close()
        return
    try:
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_node_task_in_timeout_worker_sync,
        )

        outcome = run_node_task_in_timeout_worker_sync(
            task,
            authority_active=authority_active,
            deadline_monotonic=deadline_monotonic,
        )
    except Exception as exc:
        result_sender.send(("error", f"{type(exc).__name__}: {exc}"))
    else:
        result_sender.send(("ok", outcome))
    finally:
        result_sender.close()
