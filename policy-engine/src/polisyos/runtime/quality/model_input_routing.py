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
    from pathlib import Path

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


__all__ = [
    "ModelInputPortRoute",
    "ModelInputRoutingReport",
    "ModelInputRoutingResult",
    "ModelInputRoutingUseDecision",
    "materialize_routed_model_input_observation",
    "persist_current_model_input_routing_use_decision",
    "plan_selected_model_input_routing",
    "read_model_input_routing_report",
    "read_model_input_routing_use_decision",
    "verify_model_input_routing_report",
    "verify_model_input_routing_use_decision_current",
]
