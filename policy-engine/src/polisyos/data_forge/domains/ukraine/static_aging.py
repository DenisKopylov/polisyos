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
        "base_weights": np.array(base_weights, dtype=float, copy=True),
        "origin_state_index": np.array(origin_state_index, dtype=np.int64, copy=True),
        "target_state_totals": np.array(artifacts.target_state_totals, dtype=float, copy=True),
        "entrant_state_totals": np.array(artifacts.entrant_state_totals, dtype=float, copy=True),
        "transition_prior_matrix": np.array(
            artifacts.transition_prior_matrix, dtype=float, copy=True
        ),
    }
    if artifacts.allowed_transition_mask is not None:
        state["allowed_transition_mask"] = np.array(
            artifacts.allowed_transition_mask, dtype=bool, copy=True
        )
    if artifacts.donor_weights is not None:
        state["donor_weights"] = np.array(artifacts.donor_weights, dtype=float, copy=True)
    if artifacts.donor_state_index is not None:
        state["donor_state_index"] = np.array(
            artifacts.donor_state_index, dtype=np.int64, copy=True
        )
    if artifacts.donor_record_index is not None:
        state["donor_record_index"] = np.array(
            artifacts.donor_record_index, dtype=np.int64, copy=True
        )
    state["demography_source_evidence"] = artifacts.source_evidence.model_dump(mode="json")
    if exit_weights is not None:
        state["exit_weights"] = np.array(exit_weights, dtype=float, copy=True)
    if microsim_calibration_report is not None:
        state["microsim_calibration_report"] = microsim_calibration_report
    if microsim_calibration_report_ref is not None:
        state["microsim_calibration_report_ref"] = microsim_calibration_report_ref
    return state


__all__ = ["build_static_aging_state"]
