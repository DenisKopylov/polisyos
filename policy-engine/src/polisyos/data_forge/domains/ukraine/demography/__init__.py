"""Typed demographic artifact readers for Ukraine static-aging inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

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

from polisyos.data_forge.kernel.io.generation_basis import (
    GenerationBasis,
    build_generation_basis,
)


def _to_numpy(value: object, *, dtype: npt.DTypeLike = float) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value.astype(dtype, copy=False)
    return np.asarray(value, dtype=dtype)


_DemographyLayout = Literal["new", "legacy"]
_LAYOUT_PATHS: dict[_DemographyLayout, dict[str, str]] = {
    "new": {
        "targets": "demography/targets.json",
        "priors": "demography/transition_priors.json",
        "donor": "demography/donor_pool.json",
    },
    "legacy": {
        "targets": "demography_targets.json",
        "priors": "demography_transition_priors.json",
        "donor": "demography_donor_pool.json",
    },
}
_REQUIRED_LAYOUT_MEMBERS = ("targets", "priors")
_DEMOGRAPHY_READ_PROFILE = "ukraine-demography-layout-reader.v1"


@dataclass(frozen=True, slots=True)
class _DemographyReadSelection:
    """Immutable bytes selected from the known demographic member profile.

    ``basis`` binds this call's layout and bytes. It is not persisted producer
    inventory and does not establish source completeness or a data version.
    """

    layout: _DemographyLayout
    members: tuple[tuple[str, bytes], ...]
    basis: GenerationBasis

    def payload(self, name: str) -> dict[str, Any]:
        """Decode a fresh mapping from this selection's immutable member bytes."""
        raw_members = dict(self.members)
        raw = raw_members.get(name)
        if raw is None:
            if name == "donor":
                return {}
            raise ValueError(f"required demographic member is absent: {name}")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"selected demographic {name} member is malformed in {self.layout} layout"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(
                f"selected demographic {name} member must contain a JSON object"
            )
        return cast("dict[str, Any]", payload)


def _layout_member_paths(
    root: Path,
    layout: _DemographyLayout,
) -> dict[str, Path]:
    """Resolve every member path for one declared demographic layout."""
    return {
        member: root / relative_path
        for member, relative_path in _LAYOUT_PATHS[layout].items()
    }


def _select_demography_layout(
    root: Path,
    requested_layout: _DemographyLayout | None,
) -> tuple[_DemographyLayout, dict[str, Path]]:
    """Select one complete layout before reading any demographic member."""
    layout_paths = {
        layout: _layout_member_paths(root, layout) for layout in _LAYOUT_PATHS
    }
    complete_layouts = tuple(
        layout
        for layout, paths in layout_paths.items()
        if all(paths[member].is_file() for member in _REQUIRED_LAYOUT_MEMBERS)
    )

    if requested_layout is not None:
        if requested_layout not in _LAYOUT_PATHS:
            raise ValueError(f"unsupported demographic layout: {requested_layout}")
        selected_paths = layout_paths[requested_layout]
        if not all(selected_paths[member].is_file() for member in _REQUIRED_LAYOUT_MEMBERS):
            raise FileNotFoundError(
                f"selected demographic layout is incomplete under {root}: "
                f"{requested_layout}"
            )
        selected_donor = selected_paths["donor"]
        if selected_donor.exists() and not selected_donor.is_file():
            raise ValueError(
                f"selected demographic donor member is not a file: {selected_donor}"
            )
        other_layout = "legacy" if requested_layout == "new" else "new"
        other_members = tuple(
            member
            for member, path in layout_paths[other_layout].items()
            if path.exists()
        )
        if other_members and not all(
            layout_paths[other_layout][member].is_file()
            for member in _REQUIRED_LAYOUT_MEMBERS
        ):
            raise ValueError(
                "demographic layouts are mixed or incomplete; explicit selection "
                f"cannot ignore {other_layout} members {other_members}"
            )
        return requested_layout, selected_paths

    if len(complete_layouts) > 1:
        raise ValueError(
            "multiple complete demographic layouts are present; "
            "select one explicitly"
        )
    if len(complete_layouts) == 1:
        selected_layout = complete_layouts[0]
        other_layout = "legacy" if selected_layout == "new" else "new"
        other_members = tuple(
            member
            for member, path in layout_paths[other_layout].items()
            if path.exists()
        )
        if other_members:
            raise ValueError(
                "demographic layouts are mixed; "
                f"{selected_layout} is complete but {other_layout} has "
                f"members {other_members}"
            )
        selected_donor = layout_paths[selected_layout]["donor"]
        if selected_donor.exists() and not selected_donor.is_file():
            raise ValueError(
                f"selected demographic donor member is not a file: {selected_donor}"
            )
        return selected_layout, layout_paths[selected_layout]

    present_members = tuple(
        (layout, member)
        for layout, paths in layout_paths.items()
        for member, path in paths.items()
        if path.exists()
    )
    if present_members:
        raise ValueError(
            "demographic layout is incomplete; required targets and priors "
            f"were not found as one declared snapshot: {present_members}"
        )
    raise FileNotFoundError(f"no complete demographic layout exists under {root}")


