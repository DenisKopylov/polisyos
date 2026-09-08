"""Bounded stack diagnostic for the observed idle lazy-facade import deadlock."""
import faulthandler

faulthandler.dump_traceback_later(10, exit=True)
from polisyos.foundry import MethodRouteConstraint, method_accepts_input_contract
faulthandler.cancel_dump_traceback_later()
print(MethodRouteConstraint.__module__, method_accepts_input_contract.__module__)
