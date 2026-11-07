from __future__ import annotations

import importlib
from pathlib import Path

import pytest


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


def test_causal_engine_sibling_module_imports_are_direct_source_closure_edges(
    tmp_path: Path,
) -> None:
    """Qualified module imports avoid resolving children through opaque package exports."""
    ledger = importlib.import_module("polisyos.runtime.quality.confidence_ledger")
    ledger = importlib.import_module("polisyos.runtime.quality.confidence_ledger")

    # This fixture leaves the package and child unloaded. Its globals purge makes
    # package export inference unknown, but the explicit import is still a source edge.
    fixture = tmp_path / "opaque-package-repo"
    package_dir = fixture / "src/polisyos/opaque"
    package_dir.mkdir(parents=True)
    (fixture / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text(
        "for _name in tuple(globals()):\n"
        '    if _name != "__name__":\n'
        "        globals().pop(_name, None)\n"
        "del _name\n",
        encoding="utf-8",
    )
    (package_dir / "child.py").write_text("VALUE = 1\n", encoding="utf-8")
    entry = fixture / "src/polisyos/entry.py"
    entry.write_text("import polisyos.opaque.child as _child\n", encoding="utf-8")

    closure = dict(ledger._resolve_authority_import_closure(fixture, "polisyos.entry"))
    assert closure["polisyos.opaque"] == "src/polisyos/opaque/__init__.py"
    assert closure["polisyos.opaque.child"] == "src/polisyos/opaque/child.py"

    # A `from package import child` route still depends on the parent's namespace
    # and must not inherit the explicit dotted-import exemption.
    entry.write_text("from polisyos.opaque import child as _child\n", encoding="utf-8")
    with pytest.raises(ledger.ConfidenceLedgerError, match="unqualified package initializer route"):
        ledger._resolve_authority_import_closure(fixture, "polisyos.entry")


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
    assert runtime._internal_proof_step_to_ir is core._internal_proof_step_to_ir


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