def _member_signature(path: Path) -> tuple[int, int, int, int, int]:
    """Return identity fields used to detect replacement during one read."""
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _validate_demography_payload(
    layout: _DemographyLayout,
    targets: dict[str, Any],
    priors: dict[str, Any],
    donor: dict[str, Any],
) -> None:
    """Refuse malformed or shape-incompatible bytes for every sibling reader."""
    payload = {**targets, **priors, **donor}
    if "state_ids" not in payload:
        raise ValueError("selected demographic targets must include state_ids")
    payload.setdefault("entrant_state_totals", [0.0] * len(payload["state_ids"]))
    payload.setdefault("metadata", {})
    payload["metadata"] = {**payload["metadata"], "demography_layout": layout}
    UkraineDemographyArtifacts.model_validate(payload)


def _read_demography_selection(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> _DemographyReadSelection:
    """Select and freeze one known 2-required/1-optional layout per call."""
    root_path = Path(root)
    selected_layout, selected_paths = _select_demography_layout(root_path, layout)
    selected_members = {
        name: path
        for name, path in selected_paths.items()
        if name in _REQUIRED_LAYOUT_MEMBERS or path.exists()
    }
    for name, path in selected_members.items():
        if not path.is_file():
            raise ValueError(f"selected demographic {name} member is not a file: {path}")

    before = {name: _member_signature(path) for name, path in selected_members.items()}
    member_bytes = tuple(
        (name, selected_members[name].read_bytes()) for name in sorted(selected_members)
    )
    after = {name: _member_signature(path) for name, path in selected_members.items()}
    if before != after:
        raise ValueError("demographic layout changed while its members were read")

    current_layout, current_paths = _select_demography_layout(root_path, layout)
    current_members = {
        name: path
        for name, path in current_paths.items()
        if name in _REQUIRED_LAYOUT_MEMBERS or path.exists()
    }
    if current_layout != selected_layout or current_members != selected_members:
        raise ValueError("demographic layout membership changed while it was read")

    basis = build_generation_basis(
        basis_kind="data_forge.ukraine.demography.read_selection",
        generator_rule_version=_DEMOGRAPHY_READ_PROFILE,
        members=(
            (f"{selected_layout}/{name}", raw)
            for name, raw in member_bytes
        ),
    )
    selection = _DemographyReadSelection(
        layout=selected_layout,
        members=member_bytes,
        basis=basis,
    )
    _validate_demography_payload(
        selected_layout,
        selection.payload("targets"),
        selection.payload("priors"),
        selection.payload("donor"),
    )
    return selection


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


def load_reconciled_targets(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> dict[str, Any]:
    """Load targets only after selecting and validating one complete layout."""
    return _read_demography_selection(root, layout=layout).payload("targets")


def load_transition_priors(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> dict[str, Any]:
    """Load priors only after selecting and validating one complete layout."""
    return _read_demography_selection(root, layout=layout).payload("priors")


def load_donor_pool(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> dict[str, Any]:
    """Load the optional donor only from one selected, validated layout."""
    return _read_demography_selection(root, layout=layout).payload("donor")


def load_demography_artifacts(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> UkraineDemographyArtifacts:
    """Load and validate one declared Ukraine demographic layout.

    Without ``layout``, exactly one complete new or legacy layout must be
    present.  A caller may select a layout explicitly when both complete
    snapshots are intentionally available; members are then read only from
    that selected layout.
    """
    selection = _read_demography_selection(root, layout=layout)
    targets = selection.payload("targets")
    priors = selection.payload("priors")
    donor = selection.payload("donor")
    payload = {
        **targets,
        **priors,
        **donor,
    }
    payload.setdefault("entrant_state_totals", [0.0] * len(payload["state_ids"]))
    payload.setdefault("metadata", {})
    payload["metadata"] = {
        **payload["metadata"],
        "demography_layout": selection.layout,
    }
    return UkraineDemographyArtifacts.model_validate(payload)


__all__ = [
    "UkraineDemographyArtifacts",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
]
