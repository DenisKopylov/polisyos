from __future__ import annotations

import os
from enum import Enum


class DeterminismTier(str, Enum):
    """
    Determinism guarantee levels for simulation runs.

    STRICT_CPU: Bit-for-bit reproducibility on same CPU architecture.
    BEST_EFFORT_GPU: Near-deterministic on same GPU model.
    NONDETERMINISTIC: No determinism guarantees.
    """

    STRICT_CPU = "strict_cpu"
    BEST_EFFORT_GPU = "best_effort_gpu"
    NONDETERMINISTIC = "nondeterministic"

    def requires_deterministic_ops(self) -> bool:
        return self in (DeterminismTier.STRICT_CPU, DeterminismTier.BEST_EFFORT_GPU)

    def allows_gpu(self) -> bool:
        return self != DeterminismTier.STRICT_CPU


def parse_determinism_tier(value: str | None) -> DeterminismTier | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    try:
        return DeterminismTier(normalized)
    except ValueError:
        return None


def get_determinism_tier() -> DeterminismTier | None:
    """
    Resolve determinism tier from environment, if configured.

    Uses POLISYOS_DETERMINISM_TIER with values:
    - strict_cpu
    - best_effort_gpu
    - nondeterministic
    """
    return parse_determinism_tier(os.getenv("POLISYOS_DETERMINISM_TIER"))


__all__ = ["DeterminismTier", "get_determinism_tier", "parse_determinism_tier"]
