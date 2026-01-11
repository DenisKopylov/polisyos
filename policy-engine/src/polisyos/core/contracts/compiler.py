from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


class LinkReportRef(ArtifactRef):
    kind: Literal["compiler.link_report"] = "compiler.link_report"
    media_type: Literal["application/json"] = "application/json"


class CompileReportRef(ArtifactRef):
    kind: Literal["compiler.compile_report"] = "compiler.compile_report"
    media_type: Literal["application/json"] = "application/json"


class CompilerNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: list[str] = Field(default_factory=list)
