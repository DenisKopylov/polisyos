"""Runtime pacing contracts for Data Forge batch kernels."""

from __future__ import annotations

from .thermal import (
    THERMAL_PROFILES,
    ThermalProfile,
    cooldown,
    pause_between_batches,
    resolve_profile,
)

__all__ = [
    "THERMAL_PROFILES",
    "ThermalProfile",
    "cooldown",
    "pause_between_batches",
    "resolve_profile",
]
