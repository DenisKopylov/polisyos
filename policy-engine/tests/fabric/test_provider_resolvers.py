from __future__ import annotations

from polisyos.fabric.catalog.providers import resolve_catalog_providers
from polisyos.fabric.retrieval.providers import resolve_retrieval_providers


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
