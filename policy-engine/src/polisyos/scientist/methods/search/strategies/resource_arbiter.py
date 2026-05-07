"""Runtime resource arbitration between JAX and Torch workloads."""

from __future__ import annotations

import gc
import os
import resource
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.search.strategies._deps import torch

logger = get_logger(__name__)


class ResourceMode(str, Enum):
    """Arbitration mode between runtime backends."""

    DISABLED = "disabled"
    SEQUENTIAL_LOCK = "sequential_lock"


@dataclass(slots=True)
class ResourcePolicy:
    """Runtime policy for memory and mutual exclusion."""

    mode: ResourceMode = ResourceMode.SEQUENTIAL_LOCK
    soft_rss_mb: int = 11_000
    hard_rss_mb: int = 13_000
    enable_cleanup: bool = True


def _rss_mb() -> float:
    try:
        # Linux reports KB, macOS reports bytes; detect by magnitude.
        value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if value > 10_000_000:  # bytes-like
            return value / (1024.0 * 1024.0)
        return value / 1024.0
    except Exception:
        return 0.0


def memory_cleanup() -> None:
    """Best-effort memory cleanup between JAX/Torch phases."""
    gc.collect()
    if torch is not None:  # pragma: no branch
        try:
            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)


class ResourceArbiter:
    """
    Cooperative runtime arbiter.

    Guarantees JAX and Torch phases do not execute concurrently when lock mode is enabled.
    """

    def __init__(self, policy: ResourcePolicy | None = None):
        self._policy = policy or ResourcePolicy()
        self._lock = threading.RLock()
        self._owner: str | None = None

    @property
    def policy(self) -> ResourcePolicy:
        return self._policy

    @contextmanager
    def acquire(self, owner: str) -> Iterator[None]:
        if self._policy.mode == ResourceMode.DISABLED:
            yield
            return
        with self._lock:
            self._owner = owner
            try:
                if self._policy.enable_cleanup:
                    memory_cleanup()
                yield
            finally:
                self._owner = None
                if self._policy.enable_cleanup:
                    memory_cleanup()

    def current_owner(self) -> str | None:
        return self._owner

    def memory_status(self) -> dict[str, float | int]:
        rss = _rss_mb()
        return {
            "rss_mb": rss,
            "soft_rss_mb": self._policy.soft_rss_mb,
            "hard_rss_mb": self._policy.hard_rss_mb,
        }

    def enforce_limits(self) -> tuple[bool, bool]:
        """
        Returns:
            (soft_exceeded, hard_exceeded)
        """
        rss = _rss_mb()
        soft = rss >= self._policy.soft_rss_mb
        hard = rss >= self._policy.hard_rss_mb
        if soft:
            logger.warning(
                "ResourceArbiter soft RSS limit exceeded: {:.1f}MB (soft={}MB hard={}MB)",
                rss,
                self._policy.soft_rss_mb,
                self._policy.hard_rss_mb,
            )
        if hard:
            logger.error(
                "ResourceArbiter hard RSS limit exceeded: {:.1f}MB (hard={}MB)",
                rss,
                self._policy.hard_rss_mb,
            )
        return soft, hard

    @classmethod
    def from_env(cls) -> ResourceArbiter:
        mode_raw = os.getenv("SCIENTIST_RESOURCE_MODE", ResourceMode.SEQUENTIAL_LOCK.value)
        try:
            mode = ResourceMode(mode_raw)
        except ValueError:
            mode = ResourceMode.SEQUENTIAL_LOCK
        policy = ResourcePolicy(
            mode=mode,
            soft_rss_mb=int(os.getenv("SCIENTIST_SOFT_RSS_MB", "11000")),
            hard_rss_mb=int(os.getenv("SCIENTIST_HARD_RSS_MB", "13000")),
            enable_cleanup=os.getenv("SCIENTIST_ENABLE_MEMORY_CLEANUP", "1") != "0",
        )
        return cls(policy=policy)
