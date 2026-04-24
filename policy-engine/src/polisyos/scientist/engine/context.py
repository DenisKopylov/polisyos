"""Public engine context module API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.core.security.audit_protocol import AuditLog
    from polisyos.scientist.engine.metrics_protocol import EngineMetricsCollector

from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.contracts.fabric import DataSnapshotRef, DataViewRequestRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    ExecuteRequest,
    ExecuteResult,
)
from polisyos.core.contracts.lex import ChangeProposalRef, LegalContext, LegalReportRef
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.core.run.context import RunContext


@runtime_checkable
class FoundryPort(Protocol):
    """Foundry port public type."""

    def compile(
        self, store: ArtifactStore, request: CompileRequest
    ) -> CompileResult:  # pragma: no cover - protocol
        ...

    def execute(
        self, store: ArtifactStore, request: ExecuteRequest
    ) -> ExecuteResult:  # pragma: no cover - protocol
        ...


@runtime_checkable
class FabricPort(Protocol):
    """Fabric port public type."""

    def snapshot(
        self, store: ArtifactStore, request_ref: DataViewRequestRef
    ) -> DataSnapshotRef:  # pragma: no cover - protocol
        ...


@runtime_checkable
class ScholarPort(Protocol):
    """Scholar port public type."""

    def enrich(
        self, store: ArtifactStore, intent: ResearchIntent
    ) -> KnowledgeBundleRef:  # pragma: no cover - protocol
        ...


@runtime_checkable
class LexPort(Protocol):
    """Lex port public type."""

    def evaluate(
        self, store: ArtifactStore, context: LegalContext
    ) -> tuple[LegalReportRef, ChangeProposalRef | None]:  # pragma: no cover - protocol
        ...


@runtime_checkable
class Tracer(Protocol):
    """Tracer public type."""

    def start_as_current_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Any:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class ExecutionContext:
    """Execution context public type."""

    store: ArtifactStore
    run: RunContext
    logger: logging.Logger
    tracer: Tracer | None = None

    metrics: EngineMetricsCollector | None = None
    audit: AuditLog | None = None

    depth: int = 0

    fabric: FabricPort | None = None
    foundry: FoundryPort | None = None
    scholar: ScholarPort | None = None
    lex: LexPort | None = None

    memory: Any | None = None  # PersistentMemoryStore (lazy import to avoid cycles)
