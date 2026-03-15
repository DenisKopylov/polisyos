from __future__ import annotations

from enum import Enum
import logging
from typing import Any, Literal

from pydantic import Field, model_validator

from .base import ID_PATTERN, KernelModel

logger = logging.getLogger(__name__)


class MergeRuleKind(str, Enum):
    """Core merge rule kinds with CRDT semantics."""

    SUM = "sum"
    OVERRIDE = "override"
    PRIORITY = "priority"
    ERROR = "error"


class ConflictResolution(str, Enum):
    """Strategy when concurrent writes conflict."""

    ERROR = "error"
    FIRST = "first"
    LAST = "last"
    AGGREGATE = "aggregate"


EXPECTED_ALGEBRA_PROPERTIES = {
    MergeRuleKind.SUM: {
        "commutativity": True,
        "associativity": True,
        "idempotency": False,
        "allowed_types": ["int", "decimal", "array"],
    },
    MergeRuleKind.OVERRIDE: {
        "commutativity": False,
        "associativity": False,
        "idempotency": True,
        "allowed_types": None,
    },
    MergeRuleKind.PRIORITY: {
        "commutativity": True,
        "associativity": True,
        "idempotency": True,
        "allowed_types": None,
    },
    MergeRuleKind.ERROR: {
        "commutativity": True,
        "associativity": True,
        "idempotency": True,
        "allowed_types": None,
    },
}


class MergeRuleRef(KernelModel):
    """Reference to a merge rule in the registry."""

    rule_id: str = Field(..., pattern=ID_PATTERN)


class MergeRuleSpec(KernelModel):
    """
    Formal specification of a merge rule with algebraic properties.

    Algebraic Properties:
    - commutativity: merge(a,b) == merge(b,a)
    - associativity: merge(merge(a,b),c) == merge(a,merge(b,c))
    - idempotency: merge(a,a) == a
    """

    rule_id: str = Field(..., pattern=ID_PATTERN)
    kind: MergeRuleKind
    commutativity: bool | None = Field(
        default=None,
        description="Whether merge(a,b) == merge(b,a). Required for order-independent execution.",
    )
    associativity: bool | None = Field(
        default=None,
        description=(
            "Whether merge(merge(a,b),c) == merge(a,merge(b,c)). "
            "Required for parallel reduction."
        ),
    )
    idempotency: bool | None = Field(
        default=None,
        description="Whether merge(a,a) == a. Enables deduplication.",
    )
    conflict_resolution: ConflictResolution = Field(
        default=ConflictResolution.ERROR,
        description="How to handle concurrent writes when rule does not define merge semantics.",
    )
    default_priority: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="Default priority when not specified by mechanism (0=lowest, 1000=highest).",
    )
    allowed_value_types: list[Literal["bool", "int", "decimal", "string", "array"]] | None = Field(
        default=None,
        description="Restrict which SlotValueTypes can use this rule. None = all types allowed.",
    )
    description: str | None = Field(None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def apply_kind_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        kind = data.get("kind")
        if kind is None:
            return data
        try:
            kind_enum = kind if isinstance(kind, MergeRuleKind) else MergeRuleKind(kind)
        except Exception as exc:
            logger.debug(
                "Failed to resolve MergeRuleKind from %r, skipping defaults: %s", kind, exc,
            )
            return data
        props = EXPECTED_ALGEBRA_PROPERTIES.get(kind_enum)
        if not props:
            return data
        for field_name in ("commutativity", "associativity", "idempotency"):
            if data.get(field_name) is None:
                data[field_name] = props[field_name]
        return data

    @model_validator(mode="after")
    def validate_algebra_properties(self) -> "MergeRuleSpec":
        """Ensure algebraic properties match the rule kind."""
        props = EXPECTED_ALGEBRA_PROPERTIES[self.kind]
        if self.commutativity != props["commutativity"]:
            raise ValueError(
                f"MergeRuleKind.{self.kind.name} requires commutativity={props['commutativity']}"
            )
        if self.associativity != props["associativity"]:
            raise ValueError(
                f"MergeRuleKind.{self.kind.name} requires associativity={props['associativity']}"
            )
        if self.idempotency != props["idempotency"]:
            raise ValueError(
                f"MergeRuleKind.{self.kind.name} requires idempotency={props['idempotency']}"
            )
        if self.kind == MergeRuleKind.SUM and self.allowed_value_types:
            invalid = set(self.allowed_value_types) - {"int", "decimal", "array"}
            if invalid:
                raise ValueError(f"SUM merge cannot apply to types: {sorted(invalid)}")
        return self


class MergeRuleRegistry(KernelModel):
    """Registry of all available merge rules."""

    schema_version: str = Field("2.0", pattern=r"^\d+\.\d+$")
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
    schema_version="2.0",
    rules={
        "sum": MergeRuleSpec(
            rule_id="sum",
            kind=MergeRuleKind.SUM,
            commutativity=True,
            associativity=True,
            idempotency=False,
            conflict_resolution=ConflictResolution.AGGREGATE,
            allowed_value_types=["int", "decimal", "array"],
            description="Additive merge: v1 + v2 (commutative, associative)",
        ),
        "override": MergeRuleSpec(
            rule_id="override",
            kind=MergeRuleKind.OVERRIDE,
            commutativity=False,
            associativity=False,
            idempotency=True,
            conflict_resolution=ConflictResolution.LAST,
            description="Last-write-wins by node_id ordering",
        ),
        "priority": MergeRuleSpec(
            rule_id="priority",
            kind=MergeRuleKind.PRIORITY,
            commutativity=True,
            associativity=True,
            idempotency=True,
            conflict_resolution=ConflictResolution.ERROR,
            default_priority=100,
            description="Highest priority wins, node_id tiebreaker",
        ),
        "error": MergeRuleSpec(
            rule_id="error",
            kind=MergeRuleKind.ERROR,
            commutativity=True,
            associativity=True,
            idempotency=True,
            conflict_resolution=ConflictResolution.ERROR,
            description="Explicit conflict detection - raises MergeConflict",
        ),
    },
    notes=[
        "v2.0: Added formal algebra properties (commutativity, associativity, idempotency)",
        "v2.0: Added conflict_resolution strategies",
        "v2.0: Added type constraints for SUM rule",
    ],
)
