from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest


def _build_complete_published_fixture(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    excluded_profile_input: bool = False,
) -> object:
    """Load the fixture helper beside this RAW-only test overlay."""
    import importlib.util
    import sys

    fixture_path = Path(__file__).with_name("_published_catalog_fixture.py")
    module_name = "_e02_complete_published_catalog_fixture"
    spec = importlib.util.spec_from_file_location(module_name, fixture_path)
    if spec is None:
        raise AssertionError("fixture helper module spec was not created")
    if spec.loader is None:
        raise AssertionError("fixture helper module has no loader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.build_published_catalog_fixture(
        tmp_path, monkeypatch, excluded_profile_input=excluded_profile_input
    )


def test_fixture_source_preflight_refuses_new_required_blocker(tmp_path: Path) -> None:
    """A new owner blocker cannot disappear behind the fixture's finite source map."""
    import importlib.util
    import sys

    import yaml

    from polisyos.data_forge.domains.catalog.registry import default_catalog_source_registry_path

    helper_path = Path(__file__).with_name("_published_catalog_fixture.py")
    spec = importlib.util.spec_from_file_location("_e02_catalog_coverage_fixture", helper_path)
    if spec is None:
        raise AssertionError("fixture helper module spec was not created")
    if spec.loader is None:
        raise AssertionError("fixture helper module has no loader")
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)

    canonical_path = default_catalog_source_registry_path()
    snapshot_path = tmp_path / "captured-source-registry.yaml"
    snapshot = helper._capture_fixture_source_registry(canonical_path, snapshot_path)
    assert snapshot.required_source_ids == helper.FIXTURE_SUPPORTED_SOURCE_IDS

    payload = yaml.safe_load(snapshot.source_bytes)
    sources = payload["sources"]
    marker = dict(next(row for row in sources if row["name"] == "oecd"))
    marker["name"] = "fixture_marker_blocker"
    marker["endpoint"] = "https://fixture.invalid/marker"
    sources.append(marker)
    candidate_bytes = yaml.safe_dump(payload, sort_keys=False).encode("utf-8")
    candidate_path = tmp_path / "registry-with-new-blocker.yaml"
    candidate_path.write_bytes(candidate_bytes)

    with pytest.raises(AssertionError, match="source coverage mismatch") as refusal:
        helper._assert_fixture_source_coverage(candidate_path)
    assert "fixture_marker_blocker" in str(refusal.value)

    # Simulate a registry mutation after admission but before fixture writing. The
    # writer must refuse the changed source basis rather than use stale selected IDs.
    snapshot_path.write_bytes(candidate_bytes)
    fixture_registry_path = tmp_path / "fixture-registry.yaml"
    with pytest.raises(AssertionError, match="changed after coverage preflight"):
        helper._write_registry(fixture_registry_path, "http://127.0.0.1:1", snapshot)
    assert not fixture_registry_path.exists()


try:  # pragma: no cover - optional runtime dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from fastapi.testclient import TestClient as FastAPITestClient
    from httpx import Response


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


def _build_api_env(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    *,
    snapshot_root: Path | None,
    source_owner_root: Path | None = None,
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
        source_owner_root=source_owner_root,
        catalog_run_profile=_PROFILE,
    )
    env = build_runtime_api_env(
        tmp_path / "api",
        include_test_client=True,
        app_kwargs={"catalog_source_selection": selection},
    )
    return env, selection


