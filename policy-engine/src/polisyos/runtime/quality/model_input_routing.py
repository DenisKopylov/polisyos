"""Candidate-only N7 routing for exact selected ProgramGraph input obligations.

Model-owned ports are execution requirements, not claim or facet gaps. This
module replays the selected N5 invocation, compiles its missing ports, and
discovers compatible Catalog descriptors. It also links a resolved descriptor
to independently activated Catalog evidence for candidate model-input use.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    CoreJSONArtifactProfileReader,
    CoreJSONArtifactStore,
    InputRef,
    ProducerInfo,
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
    from decimal import Decimal
    from pathlib import Path

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.contracts import (
        DerivedInputCorrespondenceRef,
        DerivedInputProfileRef,
        DerivedMeasurementRole,
        FoundryInputBindings,
        FoundryInputBindingsRef,
        ModelInputObligation,
        ModelInputObligationSet,
        ModelInputStepScope,
        RatioDenominatorSourceContextRef,
        RegisteredDerivedInputCorrespondence,
        RegisteredDerivedInputProfileRef,
        RegisteredDerivedModelInputRequest,
        RegisteredMeasurementRole,
        ResolvedDerivedInput,
        ResolvedInputBindingManifestRef,
    )
    from polisyos.data_forge.read_api.catalog import CatalogAcquisitionOverlay

    from .acquisition_executor import AdmissionPassport
    from .data_state_substrate import AcquiredObservationDataSnapshotResult


MODEL_INPUT_ROUTING_REPORT_KIND = "runtime.quality.model_input_routing_report"
MODEL_INPUT_ROUTING_REPORT_SCHEMA_NAME = "polisyos.runtime.quality.ModelInputRoutingReport"
MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION = "1.0"
MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2 = "2.0"
MODEL_INPUT_ROUTING_COMPATIBILITY_RULE_VERSION = "model_input_source_compatibility@1.0"
MODEL_INPUT_ROUTING_USE_DECISION_KIND = "runtime.quality.model_input_routing_use_decision"
MODEL_INPUT_ROUTING_USE_DECISION_SCHEMA = "polisyos.runtime.quality.ModelInputRoutingUseDecision"
MODEL_INPUT_ROUTING_USE_DECISION_VERSION = "1.0"
_MODEL_INPUT_ROUTING_PROHIBITED_USES = (
    "measurement_admission",
    "fetch_permission",
    "claim_evidence",
    "source_currentness",
    "publication",
)
_MODEL_INPUT_ROUTING_USE_DECISION_PROHIBITED_USES = (
    "measurement_admission",
    "fetch_permission",
    "claim_evidence",
    "source_currentness",
    "publication",
)
_MODEL_INPUT_ROUTING_USE_DECISION_PAYLOAD_SCHEMA = (
    "polisyos.runtime.quality.ModelInputRoutingUseDecision@1.0"
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
            refusal = envelope.route_selection_refusal(route.disposition, descriptor)
            if refusal is not None:
                raise ValueError(f"model_input_routing_v2_{refusal}")
        return self


class ModelInputRoutingUseDecision(_StrictModel):
    """Candidate-only record of the exact route rechecked at a current use."""

    ARTIFACT_KIND: ClassVar[str] = MODEL_INPUT_ROUTING_USE_DECISION_KIND
    ARTIFACT_MEDIA_TYPE: ClassVar[str] = "application/json"
    ARTIFACT_SCHEMA_NAME: ClassVar[str] = MODEL_INPUT_ROUTING_USE_DECISION_SCHEMA
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = MODEL_INPUT_ROUTING_USE_DECISION_VERSION
    ARTIFACT_SCHEMA_VERSIONS: ClassVar[tuple[str, ...]] = (
        MODEL_INPUT_ROUTING_USE_DECISION_VERSION,
    )
    ARTIFACT_PAYLOAD_SCHEMA_VERSION_BY_MANIFEST: ClassVar[dict[str, str]] = {
        MODEL_INPUT_ROUTING_USE_DECISION_VERSION: _MODEL_INPUT_ROUTING_USE_DECISION_PAYLOAD_SCHEMA
    }

    schema_version: Literal["polisyos.runtime.quality.ModelInputRoutingUseDecision@1.0"] = (
        "polisyos.runtime.quality.ModelInputRoutingUseDecision@1.0"
    )
    authority_purpose: Literal["candidate_model_input_route_recheck_only"] = (
        "candidate_model_input_route_recheck_only"
    )
    routing_report_ref: ArtifactRef
    route_port_id: str = Field(min_length=1)
    query_key_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    query_envelope_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_registry_content_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    compatibility_rule_version: str = Field(min_length=1)
    reverse_view_status: Literal["recomputed", "not_established"]
    cas_owner_generation_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    query_subscriber_inventory_sha256: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    query_subscriber_refs: tuple[ArtifactRef, ...] = ()
    active_tenant_id: str | None = None
    active_cell_id: str | None = None
    may_not_use_for: tuple[
        Literal[
            "measurement_admission",
            "fetch_permission",
            "claim_evidence",
            "source_currentness",
            "publication",
        ],
        ...,
    ] = _MODEL_INPUT_ROUTING_USE_DECISION_PROHIBITED_USES

    @model_validator(mode="after")
    def _selection_and_inventory_are_bound(self) -> Self:
        if (
            self.routing_report_ref.kind != MODEL_INPUT_ROUTING_REPORT_KIND
            or self.routing_report_ref.media_type != "application/json"
            or self.routing_report_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("model_input_routing_use_decision_report_unselected")
        if self.may_not_use_for != _MODEL_INPUT_ROUTING_USE_DECISION_PROHIBITED_USES:
            raise ValueError("model_input_routing_use_decision_boundary_invalid")
        if not self.active_tenant_id or not self.compatibility_rule_version:
            raise ValueError("model_input_routing_use_decision_scope_or_rule_missing")
        identities = tuple(artifact_ref_identity_key(ref) for ref in self.query_subscriber_refs)
        if identities != tuple(
            sorted(set(identities), key=lambda identity: tuple(value or "" for value in identity))
        ) or any(
            ref.kind != MODEL_INPUT_ROUTING_REPORT_KIND
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref in self.query_subscriber_refs
        ):
            raise ValueError("model_input_routing_use_decision_subscribers_invalid")
        inventory_values = (
            self.cas_owner_generation_sha256,
            self.query_subscriber_inventory_sha256,
            self.active_tenant_id,
        )
        if self.reverse_view_status == "recomputed":
            if (
                any(value is None for value in inventory_values)
                or not self.query_subscriber_refs
                or self.routing_report_ref not in self.query_subscriber_refs
            ):
                raise ValueError("model_input_routing_use_decision_inventory_incomplete")
        elif any(value is not None for value in inventory_values[:2]) or self.query_subscriber_refs:
            raise ValueError("model_input_routing_use_decision_inventory_status_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _RoutingQueryKey:
    """Exact query inputs without result rows or their derived envelope hash."""

    canonical_projection: str
    sha256: str
    coarse_key: tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]


@dataclass(frozen=True, slots=True)
class _RoutingReverseView:
    """Rebuildable metadata-only reverse view of selected routing-report manifests."""

    owner_generation_sha256: str
    authority_registry_content_sha256: str
    compatibility_rule_version: str
    active_tenant_id: str
    active_cell_id: str | None
    coarse_memberships: tuple[
        tuple[
            tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]],
            ArtifactRef,
        ],
        ...,
    ]
    complete: bool
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class _RoutingReverseViewStatus:
    """Current reverse-view identity, or the precise reason it was unavailable."""

    view: _RoutingReverseView | None
    reason_code: str | None = None
    query_subscriber_refs: tuple[ArtifactRef, ...] = ()


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

    report, current, _view_status = _verify_model_input_routing_report_current_with_view(
        store,
        report_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=catalog_authority,
    )
    return report, current


def _verify_model_input_routing_report_current_with_view(
    store: CoreJSONArtifactStore,
    report_ref: ArtifactRef,
    *,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
) -> tuple[
    ModelInputRoutingReport,
    ModelInputRoutingReport,
    _RoutingReverseViewStatus,
]:
    """Reopen current route facts and qualify a complete reverse-view snapshot.

    A missing inventory capability, unscoped store, incomplete manifest row, or
    query refinement problem disables only the optimization. The selected
    route is always rederived directly from the current Catalog below.
    """

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
    reverse_view_status = _build_routing_reverse_view_status(
        store,
        canonical_authority,
        report_ref=report_ref,
        report=report,
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
    if reverse_view_status.view is not None:
        current_registry_sha256 = _current_authority_registry_sha256(canonical_authority)
        descriptors = tuple(
            route.source_descriptor for route in expected.routes if route.source_descriptor
        )
        if (
            reverse_view_status.view.authority_registry_content_sha256 != current_registry_sha256
            or any(
                descriptor.authority_registry_content_sha256 != current_registry_sha256
                for descriptor in descriptors
            )
        ):
            reverse_view_status = _RoutingReverseViewStatus(
                view=None,
                reason_code="model_input_routing_reverse_view_registry_changed",
            )
    return report, expected, reverse_view_status


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


def _routing_json_bytes(value: object) -> bytes:
    """Serialize the small typed routing projections used as exact keys."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _manifest_input_identity(value: object) -> tuple[str, str] | None:
    """Return the selected blob/profile identity from one manifest input role."""

    artifact_id = getattr(value, "artifact_id", None)
    profile = getattr(value, "manifest_profile_sha256", None)
    if artifact_id is None or not isinstance(profile, str):
        return None
    return str(artifact_id), profile


