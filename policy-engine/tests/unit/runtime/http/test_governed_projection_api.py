from __future__ import annotations

from importlib.util import find_spec

import pytest
from pydantic import ValidationError

if find_spec("fastapi") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("fastapi is not installed", allow_module_level=True)

from fastapi.routing import APIRoute

from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.routes.governed_projections import (
    _get_cycle_board_projection_service,
    _get_projection_service,
)
from polisyos.runtime.http.services.governed_projections import (
    ChannelRegistryEntry,
    ProjectionId,
)
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)

_CYCLE_BOARD_PATH = "/api/v1/exports/governed-projections/depth-n-cycle-board"
_DYNAMIC_PROJECTION_PATH = "/api/v1/exports/governed-projections/{projection_id}"


class _FrozenCycleBoardService:
    """Return one frozen raw observation through the HTTP composition seam."""

    def __init__(self, raw_packet) -> None:
        self.raw_packet = raw_packet
        self.calls: list[dict[str, object]] = []

    def get(self, **pins):
        self.calls.append(dict(pins))
        assert pins.pop("replay_target", None) == "raw_v1"
        assert set(pins) == {
            "artifact_content_hash",
            "projection_hash",
            "source_dependency_hash",
            "source_as_of",
        }
        assert pins["artifact_content_hash"] == self.raw_packet.source.artifact_content_hash
        assert pins["projection_hash"] == self.raw_packet.projection_hash
        assert pins["source_dependency_hash"] == self.raw_packet.source_dependency_hash
        assert pins["source_as_of"] == self.raw_packet.as_of
        return self.raw_packet


def _cycle_board_secure_client(runtime_api_env, *, role: PolicyOSRole, suffix: str):
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


def test_governed_projection_catalog_is_typed_and_complete(runtime_api_env) -> None:
    response = runtime_api_env["client"].get("/api/v1/exports/governed-projections")

    assert response.status_code == 200
    payload = response.json()
    assert {entry["projection_id"] for entry in payload["projections"]} == {
        projection_id.value for projection_id in ProjectionId
    }
    assert all(entry["intended_audience"] for entry in payload["projections"])
    assert all(entry["stable_address"] for entry in payload["projections"])
    assert all(entry["owner_validator_id"] for entry in payload["projections"])
    assert all(entry["owner_validator_version"] for entry in payload["projections"])


def test_governed_projection_endpoint_uses_runtime_api_env(runtime_api_env) -> None:
    response = runtime_api_env["client"].get("/api/v1/exports/governed-projections/engine-census")

    assert response.status_code == 200
    payload = response.json()
    assert payload["projection_id"] == "engine-census"
    assert payload["availability"] == "available"
    assert payload["source"]["artifact_content_hash"].startswith("sha256:")
    assert payload["source"]["validation"]["status"] == "passed"
    assert payload["source_dependency_hash"].startswith("sha256:")
    assert payload["source"]["validation"]["bound_dependency_count"] > 0
    assert payload["projection_hash"].startswith("sha256:")
    assert payload["as_of"]
    assert payload["freshness"]["observed_at"]


