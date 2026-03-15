"""Kernel orchestration utilities (phase FSM + guards)."""

from .fsm import ALLOWED_TRANSITIONS, KernelState, Phase  # noqa: F401
from .guards import advance_phase  # noqa: F401
