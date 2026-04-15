from __future__ import annotations

from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType
from polisyos.scientist.governance.passes.human_review_pass import HumanReviewRequiredPass


def _graph_with_review_items() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tariff", "imports"],
        edges=[
            CausalEdge(
                src="tariff",
                dst="imports",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=True,
            )
        ],
        discovery_method="unit_test",
    )


def test_human_review_required_pass_emits_info_and_payload_in_strict() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_graph": _graph_with_review_items()},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_human_review_strict",
    )

    issues = HumanReviewRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "HUMAN_REVIEW_REQUESTED"
    assert issues[0].severity == IssueSeverity.INFO
    payload = ctx.state.get("human_review_request")
    assert isinstance(payload, dict)
    assert isinstance(payload.get("items"), list)
    assert len(payload["items"]) == 1


def test_human_review_required_pass_skips_non_strict() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_graph": _graph_with_review_items()},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_human_review_mvp",
    )

    issues = HumanReviewRequiredPass().validate(ctx)

    assert issues == []
    assert "human_review_request" not in ctx.state


def test_human_review_no_unsupported_edges_returns_empty() -> None:
    """Graph with all edges supported should not trigger review."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tariff", "imports"],
        edges=[
            CausalEdge(
                src="tariff",
                dst="imports",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=False,
            )
        ],
        discovery_method="unit_test",
    )
    ctx = PassContext(
        ir=None,
        state={"causal_graph": graph},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_human_review_supported",
    )
    issues = HumanReviewRequiredPass().validate(ctx)
    assert issues == []
    assert "human_review_request" not in ctx.state


def test_human_review_no_graph_returns_empty() -> None:
    """Without a causal graph, no review items should be collected."""
    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_human_review_no_graph",
    )
    issues = HumanReviewRequiredPass().validate(ctx)
    assert issues == []


def test_human_review_multiple_unsupported_edges() -> None:
    """Multiple unsupported edges should produce one issue listing all items."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["A", "B", "C"],
        edges=[
            CausalEdge(
                src="A", dst="B",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=True,
            ),
            CausalEdge(
                src="B", dst="C",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=True,
            ),
        ],
        discovery_method="unit_test",
    )
    ctx = PassContext(
        ir=None,
        state={"causal_graph": graph},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_human_review_multi",
    )
    issues = HumanReviewRequiredPass().validate(ctx)
    assert len(issues) == 1
    payload = ctx.state["human_review_request"]
    assert len(payload["items"]) == 2
    assert "2 governance item(s)" in issues[0].message


def test_human_review_with_edge_lag() -> None:
    """Unsupported edge with lag produces correct edge path format."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X", dst="Y",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=True,
                lag=3,
            ),
        ],
        discovery_method="unit_test",
    )
    ctx = PassContext(
        ir=None,
        state={"causal_graph": graph},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_human_review_lag",
    )
    issues = HumanReviewRequiredPass().validate(ctx)
    assert len(issues) == 1
    item = ctx.state["human_review_request"]["items"][0]
    assert item["edge"] == "X->Y@lag=3"


def test_human_review_invalid_graph_payload_emits_warning() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_graph": {"invalid": True}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_human_review_invalid",
    )

    issues = HumanReviewRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "HUMAN_REVIEW_GRAPH_INVALID"
    assert issues[0].severity == IssueSeverity.WARNING
    assert "human_review_request" not in ctx.state
