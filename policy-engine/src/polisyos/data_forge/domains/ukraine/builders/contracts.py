"""Small result contracts shared by Ukraine stage builders."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import TYPE_CHECKING, Any as _Any

if TYPE_CHECKING:
    from pathlib import Path as _Path
    from polisyos.data_forge.domains.ukraine.manifests import (
        ArtifactRecord as _ArtifactRecord,
        ValidationFinding as _ValidationFinding,
    )


@_dataclass
class StageBuildResult:
    """Structured stage output returned to the orchestrator."""

    outputs: dict[str, _ArtifactRecord] = _field(default_factory=dict)
    findings: list[_ValidationFinding] = _field(default_factory=list)
    warnings: list[str] = _field(default_factory=list)
    metrics: dict[str, _Any] = _field(default_factory=dict)
    manifest_paths: list[_Path] = _field(default_factory=list)


__all__ = ("StageBuildResult",)
