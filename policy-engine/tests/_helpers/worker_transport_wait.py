"""Bounded fixture waits for physical worker transport, independent of node SLA."""

from __future__ import annotations

import time
from typing import Any

# Worst retained healthy child:25.095s. Round 1.25x up to the next5s =35s.
WORKER_OUTCOME_WAIT_SECONDS = 35.0
WORKER_EXIT_WAIT_SECONDS = 10.0
WORKER_TERMINATE_WAIT_SECONDS = 5.0
WORKER_KILL_WAIT_SECONDS = 5.0
_POLL_INTERVAL_SECONDS = 0.1


def receive_worker_message(connection: Any, process: Any) -> Any:
    """Receive the original message, refusing expiry, EOF and dead silent child."""
    deadline = time.monotonic() + WORKER_OUTCOME_WAIT_SECONDS
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("actual worker outcome fixture deadline expired")
        if connection.poll(min(_POLL_INTERVAL_SECONDS, remaining)):
            try:
                return connection.recv()
            except EOFError as error:
                raise AssertionError("actual worker closed without an outcome") from error
        if not process.is_alive():
            # A buffered last message remains valid after natural child exit.
            if connection.poll(0):
                try:
                    return connection.recv()
                except EOFError as error:
                    raise AssertionError("actual worker closed without an outcome") from error
            raise AssertionError(
                f"actual worker exited without an outcome: exitcode={process.exitcode}"
            )


def reap_worker_process(process: Any) -> None:
    """Reap the fixture child with a bounded natural/terminate/kill sequence."""
    process.join(WORKER_EXIT_WAIT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(WORKER_TERMINATE_WAIT_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(WORKER_KILL_WAIT_SECONDS)
    if process.is_alive():
        raise AssertionError("actual worker remained live after bounded fixture cleanup")
