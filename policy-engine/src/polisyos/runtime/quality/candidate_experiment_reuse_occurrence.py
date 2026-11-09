"""Persist one candidate-only same-source reuse action occurrence.

The receipt binds the already selected request and its durable phase, Control
payload, and PA2 decision references. It records no source-currentness, effect,
acquisition, budget, numerical-work, or publication conclusion. A route-history
consumer must independently replay the live owners before using it.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.core.artifacts import (
    ArtifactManifest,
    ArtifactRef,
    CanonInfo,
    InputRef,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    artifact_ref_for_manifest,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality.agent_action_authority import (
    AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
    AGENT_ACTION_DECISION_ARTIFACT_KIND,
)
from polisyos.runtime.quality.candidate_experiment_reuse import (
    CandidateExperimentReuseActionSelection,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts import CoreJSONArtifactStore


CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND: Final = (
    "runtime_quality.candidate_experiment_reuse_occurrence"
)
CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_WIRE_VERSION: Final = "CandidateExperimentReuseOccurrence@1.0"
CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_NAME: Final = (
    "polisyos.runtime.quality.CandidateExperimentReuseOccurrence"
)
CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_VERSION: Final = "1.0"
CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER: Final = (
    "polisyos.runtime.quality.candidate_experiment_reuse_occurrence"
)
CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER_VERSION: Final = "1.0"

# Wire evolution is explicit. A new wire version must receive an intentional
# manifest-schema mapping rather than silently inheriting the current profile.
OCCURRENCE_WIRE_TO_MANIFEST_SCHEMA: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_WIRE_VERSION: (
            CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_NAME,
            CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_VERSION,
        ),
    }
)

_PHASE_KIND: Final = "runtime_quality.acquisition_candidate_experiment_phase_receipt"
_PHASE_SCHEMA_NAME: Final = "polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt"
_CONTROL_PAYLOAD_KIND: Final = "runtime.control_job_payload.acquisition"
_CONTROL_PAYLOAD_SCHEMA_NAME: Final = "polisyos.runtime.ControlJobPayload"
_PA2_SCHEMA_NAME: Final = "polisyos.runtime.AgentActionAuthorityDecision"
_MEDIA_TYPE: Final = "application/json"
_CANON_SPEC: Final = CanonSpec()

# These are the direct manifest owners for one occurrence. The four policy
# scope inputs are included because the typed policy pins select those exact
# views too; no identity is inferred from a content hash alone.
_SELECTION_REFS: Final[tuple[tuple[str, str], ...]] = (
    ("predecessor_terminal", "predecessor_terminal_ref"),
    ("predecessor_action", "predecessor_action_ref"),
    ("predecessor_source", "source_ref"),
    ("predecessor_n5_input", "n5_input_ref"),
    ("predecessor_n5_execution", "n5_execution_ref"),
    ("predecessor_n5_result", "n5_result_ref"),
    ("reuse_policy", "policy_ref"),
)
_POLICY_SCOPE_REFS: Final[tuple[tuple[str, str], ...]] = (
    ("compiled_source", "compiled_ref"),
    ("planner_report", "planner_report_ref"),
    ("compiler_report", "compiler_report_ref"),
    ("configured_candidate_port_source", "configured_port_source_ref"),
)


class CandidateExperimentReuseOccurrence(BaseModel):
    """Durable, candidate-only record of one selected reuse action occurrence.

    This records durable bindings only. It is not a worker receipt, acquisition
    attempt, proof of physical work, permission, or a current authority grant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ARTIFACT_KIND: ClassVar[str] = CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = _MEDIA_TYPE
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_NAME
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_VERSION

    schema_version: Literal[CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_WIRE_VERSION] = (
        CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_WIRE_VERSION
    )
    purpose: Literal["durable_candidate_action_occurrence"] = "durable_candidate_action_occurrence"
    selection: CandidateExperimentReuseActionSelection
    executing_phase_ref: ArtifactRef
    control_payload_ref: ArtifactRef
    pa2_decision_ref: ArtifactRef
    source_currentness: Literal["source_currentness_not_established"] = (
        "source_currentness_not_established"
    )
    observed_data_authority: Literal[False] = False
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _require_selected_owner_profiles(self) -> CandidateExperimentReuseOccurrence:
        for name, ref, kind in (
            ("executing_phase_ref", self.executing_phase_ref, _PHASE_KIND),
            ("control_payload_ref", self.control_payload_ref, _CONTROL_PAYLOAD_KIND),
            ("pa2_decision_ref", self.pa2_decision_ref, AGENT_ACTION_DECISION_ARTIFACT_KIND),
        ):
            _require_selected_ref(ref, kind=kind, field=name)
        for field, kind in (
            ("predecessor_terminal_ref", "runtime_quality.acquisition_route_loop_receipt"),
            ("predecessor_action_ref", "runtime_quality.acquisition_candidate_action_receipt"),
            ("source_ref", "runtime.quality.candidate_acquisition_source"),
            ("n5_input_ref", "runtime.quality.candidate_simulation_n5_input"),
            ("n5_execution_ref", "runtime.quality.candidate_simulation_execution"),
            ("n5_result_ref", "polisyos.runtime.joint_simulation_result"),
            ("policy_ref", "runtime_quality.candidate_unpriced_acquisition_policy"),
        ):
            _require_selected_ref(getattr(self.selection, field), kind=kind, field=field)
        return self


