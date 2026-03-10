from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from polisyos.ir.kernel.base import KernelModel

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class LinkSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LinkIssueCode(str, Enum):
    UNKNOWN_UNIT = "unknown_unit"
    UNKNOWN_CONCEPT = "unknown_concept"
    MISSING_SLOT = "missing_slot"
    INCOMPATIBLE_CONSTRAINT = "incompatible_constraint"
    UNKNOWN_MECHANISM = "unknown_mechanism"
    MISSING_PARAM = "missing_param"
    UNKNOWN_PARAM = "unknown_param"
    PARAM_TYPE = "param_type"
    PARAM_ENUM = "param_enum"
    PARAM_RANGE = "param_range"
    UNIT_MISMATCH = "unit_mismatch"
    UNKNOWN_METRIC = "unknown_metric"
    UNKNOWN_SELECTOR_FIELD = "unknown_selector_field"
    SELECTOR_SCOPE_MISMATCH = "selector_scope_mismatch"
    UNKNOWN_MERGE_RULE = "unknown_merge_rule"
    MERGE_RULE_CONFLICT = "merge_rule_conflict"
    UNKNOWN_CONSTRAINT = "unknown_constraint"
    UNKNOWN_ACTOR = "unknown_actor"
    UNKNOWN_JURISDICTION = "unknown_jurisdiction"
    MISSING_REGISTRY = "missing_registry"
    DEPRECATED_MECHANISM_BINDINGS = "deprecated_mechanism_bindings"
    MODEL_FIDELITY_LEVEL_IGNORED = "model_fidelity_level_ignored"

    # Legacy / additional codes (kept for backward compatibility)
    UNKNOWN_SLOT = "unknown_slot"
    MERGE_CONFLICT = "merge_conflict"
    MERGE_PRIORITY_MISSING = "merge_priority_missing"
    OBSERVATION_ITEM_TYPE = "observation_item_type"
    INVALID_ARTIFACT_ID = "invalid_artifact_id"
    MISSING_ACTION_FIELD = "missing_action_field"
    ACTION_FIELD_TYPE = "action_field_type"
    ACTION_TYPE = "action_type"
    ACTION_TYPE_MISMATCH = "action_type_mismatch"
    POLICY_MODEL_TYPE = "policy_model_type"
    POLICY_MODEL_LAYERS = "policy_model_layers"
    UNKNOWN_UTILITY_FIELD = "unknown_utility_field"
    MONEY_CURRENCY_MISMATCH = "money_currency_mismatch"
    MONEY_CURRENCY_MISSING = "money_currency_missing"


class LinkIssue(KernelModel):
    severity: LinkSeverity = LinkSeverity.ERROR
    code: LinkIssueCode
    message: str
    path: list[str | int] = Field(default_factory=list)
    ids: dict[str, str] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class LinkReport(KernelModel):
    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    ok: bool
    issues: list[LinkIssue] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "LinkIssue",
    "LinkIssueCode",
    "LinkReport",
    "LinkSeverity",
]
