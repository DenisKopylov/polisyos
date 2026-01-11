"""Kernel orchestration utilities (phase FSM + guards)."""

from .fsm import Phase, KernelState, ALLOWED_TRANSITIONS  # noqa: F401
from .guards import advance_phase  # noqa: F401
