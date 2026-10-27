"""Served source-progress dependency and partial projection contract tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from tests._helpers.source_progress import finite_source_reader, write_source_history

from polisyos.core.security.identity import PolicyOSRole
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.runtime.http.container import RuntimeContainerOverrides
from tests._helpers.runtime_http import _build_registry_providers
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


@pytest.fixture
def source_progress_api_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Prepare the genuine compact fixture catalog before runtime startup.

    This changes a declared fixture input, not the grounding gate. No production
    catalog, private CAS or absolute Mac path is required by these HTTP tests.
    """
    from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.http.services.control import run_lifecycle as control_lifecycle
    from polisyos.runtime.quality import substrate_registry

    catalog_root = tmp_path / "fixture-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    original_paths = substrate_registry.default_substrate_catalog_paths
    runtime_root = Path(control_lifecycle.__file__).resolve().parents[6]
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(original_paths(root), l1_dcat_path=catalog_root / "catalog.duckdb")
            if Path(root).resolve() == runtime_root
            else original_paths(root)
        ),
    )
    env = build_runtime_api_env(tmp_path / "runtime", include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def _client(runtime_api_env, providers):
    bearer = _fixture_bearer("source-progress-api")
    client, cell, identity = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(control_registry_providers=providers),
    )
    identity.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="source-progress-api-claims",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    return client, {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": runtime_api_env["tenant_a"]}


def test_post_incremental_uses_the_actual_host_bound_replay_file(
    source_progress_api_env,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real authorized POSTs reuse admitted ETAG only on actual file replay."""
    from polisyos.fabric.ingestion.source_progress import ReconciledSourceFrame

    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="rest.json",
        dataset_id="events",
        schema_id="rest.json.events",
        snapshots=[('"a8"', [])],
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config("rest.json", ConnectionConfig(url=reader.fixture_path.as_uri()))
    providers = replace(
        _build_registry_providers(), connectors=registry, source_progress_readers=(reader,)
    )
    client, headers = _client(source_progress_api_env, providers)
    observed = []
    real_fetch = ReconciledSourceFrame.replay_fetch

    def record_actual_request(frame, config, request):
        observed.append(request)
        return real_fetch(frame, config, request)

    monkeypatch.setattr(ReconciledSourceFrame, "replay_fetch", record_actual_request)
    request = {
        "datasets": [{"connector_id": "rest.json", "dataset_id": "events"}],
        "execution_mode": "batch_incremental",
        "produce_data_snapshot": True,
    }
    try:
        with client:
            first = client.post(
                "/api/v1/control/data/ingest",
                json=request,
                headers={**headers, "X-PolicyOS-Step-Up": _install_bound_test_step_up(client)},
            )
            assert first.status_code == 200
            assert first.json()["status"] == "completed", first.json()
            assert first.json()["cursor_ref"] and observed[-1].incremental_since is None
            row = {"event_id": "a-event", "source_version": "9"}
            write_source_history(reader, [('"a8"', []), ('"a9"', [row])])
            second = client.post(
                "/api/v1/control/data/ingest",
                json=request,
                headers={**headers, "X-PolicyOS-Step-Up": _install_bound_test_step_up(client)},
            )
            assert second.status_code == 200
            assert second.json()["status"] == "completed", second.json()
            assert observed[-1].incremental_since.value == '"a8"'
            assert second.json()["cursor_ref"] != first.json()["cursor_ref"]
            assert second.json()["data_snapshot_ref"]
    finally:
        registry.shutdown()


def test_post_partial_result_is_partial_and_cannot_produce_input_bindings(
    source_progress_api_env,
) -> None:
    """Consumer contract only; source-failure production is covered by real B80."""
    providers = _build_registry_providers()
    client, headers = _client(source_progress_api_env, providers)
    with (
        client,
        patch(
            "polisyos.fabric.data_plane.modes.run_batch_incremental",
            return_value=IngestionResult(
                status="partial",
                datasets_fetched=1,
                warnings=[
                    "source_fetch_failed:fixture.family.connector:fixture.dataset:FetchError"
                ],
            ),
        ),
        patch(
            "polisyos.runtime.http.services.control.run_lifecycle.ControlPlaneService._produce_input_bindings",
            side_effect=AssertionError("partial source input cannot create bindings"),
        ) as binding,
    ):
        response = client.post(
            "/api/v1/control/data/ingest",
            json={
                "datasets": [
                    {"connector_id": "fixture.family.connector", "dataset_id": "fixture.dataset"}
                ],
                "execution_mode": "batch_incremental",
                "produce_input_bindings": True,
                "binding_profile_id": "fixture_binding",
            },
            headers={**headers, "X-PolicyOS-Step-Up": _install_bound_test_step_up(client)},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["input_bindings_ref"] is None and body["data_snapshot_ref"] is None
    assert "Successfully" not in body["message"]
    binding.assert_not_called()
