"""TreeSHAP-compatible adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.berl.adapters.protocol import ExplanationContext, RawExplanation, ScalarModel


@dataclass(frozen=True, slots=True)
class TreeSHAPAdapter(KernelSHAPAdapter):
    """TreeSHAP-compatible fallback using exact empirical Shapley enumeration.

    This adapter does not claim path-dependent TreeSHAP exactness. It gives tree
    models the same bounded-infidelity audit path as other scalar black boxes
    until an optional tree-backend adapter is installed.
    """

    method_id: str = "tree_shap"

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        """Run empirical Shapley while exposing the unsupported tree fallback."""

        raw = super().explain(model, x, context)
        fallback_reason = (
            "path-dependent TreeSHAP backend unavailable; "
            "using exact empirical Shapley enumeration"
        )
        params = {
            **dict(raw.params),
            "requested_method_id": self.method_id,
            "effective_method_id": self.effective_method_id,
            "fallback": True,
            "fallback_reason": fallback_reason,
        }
        assumptions = {
            **dict(raw.assumptions),
            "tree_exactness_claimed": False,
            "fallback_reason": fallback_reason,
        }
        return replace(
            raw,
            method_id=self.method_id,
            params=params,
            assumptions=assumptions,
            requested_method_id=self.method_id,
            effective_method_id=self.effective_method_id,
            fallback=True,
            fallback_reason=fallback_reason,
        )
