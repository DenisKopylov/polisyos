from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from polisyos.core.artifacts.store import FileSystemCAS
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
    def compile(self, store: FileSystemCAS, request: CompileRequest) -> CompileResult:  # pragma: no cover - protocol
        ...

    def execute(self, store: FileSystemCAS, request: ExecuteRequest) -> ExecuteResult:  # pragma: no cover - protocol
        ...


@runtime_checkable
class FabricPort(Protocol):
    def snapshot(self, store: FileSystemCAS, request_ref: DataViewRequestRef) -> DataSnapshotRef:  # pragma: no cover - protocol
        ...


@runtime_checkable
class ScholarPort(Protocol):
    def enrich(self, store: FileSystemCAS, intent: ResearchIntent) -> KnowledgeBundleRef:  # pragma: no cover - protocol
        ...


@runtime_checkable
class LexPort(Protocol):
    def evaluate(
        self, store: FileSystemCAS, context: LegalContext
    ) -> tuple[LegalReportRef, ChangeProposalRef | None]:  # pragma: no cover - protocol
        ...


@runtime_checkable
class Tracer(Protocol):
    def start_as_current_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Any:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class ExecutionContext:
    store: FileSystemCAS
    run: RunContext
    logger: logging.Logger
    tracer: Tracer | None = None

    fabric: FabricPort | None = None
    foundry: FoundryPort | None = None
    scholar: ScholarPort | None = None
    lex: LexPort | None = None
