from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.authorization import (
    BoundActionPermissionVerification,
    RouteAuthorizationRequirement,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import BindingAuthority
from polisyos.runtime.http.routes.acquisitions import (
    _MUTATION_AUTHZ,
    _MUTATION_STEP_UP,
    router,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
    AcquisitionCustodyRecoveryRequest,
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    require_acquisition_bound_permission,
)
from tests.integration.core_runtime import test_acquisition_admission_bundle as fixture

_PHASE_RECEIPT_KIND = "runtime_quality.acquisition_route_phase_receipt"


def _phase_receipt_ref_payload(
    *,
    artifact_number: int = 7,
    profile_sha256: str | None = "sha256:" + "8" * 64,
    kind: str = _PHASE_RECEIPT_KIND,
) -> dict[str, str]:
    """Build a selected phase-receipt locator, optionally without its manifest profile."""

    payload = {
        "artifact_id": f"sha256:{artifact_number:064x}",
        "kind": kind,
        "media_type": "application/json",
    }
    if profile_sha256 is not None:
        payload["manifest_profile_sha256"] = profile_sha256
    return payload


def _request_with_custody_recovery(
    *,
    failed_attempt: int = 1,
    artifact_number: int = 7,
    profile_sha256: str = "sha256:" + "8" * 64,
) -> AcquisitionRouteMutationRequest:
    """Return a typed acquisition request carrying one selected failed attempt."""

    payload = fixture.ACQUISITION_REQUEST.model_dump(mode="python")
    payload["custody_recovery"] = AcquisitionCustodyRecoveryRequest(
        failed_attempt=failed_attempt,
        head_ref=ArtifactRef.model_validate(
            _phase_receipt_ref_payload(
                artifact_number=artifact_number,
                profile_sha256=profile_sha256,
            )
        ),
    )
    return AcquisitionRouteMutationRequest.model_validate(payload)


def _bound_permission_for_request(
    request: AcquisitionRouteMutationRequest,
    *,
    requirement: RouteAuthorizationRequirement | None = None,
) -> tuple[BoundActionPermissionVerification, str]:
    """Build the fixture's sealed proof for exact serialized request bytes and selectors."""

    selected_requirement = requirement or fixture.ACQUISITION_ROUTE_REQUIREMENT
    selectors = fixture._request_composite_selectors(request)
    request_body = request.model_dump_json().encode("utf-8")
    body_sha256 = f"sha256:{sha256(request_body).hexdigest()}"
    digest_payload = {
        "binding_version": "runtime.authorization.resource.v1",
        "permission": selected_requirement.permission.value,
        "resource_kind": selected_requirement.resource_binding.resource_kind,
        "authority": BindingAuthority.REQUEST_BOUND.value,
        "tenant_id": None,
        "body_sha256": body_sha256,
        "query_sha256": fixture.EMPTY_QUERY_SHA256,
        "selectors": selectors,
        "resolved_context_sha256": None,
    }
    canonical_digest_payload = fixture._canonical_selector(digest_payload).encode("utf-8")
    resource_digest = f"sha256:{sha256(canonical_digest_payload).hexdigest()}"
    return (
        fixture._proof(
            resource_digest=resource_digest,
            requirement=selected_requirement,
            canonical_selectors=selectors,
            body_sha256=body_sha256,
        ),
        resource_digest,
    )


def _route_dependency_calls(operation_id: str) -> tuple[object, ...]:
    """Return direct FastAPI dependencies declared on one acquisition endpoint."""

    route = next(
        route for route in router.routes if getattr(route, "operation_id", None) == operation_id
    )
    return tuple(dependency.call for dependency in route.dependant.dependencies)


def test_legacy_request_keeps_wire_and_resource_digest() -> None:
    """An absent recovery selector preserves the pre-extension wire and PA2 digest."""

    request = fixture.ACQUISITION_REQUEST
    assert "custody_recovery" not in request.model_dump(mode="json")
    assert b'"custody_recovery"' not in request.model_dump_json().encode("utf-8")

    current_binding = fixture.ACQUISITION_ROUTE_REQUIREMENT.resource_binding
    legacy_selector_fields = tuple(
        field for field in current_binding.selector_fields if field != "custody_recovery"
    )
    legacy_requirement = replace(
        fixture.ACQUISITION_ROUTE_REQUIREMENT,
        resource_binding=replace(
            current_binding,
            selector_fields=legacy_selector_fields,
            omit_absent_selector_fields=(),
            policy_digest_selector_fields=(),
        ),
    )
    selectors = fixture._request_composite_selectors(
        request,
        selector_fields=legacy_selector_fields,
    )
    proof = fixture._proof(
        resource_digest=fixture.RESOURCE_DIGEST,
        requirement=legacy_requirement,
        canonical_selectors=selectors,
        body_sha256=fixture.REQUEST_BODY_SHA256,
    )

    assert dict(selectors)["human_decision_record_ref"] == '{"present":false}'
    assert require_acquisition_bound_permission(proof, request) == fixture.RESOURCE_DIGEST


def test_custody_recovery_descriptor_binds_attempt_and_full_head_profile() -> None:
    """The producer-side verifier recomputes a digest over each complete selector."""

    first = _request_with_custody_recovery(
        failed_attempt=1,
        artifact_number=11,
        profile_sha256="sha256:" + "a" * 64,
    )
    other_profile = _request_with_custody_recovery(
        failed_attempt=1,
        artifact_number=11,
        profile_sha256="sha256:" + "b" * 64,
    )
    other_attempt = _request_with_custody_recovery(
        failed_attempt=2,
        artifact_number=11,
        profile_sha256="sha256:" + "a" * 64,
    )

    digests: list[str] = []
    for request in (first, other_profile, other_attempt):
        proof, expected_digest = _bound_permission_for_request(request)
        assert require_acquisition_bound_permission(proof, request) == expected_digest
        digests.append(expected_digest)

    assert len(set(digests)) == 3
    custody_selector = json.loads(
        dict(fixture._request_composite_selectors(first))["custody_recovery"]
    )
    assert custody_selector["failed_attempt"] == 1
    assert custody_selector["head_ref"]["manifest_profile_sha256"] == "sha256:" + "a" * 64


@pytest.mark.parametrize(
    "custody_recovery",
    [
        pytest.param(
            {
                "failed_attempt": 1,
                "head_ref": _phase_receipt_ref_payload(),
                "unrecognized": "value",
            },
            id="unknown-field",
        ),
        pytest.param(
            {
                "failed_attempt": 1,
                "head_ref": _phase_receipt_ref_payload(profile_sha256=None),
            },
            id="profileless-head",
        ),
        pytest.param(
            {
                "failed_attempt": 1,
                "head_ref": _phase_receipt_ref_payload(kind="runtime_quality.other_receipt"),
            },
            id="wrong-head-kind",
        ),
        pytest.param(
            {
                "failed_attempt": True,
                "head_ref": _phase_receipt_ref_payload(),
            },
            id="boolean-attempt",
        ),
    ],
)
def test_custody_recovery_rejects_unbound_or_invalid_descriptors(
    custody_recovery: dict[str, object],
) -> None:
    """Unknown fields and incomplete or wrongly typed locators fail DTO validation."""

    payload = fixture.ACQUISITION_REQUEST.model_dump(mode="python")
    payload["custody_recovery"] = custody_recovery
    with pytest.raises(ValidationError):
        AcquisitionRouteMutationRequest.model_validate(payload)


def test_admission_refuses_custody_recovery_with_non_acquisition_permission() -> None:
    """A sealed request proof for another action cannot authorize acquisition admission."""

    request = _request_with_custody_recovery()
    other_requirement = replace(
        fixture.ACQUISITION_ROUTE_REQUIREMENT,
        permission=RuntimePermission.RUNS_REVIEW,
    )
    proof, _digest = _bound_permission_for_request(request, requirement=other_requirement)

    with pytest.raises(AcquisitionAdmissionBundleBlocked):
        require_acquisition_bound_permission(proof, request)


def test_decision_request_rejects_custody_recovery_before_route_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recovery descriptors are scoped to execute and cannot be persisted as new decisions."""

    request = _request_with_custody_recovery()
    proof, _digest = _bound_permission_for_request(request)
    service = object.__new__(AcquisitionActionService)

    def forbid_admission(_service: AcquisitionActionService, **_kwargs: object) -> None:
        raise AssertionError("decision request reached acquisition admission")

    monkeypatch.setattr(AcquisitionActionService, "_validated_mutation", forbid_admission)
    with pytest.raises(AcquisitionActionServiceError) as blocked:
        service.request_decision(
            tenant_id="tenant-custody-recovery",
            cell_id="cell-custody-recovery",
            run_id="run-custody-recovery",
            route_id="route-custody-recovery",
            request=request,
            bound_permission=proof,
        )
    assert blocked.value.code.startswith("acquisition_custody_recovery_")


def test_acquisition_decision_and_execute_keep_permission_and_step_up() -> None:
    """The optional selector retains the existing protected mutation dependencies."""

    assert _MUTATION_AUTHZ.requirement.permission is RuntimePermission.EVIDENCE_ACQUIRE
    for operation_id in (
        "request_run_acquisition_decision",
        "execute_run_acquisition_route",
    ):
        dependencies = _route_dependency_calls(operation_id)
        assert _MUTATION_AUTHZ in dependencies
        assert _MUTATION_STEP_UP in dependencies
