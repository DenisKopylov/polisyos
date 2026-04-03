"""Artifact-reference types shared by compiler, linker, and downstream runtime surfaces."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


class LinkReportRef(ArtifactRef):
    """Artifact reference for a linker report produced while wiring a policy graph."""
    kind: Literal["compiler.link_report"] = "compiler.link_report"
    media_type: Literal["application/json"] = "application/json"


class CompileReportRef(ArtifactRef):
    """Artifact reference for the high-level report emitted by Foundry compilation."""
    kind: Literal["compiler.compile_report"] = "compiler.compile_report"
    media_type: Literal["application/json"] = "application/json"


class CompilerNotes(BaseModel):
    """Compiler notes public type."""
    model_config = ConfigDict(extra="forbid")

    notes: list[str] = Field(default_factory=list)
