"""Typed demographic artifact readers for Ukraine static-aging inputs."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar, Literal

import numpy as np
import numpy.typing as npt
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from .source_inventory import (
    DemographyRoleProjection,
    DemographySourceEvidence,
    DemographySourceRequest,
    HistoricalLayoutRequest,
    InventorySourceRequest,
    ResolvedDemographySource,
    SourceResolutionRefusalError,
    read_demography_role,
    resolve_demography_source,
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


def _layout_member_paths(
    root: Path,
    layout: _DemographyLayout,
) -> dict[str, Path]:
    """Resolve every member path for one declared demographic layout."""
    return {
        member: root / relative_path
        for member, relative_path in _LAYOUT_PATHS[layout].items()
    }


def _classify_member_entry(path: Path) -> Literal["absent", "file", "invalid"]:
    """Distinguish a missing member from a present invalid filesystem entry."""
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
) -> tuple[_DemographyLayout | None, dict[str, Path]]:
    """Select one complete layout; mixed, multiple, or malformed layouts refuse."""
    layout_paths = {
        layout: _layout_member_paths(root, layout) for layout in _LAYOUT_PATHS
    }
    member_states = {
        layout: {
            member: _classify_member_entry(path) for member, path in paths.items()
        }
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
            member
            for member, state in member_states[other_layout].items()
            if state != "absent"
        )
        if other_members and not all(
            member_states[other_layout][member] == "file"
            for member in _REQUIRED_LAYOUT_MEMBERS
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
            member
            for member, state in member_states[other_layout].items()
            if state != "absent"
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
    if (
        standalone_member == "donor"
        and requested_layout is None
        and root.is_dir()
    ):
        return None, {}
    raise FileNotFoundError(f"no complete demographic layout exists under {root}")


class UkraineDemographyArtifacts(BaseModel):
    """Contract-v2 demographic inputs with required candidate/legacy source evidence.

    The ``source_evidence`` field is required; supported readers populate it from
    the resolved source instead of defaulting or inferring it.
    """

    contract_id: ClassVar[str] = "data_forge.ukraine.demography.artifacts.v2"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    state_ids: list[str]
    target_state_totals: Any
    entrant_state_totals: Any
    transition_prior_matrix: Any
    source_evidence: DemographySourceEvidence
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


def _resolve_reader_source(
    root: str | Path | None,
    layout: _DemographyLayout | None,
    source: DemographySourceRequest | None,
    *,
    standalone_member: str | None = None,
) -> ResolvedDemographySource:
    """Resolve an inventory request or enter the bounded historical adapter."""
    if source is not None:
        if root is not None or layout is not None:
            raise ValueError("provide either an inventory source or a historical filesystem root")
        if isinstance(source, HistoricalLayoutRequest):
            return resolve_demography_source(source, standalone_member=standalone_member)
        return resolve_demography_source(source)
    if root is None:
        raise ValueError("provide an inventory source or a historical filesystem root")
    if layout is not None and (
        not isinstance(layout, str) or layout not in _LAYOUT_PATHS
    ):
        raise ValueError(f"unsupported demographic layout: {layout}")
    return resolve_demography_source(
        HistoricalLayoutRequest(kind="historical_layout", root=Path(root), layout=layout),
        standalone_member=standalone_member,
    )


def _artifacts_from_resolved_source(
    resolved: ResolvedDemographySource,
    *,
    allow_unknown_optional_donor: bool = False,
) -> UkraineDemographyArtifacts:
    """Validate every present member in one resolved snapshot as a typed bundle."""
    targets = read_demography_role(resolved, "targets").payload
    priors = read_demography_role(resolved, "priors").payload
    payload = {**targets, **priors}
    unknown_optional_donor_absent = (
        allow_unknown_optional_donor
        and resolved.status == "candidate_only"
        and resolved.donor_disposition == "not_established"
        and resolved.evidence.donor_disposition == "not_established"
        and "donor.json" not in resolved.member_bytes
    )
    if not unknown_optional_donor_absent:
        payload.update(read_demography_role(resolved, "donor").payload)
    legacy_entrant_omission = "entrant_state_totals" not in payload
    if legacy_entrant_omission:
        if resolved.status != "legacy_limited":
            raise SourceResolutionRefusalError(
                "entrant_measure_not_materialized",
                "candidate inventory requires entrant_state_totals",
            )
        state_ids = payload.get("state_ids")
        if (
            not isinstance(state_ids, list)
            or not state_ids
            or any(not isinstance(state_id, str) or not state_id for state_id in state_ids)
            or len(state_ids) != len(set(state_ids))
        ):
            raise SourceResolutionRefusalError(
                "legacy_state_axis_not_materialized",
                "historical entrant compatibility requires a complete ordered state axis",
            )
        payload["entrant_state_totals"] = [0.0] * len(state_ids)
        note = (
            "legacy compatibility projection: an omitted entrant_state_totals field is "
            "represented as zeros for the historical reader shape; this is not a measured "
            "zero and entrant-measure provenance remains not_established"
        )
        resolved = replace(
            resolved,
            evidence=resolved.evidence.model_copy(
                update={
                    "compatibility_notes": [
                        *resolved.evidence.compatibility_notes,
                        note,
                    ]
                }
            ),
        )
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise SourceResolutionRefusalError(
            "member_metadata_malformed", "demography metadata must be a JSON object"
        )
    payload["metadata"] = {
        **metadata,
        "demography_source_status": resolved.status,
        "demography_source_identity": resolved.source_identity,
        "demography_source_evidence": resolved.evidence.model_dump(mode="json"),
    }
    if legacy_entrant_omission:
        payload["metadata"]["entrant_state_totals_compatibility"] = (
            "historical_zero_projection_for_omitted_field"
        )
        payload["metadata"]["entrant_state_totals_measurement_status"] = "not_established"
    if resolved.evidence.source_layout is not None:
        payload["metadata"]["demography_layout"] = resolved.evidence.source_layout
    payload["source_evidence"] = resolved.evidence
    try:
        return UkraineDemographyArtifacts.model_validate(payload)
    except ValidationError as exc:
        if resolved.status != "candidate_only":
            raise
        raise SourceResolutionRefusalError(
            "demography_bundle_invalid",
            "candidate demographic members do not form one valid typed snapshot",
        ) from exc


def _read_demography_role(
    root: str | Path | None,
    *,
    layout: _DemographyLayout | None,
    source: DemographySourceRequest | None,
    role: Literal["targets", "priors", "donor"],
    standalone_member: Literal["targets", "priors", "donor"],
) -> DemographyRoleProjection:
    """Validate candidate snapshots as a whole before returning one role."""
    resolved = _resolve_reader_source(
        root, layout, source, standalone_member=standalone_member
    )
    if resolved.status == "candidate_only":
        _artifacts_from_resolved_source(
            resolved,
            allow_unknown_optional_donor=role in ("targets", "priors"),
        )
    return read_demography_role(resolved, role)


def load_reconciled_targets(
    root: str | Path | None = None,
    *,
    layout: _DemographyLayout | None = None,
    source: DemographySourceRequest | None = None,
) -> DemographyRoleProjection:
    """Load targets as a ``DemographyRoleProjection`` implementing ``Mapping``.

    The projection preserves mapping-style reads and exposes its source evidence.
    """
    return _read_demography_role(
        root, layout=layout, source=source, role="targets", standalone_member="targets"
    )


def load_transition_priors(
    root: str | Path | None = None,
    *,
    layout: _DemographyLayout | None = None,
    source: DemographySourceRequest | None = None,
) -> DemographyRoleProjection:
    """Load priors as a ``DemographyRoleProjection`` implementing ``Mapping``.

    The projection preserves mapping-style reads and exposes its source evidence.
    """
    return _read_demography_role(
        root, layout=layout, source=source, role="priors", standalone_member="priors"
    )


def load_donor_pool(
    root: str | Path | None = None,
    *,
    layout: _DemographyLayout | None = None,
    source: DemographySourceRequest | None = None,
) -> DemographyRoleProjection:
    """Load donors as a ``DemographyRoleProjection`` implementing ``Mapping``.

    The projection preserves mapping-style reads and exposes its source evidence.
    """
    return _read_demography_role(
        root, layout=layout, source=source, role="donor", standalone_member="donor"
    )


def load_demography_artifacts(
    root: str | Path | None = None,
    *,
    layout: _DemographyLayout | None = None,
    source: DemographySourceRequest | None = None,
) -> UkraineDemographyArtifacts:
    """Resolve and validate one complete demographic snapshot."""
    resolved = _resolve_reader_source(root, layout, source)
    return _artifacts_from_resolved_source(resolved)

__all__ = [
    "DemographyRoleProjection",
    "DemographySourceEvidence",
    "DemographySourceRequest",
    "HistoricalLayoutRequest",
    "InventorySourceRequest",
    "SourceResolutionRefusalError",
    "UkraineDemographyArtifacts",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
]
