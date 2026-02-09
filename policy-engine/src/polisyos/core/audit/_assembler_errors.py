from __future__ import annotations

__all__ = [
    "AuditAssemblyError",
    "IncompleteAuditError",
    "IncompleteRunError",
    "RunNotFoundError",
    "UnsignedArtifactError",
]


class AuditAssemblyError(RuntimeError):
    """Base export error."""


class RunNotFoundError(AuditAssemblyError):
    """Run manifest not found."""


class IncompleteRunError(AuditAssemblyError):
    """Run not finalized."""


class IncompleteAuditError(AuditAssemblyError):
    """Dependency closure is incomplete."""


class UnsignedArtifactError(AuditAssemblyError):
    """Strict signing policy failure."""