def _routing_query_key(envelope: ModelInputSourceQueryEnvelope) -> _RoutingQueryKey:
    """Project exact query scope without matching on rows or the derived hash."""

    projection = envelope.identity_payload()
    projection.pop("rows", None)
    projection.pop("content_sha256", None)
    encoded = _routing_json_bytes(projection)
    coarse = (
        artifact_ref_identity_key(envelope.model_input_interface_ref),
        artifact_ref_identity_key(envelope.model_semantic_definition_ref),
        artifact_ref_identity_key(envelope.model_representation_ref),
        artifact_ref_identity_key(envelope.binding_profile_ref),
    )
    return _RoutingQueryKey(
        canonical_projection=encoded.decode("utf-8"),
        sha256="sha256:" + hashlib.sha256(encoded).hexdigest(),
        coarse_key=tuple((identity[0], identity[3] or "") for identity in coarse),
    )


def _coarse_route_memberships(
    manifest: object,
) -> tuple[
    tuple[tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]], ...],
    str | None,
]:
    """Extract coarse selected-ref edges from report manifest roles only."""

    inputs = getattr(manifest, "inputs", None)
    if type(inputs) is not list or not inputs:
        return (), "model_input_routing_reverse_view_manifest_inputs_missing"
    route_numbers: set[str] = set()
    role_rows: dict[str, list[object]] = {}
    for item in inputs:
        role = getattr(item, "role", None)
        if not isinstance(role, str):
            return (), "model_input_routing_reverse_view_manifest_role_invalid"
        role_rows.setdefault(role, []).append(item)
        if role.startswith("route."):
            parts = role.split(".", 2)
            if len(parts) != 3 or not parts[1].isdigit():
                return (), "model_input_routing_reverse_view_manifest_role_invalid"
            route_numbers.add(parts[1])
    selected_interface = role_rows.get("selected_input_interface", ())
    if len(selected_interface) != 1:
        return (), "model_input_routing_reverse_view_interface_role_incomplete"
    interface_identity = _manifest_input_identity(selected_interface[0])
    if interface_identity is None:
        return (), "model_input_routing_reverse_view_interface_profile_missing"
    if not route_numbers:
        return (), "model_input_routing_reverse_view_route_roles_missing"
    ordered_route_numbers = sorted(route_numbers, key=int)
    if ordered_route_numbers != [str(index) for index in range(len(ordered_route_numbers))]:
        return (), "model_input_routing_reverse_view_route_roles_incomplete"

    memberships = []
    for route_number in ordered_route_numbers:
        prefix = f"route.{route_number}."

        def exact_input(route_prefix: str, *suffixes: str) -> object | None:
            matches = [
                item for suffix in suffixes for item in role_rows.get(route_prefix + suffix, ())
            ]
            return matches[0] if len(matches) == 1 else None

        semantic = exact_input(
            prefix, "model_semantic_definition", "query.model_semantic_definition"
        )
        representation = exact_input(prefix, "model_representation", "query.model_representation")
        profile = exact_input(
            prefix, "measurement_binding_profile", "query.measurement_binding_profile"
        )
        identities = tuple(
            _manifest_input_identity(item) for item in (semantic, representation, profile)
        )
        if any(identity is None for identity in identities):
            return (), "model_input_routing_reverse_view_query_roles_incomplete"
        memberships.append((interface_identity, *identities))
    return tuple(memberships), None


def _current_authority_registry_sha256(
    authority: CanonicalAcquisitionAuthority,
) -> str:
    """Reopen the canonical registry and provision before binding a view."""

    authority._require_provision_unchanged()
    registry = authority._load_registry()
    authority._require_provision_unchanged()
    return registry.content_sha256


def _active_store_owner_scope(store: object) -> tuple[str, str | None] | None:
    """Return the concrete tenant view used by the optional CAS inventory API."""

    resolver = getattr(store, "_resolve_owner", None)
    if not callable(resolver):
        return None
    try:
        tenant_id, cell_id = resolver(required=False)
    except (OSError, TypeError, ValueError, RuntimeError):
        return None
    if not isinstance(tenant_id, str) or not tenant_id:
        return None
    if cell_id is not None and not isinstance(cell_id, str):
        return None
    return tenant_id, cell_id


def _build_routing_reverse_view_status(
    store: CoreJSONArtifactStore,
    authority: CanonicalAcquisitionAuthority,
    *,
    report_ref: ArtifactRef,
    report: ModelInputRoutingReport,
) -> _RoutingReverseViewStatus:
    """Build a metadata-only coarse view and refine only the selected query.

    The concrete manifest-inventory capability is intentionally optional and
    stays outside the CoreJSONArtifactStore protocol. Unsupported or incomplete
    inventories always fall back to the fresh direct Catalog query.
    """

    tenant_scope = _active_store_owner_scope(store)
    if tenant_scope is None:
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_active_tenant_unestablished",
        )
    inventory_method = getattr(store, "manifest_inventory_snapshot", None)
    if not callable(inventory_method):
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_inventory_capability_unavailable",
        )
    try:
        registry_sha256 = _current_authority_registry_sha256(authority)
        snapshot = inventory_method(kind=MODEL_INPUT_ROUTING_REPORT_KIND)
    except (AcquisitionAuthorityError, OSError, RuntimeError, TypeError, ValueError):
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_inventory_unavailable",
        )
    required_inventory_inputs = {
        "complete canonical CAS root member names",
        "all active-scope manifest bytes, identities, and profiles",
        "signed ownership-index generation",
        f"all visible manifests with exact kind {MODEL_INPUT_ROUTING_REPORT_KIND!r}",
    }
    required_unresolved = {
        "all payload blob bytes and digests; selected payloads require consumer verification",
        "detached signature contents",
        "other tenant views hidden by the active tenant scope",
        "direct filesystem writers outside the CAS lease protocol",
    }
    if (
        getattr(snapshot, "verdict", None) != "pass"
        or not isinstance(getattr(snapshot, "owner_generation_sha256", None), str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", snapshot.owner_generation_sha256) is None
        or type(getattr(snapshot, "entries", None)) is not tuple
        or type(getattr(snapshot, "inputs", None)) is not tuple
        or not required_inventory_inputs.issubset(snapshot.inputs)
        or type(getattr(snapshot, "unresolved_by_construction", None)) is not tuple
        or not required_unresolved.issubset(snapshot.unresolved_by_construction)
        or getattr(snapshot, "reason", None) is not None
    ):
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_inventory_incomplete",
        )

    memberships: list[
        tuple[
            tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]],
            ArtifactRef,
        ]
    ] = []
    complete = True
    reason_code = None
    tenant_id, cell_id = tenant_scope
    for entry in snapshot.entries:
        manifest = getattr(entry, "manifest", None)
        manifest_hash = getattr(entry, "manifest_sha256", None)
        manifest_profile = getattr(entry, "manifest_profile_sha256", None)
        if (
            getattr(manifest, "kind", None) != MODEL_INPUT_ROUTING_REPORT_KIND
            or not isinstance(manifest_hash, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_hash) is None
            or not isinstance(manifest_profile, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_profile) is None
            or not hasattr(manifest, "artifact_id")
            or type(getattr(manifest, "inputs", None)) is not list
            or getattr(manifest, "tenant_context", None) is None
            or getattr(manifest.tenant_context, "tenant_id", None) != tenant_id
            or getattr(manifest.tenant_context, "cell_id", None) != cell_id
        ):
            complete = False
            reason_code = reason_code or (
                "model_input_routing_reverse_view_tenant_or_manifest_unbound"
            )
            continue
        exact_ref = ArtifactRef(
            artifact_id=manifest.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=manifest_profile,
        )
        route_memberships, error = _coarse_route_memberships(manifest)
        if error is not None:
            complete = False
            reason_code = reason_code or error
        else:
            memberships.extend((membership, exact_ref) for membership in route_memberships)

    try:
        current_registry_sha256 = _current_authority_registry_sha256(authority)
    except (AcquisitionAuthorityError, OSError, RuntimeError, TypeError, ValueError):
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_registry_unavailable",
        )
    if current_registry_sha256 != registry_sha256:
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_registry_changed",
        )
    view = _RoutingReverseView(
        owner_generation_sha256=snapshot.owner_generation_sha256,
        authority_registry_content_sha256=registry_sha256,
        compatibility_rule_version=MODEL_INPUT_ROUTING_COMPATIBILITY_RULE_VERSION,
        active_tenant_id=tenant_id,
        active_cell_id=cell_id,
        coarse_memberships=tuple(memberships),
        complete=complete,
        reason_code=reason_code,
    )
    if not complete:
        return _RoutingReverseViewStatus(view=None, reason_code=reason_code)
    if report.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2:
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_report_query_unavailable",
        )
    report_ref_key = artifact_ref_identity_key(report_ref)
    target_keys = tuple(
        _routing_query_key(route.query_envelope)
        for route in report.routes
        if route.query_envelope is not None
    )
    if len(target_keys) != len(report.routes):
        return _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_query_incomplete",
        )
    query_subscribers: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
    for key in target_keys:
        subscribers, complete_query = _refine_routing_query_subscribers(store, view, key)
        if not complete_query or not any(
            artifact_ref_identity_key(subscriber) == report_ref_key for subscriber in subscribers
        ):
            return _RoutingReverseViewStatus(
                view=None,
                reason_code="model_input_routing_reverse_view_query_refinement_incomplete",
            )
        query_subscribers.update(
            (artifact_ref_identity_key(subscriber), subscriber) for subscriber in subscribers
        )
    return _RoutingReverseViewStatus(
        view=view,
        query_subscriber_refs=tuple(query_subscribers[key] for key in sorted(query_subscribers)),
    )


