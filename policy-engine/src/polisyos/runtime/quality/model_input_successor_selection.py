"""Persist the exact activated input and action selected for candidate N5."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import FoundryInputBindingsRef

if TYPE_CHECKING:
    from polisyos.core.artifacts import (
        CoreJSONArtifactProfileReader,
        CoreJSONArtifactStore,
        InputRef,
    )


MODEL_INPUT_SUCCESSOR_SELECTION_KIND = "runtime.quality.model_input_successor_selection"
MODEL_INPUT_USE_ACTION_PHASE_KIND = "runtime.quality.model_input_use_action_phase"
_SCHEMA_NAME = "polisyos.runtime.ModelInputSuccessorSelection"
_PHASE_SCHEMA_NAME = "polisyos.runtime.ModelInputUseActionPhase"
_HASH = r"^sha256:[0-9a-f]{64}$"


class ModelInputUseActionPhase(BaseModel):
    """Stable owner phase for one exact action payload and protected decision."""

    ARTIFACT_KIND: ClassVar[str] = MODEL_INPUT_USE_ACTION_PHASE_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = _PHASE_SCHEMA_NAME
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.runtime.ModelInputUseActionPhase@1.0"
    }

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.ModelInputUseActionPhase@1.0"] = (
        "polisyos.runtime.ModelInputUseActionPhase@1.0"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    action_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_HASH)
    action_payload_ref: ArtifactRef
    authority_decision_ref: ArtifactRef

    @model_validator(mode="after")
    def _selected_inputs(self) -> ModelInputUseActionPhase:
        if self.action_job_id == self.source_job_id or any(
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in (
                (self.action_payload_ref, "runtime.control_job_payload.acquisition"),
                (
                    self.authority_decision_ref,
                    "runtime_quality.agent_action_authority_decision",
                ),
            )
        ):
            raise ValueError("model_input_use_phase_selected_inputs_invalid")
        return self

    def lineage(self) -> list[InputRef]:
        """Return the exact role-qualified inputs used to issue the phase."""
        return [
            input_ref_from_artifact_ref(self.action_payload_ref, role="protected_action_job"),
            input_ref_from_artifact_ref(
                self.authority_decision_ref, role="protected_action_decision"
            ),
        ]


def persist_model_input_use_action_phase(
    store: CoreJSONArtifactStore, phase: ModelInputUseActionPhase
) -> ArtifactRef:
    """Persist the stable phase and check its exact profile and lineage."""
    phase = ModelInputUseActionPhase.model_validate(phase.model_dump(mode="python"))
    ref = store.put_json(
        phase,
        PutOptions(
            kind=phase.ARTIFACT_KIND,
            media_type=phase.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=phase.ARTIFACT_SCHEMA_NAME, version=phase.ARTIFACT_SCHEMA_VERSION
            ),
            producer=ProducerInfo(component=__name__, version="1.0"),
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=phase.tenant_id, cell_id=phase.cell_id
            ),
            inputs=phase.lineage(),
        ),
        return_selected_profile=True,
    )
    if read_model_input_use_action_phase(store, ref) != phase:
        raise ValueError("model_input_use_phase_readback_mismatch")
    return ref


def read_model_input_use_action_phase(
    store: CoreJSONArtifactProfileReader, ref: ArtifactRef
) -> ModelInputUseActionPhase:
    """Check one independently selected phase without granting authority."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("model_input_use_phase_profile_required")
    phase = validate_core_model_json_artifact(ModelInputUseActionPhase, store, ref)
    manifest = store.get_manifest(ref)
    if (
        manifest.inputs != phase.lineage()
        or manifest.tenant_context
        != ArtifactTenantContextInfo(tenant_id=phase.tenant_id, cell_id=phase.cell_id)
        or manifest.producer != ProducerInfo(component=__name__, version="1.0")
    ):
        raise ValueError("model_input_use_phase_lineage_mismatch")
    return phase


