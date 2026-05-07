"""Auto-scaling signals for worker pools.

Evaluates pool utilisation and emits scaling decisions.  This is a
*signal-only* layer — it computes what should happen but delegates
the actual ``scale_to()`` call to the caller (or an integration loop).

OTel metrics are emitted for scaling events so external systems
(Kubernetes HPA, Ray autoscaler, etc.) can react.
"""

from __future__ import annotations

import logging
import time
from enum import Enum

from pydantic import BaseModel, ConfigDict

from polisyos.scientist.orchestration.engine.runner.worker_pool import WorkerPool

_logger = logging.getLogger(__name__)


class ScaleDirection(str, Enum):
    """Scale direction public type."""

    UP = "up"
    DOWN = "down"
    NONE = "none"


class ScaleDecision(BaseModel):
    """A scaling decision emitted by the autoscaler."""

    model_config = ConfigDict(extra="forbid")

    direction: ScaleDirection
    current_workers: int
    target_workers: int
    reason: str


class AutoScalePolicy(BaseModel):
    """Configuration for the autoscaler."""

    model_config = ConfigDict(extra="forbid")

    min_workers: int = 1
    max_workers: int = 16
    scale_up_threshold: float = 0.8  # utilisation ratio
    scale_down_threshold: float = 0.2
    cooldown_s: float = 60.0
    scale_factor: float = 1.5  # multiply by this on scale-up


class AutoScaler:
    """Evaluates pool utilisation and produces scaling decisions.

    Parameters
    ----------
    pool:
        The worker pool to monitor.
    policy:
        Scaling policy parameters.
    """

    def __init__(
        self,
        pool: WorkerPool,
        policy: AutoScalePolicy | None = None,
    ) -> None:
        self._pool = pool
        self._policy = policy or AutoScalePolicy()
        self._last_scale_at: float = 0.0

    async def evaluate(self) -> ScaleDecision:
        """Compute a scaling decision based on current utilisation."""
        cap = await self._pool.current_capacity()
        utilisation = cap.active_tasks / cap.total_workers if cap.total_workers > 0 else 0.0

        now = time.monotonic()
        in_cooldown = (now - self._last_scale_at) < self._policy.cooldown_s

        if in_cooldown:
            return ScaleDecision(
                direction=ScaleDirection.NONE,
                current_workers=cap.total_workers,
                target_workers=cap.total_workers,
                reason="in cooldown",
            )

        if utilisation >= self._policy.scale_up_threshold:
            target = min(
                int(cap.total_workers * self._policy.scale_factor),
                self._policy.max_workers,
            )
            if target <= cap.total_workers:
                return ScaleDecision(
                    direction=ScaleDirection.NONE,
                    current_workers=cap.total_workers,
                    target_workers=cap.total_workers,
                    reason="at max workers",
                )
            return ScaleDecision(
                direction=ScaleDirection.UP,
                current_workers=cap.total_workers,
                target_workers=target,
                reason=f"utilisation {utilisation:.0%} >= {self._policy.scale_up_threshold:.0%}",
            )

        if utilisation <= self._policy.scale_down_threshold:
            target = max(
                int(cap.total_workers / self._policy.scale_factor),
                self._policy.min_workers,
            )
            if target >= cap.total_workers:
                return ScaleDecision(
                    direction=ScaleDirection.NONE,
                    current_workers=cap.total_workers,
                    target_workers=cap.total_workers,
                    reason="at min workers",
                )
            return ScaleDecision(
                direction=ScaleDirection.DOWN,
                current_workers=cap.total_workers,
                target_workers=target,
                reason=f"utilisation {utilisation:.0%} <= {self._policy.scale_down_threshold:.0%}",
            )

        return ScaleDecision(
            direction=ScaleDirection.NONE,
            current_workers=cap.total_workers,
            target_workers=cap.total_workers,
            reason="within thresholds",
        )

    async def apply(self, decision: ScaleDecision) -> None:
        """Apply a scaling decision to the pool."""
        if decision.direction is ScaleDirection.NONE:
            return

        _logger.info(
            "Scaling %s: %d -> %d (%s)",
            decision.direction.value,
            decision.current_workers,
            decision.target_workers,
            decision.reason,
        )
        await self._pool.scale_to(decision.target_workers)
        self._last_scale_at = time.monotonic()
