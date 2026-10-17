"""Method-result and diagnostic shaping for the BERL service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter
from polisyos.berl.adapters.shap_tree import TREE_SHAP_FALLBACK_REASON, TreeSHAPAdapter
from polisyos.berl.contracts.explanation_bundle import MethodExplanation
from polisyos.berl.metrics.redundancy import detect_redundancy_clusters

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.berl.adapters.protocol import ExplanationAdapter, RawExplanation
    from polisyos.berl.metrics.disagreement import AttributionVector

MethodScope = Literal["local", "global", "local_bin", "diagnostic"]


def _reidentify_method(
    method: MethodExplanation,
    *,
    adapter: ExplanationAdapter,
    requested_method_id: str,
    effective_method_id: str | None,
) -> MethodExplanation:
    params = dict(method.params)
    params["requested_method_id"] = requested_method_id
    params["effective_method_id"] = effective_method_id
    if effective_method_id is None:
        return method.model_copy(
            update={
                "method_id": requested_method_id,
                "requested_method_id": requested_method_id,
                "effective_method_id": None,
                "params": params,
            }
        )

    assumptions = dict(method.assumptions)
    fallback = method.fallback
    fallback_reason = method.fallback_reason

    if (
        isinstance(adapter, TreeSHAPAdapter)
        and type(adapter) is TreeSHAPAdapter
        and adapter.method_id == "tree_shap"
    ):
        fallback = True
        fallback_reason = TREE_SHAP_FALLBACK_REASON
        params["fallback"] = True
        params["fallback_reason"] = fallback_reason
        assumptions["tree_exactness_claimed"] = False
        assumptions["fallback_reason"] = fallback_reason
    elif (
        isinstance(adapter, KernelSHAPAdapter)
        and type(adapter) is KernelSHAPAdapter
        and adapter.method_id
        in {
            "kernel_shap",
            "kernel_shap_marginal",
        }
    ):
        fallback = False
        fallback_reason = None
        params["fallback"] = False
        params.pop("fallback_reason", None)
        assumptions.pop("tree_exactness_claimed", None)
        assumptions.pop("fallback_reason", None)

    return method.model_copy(
        update={
            "method_id": requested_method_id,
            "requested_method_id": requested_method_id,
            "effective_method_id": effective_method_id,
            "fallback": fallback,
            "fallback_reason": fallback_reason,
            "params": params,
            "assumptions": assumptions,
        }
    )


def _diagnostic_method(method_id: str, reason: str) -> MethodExplanation:
    """Build a diagnostic record without claiming an implementation ran."""

    return MethodExplanation(
        method_id=method_id,
        requested_method_id=method_id,
        effective_method_id=None,
        library="polisyos.berl",
        scope="diagnostic",
        params={
            "diagnostic": reason,
            "requested_method_id": method_id,
            "effective_method_id": None,
        },
        assumptions={
            "faithfulness_claim": "unbounded",
            "display_policy": "diagnostic_only",
        },
    )


def _scope_from_raw(raw: RawExplanation) -> MethodScope:
    scope = raw.assumptions.get("scope")
    if scope == "local_bin_effect_evidence":
        return "local_bin"
    if scope == "global_comparison_evidence":
        return "global"
    return "local"


def _top_feature_from_vectors(vectors: Sequence[AttributionVector]) -> str | None:
    values: dict[str, float] = {}
    for vector in vectors:
        for feature, value in vector.values.items():
            if abs(value) > abs(values.get(feature, 0.0)):
                values[feature] = value
    if not values:
        return None
    return max(values.items(), key=lambda item: abs(item[1]))[0]


def _feature_in_redundancy_cluster(
    feature: str,
    background_rows: Sequence[Mapping[str, float]],
) -> bool:
    if not background_rows:
        return False
    return any(
        feature in cluster.features for cluster in detect_redundancy_clusters(background_rows)
    )
