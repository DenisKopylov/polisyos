"""Phase 4.3 characterization tests for the id_engine god-module budget."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

from polisyos.foundry.methods._internal import logging as _foundry_logging

# Phase 4.3 can land alongside the Foundry method-package split. During that
# split, legacy package bootstrap still imports the old logging shim name and
# the catalog facade may be mid-migration. Keep this characterization file
# focused on id_engine semantics instead of catalog bootstrap side effects.
sys.modules.setdefault("polisyos.foundry.methods._logging", _foundry_logging)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_CATALOG_ROOT = _REPO_ROOT / "src" / "polisyos" / "foundry" / "methods" / "catalog"
_CAUSAL_ROOT = _CATALOG_ROOT / "causal"

catalog_pkg = sys.modules.setdefault(
    "polisyos.foundry.methods.catalog",
    types.ModuleType("polisyos.foundry.methods.catalog"),
)
catalog_pkg.__path__ = [str(_CATALOG_ROOT)]  # type: ignore[attr-defined]
causal_pkg = sys.modules.setdefault(
    "polisyos.foundry.methods.catalog.causal",
    types.ModuleType("polisyos.foundry.methods.catalog.causal"),
)
causal_pkg.__path__ = [str(_CAUSAL_ROOT)]  # type: ignore[attr-defined]

_id_contracts = importlib.import_module("polisyos.foundry.methods.catalog.causal._id_contracts")
_id_engine = importlib.import_module("polisyos.foundry.methods.catalog.causal.id_engine")
_causal_graph = importlib.import_module("polisyos.ir.analytics.causal_graph")

IdentificationStatus = _id_contracts.IdentificationStatus
id_algorithm = _id_engine.id_algorithm
idc_algorithm = _id_engine.idc_algorithm
CausalEdge = _causal_graph.CausalEdge
CausalGraphModel = _causal_graph.CausalGraphModel
EdgeMark = _causal_graph.EdgeMark
GraphType = _causal_graph.GraphType


def _edge(src: str, dst: str, *, bidirected: bool = False) -> CausalEdge:
    if bidirected:
        return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def _dag(edges: list[tuple[str, str]], *, extra_nodes: tuple[str, ...] = ()) -> CausalGraphModel:
    nodes = sorted({node for edge in edges for node in edge} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[_edge(src, dst) for src, dst in edges],
    )


def _admg(nodes: list[str], edges: list[CausalEdge]) -> CausalGraphModel:
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=nodes, edges=edges)


def _formula(result: object) -> str | None:
    estimand = getattr(result, "estimand_ast", None)
    return estimand.to_latex() if estimand is not None else None


def _proof_rules(result: object) -> list[str]:
    return [step.rule_name for step in getattr(result, "proof_steps", [])]


def _required_distribution_snapshot(result: object) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    return [
        (tuple(distribution.variables), tuple(distribution.conditioning))
        for distribution in getattr(result, "required_distributions", [])
    ]


@pytest.mark.parametrize(
    ("case_name", "graph", "expected_formula", "expected_rules", "expected_distributions"),
    [
        (
            "direct_dag",
            _dag([("X", "Y")]),
            r"P(Y \mid X)",
            ["G_FORMULA"],
            [(("Y",), ("X",))],
        ),
        (
            "backdoor_dag",
            _dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
            r"\sum_{Z} P(Z) \cdot P(Y \mid X, Z)",
            ["G_FORMULA"],
            [(("Z",), ()), (("Y",), ("X", "Z"))],
        ),
        (
            "frontdoor_admg",
            _admg(
                ["X", "M", "Y"],
                [_edge("X", "M"), _edge("M", "Y"), _edge("X", "Y", bidirected=True)],
            ),
            r"\sum_{M} P(M \mid X) \cdot \sum_{X} P(Y \mid M, X) \cdot P(X)",
            ["FRONTDOOR"],
            [(("M",), ("X",)), (("Y",), ("M", "X")), (("X",), ())],
        ),
    ],
)
def test_id_algorithm_identified_characterization_snapshots(
    case_name: str,
    graph: CausalGraphModel,
    expected_formula: str,
    expected_rules: list[str],
    expected_distributions: list[tuple[tuple[str, ...], tuple[str, ...]]],
) -> None:
    result = id_algorithm(treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph)

    assert result.status is IdentificationStatus.IDENTIFIED, case_name
    assert _formula(result) == expected_formula
    assert _proof_rules(result) == expected_rules
    assert result.hedge_certificate is None
    assert _required_distribution_snapshot(result) == expected_distributions


def test_id_algorithm_hedge_certificate_characterization_snapshot() -> None:
    result = id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=_admg(
            ["X", "Y"],
            [_edge("X", "Y"), _edge("X", "Y", bidirected=True)],
        ),
    )

    assert result.status is IdentificationStatus.HEDGE_FOUND
    assert _formula(result) is None
    assert _proof_rules(result) == ["HEDGE"]

    certificate = result.hedge_certificate
    assert certificate is not None
    assert certificate.treatment == frozenset({"X"})
    assert certificate.outcome == frozenset({"Y"})
    assert certificate.hedge_forest == frozenset({"X", "Y"})
    assert certificate.hedge_root == frozenset({"Y"})
    assert certificate.c_component_witness == frozenset({"Y"})
    assert certificate.minimal_required_s_nodes == frozenset({"Y"})
    assert certificate.required_data is not None
    assert certificate.required_data.missing_distributions == ()
    assert certificate.required_data.suggested_experiment is None
    assert "NOT identifiable" in certificate.description


def test_idc_algorithm_ratio_characterization_snapshot() -> None:
    result = idc_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        conditions=frozenset({"Z"}),
        graph=_dag([("Z", "X"), ("Z", "Y"), ("X", "Y")]),
    )

    assert result.status is IdentificationStatus.IDENTIFIED
    assert _formula(result) == r"\frac{P(Z) \cdot P(Y \mid X, Z)}{P(Z)}"
    assert _proof_rules(result) == [
        "IDC_DECOMPOSE",
        "IDC_POSITIVITY",
        "G_FORMULA",
        "ANCESTRAL_COLLAPSE",
        "RULE1",
    ]
    assert result.trace == [
        "idc_algorithm: Y=['Y'], X=['X'], Z=['Z']",
        "idc_algorithm: IDENTIFIED via ratio",
    ]
