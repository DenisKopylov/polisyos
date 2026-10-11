"""Typed demographic artifact readers for Ukraine static-aging inputs."""

from __future__ import annotations

import json
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


def _to_numpy(value: object, *, dtype: npt.DTypeLike = float) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value.astype(dtype, copy=False)
    return np.asarray(value, dtype=dtype)


def _read_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


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


def _layout_member_paths(
    root: Path,
    layout: _DemographyLayout,
) -> dict[str, Path]:
    """Resolve every member path for one declared demographic layout."""
    return {member: root / relative_path for member, relative_path in _LAYOUT_PATHS[layout].items()}


def _classify_member_entry(path: Path) -> Literal["absent", "file", "invalid"]:
    """Distinguish a missing member from a present invalid filesystem entry.

    A symlink to a regular file remains readable. Broken links, directories,
    non-file entries, and inaccessible or malformed parent entries are invalid
    supplied members rather than evidence that an optional member was omitted.
    """
    try:
        path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        for ancestor in path.parents:
            try:
                ancestor.lstat()
            except (FileNotFoundError, NotADirectoryError):
                continue
            except OSError:
                return "invalid"
            if not ancestor.is_dir():
                return "invalid"
            return "absent"
        return "absent"
    except OSError:
        return "invalid"
    return "file" if path.is_file() else "invalid"


def _select_demography_layout(
    root: Path,
    requested_layout: _DemographyLayout | None,
    *,
    standalone_member: str | None = None,
) -> tuple[_DemographyLayout, dict[str, Path]]:
    """Select one complete layout before reading any demographic member.

    Scalar compatibility readers may use an isolated single-member source only
    without an explicit layout selection. Explicit selection requires a complete
    targets-and-priors snapshot even when one scalar member exists.
    """
    layout_paths = {layout: _layout_member_paths(root, layout) for layout in _LAYOUT_PATHS}
    member_states = {
        layout: {member: _classify_member_entry(path) for member, path in paths.items()}
        for layout, paths in layout_paths.items()
    }
    invalid_members = tuple(
        (layout, member)
        for layout, states in member_states.items()
        for member, state in states.items()
        if state == "invalid"
    )
    if invalid_members:
        raise ValueError(
            f"demographic member is present but is not a readable file: {invalid_members}"
        )
    present_members = tuple(
        (layout, member)
        for layout, states in member_states.items()
        for member, state in states.items()
        if state != "absent"
    )
    complete_layouts = tuple(
        layout
        for layout, states in member_states.items()
        if all(states[member] == "file" for member in _REQUIRED_LAYOUT_MEMBERS)
    )

    if requested_layout is not None:
        if requested_layout not in _LAYOUT_PATHS:
            raise ValueError(f"unsupported demographic layout: {requested_layout}")
        selected_paths = layout_paths[requested_layout]
        missing_required = tuple(
            member
            for member in _REQUIRED_LAYOUT_MEMBERS
            if member_states[requested_layout][member] == "absent"
        )
        if missing_required:
            raise FileNotFoundError(
                f"selected demographic layout is incomplete under {root}: "
                f"{requested_layout} is missing {missing_required}"
            )
        other_layout = "legacy" if requested_layout == "new" else "new"
        other_members = tuple(
            member for member, state in member_states[other_layout].items() if state != "absent"
        )
        if other_members and not all(
            member_states[other_layout][member] == "file" for member in _REQUIRED_LAYOUT_MEMBERS
        ):
            raise ValueError(
                "demographic layouts are mixed or incomplete; explicit selection "
                f"cannot ignore {other_layout} members {other_members}"
            )
        return requested_layout, selected_paths

    if len(complete_layouts) > 1:
        raise ValueError("multiple complete demographic layouts are present; select one explicitly")
    if len(complete_layouts) == 1:
        selected_layout = complete_layouts[0]
        other_layout = "legacy" if selected_layout == "new" else "new"
        other_members = tuple(
            member for member, state in member_states[other_layout].items() if state != "absent"
        )
        if other_members:
            raise ValueError(
                "demographic layouts are mixed; "
                f"{selected_layout} is complete but {other_layout} has "
                f"members {other_members}"
            )
        return selected_layout, layout_paths[selected_layout]

    if standalone_member is not None and len(present_members) == 1:
        selected_layout, selected_member = present_members[0]
        if (
            selected_member == standalone_member
            and member_states[selected_layout][selected_member] == "file"
        ):
            return selected_layout, layout_paths[selected_layout]
    if present_members:
        raise ValueError(
            "demographic layout is incomplete; required targets and priors "
            f"were not found as one declared snapshot: {present_members}"
        )
    raise FileNotFoundError(f"no complete demographic layout exists under {root}")


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
    """Load targets from one complete layout or an isolated scalar source.

    When both complete layouts exist, callers must select one with ``layout``.
    A sole isolated targets file remains readable for historical scalar callers;
    mixed and multi-member incomplete layouts are rejected.
    """
    _selected_layout, paths = _select_demography_layout(
        Path(root), layout, standalone_member="targets"
    )
    return _read_json(paths["targets"])


def load_transition_priors(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> dict[str, Any]:
    """Load priors from one complete layout or an isolated scalar source.

    When both complete layouts exist, callers must select one with ``layout``.
    A sole isolated priors file remains readable for scalar callers; mixed and
    multi-member incomplete layouts are rejected.
    """
    _selected_layout, paths = _select_demography_layout(
        Path(root), layout, standalone_member="priors"
    )
    return _read_json(paths["priors"])


def load_donor_pool(
    root: str | Path,
    *,
    layout: _DemographyLayout | None = None,
) -> dict[str, Any]:
    """Load the optional donor pool from one selected demographic layout.

    With no layout selection and no demographic inputs, an absent donor is empty.
    A selected complete layout may also omit its optional donor; an explicit layout
    selection still requires that layout's targets and priors. A sole isolated donor
    file remains readable, while mixed and multi-member incomplete layouts are rejected.
    """
    root_path = Path(root)
    try:
        _selected_layout, paths = _select_demography_layout(
            root_path, layout, standalone_member="donor"
        )
    except FileNotFoundError:
        if layout is not None:
            raise
        return {}
    donor_path = paths["donor"]
    return _read_json(donor_path) if donor_path.is_file() else {}


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
    root_path = Path(root)
    selected_layout, selected_paths = _select_demography_layout(root_path, layout)
    targets = _read_json(selected_paths["targets"])
    priors = _read_json(selected_paths["priors"])
    donor = _read_json(selected_paths["donor"]) if selected_paths["donor"].is_file() else {}
    payload = {
        **targets,
        **priors,
        **donor,
    }
    payload.setdefault("entrant_state_totals", [0.0] * len(payload["state_ids"]))
    payload.setdefault("metadata", {})
    payload["metadata"] = {
        **payload["metadata"],
        "demography_layout": selected_layout,
    }
    return UkraineDemographyArtifacts.model_validate(payload)


__all__ = [
    "UkraineDemographyArtifacts",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
]
