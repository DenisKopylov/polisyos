"""Persist the actual Stage B result without treating its observations as authority.

This carrier is deliberately not itself proof that opaque Stage B payloads have
complete artifact-reference semantics. Selected child release must refuse until
those payloads are represented by their actual typed owners.
"""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    CoreArtifactOwnerProfile,
    SchemaInfo,
    input_ref_from_artifact_ref,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts import ArtifactStore, InputRef
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

STAGE_B_PROJECTION_KIND = "scientist.hierarchical_search.stage_b_projection"
STAGE_B_PROJECTION_SCHEMA_NAME = "polisyos.scientist.hierarchical_search.StageBProjection"
STAGE_B_PROJECTION_SCHEMA_VERSION = "1.0"


class StageBProjectionRefusalError(ValueError):
    """A Stage B observation cannot be preserved with its declared sources."""


def _source_ref(value: object) -> ArtifactRef | None:
    if value is None:
        return None
    try:
        ref = ArtifactRef.model_validate(
            value.model_dump(mode="json") if isinstance(value, ArtifactRef) else value
        )
    except (TypeError, ValueError) as exc:
        raise StageBProjectionRefusalError("stage_b_source_ref_invalid") from exc
    if not ref.manifest_profile_sha256:
        raise StageBProjectionRefusalError("stage_b_source_profile_required")
    return ref