def _refine_routing_query_subscribers(
    store: CoreJSONArtifactStore,
    view: _RoutingReverseView,
    query_key: _RoutingQueryKey,
) -> tuple[tuple[ArtifactRef, ...], bool]:
    """Read only coarse-matching report payloads to group exact query keys."""

    candidates = tuple(
        report_ref
        for coarse_key, report_ref in view.coarse_memberships
        if coarse_key == query_key.coarse_key
    )
    subscribers: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
    complete = view.complete
    for candidate_ref in candidates:
        try:
            candidate_report = read_model_input_routing_report(store, candidate_ref)
        except (OSError, TypeError, ValueError):
            complete = False
            continue
        if candidate_report.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2:
            complete = False
            continue
        for route in candidate_report.routes:
            envelope = route.query_envelope
            if envelope is None:
                complete = False
                continue
            if _routing_query_key(envelope) == query_key:
                subscribers[artifact_ref_identity_key(candidate_ref)] = candidate_ref
    return tuple(subscribers[key] for key in sorted(subscribers)), complete


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

    owner_scope = _active_store_owner_scope(store)
    ref = store.put_json(
        report,
        PutOptions(
            kind=report.ARTIFACT_KIND,
            media_type=report.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=report.ARTIFACT_SCHEMA_NAME,
                version=report.schema_version,
            ),
            tenant_context=(
                ArtifactTenantContextInfo(tenant_id=owner_scope[0], cell_id=owner_scope[1])
                if owner_scope is not None
                else None
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


def persist_current_model_input_routing_use_decision(
    store: CoreJSONArtifactStore,
    report_ref: ArtifactRef,
    *,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
    tenant_id: str,
    cell_id: str,
    route_port_id: str,
) -> tuple[ArtifactRef, ModelInputRoutingUseDecision]:
    """Re-derive one current route and persist its candidate-only use decision.

    The complete Catalog re-derivation is authoritative for this use. The
    optional reverse view contributes only a scoped subscriber inventory; an
    unavailable view is persisted as ``not_established`` and never as empty.
    """

    if not tenant_id or not cell_id or not route_port_id:
        raise ValueError("model_input_routing_use_decision_scope_required")
    report, current, view_status = _verify_model_input_routing_report_current_with_view(
        store,
        report_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=catalog_authority,
    )
    if report.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2:
        raise ValueError("model_input_routing_use_decision_v2_report_required")
    if len(report.routes) != 1 or len(current.routes) != 1:
        raise ValueError("model_input_routing_use_decision_single_route_required")
    matching_routes = tuple(route for route in current.routes if route.port_id == route_port_id)
    if len(matching_routes) != 1:
        raise ValueError("model_input_routing_use_decision_route_not_selected")
    (route,) = matching_routes
    envelope = route.query_envelope
    descriptor = route.source_descriptor
    if route.disposition != "resolved" or envelope is None or descriptor is None:
        raise ValueError("model_input_routing_use_decision_resolved_route_required")
    registry_sha256 = _current_authority_registry_sha256(catalog_authority)
    if descriptor.authority_registry_content_sha256 != registry_sha256:
        raise ValueError("model_input_routing_use_decision_registry_changed")

    view = view_status.view
    if view is not None and (view.active_tenant_id, view.active_cell_id) != (tenant_id, cell_id):
        view_status = _RoutingReverseViewStatus(
            view=None,
            reason_code="model_input_routing_reverse_view_action_scope_mismatch",
        )
        view = None
    subscribers = view_status.query_subscriber_refs if view is not None else ()
    subscriber_inventory_sha256 = (
        _query_subscriber_inventory_sha256(subscribers) if view is not None else None
    )
    decision = ModelInputRoutingUseDecision(
        routing_report_ref=report_ref,
        route_port_id=route_port_id,
        query_key_sha256=_routing_query_key(envelope).sha256,
        query_envelope_content_sha256=envelope.content_sha256,
        authority_registry_content_sha256=registry_sha256,
        compatibility_rule_version=MODEL_INPUT_ROUTING_COMPATIBILITY_RULE_VERSION,
        reverse_view_status="recomputed" if view is not None else "not_established",
        cas_owner_generation_sha256=view.owner_generation_sha256 if view is not None else None,
        query_subscriber_inventory_sha256=subscriber_inventory_sha256,
        query_subscriber_refs=subscribers,
        active_tenant_id=tenant_id,
        active_cell_id=cell_id,
    )
    decision_ref = store.put_json(
        decision,
        PutOptions(
            kind=decision.ARTIFACT_KIND,
            media_type=decision.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=decision.ARTIFACT_SCHEMA_NAME,
                version=decision.ARTIFACT_SCHEMA_VERSION,
            ),
            producer=ProducerInfo(component=__name__, version="1.0"),
            tenant_context=ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id),
            inputs=_model_input_routing_use_decision_inputs(decision),
        ),
        return_selected_profile=True,
    )
    if read_model_input_routing_use_decision(store, decision_ref) != decision:
        raise ValueError("model_input_routing_use_decision_readback_mismatch")
    return decision_ref, decision


def read_model_input_routing_use_decision(
    store: CoreJSONArtifactProfileReader,
    ref: ArtifactRef,
) -> ModelInputRoutingUseDecision:
    """Read one exact candidate routing-use decision and reconcile its lineage."""

    if (
        ref.kind != MODEL_INPUT_ROUTING_USE_DECISION_KIND
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise ValueError("model_input_routing_use_decision_ref_unselected")
    decision = validate_core_model_json_artifact(ModelInputRoutingUseDecision, store, ref)
    manifest = store.get_manifest(ref)
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.version != MODEL_INPUT_ROUTING_USE_DECISION_VERSION
        or manifest.inputs != _model_input_routing_use_decision_inputs(decision)
        or manifest.producer != ProducerInfo(component=__name__, version="1.0")
        or manifest.tenant_context
        != ArtifactTenantContextInfo(
            tenant_id=decision.active_tenant_id,
            cell_id=decision.active_cell_id,
        )
    ):
        raise ValueError("model_input_routing_use_decision_lineage_mismatch")
    report = read_model_input_routing_report(store, decision.routing_report_ref)
    matching_routes = tuple(
        route for route in report.routes if route.port_id == decision.route_port_id
    )
    if len(matching_routes) != 1:
        raise ValueError("model_input_routing_use_decision_route_mismatch")
    envelope = matching_routes[0].query_envelope
    if (
        envelope is None
        or envelope.content_sha256 != decision.query_envelope_content_sha256
        or _routing_query_key(envelope).sha256 != decision.query_key_sha256
    ):
        raise ValueError("model_input_routing_use_decision_query_mismatch")
    if decision.reverse_view_status == "recomputed" and (
        _query_subscriber_inventory_sha256(decision.query_subscriber_refs)
        != decision.query_subscriber_inventory_sha256
    ):
        raise ValueError("model_input_routing_use_decision_inventory_digest_mismatch")
    if decision.reverse_view_status == "recomputed":
        for subscriber_ref in decision.query_subscriber_refs:
            subscriber = read_model_input_routing_report(store, subscriber_ref)
            if subscriber.schema_version != MODEL_INPUT_ROUTING_REPORT_SCHEMA_VERSION_V2 or not any(
                route.query_envelope is not None
                and _routing_query_key(route.query_envelope).sha256 == decision.query_key_sha256
                for route in subscriber.routes
            ):
                raise ValueError("model_input_routing_use_decision_subscriber_mismatch")
    return decision


def verify_model_input_routing_use_decision_current(
    store: CoreJSONArtifactStore,
    use_decision_ref: ArtifactRef,
    *,
    expected_report_ref: ArtifactRef,
    expected_obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
    catalog_authority: CanonicalAcquisitionAuthority,
) -> ModelInputRoutingUseDecision:
    """Recompute Catalog and inventory bindings before a protected input use."""

    decision = read_model_input_routing_use_decision(store, use_decision_ref)
    if artifact_ref_identity_key(decision.routing_report_ref) != artifact_ref_identity_key(
        expected_report_ref
    ):
        raise ValueError("model_input_routing_use_decision_report_mismatch")
    if decision.compatibility_rule_version != MODEL_INPUT_ROUTING_COMPATIBILITY_RULE_VERSION:
        raise ValueError("model_input_routing_use_decision_rule_version_stale")
    _report, current, current_view_status = _verify_model_input_routing_report_current_with_view(
        store,
        decision.routing_report_ref,
        expected_obligation_set_ref=expected_obligation_set_ref,
        selected_basis=selected_basis,
        catalog_authority=catalog_authority,
    )
    route = next((item for item in current.routes if item.port_id == decision.route_port_id), None)
    registry_sha256 = _current_authority_registry_sha256(catalog_authority)
    if (
        route is None
        or route.query_envelope is None
        or route.source_descriptor is None
        or route.disposition != "resolved"
        or _routing_query_key(route.query_envelope).sha256 != decision.query_key_sha256
        or route.query_envelope.content_sha256 != decision.query_envelope_content_sha256
        or registry_sha256 != decision.authority_registry_content_sha256
        or route.source_descriptor.authority_registry_content_sha256 != registry_sha256
    ):
        raise ValueError("model_input_routing_use_decision_currentness_mismatch")
    if decision.reverse_view_status == "recomputed":
        current_view = current_view_status.view
        if (
            current_view is None
            or (current_view.active_tenant_id, current_view.active_cell_id)
            != (decision.active_tenant_id, decision.active_cell_id)
            or current_view_status.query_subscriber_refs != decision.query_subscriber_refs
            or _query_subscriber_inventory_sha256(current_view_status.query_subscriber_refs)
            != decision.query_subscriber_inventory_sha256
        ):
            raise ValueError("model_input_routing_use_decision_inventory_stale")
    return decision


