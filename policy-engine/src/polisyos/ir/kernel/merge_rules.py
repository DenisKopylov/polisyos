from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel


class MergeRuleKind(str, Enum):
    SUM = "sum"
    OVERRIDE = "override"
    PRIORITY = "priority"
    ERROR = "error"


class MergeRuleRef(KernelModel):
    rule_id: str = Field(..., pattern=ID_PATTERN)


class MergeRuleSpec(KernelModel):
    rule_id: str = Field(..., pattern=ID_PATTERN)
    kind: MergeRuleKind
    description: str | None = Field(None, max_length=200)


class MergeRuleRegistry(KernelModel):
    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    rules: dict[str, MergeRuleSpec] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rules(self) -> "MergeRuleRegistry":
        for key, spec in self.rules.items():
            if not key or not isinstance(key, str):
                raise ValueError("merge rule id must be a non-empty string")
            if key != spec.rule_id:
                raise ValueError(f"merge rule id mismatch: '{key}' != '{spec.rule_id}'")
        return self


DEFAULT_MERGE_RULE_REGISTRY = MergeRuleRegistry(
    rules={
        "sum": MergeRuleSpec(rule_id="sum", kind=MergeRuleKind.SUM),
        "override": MergeRuleSpec(rule_id="override", kind=MergeRuleKind.OVERRIDE),
        "priority": MergeRuleSpec(rule_id="priority", kind=MergeRuleKind.PRIORITY),
        "error": MergeRuleSpec(rule_id="error", kind=MergeRuleKind.ERROR),
    }
)
