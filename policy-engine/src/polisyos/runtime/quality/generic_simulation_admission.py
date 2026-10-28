"""Virtual candidate-only admission owner for a generic controlled N5 profile.

This file is an un-applied implementation draft. It introduces a separate
server-selected profile; it does not reuse candidate-scenario offer semantics
or establish currentness, causal truth, N9, S8, or publication authority.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactSameInputClosureInfo,
    ArtifactTenantContextInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationContextInputs,
)
from polisyos.runtime.quality.cycle_substrate import (
    CycleSubstrateContext,
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextOwnerError,
    VerifiedNLJobScope,
    build_cycle_substrate_context,
    candidate_cycle_substrate_source_profile_selection,
    cycle_job_design_problem_ref,
    cycle_job_profile_selection_ref,
    generic_n4_child_profile_selection_ref,
    revalidate_cycle_substrate_context,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationRequest,
)
from polisyos.runtime.quality.substrate_registry import load_substrate_registry
from polisyos.runtime.quality.world_model_record import (
    WORLD_MODEL_RECORD_SCHEMA_V2_VERSION,
    load_world_model_record,
    world_model_artifact_views,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

_HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"
_PROFILE_KIND = "runtime.quality.generic_cycle_simulation_profile"
_PROFILE_SCHEMA = "policyos.runtime.generic_cycle_simulation_profile.v1"
_PROFILE_SCHEMA_VERSION = "1.0"
_CHILD_PROFILE_FAMILY_KIND = "runtime.quality.generic_cycle_simulation_child_profile_family"
_CHILD_PROFILE_FAMILY_SCHEMA = "policyos.runtime.generic_cycle_simulation_child_profile_family.v1"
_CHILD_PROFILE_FAMILY_SCHEMA_VERSION = "1.0"
_PROFILE_CANON = canon.CanonSpec(forbid_floats=False)
_PROFILE_LIMITATIONS = frozenset(
    {
        "controlled_inputs_only",
        "currentness_not_established",
        "n5_simulation_not_world_evidence",
        "n9_not_admitted",
        "s8_blocked",
        "source_truth_not_established",
    }
)


class _StrictModel(BaseModel):
    """Immutable strict base for the virtual request and handoff DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _GenericN5VerifiedMismatchError(CycleSubstrateContextOwnerError):
    """An independently compared N5 owner binding is demonstrably unequal."""