class ModelInputSuccessorSelection(BaseModel):
    """Input selection from the protected action before any numerical result exists."""

    ARTIFACT_KIND: ClassVar[str] = MODEL_INPUT_SUCCESSOR_SELECTION_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = _SCHEMA_NAME
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = "1.0"
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        "1.0": "polisyos.runtime.ModelInputSuccessorSelection@1.0"
    }

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.ModelInputSuccessorSelection@1.0"] = (
        "polisyos.runtime.ModelInputSuccessorSelection@1.0"
    )
    authority_purpose: Literal["candidate_simulation_input_only"] = (
        "candidate_simulation_input_only"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    compiled_ref: ArtifactRef
    blocked_execution_ref: ArtifactRef
    routing_report_ref: ArtifactRef
    activation_receipt_ref: ArtifactRef
    observation_id: str = Field(min_length=1)
    observation_content_sha256: str = Field(pattern=_HASH)
    route_id: str = Field(pattern=_HASH)
    action_job_id: str = Field(min_length=1)
    action_worker_id: str = Field(min_length=1)
    action_attempt: int = Field(ge=1, strict=True)
    action_phase_ref: ArtifactRef
    authority_decision_ref: ArtifactRef
    reentry_budget_window_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    reentry_budget_window_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_foundry_input_bindings_ref: FoundryInputBindingsRef

    @model_validator(mode="after")
    def _selected_inputs(self) -> ModelInputSuccessorSelection:
        expected = (
            (self.compiled_ref, "runtime.compiled_recursive_generation_cycle", "application/json"),
            (
                self.blocked_execution_ref,
                "runtime.quality.generic_cycle_simulation_n5_execution",
                "application/json",
            ),
            (
                self.routing_report_ref,
                "runtime.quality.model_input_routing_report",
                "application/json",
            ),
            (
                self.activation_receipt_ref,
                "epoch.activated_overlay_admission_receipt",
                "application/vnd.polisyos.epoch+json",
            ),
            (self.action_phase_ref, MODEL_INPUT_USE_ACTION_PHASE_KIND, "application/json"),
            (
                self.authority_decision_ref,
                "runtime_quality.agent_action_authority_decision",
                "application/json",
            ),
            (
                self.semantic_foundry_input_bindings_ref,
                "foundry.input_bindings",
                "application/json",
            ),
        )
        if self.action_job_id == self.source_job_id or any(
            ref.kind != kind or ref.media_type != media_type or ref.manifest_profile_sha256 is None
            for ref, kind, media_type in expected
        ):
            raise ValueError("model_input_successor_selected_inputs_invalid")
        return self


def _inputs(record: ModelInputSuccessorSelection) -> list[InputRef]:
    return [
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("completed_compiled_run", record.compiled_ref),
            ("blocked_generic_n5_execution", record.blocked_execution_ref),
            ("model_input_routing_report", record.routing_report_ref),
            ("activated_catalog_observation", record.activation_receipt_ref),
            ("protected_action_phase", record.action_phase_ref),
            ("protected_action_decision", record.authority_decision_ref),
            ("semantic_foundry_input_bindings", record.semantic_foundry_input_bindings_ref),
        )
    ]


def persist_model_input_successor_selection(
    store: CoreJSONArtifactStore, record: ModelInputSuccessorSelection
) -> ArtifactRef:
    """Persist one input chosen by the protected action owner and check readback."""
    record = ModelInputSuccessorSelection.model_validate(record.model_dump(mode="python"))
    ref = store.put_json(
        record,
        PutOptions(
            kind=record.ARTIFACT_KIND,
            media_type=record.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=record.ARTIFACT_SCHEMA_NAME, version=record.ARTIFACT_SCHEMA_VERSION
            ),
            producer=ProducerInfo(component=__name__, version="1.0"),
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=record.tenant_id, cell_id=record.cell_id
            ),
            inputs=_inputs(record),
        ),
        return_selected_profile=True,
    )
    if read_model_input_successor_selection(store, ref) != record:
        raise ValueError("model_input_successor_selection_readback_mismatch")
    return ref


def read_model_input_successor_selection(
    store: CoreJSONArtifactProfileReader, ref: ArtifactRef
) -> ModelInputSuccessorSelection:
    """Check historical selection bytes and lineage for an independently chosen ref.

    The action owner verifies authority and selects this ref. This reader
    supplies no current permission or terminal outcome.
    """
    if ref.manifest_profile_sha256 is None:
        raise ValueError("model_input_successor_selection_profile_required")
    record = validate_core_model_json_artifact(ModelInputSuccessorSelection, store, ref)
    manifest = store.get_manifest(ref)
    if (
        manifest.inputs != _inputs(record)
        or manifest.tenant_context
        != ArtifactTenantContextInfo(tenant_id=record.tenant_id, cell_id=record.cell_id)
        or manifest.producer != ProducerInfo(component=__name__, version="1.0")
    ):
        raise ValueError("model_input_successor_selection_lineage_mismatch")
    return record
