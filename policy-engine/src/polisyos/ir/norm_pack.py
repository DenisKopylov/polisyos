from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class RuleType(str, Enum):
    """Deontic classification of normative rules."""

    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"


class NormRef(BaseModel):
    """Reference to a normative document provision."""

    provision_id: str
    source_document: str
    version: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class NormRule(BaseModel):
    """Single rule within a norm pack."""

    norm_id: str
    provision_refs: List[NormRef] = Field(default_factory=list)
    rule_type: RuleType
    description: str
    backend_refs: List[str] = Field(default_factory=list)
    condition_expr: str | None = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Backend-specific rule data. For expr_ast backend: "
            "'when' (applicability), 'must' (obligation), "
            "'must_not' (prohibition)"
        ),
    )

    model_config = ConfigDict(extra="forbid", frozen=True)


class NormPack(BaseModel):
    """Package of applicable norms for policy evaluation."""

    pack_id: str
    jurisdiction: str
    effective_date: str | None = None
    norms: List[NormRule] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


__all__ = ["NormPack", "NormRef", "NormRule", "RuleType"]
