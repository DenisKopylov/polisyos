"""Regression coverage for the API-01 causal package facade migration.

The identity assertions characterize the compatibility surface that must survive
the move.  The explicit export assertions describe the intended LA-020(C)
delta: package initializers expose a reviewed manifest rather than every name
that happened to be imported by a leaf module.
"""

from __future__ import annotations

from importlib import import_module, reload

import pytest

CAUSAL_ENGINE_MODULE = "polisyos.foundry.methods.catalog.causal.causal_engine"
INTERFERENCE_MODULE = "polisyos.foundry.methods.catalog.causal.interference"

EXPECTED_CAUSAL_ENGINE_EXPORTS = (
    "CausalEngine",
    "DataReadinessBlockedError",
)
EXPECTED_INTERFERENCE_EXPORTS = (
    "BipartiteInterferenceEstimator",
    "InterferenceAugmentedGraph",
    "InterferenceIdentificationResult",
    "NetworkAIPWEstimator",
    "PartialInterferenceEstimator",
    "SpatialInterferenceEstimator",
    "build_block_stratified_network_causal_data",
    "build_interference_topology_contracts",
    "identify_interference_effect",
)

REQUIRED_MONKEYPATCH_BINDINGS = (
    "mz_id_algorithm",
    "id_with_oracle_fallback",
    "id_star_algorithm",
    "idc_star_algorithm",
)


def _star_import(module_name: str) -> dict[str, object]:
    """Return the names produced by a real ``from module import *``."""
    namespace: dict[str, object] = {}
    # Intentional dynamic import: exercise the real star-import surface.
    exec(f"from {module_name} import *", namespace)  # noqa: S102
    namespace.pop("__builtins__", None)
    return namespace


def test_causal_engine_characterization_preserves_identity_and_test_bindings() -> None:
    """Keep documented classes, errors, and test-facing monkeypatch aliases identical."""
    runtime = import_module(CAUSAL_ENGINE_MODULE)
    api = import_module(f"{CAUSAL_ENGINE_MODULE}.api")
    artifacts = import_module(f"{CAUSAL_ENGINE_MODULE}.artifacts")

    assert runtime.CausalEngine is api.CausalEngine
    assert runtime.CausalEngine.__module__ == f"{CAUSAL_ENGINE_MODULE}.api"
    assert runtime.DataReadinessBlockedError is artifacts.DataReadinessBlockedError
    assert runtime._make_dummy_identification_result is artifacts._make_dummy_identification_result

    for binding in REQUIRED_MONKEYPATCH_BINDINGS:
        assert getattr(runtime, binding) is getattr(artifacts, binding)


def test_interference_characterization_preserves_leaf_identity() -> None:
    """Keep interference package aliases pointed at their real leaf owners."""
    runtime = import_module(INTERFERENCE_MODULE)
    api = import_module(f"{INTERFERENCE_MODULE}.api")
    contracts = import_module(
        "polisyos.foundry.methods.catalog.causal._interference_contracts"
    )
    identification = import_module(f"{INTERFERENCE_MODULE}.identification")

    for name in (
        "BipartiteInterferenceEstimator",
        "NetworkAIPWEstimator",
        "PartialInterferenceEstimator",
        "SpatialInterferenceEstimator",
    ):
        assert getattr(runtime, name) is getattr(api, name)

    assert runtime.InterferenceAugmentedGraph is contracts.InterferenceAugmentedGraph
    assert runtime.InterferenceIdentificationResult is contracts.InterferenceIdentificationResult
    for name in (
        "_ReductionErrorBoundPlan",
        "_SimplicialSupportGate",
        "_TopologyCertificatePlan",
    ):
        assert getattr(runtime, name) is getattr(contracts, name)
        assert name not in runtime.__all__
    for name in (
        "build_block_stratified_network_causal_data",
        "build_interference_topology_contracts",
        "identify_interference_effect",
    ):
        assert getattr(runtime, name) is getattr(identification, name)


