"""Thermal-safe pacing helpers for laptop-friendly runs."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ThermalProfile:
    """Define pause/cooldown delays for laptop-safe batch execution."""

    name: str
    pause_seconds: float = 0.0
    cooldown_seconds: float = 0.0


THERMAL_PROFILES: dict[str, ThermalProfile] = {
    "default": ThermalProfile(name="default", pause_seconds=0.0, cooldown_seconds=0.0),
    "m2_air_16gb": ThermalProfile(name="m2_air_16gb", pause_seconds=0.5, cooldown_seconds=180.0),
}


def resolve_profile(name: str | None) -> ThermalProfile:
    """Return a named thermal profile or the `default` profile when unknown."""
    if not name:
        return THERMAL_PROFILES["default"]
    return THERMAL_PROFILES.get(name, THERMAL_PROFILES["default"])


def pause_between_batches(seconds: float) -> None:
    """Sleep between compute-heavy batches."""
    if seconds > 0:
        time.sleep(seconds)


def cooldown(seconds: float) -> None:
    """Longer pause between heavy stages."""
    if seconds > 0:
        time.sleep(seconds)
