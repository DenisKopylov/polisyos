"""Frozen method-selection receipt models for persisted N6 history reads."""

from __future__ import annotations

import hashlib
import json
import math
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common import serialization

if TYPE_CHECKING:
    from collections.abc import Mapping


class MethodSelectionAlternative(BaseModel):
    """One registry-resolved row from a real Foundry method-selection trace."""


    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    method_fqn: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    data_modalities: tuple[str, ...] = ()
    advisor_score: float | None = None
    selected: bool = False
    loss_reasons: tuple[str, ...] = ()


class MethodSelectionReceipt(BaseModel):
    """Content-bound proof emitted from the canonical Foundry selection owner."""


    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.foundry.method_selection_receipt.v2"] = (
        "policyos.foundry.method_selection_receipt.v2"
    )
    selection_authority: Literal[
        "foundry_registry_advisor",
        "requested_registry_method",
    ]
    selected_method_fqn: str = Field(min_length=1)
    ranked_alternatives: tuple[MethodSelectionAlternative, ...] = Field(min_length=1)
    denominator: tuple[str, ...] = Field(min_length=1)
    selection_context_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_selection_trace(self) -> MethodSelectionReceipt:
        canonical_denominator = tuple(sorted(set(self.denominator)))
        if self.denominator != canonical_denominator:
            raise ValueError("value_method_selection_denominator_not_canonical")
        if self.selected_method_fqn not in self.denominator:
            raise ValueError("value_method_selection_outside_registry_denominator")
        selected_trace_fqns = {row.method_fqn for row in self.ranked_alternatives}
        content_hash_matches = self.content_hash == _method_selection_receipt_content_hash(
            serialization.artifact_self_identity_projection(self)
        )
        if (
            self.selection_authority == "foundry_registry_advisor"
            and not content_hash_matches
            and self.selected_method_fqn in selected_trace_fqns
            and any(row.method_fqn not in self.denominator for row in self.ranked_alternatives)
        ):
            raise ValueError("value_method_selection_fixed_default")
        if any(row.method_fqn not in self.denominator for row in self.ranked_alternatives):
            raise ValueError("value_method_selection_trace_outside_denominator")
        selected_rows = tuple(row for row in self.ranked_alternatives if row.selected)
        if len(selected_rows) != 1 or selected_rows[0].method_fqn != self.selected_method_fqn:
            raise ValueError("value_method_selection_receipt_incoherent")
        methods = tuple(row.method_fqn for row in self.ranked_alternatives)
        if len(methods) != len(set(methods)):
            raise ValueError("value_method_selection_trace_duplicate_method")
        expected_ranks = tuple(range(1, len(self.ranked_alternatives) + 1))
        if tuple(row.rank for row in self.ranked_alternatives) != expected_ranks:
            raise ValueError("value_method_selection_trace_rank_drift")
        if self.selection_authority == "foundry_registry_advisor" and any(
            row.advisor_score is None for row in self.ranked_alternatives
        ):
            raise ValueError("value_method_selection_trace_score_missing")
        if any(
            row.advisor_score is not None and not math.isfinite(row.advisor_score)
            for row in self.ranked_alternatives
        ):
            raise ValueError("value_method_selection_trace_non_finite_score")
        payload = serialization.artifact_self_identity_projection(self)
        if self.content_hash != _method_selection_receipt_content_hash(payload):
            raise ValueError("value_method_selection_receipt_content_hash_mismatch")
        return self

    def verify_selection_context(
        self,
        expected_selection_context_hash: str,
    ) -> MethodSelectionReceipt:
        """Verify that this receipt belongs to a recomputed selector context.

        Args:
            expected_selection_context_hash: Canonical hash recomputed from live selector inputs.

        Returns:
            This validated receipt.

        Raises:
            ValueError: If the receipt was produced for another selector context.
        """

        if self.selection_context_hash != expected_selection_context_hash:
            raise ValueError("value_method_selection_context_hash_mismatch")
        return self


# Preserve the module.qualname owners frozen by existing N6 records. The
# model schemas are built in this lightweight module before retaining the
# historical public identity. advisor.py re-exports these exact objects.
MethodSelectionAlternative.__module__ = "polisyos.foundry.methods.selection.advisor"
MethodSelectionReceipt.__module__ = "polisyos.foundry.methods.selection.advisor"


def _method_selection_receipt_content_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
