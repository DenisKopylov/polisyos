"""Legal validation subsystem."""

from polisyos.core.governance.legal.backends.base import RuleBackend
from polisyos.core.governance.legal.backends.stub import StubBackend

__all__ = ["RuleBackend", "StubBackend"]