def _resolve(
    client: FastAPITestClient, env: dict[str, object], *, profile: object = _PROFILE
) -> Response:
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
    """The public route carries a typed profile to a fresh current producer snapshot."""
    from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths
    from tests._helpers.runtime_http import close_runtime_api_env
    from tests.unit.runtime.quality.test_substrate_registry import (
        _write_substrate_catalog_fixture,
    )

    owner_root = tmp_path / "catalog-fixture-owner"
    owner_root.mkdir(parents=True, exist_ok=True)
    _write_substrate_catalog_fixture(owner_root)
    project_root = Path(__file__).resolve().parents[4]
    owner_paths = default_substrate_catalog_paths(project_root, source_owner_root=owner_root)
    # The epoch regime is code-root owned; avoid a conflicting synthetic duplicate.
    owner_paths.schema_regime_registry_path.write_text('{"regimes": {}}\n', encoding="utf-8")
    fixture = _build_complete_published_fixture(owner_root / "published", monkeypatch)
    env = None
    try:
        snapshot_root = fixture.snapshot_root
        database_path = fixture.database_path
        producer_graph = fixture.producer_graph
        profile_registry = fixture.profile_registry
        assert fixture.readiness["consumer_ready"] is True
        assert fixture.readiness["evaluation_ready"] is True
        assert fixture.readiness["full_publish_ready"] == (fixture.evaluation_mode == "full-ready")
        env, selection = _build_api_env(
            tmp_path,
            monkeypatch,
            snapshot_root=snapshot_root,
            source_owner_root=owner_root,
        )
        client = env["client"]
        assert client is not None
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

        # Remove a real producer-lineage artifact, then create a second fresh reader.
        # The consumer must stop issuing plans when the native publish receipt is absent.
        stage_state_path = snapshot_root / "datasets" / "manifests" / "stage_state.json"
        stage_state = json.loads(stage_state_path.read_text(encoding="utf-8"))
        assert stage_state["publish"]["status"] == "complete"
        stage_state_path.unlink()
        refused_env, _refused_selection = _build_api_env(
            tmp_path / "receipt-removed-reader",
            monkeypatch,
            snapshot_root=snapshot_root,
            source_owner_root=owner_root,
        )
        refused_client = refused_env["client"]
        assert refused_client is not None
        try:
            refused = _resolve(refused_client, refused_env)
            assert refused.status_code == 200, refused.text
            refused_body = refused.json()
            assert refused_body["fetch_plans"] == []
            assert len(refused_body["candidates"]) == 1
            assert refused_body["candidates"][0]["metadata"]["source_currentness"] != "current"
            assert any(
                warning.startswith(("catalog_source_not_established:", "catalog_source_stale:"))
                for warning in refused_body["warnings"]
            )
        finally:
            close_runtime_api_env(refused_env)
    finally:
        if env is not None:
            close_runtime_api_env(env)
        fixture.producer_graph.close()
        fixture.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_catalog_profile_http_recomputes_same_id_profile_drift_for_real_consumers(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A live same-ID profile edit withholds stale published rows from real readers."""
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_catalog_publish_receipt,
    )
    from tests._helpers.runtime_http import close_runtime_api_env

    fixture = _build_complete_published_fixture(tmp_path / "published", monkeypatch)
    profile_registry = fixture.profile_registry
    environments: list[dict[str, object]] = []
    original_profile = profile_registry.get("worldbank_wdi")
    try:
        assert original_profile is not None
        assert original_profile.profile_id == "worldbank_wdi"

        baseline_env, _selection = _build_api_env(
            tmp_path / "baseline-reader",
            monkeypatch,
            snapshot_root=fixture.snapshot_root,
        )
        environments.append(baseline_env)
        baseline_client = baseline_env["client"]
        assert baseline_client is not None
        baseline = _resolve(baseline_client, baseline_env)
        assert baseline.status_code == 200, baseline.text
        baseline_body = baseline.json()
        assert len(baseline_body["fetch_plans"]) == 1
        assert baseline_body["candidates"][0]["metadata"]["source_currentness"] == "current"

        receipt = current_catalog_publish_receipt(
            fixture.database_path,
            run_profile=_PROFILE,
        )
        assert receipt["state"] == "current"
        profile_coverage = receipt["profile_input_coverage"]
        assert isinstance(profile_coverage, dict)
        assert profile_coverage["profiles"][original_profile.profile_id] == "none"

        drifted_profile = original_profile.model_copy(
            update={
                "base_url": f"{original_profile.base_url.rstrip('/')}/e02-profile-drift",
            },
            deep=True,
        )
        assert drifted_profile.profile_id == original_profile.profile_id
        assert drifted_profile.base_url != original_profile.base_url
        profile_registry.register(drifted_profile, override=True)

        warm = _resolve(baseline_client, baseline_env)
        assert warm.status_code == 200, warm.text
        warm_body = warm.json()
        assert warm_body["fetch_plans"] == []
        assert warm_body["candidates"]
        assert warm_body["candidates"][0]["metadata"]["source_currentness"] != "current"
        assert any(
            warning.startswith(("catalog_source_stale:", "catalog_source_not_established:"))
            for warning in warm_body["warnings"]
        )

        fresh_env, _fresh_selection = _build_api_env(
            tmp_path / "fresh-drift-reader",
            monkeypatch,
            snapshot_root=fixture.snapshot_root,
        )
        environments.append(fresh_env)
        fresh_client = fresh_env["client"]
        assert fresh_client is not None
        fresh = _resolve(fresh_client, fresh_env)
        assert fresh.status_code == 200, fresh.text
        fresh_body = fresh.json()
        assert fresh_body["fetch_plans"] == []
        assert fresh_body["candidates"]
        assert fresh_body["candidates"][0]["metadata"]["source_currentness"] != "current"

        # Removing the recomputed gate makes the persisted old dataset selectable.
        # The receipt coverage below came from the real current producer receipt.
        warm_control = baseline_env["app"].state._control_service._retrieval
        with monkeypatch.context() as removal_control:
            removal_control.setattr(
                warm_control,
                "_catalog_publish_admission",
                lambda _catalog, _run_profile: (
                    "current",
                    "removed_live_profile_currentness_gate",
                    profile_coverage,
                ),
            )
            without_gate = _resolve(baseline_client, baseline_env)
        assert without_gate.status_code == 200, without_gate.text
        stale_plans = without_gate.json()["fetch_plans"]
        assert len(stale_plans) == 1
        assert stale_plans[0]["dataset_id"] == "scope_dataset"
        warm_retrieval = baseline_env["app"].state._control_service._retrieval
        persisted = warm_retrieval._dataset_catalog
        assert persisted is not None
        persisted_titles = {
            result.title for result in persisted.search_datasets("scope metric", top_k=20)
        }
        assert stale_plans[0]["metadata"]["catalog_title"] in persisted_titles

        # Restore the exact captured owner profile; currentness must recover from
        # actual source content, without editing the published receipt or manifest.
        profile_registry.register(original_profile, override=True)
        restored_env, _restored_selection = _build_api_env(
            tmp_path / "restored-reader",
            monkeypatch,
            snapshot_root=fixture.snapshot_root,
        )
        environments.append(restored_env)
        restored_client = restored_env["client"]
        assert restored_client is not None
        restored = _resolve(restored_client, restored_env)
        assert restored.status_code == 200, restored.text
        restored_body = restored.json()
        assert len(restored_body["fetch_plans"]) == 1
        assert restored_body["candidates"][0]["metadata"]["source_currentness"] == "current"
    finally:
        if original_profile is not None:
            profile_registry.register(original_profile, override=True)
        for environment in reversed(environments):
            close_runtime_api_env(environment)
        fixture.producer_graph.close()
        fixture.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_catalog_profile_http_refuses_absent_conflicting_and_malformed_selection(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """The HTTP boundary refuses missing scope, a profile conflict, and invalid values."""
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.runtime.quality import substrate_registry
    from tests._helpers.runtime_http import close_runtime_api_env

    fixture = _build_complete_published_fixture(tmp_path, monkeypatch)
    selected_env = None
    missing_env = None
    try:
        selected_env, _selection = _build_api_env(
            tmp_path / "selected",
            monkeypatch,
            snapshot_root=fixture.snapshot_root,
        )
        selected_client = selected_env["client"]
        assert selected_client is not None
        conflict = _resolve(selected_client, selected_env, profile="rest_backfill")
        assert conflict.status_code == 422, conflict.text
        assert conflict.json()["code"] == "catalog_run_profile_conflict"
        assert "fetch_plans" not in conflict.json()

        malformed = _resolve(selected_client, selected_env, profile="future_profile")
        assert malformed.status_code == 422, malformed.text
        assert "detail" in malformed.json()
        assert "fetch_plans" not in malformed.json()

        # Exercise the same actual published DB with no app-selected/requested profile.
        # The path override is test-local; the production profile or publisher receipt
        # is not synthesized or changed.
        original_paths = substrate_registry.default_substrate_catalog_paths
        original_overlay = catalog_read_api.default_acquisition_overlay_path
        startup_root = Path.cwd().resolve()
        overlay_path = tmp_path / "missing-acquisition-overlay.duckdb"
        database_path = fixture.database_path
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
        missing = _resolve(missing_client, missing_env, profile=_MISSING)
        assert missing.status_code == 422, missing.text
        assert missing.json()["code"] == "catalog_run_profile_unresolved"
        assert "fetch_plans" not in missing.json()
    finally:
        if selected_env is not None:
            close_runtime_api_env(selected_env)
        if missing_env is not None:
            close_runtime_api_env(missing_env)
        fixture.producer_graph.close()
        fixture.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_catalog_profile_http_refuses_unversioned_private_profile_inputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Unversioned private profile input blocks publish and the HTTP fetch plan."""
    from polisyos.fabric.connectors.profiles.builtin_profiles import BUILTIN_PROFILES
    from tests._helpers.runtime_http import close_runtime_api_env

    fixture = _build_complete_published_fixture(
        tmp_path,
        monkeypatch,
        excluded_profile_input=True,
    )
    env = None
    try:
        profile_registry = fixture.profile_registry
        published_profile = profile_registry.get("worldbank_wdi")
        assert published_profile is not None
        assert published_profile.headers == {"X-PolicyOS-Fixture": "present-at-publish"}
        assert fixture.report_basis_state == "not_established"
        assert fixture.report_basis_reason == "profile_private_inputs_unversioned"
        assert fixture.publish_blocked_reason == (
            "Dataset publish blocked: benchmark/QC report basis not_established "
            "(profile_private_inputs_unversioned)"
        )
        assert fixture.publish_receipt_state == "not_established"
        assert fixture.publish_receipt_reason == "publish_lineage_absent"

        baseline = next(
            profile for profile in BUILTIN_PROFILES if profile.profile_id == "worldbank_wdi"
        ).model_copy(update={"headers": {}}, deep=True)
        profile_registry.register(baseline, override=True)
        assert profile_registry.get("worldbank_wdi") == baseline

        env, selection = _build_api_env(
            tmp_path / "reader-with-baseline-profile",
            monkeypatch,
            snapshot_root=fixture.snapshot_root,
        )
        client = env["client"]
        assert client is not None
        response = _resolve(client, env)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["fetch_plans"] == []
        assert len(body["candidates"]) == 1
        assert any(
            warning.startswith("catalog_source_not_established:") for warning in body["warnings"]
        )
        assert body["candidates"][0]["metadata"]["source_currentness"] == "not_established"
        service = env["app"].state._control_service
        assert service._catalog_run_profile == _PROFILE
        assert service._catalog_source_selection is selection
        assert service._registry_providers.source_profiles is profile_registry
    finally:
        if env is not None:
            close_runtime_api_env(env)
        fixture.producer_graph.close()
        fixture.close()
