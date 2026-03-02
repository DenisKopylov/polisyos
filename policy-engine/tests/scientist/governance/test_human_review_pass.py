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
