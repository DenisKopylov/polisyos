"""Public kernel guards module API."""

from __future__ import annotations

from collections.abc import Iterable

from polisyos.scientist.kernel.fsm import ALLOWED_TRANSITIONS, Phase


def advance_phase(state: dict, next_phase: Phase) -> dict:
    """Advance phase helper."""
    current = state.get("phase")
    current_phase = Phase(current) if current else Phase.INTAKE
    allowed = ALLOWED_TRANSITIONS.get(current_phase, set())
    if next_phase not in allowed and next_phase != current_phase:
        raise ValueError(
            f"Phase transition {current_phase.value} -> {next_phase.value} is not allowed"
        )
    state["phase"] = next_phase.value
    return state


def require_artifacts(state: dict, required_keys: Iterable[str]) -> dict:
    """Require artifacts helper."""
    missing = [key for key in required_keys if not state.get(key)]
    if missing:
        raise ValueError(f"Missing required artifacts for phase: {', '.join(missing)}")
    return state