def _require_selected_ref(ref: object, *, kind: str, field: str) -> ArtifactRef:
    """Require one exact, selected Core ref without accepting model-copy drift."""
    if (
        type(ref) is not ArtifactRef
        or set(type(ref).model_fields) != set(ArtifactRef.model_fields)
        or set(vars(ref)) != set(ArtifactRef.model_fields)
        or ref.__pydantic_extra__
        or ref.kind != kind
        or ref.media_type != _MEDIA_TYPE
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_experiment_reuse_occurrence_selected_ref_invalid:" + field)
    try:
        return ArtifactRef.model_validate(vars(ref))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "candidate_experiment_reuse_occurrence_selected_ref_invalid:" + field
        ) from exc


def _typed_selection(value: object) -> CandidateExperimentReuseActionSelection:
    if type(value) is not CandidateExperimentReuseActionSelection:
        raise TypeError("candidate_experiment_reuse_occurrence_selection_untyped")
    try:
        payload = value.model_dump(mode="python")
        return CandidateExperimentReuseActionSelection.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reuse_occurrence_selection_invalid") from exc


def _occurrence_input_refs(
    occurrence: CandidateExperimentReuseOccurrence,
) -> tuple[InputRef, ...]:
    """Return exact role-qualified Core inputs for the full typed selection."""
    refs: list[InputRef] = [
        input_ref_from_artifact_ref(
            occurrence.executing_phase_ref, role="selected_executing_phase"
        ),
        input_ref_from_artifact_ref(occurrence.control_payload_ref, role="control_job_payload"),
        input_ref_from_artifact_ref(occurrence.pa2_decision_ref, role="pa2_decision"),
    ]
    for role, field in _SELECTION_REFS:
        refs.append(input_ref_from_artifact_ref(getattr(occurrence.selection, field), role=role))
    scope = occurrence.selection.policy_scope
    for role, field in _POLICY_SCOPE_REFS:
        refs.append(input_ref_from_artifact_ref(getattr(scope, field), role=role))
    return tuple(refs)


def _selected_manifest(
    artifact_store: CoreJSONArtifactStore,
    ref: ArtifactRef,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    error_prefix: str,
) -> ArtifactManifest:
    """Reconcile one exact selected manifest profile and schema."""
    ref = _require_selected_ref(ref, kind=kind, field=error_prefix)
    try:
        manifest = artifact_store.get_manifest(ref)
        selected = artifact_ref_for_manifest(manifest)
        verification = artifact_store.verify(ref)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(error_prefix + "_selected_manifest_unavailable") from exc
    schema = manifest.artifact_schema
    if (
        artifact_ref_identity_key(selected) != artifact_ref_identity_key(ref)
        or manifest.kind != kind
        or manifest.media_type != _MEDIA_TYPE
        or schema is None
        or schema.name != schema_name
        or schema.version != schema_version
        or not verification.ok
    ):
        raise ValueError(error_prefix + "_selected_manifest_mismatch")
    return manifest


