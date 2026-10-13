from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

try:  # pragma: no cover - optional runtime dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


_PROFILE = "prod_full"
_SCOPE_NEED = {
    "data_needs": [
        {
            "metric": "scope_metric",
            "geography": "DEU",
            "time_start": "2025",
            "time_end": "2025",
        }
    ],
    "mode": "fastlane",
    "allow_explore_fallback": False,
}


def _publish_scope_catalog(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    excluded_profile_input: bool = False,
) -> tuple[Path, Path, object, object]:
    """Publish through the real producer and leave only its closed snapshot."""
    from tests.unit.fabric.test_retrieval_service_catalog import (
        _actual_scope_catalog,
        _install_builtin_worldbank_profile_scope,
    )

    profile_registry = _install_builtin_worldbank_profile_scope(monkeypatch)
    baseline = profile_registry.get("worldbank_wdi")
    assert baseline is not None
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir(parents=True, exist_ok=True)
    catalog = None
    try:
        if excluded_profile_input:
            profile_registry.register(
                baseline.model_copy(
                    update={"headers": {"X-PolicyOS-Fixture": "present-at-publish"}},
                    deep=True,
                ),
                override=True,
            )
            # This canonical publisher records excluded-present profile input in
            # its own generated receipt; the test never edits that receipt.
            catalog = _actual_scope_catalog(catalog_root)
        else:
            catalog = _actual_scope_catalog(
                catalog_root,
                profile_registry=profile_registry,
            )
        snapshot_root = catalog_root / "snapshot"
        database_path = catalog.database_path
        return snapshot_root, database_path, catalog, profile_registry
    finally:
        if excluded_profile_input:
            profile_registry.register(baseline, override=True)
        if catalog is not None:
            catalog.close()


def _build_api_env(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    snapshot_root: Path | None,
) -> tuple[dict[str, object], object | None]:
    """Build the real control app with either an exact selection or no profile."""
    from tests._helpers.runtime_http import build_runtime_api_env

    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    if snapshot_root is None:
        env = build_runtime_api_env(tmp_path / "api", include_test_client=True)
        return env, None

    from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection

    selection = CatalogServingSourceSelection(
        snapshot_root=snapshot_root,
        catalog_run_profile=_PROFILE,
    )
    env = build_runtime_api_env(
        tmp_path / "api",
        include_test_client=True,
        app_kwargs={"catalog_source_selection": selection},
    )
    return env, selection


def _resolve(client: Any, env: dict[str, object], *, profile: object = _PROFILE):
    from tests._helpers.runtime_http import _runtime_api_request

    payload = dict(_SCOPE_NEED)
    if profile is not _MISSING:
        payload["catalog_run_profile"] = profile
    return _runtime_api_request(
        env,
        client.post,
        "/api/v1/control/data/resolve",
        json=payload,
    )


_MISSING = object()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_catalog_profile_http_selects_published_plan_through_fresh_reader(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The public route carries a typed profile to a new reader of the published DB."""
    from tests._helpers.runtime_http import close_runtime_api_env

    snapshot_root, database_path, producer_graph, profile_registry = _publish_scope_catalog(
        tmp_path,
        monkeypatch,
    )
    env, selection = _build_api_env(
        tmp_path,
        monkeypatch,
        snapshot_root=snapshot_root,
    )
    client = env["client"]
    assert client is not None
    try:
        response = _resolve(client, env)
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["fetch_plans"]) == 1
        assert len(body["candidates"]) == 1
        assert body["candidates"][0]["metadata"]["source_currentness"] == "current"
        assert (
            body["candidates"][0]["metadata"]["plan_admission_reason"]
            == "catalog_profile_inputs_covered"
        )
        plan = body["fetch_plans"][0]
        assert (plan["connector_id"], plan["dataset_id"], plan["profile_id"]) == (
            "worldbank.wdi",
            "scope_dataset",
            "worldbank_wdi",
        )
        assert not any(warning.startswith("catalog_source_") for warning in body["warnings"])

        service = env["app"].state._control_service
        assert service._catalog_run_profile == _PROFILE
        assert service._catalog_source_selection is selection
        assert service._registry_providers.source_profiles is profile_registry
        fresh_graph = service._retrieval._dataset_catalog
        assert fresh_graph is not None
        assert fresh_graph is not producer_graph
        assert fresh_graph.database_path.resolve() == database_path.resolve()
    finally:
        close_runtime_api_env(env)


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_catalog_profile_http_refuses_absent_conflicting_and_malformed_selection(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The HTTP boundary refuses missing scope, a profile conflict, and invalid values."""
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.runtime.quality import substrate_registry
    from tests._helpers.runtime_http import close_runtime_api_env

    snapshot_root, database_path, _producer_graph, _profile_registry = _publish_scope_catalog(
        tmp_path,
        monkeypatch,
    )
    selected_env, _selection = _build_api_env(
        tmp_path / "selected",
        monkeypatch,
        snapshot_root=snapshot_root,
    )
    selected_client = selected_env["client"]
    assert selected_client is not None
    try:
        conflict = _resolve(selected_client, selected_env, profile="rest_backfill")
        assert conflict.status_code == 422, conflict.text
        assert conflict.json()["code"] == "catalog_run_profile_conflict"
        assert "fetch_plans" not in conflict.json()

        malformed = _resolve(selected_client, selected_env, profile="future_profile")
        assert malformed.status_code == 422, malformed.text
        assert "detail" in malformed.json()
        assert "fetch_plans" not in malformed.json()
    finally:
        close_runtime_api_env(selected_env)

    # Exercise the same actual published DB with no app-selected/requested profile.
    # The path override is test-local; the production profile or publisher receipt
    # is not synthesized or changed.
    original_paths = substrate_registry.default_substrate_catalog_paths
    original_overlay = catalog_read_api.default_acquisition_overlay_path
    startup_root = Path.cwd().resolve()
    overlay_path = tmp_path / "missing-acquisition-overlay.duckdb"
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(original_paths(root), l1_dcat_path=database_path)
            if Path(root).resolve() == startup_root
            else original_paths(root)
        ),
    )
    monkeypatch.setattr(
        catalog_read_api,
        "default_acquisition_overlay_path",
        lambda root: (
            overlay_path if Path(root).resolve() == startup_root else original_overlay(root)
        ),
    )
    missing_env, _ = _build_api_env(
        tmp_path / "missing",
        monkeypatch,
        snapshot_root=None,
    )
    missing_client = missing_env["client"]
    assert missing_client is not None
    try:
        missing = _resolve(missing_client, missing_env, profile=_MISSING)
        assert missing.status_code == 422, missing.text
        assert missing.json()["code"] == "catalog_run_profile_unresolved"
        assert "fetch_plans" not in missing.json()
    finally:
        close_runtime_api_env(missing_env)


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_catalog_profile_http_blocks_published_excluded_profile_inputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Producer-time excluded profile inputs cannot produce a current fetch plan."""
    from tests._helpers.runtime_http import close_runtime_api_env

    snapshot_root, _database_path, _producer_graph, _profile_registry = _publish_scope_catalog(
        tmp_path,
        monkeypatch,
        excluded_profile_input=True,
    )
    env, _selection = _build_api_env(
        tmp_path,
        monkeypatch,
        snapshot_root=snapshot_root,
    )
    client = env["client"]
    assert client is not None
    try:
        response = _resolve(client, env)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["fetch_plans"] == []
        assert len(body["candidates"]) == 1
        assert any(warning.startswith("catalog_source_stale:") for warning in body["warnings"])
        assert body["candidates"][0]["metadata"]["source_currentness"] == "stale"
    finally:
        close_runtime_api_env(env)
