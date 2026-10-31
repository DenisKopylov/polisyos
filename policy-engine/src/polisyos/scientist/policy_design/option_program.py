"""Reconcile explicit option intent with the final selected policy program.

The supported interpretation is deliberately an explicit IR contract. This owner
does not assign policy meaning to prose, attest legal validity, or prove that a
registered mechanism implements its advertised effect. A match concerns the
declared program; execution correspondence remains separately unestablished.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    CoreArtifactOwnerProfile,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo, artifact_ref_identity_key
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.scientist import PolicyOptionSetRef, PolicyRequestFrameRef
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec
from polisyos.ir.governance.schedule import schedule_range
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.scientist.policy_design.option_program_contracts import (
    DeclaredProgramCorrespondenceStatus,
)
from polisyos.scientist.policy_design.schema import (
    TargetPopulationSpec,
    load_policy_candidate_schema,
    policy_candidate_trinity_contents_match,
)
from polisyos.scientist.validation.policy_verified.models import (
    load_policy_option_set,
    load_policy_request_frame,
)

_VERSION = "1.0"
_KIND = "scientist.option_program_relation"
_SCHEMA = "polisyos.scientist.policy_design.OptionProgramRelation"
_OWNER = CoreArtifactOwnerProfile(
    kind=_KIND,
    media_type="application/json",
    schema_variants=(SchemaInfo(name=_SCHEMA, version=_VERSION),),
    payload_schema_version_by_manifest=(((_SCHEMA, _VERSION), _VERSION),),
)


class ExplicitPolicyProgramIntent(BaseModel):
    """An explicit, typed program obligation stored as an option's whole outline.

    Descriptive option prose is not interpreted. Parameters, selectors, units
    represented in parameter values, schedules and constraints are compared as
    their declared IR values; no unit conversion or natural-language inference
    is performed. Search may continue after a mismatch, but must reissue this
    interpretation or retain the correspondence limitation.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["polisyos.explicit_policy_program_intent.v1"]
    jurisdiction: str = Field(min_length=1)
    as_of: str | None
    policy_spec: PolicySpec
    target_population: TargetPopulationSpec
    hard_constraints: list[ConstraintSpec] = Field(default_factory=list)
    soft_constraints: list[ConstraintSpec] = Field(default_factory=list)


class OptionProgramSelection(BaseModel):
    """Exact sources and final champion selected by the calling workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_ref: ArtifactRef
    option_set_ref: ArtifactRef
    candidate_ref: ArtifactRef
    trinity_ref: ArtifactRef
    selected_option_ids: tuple[str, ...] = Field(min_length=1)
    selection_mode: Literal["single", "subset", "joint"] = "single"

    @model_validator(mode="after")
    def _validate_selection(self) -> OptionProgramSelection:
        if len(set(self.selected_option_ids)) != len(self.selected_option_ids):
            raise ValueError("option_program_duplicate_selected_option")
        if any(not item for item in self.selected_option_ids):
            raise ValueError("option_program_empty_selected_option")
        for ref in self.source_refs():
            if ref.manifest_profile_sha256 is None:
                raise ValueError("option_program_selected_profile_required")
        return self

    def source_refs(self) -> tuple[ArtifactRef, ...]:
        """Return all selected source references in their fixed role order."""
        return self.request_ref, self.option_set_ref, self.candidate_ref, self.trinity_ref


class ProgramActionBinding(BaseModel):
    """A recomputed mapping from one intent action to the final program location."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str
    intervention_id: str
    program_path: str


