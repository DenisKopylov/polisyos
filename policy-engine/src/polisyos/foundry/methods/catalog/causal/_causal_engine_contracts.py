"""Contracts for the causal engine orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from polisyos.ir.analytics.causal import DataReadinessReport

if TYPE_CHECKING:
    from polisyos.ir import InterventionExpr, InterventionQuery
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


class _CausalEngineStaticHelpers(Protocol):
    """Describe static helpers shared by split CausalEngine mixins."""

    @staticmethod
    def _graph_artifact_ref(graph: CausalGraphModel) -> str: ...

    @staticmethod
    def _intervention_target_vars(intervention: InterventionExpr) -> frozenset[str]: ...

    @staticmethod
    def _effective_intervention_expr(
        intervention: InterventionExpr,
    ) -> InterventionExpr: ...

    @staticmethod
    def _effective_intervention_type_name(query: InterventionQuery) -> str: ...


class DataReadinessBlockedError(RuntimeError):
    """Typed pre-execution failure raised when an estimation path is not ready."""

    def __init__(self, report: DataReadinessReport, *, reason: str) -> None:
        self.report = report
        self.reason = reason
        super().__init__(reason)


__all__ = ["DataReadinessBlockedError"]
