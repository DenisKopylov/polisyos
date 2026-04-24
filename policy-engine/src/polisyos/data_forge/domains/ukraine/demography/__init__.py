"""Typed demographic artifact readers for Ukraine static-aging inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, cast

import numpy as np
import numpy.typing as npt
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


def _to_numpy(value: object, *, dtype: npt.DTypeLike = float) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value.astype(dtype, copy=False)
    return np.asarray(value, dtype=dtype)


def _read_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _resolve_artifact_path(root: Path, *candidates: str) -> Path:
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    raise FileNotFoundError(
        f"none of the expected demographic artifact files exist under {root}: {candidates}"
    )


class UkraineDemographyArtifacts(BaseModel):
    """Reconciled demographic targets, priors, and donor pools for static aging."""

    contract_id: ClassVar[str] = "data_forge.ukraine.demography.artifacts.v1"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    state_ids: list[str]
    target_state_totals: Any
    entrant_state_totals: Any
    transition_prior_matrix: Any
    allowed_transition_mask: Any | None = None
    donor_weights: Any | None = None
    donor_state_index: Any | None = None
    donor_record_index: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "target_state_totals",
        "entrant_state_totals",
        "transition_prior_matrix",
        "allowed_transition_mask",
        "donor_weights",
        "donor_state_index",
        "donor_record_index",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: object) -> object:
        if value is None:
            return None
        return np.asarray(value)

    @field_serializer(
        "target_state_totals",
        "entrant_state_totals",
        "transition_prior_matrix",
        "allowed_transition_mask",
        "donor_weights",
        "donor_state_index",
        "donor_record_index",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, value: object) -> object:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @model_validator(mode="after")
    def _validate_shapes(self) -> UkraineDemographyArtifacts:
        n_states = len(self.state_ids)
        if n_states == 0:
            raise ValueError("state_ids must not be empty")

        target_state_totals = _to_numpy(self.target_state_totals, dtype=float)
        entrant_state_totals = _to_numpy(self.entrant_state_totals, dtype=float)
        transition_prior_matrix = _to_numpy(self.transition_prior_matrix, dtype=float)
        if target_state_totals.ndim != 1 or target_state_totals.shape[0] != n_states:
            raise ValueError("target_state_totals must be a 1D array aligned with state_ids")
        if entrant_state_totals.ndim != 1 or entrant_state_totals.shape[0] != n_states:
            raise ValueError("entrant_state_totals must be a 1D array aligned with state_ids")
        if transition_prior_matrix.ndim != 2 or transition_prior_matrix.shape[1] != n_states:
            raise ValueError("transition_prior_matrix must have one column per destination state")
        if np.any(target_state_totals < 0.0) or np.any(entrant_state_totals < 0.0):
            raise ValueError("state totals must be non-negative")
        if np.any(transition_prior_matrix < 0.0):
            raise ValueError("transition_prior_matrix must be non-negative")

        if self.allowed_transition_mask is not None:
            mask = np.asarray(self.allowed_transition_mask, dtype=bool)
            if mask.shape != transition_prior_matrix.shape:
                raise ValueError("allowed_transition_mask must match transition_prior_matrix")

        if self.donor_weights is not None or self.donor_state_index is not None:
            if self.donor_weights is None or self.donor_state_index is None:
                raise ValueError("donor_weights and donor_state_index must be provided together")
            donor_weights = _to_numpy(self.donor_weights, dtype=float)
            donor_state_index = _to_numpy(self.donor_state_index, dtype=np.int64)
            if donor_weights.ndim != 1 or donor_state_index.ndim != 1:
                raise ValueError("donor pool arrays must be 1D")
            if donor_weights.shape[0] != donor_state_index.shape[0]:
                raise ValueError("donor pool arrays must align")
            if np.any(donor_weights < 0.0):
                raise ValueError("donor_weights must be non-negative")
            if np.any(donor_state_index < 0) or np.any(donor_state_index >= n_states):
                raise ValueError("donor_state_index contains out-of-range ids")
            if self.donor_record_index is not None:
                donor_record_index = _to_numpy(self.donor_record_index, dtype=np.int64)
                if (
                    donor_record_index.ndim != 1
                    or donor_record_index.shape[0] != donor_weights.shape[0]
                ):
                    raise ValueError("donor_record_index must align with donor_weights")

        return self


def load_reconciled_targets(root: str | Path) -> dict[str, Any]:
    """Load the reconciled hard demographic targets for static aging."""
    root_path = Path(root)
    path = _resolve_artifact_path(
        root_path,
        "demography/targets.json",
        "demography_targets.json",
    )
    return _read_json(path)


def load_transition_priors(root: str | Path) -> dict[str, Any]:
    """Load the origin-to-destination transition priors."""
    root_path = Path(root)
    path = _resolve_artifact_path(
        root_path,
        "demography/transition_priors.json",
        "demography_transition_priors.json",
    )
    return _read_json(path)


def load_donor_pool(root: str | Path) -> dict[str, Any]:
    """Load the donor-pool artifact used to synthesize entrants."""
    root_path = Path(root)
    try:
        path = _resolve_artifact_path(
            root_path,
            "demography/donor_pool.json",
            "demography_donor_pool.json",
        )
    except FileNotFoundError:
        return {}
    return _read_json(path)


def load_demography_artifacts(root: str | Path) -> UkraineDemographyArtifacts:
    """Load and validate all Ukraine demographic artifacts from a directory."""
    targets = load_reconciled_targets(root)
    priors = load_transition_priors(root)
    donor = load_donor_pool(root)
    payload = {
        **targets,
        **priors,
        **donor,
    }
    payload.setdefault("entrant_state_totals", [0.0] * len(payload["state_ids"]))
    payload.setdefault("metadata", {})
    return UkraineDemographyArtifacts.model_validate(payload)


__all__ = [
    "UkraineDemographyArtifacts",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
]
