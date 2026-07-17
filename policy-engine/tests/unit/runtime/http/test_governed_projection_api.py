from __future__ import annotations

from importlib.util import find_spec

import pytest
from pydantic import ValidationError

if find_spec("fastapi") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.runtime.http.services.governed_projections import (
    ChannelRegistryEntry,
    ProjectionId,
)


def test_governed_projection_catalog_is_typed_and_complete(runtime_api_env) -> None:
    response = runtime_api_env["client"].get("/api/v1/exports/governed-projections")

    assert response.status_code == 200
    payload = response.json()
    assert {entry["projection_id"] for entry in payload["projections"]} == {
        projection_id.value for projection_id in ProjectionId
    }
    assert all(entry["intended_audience"] for entry in payload["projections"])
    assert all(entry["stable_address"] for entry in payload["projections"])


def test_governed_projection_endpoint_uses_runtime_api_env(runtime_api_env) -> None:
    response = runtime_api_env["client"].get(
        "/api/v1/exports/governed-projections/depth-n-cycle-board"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["projection_id"] == "depth-n-cycle-board"
    assert payload["availability"] == "available"
    assert payload["source"]["artifact_content_hash"].startswith("sha256:")
    assert payload["projection_hash"].startswith("sha256:")
    assert payload["as_of"]
    assert payload["freshness"]["observed_at"]


def test_governed_projection_endpoint_preserves_existing_auth_defaults(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/exports/governed-projections/engine-census")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["intended_audience"] == "EXPERT"


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


def test_channel_registry_rejects_unknown_channel_fields() -> None:
    with pytest.raises(ValidationError):
        ChannelRegistryEntry.model_validate(
            {
                "registry_id": "unexpected",
                "path_template": "/api/v1/unexpected/live",
                "transport": "sse",
                "message_contract": "unexpected.v1",
                "auth_class": "runtime_tenant",
                "consumers": ["test"],
                "owner": "runtime-http",
                "include_in_schema": False,
                "status": "active",
                "unexpected": "must be forbidden",
            }
        )
