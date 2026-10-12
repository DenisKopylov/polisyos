"""Small result contracts shared by Ukraine stage builders."""

from __future__ import annotations

import re as _re
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from pathlib import Path as _Path
from typing import TYPE_CHECKING
from typing import Any as _Any

from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord as _ArtifactRecord

if TYPE_CHECKING:
    from polisyos.data_forge.domains.ukraine.manifests import (
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
    # Last to preserve the positional constructor contract used by existing builders.
    inputs: list[_ArtifactRecord] = _field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate the optional builder-owned input records without changing old fields."""
        self.validate_inputs()

    def validate_inputs(self) -> None:
        """Require unique, content-bound input records disjoint from this result's outputs."""
        if not isinstance(self.inputs, list):
            raise TypeError("StageBuildResult.inputs must be a list")
        input_paths: set[str] = set()
        for record in self.inputs:
            if not isinstance(record, _ArtifactRecord):
                raise TypeError("StageBuildResult.inputs entries must be ArtifactRecord values")
            if not isinstance(record.path, str) or not record.path.strip():
                raise ValueError("StageBuildResult input path must be non-empty")
            if not isinstance(record.sha256, str) or _re.fullmatch(r"[0-9a-f]{64}", record.sha256) is None:
                raise ValueError("StageBuildResult inputs must carry a verified SHA-256")
            if type(record.size_bytes) is not int or record.size_bytes < 0:
                raise ValueError("StageBuildResult input size must be a non-negative integer")
            if record.row_count is not None and (
                type(record.row_count) is not int or record.row_count < 0
            ):
                raise ValueError("StageBuildResult input row_count must be non-negative")
            if record.nnz is not None and (type(record.nnz) is not int or record.nnz < 0):
                raise ValueError("StageBuildResult input nnz must be non-negative")
            if record.artifact_id is not None and (
                not isinstance(record.artifact_id, str) or not record.artifact_id.strip()
            ):
                raise ValueError("StageBuildResult input artifact_id must be non-empty when set")
            normalized_path = str(_Path(record.path).resolve())
            if normalized_path in input_paths:
                raise ValueError("StageBuildResult input paths must be unique")
            input_paths.add(normalized_path)

        output_paths = {
            str(_Path(record.path).resolve())
            for record in self.outputs.values()
            if isinstance(record, _ArtifactRecord) and record.path
        }
        if input_paths.intersection(output_paths):
            raise ValueError("StageBuildResult inputs and outputs must have disjoint paths")


__all__ = ("StageBuildResult",)