def _query_subscriber_inventory_sha256(refs: tuple[ArtifactRef, ...]) -> str:
    """Hash exact selected report profiles for one query-key subscriber set."""

    identities = sorted(
        (artifact_ref_identity_key(ref) for ref in refs),
        key=lambda identity: tuple(value or "" for value in identity),
    )
    return "sha256:" + hashlib.sha256(_routing_json_bytes(identities)).hexdigest()


def _model_input_routing_use_decision_inputs(
    decision: ModelInputRoutingUseDecision,
) -> list[InputRef]:
    inputs = [input_ref_from_artifact_ref(decision.routing_report_ref, role="routing_report")]
    inputs.extend(
        input_ref_from_artifact_ref(ref, role=f"query_subscriber.{index:04d}")
        for index, ref in enumerate(decision.query_subscriber_refs)
    )
    return inputs


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


@dataclass(frozen=True)
class DerivedModelInputMaterialization:
    """Persisted candidate derived input and its actual Foundry intake refs."""

    data_snapshot_ref: ArtifactRef
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef
    correspondence_ref: DerivedInputCorrespondenceRef
    input_bindings_ref: FoundryInputBindingsRef


@dataclass(frozen=True)
class DerivedModelInputBatchMaterialization:
    """One atomic input manifest and actual Foundry intake for complete ports."""

    data_snapshot_ref: ArtifactRef
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef
    correspondence_refs: tuple[DerivedInputCorrespondenceRef, ...]
    input_bindings_ref: FoundryInputBindingsRef


@dataclass(frozen=True)
class _DerivedPortOutput:
    selection: ResolvedDerivedInput
    value: Decimal
    projection: Literal["scalar", "singleton_vector"]


def _is_registered_graph_selection(
    store: CoreJSONArtifactProfileReader, selection: ResolvedDerivedInput
) -> bool:
    from polisyos.core.contracts import RegisteredDerivedGraphCorrespondence

    return store.get_manifest(selection.correspondence_ref).artifact_schema == SchemaInfo(
        name=RegisteredDerivedGraphCorrespondence.ARTIFACT_SCHEMA_NAME,
        version=RegisteredDerivedGraphCorrespondence.ARTIFACT_SCHEMA_VERSION,
    )


def materialize_derived_model_input(
    store: FileSystemCAS,
    *,
    base_data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    model_input_obligation_ref: ArtifactRef,
    profile_ref: DerivedInputProfileRef,
    source_context_ref: RatioDenominatorSourceContextRef,
    recipe_ref: ArtifactRef,
    certificate_ref: ArtifactRef,
    output_ref: ArtifactRef,
    roles: tuple[DerivedMeasurementRole, ...],
    year: int,
    binding_id: str,
    derivation_bundle_ref: ArtifactRef | None = None,
) -> DerivedModelInputMaterialization:
    """Wire one complete candidate derivation into the existing Foundry intake.

    This first materializer supports one target obligation. It retains the base
    snapshot only as physical context and writes distinct derived lineage.
    A declared method carrier persists a separate scalar NPY argument through
    Foundry and retains the exact predecessor state; a state carrier uses the
    existing declared state binding. Neither output claims to be an acquired
    observation. N7's optional bundle is planning provenance, not permission.
    """
    from polisyos.core.contracts import (
        DerivedInputCorrespondenceBasis,
        ResolvedDerivedInput,
        SelectedVariableBindingRef,
        load_derived_input_profile,
        load_model_input_obligation_set,
        persist_derived_input_correspondence,
    )
    from polisyos.core.derivations import (
        load_derivation_recipe_artifact,
        resolve_certified_derivation,
    )

    def selected(ref: ArtifactRef) -> SelectedVariableBindingRef:
        return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python"))

    base_ref = selected(base_data_snapshot_ref)
    selected_set, obligations = load_model_input_obligation_set(store, obligation_set_ref)
    if len(selected_set.obligation_refs) != 1 or (
        artifact_ref_identity_key(selected_set.obligation_refs[0])
        != artifact_ref_identity_key(model_input_obligation_ref)
    ):
        raise ValueError("derived_model_input_single_selected_obligation_required")
    (obligation,) = obligations
    profile = load_derived_input_profile(store, profile_ref)
    if obligation.port.carrier == "method_input" and (
        profile.output_projection != "scalar"
        or obligation.port.physical_encoding is None
        or obligation.port.physical_encoding.shape
    ):
        raise ValueError("derived_model_input_method_scalar_profile_required")
    recipe = load_derivation_recipe_artifact(store, recipe_ref)
    resolution = resolve_certified_derivation(
        store,
        certificate_ref=certificate_ref,
        consumer_method_id="polisyos.runtime.derived-model-input-materializer.v1",
    )
    if recipe != resolution.certificate.recipe:
        raise ValueError("derived_model_input_recipe_certificate_mismatch")
    points = tuple(point for point in resolution.series.points if point.year == year)
    if len(points) != 1:
        raise ValueError("derived_model_input_exact_year_required")
    registry = recipe.registry_artifact
    basis = DerivedInputCorrespondenceBasis(
        profile_ref=profile_ref,
        source_context_ref=source_context_ref,
        model_input_obligation_ref=selected(model_input_obligation_ref),
        model_interface_ref=selected(obligation.interface_ref),
        model_port_id=obligation.port.port_id,
        target_definition_ref=obligation.port.semantic_definition_ref,
        target_representation_ref=obligation.port.representation_ref,
        binding_profile_ref=obligation.port.binding_profile_ref,
        scope=obligation.port.scope,
        year=year,
        registry_ref=SelectedVariableBindingRef(
            artifact_id=registry.artifact_id,
            kind=registry.kind,
            media_type=registry.media_type,
            manifest_profile_sha256=registry.manifest_profile_sha256,
        ),
        family_id=recipe.family.family_id,
        method_version=recipe.method_version,
        recipe_ref=selected(recipe_ref),
        certificate_ref=selected(certificate_ref),
        output_ref=selected(output_ref),
        roles=roles,
    )
    correspondence_ref = persist_derived_input_correspondence(store, basis)
    source_path_key = hashlib.sha256(binding_id.encode()).hexdigest()[:20]
    selection = ResolvedDerivedInput(
        binding_id=binding_id,
        model_input_obligation_ref=selected(model_input_obligation_ref),
        model_interface_ref=selected(obligation.interface_ref),
        model_port_id=obligation.port.port_id,
        recipe_ref=selected(recipe_ref),
        certificate_ref=selected(certificate_ref),
        output_ref=selected(output_ref),
        year=year,
        correspondence_ref=correspondence_ref,
        profile_ref=profile_ref,
        source_path=f"derived_inputs.{source_path_key}.value",
        derivation_bundle_ref=(
            None if derivation_bundle_ref is None else selected(derivation_bundle_ref)
        ),
    )
    batch = _persist_derived_input_batch(
        store,
        base_data_snapshot_ref=base_ref,
        obligation_set_ref=obligation_set_ref,
        selected_set=selected_set,
        outputs=(_DerivedPortOutput(selection, points[0].value, profile.output_projection),),
    )
    return DerivedModelInputMaterialization(
        data_snapshot_ref=batch.data_snapshot_ref,
        resolved_binding_manifest_ref=batch.resolved_binding_manifest_ref,
        correspondence_ref=correspondence_ref,
        input_bindings_ref=batch.input_bindings_ref,
    )


