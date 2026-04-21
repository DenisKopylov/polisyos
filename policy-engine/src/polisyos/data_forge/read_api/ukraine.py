"""Runtime-safe read API for Ukraine demographic static-aging artifacts."""
from __future__ import annotations

from typing import Any

import numpy as np

from polisyos.data_forge.domains.ukraine.demography import (
    UkraineDemographyArtifacts,
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)


def build_static_aging_state(
    *,
    base_weights: Any,
    origin_state_index: Any,
    artifacts: UkraineDemographyArtifacts,
    exit_weights: Any | None = None,
    microsim_calibration_report: Any | None = None,
    microsim_calibration_report_ref: Any | None = None,
) -> dict[str, Any]:
    """Compose a Foundry-ready state dict for static aging from read_api artifacts."""
    state: dict[str, Any] = {
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


__all__ = [
    "UkraineDemographyArtifacts",
    "build_static_aging_state",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
]
