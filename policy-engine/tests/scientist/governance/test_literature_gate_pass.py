from __future__ import annotations

from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeSource, GraphType
from polisyos.scientist.governance.passes.literature_gate_pass import LiteratureGatePass


def _graph_with_unsupported_edge() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["tax_rate", "gdp_growth"],
        edges=[
            CausalEdge(
                src="tax_rate",
                dst="gdp_growth",
                sources=[EdgeSource.LLM_PRIOR],
                unsupported_by_evidence=True,
            )
        ],
        discovery_method="unit_test",
    )


def test_literature_gate_fast_skips() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_graph": _graph_with_unsupported_edge()},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="R_lit_fast",
    )

    issues = LiteratureGatePass().validate(ctx)

    assert issues == []


def test_literature_gate_mvp_warns() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_graph": _graph_with_unsupported_edge()},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_lit_mvp",
    )

    issues = LiteratureGatePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "LITERATURE_GATE_UNSUPPORTED_EDGE"
    assert issues[0].severity == IssueSeverity.WARNING


def test_literature_gate_strict_blocks() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_graph": _graph_with_unsupported_edge()},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_lit_strict",
    )

    issues = LiteratureGatePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "LITERATURE_GATE_UNSUPPORTED_EDGE"
    assert issues[0].severity == IssueSeverity.BLOCKER
