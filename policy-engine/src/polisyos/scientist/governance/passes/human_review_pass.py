"""Request explicit human review when a STRICT run still carries review-sensitive graph state."""
from __future__ import annotations

from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    load_causal_graph_model,
)


class HumanReviewRequiredPass(ValidatorPass):
    """Emit `HUMAN_REVIEW_REQUESTED` and populate `human_review_request` state.

    The pass runs only under `ProfileLevel.STRICT` and resolves a direct
    `causal_graph`, `causal_graph_ref`, or graph artifact ref via `_store`.
    Findings are informational, but downstream human-gate orchestration consumes
    the written state payload.
    """

    @property
    def pass_id(self) -> str:
        return "human_review_required"

    @property
    def estimated_cost_ms(self) -> int:
        return 50

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.profile.level is not ProfileLevel.STRICT:
            return []

        review_items = _collect_review_items(ctx)
        if not review_items:
            return []

        ctx.state["human_review_request"] = {
            "items": review_items,
            "created_by": "governance.human_review_required",
            "deadline_hours": 72,
        }
        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["human_review"],
                message=f"Human review requested for {len(review_items)} governance item(s).",
                severity=IssueSeverity.INFO,
                code="HUMAN_REVIEW_REQUESTED",
            )
        ]


def _collect_review_items(ctx: PassContext) -> list[dict[str, object]]:
    graph = _resolve_graph(ctx)
    if graph is None:
        return []

    items: list[dict[str, object]] = []
    for edge in graph.edges:
        if not edge.unsupported_by_evidence:
            continue
        items.append(
            {
                "kind": "unsupported_edge",
                "edge": _edge_path(edge),
                "sources": [source.value for source in edge.sources],
                "reason": "unsupported_by_evidence",
            }
        )
    return items


def _resolve_graph(ctx: PassContext) -> CausalGraphModel | None:
    direct = ctx.state.get("causal_graph")
    if isinstance(direct, CausalGraphModel):
        return direct
    if isinstance(direct, dict):
        try:
            return CausalGraphModel.model_validate(direct)
        except Exception:
            return None

    ref = ctx.state.get("causal_graph_ref")
    if ref is None:
        artifacts_index = ctx.state.get("artifacts_index")
        if isinstance(artifacts_index, dict):
            ref = artifacts_index.get("causal_graph_ref")
    if ref is None:
        return None

    store = ctx.state.get("_store")
    if store is None:
        return None
    try:
        return load_causal_graph_model(store, ref)
    except Exception:
        return None


def _edge_path(edge: CausalEdge) -> str:
    if edge.lag is None:
        return f"{edge.src}->{edge.dst}"
    return f"{edge.src}->{edge.dst}@lag={edge.lag}"


__all__ = ["HumanReviewRequiredPass"]
