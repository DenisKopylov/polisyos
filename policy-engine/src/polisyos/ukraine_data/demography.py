"""Compatibility shim for demographic static-aging read surfaces."""
from __future__ import annotations

from polisyos.data_forge.read_api.ukraine import (
    UkraineDemographyArtifacts,
    build_static_aging_state,
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)

__all__ = [
    "UkraineDemographyArtifacts",
    "build_static_aging_state",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
]
