"""Behavioral ABI witnesses for the existing causal package facades (LA-020).

These controls concern supported imports, identification and serialization;
they do not attest optional estimation backends or effects on admitted data.
"""

from __future__ import annotations

import ast
import importlib
import json
import pickle
import pydoc
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from polisyos.foundry.methods.catalog.causal import causal_engine, interference
from polisyos.foundry.methods.catalog.causal.causal_engine import identification
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle
from polisyos.ir.analytics.negative_certificate import NegativeCertificate
from polisyos.scientist.methods.discovery.stability import _evaluate_identifiability


def _graph(*, confounded: bool = False) -> CausalGraphModel:
    edges = [CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)]
    if confounded:
        edges.append(CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=["X", "Y"], edges=edges)


@pytest.mark.parametrize("confounded", [False, True])
def test_scientist_consumer_uses_facade_identification_status(confounded: bool) -> None:
    """The actual discovery consumer distinguishes an identified DAG from a bow graph."""
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )
    assert _evaluate_identifiability(_graph(confounded=confounded), query) is not confounded


@pytest.mark.parametrize("confounded", [False, True])
def test_facade_run_bundle_roundtrip_preserves_identification_boundary(confounded: bool) -> None:
    """Run the real public engine and consume its serialized evidence without an estimator."""
    report, bundle, certificate = causal_engine.CausalEngine().run(
        "X", "Y", _graph(confounded=confounded), run_id="api-consumer-abi"
    )
    rebuilt = EvidenceBundle.model_validate_json(bundle.model_dump_json())
    assert rebuilt == bundle
    assert rebuilt.run_id == "api-consumer-abi"
    assert report is None  # This witness has no numeric-estimation registry.
    if confounded:
        assert rebuilt.identification_status == "hedge_found"
        assert isinstance(certificate, NegativeCertificate)
    else:
        assert rebuilt.identification_status == "identified"
        assert certificate is None


def test_supported_facade_monkeypatch_executes_real_leaf_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A historical patch address must affect execution, then return to the real algorithm."""
    original = causal_engine.id_with_oracle_fallback
    calls: list[dict[str, object]] = []

    def observed_algorithm(**kwargs: object) -> IdentificationResult:
        calls.append(kwargs)
        return original(**kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, "id_with_oracle_fallback", observed_algorithm)
        result = causal_engine.CausalEngine().identify("X", "Y", _graph())
        assert result.status is IdentificationStatus.IDENTIFIED
        assert len(calls) == 1
        assert calls[0]["treatment"] == frozenset({"X"})
        assert calls[0]["outcome"] == frozenset({"Y"})

    restored = causal_engine.CausalEngine().identify("X", "Y", _graph())
    assert restored.status is IdentificationStatus.IDENTIFIED
    assert len(calls) == 1
    assert identification.id_with_oracle_fallback is original


def test_export_identity_proxy_misses_deleted_monkeypatch_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep public names and class identity while removing the runtime ABI property."""
    original = causal_engine.id_with_oracle_fallback
    calls: list[object] = []

    def observed_algorithm(**kwargs: object) -> IdentificationResult:
        calls.append(kwargs)
        return original(**kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(causal_engine, "id_with_oracle_fallback", observed_algorithm)
        patch.setattr(identification, "_sync_public_algorithm_overrides", lambda: None)
        # The cheap public-export/identity proxy is still green.
        api = importlib.import_module(f"{causal_engine.__name__}.api")
        assert causal_engine.CausalEngine is api.CausalEngine
        assert causal_engine.__all__ == ["CausalEngine", "DataReadinessBlockedError"]
        result = causal_engine.CausalEngine().identify("X", "Y", _graph())
        assert result.status is IdentificationStatus.IDENTIFIED
        assert calls == []  # The supported patch did not reach the real invocation.


@pytest.mark.parametrize("module", [causal_engine, interference])
def test_supported_objects_keep_leaf_fqns_and_pickle_identity(module: ModuleType) -> None:
    """Public symbols resolve from their serialized owner addresses without wrapper types."""
    for name in module.__all__:
        value = getattr(module, name)
        owner = importlib.import_module(value.__module__)
        assert getattr(owner, value.__qualname__) is value
        assert pickle.loads(pickle.dumps(value)) is value  # noqa: S301 - locally produced bytes


@pytest.mark.parametrize("module", [causal_engine, interference])
def test_runtime_documentation_renders_supported_facade(module: ModuleType) -> None:
    """Generate runtime API documentation from the actual modules, rather than source markers."""
    document = pydoc.plain(pydoc.render_doc(module))
    for name in module.__all__:
        assert name in document


def test_interference_serialized_result_consumed_via_supported_facade() -> None:
    """Identify cross-unit interference and read the resulting typed graph through the facade."""
    graph = CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=["T_1", "Y_1", "T_2", "Y_2"],
        edges=[
            CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
            for src, dst in [("T_1", "Y_1"), ("T_2", "Y_2"), ("T_1", "Y_2")]
        ],
    )
    result = interference.identify_interference_effect(graph, treatment="T_1", outcome="Y_1")
    rebuilt = interference.InterferenceIdentificationResult.model_validate_json(
        result.model_dump_json()
    )
    assert rebuilt == result
    assert rebuilt.interference_detected
    assert rebuilt.sutva_violated
    assert isinstance(rebuilt.augmented_graph, interference.InterferenceAugmentedGraph)
    assert rebuilt.augmented_graph.exposure_nodes == ("E__u0",)


def test_repository_literal_facade_imports_resolve() -> None:
    """Recompute all tracked Python literal callers and perform their actual imports.

    This denominator covers literal AST imports, including relative imports.
    It cannot establish computed import addresses or callers outside this repository.
    """
    root = next(parent for parent in Path(__file__).resolve().parents if (parent / ".git").exists())
    paths = subprocess.check_output(["git", "ls-files", "*.py"], cwd=root, text=True).splitlines()
    prefix = "polisyos.foundry.methods.catalog.causal"
    targets = {f"{prefix}.causal_engine", f"{prefix}.interference"}
    occurrences = 0
    callers: set[str] = set()
    for path in paths:
        source = (root / path).read_text()
        if "causal_engine" not in source and "interference" not in source:
            continue
        tree = ast.parse(source, filename=path)
        package = ""
        if "/src/" in path:
            address = path.split("/src/", 1)[1].removesuffix(".py").replace("/", ".")
            package = (
                address.removesuffix(".__init__")
                if address.endswith(".__init__")
                else address.rsplit(".", 1)[0]
            )
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level and package:
                    module = importlib.util.resolve_name("." * node.level + module, package)
                if module in targets:
                    names = [alias.name for alias in node.names]
                elif module == prefix:
                    names = [
                        alias.name for alias in node.names if f"{prefix}.{alias.name}" in targets
                    ]
                else:
                    continue
                if names:
                    # Execute the real from-import semantics, including submodule fallback.
                    namespace: dict[str, object] = {}
                    exec(f"from {module} import {', '.join(names)}", namespace)  # noqa: S102
                    occurrences += 1
                    callers.add(path)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in targets:
                        importlib.import_module(alias.name)
                        occurrences += 1
                        callers.add(path)
    assert occurrences > 0  # Positive control for an accidentally empty measurement.
    print(
        json.dumps(
            {
                "executing_party": "F/causal_api",
                "tracked_python_denominator": len(paths),
                "literal_import_occurrences": occurrences,
                "literal_import_files": len(callers),
                "unresolved_boundary": "computed import addresses and external callers",
            },
            sort_keys=True,
        )
    )
