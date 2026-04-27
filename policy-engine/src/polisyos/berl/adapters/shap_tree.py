"""TreeSHAP-compatible adapter boundary."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter


@dataclass(frozen=True, slots=True)
class TreeSHAPAdapter(KernelSHAPAdapter):
    """TreeSHAP-compatible fallback using exact empirical Shapley enumeration.

    This adapter does not claim path-dependent TreeSHAP exactness. It gives tree
    models the same bounded-infidelity audit path as other scalar black boxes
    until an optional tree-backend adapter is installed.
    """

    method_id: str = "tree_shap"
