"""Represent normative provisions and deontic rules used during policy review."""

from __future__ import annotations

import ast
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

from polisyos.ir.analytics.applicability import NormApplicability
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel

if TYPE_CHECKING:
    from polisyos.ir.loading.citations import CitationRef
else:
    from polisyos.ir.loading.citations import CitationRef

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class RuleType(str, Enum):
    """Classify how a provision constrains policy actions in a norm pack.

    Downstream compliance and reporting logic can treat obligations,
    prohibitions, and permissions differently when explaining policy feasibility
    or legal conflict.
    """

    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"


class NormRef(KernelModel):
    """Reference a source provision that grounds one normative rule.

    Prefer ``citations`` for content-addressed provenance; legacy
    ``source_document`` and ``version`` fields remain accepted for migration.
    Validators require at least one provenance path so a rule cannot be orphaned
    from its source text.
    """

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
    def validate_ref(self) -> NormRef:
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
    """Declare one machine-readable norm and its source-backed applicability scope.

    ``backend_exprs`` can carry backend-specific execution forms, while
    ``rule_type`` and ``applicability`` preserve IR-level semantics for
    governance and explanation layers.
    """

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
    "BackendExpr",
    "NormApplicability",
    "NormPack",
    "NormRef",
    "NormRule",
    "RuleType",
    "parse_expr_syntax",
]
