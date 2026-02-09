from __future__ import annotations

import ast
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from polisyos.ir.analytics.applicability import NormApplicability
from polisyos.ir.citations import CitationRef
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class RuleType(str, Enum):
    """Deontic classification of normative rules."""

    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"


class NormRef(KernelModel):
    """Reference to a normative document provision."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    provision_id: str = Field(..., pattern=ID_PATTERN)
    citations: list[CitationRef] = Field(default_factory=list)
    source_document: str | None = Field(
        default=None,
        description="DEPRECATED: use citations instead",
    )
    version: str | None = Field(
        default=None,
        description="DEPRECATED: use citations instead",
    )

    @classmethod
    def _legacy_hint(cls) -> str:
        return "citations or source_document must be provided"

    @model_validator(mode="after")
    def validate_ref(self) -> "NormRef":
        if not self.citations and not self.source_document:
            raise ValueError(self._legacy_hint())
        return self


class BackendExpr(KernelModel):
    """Backend-specific expression payload."""

    backend: str
    expr: str
    language: str | None = None
    notes: list[str] = Field(default_factory=list)


class NormRule(KernelModel):
    """Single rule within a norm pack."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    norm_id: str = Field(..., pattern=ID_PATTERN)
    provision_refs: list[NormRef] = Field(default_factory=list)
    rule_type: RuleType
    description: str
    applicability: NormApplicability = Field(default_factory=NormApplicability)
    backend_refs: list[str] = Field(default_factory=list)
    backend_exprs: list[BackendExpr] = Field(default_factory=list)
    backend_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Backend-specific rule data (not interpreted by IR)",
    )
    notes: list[str] = Field(default_factory=list)


class NormPack(KernelModel):
    """Package of applicable norms for policy evaluation."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    pack_id: str = Field(..., pattern=ID_PATTERN)
    jurisdiction: str
    effective_date: str | None = None
    norms: list[NormRule] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def parse_expr_syntax(expr: str) -> tuple[bool, str | None]:
    """Parse an expression in eval mode and return (ok, error_message)."""
    try:
        ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        return False, str(exc)
    return True, None


__all__ = [
    "NormPack",
    "NormRef",
    "NormRule",
    "RuleType",
    "NormApplicability",
    "BackendExpr",
    "parse_expr_syntax",
]
