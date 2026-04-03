"""Public passes literature gate pass module API."""
from __future__ import annotations

from polisyos.common.logger import get_logger
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass
from polisyos.core.governance.profiles import ProfileLevel
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    load_causal_graph_model,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceNeedType,
    EvidenceStatus,
    load_cross_graph_evidence_profile,
)
from polisyos.ir.refs import CrossGraphEvidenceProfileRef

logger = get_logger(__name__)


class LiteratureGatePass(ValidatorPass):
    """Blocks unsupported causal edges in STRICT and warns in MVP."""

    @property
    def pass_id(self) -> str:
        return "literature_gate"

    @property
    def estimated_cost_ms(self) -> int:
        return 30

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if ctx.profile.level is ProfileLevel.FAST:
            return []

        profile = _resolve_cross_graph_profile(ctx)
        if profile is not None:
            return _issues_from_cross_graph_profile(ctx, profile)

        graph = _resolve_graph(ctx)
        if graph is None:
            return []

        severity = (
            IssueSeverity.BLOCKER
            if ctx.profile.level is ProfileLevel.STRICT
            else IssueSeverity.WARNING
        )
        issues: list[ComplianceIssue] = []
        for edge in graph.edges:
            if not edge.unsupported_by_evidence:
                continue
            sources = [source.value for source in edge.sources]
            issues.append(
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["causal_graph", "edges", _edge_path(edge)],
                    message=(
                        f"Edge {_edge_path(edge)} has sources={sources} "
                        "with no literature or data support."
                    ),
                    severity=severity,
                    code="LITERATURE_GATE_UNSUPPORTED_EDGE",
                    suggestion="Add peer-reviewed/data evidence or remove this edge.",
                )
            )
        return issues


def _issues_from_cross_graph_profile(
    ctx: PassContext,
    profile: CrossGraphEvidenceProfile,
) -> list[ComplianceIssue]:
    severity = (
        IssueSeverity.BLOCKER
        if ctx.profile.level is ProfileLevel.STRICT
        else IssueSeverity.WARNING
    )
    issues: list[ComplianceIssue] = []
    for assessment in profile.needs:
        if assessment.need.need_type is not EvidenceNeedType.CAUSAL_EDGE_NEED:
            continue
        if assessment.evidence_status is not EvidenceStatus.UNSUPPORTED:
            continue
        edge_label = f"{assessment.need.cause}->{assessment.need.effect}"
        issues.append(
            ComplianceIssue(
                pass_id="literature_gate",
                path=["cross_graph", assessment.need.need_id],
                message=f"Edge {edge_label} is unsupported by unified evidence profile.",
                severity=severity,
                code="LITERATURE_GATE_UNSUPPORTED_EDGE",
                suggestion="Add peer-reviewed/data evidence or remove this edge.",
            )
        )
    return issues


def _resolve_graph(ctx: PassContext) -> CausalGraphModel | None:
    direct = ctx.state.get("causal_graph")
    if isinstance(direct, CausalGraphModel):
        return direct
    if isinstance(direct, dict):
        try:
            return CausalGraphModel.model_validate(direct)
        except Exception:
            logger.warning(
                "Failed to parse CausalGraphModel from dict",
                exc_info=True,
            )
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
        logger.warning(
            "Failed to load causal graph model from ref %s",
            ref,
            exc_info=True,
        )
        return None


def _resolve_cross_graph_profile(ctx: PassContext) -> CrossGraphEvidenceProfile | None:
    artifacts_index = ctx.state.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return None
    raw_ref = artifacts_index.get("cross_graph_evidence_profile_ref")
    if raw_ref is None:
        return None

    store = ctx.state.get("_store")
    if store is None:
        return None
    try:
        ref = CrossGraphEvidenceProfileRef.model_validate(raw_ref)
        return load_cross_graph_evidence_profile(store, ref)
    except Exception:
        logger.debug(
            "Failed to resolve cross-graph evidence profile from ref %s",
            raw_ref,
            exc_info=True,
        )
        return None


def _edge_path(edge: CausalEdge) -> str:
    if edge.lag is None:
        return f"{edge.src}->{edge.dst}"
    return f"{edge.src}->{edge.dst}@lag={edge.lag}"


__all__ = ["LiteratureGatePass"]
