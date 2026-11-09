"""Candidate-only N7 routing for exact selected ProgramGraph input obligations.

Model-owned ports are execution requirements, not claim or facet gaps. This
module replays the selected N5 invocation, compiles its missing ports, and
discovers compatible Catalog descriptors. It also links a resolved descriptor
to independently activated Catalog evidence for candidate model-input use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    CoreJSONArtifactStore,
    InputRef,
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import ProgramGraphInputInvocation
from polisyos.data_forge.read_api.catalog import (
    AcquisitionAuthorityError,
    CanonicalAcquisitionAuthority,
    ModelInputSourceDescriptorCandidate,
    ModelInputSourceQueryEnvelope,
)
from polisyos.data_requirement import (
    DataRequirementCompiler,
    ModelInputCompilationReport,
    persist_model_input_compilation_report,
    verify_model_input_compilation_report,
)

from .model_input_requirements import (
    SelectedProgramGraphInputBasis,
    replay_selected_program_graph_input_obligations,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

    from polisyos.data_forge.read_api.catalog import CatalogAcquisitionOverlay

    from .acquisition_executor import AdmissionPassport
    from .data_state_substrate import AcquiredObservationDataSnapshotResult


MODEL_INPUT_ROUTING_REPORT_KIND = "runtime.quality.model_input_routing_report"
MODEL_INPUT_ROUTING_REPORT_SCHEMA_NAME = "polisyos.runtime.quality.ModelInputRoutingReport"
MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION = "1.0"
MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2 = "2.0"
_MODEL_INPUT_ROUTING_PROHIBITED_USES = (
    "measurement_admission",
    "fetch_permission",
    "claim_evidence",
    "source_currentness",
    "publication",
)
_MODEL_INPUT_SOURCE_REFUSAL_DISPOSITIONS: dict[str, Literal["absent", "ambiguous", "conflict"]] = {
    "model_input_source_descriptor_unresolved": "absent",
    "model_input_source_descriptor_ambiguous": "ambiguous",
    "model_input_source_descriptor_incompatible": "conflict",
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelInputRoutingActivationError(ValueError):
    """A verified routing report cannot select the requested activation."""

    def __init__(
        self,
        reason: Literal[
            "single_obligation_required",
            "resolved_route_required",
            "activated_source_mismatch",
            "live_authority_drift",
        ],
    ) -> None:
        self.reason = reason
        worker_reason = "activated_source_mismatch" if reason == "live_authority_drift" else reason
        super().__init__(f"model_input_routing_{worker_reason}")


class ModelInputPortRoute(_StrictModel):
    """Candidate source-discovery result for one compiled executable port."""

    requirement_id: str = Field(min_length=1)
    obligation_ref: ArtifactRef
    port_id: str = Field(min_length=1)
    disposition: Literal["resolved", "absent", "ambiguous", "conflict"]
    source_descriptor: ModelInputSourceDescriptorCandidate | None = None
    query_envelope: ModelInputSourceQueryEnvelope | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    reason_code: str | None = None
    voi_status: Literal["unknown"] = "unknown"
    fetch_status: Literal["not_attempted"] = "not_attempted"
    catalog_search_completeness: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )
    may_not_use_for: tuple[
        Literal[
            "measurement_admission",
            "fetch_permission",
            "claim_evidence",
            "source_currentness",
            "publication",
        ],
        ...,
    ] = _MODEL_INPUT_ROUTING_PROHIBITED_USES

    @model_validator(mode="after")
    def _disposition_matches_result(self) -> Self:
        if self.obligation_ref.manifest_profile_sha256 is None:
            raise ValueError("model_input_routing_obligation_ref_unselected")
        if (
            self.query_envelope is not None
            and self.query_envelope.model_input_port_id != self.port_id
        ):
            raise ValueError("model_input_routing_query_envelope_port_mismatch")
        if self.disposition == "resolved":
            if self.source_descriptor is None or self.reason_code is not None:
                raise ValueError("model_input_routing_resolved_result_invalid")
            if self.source_descriptor.model_input_port_id != self.port_id:
                raise ValueError("model_input_routing_descriptor_port_mismatch")
        else:
            expected_reason = next(
                (
                    code
                    for code, disposition in _MODEL_INPUT_SOURCE_REFUSAL_DISPOSITIONS.items()
                    if disposition == self.disposition
                ),
                None,
            )
            if (
                self.source_descriptor is not None
                or self.reason_code != expected_reason
                or expected_reason is None
            ):
                raise ValueError("model_input_routing_refusal_result_invalid")
        if self.may_not_use_for != _MODEL_INPUT_ROUTING_PROHIBITED_USES:
            raise ValueError("model_input_routing_authority_boundary_invalid")
        return self


class ModelInputRoutingReport(_StrictModel):
    """Replay-bound candidate-only routes for one selected ProgramGraph N5."""

    ARTIFACT_KIND: ClassVar[str] = MODEL_INPUT_ROUTING_REPORT_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = MODEL_INPUT_ROUTING_REPORT_SCHEMA_NAME
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = (
        MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION,
        MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2,
    )

    schema_version: Literal["1.0", "2.0"] = "1.0"
    authority_purpose: Literal["candidate_acquisition_routing_only"] = (
        "candidate_acquisition_routing_only"
    )
    selected_invocation: ProgramGraphInputInvocation
    obligation_set_ref: ArtifactRef
    compilation_report_ref: ArtifactRef
    routes: tuple[ModelInputPortRoute, ...] = Field(min_length=1)
    status: Literal["candidate_descriptors_resolved", "candidate_descriptors_limited"]
    voi_status: Literal["unknown"] = "unknown"
    fetch_status: Literal["not_attempted"] = "not_attempted"
    may_not_use_for: tuple[
        Literal[
            "measurement_admission",
            "fetch_permission",
            "claim_evidence",
            "source_currentness",
            "publication",
        ],
        ...,
    ] = _MODEL_INPUT_ROUTING_PROHIBITED_USES

    @model_validator(mode="after")
    def _route_denominator_and_status(self) -> Self:
        if (
            self.obligation_set_ref.kind != "runtime.quality.model_input_obligation_set"
            or self.obligation_set_ref.media_type != "application/json"
            or self.obligation_set_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_routing_obligation_set_ref_invalid")
        if (
            self.compilation_report_ref.kind != ModelInputCompilationReport.ARTIFACT_KIND
            or self.compilation_report_ref.media_type != "application/json"
            or self.compilation_report_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_routing_compilation_report_ref_invalid")
        ports = tuple(route.port_id for route in self.routes)
        obligations = tuple(
            artifact_ref_identity_key(route.obligation_ref) for route in self.routes
        )
        if len(set(ports)) != len(ports) or len(set(obligations)) != len(obligations):
            raise ValueError("model_input_routing_route_duplicate")
        expected_status = (
            "candidate_descriptors_resolved"
            if all(route.disposition == "resolved" for route in self.routes)
            else "candidate_descriptors_limited"
        )
        if self.status != expected_status:
            raise ValueError("model_input_routing_status_mismatch")
        if self.may_not_use_for != _MODEL_INPUT_ROUTING_PROHIBITED_USES:
            raise ValueError("model_input_routing_authority_boundary_invalid")
        for route in self.routes:
            descriptor = route.source_descriptor
            if descriptor is not None and artifact_ref_identity_key(
                descriptor.model_input_interface_ref
            ) != artifact_ref_identity_key(self.selected_invocation.interface_ref):
                raise ValueError("model_input_routing_descriptor_interface_mismatch")
            if self.schema_version == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION:
                if route.query_envelope is not None or (
                    descriptor is not None and descriptor.query_envelope is not None
                ):
                    raise ValueError("model_input_routing_v1_query_envelope_forbidden")
                continue

            envelope = route.query_envelope
            if envelope is None:
                raise ValueError("model_input_routing_v2_query_envelope_required")
            if artifact_ref_identity_key(
                envelope.model_input_interface_ref
            ) != artifact_ref_identity_key(self.selected_invocation.interface_ref):
                raise ValueError("model_input_routing_query_envelope_interface_mismatch")
            if envelope.model_input_port_id != route.port_id:
                raise ValueError("model_input_routing_query_envelope_port_mismatch")
            compatible_entry_ids = tuple(
                row.entry_id for row in envelope.rows if row.disposition == "compatible"
            )
            if route.disposition == "resolved":
                if (
                    descriptor is None
                    or descriptor.query_envelope is not None
                    or compatible_entry_ids != (descriptor.authority_entry_id,)
                    or envelope.model_semantic_definition_ref
                    != descriptor.model_semantic_definition_ref
                    or envelope.model_representation_ref != descriptor.model_representation_ref
                    or envelope.binding_profile_ref != descriptor.binding_profile_ref
                ):
                    raise ValueError("model_input_routing_v2_resolved_query_invalid")
            elif route.disposition == "absent":
                if envelope.rows:
                    raise ValueError("model_input_routing_v2_absence_query_not_empty")
            elif route.disposition == "ambiguous":
                if len(compatible_entry_ids) < 2:
                    raise ValueError("model_input_routing_v2_ambiguity_query_incomplete")
            elif not envelope.rows or compatible_entry_ids:
                raise ValueError("model_input_routing_v2_conflict_query_incomplete")
        return self


@dataclass(frozen=True)
class ModelInputRoutingResult:
    """Persisted compiler and candidate-routing artifacts for a selected N5."""

    compilation_report: ModelInputCompilationReport
    compilation_report_ref: ArtifactRef
    report: ModelInputRoutingReport
    report_ref: ArtifactRef


def plan_selected_model_input_routing(
    store: CoreJSONArtifactStore,
    *,
    obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
    report_version: Literal["1.0", "2.0"] = MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION,
) -> ModelInputRoutingResult:
    """Replay, compile, and discover sources for one exact selected N5 input set.

    The caller must supply selection facts from the active N5 request and
    selected candidate. This function never derives expected selection from
    the obligation artifact itself. Only the three typed Catalog discovery
    outcomes become per-port limitations; other Catalog/store errors escape.
    """

    canonical_authority = _require_canonical_acquisition_authority(catalog_authority)
    selected_set = replay_selected_program_graph_input_obligations(
        store,
        obligation_set_ref=obligation_set_ref,
        selected_basis=selected_basis,
    )
    interface_ref = selected_set.invocation.interface_ref
    compilation_report = DataRequirementCompiler.compile_model_input_obligations(
        store,
        obligation_set_ref=obligation_set_ref,
        expected_context=selected_basis.context,
        expected_interface_ref=interface_ref,
    )
    compilation_report_ref = persist_model_input_compilation_report(store, compilation_report)
    routes = _discover_port_routes(
        store,
        compilation_report=compilation_report,
        catalog_authority=canonical_authority,
        include_query_envelope=report_version == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2,
    )
    report = _build_report(
        selected_basis=selected_basis,
        selected_invocation=selected_basis.invocation(interface_ref),
        obligation_set_ref=obligation_set_ref,
        compilation_report_ref=compilation_report_ref,
        routes=routes,
        schema_version=report_version,
    )
    report_ref = _persist_model_input_routing_report(store, report)
    if read_model_input_routing_report(store, report_ref) != report:
        raise ValueError("model_input_routing_report_readback_mismatch")
    return ModelInputRoutingResult(
        compilation_report=compilation_report,
        compilation_report_ref=compilation_report_ref,
        report=report,
        report_ref=report_ref,
    )


def verify_model_input_routing_report(
    store: CoreJSONArtifactStore,
    report_ref: ArtifactRef,
    *,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
) -> ModelInputRoutingReport:
    """Reopen a stored report and verify it against current Catalog routing."""

    stored_report, _current_report = _verify_model_input_routing_report_current(
        store,
        report_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=catalog_authority,
    )
    return stored_report


def _verify_model_input_routing_report_current(
    store: CoreJSONArtifactStore,
    report_ref: ArtifactRef,
    *,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
) -> tuple[ModelInputRoutingReport, ModelInputRoutingReport]:
    """Return the frozen report and its freshly rederived current counterpart."""

    canonical_authority = _require_canonical_acquisition_authority(catalog_authority)
    report = read_model_input_routing_report(store, report_ref)
    if artifact_ref_identity_key(report.obligation_set_ref) != artifact_ref_identity_key(
        expected_obligation_set_ref
    ):
        raise ValueError("model_input_routing_obligation_set_selection_mismatch")
    selected_set = replay_selected_program_graph_input_obligations(
        store,
        obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
    )
    interface_ref = selected_set.invocation.interface_ref
    compilation = verify_model_input_compilation_report(
        store,
        report.compilation_report_ref,
        expected_context=selected_basis.context,
        expected_interface_ref=interface_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
    )
    expected = _build_report(
        selected_basis=selected_basis,
        selected_invocation=selected_basis.invocation(interface_ref),
        obligation_set_ref=expected_obligation_set_ref,
        compilation_report_ref=report.compilation_report_ref,
        routes=_discover_port_routes(
            store,
            compilation_report=compilation,
            catalog_authority=canonical_authority,
            include_query_envelope=(
                report.schema_version == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2
            ),
        ),
        schema_version=report.schema_version,
    )
    if report.schema_version == MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION:
        matches_current = report == expected
    else:
        matches_current = _v2_routing_report_matches_current(report, expected)
    if not matches_current:
        raise ValueError("model_input_routing_report_selection_mismatch")
    return report, expected


def _v2_routing_report_matches_current(
    stored: ModelInputRoutingReport,
    current: ModelInputRoutingReport,
) -> bool:
    """Compare V2 query scope and descriptor facts, excluding only registry hash."""

    if (
        stored.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2
        or current.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2
        or stored.model_dump(mode="python", exclude={"routes"})
        != current.model_dump(mode="python", exclude={"routes"})
        or len(stored.routes) != len(current.routes)
    ):
        return False
    for stored_route, current_route in zip(stored.routes, current.routes, strict=True):
        if (
            stored_route.model_dump(
                mode="python",
                exclude={"source_descriptor", "query_envelope"},
            )
            != current_route.model_dump(
                mode="python",
                exclude={"source_descriptor", "query_envelope"},
            )
            or stored_route.query_envelope != current_route.query_envelope
        ):
            return False
        stored_descriptor = stored_route.source_descriptor
        current_descriptor = current_route.source_descriptor
        if (stored_descriptor is None) != (current_descriptor is None):
            return False
        if stored_descriptor is None or current_descriptor is None:
            continue
        if stored_descriptor.model_dump(
            mode="python",
            exclude={"authority_registry_content_sha256"},
        ) != current_descriptor.model_dump(
            mode="python",
            exclude={"authority_registry_content_sha256"},
        ):
            return False
    return True


def resolve_model_input_routing_activation(
    store: CoreJSONArtifactStore,
    report_ref: ArtifactRef,
    *,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
    receipt_ref: ArtifactRef,
    passport: AdmissionPassport,
) -> tuple[ModelInputRoutingReport, CanonicalAcquisitionAuthority]:
    """Revalidate the frozen activation and its current exact source selection."""
    report, current = _verify_model_input_routing_report_current(
        store,
        report_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=catalog_authority,
    )
    if len(report.routes) != 1:
        raise ModelInputRoutingActivationError("single_obligation_required")
    (route,) = report.routes
    (current_route,) = current.routes
    stored_descriptor = route.source_descriptor
    current_descriptor = current_route.source_descriptor
    if stored_descriptor is None or current_descriptor is None:
        raise ModelInputRoutingActivationError("resolved_route_required")
    if (
        stored_descriptor.authority_entry_id != passport.authority_entry_id
        or stored_descriptor.authority_registry_content_sha256
        != passport.authority_registry_content_sha256
    ):
        raise ModelInputRoutingActivationError("activated_source_mismatch")
    current_registry = current_descriptor.authority_registry_content_sha256
    if current_registry != passport.authority_registry_content_sha256:
        if (
            report.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2
            or route.query_envelope is None
        ):
            raise ModelInputRoutingActivationError("activated_source_mismatch")
        if passport.source_lane == "live_fetch":
            raise ModelInputRoutingActivationError("live_authority_drift")
        if passport.source_lane != "local_lift":
            raise ModelInputRoutingActivationError("activated_source_mismatch")
        catalog_authority = catalog_authority._for_model_input_activation(
            store,
            receipt_ref=receipt_ref,
            routing_report_ref=report_ref,
            current_registry_sha256=current_registry,
        )
    return report, catalog_authority


def materialize_routed_model_input_observation(
    store: CoreJSONArtifactStore,
    *,
    report_ref: ArtifactRef,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
    overlay: CatalogAcquisitionOverlay,
    receipt_ref: ArtifactRef,
    passport: AdmissionPassport,
    observation_id: str,
    profile_selection_ref: str,
    workspace_dir: Path,
    transaction_time: datetime,
) -> AcquiredObservationDataSnapshotResult:
    """Bind the single routed model input to an independently activated observation.

    The execution owner establishes operation authority before calling. It
    supplies the exact blocked N5 basis and selected acquisition receipt.
    Catalog independently replays the route and the active observation. The
    resulting snapshot has candidate simulation input purpose only.

    Returns:
        The candidate snapshot and exact semantic Foundry bindings.

    Raises:
        ValueError: If the route, activated source, or selected input is incompatible.
    """
    from polisyos.core.contracts import (
        SelectedVariableBindingRef,
        load_program_graph_input_interface,
    )
    from polisyos.data_forge.read_api.catalog import CatalogAcquisitionOverlay
    from polisyos.foundry.data_plane import load_input_bindings

    from .acquisition_executor import AdmissionPassport
    from .data_state_substrate import (
        AcquiredObservationSemanticInputRequest,
        ControlledAcquisitionSlotBinding,
        acquired_observation_binding_rule,
        materialize_acquired_observation_snapshot,
    )

    if type(overlay) is not CatalogAcquisitionOverlay or type(passport) is not AdmissionPassport:
        raise ValueError("model_input_routing_activation_owner_untyped")
    report, catalog_authority = resolve_model_input_routing_activation(
        store,
        report_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=catalog_authority,
        receipt_ref=receipt_ref,
        passport=passport,
    )
    (route,) = report.routes
    descriptor = route.source_descriptor
    if descriptor is None:
        raise ValueError("model_input_routing_resolved_route_required")

    invocation = report.selected_invocation
    interface = load_program_graph_input_interface(store, invocation.interface_ref)
    port = next(port for port in interface.ports if port.port_id == route.port_id)
    projection = overlay.read_activated_semantic_epoch_observations(
        receipt_ref=receipt_ref,
        artifact_store=store,
        passport=passport,
        authority=catalog_authority,
    )
    observations = tuple(
        row.observation
        for row in projection.observations
        if row.observation.observation_id == observation_id
    )
    if len(observations) != 1:
        raise ValueError("model_input_routing_activated_observation_not_selected")
    (observation,) = observations
    slot_binding = ControlledAcquisitionSlotBinding(
        profile_selection_ref=profile_selection_ref,
        canonical_variable_id=projection.variable_id,
        target_slot_id=port.slot_id,
    )
    rule = acquired_observation_binding_rule(observation=observation, slot_binding=slot_binding)
    predecessor = load_input_bindings(store, invocation.input_bindings_ref)
    return materialize_acquired_observation_snapshot(
        store,
        base_data_snapshot_ref=predecessor.data_snapshot_ref,
        overlay=overlay,
        receipt_ref=receipt_ref,
        passport=passport,
        authority=catalog_authority,
        observation_id=observation_id,
        slot_binding=slot_binding,
        workspace_dir=workspace_dir,
        transaction_time=transaction_time,
        semantic_input_request=AcquiredObservationSemanticInputRequest(
            binding_id=rule.binding_id,
            source_definition_ref=descriptor.source_semantic_definition_ref,
            source_representation_ref=descriptor.source_representation_ref,
            obligation_set_ref=SelectedVariableBindingRef.model_validate(
                report.obligation_set_ref.model_dump(mode="python")
            ),
            expected_invocation=invocation,
            model_port_id=port.port_id,
        ),
    )


def _require_canonical_acquisition_authority(
    value: object,
) -> CanonicalAcquisitionAuthority:
    """Refuse duck-typed Catalog substitutes at the candidate-routing boundary."""

    if type(value) is not CanonicalAcquisitionAuthority:
        raise TypeError("model_input_routing_catalog_authority_not_canonical")
    return value


def _persist_model_input_routing_report(
    store: CoreJSONArtifactStore,
    report: ModelInputRoutingReport,
) -> ArtifactRef:
    """Persist the exact candidate-only route and validate its selected CAS readback."""

    ref = store.put_json(
        report,
        PutOptions(
            kind=report.ARTIFACT_KIND,
            media_type=report.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=report.ARTIFACT_SCHEMA_NAME,
                version=report.schema_version,
            ),
            inputs=_model_input_routing_inputs(report),
        ),
        return_selected_profile=True,
    )
    if read_model_input_routing_report(store, ref) != report:
        raise ValueError("model_input_routing_report_readback_mismatch")
    return ref


def read_model_input_routing_report(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> ModelInputRoutingReport:
    """Read a selected routing report and reconcile its complete CAS lineage."""

    if (
        ref.kind != MODEL_INPUT_ROUTING_REPORT_KIND
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("model_input_routing_report_ref_unselected")
    report = validate_core_model_json_artifact(ModelInputRoutingReport, store, ref)
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if schema is None or schema.version != report.schema_version:
        raise ValueError("model_input_routing_report_schema_version_mismatch")
    if manifest.inputs != _model_input_routing_inputs(report):
        raise ValueError("model_input_routing_report_lineage_mismatch")
    return report


def _discover_port_routes(
    store: CoreJSONArtifactStore,
    *,
    compilation_report: ModelInputCompilationReport,
    catalog_authority: CanonicalAcquisitionAuthority,
    include_query_envelope: bool = False,
) -> tuple[ModelInputPortRoute, ...]:
    routes: list[ModelInputPortRoute] = []
    for requirement in compilation_report.requirements:
        try:
            descriptor = catalog_authority.discover_model_input_source_descriptor(
                store,
                model_input_interface_ref=compilation_report.interface_ref,
                port_id=requirement.port.port_id,
                include_query_envelope=include_query_envelope,
            )
        except AcquisitionAuthorityError as exc:
            disposition = _MODEL_INPUT_SOURCE_REFUSAL_DISPOSITIONS.get(exc.code)
            if disposition is None:
                raise
            query_envelope = exc.query_envelope
            if include_query_envelope and query_envelope is None:
                raise ValueError("model_input_routing_query_envelope_unavailable") from exc
            routes.append(
                ModelInputPortRoute(
                    requirement_id=requirement.requirement_id,
                    obligation_ref=requirement.obligation_ref,
                    port_id=requirement.port.port_id,
                    disposition=disposition,
                    query_envelope=query_envelope if include_query_envelope else None,
                    reason_code=exc.code,
                )
            )
        else:
            query_envelope = descriptor.query_envelope
            if include_query_envelope and query_envelope is None:
                raise ValueError("model_input_routing_query_envelope_unavailable")
            if include_query_envelope:
                descriptor = ModelInputSourceDescriptorCandidate.model_validate(
                    {
                        **descriptor.model_dump(mode="python"),
                        "query_envelope": None,
                    }
                )
            routes.append(
                ModelInputPortRoute(
                    requirement_id=requirement.requirement_id,
                    obligation_ref=requirement.obligation_ref,
                    port_id=requirement.port.port_id,
                    disposition="resolved",
                    source_descriptor=descriptor,
                    query_envelope=query_envelope if include_query_envelope else None,
                )
            )
    if len(routes) != len(compilation_report.requirements):
        raise ValueError("model_input_routing_requirement_denominator_mismatch")
    return tuple(routes)


def _build_report(
    *,
    selected_basis: SelectedProgramGraphInputBasis,
    selected_invocation: ProgramGraphInputInvocation,
    obligation_set_ref: ArtifactRef,
    compilation_report_ref: ArtifactRef,
    routes: Sequence[ModelInputPortRoute],
    schema_version: Literal["1.0", "2.0"] = MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION,
) -> ModelInputRoutingReport:
    if selected_invocation.context != selected_basis.context:
        raise ValueError("model_input_routing_selected_context_mismatch")
    return ModelInputRoutingReport(
        schema_version=schema_version,
        selected_invocation=selected_invocation,
        obligation_set_ref=obligation_set_ref,
        compilation_report_ref=compilation_report_ref,
        routes=tuple(routes),
        status=(
            "candidate_descriptors_resolved"
            if routes and all(route.disposition == "resolved" for route in routes)
            else "candidate_descriptors_limited"
        ),
    )


def _model_input_routing_inputs(report: ModelInputRoutingReport) -> list[InputRef]:
    invocation = report.selected_invocation
    inputs = [
        input_ref_from_artifact_ref(report.obligation_set_ref, role="selected_obligation_set"),
        input_ref_from_artifact_ref(
            report.compilation_report_ref, role="model_input_compilation_report"
        ),
        input_ref_from_artifact_ref(invocation.interface_ref, role="selected_input_interface"),
        input_ref_from_artifact_ref(invocation.program_graph_ref, role="selected_program_graph"),
        input_ref_from_artifact_ref(invocation.exec_plan_ref, role="selected_exec_plan"),
        input_ref_from_artifact_ref(
            invocation.registry_bundle_ref, role="selected_registry_bundle"
        ),
        input_ref_from_artifact_ref(invocation.input_bindings_ref, role="selected_input_bindings"),
    ]
    if invocation.context.candidate_source_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                invocation.context.candidate_source_ref, role="selected_candidate_source"
            )
        )
    if invocation.context.context_job_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                invocation.context.context_job_ref, role="selected_context_job"
            )
        )
    if invocation.parameter_override_bundle_ref is not None:
        inputs.append(
            input_ref_from_artifact_ref(
                invocation.parameter_override_bundle_ref, role="selected_parameter_overrides"
            )
        )
    for index, route in enumerate(report.routes):
        descriptor = route.source_descriptor
        if descriptor is None:
            envelope = route.query_envelope
            if envelope is not None:
                for role, ref in (
                    ("model_semantic_definition", envelope.model_semantic_definition_ref),
                    ("model_representation", envelope.model_representation_ref),
                    ("measurement_binding_profile", envelope.binding_profile_ref),
                ):
                    inputs.append(
                        input_ref_from_artifact_ref(ref, role=f"route.{index}.query.{role}")
                    )
            continue
        for role, ref in (
            ("source_semantic_definition", descriptor.source_semantic_definition_ref),
            ("source_representation", descriptor.source_representation_ref),
            ("model_semantic_definition", descriptor.model_semantic_definition_ref),
            ("model_representation", descriptor.model_representation_ref),
            ("measurement_binding_profile", descriptor.binding_profile_ref),
        ):
            inputs.append(input_ref_from_artifact_ref(ref, role=f"route.{index}.{role}"))
    return inputs


__all__ = [
    "ModelInputPortRoute",
    "ModelInputRoutingReport",
    "ModelInputRoutingResult",
    "materialize_routed_model_input_observation",
    "plan_selected_model_input_routing",
    "read_model_input_routing_report",
    "verify_model_input_routing_report",
]