def test_governed_projection_endpoint_enforces_replay_time_pin(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    path = "/api/v1/exports/governed-projections/engine-census"
    current = client.get(path).json()

    replay = client.get(current["replay_address"])
    stale = client.get(
        path,
        params={
            "artifact_content_hash": current["source"]["artifact_content_hash"],
            "projection_hash": current["projection_hash"],
            "source_dependency_hash": current["source_dependency_hash"],
            "source_as_of": "2000-01-01T00:00:00Z",
        },
    )

    assert replay.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "governed_projection_replay_pin_mismatch"
    assert stale.json()["field"] == "source_as_of"


def test_governed_projection_endpoint_enforces_dependency_replay_pin(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].get(
        "/api/v1/exports/governed-projections/engine-census",
        params={"source_dependency_hash": f"sha256:{'0' * 64}"},
    )

    assert response.status_code == 409
    assert response.json()["field"] == "source_dependency_hash"


def test_governed_projection_endpoint_preserves_existing_auth_defaults(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/exports/governed-projections/engine-census")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["intended_audience"] == "EXPERT"


def test_cycle_board_static_export_is_review_guarded_and_shadows_raw_dynamic(
    runtime_api_env,
) -> None:
    analyst, analyst_headers = _cycle_board_secure_client(
        runtime_api_env,
        role=PolicyOSRole.ANALYST,
        suffix="cycle-board-analyst",
    )
    viewer, viewer_headers = _cycle_board_secure_client(
        runtime_api_env,
        role=PolicyOSRole.VIEWER,
        suffix="cycle-board-viewer",
    )
    routes = [route for route in analyst.app.routes if isinstance(route, APIRoute)]
    static_routes = [
        (index, route)
        for index, route in enumerate(routes)
        if route.path == _CYCLE_BOARD_PATH and "GET" in route.methods
    ]
    dynamic_routes = [
        (index, route)
        for index, route in enumerate(routes)
        if route.path == _DYNAMIC_PROJECTION_PATH and "GET" in route.methods
    ]

    assert len(static_routes) == 1
    assert len(dynamic_routes) == 1
    static_index, static_route = static_routes[0]
    dynamic_index, _ = dynamic_routes[0]
    dependency = get_route_action_permission_dependency(static_route)

    assert static_index < dynamic_index
    assert static_route.operation_id == "get_depth_n_cycle_board_projection"
    assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
    binding = dependency.requirement.resource_binding
    assert binding.source is ResourceBindingSource.TENANT_COLLECTION
    assert binding.resource_kind == "runtime.governed_projection.depth_n_cycle_board"

    admitted = analyst.get(_CYCLE_BOARD_PATH, headers=analyst_headers)
    assert admitted.status_code == 200, admitted.text
    assert admitted.json()["projection_rule_version"] == ("policyos.runtime.depth_n_cycle_board.v2")

    raw_packet = _get_projection_service().get(ProjectionId.DEPTH_N_CYCLE_BOARD)
    assert raw_packet.availability.value == "available"
    complete_v2 = {
        "replay_target": "composed_v2",
        "projection_rule_version": admitted.json()["projection_rule_version"],
        "composition_manifest_hash": admitted.json()["composition_manifest_hash"],
        "projection_hash": admitted.json()["projection_hash"],
        "source_dependency_hash": admitted.json()["source_dependency_hash"],
    }
    conflict_queries = (
        (
            "wrong-complete-raw",
            {
                "replay_target": "raw_v1",
                "artifact_content_hash": raw_packet.source.artifact_content_hash,
                "projection_hash": f"sha256:{'0' * 64}",
                "source_dependency_hash": raw_packet.source_dependency_hash,
                "source_as_of": raw_packet.as_of.isoformat(),
            },
        ),
        ("untargeted-pin", {"projection_hash": admitted.json()["projection_hash"]}),
        (
            "partial-raw",
            {
                "replay_target": "raw_v1",
                "artifact_content_hash": raw_packet.source.artifact_content_hash,
            },
        ),
        (
            "partial-v2",
            {key: value for key, value in complete_v2.items() if key != "source_dependency_hash"},
        ),
        (
            "mixed-generations",
            {**complete_v2, "artifact_content_hash": raw_packet.source.artifact_content_hash},
        ),
    )
    for case_id, query in conflict_queries:
        response = analyst.get(_CYCLE_BOARD_PATH, headers=analyst_headers, params=query)
        assert response.status_code == 409, f"{case_id}: {response.text}"
        assert response.json()["code"] == "cycle_board_replay_conflict"

    frozen_service = _FrozenCycleBoardService(raw_packet)
    for client in (analyst, viewer):
        client.app.dependency_overrides[_get_cycle_board_projection_service] = lambda: (
            frozen_service
        )

    raw_replay = analyst.get(
        _CYCLE_BOARD_PATH,
        headers=analyst_headers,
        params={
            "replay_target": "raw_v1",
            "artifact_content_hash": raw_packet.source.artifact_content_hash,
            "projection_hash": raw_packet.projection_hash,
            "source_dependency_hash": raw_packet.source_dependency_hash,
            "source_as_of": raw_packet.as_of.isoformat(),
        },
    )
    assert raw_replay.status_code == 200, raw_replay.text
    assert raw_replay.content == raw_packet.model_dump_json().encode()
    expected_call = {
        "replay_target": "raw_v1",
        "artifact_content_hash": raw_packet.source.artifact_content_hash,
        "projection_hash": raw_packet.projection_hash,
        "source_dependency_hash": raw_packet.source_dependency_hash,
        "source_as_of": raw_packet.as_of,
    }
    assert frozen_service.calls == [expected_call]
    calls_after_authorized_raw = tuple(frozen_service.calls)

    denied = viewer.get(_CYCLE_BOARD_PATH, headers=viewer_headers)
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"

    denied_raw_replay = viewer.get(
        _CYCLE_BOARD_PATH,
        headers=viewer_headers,
        params={
            "replay_target": "raw_v1",
            "artifact_content_hash": f"sha256:{'0' * 64}",
            "projection_hash": f"sha256:{'0' * 64}",
            "source_dependency_hash": f"sha256:{'0' * 64}",
            "source_as_of": "2000-01-01T00:00:00Z",
        },
    )
    assert denied_raw_replay.status_code == 403
    assert denied_raw_replay.json()["code"] == "action_permission_denied"
    assert tuple(frozen_service.calls) == calls_after_authorized_raw


def test_governed_projection_openapi_encodes_typed_states_and_payloads(
    runtime_api_env,
) -> None:
    schema = runtime_api_env["app"].openapi()
    response_schema = schema["paths"]["/api/v1/exports/governed-projections/{projection_id}"][
        "get"
    ]["responses"]["200"]["content"]["application/json"]["schema"]

    assert response_schema["discriminator"]["propertyName"] == "availability"
    components = schema["components"]["schemas"]
    state_refs = {choice["$ref"].rsplit("/", maxsplit=1)[-1] for choice in response_schema["oneOf"]}
    assert state_refs == {
        "AvailableGovernedProjectionPacket",
        "ArtifactMissingGovernedProjectionPacket",
        "InvalidGovernedProjectionPacket",
    }
    available = components["AvailableGovernedProjectionPacket"]
    payload_choices = available["properties"]["payload"]["anyOf"]
    assert len(payload_choices) == len(ProjectionId)
    for choice in payload_choices:
        payload_ref = choice["$ref"]
        payload_component = components[payload_ref.rsplit("/", maxsplit=1)[-1]]
        assert payload_component["additionalProperties"] is False
        assert payload_component["required"]


def test_channel_registry_covers_every_active_hidden_runtime_channel(
    runtime_api_env,
) -> None:
    app = runtime_api_env["app"]
    hidden_http_paths = {
        route.path
        for route in app.routes
        if getattr(route, "include_in_schema", True) is False and route.path.startswith("/api/v1/")
    }
    websocket_paths = {
        route.path
        for route in app.routes
        if type(route).__name__ == "APIWebSocketRoute" and route.path.startswith("/api/v1/")
    }
    response = runtime_api_env["client"].get("/api/v1/exports/channel-registry")

    assert response.status_code == 200
    entries = response.json()["channels"]
    registered_paths = {entry["path_template"] for entry in entries}
    assert hidden_http_paths | websocket_paths == registered_paths
    assert all(entry["auth_class"] for entry in entries)
    assert all(entry["consumers"] for entry in entries)
    assert all(entry["producer_contract_ref"] for entry in entries)
    assert {entry["capability_state"] for entry in entries} == {"verification_missing"}
    sse_entries = [entry for entry in entries if entry["transport"] == "sse"]
    assert {entry["message_contract"] for entry in sse_entries} == {
        "policyos.runtime.runs_channel_data_event.v2"
    }
    assert {entry["producer_contract_ref"] for entry in sse_entries} == {
        "polisyos.runtime.http.services.channel_contracts:RunsChannelDataEvent"
    }


def test_channel_registry_rejects_unknown_channel_fields() -> None:
    with pytest.raises(ValidationError):
        ChannelRegistryEntry.model_validate(
            {
                "registry_id": "unexpected",
                "path_template": "/api/v1/unexpected/live",
                "transport": "sse",
                "message_contract": "unexpected.v1",
                "producer_contract_ref": "test:UnexpectedContract",
                "auth_class": "runtime_tenant",
                "consumers": ["test"],
                "owner": "runtime-http",
                "include_in_schema": False,
                "status": "active",
                "unexpected": "must be forbidden",
            }
        )
