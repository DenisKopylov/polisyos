"""Project one resolved Search interval onto the funnel's candidate report."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.scientist.methods.search.uncertainty import (
    SearchAssessedTargetRelation,
    SearchUncertaintyCurrentRead,
)


class SourceOwnedInterval(BaseModel):
    """Candidate interval from the exact selected method and physical input."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    schema_version: Literal["1.0"] = "1.0"
    origin: Literal["source_owned_interval"] = "source_owned_interval"
    verification: Literal["recomputed"] = "recomputed"
    authority_status: Literal["candidate"] = "candidate"
    as_of_status: Literal["pinned_task_epoch"] = "pinned_task_epoch"
    projection_ref: ArtifactRef
    task_epoch_ref: ArtifactRef
    observation_ref: ArtifactRef
    method_input_ref: ArtifactRef
    inference_basis_ref: ArtifactRef
    unit_scope_ref: ArtifactRef
    method_fqn: str
    method_abi_digest: str
    inference_profile_id: str
    interval_semantics: Literal["native_mean_confidence_interval"]
    point: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = Field(gt=0.0, lt=1.0)
    computed_at: AwareDatetime
    target_relation: SearchAssessedTargetRelation
    limitations: tuple[str, ...]


def project_source_owned_interval(
    current_read: SearchUncertaintyCurrentRead | None,
    *,
    subject_ref: ArtifactRef | None,
    task_binding_ref: ArtifactRef | None,
    ticket_generation: int | None,
) -> SourceOwnedInterval | None:
    """Report the exact admitted interval after the Search owner replays its sources.

    Args:
        current_read: The fresh owner snapshot for this funnel ticket.
        subject_ref: The selected policy candidate.
        task_binding_ref: The original profiled task binding of the funnel ticket.
        ticket_generation: The generation held by the funnel ticket.

    Returns:
        The bounded candidate interval, if this ticket resolves to one.
    """
    if (
        current_read is None
        or current_read.status != "available_as_of_task_epoch"
        or current_read.ticket_generation != ticket_generation
        or task_binding_ref is None
        or subject_ref is None
    ):
        return None

    admission = current_read.task_admission
    admission_ref = current_read.task_admission_ref
    resolved = current_read.resolved_projection
    if (
        resolved is None
        or admission is None
        or admission_ref is None
        or admission.status != "unassessed"
        or admission.basis_ref is None
    ):
        return None
    # Publishing the assessment retires the dispatch binding into the
    # selected projection's history. Its exact profile still binds this fit.
    binding_key = artifact_ref_identity_key(task_binding_ref)
    if not any(
        artifact_ref_identity_key(ref) == binding_key
        for ref in resolved.projection.historical_binding_refs
    ):
        return None
    basis_key = artifact_ref_identity_key(admission.basis_ref)
    obligations = [
        item
        for item in resolved.current_obligations
        if artifact_ref_identity_key(item.basis_ref) == basis_key
    ]
    if len(obligations) != 1 or obligations[0].selection.status != "assessed":
        return None
    selected = obligations[0]
    basis = selected.basis
    if artifact_ref_identity_key(basis.subject_ref) != artifact_ref_identity_key(
        subject_ref
    ) or artifact_ref_identity_key(
        selected.predecessor.observation.task_admission_ref
    ) != artifact_ref_identity_key(admission_ref):
        return None

    successor = selected.successors[0]
    observation = successor.observation
    relation = observation.target_relation
    if (
        observation.outcome_kind != "interval_estimate"
        or artifact_ref_identity_key(observation.search_uncertainty_task_binding_ref) != binding_key
        or observation.inference_basis_ref is None
        or observation.interval_semantics is None
        or observation.lower_bound is None
        or observation.upper_bound is None
        or observation.confidence_level is None
        or observation.unit_binding_status != "bound"
        or observation.unit_scope_ref is None
        or relation.scope_disposition != "satisfied"
        or relation.profile_status != "qualified"
        or relation.computed_guarantee != "backend_conditional_interval"
    ):
        return None
    # The owner already replays the exact method, source, units and completed
    # attempt. The report retains its bounded scope and limitations verbatim.
    return SourceOwnedInterval(
        projection_ref=resolved.projection_ref,
        task_epoch_ref=admission.task_epoch_ref,
        observation_ref=successor.observation_ref,
        method_input_ref=basis.selected_method_input_ref,
        inference_basis_ref=observation.inference_basis_ref,
        unit_scope_ref=observation.unit_scope_ref,
        method_fqn=observation.producer_method_fqn,
        method_abi_digest=observation.producer_method_abi_digest,
        inference_profile_id=observation.inference_profile_id,
        interval_semantics=observation.interval_semantics,
        point=observation.theta,
        lower_bound=observation.lower_bound,
        upper_bound=observation.upper_bound,
        confidence_level=observation.confidence_level,
        computed_at=observation.computed_at,
        target_relation=relation,
        limitations=observation.limitations,
    )