class StageBProjection(BaseModel):
    """Exact Stage B observation and selected source refs, not a rank or release grant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = STAGE_B_PROJECTION_SCHEMA_VERSION
    candidate_ref: ArtifactRef | None = None
    evaluation_ref: ArtifactRef | None = None
    simulation_result_ref: ArtifactRef | None = None
    score_status: str | None = None
    result: dict[str, Any]

    @model_validator(mode="after")
    def bind_result_fields(self) -> StageBProjection:
        """Forbid an envelope that disagrees with the actual producer result."""
        _require_lossless_json(self.result)
        candidate = _source_ref(self.result.get("candidate_ref"))
        evaluation = _source_ref(self.result.get("policy_evaluation_ref"))
        simulation = _source_ref(self.result.get("simulation_result_ref"))
        if (
            candidate != self.candidate_ref
            or evaluation != self.evaluation_ref
            or simulation != self.simulation_result_ref
        ):
            raise StageBProjectionRefusalError("stage_b_projection_source_mismatch")
        status = self.result.get("objective_score_status")
        if status is not None and type(status) is not str:
            raise StageBProjectionRefusalError("stage_b_score_status_invalid")
        if status != self.score_status:
            raise StageBProjectionRefusalError("stage_b_projection_score_status_mismatch")
        return self

    def original_result(self) -> dict[str, Any]:
        """Return an isolated copy of the observation for the existing consumer."""
        return deepcopy(self.result)


def _require_lossless_json(value: object, depth: int = 0) -> None:
    if depth > 100:
        raise StageBProjectionRefusalError("stage_b_result_depth_exceeded")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if isfinite(value):
            return
        raise StageBProjectionRefusalError("stage_b_result_nonfinite")
    if type(value) is list:
        for item in value:
            _require_lossless_json(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise StageBProjectionRefusalError("stage_b_result_key_not_string")
            _require_lossless_json(item, depth + 1)
        return
    raise StageBProjectionRefusalError("stage_b_result_non_json_value")


def stage_b_projection(result: dict[str, Any]) -> StageBProjection:
    """Bind a real evaluator result; absent sources remain candidate observations."""
    if type(result) is not dict:
        raise StageBProjectionRefusalError("stage_b_result_invalid")
    _require_lossless_json(result)
    snapshot = deepcopy(result)
    return StageBProjection(
        candidate_ref=_source_ref(snapshot.get("candidate_ref")),
        evaluation_ref=_source_ref(snapshot.get("policy_evaluation_ref")),
        simulation_result_ref=_source_ref(snapshot.get("simulation_result_ref")),
        score_status=snapshot.get("objective_score_status"),
        result=snapshot,
    )


def persist_stage_b_projection(store: ArtifactStore, result: dict[str, Any]) -> ArtifactRef:
    """Persist the observation and its explicit selected source input edges.

    The producer must call this on its actual evaluator output. The two typed
    refs are not a declaration that arbitrary nested payload refs are complete.
    """
    projection = stage_b_projection(result)
    inputs = []
    if projection.candidate_ref is not None:
        inputs.append(input_ref_from_artifact_ref(projection.candidate_ref, role="candidate"))
    if projection.evaluation_ref is not None:
        inputs.append(input_ref_from_artifact_ref(projection.evaluation_ref, role="evaluation"))
    if projection.simulation_result_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(projection.simulation_result_ref, role="simulation_result")
        )
    return store.put_json(
        projection,
        ArtifactWriteOptions(
            kind=STAGE_B_PROJECTION_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=STAGE_B_PROJECTION_SCHEMA_NAME, version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def load_stage_b_projection(store: object, ref: ArtifactRef) -> StageBProjection:
    """Read the exact selected owner-bound projection without asserting authority."""
    if not ref.manifest_profile_sha256:
        raise StageBProjectionRefusalError("stage_b_projection_profile_required")
    owner = CoreArtifactOwnerProfile(
        kind=STAGE_B_PROJECTION_KIND,
        media_type="application/json",
        schema_variants=(SchemaInfo(name=STAGE_B_PROJECTION_SCHEMA_NAME, version="1.0"),),
        payload_schema_version_by_manifest=(((STAGE_B_PROJECTION_SCHEMA_NAME, "1.0"), "1.0"),),
    )
    return validate_owned_core_model_json_artifact(
        StageBProjection, store, ref, expected_owner=owner
    ).value


def bind_candidate_model_inputs(
    candidate: PolicyCandidateSchema, state_inputs: Mapping[str, ArtifactRef]
) -> list[InputRef]:
    """Resolve ModelSpec's known ID-only artifact references from selected state inputs.

    This is a narrow producer companion, not complete candidate reference closure.
    It never selects a default view or treats these inputs as authority. The caller
    must supply actual owner-admitted state inputs and Core must still enforce access.
    Every populated source ModelSpec, including fallback variants, is reconciled.
    """
    bindings: list[InputRef] = []
    models = [("primary", candidate.trinity_bundle)]
    models.extend(
        (f"fallback_{i}", item.trinity_bundle) for i, item in enumerate(candidate.fallback_variants)
    )
    for label, bundle in models:
        model = bundle.model_spec
        refs = [
            ("problem_frame", bundle.policy_spec.problem_frame_ref),
            ("data_snapshot", model.data_snapshot_ref),
            ("registry", model.registry_bundle_ref),
            ("calibration", model.calibration_ref),
            ("network_graph", model.agent_config.network_graph_ref),
        ]
        refs.extend(
            (f"time_series_{i}", param.time_series_ref)
            for i, param in enumerate(model.environment_config.params)
        )
        for role, artifact_id in refs:
            if artifact_id is None:
                continue
            matching = [
                ArtifactRef.model_validate(ref.model_dump(mode="json"))
                for ref in state_inputs.values()
                if str(ref.artifact_id) == artifact_id
            ]
            selected = {ref.manifest_profile_sha256 for ref in matching}
            if len(selected) != 1 or None in selected:
                raise StageBProjectionRefusalError("stage_b_candidate_model_input_unresolved")
            identities = {
                (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)
                for ref in matching
            }
            if len(identities) != 1:
                raise StageBProjectionRefusalError("stage_b_candidate_model_input_ambiguous")
            bindings.append(input_ref_from_artifact_ref(matching[0], role=f"model_{label}_{role}"))
    for index, assumption in enumerate(candidate.evidence_assumptions):
        if assumption.source_ref is not None:
            ref = _source_ref(assumption.source_ref)
            if ref is None:
                raise StageBProjectionRefusalError("stage_b_assumption_ref_invalid")
            bindings.append(input_ref_from_artifact_ref(ref, role=f"evidence_assumption_{index}"))
    # Foundry's selected execution basis resolves these canonical source roles.
    # They select the same already-reconciled occurrences as the model roles;
    # neither edge by itself admits the source contents.
    world_roles = {
        "model_primary_data_snapshot": "world_model_data_snapshot",
        "model_primary_registry": "world_model_registry",
    }
    bindings.extend(
        edge.model_copy(update={"role": world_roles[edge.role]})
        for edge in tuple(bindings)
        if edge.role in world_roles
    )
    return bindings


def persist_stage_b_candidate(
    store: ArtifactStore, candidate: PolicyCandidateSchema, state_inputs: Mapping[str, ArtifactRef]
) -> ArtifactRef:
    """Use the existing candidate producer with selected ModelSpec lineage edges."""
    from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema

    return persist_policy_candidate_schema(
        store,
        candidate,
        inputs=bind_candidate_model_inputs(candidate, state_inputs),
        return_selected_profile=True,
    )
