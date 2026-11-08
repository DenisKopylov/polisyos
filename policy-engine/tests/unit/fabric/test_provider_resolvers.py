from __future__ import annotations

from collections.abc import Callable
from typing import get_type_hints

from polisyos.core.observability import PolicyOSTracer
from polisyos.fabric.catalog.providers import resolve_catalog_providers
from polisyos.fabric.connectors.federation import DataComposer
from polisyos.fabric.ingestion.ingestion_providers import (
    IngestionDependencies,
    resolve_ingestion_dependencies,
)
from polisyos.fabric.retrieval.providers import RetrievalProviders, resolve_retrieval_providers
from polisyos.fabric.world.providers import WorldObservabilityProviders, resolve_world_observability


def test_fabric_provider_tracer_annotations_resolve_to_runtime_tracer() -> None:
    for providers, resolve in (
        (IngestionDependencies, resolve_ingestion_dependencies),
        (RetrievalProviders, resolve_retrieval_providers),
        (WorldObservabilityProviders, resolve_world_observability),
    ):
        assert get_type_hints(providers)["tracer"] is PolicyOSTracer
        annotations = get_type_hints(resolve)
        assert annotations["tracer"] == PolicyOSTracer | None
        assert annotations["tracer_factory"] == Callable[[], PolicyOSTracer] | None
    assert get_type_hints(DataComposer.__init__)["tracer"] == PolicyOSTracer | None


def test_resolve_retrieval_providers_uses_factory_overrides(monkeypatch) -> None:
    class DummyRegistry:
        pass

    class DummyProfiles:
        pass

    class DummyTracer:
        pass

    class DummyMetrics:
        pass

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers._default_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers._default_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global profiles should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers._default_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    providers = resolve_retrieval_providers(
        registry_factory=DummyRegistry,  # type: ignore[arg-type]
        profiles_factory=DummyProfiles,  # type: ignore[arg-type]
        tracer_factory=DummyTracer,  # type: ignore[arg-type]
        metrics_factory=DummyMetrics,  # type: ignore[arg-type]
    )

    assert isinstance(providers.registry, DummyRegistry)
    assert isinstance(providers.profiles, DummyProfiles)
    assert isinstance(providers.tracer, DummyTracer)
    assert isinstance(providers.metrics, DummyMetrics)


def test_resolve_catalog_providers_uses_factory_overrides(monkeypatch) -> None:
    class DummyRegistry:
        pass

    class DummyProfiles:
        pass

    monkeypatch.setattr(
        "polisyos.fabric.catalog.providers._default_connector_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.catalog.providers._default_source_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("global profiles should not be used")),
    )

    providers = resolve_catalog_providers(
        connector_registry_factory=DummyRegistry,  # type: ignore[arg-type]
        source_profiles_factory=DummyProfiles,  # type: ignore[arg-type]
    )

    assert isinstance(providers.connector_registry, DummyRegistry)
    assert isinstance(providers.source_profiles, DummyProfiles)
