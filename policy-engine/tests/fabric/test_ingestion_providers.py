from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.ingestion_providers import (
    build_filesystem_artifact_store,
    resolve_ingestion_dependencies,
)


def test_build_filesystem_artifact_store_returns_filesystem_cas(tmp_path) -> None:
    store = build_filesystem_artifact_store(tmp_path / ".polisyos")

    assert isinstance(store, FileSystemCAS)
    assert store.root == tmp_path / ".polisyos"


def test_resolve_ingestion_dependencies_uses_explicit_providers() -> None:
    class DummyRegistry:
        pass

    class DummyTracer:
        pass

    class DummyMetrics:
        pass

    dependencies = resolve_ingestion_dependencies(
        registry=DummyRegistry(),  # type: ignore[arg-type]
        tracer=DummyTracer(),  # type: ignore[arg-type]
        metrics=DummyMetrics(),  # type: ignore[arg-type]
        store_factory=build_filesystem_artifact_store,
    )

    assert isinstance(dependencies.registry, DummyRegistry)
    assert isinstance(dependencies.tracer, DummyTracer)
    assert isinstance(dependencies.metrics, DummyMetrics)
    assert dependencies.store_factory is build_filesystem_artifact_store


def test_resolve_ingestion_dependencies_uses_factory_overrides(
    monkeypatch,
) -> None:
    class DummyRegistry:
        pass

    class DummyTracer:
        pass

    class DummyMetrics:
        pass

    monkeypatch.setattr(
        "polisyos.fabric.ingestion_providers._default_registry",
        lambda: (_ for _ in ()).throw(AssertionError("global registry should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion_providers._default_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.ingestion_providers._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    dependencies = resolve_ingestion_dependencies(
        registry_factory=DummyRegistry,  # type: ignore[arg-type]
        tracer_factory=DummyTracer,  # type: ignore[arg-type]
        metrics_factory=DummyMetrics,  # type: ignore[arg-type]
        store_factory=build_filesystem_artifact_store,
    )

    assert isinstance(dependencies.registry, DummyRegistry)
    assert isinstance(dependencies.tracer, DummyTracer)
    assert isinstance(dependencies.metrics, DummyMetrics)
