"""Red-first HTTP boundary test for the DS17 confidence-ledger risk-spend route."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

try:  # pragma: no cover - optional dependency guard
    from fastapi.routing import APIRoute
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.routes.governed_projections import (
    _get_confidence_ledger_risk_spend_projection_service,
)
from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    AvailableConfidenceLedgerRiskSpendPacket,
    ConfidenceLedgerRiskSpendPacket,
)
from polisyos.runtime.http.services.confidence_ledger_risk_spend_projection import (
    ConfidenceLedgerRiskSpendProjectionService,
)
from polisyos.runtime.http.services.governed_projections import (
    GovernedProjectionService,
    GuardedProjectionId,
)
from tests.unit.runtime.http.test_confidence_ledger_risk_spend_projection import (
    coherent_over_spend_artifact,
)
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)

_PATH = "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
_DYNAMIC_PATH = "/api/v1/exports/governed-projections/{projection_id}"
_SOURCE = "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json"


def _secure_client(runtime_api_env, *, role: PolicyOSRole, suffix: str):
    """Create one tenant-bound caller for the protected-operation assertion."""
    bearer = _fixture_bearer(suffix)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-{suffix}",
            roles=frozenset({role}),
        ),
    )
    return client, {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }


def test_confidence_ledger_risk_spend_operation_is_typed_and_protected(
    runtime_api_env,
) -> None:
    """Require the static reviewer operation; C00 observes its dynamic-route 422 red."""
    analyst, analyst_headers = _secure_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        suffix="ds17-analyst",
    )
    viewer, viewer_headers = _secure_client(
        runtime_api_env,
        role=PolicyOSRole.VIEWER,
        suffix="ds17-viewer",
    )
    response = analyst.get(_PATH, headers=analyst_headers)

    assert response.status_code == 200, (
        "DS17 C02 missing: the typed review-protected confidence-ledger risk-spend "
        f"operation is absent at {_PATH}; received HTTP {response.status_code}: {response.text}"
    )

    routes = [route for route in analyst.app.routes if isinstance(route, APIRoute)]
    static_index, static_route = next(
        (index, route)
        for index, route in enumerate(routes)
        if route.path == _PATH and "GET" in route.methods
    )
    dynamic_index, _ = next(
        (index, route)
        for index, route in enumerate(routes)
        if route.path == _DYNAMIC_PATH and "GET" in route.methods
    )
    dependency = get_route_action_permission_dependency(static_route)
    assert static_index < dynamic_index
    assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
    assert dependency.requirement.resource_binding.source is ResourceBindingSource.TENANT_COLLECTION

    payload = response.json()
    adapter = TypeAdapter(static_route.response_model)
    typed_payload = adapter.validate_json(response.content, strict=True)
    assert not isinstance(typed_payload, dict)
    assert typed_payload.model_dump(mode="json") == payload
    with pytest.raises(ValidationError):
        adapter.validate_json(
            json.dumps({**payload, "unexpected": "DS17 typed-contract probe"}),
            strict=True,
        )
    assert payload["projection_id"] == "confidence-ledger-risk-spend"
    assert payload["intended_audience"] == "REVIEWER"
    assert payload["intended_audiences"] == ["REVIEWER", "EXPERT", "MACHINE"]
    assert "PUBLIC" not in payload["intended_audiences"]
    assert payload["availability"] == "available"

    replay = analyst.get(payload["replay_address"], headers=analyst_headers)
    assert replay.status_code == 200
    assert replay.json()["projection_hash"] == payload["projection_hash"]
    stale = analyst.get(
        _PATH,
        headers=analyst_headers,
        params={"projection_hash": "sha256:" + "0" * 64},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "governed_projection_replay_pin_mismatch"
    assert stale.json()["field"] == "projection_hash"

    denied = viewer.get(_PATH, headers=viewer_headers)
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"


def test_confidence_ledger_risk_spend_openapi_is_strict_measured_negative(
    runtime_api_env,
) -> None:
    schema = runtime_api_env["app"].openapi()
    operation = schema["paths"][_PATH]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    example = operation["responses"]["200"]["content"]["application/json"][
        "examples"
    ]["default"]["value"]
    parsed = TypeAdapter(ConfidenceLedgerRiskSpendPacket).validate_json(
        json.dumps(example),
        strict=True,
    )

    assert operation["operationId"] == "get_confidence_ledger_risk_spend_projection"
    assert response_schema["discriminator"]["propertyName"] == "availability"
    assert set(response_schema["discriminator"]["mapping"]) == {
        "available",
        "source_blocked",
        "artifact_missing",
        "invalid_source",
    }
    assert isinstance(parsed, AvailableConfidenceLedgerRiskSpendPacket)
    assert len(parsed.payload.refusal_instance_refs) == 1
    assert len(parsed.payload.acquisition_instance_refs) == 2
    assert len(parsed.payload.obligation_class_risk_spend) == 15
    assert len(parsed.payload.instrument_definitions) == 13
    assert parsed.payload.positive_register.population_count == 0
    assert parsed.payload.total_spend.amount.fraction == 0
    assert parsed.payload.coverage_assessment.value == "open_world_unresolved"
    assert parsed.payload.status == "not_promoted"


def test_nested_outside_owner_issue_fails_closed_through_worker_service_and_api(
    runtime_api_env,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / _SOURCE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        json.dumps(coherent_over_spend_artifact(0), sort_keys=True),
        encoding="utf-8",
    )
    hook_root = tmp_path / "worker-hook"
    hook_root.mkdir()
    (hook_root / "sitecustomize.py").write_text(
        "\n".join(
            (
                "from tools.quality.validation import "
                "check_layer3_gy_confidence_ledger as owner",
                "original = owner.validate_payload",
                "def validate_payload(payload):",
                "    result = original(payload)",
                "    issues = list(result.get('issues') or [])",
                "    if issues:",
                "        first = dict(issues[0])",
                "        first['detail'] = {'code': 'outside_diagnostic'}",
                "        result = {**result, 'issues': [first, *issues[1:]]}",
                "    return result",
                "owner.validate_payload = validate_payload",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(hook_root))
    source_service = GovernedProjectionService(tmp_path)
    resolution = source_service.resolve_guarded_source(
        GuardedProjectionId.CONFIDENCE_LEDGER_RISK_SPEND
    )
    assert resolution.validation is not None
    assert "outside_diagnostic" in resolution.validation.issue_codes
    service = ConfidenceLedgerRiskSpendProjectionService(
        tmp_path,
        source_service=source_service,
    )
    analyst, headers = _secure_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        suffix="ds17-nested-owner-issue",
    )
    analyst.app.dependency_overrides[
        _get_confidence_ledger_risk_spend_projection_service
    ] = lambda: service
    try:
        response = analyst.get(_PATH, headers=headers)
    finally:
        analyst.app.dependency_overrides.pop(
            _get_confidence_ledger_risk_spend_projection_service,
            None,
        )

    assert response.status_code == 200, response.text
    assert response.json()["availability"] == "invalid_source"
