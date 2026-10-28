"""Authenticated Runtime fixture shared by candidate source-access regressions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from tests._helpers.control_worker import stop_embedded_control_worker
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)


@pytest.fixture
def scoped_source_runtime(runtime_api_env: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Use the actual authenticated HTTP policy and its actual durable service."""
    client, cell, provider = _build_secure_client(
        runtime_api_env, opa_client=_AllowOPA(), claims_by_token={}
    )
    service = client.app.state.runtime_container.control_service
    assert service is not None
    stop_embedded_control_worker(service)
    result = {**runtime_api_env, "client": client, "service": service, "cell": cell.cell_id}
    for label in ("a", "b"):
        token = _fixture_bearer("source-access-" + label)
        tenant = runtime_api_env["tenant_" + label]
        provider.put_claim(
            token, _claims(tenant_id=tenant, cell_id=cell.cell_id, jti="source-" + label)
        )
        result["headers_" + label] = {"Authorization": "Bearer " + token, "X-Tenant-ID": tenant}
    try:
        yield result
    finally:
        stop_embedded_control_worker(service)
        client.close()
