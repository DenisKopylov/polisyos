"""Request explicit human review when a STRICT run still carries review-sensitive graph state."""

from __future__ import annotations

from polisyos.common.logger import get_logger
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    CausalGraphModelRef,
    load_causal_graph_model,
)
from polisyos.scientist.governance.passes._artifact_resolution import (
    ArtifactResolution,
    resolve_optional_artifact_model,
)

logger = get_logger(__name__)


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

        graph_resolution = _resolve_graph(ctx)
        review_items = _collect_review_items(graph_resolution.value)
        if not review_items:
            return list(graph_resolution.issues)

        ctx.state["human_review_request"] = {
            "items": review_items,
            "created_by": "governance.human_review_required",
            "deadline_hours": 72,
        }
        return [
            *graph_resolution.issues,
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["human_review"],
                message=f"Human review requested for {len(review_items)} governance item(s).",
                severity=IssueSeverity.INFO,
                code="HUMAN_REVIEW_REQUESTED",
            ),
        ]


def _collect_review_items(graph: CausalGraphModel | None) -> list[dict[str, object]]:
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


def _resolve_graph(ctx: PassContext) -> ArtifactResolution[CausalGraphModel]:
    return resolve_optional_artifact_model(
        ctx=ctx,
        pass_id="human_review_required",
        direct_key="causal_graph",
        ref_key="causal_graph_ref",
        model_cls=CausalGraphModel,
        ref_model=CausalGraphModelRef,
        load_model=load_causal_graph_model,
        severity=IssueSeverity.WARNING,
        code="HUMAN_REVIEW_GRAPH_INVALID",
        message="Causal graph could not be validated or loaded for human review.",
        suggestion="Rebuild the causal graph artifact before strict governance review.",
        log=logger,
    )


def _edge_path(edge: CausalEdge) -> str:
    if edge.lag is None:
        return f"{edge.src}->{edge.dst}"
    return f"{edge.src}->{edge.dst}@lag={edge.lag}"


__all__ = ["HumanReviewRequiredPass"]