def _persist_derived_input_batch(
    store: FileSystemCAS,
    *,
    base_data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    selected_set: ModelInputObligationSet,
    outputs: tuple[_DerivedPortOutput, ...],
) -> DerivedModelInputBatchMaterialization:
    """Write one complete port denominator through the canonical Foundry intake."""
    import copy

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts import (
        DERIVED_MODEL_INPUT_PAYLOAD_KIND,
        DataSnapshot,
        DataSnapshotOwnerBound,
        DerivedModelInputDataSnapshotLineage,
        ResolvedInputBindingManifest,
        SelectedVariableBindingRef,
        data_snapshot_owner_input_requirements,
        persist_resolved_input_binding_manifest,
    )
    from polisyos.foundry.data_plane import build_input_bindings, load_input_bindings

    def selected(ref: ArtifactRef) -> SelectedVariableBindingRef:
        return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python"))

    expected = {artifact_ref_identity_key(ref) for ref in selected_set.obligation_refs}
    actual = tuple(
        artifact_ref_identity_key(item.selection.model_input_obligation_ref) for item in outputs
    )
    if not outputs or len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("derived_model_input_complete_target_set_required")
    if len({item.selection.binding_id for item in outputs}) != len(outputs):
        raise ValueError("derived_model_input_binding_id_duplicate")
    predecessor = load_input_bindings(store, selected_set.invocation.input_bindings_ref)
    base_ref = selected(base_data_snapshot_ref)
    if artifact_ref_identity_key(base_ref) != artifact_ref_identity_key(
        predecessor.data_snapshot_ref
    ):
        raise ValueError("derived_model_input_base_context_mismatch")
    base = validate_core_model_json_artifact(DataSnapshot, store, base_ref)
    raw_payload = load_core_json_artifact(store, base.data_ref)
    if not isinstance(raw_payload, dict):
        raise ValueError("derived_model_input_base_payload_profile_unsupported")
    if "derived_inputs" in raw_payload:
        _verify_registered_method_reseal_namespace(
            store,
            source_input_bindings_ref=selected_set.invocation.input_bindings_ref,
            predecessor=predecessor,
            obligation_set_ref=obligation_set_ref,
            selected_set=selected_set,
            outputs=outputs,
            namespace=raw_payload["derived_inputs"],
        )
    payload = copy.deepcopy(raw_payload)
    derived_values: dict[str, dict[str, object]] = {}
    payload_inputs = [input_ref_from_artifact_ref(base.data_ref, role="context.base_payload")]
    for item in outputs:
        key = hashlib.sha256(item.selection.binding_id.encode()).hexdigest()[:20]
        if key in derived_values or item.selection.source_path != f"derived_inputs.{key}.value":
            raise ValueError("derived_model_input_source_path_collision")
        derived_values[key] = {"value": item.value if item.projection == "scalar" else [item.value]}
        payload_inputs.extend(
            (
                input_ref_from_artifact_ref(
                    item.selection.output_ref, role=item.selection.payload_output_role()
                ),
                input_ref_from_artifact_ref(
                    item.selection.correspondence_ref, role="derived.correspondence"
                ),
            )
        )
    payload["derived_inputs"] = derived_values
    payload_ref = store.put_json(
        payload,
        PutOptions(
            kind=DERIVED_MODEL_INPUT_PAYLOAD_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.0"
            ),
            inputs=payload_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot = DataSnapshotOwnerBound(
        data_ref=payload_ref,
        source_lineage=DerivedModelInputDataSnapshotLineage(
            base_data_snapshot_ref=base_ref,
            model_input_obligation_set_ref=obligation_set_ref,
            selections=tuple(item.selection for item in outputs),
        ),
        stats={"snapshot_id": "derived-model-input-" + payload_ref.artifact_id.hex[:20]},
        notes=[
            "candidate_simulation_input_only",
            "derived_input_not_acquired_observation",
            "external_empirical_context_not_established",
            "derivation_uncertainty_not_established",
        ],
    )
    correspondence_refs = tuple(item.selection.correspondence_ref for item in outputs)
    snapshot_ref = store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=snapshot.ARTIFACT_SCHEMA_NAME, version=snapshot.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role=role)
                for ref, role in data_snapshot_owner_input_requirements(snapshot)
            ],
        ),
        return_selected_profile=True,
    )
    retained_ids = tuple(
        rule.binding_id
        for rule in predecessor.rules
        if rule.target_slot_id in selected_set.supplied_initial_slots
    )
    manifest_ref = persist_resolved_input_binding_manifest(
        store,
        ResolvedInputBindingManifest(
            schema_version="2.0",
            data_snapshot_ref=selected(snapshot_ref),
            model_input_obligation_set_ref=selected(obligation_set_ref),
            derivations=tuple(item.selection for item in outputs),
            retained_binding_ids=retained_ids,
        ),
    )
    built = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=selected_set.invocation.registry_bundle_ref,
        resolved_binding_manifest_ref=manifest_ref,
        return_selected_profile=True,
    )
    return DerivedModelInputBatchMaterialization(
        data_snapshot_ref=snapshot_ref,
        resolved_binding_manifest_ref=manifest_ref,
        correspondence_refs=correspondence_refs,
        input_bindings_ref=built.input_bindings_ref,
    )


def _verify_registered_method_reseal_namespace(
    store: FileSystemCAS,
    *,
    source_input_bindings_ref: FoundryInputBindingsRef,
    predecessor: FoundryInputBindings,
    obligation_set_ref: ArtifactRef,
    selected_set: ModelInputObligationSet,
    outputs: tuple[_DerivedPortOutput, ...],
    namespace: object,
) -> None:
    """Reopen the complete old namespace before its method-only replacement."""
    from polisyos.core.contracts import (
        FoundrySelectedMethodInput,
        load_model_input_obligation_set,
        load_native_derivation_source_projection,
        load_registered_derived_input_correspondence,
        load_resolved_input_binding_manifest,
    )
    from polisyos.foundry.data_plane import replay_selected_method_input_facts
    from polisyos.foundry.execute import verify_current_use_method_input_revalidation

    if (
        selected_set.schema_version != "1.3"
        or selected_set.purpose != "current_use_method_input_revalidation"
        or selected_set.authority_purpose != "candidate_execution_input_revalidation_only"
        or predecessor.schema_version != "1.4"
        or predecessor.resolved_binding_manifest_ref is None
    ):
        raise ValueError("derived_model_input_base_payload_profile_unsupported")
    fresh = verify_current_use_method_input_revalidation(
        store,
        obligation_set_ref=obligation_set_ref,
        expected_invocation=selected_set.invocation,
    )
    if fresh != selected_set:
        raise ValueError("registered_method_reseal_set_replay_mismatch")
    old_manifest = load_resolved_input_binding_manifest(
        store, predecessor.resolved_binding_manifest_ref
    )
    old_set, old_members = load_model_input_obligation_set(
        store, old_manifest.model_input_obligation_set_ref
    )
    if (
        old_set.schema_version != "1.1"
        or old_manifest.schema_version != "2.0"
        or old_manifest.measurements
        or old_manifest.method_input_steps
        or len(old_manifest.derivations) != len(old_members)
    ):
        raise ValueError("registered_method_reseal_source_profile_unsupported")
    old_facts = replay_selected_method_input_facts(
        store,
        input_bindings_ref=source_input_bindings_ref,
        expected_invocation=old_set.invocation,
    )
    if (
        old_facts.bindings != predecessor
        or len(old_facts.records) != len(old_members)
        or any(row.shape for row in old_facts.records)
        or artifact_ref_identity_key(selected_set.prestate_ref)
        != artifact_ref_identity_key(predecessor.bound_state_snapshot_ref)
    ):
        raise ValueError("registered_method_reseal_source_prestate_mismatch")
    expected_namespace = {
        hashlib.sha256(row.binding_id.encode()).hexdigest()[:20]: {"value": row.canonical_value}
        for row in old_facts.records
    }
    if (
        len(expected_namespace) != len(old_facts.records)
        or namespace != expected_namespace
        or any(
            row.source_path
            != "derived_inputs."
            + hashlib.sha256(row.binding_id.encode()).hexdigest()[:20]
            + ".value"
            for row in old_manifest.derivations
        )
    ):
        raise ValueError("registered_method_reseal_source_namespace_mismatch")
    _, fresh_members = load_model_input_obligation_set(store, obligation_set_ref)
    old_ports = {member.port.port_id: member.port for member in old_members}
    fresh_ports = {member.port.port_id: member.port for member in fresh_members}
    if (
        len(old_ports) != len(old_members)
        or len(fresh_ports) != len(fresh_members)
        or old_ports != fresh_ports
        or any(port.carrier != "method_input" for port in fresh_ports.values())
    ):
        raise ValueError("registered_method_reseal_complete_port_set_required")
    old_by_port = {row.model_port_id: row for row in old_manifest.derivations}
    old_by_binding = {row.binding_id: row for row in old_facts.records}
    if len(old_by_port) != len(outputs):
        raise ValueError("registered_method_reseal_complete_port_set_required")
    for item in outputs:
        prior = old_by_port.get(item.selection.model_port_id)
        if prior is None or artifact_ref_identity_key(
            prior.profile_ref
        ) != artifact_ref_identity_key(item.selection.profile_ref):
            raise ValueError("registered_method_reseal_source_selection_mismatch")
        if _is_registered_graph_selection(store, prior):
            record = old_by_binding.get(prior.binding_id)
            if (
                type(record) is not FoundrySelectedMethodInput
                or item.selection
                != prior.model_copy(
                    update={"model_input_obligation_ref": item.selection.model_input_obligation_ref}
                )
                or item.value != record.canonical_value
                or item.projection != "scalar"
            ):
                raise ValueError("registered_method_reseal_source_selection_mismatch")
            continue
        old_proof = load_registered_derived_input_correspondence(store, prior.correspondence_ref)
        new_proof = load_registered_derived_input_correspondence(
            store, item.selection.correspondence_ref
        )

        def role_selection(
            proof: RegisteredDerivedInputCorrespondence,
        ) -> tuple[tuple[str, tuple[str, str, str, str | None]], ...]:
            return tuple(
                (
                    role.role,
                    artifact_ref_identity_key(
                        load_native_derivation_source_projection(
                            store, role.source_projection_ref
                        ).occurrence_ref
                    ),
                )
                for role in proof.roles
            )

        if role_selection(old_proof) != role_selection(new_proof):
            raise ValueError("registered_method_reseal_source_selection_mismatch")


@dataclass(frozen=True)
class RegisteredDerivedGraphModelInputRequest:
    """Materialize a selected registered graph from the exact retained leaf collection."""

    model_input_obligation_ref: ArtifactRef
    profile_ref: ArtifactRef
    collection_ref: ArtifactRef
    binding_id: str

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}", self.binding_id) is None:
            raise ValueError("registered_derived_model_input_invalid_binding_id")


