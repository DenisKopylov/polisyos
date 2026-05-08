"""Example Scientist governance pass exposed through entry points."""

from .governance import ExampleAuditMarkerPass, audit_marker_pass_factory

__all__ = ["ExampleAuditMarkerPass", "audit_marker_pass_factory"]
