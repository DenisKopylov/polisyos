"""Public contracts compiler module API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


class LinkReportRef(ArtifactRef):
    """Link report ref data model."""
    kind: Literal["compiler.link_report"] = "compiler.link_report"
    media_type: Literal["application/json"] = "application/json"


class CompileReportRef(ArtifactRef):
    """Compile report ref data model."""
    kind: Literal["compiler.compile_report"] = "compiler.compile_report"
    media_type: Literal["application/json"] = "application/json"


class CompilerNotes(BaseModel):
    """Compiler notes public type."""
    model_config = ConfigDict(extra="forbid")

    notes: list[str] = Field(default_factory=list)
