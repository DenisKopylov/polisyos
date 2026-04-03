"""Quality-report contracts emitted by document, claim, and conflict-resolution pipelines."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BeforeValidator, Field, field_validator, model_validator
from typing_extensions import Annotated

from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel, reject_floats_deep
from polisyos.ir.world.ids import quality_report_id_from_payload

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class QualityScope(str, Enum):
    """Quality scope public type."""
    DOCS_PIPELINE = "docs_pipeline"
    CLAIMS_PIPELINE = "claims_pipeline"
    CONFLICT_RESOLUTION = "conflict_resolution"


class QualityIssueSeverity(str, Enum):
    """Quality issue severity public type."""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class QualityIssue(KernelModel):
    """Represent one deterministic quality finding attached to a world quality report."""
    code: str
    severity: QualityIssueSeverity
    msg: str
    context_json: Annotated[dict[str, Any] | list[Any], BeforeValidator(reject_floats_deep)] = (
        Field(default_factory=dict)
    )


class QualityReport(KernelModel):
    """Persist the sorted quality findings for one pipeline run and give them a stable world id."""
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    quality_report_id: str = Field(..., pattern=ID_PATTERN)
    scope: QualityScope
    run_event_id: str = Field(..., pattern=ID_PATTERN)
    policy_id: str = Field(..., pattern=ID_PATTERN)
    algorithm_version: str
    metrics: Annotated[dict[str, int | str | bool], BeforeValidator(reject_floats_deep)] = (
        Field(default_factory=dict)
    )
    issues: list[QualityIssue] = Field(default_factory=list)
    props: Annotated[dict[str, Any], BeforeValidator(reject_floats_deep)] = Field(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def reject_floats(cls, value: Any) -> Any:
        reject_floats_deep(value)
        return value

    @field_validator("issues")
    @classmethod
    def validate_sorted_issues(cls, value: list[QualityIssue]) -> list[QualityIssue]:
        def _key(issue: QualityIssue) -> tuple[str, str, str, str]:
            context = to_canonical_bytes(issue.context_json).decode("utf-8")
            return (issue.severity.value, issue.code, issue.msg, context)

        sorted_issues = sorted(value, key=_key)
        if [_key(issue) for issue in sorted_issues] != [_key(issue) for issue in value]:
            raise ValueError("issues must be sorted deterministically")
        return value

    @model_validator(mode="after")
    def validate_id(self) -> "QualityReport":
        payload = {
            "scope": self.scope.value,
            "run_event_id": self.run_event_id,
            "policy_id": self.policy_id,
            "algorithm_version": self.algorithm_version,
            "metrics": self.metrics,
            "issues": [issue.model_dump(mode="python") for issue in self.issues],
            "props": self.props,
        }
        expected = quality_report_id_from_payload(payload=payload)
        if self.quality_report_id != expected:
            raise ValueError(
                f"quality_report_id mismatch: {self.quality_report_id} != {expected}"
            )
        return self


__all__ = [
    "QualityIssue",
    "QualityIssueSeverity",
    "QualityReport",
    "QualityScope",
]
