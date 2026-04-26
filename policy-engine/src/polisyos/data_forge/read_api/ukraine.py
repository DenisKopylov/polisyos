"""Runtime-safe read API for Ukraine demographic static-aging artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    import numpy.typing as npt

    from polisyos.data_forge.domains.ukraine import UkraineDemographyArtifacts

_UKRAINE_DOMAIN = "polisyos.data_forge.domains.ukraine"
_EXPORTS = {
    "UKRAINE_ASSET_GROUP": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_DONOR_POOL_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_PRIORS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_DEMOGRAPHY_TARGETS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_NORMALIZED_SOURCES_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_RAW_SOURCES_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_READINESS_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_SOURCE_CONFIG_KEY": _UKRAINE_DOMAIN,
    "UKRAINE_STATIC_AGING_INPUTS_KEY": _UKRAINE_DOMAIN,
    "UkraineDemographyArtifacts": _UKRAINE_DOMAIN,
    "UkraineReadinessSummary": _UKRAINE_DOMAIN,
    "UkraineShadowArtifact": _UKRAINE_DOMAIN,
    "UkraineShadowBundle": _UKRAINE_DOMAIN,
    "UkraineShadowDiff": _UKRAINE_DOMAIN,
    "UkraineSourceSummary": _UKRAINE_DOMAIN,
    "compare_ukraine_shadow_bundles": _UKRAINE_DOMAIN,
    "load_demography_artifacts": _UKRAINE_DOMAIN,
    "load_donor_pool": _UKRAINE_DOMAIN,
    "load_reconciled_targets": _UKRAINE_DOMAIN,
    "load_transition_priors": _UKRAINE_DOMAIN,
    "load_ukraine_shadow_bundle": _UKRAINE_DOMAIN,
}


def __getattr__(name: str) -> object:
    """Lazily resolve Ukraine exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public Ukraine read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


def build_static_aging_state(
    *,
    base_weights: npt.ArrayLike,
    origin_state_index: npt.ArrayLike,
    artifacts: UkraineDemographyArtifacts,
    exit_weights: npt.ArrayLike | None = None,
    microsim_calibration_report: object | None = None,
    microsim_calibration_report_ref: object | None = None,
) -> dict[str, object]:
    """Compose a Foundry-ready state dict for static aging from read_api artifacts."""
    import numpy as np

    state: dict[str, object] = {
        "base_weights": np.asarray(base_weights, dtype=float),
        "origin_state_index": np.asarray(origin_state_index, dtype=np.int64),
        "target_state_totals": np.asarray(artifacts.target_state_totals, dtype=float),
        "entrant_state_totals": np.asarray(artifacts.entrant_state_totals, dtype=float),
        "transition_prior_matrix": np.asarray(artifacts.transition_prior_matrix, dtype=float),
    }
    if artifacts.allowed_transition_mask is not None:
        state["allowed_transition_mask"] = np.asarray(artifacts.allowed_transition_mask, dtype=bool)
    if artifacts.donor_weights is not None:
        state["donor_weights"] = np.asarray(artifacts.donor_weights, dtype=float)
    if artifacts.donor_state_index is not None:
        state["donor_state_index"] = np.asarray(artifacts.donor_state_index, dtype=np.int64)
    if artifacts.donor_record_index is not None:
        state["donor_record_index"] = np.asarray(artifacts.donor_record_index, dtype=np.int64)
    if exit_weights is not None:
        state["exit_weights"] = np.asarray(exit_weights, dtype=float)
    if microsim_calibration_report is not None:
        state["microsim_calibration_report"] = microsim_calibration_report
    if microsim_calibration_report_ref is not None:
        state["microsim_calibration_report_ref"] = microsim_calibration_report_ref
    return state


__all__ = sorted((*_EXPORTS, "build_static_aging_state"))