def _require_expected_schema(occurrence: CandidateExperimentReuseOccurrence) -> SchemaInfo:
    schema = OCCURRENCE_WIRE_TO_MANIFEST_SCHEMA.get(occurrence.schema_version)
    if schema is None:
        raise ValueError("candidate_experiment_reuse_occurrence_wire_version_unsupported")
    return SchemaInfo(name=schema[0], version=schema[1])


def _verify_selected_context(
    *,
    artifact_store: CoreJSONArtifactStore,
    occurrence: CandidateExperimentReuseOccurrence,
) -> None:
    """Verify the phase selection and typed auxiliary CAS views, not authority."""
    _selected_manifest(
        artifact_store,
        occurrence.executing_phase_ref,
        kind=_PHASE_KIND,
        schema_name=_PHASE_SCHEMA_NAME,
        schema_version="1.0",
        error_prefix="candidate_experiment_reuse_occurrence_phase",
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        parse_acquisition_route_phase_receipt,
    )

    try:
        phase = parse_acquisition_route_phase_receipt(
            load_core_json_artifact(artifact_store, occurrence.executing_phase_ref)
        )
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reuse_occurrence_phase_invalid") from exc
    selection = occurrence.selection
    if (
        type(phase) is not AcquisitionCandidateExperimentPhaseReceipt
        or phase.receipt_phase != "executing"
        or phase.coarse_phase != "executing"
        or phase.recovery_state != "none"
        or (phase.tenant_id, phase.cell_id, phase.run_id, phase.source_job_id)
        != (selection.tenant_id, selection.cell_id, selection.run_id, selection.source_job_id)
        or phase.job_id != selection.action_job_id
        or phase.route_id != selection.route_id
        or phase.action_generation != selection.action_generation
        or phase.source_payload_ref != selection.source_payload_ref
        or phase.request_content_hash != selection.request_content_hash
        or phase.policy_scope != selection.policy_scope
        or artifact_ref_identity_key(phase.policy_ref)
        != artifact_ref_identity_key(selection.policy_ref)
        or artifact_ref_identity_key(phase.authority_decision_ref)
        != artifact_ref_identity_key(occurrence.pa2_decision_ref)
    ):
        raise ValueError("candidate_experiment_reuse_occurrence_phase_selection_mismatch")
    _selected_manifest(
        artifact_store,
        occurrence.control_payload_ref,
        kind=_CONTROL_PAYLOAD_KIND,
        schema_name=_CONTROL_PAYLOAD_SCHEMA_NAME,
        schema_version="1.0",
        error_prefix="candidate_experiment_reuse_occurrence_control_payload",
    )
    _selected_manifest(
        artifact_store,
        occurrence.pa2_decision_ref,
        kind=AGENT_ACTION_DECISION_ARTIFACT_KIND,
        schema_name=_PA2_SCHEMA_NAME,
        schema_version=AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        error_prefix="candidate_experiment_reuse_occurrence_pa2_decision",
    )


