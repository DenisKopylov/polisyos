"""AuditLog protocol — lightweight audit event interface for the engine."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from polisyos.core.artifacts.manifest import ArtifactRef


@runtime_checkable
class AuditLog(Protocol):
    """Minimal append-only audit log interface.

    Implementations may delegate to ``ChainedAuditSink`` (tamper-evident
    chain) or simply no-op in non-production environments.
    """

    def append(
        self,
        *,
        run_id: str,
        actor: str,
        action: str,
        artifact_refs: list[ArtifactRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:  # pragma: no cover - protocol
        ...

    def close(self) -> None:  # pragma: no cover - protocol
        ...


class NoopAuditLog:
    """No-op implementation for when audit is disabled."""

    def append(self, **kwargs: Any) -> None:
        return None

    def close(self) -> None:
        return None