class OptionProgramRelation(BaseModel):
    """Candidate-grade result of declared-program semantic reconciliation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    selection: OptionProgramSelection
    status: DeclaredProgramCorrespondenceStatus
    reason_codes: tuple[str, ...] = ()
    action_bindings: tuple[ProgramActionBinding, ...] = ()
    interpretation_profile: Literal["explicit_policy_spec.v1"] = "explicit_policy_spec.v1"
    authority_boundary: Literal["candidate_declared_program_only"] = (
        "candidate_declared_program_only"
    )
    execution_correspondence: Literal["not_established"] = "not_established"
    intent_provenance: Literal["consumer_asserted"] = "consumer_asserted"


def _lineage_matches(inputs: list[InputRef], role: str, expected: ArtifactRef) -> bool:
    selected = [item for item in inputs if item.role == role]
    return len(selected) == 1 and selected[0] == input_ref_from_artifact_ref(expected, role=role)


def _content_bytes(payload: object) -> bytes:
    return to_canonical_bytes(payload, spec=CanonSpec(forbid_floats=False, exclude_none=False))


def _policy_semantics(policy: PolicySpec) -> bytes:
    """Compare the complete declared program, with equivalent schedule spellings."""
    payload = policy.model_dump(
        mode="json",
        exclude={"policy_id", "name", "description", "labels", "version_tag", "notes"},
    )
    payload["global_schedule"] = (
        schedule_range(policy.global_schedule) if policy.global_schedule is not None else None
    )
    interventions = []
    for intervention in policy.interventions:
        action = intervention.model_dump(mode="json", exclude={"notes"})
        action["schedule"] = schedule_range(intervention.schedule)
        interventions.append(action)
    payload["interventions"] = interventions
    return _content_bytes(payload)


def reconcile_option_program(
    store: ArtifactStore,
    selection: OptionProgramSelection,
) -> OptionProgramRelation:
    """Independently compare selected typed intent with the actual final program.

    Missing semantics yield a named limitation. Bad source selection or corrupted
    bytes raise rather than becoming a successful match. This compares actual
    content, never a producer-supplied action mapping or previously stored status.
    """
    selection = OptionProgramSelection.model_validate(selection.model_dump(mode="json"))
    frame = load_policy_request_frame(
        store, PolicyRequestFrameRef.model_validate(selection.request_ref.model_dump())
    )
    options = load_policy_option_set(
        store, PolicyOptionSetRef.model_validate(selection.option_set_ref.model_dump())
    )
    candidate = load_policy_candidate_schema(store, selection.candidate_ref)
    trinity = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), selection.trinity_ref)
    # Compare admitted source content before the Core/IR typed decoders choose
    # different valid branches of IR unions (for example ConstraintSpec.value).
    # Canonical content bytes also keep boolean and numeric values distinct.
    candidate_payload = load_core_json_artifact(store, selection.candidate_ref)
    trinity_payload = load_core_json_artifact(store, selection.trinity_ref)
    if not policy_candidate_trinity_contents_match(candidate_payload, trinity_payload):
        raise ValueError("option_program_candidate_trinity_mismatch")
    if options.request_id != frame.request_id:
        raise ValueError("option_program_request_mismatch")
    if not _lineage_matches(
        store.get_manifest(selection.option_set_ref).inputs,
        "policy_request_frame",
        selection.request_ref,
    ):
        raise ValueError("option_program_option_request_edge_mismatch")

    def result(
        status: DeclaredProgramCorrespondenceStatus,
        *reasons: str,
        bindings: tuple[ProgramActionBinding, ...] = (),
    ) -> OptionProgramRelation:
        return OptionProgramRelation(
            selection=selection, status=status, reason_codes=reasons, action_bindings=bindings
        )

    all_options = [*options.verified_options, *options.hypothesis_options]
    ids = [item.option_id for item in all_options]
    if len(set(ids)) != len(ids):
        raise ValueError("option_program_option_identity_ambiguous")
    if any(item not in ids for item in selection.selected_option_ids):
        raise ValueError("option_program_selected_option_missing")
    if selection.selection_mode != "single" or len(selection.selected_option_ids) != 1:
        return result("not_established", "option_program_composition_semantics_not_established")
    option = all_options[ids.index(selection.selected_option_ids[0])]
    option_payload = load_core_json_artifact(store, selection.option_set_ref)
    raw_options = [
        *option_payload.get("verified_options", []),
        *option_payload.get("hypothesis_options", []),
    ]
    try:
        intent = ExplicitPolicyProgramIntent.model_validate(
            raw_options[ids.index(option.option_id)].get("intervention_outline", {})
        )
    except ValidationError:
        return result("not_established", "option_program_typed_intent_not_established")
    if option.constraints or option.thresholds or option.timing:
        return result("not_established", "option_program_prose_obligations_not_interpreted")
    if frame.schema_version != "1.1" or getattr(frame, "jurisdiction_source", None) not in {
        "policy_request_jurisdiction",
        "jurisdiction",
    }:
        return result("not_established", "option_program_request_scope_not_established")
    if intent.jurisdiction != frame.jurisdiction or intent.as_of != frame.as_of:
        return result("mismatch", "option_program_scope_or_time_mismatch")
    if intent.target_population != candidate.target_population:
        return result("mismatch", "option_program_population_mismatch")
    problem = trinity.problem_frame
    if _content_bytes(
        [item.model_dump(mode="json") for item in intent.hard_constraints]
    ) != _content_bytes(
        [item.model_dump(mode="json") for item in problem.hard_constraints]
    ) or _content_bytes(
        [item.model_dump(mode="json") for item in intent.soft_constraints]
    ) != _content_bytes([item.model_dump(mode="json") for item in problem.soft_constraints]):
        return result("mismatch", "option_program_constraints_mismatch")
    if _policy_semantics(intent.policy_spec) != _policy_semantics(trinity.policy_spec):
        return result("mismatch", "option_program_declared_actions_mismatch")
    bindings = tuple(
        ProgramActionBinding(
            option_id=option.option_id,
            intervention_id=action.intervention_id,
            program_path=f"policy_spec.interventions[{index}]",
        )
        for index, action in enumerate(trinity.policy_spec.interventions)
    )
    return result("declared_program_match", bindings=bindings)


def produce_option_program_relation(
    store: ArtifactStore,
    selection: OptionProgramSelection,
) -> ArtifactRef:
    """Persist a freshly recomputed relation and its exact source edges."""
    relation = reconcile_option_program(store, selection)
    return store.put_json(
        relation,
        PutOptions(
            kind=_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA, version=_VERSION),
            inputs=_source_inputs(relation.selection),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )


def _source_inputs(selection: OptionProgramSelection) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in zip(
            ("policy_request_frame", "policy_option_set", "final_candidate", "final_trinity"),
            selection.source_refs(),
            strict=True,
        )
    ]


def load_option_program_relation(
    store: ArtifactStore,
    ref: ArtifactRef | None,
    *,
    selection: OptionProgramSelection,
) -> OptionProgramRelation:
    """Read and recompute a relation against the caller's actual final selection.

    A forged status, stale champion, substituted edge, incomplete mapping or
    foreign selected manifest cannot be promoted by the persisted result.
    """
    if ref is None:
        raise ValueError("option_program_relation_missing")
    if ref.manifest_profile_sha256 is None:
        raise ValueError("option_program_relation_selected_profile_required")
    selection = OptionProgramSelection.model_validate(selection.model_dump(mode="json"))
    persisted = validate_owned_core_model_json_artifact(
        OptionProgramRelation, store, ref, expected_owner=_OWNER
    ).value
    if (
        any(
            artifact_ref_identity_key(left) != artifact_ref_identity_key(right)
            for left, right in zip(
                persisted.selection.source_refs(), selection.source_refs(), strict=True
            )
        )
        or persisted.selection.selected_option_ids != selection.selected_option_ids
        or persisted.selection.selection_mode != selection.selection_mode
    ):
        raise ValueError("option_program_relation_selection_mismatch")
    if store.get_manifest(ref).inputs != _source_inputs(selection):
        raise ValueError("option_program_relation_source_edges_mismatch")
    recomputed = reconcile_option_program(store, selection)
    if persisted.model_dump(mode="json") != recomputed.model_dump(mode="json"):
        raise ValueError("option_program_relation_result_not_recomputed")
    return recomputed


__all__ = [
    "ExplicitPolicyProgramIntent",
    "OptionProgramRelation",
    "OptionProgramSelection",
    "ProgramActionBinding",
    "load_option_program_relation",
    "produce_option_program_relation",
    "reconcile_option_program",
]
