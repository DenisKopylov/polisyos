"""Rule evaluation backends."""

from polisyos.scientist.governance.legal.backends.base import RuleBackend
from polisyos.scientist.governance.legal.backends.stub import StubBackend

__all__ = ["RuleBackend", "StubBackend"]
