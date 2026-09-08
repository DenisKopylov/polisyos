"""Capture ordinary Python frames after the measured lazy-facade stall."""
import signal


def expired(_signal, _frame):
    raise RuntimeError("facade_import_diagnostic_120_second_interrupt")


signal.signal(signal.SIGALRM, expired)
signal.setitimer(signal.ITIMER_REAL, 120)
from polisyos.foundry import MethodRouteConstraint, method_accepts_input_contract
signal.setitimer(signal.ITIMER_REAL, 0)
print(MethodRouteConstraint.__module__, method_accepts_input_contract.__module__)
