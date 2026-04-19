from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from polisyos.common.async_tools import get_shared_executor
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import IngestRequest
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import (
    ControlRegistryProviders,
    resolve_control_registry_providers,
)
from polisyos.runtime.http.services.task_runner import TaskRunner

try:  # pragma: no cover - optional runtime dependency
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


class _NoOpRetrievalService:
    def list_promotion_candidates(self):
        return []


def _build_registry_providers() -> ControlRegistryProviders:
    source_profile = SimpleNamespace(
        profile_id="fixture_profile",
        display_name="Fixture Profile",
        description="fixture source profile",
        connector_family="fixture.family",
        base_url="https://example.test/api",
        auth_policy="none",
        tags=("fixture",),
        source_organization="Fixture Org",
        estimated_datasets=1,
    )
    binding_profile = SimpleNamespace(
        profile_id="fixture_binding",
        display_name="Fixture Binding",
        description="fixture binding profile",
        schema_family="time_series",
        strategy="strict",
        rules=[{"name": "metric"}],
        expected_columns=["metric"],
        tags=("fixture",),
    )
    model_profile = SimpleNamespace(
        profile_id="fixture_model",
        display_name="Fixture Model",
        description="fixture llm profile",
        provider="openai",
        model_id="gpt-5-mini",
        base_url="https://api.example.test/v1",
        tags=("fixture",),
        capabilities=["chat"],
        input_cost_per_mtoken_usd=0.1,
        output_cost_per_mtoken_usd=0.2,
        enabled=True,
    )
    connector_entry = SimpleNamespace(
        metadata=SimpleNamespace(
            fully_qualified_id="fixture.family.connector",
            namespace="fixture.family",
            version="1.0.0",
            observed_latency_ms=12,
        ),
        known_datasets={"fixture.dataset"},
        loaded=True,
        last_health_check=datetime.now(UTC),
        short_id="fixture.family.connector",
    )

    return ControlRegistryProviders(
        connectors=SimpleNamespace(query_entries=lambda *args, **kwargs: [connector_entry]),
        source_profiles=SimpleNamespace(
            get=lambda profile_id: source_profile if profile_id == "fixture_profile" else None,
            list_all=lambda: [source_profile],
            list_by_family=lambda connector_family: (
                [source_profile] if connector_family == "fixture.family" else []
            ),
        ),
        binding_profiles=SimpleNamespace(
            get=lambda profile_id: binding_profile if profile_id == "fixture_binding" else None,
            list_all=lambda: [binding_profile],
        ),
        model_profiles=SimpleNamespace(list_all=lambda: [model_profile]),
    )


def test_control_service_uses_injected_registry_providers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    providers = _build_registry_providers()
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    service = ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=providers,
    )

    def _unexpected(cls, *args, **kwargs):
        del cls, args, kwargs
        raise AssertionError("singleton lookup should not be used")

    from polisyos.fabric.connectors.bindings.registry import BindingProfileRegistry
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.scientist.llm.profiles.registry import ModelProfileRegistry

    monkeypatch.setattr(SourceProfileRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(BindingProfileRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(ConnectorRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(ModelProfileRegistry, "get_instance", classmethod(_unexpected))

    connectors = service.list_connectors()
    source_profiles = service.list_source_profiles()
    binding_profiles = service.list_binding_profiles()
    model_profiles = service.list_model_profiles()

    assert connectors.connectors[0].connector_id == "fixture.family.connector"
    assert connectors.connectors[0].available_profiles == ["fixture_profile"]
    assert source_profiles.profiles[0].profile_id == "fixture_profile"
    assert source_profiles.profiles[0].connector_available is True
    assert binding_profiles.profiles[0].profile_id == "fixture_binding"
    assert model_profiles.profiles[0].profile_id == "fixture_model"

    connection_config = object()

    def _run_orchestrated_ingestion(**kwargs):
        assert kwargs["connection_config"] is connection_config
        return SimpleNamespace(
            evidence_bundle_ref=None,
            data_snapshot_ref=None,
            datasets_fetched=1,
            warnings=[],
            cursor_ref=None,
        )

    monkeypatch.setattr(
        "polisyos.fabric.connectors.profiles.resolver.resolve_connection_config",
        lambda profile: connection_config if profile.profile_id == "fixture_profile" else None,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_orchestrated_ingestion",
        _run_orchestrated_ingestion,
    )

    response = service.run_data_ingestion(
        IngestRequest.model_validate(
            {
                "datasets": [
                    {
                        "connector_id": "fixture.family.connector",
                        "dataset_id": "fixture.dataset",
                    }
                ],
                "connection_profile": "fixture_profile",
            }
        )
    )

    assert response.status == "completed"
    assert response.datasets_fetched == 1
    service.close()


def test_resolve_control_registry_providers_uses_factory_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    providers = _build_registry_providers()

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_connectors",
        lambda: (_ for _ in ()).throw(AssertionError("global connectors should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_source_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global source profiles should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_binding_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global binding profiles should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control_registry_providers._default_model_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global model profiles should not be used")),
    )

    resolved = resolve_control_registry_providers(
        connectors_factory=lambda: providers.connectors,
        source_profiles_factory=lambda: providers.source_profiles,
        binding_profiles_factory=lambda: providers.binding_profiles,
        model_profiles_factory=lambda: providers.model_profiles,
    )

    assert resolved == providers


def test_control_service_builds_retrieval_with_injected_provider_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    providers = _build_registry_providers()
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    seen: dict[str, object] = {}

    class _FakeRetrievalService:
        def __init__(self, *, curated_dir, cas_root, providers=None, **kwargs) -> None:
            del curated_dir, cas_root, kwargs
            seen["providers"] = providers

        def list_promotion_candidates(self):
            return []

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService",
        _FakeRetrievalService,
    )

    service = ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        policy_resolver=resolver,
        registry_providers=providers,
    )

    retrieval_providers = seen["providers"]
    assert retrieval_providers.registry is providers.connectors
    assert retrieval_providers.profiles is providers.source_profiles
    assert retrieval_providers.tracer is service._tracer
    assert retrieval_providers.metrics is service._metrics
    service.close()


def test_control_service_accepts_injected_observability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    providers = _build_registry_providers()
    store = FileSystemCAS(tmp_path / ".polisyos")
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=".polisyos/control.sqlite3",
        postgres_dsn=None,
    )
    metrics = object()
    tracer = object()

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control._default_runtime_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.control._default_runtime_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
    )

    service = ControlPlaneService(
        cas_root=tmp_path / ".polisyos",
        core_runs_root=tmp_path / ".polisyos" / "runs",
        artifact_store=store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=resolver,
        registry_providers=providers,
        metrics=metrics,
        tracer=tracer,
    )

    assert service._metrics is metrics
    assert service._tracer is tracer
    service.close()


def test_task_runner_uses_shared_executor_by_default() -> None:
    runner = TaskRunner()

    assert runner._executor is get_shared_executor()
    assert runner._owns_executor is False

    runner.close()


@pytest.mark.skipif(TestClient is None, reason="fastapi is not installed")
def test_runtime_container_passes_control_registry_provider_override(tmp_path) -> None:
    providers = _build_registry_providers()
    app = create_runtime_api_app(
        cas_root=tmp_path / ".polisyos",
        allow_fixture_identity=True,
        container_overrides=RuntimeContainerOverrides(
            control_registry_providers=providers,
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert app.state._control_service._registry_providers is providers
