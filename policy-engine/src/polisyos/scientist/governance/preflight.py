from __future__ import annotations

from polisyos.scientist.kernel.human_gate import GateRequest, GateDecision


def preflight_checks(state: dict) -> tuple[dict, GateRequest | None]:
    """
    Placeholder pre-flight governance: returns state unchanged and optional GateRequest.
    """
    return state, None
