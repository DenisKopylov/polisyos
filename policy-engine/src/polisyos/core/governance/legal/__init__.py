"""Legal validation subsystem shared by Lex and Scientist."""

from polisyos.core.governance.legal.backends.base import RuleBackend
from polisyos.core.governance.legal.backends.stub import StubBackend

__all__ = ["RuleBackend", "StubBackend"]