class GenericCycleN5RequestProfileV1(_StrictModel):
    """Server-owned N5 request settings for one exact generic profile."""

    schema_version: Literal["policyos.runtime.generic_cycle_n5_request_profile.v1"] = (
        "policyos.runtime.generic_cycle_n5_request_profile.v1"
    )
    resource: Literal["ncm_parallel_worlds"] = "ncm_parallel_worlds"
    budget_ref: str = Field(min_length=1, strict=True)
    horizon: HorizonSpec
    baseline_state: dict[str, float] = Field(default_factory=dict)
    comparator_refs: tuple[str, ...] = ()
    seed: int = Field(default=0, strict=True)
    replications: int = Field(default=1, ge=1, strict=True)

    @field_validator("baseline_state")
    @classmethod
    def _finite_baseline(cls, values: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError("generic_cycle_n5_baseline_non_finite")
        return values

    @field_validator("comparator_refs")
    @classmethod
    def _unique_comparators(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values) or len(values) != len(set(values)):
            raise ValueError("generic_cycle_n5_comparator_ref_invalid")
        return values


class GenericCycleSimulationProfileV1(_StrictModel):
    """Server-owned context and request profile for generic candidate-only N5."""

    schema_version: Literal[_PROFILE_SCHEMA] = _PROFILE_SCHEMA
    profile_id: str = Field(min_length=1, strict=True)
    profile_selection_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    profile_selection_kind: Literal["problem", "n4_candidate_child"] = "problem"
    input_purpose: Literal["controlled_generic_cycle_simulation"] = (
        "controlled_generic_cycle_simulation"
    )
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    world_model_record_ref: ArtifactRef
    substrate_registry_ref: ArtifactRef
    selected_ncm_ref: ArtifactRef
    context_inputs: CandidateSimulationContextInputs
    n5: GenericCycleN5RequestProfileV1
    limitations: tuple[
        Literal[
            "controlled_inputs_only",
            "currentness_not_established",
            "n5_simulation_not_world_evidence",
            "n9_not_admitted",
            "s8_blocked",
            "source_truth_not_established",
        ],
        ...,
    ]
    content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_profile(self) -> GenericCycleSimulationProfileV1:
        typed_refs = (
            (self.world_model_record_ref, "runtime.quality.world_model_record"),
            (
                self.substrate_registry_ref,
                "runtime.quality.production_data_substrate_registry",
            ),
            (self.selected_ncm_ref, "ir.ncm_spec"),
        )
        if any(
            type(ref) is not ArtifactRef or ref.kind != kind or ref.media_type != "application/json"
            for ref, kind in typed_refs
        ):
            raise ValueError("generic_cycle_simulation_profile_ref_kind_invalid")
        # This initial controlled profile supports the one WMR-default NCM view.
        # A selected-view NCM requires its own declaration owner and is refused.
        if self.selected_ncm_ref.manifest_profile_sha256 is not None:
            raise ValueError("generic_cycle_simulation_ncm_view_source_not_established")
        if len(self.limitations) != len(set(self.limitations)) or not _PROFILE_LIMITATIONS.issubset(
            self.limitations
        ):
            raise ValueError("generic_cycle_simulation_profile_limitation_missing")
        if (
            self.context_inputs.world_model_record.schema_version
            != WORLD_MODEL_RECORD_SCHEMA_V2_VERSION
        ):
            raise ValueError("generic_cycle_simulation_wmr_v2_required")
        expected = gy_content_hash(self.model_dump(mode="json", exclude={"content_hash"}))
        if self.content_hash != expected:
            raise ValueError("generic_cycle_simulation_profile_content_hash_mismatch")
        return self


class GenericCycleSimulationChildProfileMemberV1(_StrictModel):
    """One immutable child-profile member in a pre-N4 configured family."""

    profile_id: str = Field(min_length=1, strict=True)
    profile_selection_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    profile_content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)
    profile_ref: ArtifactRef

    @model_validator(mode="after")
    def _typed_profile_ref(self) -> GenericCycleSimulationChildProfileMemberV1:
        if (
            type(self.profile_ref) is not ArtifactRef
            or self.profile_ref.kind != _PROFILE_KIND
            or self.profile_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_child_family_profile_ref_invalid")
        return self


class GenericCycleSimulationChildProfileFamilyV1(_StrictModel):
    """Owner-persisted complete configured child tuple, written before N4."""

    schema_version: Literal[_CHILD_PROFILE_FAMILY_SCHEMA] = _CHILD_PROFILE_FAMILY_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    job_id: str = Field(min_length=1, strict=True)
    run_id: str = Field(min_length=1, strict=True)
    tenant_id: str = Field(min_length=1, strict=True)
    cell_id: str = Field(min_length=1, strict=True)
    parent_problem_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    parent_context_hash: str = Field(pattern=_HASH_PATTERN, strict=True)
    parent_profile_id: str = Field(min_length=1, strict=True)
    parent_profile_selection_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    parent_context_job_ref: ArtifactRef
    parent_profile_ref: ArtifactRef
    parent_profile_content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)
    children: tuple[GenericCycleSimulationChildProfileMemberV1, ...]
    content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _complete_child_tuple(self) -> GenericCycleSimulationChildProfileFamilyV1:
        if (
            type(self.parent_context_job_ref) is not ArtifactRef
            or self.parent_context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.parent_context_job_ref.media_type != "application/json"
            or type(self.parent_profile_ref) is not ArtifactRef
            or self.parent_profile_ref.kind != _PROFILE_KIND
            or self.parent_profile_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_child_family_parent_ref_invalid")
        ids = tuple(member.profile_id for member in self.children)
        if not ids or ids != tuple(sorted(set(ids))):
            raise ValueError("generic_cycle_simulation_child_family_tuple_incomplete")
        selections = tuple(member.profile_selection_ref for member in self.children)
        if len(selections) != len(set(selections)):
            raise ValueError("generic_cycle_simulation_child_family_selection_ambiguous")
        expected = gy_content_hash(self.model_dump(mode="json", exclude={"content_hash"}))
        if self.content_hash != expected:
            raise ValueError("generic_cycle_simulation_child_family_content_hash_mismatch")
        return self


class GenericCycleSimulationContextOfferV1(_StrictModel):
    """Verified configured profile and context before the current-job write."""

    context: CycleSubstrateContext
    profile: GenericCycleSimulationProfileV1
    profile_ref: ArtifactRef
    n4_child_profile_family_ref: ArtifactRef | None = None
    parent_problem: DesignProblem | None = None
    parent_handoff: GenericCycleSimulationContextHandoffV1 | None = None

    @model_validator(mode="after")
    def _bind_offer(self) -> GenericCycleSimulationContextOfferV1:
        if (
            self.profile_ref.kind != _PROFILE_KIND
            or self.profile_ref.media_type != "application/json"
            or self.context.authority_purpose != "cycle_input_candidate_only"
        ):
            raise ValueError("generic_cycle_simulation_offer_binding_invalid")
        if self.n4_child_profile_family_ref is not None and (
            type(self.n4_child_profile_family_ref) is not ArtifactRef
            or self.n4_child_profile_family_ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or self.n4_child_profile_family_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_offer_family_ref_invalid")
        if (self.parent_problem is None) != (self.parent_handoff is None):
            raise ValueError("generic_cycle_simulation_offer_parent_binding_incomplete")
        if self.n4_child_profile_family_ref is not None and (
            self.parent_handoff is None
            or self.parent_handoff.n4_child_profile_family_ref != self.n4_child_profile_family_ref
            or self.profile.profile_selection_kind != "n4_candidate_child"
        ):
            raise ValueError("generic_cycle_simulation_offer_family_parent_mismatch")
        return self


class GenericCycleSimulationContextHandoffV1(_StrictModel):
    """Persisted generic context/profile pair bound to one active job lease."""

    context: CycleSubstrateContext
    context_job_ref: ArtifactRef
    profile: GenericCycleSimulationProfileV1
    profile_ref: ArtifactRef
    job_id: str = Field(min_length=1, strict=True)
    run_id: str = Field(min_length=1, strict=True)
    tenant_id: str = Field(min_length=1, strict=True)
    cell_id: str = Field(min_length=1, strict=True)
    n4_child_profile_family_ref: ArtifactRef | None = None
    currentness_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"

    @model_validator(mode="after")
    def _bind_handoff(self) -> GenericCycleSimulationContextHandoffV1:
        if (
            self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.profile_ref.kind != _PROFILE_KIND
            or self.profile_ref.media_type != "application/json"
            or self.context.authority_purpose != self.authority_purpose
        ):
            raise ValueError("generic_cycle_simulation_handoff_ref_invalid")
        if self.n4_child_profile_family_ref is not None and (
            type(self.n4_child_profile_family_ref) is not ArtifactRef
            or self.n4_child_profile_family_ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or self.n4_child_profile_family_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_handoff_family_ref_invalid")
        if (
            self.profile.profile_selection_kind == "n4_candidate_child"
            and self.n4_child_profile_family_ref is None
        ):
            raise ValueError("generic_cycle_simulation_child_handoff_family_missing")
        return self


GenericCycleSimulationContextOfferV1.model_rebuild()


class GenericCycleSimulationChildSelectionV1(_StrictModel):
    """Family-verified identity for selecting a configured derived-child profile.

    The complete child problem and its N4/family lineage remain in the record.
    Only the three dynamic lineage references are omitted from the profile key
    by the canonical cycle-substrate selector after family replay.
    """

    schema_version: Literal["policyos.runtime.generic_cycle_simulation_child_selection.v1"] = (
        "policyos.runtime.generic_cycle_simulation_child_selection.v1"
    )
    node_ref: str = Field(min_length=1, strict=True)
    parent_ref: str = Field(min_length=1, strict=True)
    parent_problem: DesignProblem
    parent_handoff: GenericCycleSimulationContextHandoffV1
    problem: DesignProblem
    full_child_problem_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    parent_problem_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    source_result_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    source_atom_refs: tuple[str, ...] = ()
    semantic_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    n4_source_ref: ArtifactRef
    n4_child_profile_family_ref: ArtifactRef
    profile_selection_ref: str = Field(pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _verify_child_identity(self) -> GenericCycleSimulationChildSelectionV1:
        source = self.problem.runtime_hints.get("n4_candidate_child_source")
        if (
            type(self.n4_source_ref) is not ArtifactRef
            or self.n4_source_ref.kind != "runtime.generation_source_handoff"
            or self.n4_source_ref.media_type != "application/json"
            or type(self.n4_child_profile_family_ref) is not ArtifactRef
            or self.n4_child_profile_family_ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or self.n4_child_profile_family_ref.media_type != "application/json"
            or self.parent_handoff.n4_child_profile_family_ref != self.n4_child_profile_family_ref
            or cycle_job_design_problem_ref(self.parent_problem) != self.parent_problem_ref
            or self.parent_handoff.profile.profile_selection_kind != "problem"
            or self.parent_handoff.profile.profile_selection_ref
            != cycle_job_profile_selection_ref(self.parent_problem)
            or self.parent_handoff.context.design_problem_ref != self.parent_problem_ref
            or self.full_child_problem_ref != cycle_job_design_problem_ref(self.problem)
            or not isinstance(source, dict)
            or source.get("purpose") != "candidate_lever_exploration_only"
            or source.get("parent_design_problem_ref") != self.parent_problem_ref
            or source.get("source_result_ref") != self.source_result_ref
            or tuple(source.get("source_atom_refs", ())) != self.source_atom_refs
            or source.get("semantic_ref") != self.semantic_ref
            or not self.source_atom_refs
            or self.source_atom_refs != tuple(sorted(set(self.source_atom_refs)))
            or any(
                not isinstance(item, str) or not item.startswith("sha256:")
                for item in self.source_atom_refs
            )
            or self.profile_selection_ref
            != generic_n4_child_profile_selection_ref(
                self.problem,
                parent_problem_ref=self.parent_problem_ref,
                source_result_ref=self.source_result_ref,
                source_atom_refs=self.source_atom_refs,
                semantic_ref=self.semantic_ref,
            )
        ):
            raise ValueError("generic_cycle_simulation_child_selection_binding_mismatch")
        return self


_N5_INPUT_KIND = "runtime.quality.generic_cycle_simulation_n5_input"
_N5_INPUT_SCHEMA = "policyos.runtime.generic_cycle_simulation_n5_input.v1"
_N5_EXECUTION_KIND = "runtime.quality.generic_cycle_simulation_n5_execution"
_N5_EXECUTION_SCHEMA = "policyos.runtime.generic_cycle_simulation_n5_execution.v1"
_N5_EXECUTION_V2_SCHEMA = "policyos.runtime.generic_cycle_simulation_n5_execution.v2"
_N5_EXECUTION_V3_SCHEMA = "policyos.runtime.generic_cycle_simulation_n5_execution.v3"
_N5_REQUEST_BINDING_SCHEMA = "policyos.runtime.generic_cycle_simulation_n5_request_binding.v1"
_N5_REQUEST_BINDING_V2_SCHEMA = "policyos.runtime.generic_cycle_simulation_n5_request_binding.v2"
_N5_TYPED_CANON = canon.CanonSpec(forbid_floats=False, exclude_none=False)
_N5_TYPED_CANON_INFO = artifacts.CanonInfo.from_spec(_N5_TYPED_CANON)
_N5_TYPED_CANON_PROFILE_ID = (
    f"{_N5_TYPED_CANON_INFO.name}@{_N5_TYPED_CANON_INFO.version}:"
    f"{canon.fingerprint(_N5_TYPED_CANON_INFO.model_dump(mode='python'))}"
)


def _n5_typed_request_content_hash(request: JointSimulationRequest) -> str:
    """Hash the complete request with Core's pinned typed canonical profile."""
    return canon.fingerprint(
        {
            "schema_version": _N5_REQUEST_BINDING_V2_SCHEMA,
            "canon_profile_id": _N5_TYPED_CANON_PROFILE_ID,
            "request": request,
        },
        prefix=True,
        canon_spec=_N5_TYPED_CANON,
    )


def _n5_typed_execution_content_hash(record: object) -> str:
    """Hash a v3 execution body with the same typed canonical profile."""
    if type(record) is not GenericCycleSimulationN5ExecutionV3:
        raise TypeError("generic_cycle_simulation_n5_execution_v3_untyped")
    return canon.fingerprint(
        {
            "schema_version": _N5_EXECUTION_V3_SCHEMA,
            "execution": record.model_dump(mode="python", exclude={"content_hash"}),
        },
        prefix=True,
        canon_spec=_N5_TYPED_CANON,
    )


def _same_typed_public_value(left: object, right: object) -> bool:
    """Compare serialized public model values without lossy Python equality."""
    if type(left) is not type(right):
        return False
    if isinstance(left, BaseModel):
        return all(
            field.exclude is True
            or _same_typed_public_value(getattr(left, name), getattr(right, name))
            for name, field in type(left).model_fields.items()
        )
    if isinstance(left, Decimal):
        return left.as_tuple() == right.as_tuple()
    if isinstance(left, float):
        return left.hex() == right.hex()
    if isinstance(left, datetime):
        return (
            left.isoformat() == right.isoformat()
            and left.fold == right.fold
            and type(left.tzinfo) is type(right.tzinfo)
            and str(left.tzinfo) == str(right.tzinfo)
            and left.tzname() == right.tzname()
            and left.utcoffset() == right.utcoffset()
        )
    if isinstance(left, Enum):
        return _same_typed_public_value(left.value, right.value)
    if isinstance(left, Mapping):
        if len(left) != len(right):
            return False
        unmatched_right = list(right.items())
        for left_key, left_value in left.items():
            match_index = next(
                (
                    index
                    for index, (right_key, _) in enumerate(unmatched_right)
                    if _same_typed_public_value(left_key, right_key)
                ),
                None,
            )
            if match_index is None:
                return False
            _, right_value = unmatched_right.pop(match_index)
            if not _same_typed_public_value(left_value, right_value):
                return False
        return not unmatched_right
    if is_dataclass(left):
        return all(
            _same_typed_public_value(getattr(left, item.name), getattr(right, item.name))
            for item in fields(left)
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _same_typed_public_value(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, date):
        return left.isoformat() == right.isoformat()
    if type(left) in {str, int, bool, bytes, type(None)}:
        return bool(left == right)
    return False


def _validate_n5_typed_request_roundtrip(request: JointSimulationRequest) -> None:
    """Refuse a request if Core cannot reproduce every public typed value."""
    try:
        reopened = JointSimulationRequest.model_validate(
            canon.from_canonical_bytes(canon.to_canonical_bytes(request, _N5_TYPED_CANON))
        )
    except Exception as exc:
        raise ValueError("generic_cycle_simulation_n5_request_canonical_roundtrip_invalid") from exc
    if not _same_typed_public_value(request, reopened):
        raise ValueError("generic_cycle_simulation_n5_request_canonical_roundtrip_mismatch")


class GenericCycleSimulationN5InputV1(_StrictModel):
    """Persisted, source-bound N5 input for one server-owned generic profile."""

    schema_version: Literal[_N5_INPUT_SCHEMA] = _N5_INPUT_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    job_id: str = Field(min_length=1, strict=True)
    run_id: str = Field(min_length=1, strict=True)
    source_run_id: str = Field(min_length=1, strict=True)
    tenant_id: str = Field(min_length=1, strict=True)
    cell_id: str = Field(min_length=1, strict=True)
    design_problem_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    cycle_index: int = Field(ge=0, strict=True)
    n4_source_ref: ArtifactRef
    n4_child_profile_family_ref: ArtifactRef | None = None
    n4_child_profile_set_ref: ArtifactRef | None = None
    child_selection: GenericCycleSimulationChildSelectionV1 | None = None
    context_job_ref: ArtifactRef
    profile_ref: ArtifactRef
    profile: GenericCycleSimulationProfileV1
    candidate_id: str = Field(min_length=1, strict=True)
    candidate_atom_hash: str = Field(pattern=_HASH_PATTERN, strict=True)
    outcome_variable: str = Field(min_length=1, strict=True)
    n5: GenericCycleN5RequestProfileV1
    content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _bind_n5_input(self) -> GenericCycleSimulationN5InputV1:
        refs = (
            (self.n4_source_ref, "runtime.generation_source_handoff"),
            (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
            (self.profile_ref, _PROFILE_KIND),
        )
        if any(
            type(ref) is not ArtifactRef or ref.kind != kind or ref.media_type != "application/json"
            for ref, kind in refs
        ):
            raise ValueError("generic_cycle_simulation_n5_input_ref_invalid")
        if self.n4_child_profile_family_ref is not None and (
            type(self.n4_child_profile_family_ref) is not ArtifactRef
            or self.n4_child_profile_family_ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or self.n4_child_profile_family_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_n5_child_family_ref_invalid")
        if self.n4_child_profile_set_ref is not None and (
            type(self.n4_child_profile_set_ref) is not ArtifactRef
            or self.n4_child_profile_set_ref.kind
            != "runtime.quality.recursive_n4_child_profile_set"
            or self.n4_child_profile_set_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_n5_child_set_ref_invalid")
        if self.n5 != self.profile.n5:
            raise ValueError("generic_cycle_simulation_n5_profile_mismatch")
        if self.profile.profile_selection_kind == "n4_candidate_child" and (
            self.n4_child_profile_family_ref is None
            or self.n4_child_profile_set_ref is None
            or self.child_selection is None
        ):
            raise ValueError("generic_cycle_simulation_n5_child_family_or_set_missing")
        if self.profile.profile_selection_kind == "problem" and (
            self.child_selection is not None or self.n4_child_profile_set_ref is not None
        ):
            raise ValueError("generic_cycle_simulation_parent_input_has_child_binding")
        if self.child_selection is not None and (
            cycle_job_design_problem_ref(self.child_selection.problem) != self.design_problem_ref
            or self.child_selection.profile_selection_ref != self.profile.profile_selection_ref
            or self.child_selection.n4_child_profile_family_ref != self.n4_child_profile_family_ref
        ):
            raise ValueError("generic_cycle_simulation_n5_child_selection_mismatch")
        if self.outcome_variable not in self.n5.baseline_state:
            raise ValueError("generic_cycle_simulation_n5_outcome_baseline_missing")
        expected = gy_content_hash(self.model_dump(mode="json", exclude={"content_hash"}))
        if self.content_hash != expected:
            raise ValueError("generic_cycle_simulation_n5_input_content_hash_mismatch")
        return self


class GenericCycleSimulationN5RequestBindingV1(_StrictModel):
    """Bind the complete controller request to the persisted N5 input."""

    schema_version: Literal[_N5_REQUEST_BINDING_SCHEMA] = _N5_REQUEST_BINDING_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    request: JointSimulationRequest
    request_content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _request_content_is_bound(self) -> GenericCycleSimulationN5RequestBindingV1:
        expected = (
            _n5_typed_request_content_hash(self.request)
            if self.schema_version == _N5_REQUEST_BINDING_V2_SCHEMA
            else gy_content_hash(self.request.model_dump(mode="json"))
        )
        if self.request_content_hash != expected:
            raise ValueError("generic_cycle_simulation_n5_request_content_hash_mismatch")
        return self


class GenericCycleSimulationN5RequestBindingV2(GenericCycleSimulationN5RequestBindingV1):
    """Bind a request under the exact Core typed canonical profile."""

    schema_version: Literal[_N5_REQUEST_BINDING_V2_SCHEMA] = _N5_REQUEST_BINDING_V2_SCHEMA
    canon_profile_id: Literal[_N5_TYPED_CANON_PROFILE_ID]

    @classmethod
    def from_request(
        cls, request: JointSimulationRequest
    ) -> GenericCycleSimulationN5RequestBindingV2:
        """Create a binding only when typed Core round-trip is lossless."""
        if type(request) is not JointSimulationRequest:
            raise TypeError("generic_cycle_simulation_n5_request_untyped")
        _validate_n5_typed_request_roundtrip(request)
        return cls(
            canon_profile_id=_N5_TYPED_CANON_PROFILE_ID,
            request=request,
            request_content_hash=_n5_typed_request_content_hash(request),
        )

    @model_validator(mode="after")
    def _typed_request_is_recoverable(self) -> GenericCycleSimulationN5RequestBindingV2:
        _validate_n5_typed_request_roundtrip(self.request)
        if self.request_content_hash != _n5_typed_request_content_hash(self.request):
            raise ValueError("generic_cycle_simulation_n5_request_content_hash_mismatch")
        return self


class GenericCycleSimulationN5ExecutionV1(_StrictModel):
    """Persisted binding of one N5 result to its exact source-bound input."""

    schema_version: Literal[_N5_EXECUTION_SCHEMA] = _N5_EXECUTION_SCHEMA
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    status: Literal["joint_simulated", "simulation_blocked"]
    job_id: str = Field(min_length=1, strict=True)
    run_id: str = Field(min_length=1, strict=True)
    source_run_id: str = Field(min_length=1, strict=True)
    tenant_id: str = Field(min_length=1, strict=True)
    cell_id: str = Field(min_length=1, strict=True)
    input_ref: ArtifactRef
    result_ref: ArtifactRef | None = None
    n4_source_ref: ArtifactRef
    n4_child_profile_family_ref: ArtifactRef | None = None
    n4_child_profile_set_ref: ArtifactRef | None = None
    context_job_ref: ArtifactRef
    profile_ref: ArtifactRef
    child_selection: GenericCycleSimulationChildSelectionV1 | None = None
    profile_selection_ref: str = Field(pattern=_HASH_PATTERN, strict=True)
    world_model_record_content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)
    candidate_id: str = Field(min_length=1, strict=True)
    candidate_atom_hash: str = Field(pattern=_HASH_PATTERN, strict=True)
    outcome_variable: str = Field(min_length=1, strict=True)
    limitation_code: str | None = Field(default=None, min_length=1, strict=True)
    content_hash: str = Field(pattern=_HASH_PATTERN, strict=True)

    @model_validator(mode="after")
    def _bind_execution(self) -> GenericCycleSimulationN5ExecutionV1:
        refs = (
            (self.input_ref, _N5_INPUT_KIND),
            (self.n4_source_ref, "runtime.generation_source_handoff"),
            (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
            (self.profile_ref, _PROFILE_KIND),
        )
        if any(
            type(ref) is not ArtifactRef or ref.kind != kind or ref.media_type != "application/json"
            for ref, kind in refs
        ):
            raise ValueError("generic_cycle_simulation_n5_execution_ref_invalid")
        if self.result_ref is not None and (
            type(self.result_ref) is not ArtifactRef
            or self.result_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.result_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_n5_execution_result_ref_invalid")
        if self.n4_child_profile_family_ref is not None and (
            type(self.n4_child_profile_family_ref) is not ArtifactRef
            or self.n4_child_profile_family_ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or self.n4_child_profile_family_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_n5_execution_child_family_ref_invalid")
        if self.n4_child_profile_set_ref is not None and (
            type(self.n4_child_profile_set_ref) is not ArtifactRef
            or self.n4_child_profile_set_ref.kind
            != "runtime.quality.recursive_n4_child_profile_set"
            or self.n4_child_profile_set_ref.media_type != "application/json"
        ):
            raise ValueError("generic_cycle_simulation_n5_execution_child_set_ref_invalid")
        if self.n4_child_profile_set_ref is not None and self.n4_child_profile_family_ref is None:
            raise ValueError("generic_cycle_simulation_n5_execution_child_family_missing")
        if self.status == "joint_simulated" and self.result_ref is None:
            raise ValueError("generic_cycle_simulation_n5_execution_result_missing")
        if (
            self.status == "simulation_blocked"
            and self.result_ref is None
            and not self.limitation_code
        ):
            raise ValueError("generic_cycle_simulation_n5_execution_limitation_missing")
        if self.status == "joint_simulated" and self.limitation_code is not None:
            raise ValueError("generic_cycle_simulation_n5_execution_success_has_limitation")
        if (self.child_selection is None) != (self.n4_child_profile_set_ref is None):
            raise ValueError("generic_cycle_simulation_n5_execution_child_selection_pair_mismatch")
        if self.child_selection is not None and (
            self.child_selection.profile_selection_ref != self.profile_selection_ref
            or self.child_selection.n4_child_profile_family_ref != self.n4_child_profile_family_ref
        ):
            raise ValueError("generic_cycle_simulation_n5_execution_child_selection_mismatch")
        expected = (
            _n5_typed_execution_content_hash(self)
            if self.schema_version == _N5_EXECUTION_V3_SCHEMA
            else gy_content_hash(self.model_dump(mode="json", exclude={"content_hash"}))
        )
        if self.content_hash != expected:
            raise ValueError("generic_cycle_simulation_n5_execution_content_hash_mismatch")
        return self


class GenericCycleSimulationN5ExecutionV2(GenericCycleSimulationN5ExecutionV1):
    """Current execution record carrying the complete canonical N5 request."""

    schema_version: Literal[_N5_EXECUTION_V2_SCHEMA] = _N5_EXECUTION_V2_SCHEMA
    request_binding: GenericCycleSimulationN5RequestBindingV1 | None = None

    @model_validator(mode="after")
    def _bind_request_to_execution(self) -> GenericCycleSimulationN5ExecutionV2:
        if self.status == "joint_simulated" and self.request_binding is None:
            raise ValueError("generic_cycle_simulation_n5_execution_request_binding_missing")
        if self.request_binding is not None:
            request = self.request_binding.request
            if request.world_model_record.content_hash != self.world_model_record_content_hash:
                raise ValueError("generic_cycle_simulation_n5_execution_request_wmr_mismatch")
            if request.selected_outcomes != (self.outcome_variable,):
                raise ValueError("generic_cycle_simulation_n5_execution_request_outcome_mismatch")
            if tuple(atom.intervention_id for atom in request.intervention_atoms) == ():
                raise ValueError("generic_cycle_simulation_n5_execution_request_atoms_missing")
        return self


class GenericCycleSimulationN5ExecutionV3(GenericCycleSimulationN5ExecutionV2):
    """Current execution with a typed request binding and Core CAS profile."""

    schema_version: Literal[_N5_EXECUTION_V3_SCHEMA] = _N5_EXECUTION_V3_SCHEMA
    request_binding: GenericCycleSimulationN5RequestBindingV2 = Field(...)

    @model_validator(mode="after")
    def _typed_request_binding_is_current(self) -> GenericCycleSimulationN5ExecutionV3:
        if type(self.request_binding) is not GenericCycleSimulationN5RequestBindingV2:
            raise ValueError("generic_cycle_simulation_n5_execution_request_binding_v2_required")
        validated = GenericCycleSimulationN5RequestBindingV2.model_validate(
            self.request_binding.model_dump(mode="python")
        )
        if validated != self.request_binding:
            raise ValueError("generic_cycle_simulation_n5_execution_request_binding_mismatch")
        return self


GenericCycleSimulationN5ExecutionRecord = (
    GenericCycleSimulationN5ExecutionV1
    | GenericCycleSimulationN5ExecutionV2
    | GenericCycleSimulationN5ExecutionV3
)


class GenericN5ExecutionJoinExpectation(_StrictModel):
    """Cycle-owned identities that a reopened generic execution must match."""

    input_ref: ArtifactRef
    result_ref: ArtifactRef | None
    status: Literal["joint_simulated", "simulation_blocked"]
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    profile_ref: ArtifactRef
    child_family_ref: ArtifactRef | None
    child_set_ref: ArtifactRef | None
    profile_selection_ref: str
    profile: GenericCycleSimulationProfileV1 | None = None
    child_selection: GenericCycleSimulationChildSelectionV1 | None = None
    design_problem_ref: str
    outcome_variable: str
    cycle_index: int
    candidate_id: str
    candidate_atom_hash: str
    world_model_record_content_hash: str
    job_id: str
    run_id: str
    source_run_id: str
    tenant_id: str
    cell_id: str


class GenericN5ExecutionJoinOutcome(_StrictModel):
    """Candidate-only evidence for one independently reopened execution join."""

    status: Literal["resolved", "unavailable", "invalid", "mismatch", "not_established"]
    code: str | None = None
    execution: GenericCycleSimulationN5ExecutionV3 | None = None
    input_record: GenericCycleSimulationN5InputV1 | None = None
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"

    @model_validator(mode="after")
    def _consistent_outcome(self) -> GenericN5ExecutionJoinOutcome:
        if self.status == "resolved":
            if self.execution is None or self.input_record is None or self.code is not None:
                raise ValueError("generic_n5_join_resolved_shape_invalid")
        elif self.execution is not None or self.input_record is not None or not self.code:
            raise ValueError("generic_n5_join_refusal_shape_invalid")
        return self


def parse_generic_cycle_simulation_n5_execution(
    payload: object,
) -> GenericCycleSimulationN5ExecutionRecord:
    """Parse one known N5 execution wire version without upgrading history."""
    if not isinstance(payload, dict):
        raise ValueError("generic_cycle_simulation_n5_execution_payload_invalid")
    version = payload.get("schema_version")
    if version == _N5_EXECUTION_SCHEMA:
        return GenericCycleSimulationN5ExecutionV1.model_validate(payload)
    if version == _N5_EXECUTION_V2_SCHEMA:
        return GenericCycleSimulationN5ExecutionV2.model_validate(payload)
    if version == _N5_EXECUTION_V3_SCHEMA:
        return GenericCycleSimulationN5ExecutionV3.model_validate(payload)
    raise ValueError("generic_cycle_simulation_n5_execution_schema_unsupported")


class GenericCycleSimulationAdmissionOwner:
    """Select server profiles and persist/replay current-job context handoffs."""

    def __init__(
        self,
        *,
        profiles: Sequence[GenericCycleSimulationProfileV1],
        store: artifacts.ArtifactStore,
    ) -> None:
        by_id: dict[str, GenericCycleSimulationProfileV1] = {}
        by_selection: dict[tuple[str, str], str] = {}
        for raw in profiles:
            if type(raw) is not GenericCycleSimulationProfileV1:
                raise TypeError("generic_cycle_simulation_profile_untyped")
            profile = GenericCycleSimulationProfileV1.model_validate(raw.model_dump(mode="python"))
            if profile.profile_id in by_id:
                raise ValueError("generic_cycle_simulation_profile_id_duplicate")
            selection_key = (
                profile.profile_selection_kind,
                profile.profile_selection_ref,
            )
            if selection_key in by_selection:
                raise ValueError("generic_cycle_simulation_profile_selection_ambiguous")
            by_id[profile.profile_id] = profile
            by_selection[selection_key] = profile.profile_id
        self._profiles = by_id
        self._profile_ids_by_selection = by_selection
        self._store = store

    @property
    def profiles(self) -> tuple[GenericCycleSimulationProfileV1, ...]:
        """Return the immutable server-configured profile set."""
        return tuple(self._profiles.values())

    @property
    def store(self) -> artifacts.ArtifactStore:
        """Return the exact runtime-owned CAS used for every handoff."""
        return self._store

    def configured_profile_id_for_selection_ref(self, profile_selection_ref: str) -> str:
        """Return the unique configured member for an exact problem selection.

        This is a lookup only. The caller must still pass the returned ID to
        :meth:`admit_context`, which rechecks the selected problem and worker
        scope before issuing a persisted handoff.
        """
        if not isinstance(profile_selection_ref, str) or not profile_selection_ref.strip():
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_profile_selection_not_established"
            )
        profile_id = self._profile_ids_by_selection.get(("problem", profile_selection_ref))
        if profile_id is None:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_profile_selection_not_configured"
            )
        return profile_id

    def admit_context(
        self,
        *,
        generic_simulation_profile_id: str,
        problem: DesignProblem,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
    ) -> GenericCycleSimulationContextOfferV1:
        """Resolve a server-configured profile against the full problem key."""
        self._require_scope(
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if type(problem) is not DesignProblem:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_problem_untyped")
        profile = self._profiles.get(generic_simulation_profile_id)
        if profile is None:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_profile_not_configured")
        if (
            profile.profile_selection_kind != "problem"
            or profile.profile_selection_ref != cycle_job_profile_selection_ref(problem)
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_profile_problem_mismatch"
            )
        return self._admit_profile(
            profile=profile,
            problem=problem,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )

    @staticmethod
    def _rebind_child_selection_for_problem(
        *,
        child_selection: GenericCycleSimulationChildSelectionV1 | None,
        problem: DesignProblem,
        profile: GenericCycleSimulationProfileV1,
    ) -> GenericCycleSimulationChildSelectionV1:
        """Derive the current full selection from verified initial child lineage."""

        if type(child_selection) is not GenericCycleSimulationChildSelectionV1:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_handoff_selection_missing"
            )
        selection_payload = child_selection.model_dump(mode="python")
        selection_payload.update(
            {
                "problem": problem,
                "full_child_problem_ref": cycle_job_design_problem_ref(problem),
                "profile_selection_ref": generic_n4_child_profile_selection_ref(
                    problem,
                    parent_problem_ref=child_selection.parent_problem_ref,
                    source_result_ref=child_selection.source_result_ref,
                    source_atom_refs=child_selection.source_atom_refs,
                    semantic_ref=child_selection.semantic_ref,
                ),
            }
        )
        rebound = GenericCycleSimulationChildSelectionV1.model_validate(selection_payload)
        if rebound.profile_selection_ref != profile.profile_selection_ref:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_profile_problem_mismatch"
            )
        return rebound

    def reissue_handoff_for_problem(
        self,
        *,
        handoff: GenericCycleSimulationContextHandoffV1,
        previous_problem: DesignProblem,
        problem: DesignProblem,
        verified_nl_job_scope: VerifiedNLJobScope,
        context_owner: CycleSubstrateContextArtifactOwner,
        repo_root: Path,
        source_context_job_ref: ArtifactRef | None = None,
        cycle_context_job_ref: ArtifactRef | None = None,
        child_selection: GenericCycleSimulationChildSelectionV1 | None = None,
    ) -> tuple[
        GenericCycleSimulationContextHandoffV1,
        GenericCycleSimulationChildSelectionV1 | None,
    ]:
        """Reissue one configured N5 handoff for the exact current problem.

        A source-profile context is accepted only after the current-job context
        owner resolves it. The generic N5 profile remains the source of WMR,
        NCM, registry, and request settings; the persisted V5 context adds the
        current source-owner projection while retaining the full problem hash.
        """
        if type(previous_problem) is not DesignProblem or type(problem) is not DesignProblem:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_rebind_problem_untyped")
        if type(context_owner) is not CycleSubstrateContextArtifactOwner:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_owner_not_canonical"
            )
        if context_owner._store is not self._store:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_store_owner_mismatch")
        self._require_scope(
            job_id=handoff.job_id,
            run_id=handoff.run_id,
            tenant_id=handoff.tenant_id,
            cell_id=handoff.cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        current_handoff = self.resolve_handoff(
            handoff=handoff,
            problem=previous_problem,
            verified_nl_job_scope=verified_nl_job_scope,
            context_owner=context_owner,
            repo_root=repo_root,
            child_selection=child_selection,
        )
        profile = current_handoff.profile
        if profile.profile_selection_kind == "problem":
            if child_selection is not None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_parent_handoff_has_child_selection"
                )
            profile_selection_ref = cycle_job_profile_selection_ref(problem)
            if profile_selection_ref != profile.profile_selection_ref:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_profile_problem_mismatch"
                )
            offer = self.admit_context(
                generic_simulation_profile_id=profile.profile_id,
                problem=problem,
                job_id=current_handoff.job_id,
                run_id=current_handoff.run_id,
                tenant_id=current_handoff.tenant_id,
                cell_id=current_handoff.cell_id,
                verified_nl_job_scope=verified_nl_job_scope,
            )
            rebound_child_selection = None
        else:
            rebound_child_selection = self._rebind_child_selection_for_problem(
                child_selection=child_selection,
                problem=problem,
                profile=profile,
            )
            offer = self.admit_child_context(
                selection=rebound_child_selection,
                job_id=current_handoff.job_id,
                run_id=current_handoff.run_id,
                tenant_id=current_handoff.tenant_id,
                cell_id=current_handoff.cell_id,
                verified_nl_job_scope=verified_nl_job_scope,
                context_owner=context_owner,
                repo_root=repo_root,
            )

        if source_context_job_ref is not None and cycle_context_job_ref is not None:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_rebind_context_ref_ambiguous"
            )
        source_selection = candidate_cycle_substrate_source_profile_selection(problem)
        if source_selection is None:
            if source_context_job_ref is not None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_rebind_source_selection_missing"
                )
            if cycle_context_job_ref is not None:
                try:
                    resolved_context_job = context_owner.resolve_for_current_job(
                        cycle_context_job_ref,
                        problem=problem,
                        repo_root=repo_root,
                        verified_nl_job_scope=verified_nl_job_scope,
                    )
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    raise CycleSubstrateContextOwnerError(
                        "generic_cycle_simulation_rebind_context_not_current",
                        str(getattr(exc, "code", None) or exc),
                    ) from exc
                resolved_context = getattr(resolved_context_job, "context", None)
                if (
                    type(resolved_context) is not CycleSubstrateContext
                    or resolved_context.source_profile is not None
                    or resolved_context.design_problem_ref != cycle_job_design_problem_ref(problem)
                    or not self.context_matches_profile(resolved_context, offer.profile, problem)
                ):
                    raise CycleSubstrateContextOwnerError(
                        "generic_cycle_simulation_rebind_context_profile_join_mismatch"
                    )
                offer = offer.model_copy(update={"context": resolved_context})
        else:
            if source_context_job_ref is None or cycle_context_job_ref is not None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_rebind_source_context_missing"
                )
            try:
                resolved_source_job = context_owner.resolve_for_current_job(
                    source_context_job_ref,
                    problem=problem,
                    repo_root=repo_root,
                    verified_nl_job_scope=verified_nl_job_scope,
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_rebind_source_context_not_current",
                    str(getattr(exc, "code", None) or exc),
                ) from exc
            source_context = getattr(resolved_source_job, "context", None)
            if (
                type(source_context) is not CycleSubstrateContext
                or source_context.source_profile is None
                or source_context.design_problem_ref != cycle_job_design_problem_ref(problem)
                or not self.context_matches_profile(source_context, offer.profile, problem)
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_rebind_source_profile_join_mismatch"
                )
            offer = offer.model_copy(update={"context": source_context})

        rebound = self.persist_handoff(
            offer=offer,
            problem=problem,
            job_id=current_handoff.job_id,
            run_id=current_handoff.run_id,
            tenant_id=current_handoff.tenant_id,
            cell_id=current_handoff.cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
            context_owner=context_owner,
            repo_root=repo_root,
        )
        resolved = self.resolve_handoff(
            handoff=rebound,
            problem=problem,
            verified_nl_job_scope=verified_nl_job_scope,
            context_owner=context_owner,
            repo_root=repo_root,
            child_selection=rebound_child_selection,
        )
        return resolved, rebound_child_selection

    @staticmethod
    def context_matches_profile(
        context: CycleSubstrateContext,
        profile: GenericCycleSimulationProfileV1,
        problem: DesignProblem,
    ) -> bool:
        """Join immutable profile inputs to one exact current V5 owner context.

        The profile artifact retains its own complete, immutable context and N5
        request. V5 independently binds the per-cycle problem and current source
        rows, so its source-specific input hash is not compared to the reusable
        profile's input hash. Shared WMR, registry, selected entries, L6, and any
        profile-declared candidate/transport evidence must still agree.
        """
        if (
            type(context) is not CycleSubstrateContext
            or type(profile) is not GenericCycleSimulationProfileV1
            or type(problem) is not DesignProblem
        ):
            return False
        try:
            expected = GenericCycleSimulationAdmissionOwner.context_for_profile(profile, problem)
            views = world_model_artifact_views(context.world_model_record)
        except (AttributeError, CycleSubstrateContextOwnerError, TypeError, ValueError):
            return False
        if (
            views.substrate_registry_ref is None
            or artifact_ref_identity_key(views.substrate_registry_ref)
            != artifact_ref_identity_key(profile.substrate_registry_ref)
            or len(views.ncm_refs) != 1
            or artifact_ref_identity_key(views.ncm_refs[0])
            != artifact_ref_identity_key(profile.selected_ncm_ref)
        ):
            return False
        if context.source_profile is None:
            return context == expected
        source = context.source_profile
        inputs = profile.context_inputs
        profile_candidate_levers_match = (
            not inputs.candidate_levers or context.candidate_levers == inputs.candidate_levers
        )
        return (
            context.schema_version == "policyos.runtime.cycle_substrate_context.v2"
            and context.design_problem_ref == expected.design_problem_ref
            and context.domain == expected.domain
            and context.substrate_registry == expected.substrate_registry
            and context.substrate_registry_content_hash == expected.substrate_registry_content_hash
            and context.selected_registry_entry_hashes == expected.selected_registry_entry_hashes
            and context.world_model_record == inputs.world_model_record
            and context.world_model_record_content_hash == inputs.world_model_record.content_hash
            and context.intervention_substrate == inputs.intervention_substrate
            and profile_candidate_levers_match
            and context.transport_context == inputs.transport_context
            and source.profile_status == "candidate_only"
            and source.owner_recomputation_status == "recomputed"
            and source.authority_purpose == "cycle_input_candidate_only"
            and source.source_basis_status == "not_established"
            and source.source_authenticity_status == "not_established"
            and source.source_currentness_status == "not_established"
            and source.design_problem_ref == cycle_job_design_problem_ref(problem)
            and source.selected_outcome_variable == problem.outcome_of_interest.target_variable
            and source.world_model_record_content_hash == context.world_model_record_content_hash
            and source.s0_registry_content_hash == context.substrate_registry_content_hash
            and source.selected_registry_entry_hashes == context.selected_registry_entry_hashes
        )

    def configured_profile_id_for_child_selection(
        self,
        selection: GenericCycleSimulationChildSelectionV1,
    ) -> str:
        """Select a child profile only from the family-bound typed child identity."""
        if type(selection) is not GenericCycleSimulationChildSelectionV1:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_selection_untyped"
            )
        expected = generic_n4_child_profile_selection_ref(
            selection.problem,
            parent_problem_ref=selection.parent_problem_ref,
            source_result_ref=selection.source_result_ref,
            source_atom_refs=selection.source_atom_refs,
            semantic_ref=selection.semantic_ref,
        )
        if (
            selection.full_child_problem_ref != cycle_job_design_problem_ref(selection.problem)
            or selection.profile_selection_ref != expected
            or selection.parent_handoff.n4_child_profile_family_ref
            != selection.n4_child_profile_family_ref
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_selection_not_recomputed"
            )
        profile_id = self._profile_ids_by_selection.get(
            ("n4_candidate_child", selection.profile_selection_ref)
        )
        if profile_id is None:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_profile_not_configured"
            )
        return profile_id

    def admit_child_context(
        self,
        *,
        selection: GenericCycleSimulationChildSelectionV1,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
        context_owner: CycleSubstrateContextArtifactOwner,
        repo_root: Path | None = None,
    ) -> GenericCycleSimulationContextOfferV1:
        """Resolve one configured profile for a fully typed N4-derived child."""
        self._require_scope(
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if type(selection) is not GenericCycleSimulationChildSelectionV1:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_selection_untyped"
            )
        parent_handoff = self.resolve_handoff(
            handoff=selection.parent_handoff,
            problem=selection.parent_problem,
            verified_nl_job_scope=verified_nl_job_scope,
            context_owner=context_owner,
            repo_root=repo_root,
        )
        family = self.resolve_child_profile_family(
            selection.n4_child_profile_family_ref,
            parent_handoff=parent_handoff,
            parent_problem=selection.parent_problem,
            verified_nl_job_scope=verified_nl_job_scope,
            context_owner=context_owner,
            repo_root=repo_root,
        )
        profile_id = self.configured_profile_id_for_child_selection(selection)
        profile = self._profiles[profile_id]
        if profile.profile_selection_kind != "n4_candidate_child":
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_profile_kind_mismatch"
            )
        if not any(
            member.profile_id == profile.profile_id
            and member.profile_selection_ref == profile.profile_selection_ref
            for member in family.children
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_profile_outside_family"
            )
        offer = self._admit_profile(
            profile=profile,
            problem=selection.problem,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        return GenericCycleSimulationContextOfferV1.model_validate(
            {
                **offer.model_dump(mode="python"),
                "n4_child_profile_family_ref": selection.n4_child_profile_family_ref,
                "parent_problem": selection.parent_problem,
                "parent_handoff": parent_handoff,
            }
        )

    def _admit_profile(
        self,
        *,
        profile: GenericCycleSimulationProfileV1,
        problem: DesignProblem,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
    ) -> GenericCycleSimulationContextOfferV1:
        try:
            self._verify_json_artifact(
                profile.world_model_record_ref,
                expected_kind="runtime.quality.world_model_record",
            )
            world = load_world_model_record(self._store, profile.world_model_record_ref)
            views = world_model_artifact_views(world)
            if (
                world != profile.context_inputs.world_model_record
                or views.substrate_registry_ref is None
                or artifact_ref_identity_key(views.substrate_registry_ref)
                != artifact_ref_identity_key(profile.substrate_registry_ref)
                or len(views.ncm_refs) != 1
                or artifact_ref_identity_key(views.ncm_refs[0])
                != artifact_ref_identity_key(profile.selected_ncm_ref)
            ):
                raise ValueError("generic_cycle_simulation_source_binding_mismatch")
            self._verify_json_artifact(
                profile.substrate_registry_ref,
                expected_kind="runtime.quality.production_data_substrate_registry",
            )
            registry = load_substrate_registry(self._store, profile.substrate_registry_ref)
            if registry != profile.context_inputs.substrate_registry:
                raise ValueError("generic_cycle_simulation_registry_content_mismatch")
            self._verify_json_artifact(profile.selected_ncm_ref, expected_kind="ir.ncm_spec")
            self._verify_default_ncm(profile.selected_ncm_ref)
        except (OSError, TypeError, ValueError) as exc:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_source_not_established", str(exc)
            ) from exc

        context = build_cycle_substrate_context(
            design_problem_ref=cycle_job_design_problem_ref(problem),
            domain=problem.domain,
            substrate_registry=registry,
            selected_registry_entry_hashes=profile.context_inputs.selected_registry_entry_hashes,
            world_model_record=world,
            intervention_substrate=profile.context_inputs.intervention_substrate,
            candidate_levers=profile.context_inputs.candidate_levers,
            transport_context=profile.context_inputs.transport_context,
            source_pack_content_hash=profile.context_inputs.source_pack_content_hash,
            substrate_input_content_hash=profile.context_inputs.substrate_input_content_hash,
        )
        context = revalidate_cycle_substrate_context(context)
        profile_ref = self._persist_profile(
            profile=profile,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        return GenericCycleSimulationContextOfferV1(
            context=context,
            profile=profile,
            profile_ref=profile_ref,
        )

    def persist_handoff(
        self,
        *,
        offer: GenericCycleSimulationContextOfferV1,
        problem: DesignProblem,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
        context_owner: CycleSubstrateContextArtifactOwner,
        repo_root: Path | None = None,
    ) -> GenericCycleSimulationContextHandoffV1:
        """Persist and immediately replay the context using the current-job owner."""
        self._require_scope(
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if type(context_owner) is not CycleSubstrateContextArtifactOwner:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_owner_not_canonical"
            )
        if context_owner._store is not self._store:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_store_owner_mismatch")
        self.resolve_profile(
            offer.profile_ref,
            expected_profile=offer.profile,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        if not self.context_matches_profile(offer.context, offer.profile, problem):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_profile_join_mismatch"
            )
        # Keep the persisted ArtifactRef; resolve_profile returns profile content.
        profile_ref = offer.profile_ref
        context_ref = context_owner.persist_for_current_job(
            offer.context,
            problem=problem,
            repo_root=repo_root,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        resolved = context_owner.resolve_for_current_job(
            context_ref,
            problem=problem,
            repo_root=repo_root,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if (
            resolved.context != offer.context
            or resolved.context.content_hash != offer.context.content_hash
            or resolved.job_id != job_id
            or resolved.run_id != run_id
            or resolved.tenant_id != tenant_id
            or resolved.cell_id != cell_id
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_readback_mismatch"
            )
        family_ref: ArtifactRef | None = None
        if offer.parent_handoff is not None:
            parent_problem = offer.parent_problem
            if parent_problem is None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_family_parent_problem_missing"
                )
            parent = self.resolve_handoff(
                handoff=offer.parent_handoff,
                problem=parent_problem,
                verified_nl_job_scope=verified_nl_job_scope,
                context_owner=context_owner,
                repo_root=repo_root,
            )
            family_ref = offer.n4_child_profile_family_ref
            if (
                family_ref is None
                or family_ref != parent.n4_child_profile_family_ref
                or offer.parent_handoff != parent
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_family_parent_mismatch"
                )
            family = self.resolve_child_profile_family(
                family_ref,
                parent_handoff=parent,
                parent_problem=parent_problem,
                verified_nl_job_scope=verified_nl_job_scope,
                context_owner=context_owner,
                repo_root=repo_root,
            )
            if not any(
                member.profile_id == offer.profile.profile_id
                and member.profile_selection_ref == offer.profile.profile_selection_ref
                and member.profile_ref == offer.profile_ref
                for member in family.children
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_profile_outside_family"
                )
        elif offer.profile.profile_selection_kind == "problem":
            child_profiles = self._configured_child_profiles()
            if child_profiles:
                family_ref = self._persist_child_profile_family(
                    problem=problem,
                    parent_context=resolved.context,
                    parent_context_job_ref=context_ref,
                    parent_profile=offer.profile,
                    parent_profile_ref=profile_ref,
                    child_profiles=child_profiles,
                    job_id=job_id,
                    run_id=run_id,
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    verified_nl_job_scope=verified_nl_job_scope,
                )
        elif offer.profile.profile_selection_kind == "n4_candidate_child":
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_parent_binding_missing"
            )
        return GenericCycleSimulationContextHandoffV1(
            context=resolved.context,
            context_job_ref=context_ref,
            profile=offer.profile,
            profile_ref=profile_ref,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            n4_child_profile_family_ref=family_ref,
        )

    def resolve_handoff(
        self,
        *,
        handoff: GenericCycleSimulationContextHandoffV1,
        problem: DesignProblem,
        verified_nl_job_scope: VerifiedNLJobScope,
        context_owner: CycleSubstrateContextArtifactOwner,
        repo_root: Path | None = None,
        child_selection: GenericCycleSimulationChildSelectionV1 | None = None,
    ) -> GenericCycleSimulationContextHandoffV1:
        """Reconcile persisted profile and context against the active worker lease."""
        if type(handoff) is not GenericCycleSimulationContextHandoffV1:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_handoff_untyped")
        self._require_scope(
            job_id=handoff.job_id,
            run_id=handoff.run_id,
            tenant_id=handoff.tenant_id,
            cell_id=handoff.cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if type(context_owner) is not CycleSubstrateContextArtifactOwner:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_owner_not_canonical"
            )
        if context_owner._store is not self._store:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_store_owner_mismatch")
        profile = self.resolve_profile(
            handoff.profile_ref,
            expected_profile=handoff.profile,
            job_id=handoff.job_id,
            run_id=handoff.run_id,
            tenant_id=handoff.tenant_id,
            cell_id=handoff.cell_id,
        )
        resolved = context_owner.resolve_for_current_job(
            handoff.context_job_ref,
            problem=problem,
            repo_root=repo_root,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if profile.profile_selection_kind == "problem":
            if child_selection is not None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_parent_handoff_has_child_selection"
                )
            selection_ref = cycle_job_profile_selection_ref(problem)
        else:
            if type(child_selection) is not GenericCycleSimulationChildSelectionV1:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_handoff_selection_missing"
                )
            if (
                child_selection.problem != problem
                or child_selection.n4_child_profile_family_ref
                != handoff.n4_child_profile_family_ref
                or child_selection.parent_handoff.n4_child_profile_family_ref
                != handoff.n4_child_profile_family_ref
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_handoff_selection_mismatch"
                )
            parent_handoff = self.resolve_handoff(
                handoff=child_selection.parent_handoff,
                problem=child_selection.parent_problem,
                verified_nl_job_scope=verified_nl_job_scope,
                context_owner=context_owner,
                repo_root=repo_root,
            )
            family = self.resolve_child_profile_family(
                child_selection.n4_child_profile_family_ref,
                parent_handoff=parent_handoff,
                parent_problem=child_selection.parent_problem,
                verified_nl_job_scope=verified_nl_job_scope,
                context_owner=context_owner,
                repo_root=repo_root,
            )
            if not any(
                member.profile_id == profile.profile_id
                and member.profile_ref == handoff.profile_ref
                and member.profile_selection_ref == profile.profile_selection_ref
                for member in family.children
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_handoff_outside_family"
                )
            if (
                self.configured_profile_id_for_child_selection(child_selection)
                != profile.profile_id
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_handoff_profile_mismatch"
                )
            selection_ref = child_selection.profile_selection_ref
        if (
            resolved.context != handoff.context
            or resolved.context.content_hash != handoff.context.content_hash
            or (resolved.job_id, resolved.run_id, resolved.tenant_id, resolved.cell_id)
            != (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id)
            or profile.profile_selection_ref != selection_ref
            or not self.context_matches_profile(resolved.context, profile, problem)
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_handoff_binding_mismatch"
            )
        return GenericCycleSimulationContextHandoffV1.model_validate(
            {
                **handoff.model_dump(mode="python"),
                "profile": profile,
                "context": resolved.context,
            }
        )

    def profile_selection_ref_for_handoff(
        self,
        *,
        handoff: GenericCycleSimulationContextHandoffV1,
        problem: DesignProblem,
        child_selection: GenericCycleSimulationChildSelectionV1 | None,
    ) -> str:
        """Return a profile key only from a parent key or a typed child lineage."""
        if (
            type(handoff) is not GenericCycleSimulationContextHandoffV1
            or type(problem) is not DesignProblem
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_selection_inputs_untyped"
            )
        if handoff.profile.profile_selection_kind == "problem":
            if child_selection is not None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_parent_handoff_has_child_selection"
                )
            return cycle_job_profile_selection_ref(problem)
        if type(child_selection) is not GenericCycleSimulationChildSelectionV1:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_handoff_selection_missing"
            )
        if (
            child_selection.problem != problem
            or child_selection.n4_child_profile_family_ref != handoff.n4_child_profile_family_ref
            or self.configured_profile_id_for_child_selection(child_selection)
            != handoff.profile.profile_id
            or child_selection.profile_selection_ref != handoff.profile.profile_selection_ref
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_handoff_selection_mismatch"
            )
        return child_selection.profile_selection_ref

    @staticmethod
    def context_for_profile(
        profile: GenericCycleSimulationProfileV1,
        problem: DesignProblem,
    ) -> CycleSubstrateContext:
        """Recompute a context from the persisted profile's typed source inputs."""
        if (
            type(profile) is not GenericCycleSimulationProfileV1
            or type(problem) is not DesignProblem
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_recompute_inputs_untyped"
            )
        inputs = profile.context_inputs
        context = build_cycle_substrate_context(
            design_problem_ref=cycle_job_design_problem_ref(problem),
            domain=problem.domain,
            substrate_registry=inputs.substrate_registry,
            selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
            world_model_record=inputs.world_model_record,
            intervention_substrate=inputs.intervention_substrate,
            candidate_levers=inputs.candidate_levers,
            transport_context=inputs.transport_context,
            source_pack_content_hash=inputs.source_pack_content_hash,
            substrate_input_content_hash=inputs.substrate_input_content_hash,
        )
        return revalidate_cycle_substrate_context(context)

    def resolve_profile(
        self,
        ref: ArtifactRef,
        *,
        expected_profile: GenericCycleSimulationProfileV1,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> GenericCycleSimulationProfileV1:
        """Resolve the exact persisted server profile and its whole manifest scope."""
        from polisyos.core.artifacts import load_core_json_artifact

        configured = self._profiles.get(expected_profile.profile_id)
        if configured != expected_profile:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_profile_not_currently_configured"
            )
        self._verify_json_artifact(ref, expected_kind=_PROFILE_KIND)
        manifest = self._store.get_manifest(ref)
        expected_options = self._profile_write_options(
            profile=configured,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        if not self._manifest_matches_profile(manifest, ref, expected_options):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_profile_manifest_binding_mismatch"
            )
        profile = GenericCycleSimulationProfileV1.model_validate(
            load_core_json_artifact(self._store, ref)
        )
        if profile != configured:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_profile_content_binding_mismatch"
            )
        return profile

    def resolve_profile_historical(
        self,
        ref: ArtifactRef,
        *,
        expected_profile: GenericCycleSimulationProfileV1,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> GenericCycleSimulationProfileV1:
        """Verify a historical configured profile without claiming it is current."""
        from polisyos.core.artifacts import load_core_json_artifact

        if type(expected_profile) is not GenericCycleSimulationProfileV1:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_profile_untyped"
            )
        self._verify_json_artifact(ref, expected_kind=_PROFILE_KIND)
        manifest = self._store.get_manifest(ref)
        expected_options = self._profile_write_options(
            profile=expected_profile,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        if not self._manifest_matches_profile(manifest, ref, expected_options):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_profile_manifest_mismatch"
            )
        profile = GenericCycleSimulationProfileV1.model_validate(
            load_core_json_artifact(self._store, ref)
        )
        if profile != expected_profile:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_profile_content_mismatch"
            )
        return profile

    def resolve_child_profile_family(
        self,
        ref: ArtifactRef,
        *,
        parent_handoff: GenericCycleSimulationContextHandoffV1,
        parent_problem: DesignProblem,
        verified_nl_job_scope: VerifiedNLJobScope,
        context_owner: CycleSubstrateContextArtifactOwner,
        repo_root: Path | None = None,
    ) -> GenericCycleSimulationChildProfileFamilyV1:
        """Resolve the whole current child-profile tuple against its parent lease."""
        from polisyos.core.artifacts import load_core_json_artifact

        if type(parent_handoff) is not GenericCycleSimulationContextHandoffV1:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_parent_untyped"
            )
        if type(parent_problem) is not DesignProblem:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_parent_problem_untyped"
            )
        self._require_scope(
            job_id=parent_handoff.job_id,
            run_id=parent_handoff.run_id,
            tenant_id=parent_handoff.tenant_id,
            cell_id=parent_handoff.cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if type(context_owner) is not CycleSubstrateContextArtifactOwner:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_context_owner_not_canonical"
            )
        if context_owner._store is not self._store:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_store_owner_mismatch")
        resolved_parent = self.resolve_handoff(
            handoff=parent_handoff,
            problem=parent_problem,
            verified_nl_job_scope=verified_nl_job_scope,
            context_owner=context_owner,
            repo_root=repo_root,
        )
        if (
            type(ref) is not ArtifactRef
            or ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or ref.media_type != "application/json"
            or resolved_parent.n4_child_profile_family_ref != ref
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_parent_ref_mismatch"
            )
        self._verify_json_artifact(ref, expected_kind=_CHILD_PROFILE_FAMILY_KIND)
        try:
            family = GenericCycleSimulationChildProfileFamilyV1.model_validate(
                load_core_json_artifact(self._store, ref)
            )
        except (TypeError, ValueError) as exc:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_invalid", str(exc)
            ) from exc
        configured_children = self._configured_child_profiles()
        if tuple(member.profile_id for member in family.children) != tuple(
            profile.profile_id for profile in configured_children
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_tuple_not_current"
            )
        for member, profile in zip(family.children, configured_children, strict=True):
            if (
                member.profile_selection_ref != profile.profile_selection_ref
                or member.profile_content_hash != profile.content_hash
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_family_member_mismatch"
                )
            self.resolve_profile(
                member.profile_ref,
                expected_profile=profile,
                job_id=family.job_id,
                run_id=family.run_id,
                tenant_id=family.tenant_id,
                cell_id=family.cell_id,
            )
        expected_parent = resolved_parent
        if (
            family.job_id != expected_parent.job_id
            or family.run_id != expected_parent.run_id
            or family.tenant_id != expected_parent.tenant_id
            or family.cell_id != expected_parent.cell_id
            or family.parent_problem_ref != cycle_job_design_problem_ref(parent_problem)
            or family.parent_context_hash != expected_parent.context.content_hash
            or family.parent_profile_id != expected_parent.profile.profile_id
            or family.parent_profile_selection_ref != expected_parent.profile.profile_selection_ref
            or family.parent_context_job_ref != expected_parent.context_job_ref
            or family.parent_profile_ref != expected_parent.profile_ref
            or family.parent_profile_content_hash != expected_parent.profile.content_hash
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_parent_binding_mismatch"
            )
        manifest = self._store.get_manifest(ref)
        if not self._manifest_matches_child_profile_family(manifest, ref, family):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_manifest_mismatch"
            )
        return family

    def resolve_child_profile_family_historical(
        self,
        ref: ArtifactRef,
        *,
        expected_parent_handoff: GenericCycleSimulationContextHandoffV1,
        expected_parent_problem: DesignProblem,
    ) -> GenericCycleSimulationChildProfileFamilyV1:
        """Read a past family without treating its configured tuple as current."""
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )

        if (
            type(expected_parent_handoff) is not GenericCycleSimulationContextHandoffV1
            or type(expected_parent_problem) is not DesignProblem
            or type(ref) is not ArtifactRef
            or ref.kind != _CHILD_PROFILE_FAMILY_KIND
            or ref.media_type != "application/json"
            or expected_parent_handoff.n4_child_profile_family_ref != ref
            or expected_parent_handoff.profile.profile_selection_kind != "problem"
            or expected_parent_handoff.profile.profile_selection_ref
            != cycle_job_profile_selection_ref(expected_parent_problem)
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_child_family_parent_invalid"
            )
        self._verify_json_artifact(ref, expected_kind=_CHILD_PROFILE_FAMILY_KIND)
        try:
            family = GenericCycleSimulationChildProfileFamilyV1.model_validate(
                load_core_json_artifact(self._store, ref)
            )
        except (TypeError, ValueError) as exc:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_child_family_invalid", str(exc)
            ) from exc
        parent = expected_parent_handoff
        if (
            family.job_id != parent.job_id
            or family.run_id != parent.run_id
            or family.tenant_id != parent.tenant_id
            or family.cell_id != parent.cell_id
            or family.parent_problem_ref != cycle_job_design_problem_ref(expected_parent_problem)
            or family.parent_context_hash != parent.context.content_hash
            or family.parent_profile_id != parent.profile.profile_id
            or family.parent_profile_selection_ref != parent.profile.profile_selection_ref
            or family.parent_context_job_ref != parent.context_job_ref
            or family.parent_profile_ref != parent.profile_ref
            or family.parent_profile_content_hash != parent.profile.content_hash
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_child_family_parent_mismatch"
            )
        context_record = CycleSubstrateContextArtifactOwner(
            store=self._store
        ).resolve_historical_job_artifact(
            parent.context_job_ref,
            problem=expected_parent_problem,
            expected_job_id=parent.job_id,
            expected_run_id=parent.run_id,
            expected_tenant_id=parent.tenant_id,
            expected_cell_id=parent.cell_id,
        )
        if getattr(context_record, "context", None) != parent.context:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_parent_context_mismatch"
            )
        parent_profile = self.resolve_profile_historical(
            parent.profile_ref,
            expected_profile=parent.profile,
            job_id=parent.job_id,
            run_id=parent.run_id,
            tenant_id=parent.tenant_id,
            cell_id=parent.cell_id,
        )
        if parent_profile.content_hash != family.parent_profile_content_hash:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_parent_profile_mismatch"
            )
        for member in family.children:
            self._verify_json_artifact(member.profile_ref, expected_kind=_PROFILE_KIND)
            try:
                child_profile = GenericCycleSimulationProfileV1.model_validate(
                    load_core_json_artifact(self._store, member.profile_ref)
                )
            except (TypeError, ValueError) as exc:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_historical_child_profile_invalid",
                    str(exc),
                ) from exc
            child_profile = self.resolve_profile_historical(
                member.profile_ref,
                expected_profile=child_profile,
                job_id=family.job_id,
                run_id=family.run_id,
                tenant_id=family.tenant_id,
                cell_id=family.cell_id,
            )
            if (
                child_profile.profile_selection_kind != "n4_candidate_child"
                or child_profile.profile_id != member.profile_id
                or child_profile.profile_selection_ref != member.profile_selection_ref
                or child_profile.content_hash != member.profile_content_hash
            ):
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_historical_child_profile_binding_mismatch"
                )
        if not self._manifest_matches_child_profile_family(
            self._store.get_manifest(ref), ref, family
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_historical_child_family_manifest_mismatch"
            )
        return family

    def _configured_child_profiles(
        self,
    ) -> tuple[GenericCycleSimulationProfileV1, ...]:
        return tuple(
            sorted(
                (
                    profile
                    for profile in self._profiles.values()
                    if profile.profile_selection_kind == "n4_candidate_child"
                ),
                key=lambda profile: profile.profile_id,
            )
        )

    def _persist_child_profile_family(
        self,
        *,
        problem: DesignProblem,
        parent_context: CycleSubstrateContext,
        parent_context_job_ref: ArtifactRef,
        parent_profile: GenericCycleSimulationProfileV1,
        parent_profile_ref: ArtifactRef,
        child_profiles: tuple[GenericCycleSimulationProfileV1, ...],
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
    ) -> ArtifactRef:
        from polisyos.core.artifacts import load_core_json_artifact

        self._require_scope(
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        members: list[GenericCycleSimulationChildProfileMemberV1] = []
        for profile in child_profiles:
            profile_ref = self._persist_profile(
                profile=profile,
                job_id=job_id,
                run_id=run_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                verified_nl_job_scope=verified_nl_job_scope,
            )
            members.append(
                GenericCycleSimulationChildProfileMemberV1(
                    profile_id=profile.profile_id,
                    profile_selection_ref=profile.profile_selection_ref,
                    profile_content_hash=profile.content_hash,
                    profile_ref=profile_ref,
                )
            )
        draft = {
            "schema_version": _CHILD_PROFILE_FAMILY_SCHEMA,
            "authority_purpose": "cycle_input_candidate_only",
            "job_id": job_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "parent_problem_ref": cycle_job_design_problem_ref(problem),
            "parent_context_hash": parent_context.content_hash,
            "parent_profile_id": parent_profile.profile_id,
            "parent_profile_selection_ref": parent_profile.profile_selection_ref,
            "parent_context_job_ref": parent_context_job_ref,
            "parent_profile_ref": parent_profile_ref,
            "parent_profile_content_hash": parent_profile.content_hash,
            "children": tuple(members),
        }
        family_body = {
            **draft,
            "content_hash": gy_content_hash(
                GenericCycleSimulationChildProfileFamilyV1.model_construct(
                    **draft, content_hash="sha256:" + "0" * 64
                ).model_dump(mode="json", exclude={"content_hash"})
            ),
        }
        family = GenericCycleSimulationChildProfileFamilyV1.model_validate(family_body)
        options = self._child_profile_family_write_options(family)
        ref = self._store.put_json(
            family.model_dump(mode="json"), options, canon_spec=_PROFILE_CANON
        )
        self._verify_json_artifact(ref, expected_kind=_CHILD_PROFILE_FAMILY_KIND)
        persisted = GenericCycleSimulationChildProfileFamilyV1.model_validate(
            load_core_json_artifact(self._store, ref)
        )
        manifest = self._store.get_manifest(ref)
        if persisted != family or not self._manifest_matches_child_profile_family(
            manifest, ref, family
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_child_family_readback_mismatch"
            )
        return ref

    def persist_n5_input(
        self,
        *,
        handoff: GenericCycleSimulationContextHandoffV1,
        source_ref: ArtifactRef,
        source_run_id: str,
        child_profile_family_ref: ArtifactRef | None,
        child_profile_set_ref: ArtifactRef | None,
        problem: DesignProblem,
        cycle_index: int,
        candidate_id: str,
        candidate_atom_hash: str,
        outcome_variable: str,
        child_selection: GenericCycleSimulationChildSelectionV1 | None = None,
    ) -> ArtifactRef:
        """Persist one N4-derived input and immediately resolve its exact view."""
        if type(handoff) is not GenericCycleSimulationContextHandoffV1:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_handoff_untyped")
        if type(problem) is not DesignProblem:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_problem_untyped")
        if handoff.profile.profile_selection_kind == "problem":
            selected_ref = cycle_job_profile_selection_ref(problem)
            if child_selection is not None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_parent_input_has_child_selection"
                )
        else:
            if type(child_selection) is not GenericCycleSimulationChildSelectionV1:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_input_selection_missing"
                )
            if child_selection.problem != problem:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_child_input_problem_mismatch"
                )
            self.configured_profile_id_for_child_selection(child_selection)
            selected_ref = child_selection.profile_selection_ref
        if selected_ref != handoff.profile.profile_selection_ref:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_problem_profile_mismatch"
            )
        if child_profile_family_ref != handoff.n4_child_profile_family_ref:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_child_family_handoff_mismatch"
            )
        if handoff.profile.profile_selection_kind == "n4_candidate_child" and (
            child_profile_family_ref is None or child_profile_set_ref is None
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_child_family_or_set_missing"
            )
        if (
            handoff.profile.profile_selection_kind == "problem"
            and child_profile_set_ref is not None
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_parent_input_has_child_set"
            )
        payload = {
            "schema_version": _N5_INPUT_SCHEMA,
            "authority_purpose": "cycle_input_candidate_only",
            "job_id": handoff.job_id,
            "run_id": handoff.run_id,
            "source_run_id": source_run_id,
            "tenant_id": handoff.tenant_id,
            "cell_id": handoff.cell_id,
            "design_problem_ref": cycle_job_design_problem_ref(problem),
            "cycle_index": cycle_index,
            "n4_source_ref": source_ref,
            "n4_child_profile_family_ref": child_profile_family_ref,
            "n4_child_profile_set_ref": child_profile_set_ref,
            "child_selection": child_selection,
            "context_job_ref": handoff.context_job_ref,
            "profile_ref": handoff.profile_ref,
            "profile": handoff.profile,
            "candidate_id": candidate_id,
            "candidate_atom_hash": candidate_atom_hash,
            "outcome_variable": outcome_variable,
            "n5": handoff.profile.n5,
        }
        normalized = GenericCycleSimulationN5InputV1.model_construct(
            **payload,
            content_hash="sha256:" + "0" * 64,
        ).model_dump(mode="json", exclude={"content_hash"})
        record = GenericCycleSimulationN5InputV1.model_validate(
            {**normalized, "content_hash": gy_content_hash(normalized)}
        )
        ref = self._store.put_json(
            record.model_dump(mode="json"),
            self._n5_input_write_options(record),
            canon_spec=_PROFILE_CANON,
            return_selected_profile=True,
        )
        self.resolve_n5_input(ref, expected=record)
        return ref

    def resolve_n5_input(
        self,
        ref: ArtifactRef,
        *,
        expected: GenericCycleSimulationN5InputV1,
    ) -> GenericCycleSimulationN5InputV1:
        """Resolve exact selected N5 bytes and the complete owner manifest."""
        from polisyos.core.artifacts import load_core_json_artifact

        if type(expected) is not GenericCycleSimulationN5InputV1:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_n5_input_untyped")
        self._verify_json_artifact(ref, expected_kind=_N5_INPUT_KIND)
        manifest = self._store.get_manifest(ref)
        if not self._manifest_matches_record(manifest, ref, self._n5_input_write_options(expected)):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_input_manifest_mismatch"
            )
        record = GenericCycleSimulationN5InputV1.model_validate(
            load_core_json_artifact(self._store, ref)
        )
        if record != expected:
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_input_content_mismatch"
            )
        return record

    def persist_n5_execution(
        self,
        *,
        input_ref: ArtifactRef,
        input_record: GenericCycleSimulationN5InputV1,
        result_ref: ArtifactRef | None,
        status: Literal["joint_simulated", "simulation_blocked"],
        world_model_record_content_hash: str,
        request_binding: (
            GenericCycleSimulationN5RequestBindingV1
            | GenericCycleSimulationN5RequestBindingV2
            | None
        ) = None,
        limitation_code: str | None = None,
    ) -> ArtifactRef:
        """Persist exact source, request, and result linkage as candidate-only data."""
        from polisyos.core.artifacts import load_core_json_artifact

        self.resolve_n5_input(input_ref, expected=input_record)
        if status == "joint_simulated" and (result_ref is None or request_binding is None):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_execution_request_binding_missing"
            )
        if request_binding is not None and type(request_binding) not in {
            GenericCycleSimulationN5RequestBindingV1,
            GenericCycleSimulationN5RequestBindingV2,
        }:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_request_binding_untyped"
            )
        if request_binding is not None:
            try:
                request_binding = type(request_binding).model_validate(
                    request_binding.model_dump(mode="python")
                )
            except (TypeError, ValueError) as exc:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_n5_request_binding_invalid"
                ) from exc
        is_typed_binding = type(request_binding) is GenericCycleSimulationN5RequestBindingV2
        draft = {
            "schema_version": (
                _N5_EXECUTION_V3_SCHEMA
                if is_typed_binding
                else _N5_EXECUTION_V2_SCHEMA
                if request_binding is not None
                else _N5_EXECUTION_SCHEMA
            ),
            "authority_purpose": "cycle_input_candidate_only",
            "status": status,
            "job_id": input_record.job_id,
            "run_id": input_record.run_id,
            "source_run_id": input_record.source_run_id,
            "tenant_id": input_record.tenant_id,
            "cell_id": input_record.cell_id,
            "input_ref": input_ref,
            "result_ref": result_ref,
            "n4_source_ref": input_record.n4_source_ref,
            "n4_child_profile_family_ref": input_record.n4_child_profile_family_ref,
            "n4_child_profile_set_ref": input_record.n4_child_profile_set_ref,
            "context_job_ref": input_record.context_job_ref,
            "profile_ref": input_record.profile_ref,
            "child_selection": input_record.child_selection,
            "profile_selection_ref": input_record.profile.profile_selection_ref,
            "world_model_record_content_hash": world_model_record_content_hash,
            "candidate_id": input_record.candidate_id,
            "candidate_atom_hash": input_record.candidate_atom_hash,
            "outcome_variable": input_record.outcome_variable,
            "limitation_code": limitation_code,
        }
        record_type = (
            GenericCycleSimulationN5ExecutionV3
            if is_typed_binding
            else GenericCycleSimulationN5ExecutionV2
            if request_binding is not None
            else GenericCycleSimulationN5ExecutionV1
        )
        if request_binding is not None:
            draft["request_binding"] = request_binding
        draft_record = record_type.model_construct(
            **draft,
            content_hash="sha256:" + "0" * 64,
        )
        if is_typed_binding:
            normalized = draft_record.model_dump(mode="python", exclude={"content_hash"})
            content_hash = _n5_typed_execution_content_hash(draft_record)
        else:
            normalized = draft_record.model_dump(mode="json", exclude={"content_hash"})
            content_hash = gy_content_hash(normalized)
        record = record_type.model_validate({**normalized, "content_hash": content_hash})
        options = self._n5_execution_write_options(record)
        payload_mode = "python" if is_typed_binding else "json"
        canon_spec = _N5_TYPED_CANON if is_typed_binding else _PROFILE_CANON
        ref = self._store.put_json(
            record.model_dump(mode=payload_mode),
            options,
            canon_spec=canon_spec,
            return_selected_profile=True,
        )
        self._verify_json_artifact(ref, expected_kind=_N5_EXECUTION_KIND)
        manifest = self._store.get_manifest(ref)
        persisted = parse_generic_cycle_simulation_n5_execution(
            load_core_json_artifact(self._store, ref)
        )
        if not self._manifest_matches_record(manifest, ref, options) or persisted != record:
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_execution_readback_mismatch"
            )
        self.resolve_n5_execution(ref, expected=record)
        return ref

    def resolve_n5_execution(
        self,
        ref: ArtifactRef,
        *,
        expected: GenericCycleSimulationN5ExecutionRecord,
    ) -> GenericCycleSimulationN5ExecutionRecord:
        """Resolve the complete selected result/input manifest and bytes."""
        from polisyos.core.artifacts import load_core_json_artifact

        if type(expected) not in {
            GenericCycleSimulationN5ExecutionV1,
            GenericCycleSimulationN5ExecutionV2,
            GenericCycleSimulationN5ExecutionV3,
        }:
            raise CycleSubstrateContextOwnerError("generic_cycle_simulation_n5_execution_untyped")
        self._verify_json_artifact(ref, expected_kind=_N5_EXECUTION_KIND)
        manifest = self._store.get_manifest(ref)
        if not self._manifest_matches_record(
            manifest, ref, self._n5_execution_write_options(expected)
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_execution_manifest_mismatch"
            )
        record = parse_generic_cycle_simulation_n5_execution(
            load_core_json_artifact(self._store, ref)
        )
        input_ref = record.input_ref
        self._verify_json_artifact(input_ref, expected_kind=_N5_INPUT_KIND)
        input_record = GenericCycleSimulationN5InputV1.model_validate(
            load_core_json_artifact(self._store, input_ref)
        )
        self.resolve_n5_input(input_ref, expected=input_record)
        source, source_candidate, source_context, port = self._replay_n5_execution_sources(
            record, input_record
        )
        if (
            type(record) is not type(expected)
            or record != expected
            or record.profile_selection_ref != input_record.profile.profile_selection_ref
            or record.child_selection != input_record.child_selection
            or record.n4_child_profile_family_ref != input_record.n4_child_profile_family_ref
            or record.n4_child_profile_set_ref != input_record.n4_child_profile_set_ref
            or record.world_model_record_content_hash
            != input_record.profile.context_inputs.world_model_record.content_hash
            or record.candidate_id != input_record.candidate_id
            or record.candidate_atom_hash != input_record.candidate_atom_hash
            or record.outcome_variable != input_record.outcome_variable
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_execution_content_mismatch"
            )
        if type(record) in {
            GenericCycleSimulationN5ExecutionV2,
            GenericCycleSimulationN5ExecutionV3,
        }:
            binding = record.request_binding
            if binding is None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_n5_execution_request_binding_missing"
                )
            request = binding.request
            expected_request = self._recompute_n5_request(
                input_record=input_record,
                source=source,
                source_candidate=source_candidate,
                source_context=source_context,
                port=port,
            )
            if not _same_typed_public_value(request, expected_request):
                raise _GenericN5VerifiedMismatchError(
                    "generic_cycle_simulation_n5_execution_request_profile_mismatch"
                )
            if record.status == "joint_simulated":
                if record.result_ref is None:
                    raise CycleSubstrateContextOwnerError(
                        "generic_cycle_simulation_n5_execution_result_missing"
                    )
                from polisyos.runtime.quality.generation_cycle import (
                    load_joint_simulation_result,
                )

                result = load_joint_simulation_result(
                    record.result_ref,
                    store=self._store,
                    expected_world_model_record_content_hash=(
                        record.world_model_record_content_hash
                    ),
                    expected_atom_ids=tuple(
                        atom.intervention_id for atom in request.intervention_atoms
                    ),
                    expected_selected_outcomes=request.selected_outcomes,
                    # Old results can lack a selected profile. They remain
                    # candidate inputs, but cannot carry a verified join.
                    expected_request=(
                        request if record.result_ref.manifest_profile_sha256 is not None else None
                    ),
                )
                if (
                    result.horizon != request.horizon
                    or result.world_model_record_ref != request.world_model_record_ref
                    or result.diagnostics.get("generic_n5_request_content_hash")
                    != binding.request_content_hash
                    or result.diagnostics.get("comparator_refs") != list(request.comparator_refs)
                    or result.diagnostics.get("requested_replications") != request.replications
                    or result.diagnostics.get("replication_seeds")
                    != [request.seed + offset for offset in range(request.replications)]
                    or result.world_credal_state_before != request.world_credal_state_before
                    or result.world_credal_state_after != request.world_credal_state_before
                ):
                    raise _GenericN5VerifiedMismatchError(
                        "generic_cycle_simulation_n5_execution_result_request_mismatch"
                    )
        return record

    def resolve_n5_execution_join(
        self,
        ref: ArtifactRef | None,
        *,
        expected: GenericN5ExecutionJoinExpectation,
    ) -> GenericN5ExecutionJoinOutcome:
        """Resolve and classify the exact cycle/result join without an existence proxy.

        This proves only the scoped candidate input consistency provided by the
        existing owner. It does not authenticate an external numerical producer.
        """
        from pydantic import ValidationError

        from polisyos.common.canonical_profile import CanonicalProfileRefusalError
        from polisyos.core.artifacts import (
            ArtifactIntegrityError,
            ArtifactOwnershipError,
            ArtifactUnavailableError,
            raise_artifact_read_access_error,
            read_core_json_artifact,
        )
        from polisyos.runtime.http.errors import RuntimeDependencyError
        from polisyos.runtime.quality.generation_cycle import (
            GenerationCycleError,
            _JointSimulationBindingMismatchError,
            _JointSimulationInvalidError,
        )

        if type(self._store) is not artifacts.SelectedProfileVerificationReader:
            # Use one selected-read boundary for all consumers of this owner,
            # including N8; retain the producer's actual store and profile set.
            replay_owner = GenericCycleSimulationAdmissionOwner(
                profiles=self.profiles,
                store=artifacts.SelectedProfileVerificationReader(self._store),
            )
            return replay_owner.resolve_n5_execution_join(ref, expected=expected)

        def refused(
            status: Literal["unavailable", "invalid", "mismatch", "not_established"], code: str
        ) -> GenericN5ExecutionJoinOutcome:
            return GenericN5ExecutionJoinOutcome(status=status, code=code)

        # Establish every independently available input binding before an
        # unavailable execution can reduce assurance to candidate-only.
        input_problem: GenericN5ExecutionJoinOutcome | None = None
        input_record: GenericCycleSimulationN5InputV1 | None = None
        if expected.input_ref.manifest_profile_sha256 is None:
            input_problem = refused("not_established", "generic_n5_selected_input_view_missing")
        else:
            try:
                input_record = GenericCycleSimulationN5InputV1.model_validate(
                    read_core_json_artifact(self._store, expected.input_ref).value
                )
                self.resolve_n5_input(expected.input_ref, expected=input_record)
            except FileNotFoundError:
                input_problem = refused("unavailable", "generic_n5_input_view_absent")
            except CanonicalProfileRefusalError as exc:
                if exc.code in {
                    "canon_profile_raw_manifest_unavailable",
                    "canon_profile_typed_manifest_unavailable",
                    "canon_profile_payload_unavailable",
                }:
                    input_problem = refused("unavailable", exc.code)
                else:
                    return refused("invalid", exc.code)
            except ArtifactUnavailableError:
                input_problem = refused("unavailable", "generic_n5_input_owner_unavailable")
            except ArtifactOwnershipError:
                raise
            except (TimeoutError, ConnectionError, RuntimeDependencyError):
                input_problem = refused("unavailable", "generic_n5_input_backend_unavailable")
            except (ArtifactIntegrityError, ValidationError):
                return refused("invalid", "generic_n5_input_integrity_invalid")
            except _GenericN5VerifiedMismatchError as exc:
                return refused("mismatch", exc.code)
            except (CycleSubstrateContextOwnerError, TypeError, ValueError) as exc:
                raise_artifact_read_access_error(exc)
                input_problem = refused(
                    "not_established", "generic_n5_input_replay_not_established"
                )
            else:
                if (input_record.tenant_id, input_record.cell_id) != (
                    expected.tenant_id,
                    expected.cell_id,
                ):
                    return refused("invalid", "generic_n5_input_scope_refused")
                if (
                    input_record.n4_source_ref != expected.n4_source_ref
                    or input_record.context_job_ref != expected.context_job_ref
                    or input_record.profile_ref != expected.profile_ref
                    or input_record.n4_child_profile_family_ref != expected.child_family_ref
                    or input_record.n4_child_profile_set_ref != expected.child_set_ref
                    or input_record.profile.profile_selection_ref != expected.profile_selection_ref
                    or (
                        expected.profile is not None
                        and (
                            input_record.profile != expected.profile
                            or input_record.child_selection != expected.child_selection
                        )
                    )
                    or input_record.design_problem_ref != expected.design_problem_ref
                    or input_record.outcome_variable != expected.outcome_variable
                    or input_record.cycle_index != expected.cycle_index
                    or input_record.candidate_id != expected.candidate_id
                    or input_record.candidate_atom_hash != expected.candidate_atom_hash
                    or input_record.profile.context_inputs.world_model_record.content_hash
                    != expected.world_model_record_content_hash
                    or input_record.job_id != expected.job_id
                    or input_record.run_id != expected.run_id
                    or input_record.source_run_id != expected.source_run_id
                ):
                    return refused("mismatch", "generic_n5_input_cycle_join_mismatch")
                if expected.profile is None:
                    input_problem = refused(
                        "not_established", "generic_n5_expected_profile_not_established"
                    )
        if ref is None:
            return input_problem or refused(
                "not_established", "generic_n5_owner_ref_not_established"
            )
        if type(ref) is not ArtifactRef or ref.kind != _N5_EXECUTION_KIND:
            return refused("invalid", "generic_n5_owner_ref_invalid")
        if ref.manifest_profile_sha256 is None or (
            expected.result_ref is not None and expected.result_ref.manifest_profile_sha256 is None
        ):
            return input_problem or refused(
                "not_established", "generic_n5_selected_owner_view_not_established"
            )
        try:
            payload = read_core_json_artifact(self._store, ref).value
            record = parse_generic_cycle_simulation_n5_execution(payload)
        except FileNotFoundError:
            return refused("unavailable", "generic_n5_owner_view_absent")
        except CanonicalProfileRefusalError as exc:
            if exc.code in {
                "canon_profile_raw_manifest_unavailable",
                "canon_profile_typed_manifest_unavailable",
                "canon_profile_payload_unavailable",
            }:
                return refused("unavailable", exc.code)
            return refused("invalid", exc.code)
        except ArtifactUnavailableError:
            return refused("unavailable", "generic_n5_owner_unavailable")
        except ArtifactOwnershipError:
            raise
        except (TimeoutError, ConnectionError, RuntimeDependencyError):
            return refused("unavailable", "generic_n5_owner_backend_unavailable")
        except (ArtifactIntegrityError, TypeError, ValueError):
            return refused("invalid", "generic_n5_owner_artifact_invalid")
        if type(record) is not GenericCycleSimulationN5ExecutionV3:
            return refused("not_established", "generic_n5_typed_request_not_established")
        if (record.tenant_id, record.cell_id) != (expected.tenant_id, expected.cell_id):
            return refused("invalid", "generic_n5_execution_scope_refused")
        if (
            record.status != expected.status
            or record.input_ref != expected.input_ref
            or record.result_ref != expected.result_ref
            or record.n4_source_ref != expected.n4_source_ref
            or record.context_job_ref != expected.context_job_ref
            or record.profile_ref != expected.profile_ref
            or record.n4_child_profile_family_ref != expected.child_family_ref
            or record.n4_child_profile_set_ref != expected.child_set_ref
            or record.profile_selection_ref != expected.profile_selection_ref
            or record.candidate_id != expected.candidate_id
            or record.candidate_atom_hash != expected.candidate_atom_hash
            or record.world_model_record_content_hash != expected.world_model_record_content_hash
            or record.job_id != expected.job_id
            or record.run_id != expected.run_id
            or record.source_run_id != expected.source_run_id
        ):
            return refused("mismatch", "generic_n5_execution_cycle_join_mismatch")
        if input_problem is not None:
            return input_problem
        try:
            verified = self.resolve_n5_execution(ref, expected=record)
        except FileNotFoundError:
            return refused("unavailable", "generic_n5_execution_dependency_absent")
        except CanonicalProfileRefusalError as exc:
            if exc.code in {
                "canon_profile_raw_manifest_unavailable",
                "canon_profile_typed_manifest_unavailable",
                "canon_profile_payload_unavailable",
            }:
                return refused("unavailable", exc.code)
            return refused("invalid", exc.code)
        except ArtifactUnavailableError:
            return refused("unavailable", "generic_n5_execution_owner_unavailable")
        except ArtifactOwnershipError:
            raise
        except (TimeoutError, ConnectionError, RuntimeDependencyError):
            return refused("unavailable", "generic_n5_execution_backend_unavailable")
        except ArtifactIntegrityError:
            return refused("invalid", "generic_n5_execution_integrity_invalid")
        except _JointSimulationBindingMismatchError as exc:
            return refused("mismatch", exc.code)
        except _JointSimulationInvalidError as exc:
            return refused("invalid", exc.code)
        except GenerationCycleError as exc:
            raise_artifact_read_access_error(exc)
            return refused("not_established", exc.code)
        except _GenericN5VerifiedMismatchError as exc:
            return refused("mismatch", exc.code)
        except (CycleSubstrateContextOwnerError, TypeError, ValueError) as exc:
            raise_artifact_read_access_error(exc)
            # Some old owner failures collapse missing, invalid, and conflicting
            # dependencies. Do not re-label their ambiguous cause as absence.
            return refused("not_established", "generic_n5_execution_replay_not_established")
        if type(verified) is not GenericCycleSimulationN5ExecutionV3 or input_record is None:
            return refused("not_established", "generic_n5_typed_request_not_established")
        return GenericN5ExecutionJoinOutcome(
            status="resolved", execution=verified, input_record=input_record
        )

    def _replay_n5_execution_sources(
        self,
        record: GenericCycleSimulationN5ExecutionRecord,
        input_record: GenericCycleSimulationN5InputV1,
    ) -> tuple[object, object, CycleSubstrateContext, object]:
        """Reopen the exact N4 candidate, profile context, and canonical N5 builder inputs."""
        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.design_generation import ShadowGeneratedCandidate
        from polisyos.runtime.quality.generation_cycle import JointSimulationPort
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
        )

        if (
            record.n4_source_ref != input_record.n4_source_ref
            or record.context_job_ref != input_record.context_job_ref
            or record.profile_ref != input_record.profile_ref
            or record.n4_child_profile_family_ref != input_record.n4_child_profile_family_ref
            or record.n4_child_profile_set_ref != input_record.n4_child_profile_set_ref
            or (
                record.job_id,
                record.run_id,
                record.source_run_id,
                record.tenant_id,
                record.cell_id,
            )
            != (
                input_record.job_id,
                input_record.run_id,
                input_record.source_run_id,
                input_record.tenant_id,
                input_record.cell_id,
            )
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_source_scope_mismatch"
            )
        source = GenerationSourceRepository(self._store).load(
            input_record.n4_source_ref,
            run_id=input_record.source_run_id,
            expected_job_id=input_record.job_id,
            expected_run_id=input_record.run_id,
            expected_tenant_id=input_record.tenant_id,
            expected_cell_id=input_record.cell_id,
            context_job_ref=input_record.context_job_ref,
            profile_ref=input_record.profile_ref,
            n4_child_profile_family_ref=input_record.n4_child_profile_family_ref,
        )
        problem = source.problem
        if (
            type(problem) is not DesignProblem
            or source.cycle_index != input_record.cycle_index
            or cycle_job_design_problem_ref(problem) != input_record.design_problem_ref
            or source.cycle_substrate_context is None
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_source_problem_mismatch"
            )
        profile = self.resolve_profile_historical(
            input_record.profile_ref,
            expected_profile=input_record.profile,
            job_id=input_record.job_id,
            run_id=input_record.run_id,
            tenant_id=input_record.tenant_id,
            cell_id=input_record.cell_id,
        )
        context_owner = CycleSubstrateContextArtifactOwner(store=self._store)
        context_record = context_owner.resolve_historical_job_artifact(
            input_record.context_job_ref,
            problem=problem,
            expected_job_id=input_record.job_id,
            expected_run_id=input_record.run_id,
            expected_tenant_id=input_record.tenant_id,
            expected_cell_id=input_record.cell_id,
        )
        source_context = context_record.context
        if (
            source.cycle_substrate_context != source_context
            or source.cycle_substrate_context.content_hash != source_context.content_hash
            or not self.context_matches_profile(source_context, profile, problem)
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_context_source_mismatch"
            )
        expected_context = source_context
        candidates = tuple(
            candidate
            for candidate in source.generation_result.candidates
            if getattr(candidate, "candidate_id", None) == input_record.candidate_id
            and getattr(getattr(candidate, "atom", None), "content_hash", None)
            == input_record.candidate_atom_hash
        )
        if len(candidates) != 1 or type(candidates[0]) is not ShadowGeneratedCandidate:
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_candidate_source_mismatch"
            )
        candidate = candidates[0]
        if input_record.child_selection is not None:
            selection = input_record.child_selection
            if (
                selection.problem != problem
                or selection.n4_child_profile_family_ref != input_record.n4_child_profile_family_ref
            ):
                raise _GenericN5VerifiedMismatchError(
                    "generic_cycle_simulation_n5_child_selection_source_mismatch"
                )
            family = self.resolve_child_profile_family_historical(
                input_record.n4_child_profile_family_ref,
                expected_parent_handoff=selection.parent_handoff,
                expected_parent_problem=selection.parent_problem,
            )
            if not any(
                member.profile_id == profile.profile_id
                and member.profile_ref == input_record.profile_ref
                and member.profile_selection_ref == profile.profile_selection_ref
                for member in family.children
            ):
                raise _GenericN5VerifiedMismatchError(
                    "generic_cycle_simulation_n5_child_profile_not_in_family"
                )
        elif profile.profile_selection_kind != "problem":
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_child_selection_missing"
            )
        if profile.profile_selection_kind == "problem":
            expected_selection = cycle_job_profile_selection_ref(problem)
        else:
            selection = input_record.child_selection
            if selection is None:
                raise CycleSubstrateContextOwnerError(
                    "generic_cycle_simulation_n5_child_selection_missing"
                )
            expected_selection = generic_n4_child_profile_selection_ref(
                selection.problem,
                parent_problem_ref=selection.parent_problem_ref,
                source_result_ref=selection.source_result_ref,
                source_atom_refs=selection.source_atom_refs,
                semantic_ref=selection.semantic_ref,
            )
        if (
            profile.profile_selection_ref != expected_selection
            or record.profile_selection_ref != expected_selection
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_profile_selection_mismatch"
            )
        self._verify_json_artifact(
            profile.world_model_record_ref,
            expected_kind="runtime.quality.world_model_record",
        )
        world = load_world_model_record(self._store, profile.world_model_record_ref)
        views = world_model_artifact_views(world)
        if (
            world != profile.context_inputs.world_model_record
            or views.substrate_registry_ref is None
            or artifact_ref_identity_key(views.substrate_registry_ref)
            != artifact_ref_identity_key(profile.substrate_registry_ref)
            or len(views.ncm_refs) != 1
            or artifact_ref_identity_key(views.ncm_refs[0])
            != artifact_ref_identity_key(profile.selected_ncm_ref)
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_wmr_profile_mismatch"
            )
        self._verify_json_artifact(
            profile.substrate_registry_ref,
            expected_kind="runtime.quality.production_data_substrate_registry",
        )
        registry = load_substrate_registry(self._store, profile.substrate_registry_ref)
        if registry != profile.context_inputs.substrate_registry:
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_registry_profile_mismatch"
            )
        self._verify_json_artifact(profile.selected_ncm_ref, expected_kind="ir.ncm_spec")
        self._verify_default_ncm(profile.selected_ncm_ref)

        port = JointSimulationPort(
            cycle_substrate_context=expected_context,
            artifact_store=self._store,
            generic_cycle_simulation_admission_owner=self,
            generic_cycle_simulation_handoff=GenericCycleSimulationContextHandoffV1(
                context=expected_context,
                context_job_ref=input_record.context_job_ref,
                profile=profile,
                profile_ref=input_record.profile_ref,
                job_id=input_record.job_id,
                run_id=input_record.run_id,
                tenant_id=input_record.tenant_id,
                cell_id=input_record.cell_id,
                n4_child_profile_family_ref=input_record.n4_child_profile_family_ref,
            ),
            generic_cycle_simulation_child_selection=input_record.child_selection,
            generic_n4_child_profile_set_ref=input_record.n4_child_profile_set_ref,
        )
        return source, candidate, expected_context, port

    def _recompute_n5_request(
        self,
        *,
        input_record: GenericCycleSimulationN5InputV1,
        source: object,
        source_candidate: object,
        source_context: CycleSubstrateContext,
        port: object,
    ) -> JointSimulationRequest:
        """Recompute the complete request from the reopened N4 source and profile."""
        from polisyos.runtime.quality.design_generation import ShadowGeneratedCandidate
        from polisyos.runtime.quality.generation_cycle import (
            JointSimulationPort,
            _value_outcome_variable,
        )
        from polisyos.runtime.quality.intervention_atom_binding import (
            InterventionAtomBinding,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import EnginePlan

        if (
            type(port) is not JointSimulationPort
            or type(source_candidate) is not ShadowGeneratedCandidate
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_request_recompute_inputs_untyped"
            )
        atoms = tuple(getattr(source_candidate, "intervention_atoms", ()) or ())
        if not atoms:
            atoms = (source_candidate.atom,)
        if not atoms or any(type(atom) is not InterventionAtomBinding for atom in atoms):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_n5_request_atoms_untyped"
            )
        outcome = _value_outcome_variable(source_candidate, source.problem)
        if (
            outcome != input_record.outcome_variable
            or outcome not in input_record.n5.baseline_state
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_request_outcome_mismatch"
            )
        world_record = port._context_world_model_record(
            candidate=source_candidate, problem=source.problem
        )
        if (
            source_context != port._cycle_substrate_context
            or world_record != input_record.profile.context_inputs.world_model_record
        ):
            raise _GenericN5VerifiedMismatchError(
                "generic_cycle_simulation_n5_request_world_model_mismatch"
            )
        variable_map = port._joint_simulation_variable_map(
            atoms=atoms, outcome=outcome, raw_hint=None
        )
        ncm_spec = port._resolve_joint_simulation_ncm(
            problem=source.problem,
            world_record=world_record,
        )
        expected = JointSimulationRequest(
            world_model_record_ref=world_record.world_model_record_id,
            world_model_record=world_record,
            intervention_atoms=atoms,
            selected_outcomes=(outcome,),
            horizon=input_record.n5.horizon,
            engine_plan=(
                EnginePlan(
                    engine_kind=input_record.n5.resource,
                    objective_ref=f"objective://{outcome}",
                    eligibility_conditions=("acyclic", "counterfactual_do_worlds"),
                    ncm_spec=ncm_spec,
                    variable_map=variable_map,
                ),
            ),
            baseline_state=dict(input_record.n5.baseline_state),
            comparator_refs=input_record.n5.comparator_refs,
            budget_ref=input_record.n5.budget_ref,
            seed=input_record.n5.seed,
            replications=input_record.n5.replications,
        )
        return expected

    def _n5_input_write_options(
        self,
        record: GenericCycleSimulationN5InputV1,
    ) -> artifacts.ArtifactWriteOptions:
        inputs = [
            input_ref_from_artifact_ref(record.n4_source_ref, role="n4_generation_source"),
            input_ref_from_artifact_ref(record.context_job_ref, role="cycle_substrate_context_job"),
            input_ref_from_artifact_ref(
                record.profile_ref, role="generic_cycle_simulation_profile"
            ),
        ]
        if record.n4_child_profile_family_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    record.n4_child_profile_family_ref,
                    role="generic_cycle_simulation_child_profile_family",
                )
            )
        if record.n4_child_profile_set_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    record.n4_child_profile_set_ref,
                    role="recursive_n4_child_profile_set",
                )
            )
        return artifacts.ArtifactWriteOptions(
            kind=_N5_INPUT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=_N5_INPUT_SCHEMA, version="1.0"),
            producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
            inputs=inputs,
            canon=artifacts.CanonInfo.from_spec(_PROFILE_CANON),
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=record.tenant_id, cell_id=record.cell_id
            ),
            same_input_closure=ArtifactSameInputClosureInfo(
                closure_id=f"generic-cycle-n5:{record.run_id}:{record.job_id}:{record.candidate_id}",
                status="candidate_only",
                run_id=record.run_id,
                job_id=record.job_id,
                tenant_id=record.tenant_id,
                cell_id=record.cell_id,
            ),
        )

    def _n5_execution_write_options(
        self,
        record: GenericCycleSimulationN5ExecutionRecord,
    ) -> artifacts.ArtifactWriteOptions:
        inputs = [
            input_ref_from_artifact_ref(record.input_ref, role="generic_n5_input"),
            input_ref_from_artifact_ref(record.n4_source_ref, role="n4_generation_source"),
            input_ref_from_artifact_ref(record.context_job_ref, role="cycle_substrate_context_job"),
            input_ref_from_artifact_ref(
                record.profile_ref, role="generic_cycle_simulation_profile"
            ),
        ]
        if record.result_ref is not None:
            inputs.insert(
                1,
                input_ref_from_artifact_ref(record.result_ref, role="joint_simulation_result"),
            )
        if record.n4_child_profile_family_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    record.n4_child_profile_family_ref,
                    role="generic_cycle_simulation_child_profile_family",
                )
            )
        if record.n4_child_profile_set_ref is not None:
            inputs.append(
                input_ref_from_artifact_ref(
                    record.n4_child_profile_set_ref,
                    role="recursive_n4_child_profile_set",
                )
            )
        return artifacts.ArtifactWriteOptions(
            kind=_N5_EXECUTION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=(
                    _N5_EXECUTION_V3_SCHEMA
                    if type(record) is GenericCycleSimulationN5ExecutionV3
                    else _N5_EXECUTION_V2_SCHEMA
                    if type(record) is GenericCycleSimulationN5ExecutionV2
                    else _N5_EXECUTION_SCHEMA
                ),
                version=(
                    "3.0"
                    if type(record) is GenericCycleSimulationN5ExecutionV3
                    else "2.0"
                    if type(record) is GenericCycleSimulationN5ExecutionV2
                    else "1.0"
                ),
            ),
            producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
            inputs=inputs,
            canon=artifacts.CanonInfo.from_spec(
                _N5_TYPED_CANON
                if type(record) is GenericCycleSimulationN5ExecutionV3
                else _PROFILE_CANON
            ),
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=record.tenant_id, cell_id=record.cell_id
            ),
            same_input_closure=ArtifactSameInputClosureInfo(
                closure_id=f"generic-cycle-n5-execution:{record.run_id}:{record.job_id}:{record.candidate_id}",
                status="candidate_only",
                run_id=record.run_id,
                job_id=record.job_id,
                tenant_id=record.tenant_id,
                cell_id=record.cell_id,
            ),
        )

    @staticmethod
    def _manifest_matches_record(
        manifest: artifacts.ArtifactManifest,
        ref: ArtifactRef,
        expected: artifacts.ArtifactWriteOptions,
    ) -> bool:
        return (
            manifest.artifact_id == ref.artifact_id
            and manifest.kind == expected.kind
            and manifest.media_type == expected.media_type
            and manifest.artifact_schema == expected.schema
            and manifest.producer == expected.producer
            and manifest.inputs == expected.inputs
            and manifest.canon == expected.canon
            and manifest.tenant_context == expected.tenant_context
            and manifest.same_input_closure == expected.same_input_closure
            and manifest.env == expected.env
            and manifest.governance == expected.governance
            and manifest.authority == expected.authority
            and manifest.warnings == (expected.warnings or [])
        )

    def _verify_json_artifact(self, ref: ArtifactRef, *, expected_kind: str) -> None:
        if (
            type(ref) is not ArtifactRef
            or ref.kind != expected_kind
            or ref.media_type != "application/json"
            or not self._store.verify(ref).ok
        ):
            raise ValueError("generic_cycle_simulation_input_integrity_failed")
        manifest = self._store.get_manifest(ref)
        body = self._store.get_bytes(ref)
        if (
            str(manifest.artifact_id) != str(ref.artifact_id)
            or manifest.kind != ref.kind
            or manifest.media_type != ref.media_type
            or "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id)
        ):
            raise ValueError("generic_cycle_simulation_input_identity_mismatch")

    def _verify_default_ncm(self, ref: ArtifactRef) -> None:
        """Load only the WMR-default NCM view through the public Core→IR adapter."""
        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.ir import NCMSpecRef, load_ncm_spec

        typed = NCMSpecRef.model_validate(ref.model_dump(mode="python"))
        load_ncm_spec(ensure_ir_artifact_store(self._store), typed)

    def _profile_write_options(
        self,
        *,
        profile: GenericCycleSimulationProfileV1,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> artifacts.ArtifactWriteOptions:
        input_refs = [
            input_ref_from_artifact_ref(profile.world_model_record_ref, role="world_model_record"),
            input_ref_from_artifact_ref(profile.substrate_registry_ref, role="substrate_registry"),
            input_ref_from_artifact_ref(profile.selected_ncm_ref, role="selected_ncm"),
        ]
        return artifacts.ArtifactWriteOptions(
            kind=_PROFILE_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=_PROFILE_SCHEMA, version=_PROFILE_SCHEMA_VERSION),
            producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
            inputs=input_refs,
            canon=artifacts.CanonInfo.from_spec(_PROFILE_CANON),
            tenant_context=ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id),
            same_input_closure=ArtifactSameInputClosureInfo(
                closure_id=f"generic-cycle-simulation:{run_id}:{job_id}:{profile.profile_id}",
                status="candidate_only",
                run_id=run_id,
                job_id=job_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
            ),
        )

    def _child_profile_family_write_options(
        self,
        family: GenericCycleSimulationChildProfileFamilyV1,
    ) -> artifacts.ArtifactWriteOptions:
        inputs = [
            input_ref_from_artifact_ref(
                family.parent_context_job_ref, role="parent_cycle_substrate_context_job"
            ),
            input_ref_from_artifact_ref(
                family.parent_profile_ref,
                role="parent_generic_cycle_simulation_profile",
            ),
        ]
        inputs.extend(
            input_ref_from_artifact_ref(
                member.profile_ref,
                role=f"configured_child_profile:{member.profile_id}",
            )
            for member in family.children
        )
        return artifacts.ArtifactWriteOptions(
            kind=_CHILD_PROFILE_FAMILY_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=_CHILD_PROFILE_FAMILY_SCHEMA,
                version=_CHILD_PROFILE_FAMILY_SCHEMA_VERSION,
            ),
            producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
            inputs=inputs,
            canon=artifacts.CanonInfo.from_spec(_PROFILE_CANON),
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=family.tenant_id, cell_id=family.cell_id
            ),
            same_input_closure=ArtifactSameInputClosureInfo(
                closure_id=(
                    f"generic-cycle-child-profile-family:{family.run_id}:"
                    f"{family.job_id}:{family.parent_profile_id}"
                ),
                status="candidate_only",
                run_id=family.run_id,
                job_id=family.job_id,
                tenant_id=family.tenant_id,
                cell_id=family.cell_id,
            ),
        )

    def _manifest_matches_child_profile_family(
        self,
        manifest: artifacts.ArtifactManifest,
        ref: ArtifactRef,
        family: GenericCycleSimulationChildProfileFamilyV1,
    ) -> bool:
        expected = self._child_profile_family_write_options(family)
        return (
            manifest.artifact_id == ref.artifact_id
            and manifest.kind == expected.kind
            and manifest.media_type == expected.media_type
            and manifest.artifact_schema == expected.schema
            and manifest.producer == expected.producer
            and manifest.inputs == expected.inputs
            and manifest.canon == expected.canon
            and manifest.tenant_context == expected.tenant_context
            and manifest.same_input_closure == expected.same_input_closure
            and manifest.env == expected.env
            and manifest.governance == expected.governance
            and manifest.authority == expected.authority
            and manifest.warnings == (expected.warnings or [])
            and ref.kind == expected.kind
            and ref.media_type == expected.media_type
        )

    @staticmethod
    def _manifest_matches_profile(
        manifest: artifacts.ArtifactManifest,
        ref: ArtifactRef,
        expected: artifacts.ArtifactWriteOptions,
    ) -> bool:
        """Recompute the complete written profile projection, not marker presence."""
        return (
            manifest.artifact_id == ref.artifact_id
            and manifest.kind == expected.kind
            and manifest.media_type == expected.media_type
            and manifest.artifact_schema == expected.schema
            and manifest.producer == expected.producer
            and manifest.inputs == expected.inputs
            and manifest.canon == expected.canon
            and manifest.tenant_context == expected.tenant_context
            and manifest.same_input_closure == expected.same_input_closure
            and manifest.env == expected.env
            and manifest.governance == expected.governance
            and manifest.authority == expected.authority
            and manifest.warnings == (expected.warnings or [])
            and ref.kind == expected.kind
            and ref.media_type == expected.media_type
        )

    def _persist_profile(
        self,
        *,
        profile: GenericCycleSimulationProfileV1,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
    ) -> ArtifactRef:
        self._require_scope(
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        options = self._profile_write_options(
            profile=profile,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        ref = self._store.put_json(
            profile.model_dump(mode="json"),
            options,
            canon_spec=_PROFILE_CANON,
        )
        self.resolve_profile(
            ref,
            expected_profile=profile,
            job_id=job_id,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        return ref

    @staticmethod
    def _require_scope(
        *,
        job_id: str,
        run_id: str,
        tenant_id: str,
        cell_id: str,
        verified_nl_job_scope: VerifiedNLJobScope,
    ) -> None:
        if type(verified_nl_job_scope) is not VerifiedNLJobScope or not (
            verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
            and verified_nl_job_scope.intent_band == "simulate_only_attempt"
            and verified_nl_job_scope.canonical_mode == "simulate_only"
            and verified_nl_job_scope.job_id == job_id
            and verified_nl_job_scope.run_id == run_id
            and verified_nl_job_scope.tenant_id == tenant_id
            and verified_nl_job_scope.cell_id == cell_id
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_verified_worker_scope_not_established"
            )
        if not all(
            isinstance(value, str) and value.strip()
            for value in (job_id, run_id, tenant_id, cell_id)
        ):
            raise CycleSubstrateContextOwnerError(
                "generic_cycle_simulation_job_scope_not_established"
            )
