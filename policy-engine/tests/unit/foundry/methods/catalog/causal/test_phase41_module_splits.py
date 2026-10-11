from __future__ import annotations

import importlib


def test_causal_engine_split_modules_preserve_legacy_runtime_surface() -> None:
    runtime = importlib.import_module("polisyos.foundry.methods.catalog.causal.causal_engine")
    api = importlib.import_module("polisyos.foundry.methods.catalog.causal.causal_engine.api")
    artifacts = importlib.import_module(
        "polisyos.foundry.methods.catalog.causal.causal_engine.artifacts"
    )

    for leaf in ("discovery", "identification", "estimation", "sensitivity"):
        importlib.import_module(f"polisyos.foundry.methods.catalog.causal.causal_engine.{leaf}")

    assert runtime.CausalEngine is api.CausalEngine
    assert runtime.DataReadinessBlockedError is artifacts.DataReadinessBlockedError


def test_interference_split_module_preserves_legacy_runtime_surface() -> None:
    runtime = importlib.import_module("polisyos.foundry.methods.catalog.causal.interference")
    api = importlib.import_module("polisyos.foundry.methods.catalog.causal.interference.api")

    assert runtime.NetworkAIPWEstimator is api.NetworkAIPWEstimator
    assert runtime.InterferenceIdentificationResult is api.InterferenceIdentificationResult


def test_id_engine_split_modules_preserve_legacy_runtime_surface() -> None:
    runtime = importlib.import_module("polisyos.foundry.methods.catalog.causal.id_engine")
    api = importlib.import_module("polisyos.foundry.methods.catalog.causal.id_engine.api")
    core = importlib.import_module("polisyos.foundry.methods.catalog.causal.id_engine.core")

    assert runtime.id_algorithm is api.id_algorithm
    assert runtime.IdentificationResult is core.IdentificationResult


def test_causal_engine_split_has_no_deferred_api_import_cycle() -> None:
    """The split mixins depend on a leaf helper contract, not the composed API."""
    from tools.quality.validation.decomposition_preflight import collect_import_graph

    api = "polisyos.foundry.methods.catalog.causal.causal_engine.api"
    split_leaves = {
        "polisyos.foundry.methods.catalog.causal.causal_engine.discovery",
        "polisyos.foundry.methods.catalog.causal.causal_engine.identification",
    }
    cycles = collect_import_graph()["cycles"]

    assert not [
        cycle
        for cycle in cycles
        if api in cycle["modules"] and split_leaves.intersection(cycle["modules"])
    ]