def persist_candidate_experiment_reuse_occurrence(
    artifact_store: CoreJSONArtifactStore,
    *,
    selection: CandidateExperimentReuseActionSelection,
    executing_phase_ref: ArtifactRef,
    control_payload_ref: ArtifactRef,
    pa2_decision_ref: ArtifactRef,
) -> ArtifactRef:
    """Persist and selected-profile read back one durable candidate occurrence.

    The caller owns the live Control lease, exact job payload, signed PA2
    verification, and current owner checks. This function only binds their
    selected references to the typed reuse selection and executing phase.
    """
    typed_selection = _typed_selection(selection)
    occurrence = CandidateExperimentReuseOccurrence(
        selection=typed_selection,
        executing_phase_ref=executing_phase_ref,
        control_payload_ref=control_payload_ref,
        pa2_decision_ref=pa2_decision_ref,
    )
    schema = _require_expected_schema(occurrence)
    _verify_selected_context(artifact_store=artifact_store, occurrence=occurrence)
    ref = artifact_store.put_json(
        occurrence.model_dump(mode="json"),
        PutOptions(
            kind=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND,
            media_type=_MEDIA_TYPE,
            schema=schema,
            producer=ProducerInfo(
                component=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER,
                version=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER_VERSION,
            ),
            canon=CanonInfo.from_spec(_CANON_SPEC),
            inputs=list(_occurrence_input_refs(occurrence)),
        ),
        canon_spec=_CANON_SPEC,
        return_selected_profile=True,
    )
    if ref.manifest_profile_sha256 is None:
        raise ValueError("candidate_experiment_reuse_occurrence_writer_profile_missing")
    read_candidate_experiment_reuse_occurrence(
        artifact_store,
        occurrence_ref=ref,
        expected_selection=typed_selection,
        expected_executing_phase_ref=executing_phase_ref,
        expected_control_payload_ref=control_payload_ref,
        expected_pa2_decision_ref=pa2_decision_ref,
    )
    return ref


def read_candidate_experiment_reuse_occurrence(
    artifact_store: CoreJSONArtifactStore,
    *,
    occurrence_ref: ArtifactRef,
    expected_selection: CandidateExperimentReuseActionSelection,
    expected_executing_phase_ref: ArtifactRef | None = None,
    expected_control_payload_ref: ArtifactRef | None = None,
    expected_pa2_decision_ref: ArtifactRef | None = None,
) -> CandidateExperimentReuseOccurrence:
    """Reopen one exact occurrence and reconcile its selected roles and pins.

    This historical reader does not revalidate a live PA2 grant, current
    comparator result, current lease, terminal state, or source eligibility.
    """
    selection = _typed_selection(expected_selection)
    occurrence_ref = _require_selected_ref(
        occurrence_ref,
        kind=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND,
        field="occurrence_ref",
    )
    try:
        manifest = artifact_store.get_manifest(occurrence_ref)
        selected = artifact_ref_for_manifest(manifest)
        verification = artifact_store.verify(occurrence_ref)
        payload = load_core_json_artifact(artifact_store, occurrence_ref)
        occurrence = CandidateExperimentReuseOccurrence.model_validate(payload)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reuse_occurrence_selected_read_failed") from exc
    schema = _require_expected_schema(occurrence)
    producer = manifest.producer
    if (
        artifact_ref_identity_key(selected) != artifact_ref_identity_key(occurrence_ref)
        or manifest.kind != CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND
        or manifest.media_type != _MEDIA_TYPE
        or manifest.artifact_schema != schema
        or producer is None
        or producer.component != CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER
        or producer.version != CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER_VERSION
        or not verification.ok
    ):
        raise ValueError("candidate_experiment_reuse_occurrence_manifest_mismatch")
    expected_inputs = _occurrence_input_refs(occurrence)
    if tuple(manifest.inputs) != expected_inputs:
        raise ValueError("candidate_experiment_reuse_occurrence_manifest_closure_mismatch")
    if occurrence.selection != selection:
        raise ValueError("candidate_experiment_reuse_occurrence_selection_mismatch")
    for field, expected in (
        ("executing_phase_ref", expected_executing_phase_ref),
        ("control_payload_ref", expected_control_payload_ref),
        ("pa2_decision_ref", expected_pa2_decision_ref),
    ):
        if expected is not None:
            _require_selected_ref(expected, kind=getattr(occurrence, field).kind, field=field)
            if artifact_ref_identity_key(getattr(occurrence, field)) != artifact_ref_identity_key(
                expected
            ):
                raise ValueError("candidate_experiment_reuse_occurrence_" + field + "_mismatch")
    _verify_selected_context(artifact_store=artifact_store, occurrence=occurrence)
    return occurrence