def materialize_registered_derived_model_inputs(
    store: FileSystemCAS,
    *,
    base_data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    inputs: tuple[
        RegisteredDerivedModelInputRequest | RegisteredDerivedGraphModelInputRequest, ...
    ],
) -> DerivedModelInputBatchMaterialization:
    """Produce one complete candidate v3 input batch from native occurrences.

    Every requested port must belong to the same exact invocation. The complete
    required target set is checked before producing an executable manifest;
    partial native collections remain the acquisition owner's pending output.
    No caller-provided scalar, authority score, or inferred price base is used.
    """
    from polisyos.core.contracts import load_model_input_obligation_set

    selected_set, obligations = load_model_input_obligation_set(store, obligation_set_ref)
    if len(selected_set.invocation.steps) != 1:
        raise ValueError("registered_derived_model_input_temporal_profile_unsupported")
    expected = {artifact_ref_identity_key(ref) for ref in selected_set.obligation_refs}
    actual = tuple(artifact_ref_identity_key(item.model_input_obligation_ref) for item in inputs)
    if not inputs or len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("registered_derived_model_input_complete_target_set_required")
    if len({item.binding_id for item in inputs}) != len(inputs):
        raise ValueError("registered_derived_model_input_binding_id_duplicate")
    members = {
        artifact_ref_identity_key(ref): member
        for ref, member in zip(selected_set.obligation_refs, obligations, strict=True)
    }
    outputs = tuple(
        (
            _prepare_registered_graph_port_output(
                store,
                obligation_set_ref=obligation_set_ref,
                request=item,
                obligation=members[artifact_ref_identity_key(item.model_input_obligation_ref)],
            )
            if isinstance(item, RegisteredDerivedGraphModelInputRequest)
            else _prepare_registered_derived_port_output(
                store,
                obligation_set_ref=obligation_set_ref,
                request=item,
                obligation=members[artifact_ref_identity_key(item.model_input_obligation_ref)],
            )
        )
        for item in sorted(inputs, key=lambda request: request.binding_id)
    )
    return _persist_derived_input_batch(
        store,
        base_data_snapshot_ref=base_data_snapshot_ref,
        obligation_set_ref=obligation_set_ref,
        selected_set=selected_set,
        outputs=outputs,
    )


def reseal_registered_method_input_bindings(
    store: FileSystemCAS,
    *,
    source_input_bindings_ref: FoundryInputBindingsRef,
    obligation_set_ref: ArtifactRef,
    expected_invocation: ProgramGraphInputInvocation,
) -> DerivedModelInputBatchMaterialization:
    """Replay selected native sources into an exact new method-input context.

    The old binding supplies source evidence for the new obligation. Graph
    inputs preserve the exact selected graph proof while singleton inputs use
    the existing recipe producer. The result carries candidate-only input
    evidence for the new invocation.

    Args:
        store: The caller's current, access-controlled artifact store.
        source_input_bindings_ref: Exact prior method-only 1.4 source selection.
        obligation_set_ref: Complete fresh set from the canonical preflight.
        expected_invocation: Actual invocation selected by the Runtime owner.

    Returns:
        A new typed snapshot, manifest and binding with the exact prior prestate.

    Raises:
        ValueError: If either subject, source closure or bounded profile differs.
    """
    from polisyos.core.contracts import (
        FoundrySelectedMethodInput,
        RegisteredDerivedModelInputRequest,
        RegisteredMeasurementRole,
        SelectedVariableBindingRef,
        load_model_input_obligation_set,
        load_native_derivation_source_projection,
        load_registered_derived_input_context,
        load_registered_derived_input_correspondence,
        load_resolved_input_binding_manifest,
    )
    from polisyos.foundry.data_plane import (
        load_input_bindings,
        reconcile_selected_method_input_bindings,
        replay_selected_method_input_facts,
    )
    from polisyos.foundry.execute import verify_current_use_method_input_revalidation

    fresh_set = verify_current_use_method_input_revalidation(
        store,
        obligation_set_ref=obligation_set_ref,
        expected_invocation=expected_invocation,
    )
    loaded_set, fresh_obligations = load_model_input_obligation_set(store, obligation_set_ref)
    if loaded_set != fresh_set:
        raise ValueError("registered_method_reseal_set_replay_mismatch")
    source = load_input_bindings(store, source_input_bindings_ref)
    manifest_ref = source.resolved_binding_manifest_ref
    if (
        source.schema_version != "1.4"
        or manifest_ref is None
        or fresh_set.schema_version != "1.3"
        or fresh_set.purpose != "current_use_method_input_revalidation"
        or fresh_set.authority_purpose != "candidate_execution_input_revalidation_only"
        or len(expected_invocation.steps) != 1
        or fresh_set.invocation != expected_invocation
        or artifact_ref_identity_key(expected_invocation.input_bindings_ref)
        != artifact_ref_identity_key(source_input_bindings_ref)
        or artifact_ref_identity_key(fresh_set.prestate_ref)
        != artifact_ref_identity_key(source.bound_state_snapshot_ref)
    ):
        raise ValueError("registered_method_reseal_current_subject_mismatch")
    source_manifest = load_resolved_input_binding_manifest(store, manifest_ref)
    if (
        source_manifest.schema_version != "2.0"
        or source_manifest.measurements
        or not source_manifest.derivations
        or source_manifest.method_input_steps
    ):
        raise ValueError("registered_method_reseal_source_profile_unsupported")
    source_set, source_obligations = load_model_input_obligation_set(
        store, source_manifest.model_input_obligation_set_ref
    )
    if source_set.schema_version != "1.1":
        raise ValueError("registered_method_reseal_source_profile_unsupported")
    facts = replay_selected_method_input_facts(
        store,
        input_bindings_ref=source_input_bindings_ref,
        expected_invocation=source_set.invocation,
    )
    if (
        facts.bindings != source
        or any(
            artifact_ref_identity_key(getattr(source_set.invocation, name))
            != artifact_ref_identity_key(getattr(expected_invocation, name))
            for name in (
                "interface_ref",
                "program_graph_ref",
                "exec_plan_ref",
                "registry_bundle_ref",
            )
        )
        or (
            source_set.invocation.steps != expected_invocation.steps
            or source_set.invocation.parameter_override_bundle_ref is not None
            or expected_invocation.parameter_override_bundle_ref is not None
        )
    ):
        raise ValueError("registered_method_reseal_invocation_profile_mismatch")
    old_members = {
        artifact_ref_identity_key(ref): member
        for ref, member in zip(source_set.obligation_refs, source_obligations, strict=True)
    }
    fresh_members = {
        member.port.port_id: (ref, member)
        for ref, member in zip(fresh_set.obligation_refs, fresh_obligations, strict=True)
    }
    if (
        len(fresh_members) != len(fresh_obligations)
        or len(fresh_members) != len(source_manifest.derivations)
        or len(source_manifest.derivations) != len(source_obligations)
        or len(facts.records) != len(source_manifest.derivations)
        or any(member.port.carrier != "method_input" for member in fresh_obligations)
    ):
        raise ValueError("registered_method_reseal_complete_port_set_required")
    requests: list[RegisteredDerivedModelInputRequest] = []
    graph_outputs: list[_DerivedPortOutput] = []
    records_by_port = {record.port_id: record for record in facts.records}
    selected_ports = set()
    for selection in source_manifest.derivations:
        old_member = old_members.get(
            artifact_ref_identity_key(selection.model_input_obligation_ref)
        )
        selected = fresh_members.get(selection.model_port_id)
        if (
            old_member is None
            or selected is None
            or old_member.port.carrier != "method_input"
            or old_member.port != selected[1].port
            or selection.model_port_id in selected_ports
        ):
            raise ValueError("registered_method_reseal_port_subject_mismatch")
        selected_ports.add(selection.model_port_id)
        obligation_ref = SelectedVariableBindingRef.model_validate(
            selected[0].model_dump(mode="python")
        )
        if _is_registered_graph_selection(store, selection):
            record = records_by_port.get(selection.model_port_id)
            if (
                type(record) is not FoundrySelectedMethodInput
                or record.shape
                or record.binding_id != selection.binding_id
                or artifact_ref_identity_key(record.model_input_obligation_ref)
                != artifact_ref_identity_key(selection.model_input_obligation_ref)
            ):
                raise ValueError("registered_method_reseal_graph_record_mismatch")
            graph_outputs.append(
                _DerivedPortOutput(
                    selection.model_copy(update={"model_input_obligation_ref": obligation_ref}),
                    record.canonical_value,
                    "scalar",
                )
            )
            continue
        proof = load_registered_derived_input_correspondence(store, selection.correspondence_ref)
        context = load_registered_derived_input_context(store, proof.context_ref)
        if proof.schema_version != "2.0" or context.schema_version != "1.0":
            raise ValueError("registered_method_reseal_temporal_profile_unsupported")
        roles = tuple(
            RegisteredMeasurementRole(
                role=role.role,
                occurrence_ref=load_native_derivation_source_projection(
                    store, role.source_projection_ref
                ).occurrence_ref,
            )
            for role in proof.roles
        )
        if roles != context.roles:
            raise ValueError("registered_method_reseal_role_selection_mismatch")
        requests.append(
            RegisteredDerivedModelInputRequest(
                model_input_obligation_ref=obligation_ref,
                profile_ref=proof.profile_ref,
                role_occurrences=roles,
                binding_id=selection.binding_id,
            )
        )
    # Any old N7 bundle remains in the immutable source lineage. It is not
    # reissued as a planning or authority claim about this new invocation.
    if graph_outputs:
        fresh_members_by_ref = {
            artifact_ref_identity_key(ref): member for ref, member in fresh_members.values()
        }
        outputs = [
            *graph_outputs,
            *(
                _prepare_registered_derived_port_output(
                    store,
                    obligation_set_ref=obligation_set_ref,
                    request=request,
                    obligation=fresh_members_by_ref[
                        artifact_ref_identity_key(request.model_input_obligation_ref)
                    ],
                )
                for request in requests
            ),
        ]
        result = _persist_derived_input_batch(
            store,
            base_data_snapshot_ref=source.data_snapshot_ref,
            obligation_set_ref=obligation_set_ref,
            selected_set=fresh_set,
            outputs=tuple(sorted(outputs, key=lambda item: item.selection.binding_id)),
        )
    else:
        result = materialize_registered_derived_model_inputs(
            store,
            base_data_snapshot_ref=source.data_snapshot_ref,
            obligation_set_ref=obligation_set_ref,
            inputs=tuple(requests),
        )
    current = reconcile_selected_method_input_bindings(
        store,
        input_bindings_ref=result.input_bindings_ref,
        expected_invocation=expected_invocation,
        effective_step=expected_invocation.steps[0],
    )
    if artifact_ref_identity_key(
        current.bindings.bound_state_snapshot_ref
    ) != artifact_ref_identity_key(source.bound_state_snapshot_ref):
        raise ValueError("registered_method_reseal_physical_prestate_changed")
    return result


