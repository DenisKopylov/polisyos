"""Kernel orchestration utilities (phase FSM + guards)."""

from .fsm import ALLOWED_TRANSITIONS, KernelState, Phase
from .guards import advance_phase
