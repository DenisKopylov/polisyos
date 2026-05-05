"""Static-aging state builders for Ukraine demographic artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from .demography import UkraineDemographyArtifacts


def build_static_aging_state(
    *,
    base_weights: npt.ArrayLike,
    origin_state_index: npt.ArrayLike,
    artifacts: UkraineDemographyArtifacts,
    exit_weights: npt.ArrayLike | None = None,
    microsim_calibration_report: object | None = None,
    microsim_calibration_report_ref: object | None = None,
) -> dict[str, object]:
    """Compose a Foundry-ready state dict from static-aging demographic inputs."""

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


__all__ = ["build_static_aging_state"]