def materialize_registered_derived_model_input(
    store: FileSystemCAS,
    *,
    base_data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    model_input_obligation_ref: ArtifactRef,
    profile_ref: RegisteredDerivedInputProfileRef,
    role_occurrences: tuple[RegisteredMeasurementRole, ...],
    binding_id: str,
    derivation_bundle_ref: ArtifactRef | None = None,
) -> DerivedModelInputMaterialization:
    """Delegate a complete one-port invocation to the canonical batch producer."""
    from polisyos.core.contracts import (
        RegisteredDerivedModelInputRequest,
        SelectedVariableBindingRef,
    )

    request = RegisteredDerivedModelInputRequest(
        model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
            model_input_obligation_ref.model_dump(mode="python")
        ),
        profile_ref=profile_ref,
        role_occurrences=role_occurrences,
        binding_id=binding_id,
        derivation_bundle_ref=(
            None
            if derivation_bundle_ref is None
            else SelectedVariableBindingRef.model_validate(
                derivation_bundle_ref.model_dump(mode="python")
            )
        ),
    )
    result = materialize_registered_derived_model_inputs(
        store,
        base_data_snapshot_ref=base_data_snapshot_ref,
        obligation_set_ref=obligation_set_ref,
        inputs=(request,),
    )
    return DerivedModelInputMaterialization(
        data_snapshot_ref=result.data_snapshot_ref,
        resolved_binding_manifest_ref=result.resolved_binding_manifest_ref,
        correspondence_ref=result.correspondence_refs[0],
        input_bindings_ref=result.input_bindings_ref,
    )


def _prepare_registered_graph_port_output(
    store: FileSystemCAS,
    *,
    obligation_set_ref: ArtifactRef,
    request: RegisteredDerivedGraphModelInputRequest,
    obligation: ModelInputObligation,
) -> _DerivedPortOutput:
    """Materialize standard Core nodes and publish only the selected root port."""
    from polisyos.core.contracts import (
        RegisteredDerivedGraphCorrespondence,
        RegisteredDerivedGraphLeaf,
        RegisteredDerivedGraphOperation,
        ResolvedDerivedInput,
        SelectedVariableBindingRef,
        persist_registered_derived_graph_correspondence,
    )
    from polisyos.core.derivations import (
        materialize_derivation_dag,
        persist_candidate_source_series,
        persist_composition_recipe_artifact,
    )
    from polisyos.foundry.data_plane import prepare_registered_derivation_graph_inputs

    from .acquisition_planner import load_n7_derivation_bundle
    from .acquisition_world_growth import replay_native_derivation_input_collection

    collection = replay_native_derivation_input_collection(store, request.collection_ref).collection
    bundle = load_n7_derivation_bundle(store, collection.derivation_bundle_ref)
    if (
        bundle.schema_version != "policyos.runtime.n7_derivation_bundle.v3"
        or bundle.registered_profile_ref is None
        or collection.input_closure_status != "inputs_complete"
        or collection.pending_actions
        or any(
            artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected)
            for actual, expected in (
                (bundle.registered_profile_ref, request.profile_ref),
                (bundle.obligation_set_ref, obligation_set_ref),
                (bundle.model_input_obligation_ref, request.model_input_obligation_ref),
            )
        )
    ):
        raise ValueError("registered_derived_model_input_graph_selection_mismatch")

    graph = prepare_registered_derivation_graph_inputs(
        store,
        bundle_ref=collection.derivation_bundle_ref,
        collection_ref=request.collection_ref,
        profile_ref=request.profile_ref,
        obligation_set_ref=obligation_set_ref,
        obligation_ref=request.model_input_obligation_ref,
        obligation=obligation,
    )

    def selected(ref: ArtifactRef) -> SelectedVariableBindingRef:
        return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python"))

    sources = tuple(
        RegisteredDerivedGraphLeaf(
            node_id=node_id,
            occurrence_ref=graph.sources[node_id][0],
            source_series_ref=selected(
                persist_candidate_source_series(store, graph.sources[node_id][1])
            ),
        )
        for node_id in sorted(graph.sources)
    )
    materializations = materialize_derivation_dag(
        store,
        registry=graph.registry,
        registry_ref=graph.registry_ref,
        nodes=graph.dag_nodes({row.node_id: row.source_series_ref for row in sources}),
        root_node_id=graph.root_node_id,
        context=graph.context,
        limits=graph.limits,
    )
    profile_refs = {row.node_id: row.registered_profile_ref for row in graph.operations}
    results = dict(zip(materializations.node_ids, materializations.materializations, strict=True))
    operations = tuple(
        RegisteredDerivedGraphOperation(
            node_id=node_id,
            profile_ref=profile_refs[node_id],
            recipe_ref=selected(
                persist_composition_recipe_artifact(store, results[node_id].recipe)
            ),
            certificate_ref=selected(results[node_id].certificate_artifact_ref),
            output_ref=selected(results[node_id].derived_artifact_ref),
        )
        for node_id in sorted(results)
    )
    proof = RegisteredDerivedGraphCorrespondence(
        model_input_obligation_ref=selected(request.model_input_obligation_ref),
        model_interface_ref=selected(obligation.interface_ref),
        model_port_id=obligation.port.port_id,
        year=graph.context.years[0],
        bundle_ref=selected(collection.derivation_bundle_ref),
        collection_ref=selected(request.collection_ref),
        root_node_id=graph.root_node_id,
        sources=sources,
        operations=operations,
    )
    correspondence_ref = persist_registered_derived_graph_correspondence(store, proof)
    root = proof.root
    source_key = hashlib.sha256(request.binding_id.encode()).hexdigest()[:20]
    selection = ResolvedDerivedInput(
        binding_id=request.binding_id,
        model_input_obligation_ref=proof.model_input_obligation_ref,
        model_interface_ref=proof.model_interface_ref,
        model_port_id=proof.model_port_id,
        recipe_ref=root.recipe_ref,
        certificate_ref=root.certificate_ref,
        output_ref=root.output_ref,
        year=proof.year,
        correspondence_ref=correspondence_ref,
        profile_ref=root.profile_ref,
        source_path=f"derived_inputs.{source_key}.value",
        derivation_bundle_ref=proof.bundle_ref,
    )
    return _DerivedPortOutput(selection, materializations.root.series.points[0].value, "scalar")