@pytest.mark.parametrize(
    ("module_name", "expected_exports"),
    [
        (CAUSAL_ENGINE_MODULE, EXPECTED_CAUSAL_ENGINE_EXPORTS),
        (INTERFERENCE_MODULE, EXPECTED_INTERFERENCE_EXPORTS),
    ],
)
def test_explicit_export_manifests_are_deterministic_and_star_importable(
    module_name: str,
    expected_exports: tuple[str, ...],
) -> None:
    """Use a fixed public manifest and make star-import match it exactly."""
    runtime = import_module(module_name)
    first_manifest = tuple(runtime.__all__)
    second_manifest = tuple(import_module(module_name).__all__)

    assert first_manifest == expected_exports
    assert second_manifest == first_manifest
    assert len(first_manifest) == len(set(first_manifest))
    assert all(not name.startswith("_") for name in first_manifest)
    assert set(_star_import(module_name)) == set(first_manifest)


def test_causal_engine_private_and_test_helpers_are_not_public_exports() -> None:
    """Keep compatibility-only private/test names addressable but out of ``__all__``."""
    runtime = import_module(CAUSAL_ENGINE_MODULE)

    assert "_make_dummy_identification_result" not in runtime.__all__
    assert set(REQUIRED_MONKEYPATCH_BINDINGS).isdisjoint(runtime.__all__)
    assert "_artifacts" not in runtime.__all__


@pytest.mark.parametrize("module_name", [CAUSAL_ENGINE_MODULE, INTERFERENCE_MODULE])
def test_unknown_facade_names_fail_closed(module_name: str) -> None:
    """An unknown name must not become importable through a package facade."""
    with pytest.raises(ImportError):
        # Intentional dynamic import: prove unknown names fail closed.
        exec(f"from {module_name} import __api_01_unknown_name__", {})  # noqa: S102


def test_causal_engine_incidental_leaf_import_does_not_expand_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding a public-looking leaf import must not change the causal facade."""
    runtime = import_module(CAUSAL_ENGINE_MODULE)
    artifacts = import_module(f"{CAUSAL_ENGINE_MODULE}.artifacts")
    incidental_name = "API_01_INCIDENTAL_IMPORT"

    monkeypatch.setattr(artifacts, incidental_name, object(), raising=False)
    try:
        reload(runtime)
        assert not hasattr(runtime, incidental_name)
        assert incidental_name not in runtime.__all__
    finally:
        monkeypatch.undo()
        runtime.__dict__.pop(incidental_name, None)
        reload(runtime)


def test_interference_incidental_leaf_import_does_not_expand_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adding a public-looking API-module import must not change the facade."""
    runtime = import_module(INTERFERENCE_MODULE)
    api = import_module(f"{INTERFERENCE_MODULE}.api")
    incidental_name = "API_01_INCIDENTAL_IMPORT"

    monkeypatch.setattr(api, incidental_name, object(), raising=False)
    try:
        reload(runtime)
        assert not hasattr(runtime, incidental_name)
        assert incidental_name not in runtime.__all__
    finally:
        monkeypatch.undo()
        runtime.__dict__.pop(incidental_name, None)
        reload(runtime)


@pytest.mark.parametrize(
    ("module_name", "required_bindings"),
    [
        (
            CAUSAL_ENGINE_MODULE,
            (
                "CausalEngine",
                "DataReadinessBlockedError",
                *REQUIRED_MONKEYPATCH_BINDINGS,
                "_make_dummy_identification_result",
            ),
        ),
        (
            INTERFERENCE_MODULE,
            (
                "InterferenceAugmentedGraph",
                "InterferenceIdentificationResult",
                "_ReductionErrorBoundPlan",
                "_SimplicialSupportGate",
                "_TopologyCertificatePlan",
            ),
        ),
    ],
)
def test_facade_reload_purges_stale_injected_names(
    module_name: str,
    required_bindings: tuple[str, ...],
) -> None:
    """Reloading a facade must not retain names from its previous module dict."""
    runtime = import_module(module_name)
    stale_name = "API_01_STALE_INJECTED_NAME"
    runtime.__dict__[stale_name] = object()

    try:
        reloaded = reload(runtime)
        assert not hasattr(reloaded, stale_name)
        assert stale_name not in reloaded.__all__
        for name in required_bindings:
            assert hasattr(reloaded, name)
    finally:
        runtime.__dict__.pop(stale_name, None)
        reload(runtime)
