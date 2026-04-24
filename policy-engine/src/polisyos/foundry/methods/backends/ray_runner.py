"""
Ray distributed backend for Foundry methods.

``RayMethodRunner`` executes a method's ``pure_step`` as a Ray remote task,
enabling transparent distribution across a Ray cluster.

This module is **opt-in** — Ray is an optional dependency.  All public
symbols degrade gracefully when Ray is not installed; attempting to run a
task raises ``RayNotAvailableError`` instead of a cryptic ImportError.

Usage
-----
::

    import ray
    ray.init()

    from polisyos.foundry.methods.backends.ray_runner import RayMethodRunner

    runner = RayMethodRunner(num_cpus=4, memory=2 * 1024**3)
    result = runner.run(method_class, state=state, params={})

    ray.shutdown()

Design decisions
----------------
- ``pure_step`` is submitted as a Ray *remote function* (not an Actor) so
  there is no persistent worker state between calls.  This is consistent with
  the pure-function contract.
- The runner serialises ``state`` and ``params`` via Ray's default serialiser
  (pickle-compatible).  NumPy arrays are zero-copy when the worker is on the
  same host.
- ``timeout`` defaults to None (wait indefinitely), matching the behaviour of
  the local synchronous dispatcher.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "RayMethodRunner",
    "RayNotAvailableError",
    "RayTaskResult",
]


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------


def _ray_available() -> bool:
    try:
        import ray

        return True
    except ImportError:
        return False


class RayNotAvailableError(RuntimeError):
    """Raised when Ray is not installed or not initialised."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RayTaskResult:
    """Result of a single ``pure_step`` executed as a Ray remote task."""

    method_fqn: str
    output: dict[str, Any]
    wall_time_ms: float
    worker_pid: int | None = None


# ---------------------------------------------------------------------------
# Remote task function (defined at module level for pickling)
# ---------------------------------------------------------------------------


def _remote_pure_step(
    method_fqn: str,
    pure_step_fn: Any,
    state: Any,
    params: Mapping[str, Any],
) -> tuple[str, dict[str, Any], float, int | None]:
    """
    Execute ``pure_step`` inside a Ray worker and return serialisable results.

    Returns a tuple ``(method_fqn, output, wall_time_ms, worker_pid)``.
    Defined at module level so Ray's default serialiser can pickle it.
    """
    import os

    t0 = time.perf_counter()
    output = pure_step_fn(state, dict(params))
    elapsed = (time.perf_counter() - t0) * 1000.0
    return method_fqn, output, elapsed, os.getpid()


# ---------------------------------------------------------------------------
# RayMethodRunner
# ---------------------------------------------------------------------------


class RayMethodRunner:
    """
    Executes a Foundry ``pure_step`` as a Ray remote task.

    Parameters
    ----------
    num_cpus:
        Number of CPUs requested per task.  Default 1.
    memory:
        Memory (bytes) requested per task.  Default None (Ray decides).
    timeout:
        Maximum seconds to wait for the result.  Default None (infinite).
    """

    def __init__(
        self,
        *,
        num_cpus: float = 1.0,
        memory: int | None = None,
        timeout: float | None = None,
    ) -> None:
        self._num_cpus = num_cpus
        self._memory = memory
        self._timeout = timeout

    def is_available(self) -> bool:
        """Return True if Ray is installed and a runtime is active."""
        if not _ray_available():
            return False
        try:
            import ray

            return ray.is_initialized()
        except Exception:
            return False

    def run(
        self,
        method_class: Any,
        *,
        state: Any,
        params: Mapping[str, Any],
    ) -> RayTaskResult:
        """
        Submit ``method_class.pure_step`` to Ray and block for the result.

        Parameters
        ----------
        method_class:
            A class with a ``pure_step`` staticmethod and a ``signature``
            attribute (standard Foundry method ABI).
        state:
            Input state dict.
        params:
            Runtime parameters dict.

        Returns
        -------
        RayTaskResult

        Raises
        ------
        RayNotAvailableError
            If Ray is not installed or not initialised.
        RuntimeError
            If the remote task raises an exception.
        """
        if not _ray_available():
            raise RayNotAvailableError(
                "Ray is not installed. Install with: pip install 'ray[default]'"
            )
        import ray

        if not ray.is_initialized():
            raise RayNotAvailableError(
                "Ray runtime is not initialised. Call ray.init() before using RayMethodRunner."
            )

        fqn = method_class.signature.fqn
        pure_step = method_class.pure_step

        # Build Ray remote function with resource requests.
        remote_kwargs: dict[str, Any] = {"num_cpus": self._num_cpus}
        if self._memory is not None:
            remote_kwargs["memory"] = self._memory

        remote_fn = ray.remote(**remote_kwargs)(_remote_pure_step)

        ref = remote_fn.remote(fqn, pure_step, state, params)

        try:
            result_tuple = ray.get(ref, timeout=self._timeout)
        except Exception as exc:
            raise RuntimeError(f"Ray remote task for '{fqn}' failed: {exc}") from exc

        _fqn, output, wall_time_ms, worker_pid = result_tuple
        return RayTaskResult(
            method_fqn=_fqn,
            output=output,
            wall_time_ms=wall_time_ms,
            worker_pid=worker_pid,
        )

    def __repr__(self) -> str:
        return (
            f"<RayMethodRunner num_cpus={self._num_cpus} "
            f"memory={self._memory} timeout={self._timeout}>"
        )