def _prepare_registered_derived_port_output(
    store: FileSystemCAS,
    *,
    obligation_set_ref: ArtifactRef,
    request: RegisteredDerivedModelInputRequest,
    obligation: object,
    expected_step_scope: ModelInputStepScope | None = None,
) -> _DerivedPortOutput:
    """Replay native roles through the one Core producer and semantic predicate.

    A temporal caller supplies the scope already recomputed from one original
    full-horizon set. The immutable port envelope is never narrowed in place.
    The default branch retains the historical one-period wire contract.
    """
    from polisyos.core.contracts import (
        CandidateDerivedMeasurementRole,
        MeasurementBindingProfile,
        ModelInputObligation,
        ModelInputStepScope,
        RegisteredDerivedInputContext,
        RegisteredDerivedInputCorrespondence,
        RegisteredRoleScope,
        ReplayedCandidateDerivationRole,
        ResolvedDerivedInput,
        SelectedVariableBindingRef,
        VariableSemanticDefinition,
        evaluate_registered_derived_input_correspondence,
        load_registered_derived_input_profile,
        load_variable_representation,
        persist_native_derivation_source_projection,
        persist_registered_derived_input_context,
        persist_registered_derived_input_correspondence,
        recompute_native_derivation_source_projection,
        verify_registered_derived_family,
    )
    from polisyos.core.derivations import (
        BasisSignature,
        CandidateDerivationInput,
        CandidateSourceSeries,
        DerivationContext,
        build_composition_recipe,
        load_selected_transform_family_registry,
        materialize_composition,
        persist_candidate_source_series,
        persist_composition_recipe_artifact,
    )
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.data_forge.read_api import catalog

    if not isinstance(obligation, ModelInputObligation):
        raise TypeError("registered_derived_model_input_obligation_type_required")
    if expected_step_scope is not None and (
        type(expected_step_scope) is not ModelInputStepScope
        or expected_step_scope.port_id != obligation.port.port_id
    ):
        raise ValueError("registered_derived_model_input_step_subject_mismatch")
    target_scope = (
        obligation.port.scope if expected_step_scope is None else expected_step_scope.scope
    )

    def selected(ref: ArtifactRef) -> SelectedVariableBindingRef:
        return SelectedVariableBindingRef.model_validate(ref.model_dump(mode="python"))

    profile = load_registered_derived_input_profile(store, request.profile_ref)
    registry = load_selected_transform_family_registry(store, profile.registry_ref)
    families = tuple(
        family
        for family in registry.families
        if (family.family_id, family.method_version) == (profile.family_id, profile.method_version)
    )
    if len(families) != 1:
        raise ValueError("registered_derived_model_input_family_not_unique")
    (family,) = families
    verify_registered_derived_family(profile, family)
    expected_roles = tuple(item.role for item in profile.inputs)
    if tuple(item.role for item in request.role_occurrences) != expected_roles:
        raise ValueError("registered_derived_model_input_complete_role_set_required")
    if (
        artifact_ref_identity_key(profile.output.semantic_definition_ref)
        != artifact_ref_identity_key(obligation.port.semantic_definition_ref)
        or artifact_ref_identity_key(profile.output.representation_ref)
        != artifact_ref_identity_key(obligation.port.representation_ref)
        or artifact_ref_identity_key(profile.output.binding_profile_ref)
        != artifact_ref_identity_key(obligation.port.binding_profile_ref)
    ):
        raise ValueError("registered_derived_model_input_target_basis_mismatch")
    facts = {
        item.role: catalog.replay_selected_scoped_measurement_facts(store, item.occurrence_ref)
        for item in request.role_occurrences
    }
    context = RegisteredDerivedInputContext(
        profile_ref=request.profile_ref,
        obligation_set_ref=selected(obligation_set_ref),
        model_input_obligation_ref=request.model_input_obligation_ref,
        model_interface_ref=selected(obligation.interface_ref),
        model_port_id=obligation.port.port_id,
        registry_bundle_ref=selected(obligation.registry_bundle_ref),
        year=target_scope.period_start.year,
        output_scope=target_scope,
        roles=request.role_occurrences,
        role_scopes=tuple(
            RegisteredRoleScope(role=role, scope=facts[role][0].source_scope)
            for role in expected_roles
        ),
        **(
            {"schema_version": "1.1", "step_scope": expected_step_scope}
            if expected_step_scope is not None
            else {}
        ),
    )
    context_ref = persist_registered_derived_input_context(store, context)
    roles = []
    replayed_roles: list[ReplayedCandidateDerivationRole] = []
    input_refs = {}
    for role_basis in profile.inputs:
        role = role_basis.role
        occurrence, replayed, source_selection = facts[role]
        definition = validate_core_model_json_artifact(
            VariableSemanticDefinition, store, role_basis.basis.semantic_definition_ref
        )
        representation = load_variable_representation(store, role_basis.basis.representation_ref)
        binding_profile = validate_core_model_json_artifact(
            MeasurementBindingProfile, store, role_basis.basis.binding_profile_ref
        )
        if any(not store.verify(ref).ok for ref in definition.definition_evidence_refs):
            raise ValueError("registered_derived_model_input_definition_evidence_unavailable")
        occurrence_ref = next(
            item.occurrence_ref for item in request.role_occurrences if item.role == role
        )
        projection = recompute_native_derivation_source_projection(
            profile_ref=request.profile_ref,
            profile=profile,
            context_ref=context_ref,
            context=context,
            role=role,
            occurrence_ref=occurrence_ref,
            occurrence=occurrence,
            replayed_occurrence=replayed,
            source_selection=source_selection,
            definition=definition,
            representation=representation,
            binding_profile=binding_profile,
        )
        projection_ref = persist_native_derivation_source_projection(store, projection)
        arithmetic_basis = BasisSignature(
            quantity_kind=projection.quantity_kind, unit=projection.unit_id
        )
        expected_basis = next(item.basis for item in family.input_specs if item.role == role)
        if arithmetic_basis != expected_basis:
            raise ValueError("registered_derived_model_input_basis_axes_unsupported")
        lineage = {
            artifact_ref_identity_key(ref): ref
            for ref in (
                projection_ref,
                occurrence.source_receipt_ref,
                occurrence.source_passport_ref,
                occurrence.source_boundary_candidate_ref,
                occurrence.source_record_ref,
                role_basis.basis.semantic_definition_ref,
                role_basis.basis.representation_ref,
                role_basis.basis.binding_profile_ref,
            )
        }
        source = CandidateSourceSeries(
            variable_id=projection.source_variable_id,
            basis=arithmetic_basis,
            points=({"year": context.year, "value": projection.canonical_value},),
            source_occurrence_ref=occurrence_ref,
            source_ref=occurrence.source_record_ref,
            context_ref=context_ref,
            scope_ref=context_ref,
            units_profile="selected_registry_bundle",
            registry_bundle_ref=obligation.registry_bundle_ref,
            lineage_refs=tuple(lineage[key] for key in sorted(lineage)),
        )
        source_ref = persist_candidate_source_series(store, source)
        role_selection = CandidateDerivedMeasurementRole(
            role=role,
            source_series_ref=selected(source_ref),
            source_projection_ref=projection_ref,
        )
        roles.append(role_selection)
        if expected_step_scope is not None:
            replayed_roles.append(
                ReplayedCandidateDerivationRole(
                    selection=role_selection,
                    projection=projection,
                    occurrence=occurrence,
                    replayed_occurrence=replayed,
                    source_selection=source_selection,
                    definition=definition,
                    representation=representation,
                    binding_profile=binding_profile,
                    series=source,
                )
            )
        input_refs[role] = CandidateDerivationInput(artifact_ref=source_ref)
    target_definition = validate_core_model_json_artifact(
        VariableSemanticDefinition, store, obligation.port.semantic_definition_ref
    )
    target_representation = load_variable_representation(store, obligation.port.representation_ref)
    recipe = build_composition_recipe(
        store,
        registry=registry,
        registry_ref=profile.registry_ref,
        input_refs=input_refs,
        context=DerivationContext(
            context_ref=context_ref,
            scope_ref=context_ref,
            years=(context.year,),
            units_profile="selected_registry_bundle",
            registry_bundle_ref=obligation.registry_bundle_ref,
        ),
        output_variable_id=f"{target_definition.namespace}.{target_definition.stable_id}",
        output_basis=BasisSignature(
            quantity_kind=target_representation.quantity_kind, unit=target_representation.unit_id
        ),
        family_id=profile.family_id,
        method_version=profile.method_version,
    )
    recipe_ref = persist_composition_recipe_artifact(store, recipe)
    produced = materialize_composition(store, recipe)
    correspondence = RegisteredDerivedInputCorrespondence(
        profile_ref=request.profile_ref,
        context_ref=context_ref,
        model_input_obligation_ref=request.model_input_obligation_ref,
        model_interface_ref=selected(obligation.interface_ref),
        model_port_id=obligation.port.port_id,
        recipe_ref=selected(recipe_ref),
        certificate_ref=selected(produced.certificate_artifact_ref),
        output_ref=selected(produced.derived_artifact_ref),
        year=context.year,
        roles=tuple(roles),
        **(
            {"schema_version": "2.1", "step_scope": expected_step_scope}
            if expected_step_scope is not None
            else {}
        ),
    )
    if expected_step_scope is not None:
        if any(not store.verify(ref).ok for ref in target_definition.definition_evidence_refs):
            raise ValueError("registered_derived_model_input_definition_evidence_unavailable")
        result = evaluate_registered_derived_input_correspondence(
            correspondence=correspondence,
            profile=profile,
            context=context,
            obligation_ref=request.model_input_obligation_ref,
            obligation=obligation,
            target_definition=target_definition,
            target_representation=target_representation,
            binding_profile=validate_core_model_json_artifact(
                MeasurementBindingProfile, store, obligation.port.binding_profile_ref
            ),
            units_registry=load_registry_bundle_content(
                store, obligation.registry_bundle_ref
            ).units_registry,
            recipe=recipe,
            series=produced.series,
            roles=tuple(replayed_roles),
            expected_step_scope=expected_step_scope,
        )
        if result.status != "candidate" or result.value != produced.series.points[0].value:
            raise ValueError(
                "registered_derived_model_input_semantic_refused:"
                + ",".join(result.refusal_codes or ("output_value_mismatch",))
            )
    correspondence_ref = persist_registered_derived_input_correspondence(store, correspondence)
    source_key = hashlib.sha256(request.binding_id.encode()).hexdigest()[:20]
    selection = ResolvedDerivedInput(
        binding_id=request.binding_id,
        model_input_obligation_ref=request.model_input_obligation_ref,
        model_interface_ref=selected(obligation.interface_ref),
        model_port_id=obligation.port.port_id,
        recipe_ref=selected(recipe_ref),
        certificate_ref=selected(produced.certificate_artifact_ref),
        output_ref=selected(produced.derived_artifact_ref),
        year=context.year,
        correspondence_ref=correspondence_ref,
        profile_ref=request.profile_ref,
        source_path=f"derived_inputs.{source_key}.value",
        derivation_bundle_ref=request.derivation_bundle_ref,
    )
    return _DerivedPortOutput(selection, produced.series.points[0].value, "scalar")


__all__ = [
    "DerivedModelInputBatchMaterialization",
    "DerivedModelInputMaterialization",
    "ModelInputPortRoute",
    "ModelInputRoutingReport",
    "ModelInputRoutingResult",
    "ModelInputRoutingUseDecision",
    "RegisteredDerivedGraphModelInputRequest",
    "materialize_derived_model_input",
    "materialize_registered_derived_model_input",
    "materialize_registered_derived_model_inputs",
    "materialize_routed_model_input_observation",
    "persist_current_model_input_routing_use_decision",
    "plan_selected_model_input_routing",
    "read_model_input_routing_report",
    "read_model_input_routing_use_decision",
    "verify_model_input_routing_report",
    "verify_model_input_routing_use_decision_current",
]
