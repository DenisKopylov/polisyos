"""CausalQueryValidator — pre-flight validation of causal queries.

Validates a (graph, EstimandAST, DataKnowledgeBase?) triple before
identification and estimation begin. Returns a structured QueryValidationReport.

Design mirrors SchemaResolver: plain Python class, lazy imports, no @foundry_method.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from polisyos.ir.analytics.query_validation_report import (
    QueryValidationReport,
    ValidationError,
    ValidationWarning,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel
    from polisyos.ir.analytics.estimand import EstimandAST
    from polisyos.ir.analytics.knowledge_base import DataKnowledgeBase


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_SMALL_SAMPLE_THRESHOLD: int = 100
_INFEASIBLE_SCORE_THRESHOLD: float = 0.3
_PARTIAL_SCORE_THRESHOLD: float = 1.0

# Heuristic pattern for S-node variable names added by tr_algorithm
_S_NODE_PATTERN: re.Pattern[str] = re.compile(r"^S(_\w+)?$")


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class CausalQueryValidator:
    """Validates a causal query against a graph and (optionally) a knowledge base.

    Checks performed:

    F2 structural (always):
      - Graph acyclicity for directed edges
      - treatment / outcome ∈ graph.nodes
      - treatment ≠ outcome
      - all EstimandAST variables ∈ graph.nodes (catches dangling S-nodes)

    F2 + F3 KB-gated (only when knowledge_base is provided):
      - required_datasets() ⊆ KB.all_dataset_refs()
      - domain labels in DistributionRefs consistent with KB entries
      - SideCondition feasibility per variable coverage in KB
      - overall KB feasibility score
      - sample-size warnings per DatasetEntry
    """

    def validate(
        self,
        graph: "CausalGraphModel",
        estimand_ast: "EstimandAST",
        knowledge_base: "DataKnowledgeBase | None" = None,
    ) -> QueryValidationReport:
        """Run all validation checks and return a structured report.

        Args:
            graph: Causal graph (DAG / CPDAG / PAG).
            estimand_ast: Symbolic estimand produced by the identification engine.
            knowledge_base: Optional data registry. If omitted, only structural
                checks (F2) are performed.

        Returns:
            QueryValidationReport with is_valid=True iff no errors were found.
        """
        errors: list[ValidationError] = []
        warnings: list[ValidationWarning] = []

        # F2 — structural checks (always)
        self._check_graph_acyclicity(graph, errors, warnings)
        self._check_treatment_in_graph(graph, estimand_ast, errors)
        self._check_outcome_in_graph(graph, estimand_ast, errors)
        self._check_treatment_not_equals_outcome(estimand_ast, errors)
        self._check_all_vars_in_graph(graph, estimand_ast, warnings)

        # F2 + F3 — KB-gated checks
        if knowledge_base is not None:
            self._check_datasets_present(estimand_ast, knowledge_base, errors)
            self._check_domain_labels_consistent(estimand_ast, knowledge_base, warnings)
            self._check_side_condition_feasibility(estimand_ast, knowledge_base, warnings)
            self._check_kb_coverage(estimand_ast, knowledge_base, errors, warnings)
            self._check_sample_sizes(knowledge_base, warnings)

        return QueryValidationReport(
            is_valid=len(errors) == 0,
            errors=tuple(errors),
            warnings=tuple(warnings),
            query_str=estimand_ast.query_str if hasattr(estimand_ast, "query_str") else "",
            checked_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # F2 structural checks
    # ------------------------------------------------------------------

    def _check_graph_acyclicity(
        self,
        graph: "CausalGraphModel",
        errors: list[ValidationError],
        warnings: list[ValidationWarning],
    ) -> None:
        """Check that the directed subgraph contains no cycles."""
        from polisyos.foundry.methods.catalog.causal.admg_ops import topological_order
        from polisyos.ir.analytics.causal_graph import GraphType

        try:
            topological_order(graph)
        except ValueError as exc:
            detail = str(exc)
            if graph.graph_type is GraphType.DAG:
                errors.append(
                    ValidationError(
                        code="GRAPH_CYCLE",
                        message=(
                            "DAG contains a directed cycle in its contemporaneous edges. "
                            "Identification requires an acyclic graph."
                        ),
                        context={"detail": detail, "graph_type": graph.graph_type.value},
                    )
                )
            else:
                # CPDAG / PAG — orientation is uncertain; cycle may not be real
                warnings.append(
                    ValidationWarning(
                        code="GRAPH_CYCLE",
                        message=(
                            f"{graph.graph_type.value.upper()} contains a directed cycle in its "
                            "contemporaneous edges. For PAG/CPDAG this may reflect uncertain "
                            "orientation; verify the graph before proceeding."
                        ),
                        context={"detail": detail, "graph_type": graph.graph_type.value},
                    )
                )

    def _check_treatment_in_graph(
        self,
        graph: "CausalGraphModel",
        estimand_ast: "EstimandAST",
        errors: list[ValidationError],
    ) -> None:
        treatment = getattr(estimand_ast, "treatment", None)
        if treatment and treatment not in graph.nodes:
            errors.append(
                ValidationError(
                    code="TREATMENT_MISSING",
                    message=f"Treatment variable '{treatment}' is not in the graph nodes.",
                    context={"variable": treatment, "graph_nodes": sorted(graph.nodes)},
                )
            )

    def _check_outcome_in_graph(
        self,
        graph: "CausalGraphModel",
        estimand_ast: "EstimandAST",
        errors: list[ValidationError],
    ) -> None:
        outcome = getattr(estimand_ast, "outcome", None)
        if outcome and outcome not in graph.nodes:
            errors.append(
                ValidationError(
                    code="OUTCOME_MISSING",
                    message=f"Outcome variable '{outcome}' is not in the graph nodes.",
                    context={"variable": outcome, "graph_nodes": sorted(graph.nodes)},
                )
            )

    def _check_treatment_not_equals_outcome(
        self,
        estimand_ast: "EstimandAST",
        errors: list[ValidationError],
    ) -> None:
        treatment = getattr(estimand_ast, "treatment", None)
        outcome = getattr(estimand_ast, "outcome", None)
        if treatment and outcome and treatment == outcome:
            errors.append(
                ValidationError(
                    code="TREATMENT_EQUALS_OUTCOME",
                    message=(
                        f"Treatment and outcome refer to the same variable '{treatment}'. "
                        "A variable cannot cause itself."
                    ),
                    context={"variable": treatment},
                )
            )

    def _check_all_vars_in_graph(
        self,
        graph: "CausalGraphModel",
        estimand_ast: "EstimandAST",
        warnings: list[ValidationWarning],
    ) -> None:
        """Warn for every estimand variable that is absent from the graph.

        S-node variables (matching ``^S(_\\w+)?$``) get the more specific
        code ``S_NODE_DANGLING`` for clearer transportability debugging.
        """
        all_vars: tuple[str, ...] = getattr(estimand_ast, "all_variables", ())
        graph_nodes = set(graph.nodes)
        for var in sorted(all_vars):
            if var not in graph_nodes:
                code = "S_NODE_DANGLING" if _S_NODE_PATTERN.match(var) else "UNKNOWN_VARIABLE"
                warnings.append(
                    ValidationWarning(
                        code=code,
                        message=(
                            f"Variable '{var}' appears in the estimand but is not in the graph."
                        ),
                        context={"variable": var},
                    )
                )

    # ------------------------------------------------------------------
    # F2 KB-gated structural checks
    # ------------------------------------------------------------------

    def _check_datasets_present(
        self,
        estimand_ast: "EstimandAST",
        knowledge_base: "DataKnowledgeBase",
        errors: list[ValidationError],
    ) -> None:
        """Verify every required dataset_ref is registered in the KB."""
        known = set(knowledge_base.all_dataset_refs())
        required: list[str] = (
            estimand_ast.required_datasets()
            if hasattr(estimand_ast, "required_datasets")
            else []
        )
        for ref in required:
            if ref not in known:
                errors.append(
                    ValidationError(
                        code="DATASET_MISSING",
                        message=(
                            f"Dataset '{ref}' is required by the estimand but not found "
                            "in the knowledge base."
                        ),
                        context={"dataset_ref": ref, "available_refs": sorted(known)},
                    )
                )

    def _check_domain_labels_consistent(
        self,
        estimand_ast: "EstimandAST",
        knowledge_base: "DataKnowledgeBase",
        warnings: list[ValidationWarning],
    ) -> None:
        """Warn when a DistributionRef's domain disagrees with its matched KB entry."""
        dist_refs = (
            estimand_ast.collect_distribution_refs()
            if hasattr(estimand_ast, "collect_distribution_refs")
            else []
        )
        # Build a lookup: dataset_ref → domain from KB
        kb_domain: dict[str, str] = {
            entry.dataset_ref: entry.domain.value for entry in knowledge_base.datasets
        }
        seen: set[tuple[str, str]] = set()  # avoid duplicate warnings
        for dr in dist_refs:
            ref = dr.dataset_ref
            if ref is None or ref not in kb_domain:
                continue
            key = (ref, dr.domain.value)
            if key in seen:
                continue
            seen.add(key)
            if kb_domain[ref] != dr.domain.value:
                warnings.append(
                    ValidationWarning(
                        code="DOMAIN_MISMATCH",
                        message=(
                            f"DistributionRef uses domain='{dr.domain.value}' for dataset "
                            f"'{ref}', but the KB entry has domain='{kb_domain[ref]}'."
                        ),
                        context={
                            "dataset_ref": ref,
                            "estimand_domain": dr.domain.value,
                            "kb_domain": kb_domain[ref],
                        },
                    )
                )

    # ------------------------------------------------------------------
    # F3 feasibility checks
    # ------------------------------------------------------------------

    def _check_side_condition_feasibility(
        self,
        estimand_ast: "EstimandAST",
        knowledge_base: "DataKnowledgeBase",
        warnings: list[ValidationWarning],
    ) -> None:
        """Check data sufficiency for each SideCondition in the estimand."""
        from polisyos.ir.analytics.estimand import SideConditionKind

        treatment = getattr(estimand_ast, "treatment", "")

        # Collect all side conditions: top-level + per-DistributionRef
        side_conditions: list = list(getattr(estimand_ast, "side_conditions", ()))
        dist_refs = (
            estimand_ast.collect_distribution_refs()
            if hasattr(estimand_ast, "collect_distribution_refs")
            else []
        )
        for dr in dist_refs:
            side_conditions.extend(dr.side_conditions)

        # For POSITIVITY/OVERLAP/CONSISTENCY: check treatment var coverage in KB
        treatment_covered = _treatment_covered_in_kb(treatment, knowledge_base)

        emitted_positivity = False
        emitted_consistency = False
        for sc in side_conditions:
            if sc.kind in (SideConditionKind.POSITIVITY, SideConditionKind.OVERLAP):
                if not emitted_positivity and not treatment_covered:
                    warnings.append(
                        ValidationWarning(
                            code="POSITIVITY_DATA_ABSENT",
                            message=(
                                f"SideCondition '{sc.kind.value}' requires treatment "
                                f"variable '{treatment}' to be present in a source-domain "
                                "dataset, but no matching entry was found in the knowledge base."
                            ),
                            context={"treatment": treatment, "side_condition": sc.kind.value},
                        )
                    )
                    emitted_positivity = True

            elif sc.kind is SideConditionKind.CONSISTENCY:
                if not emitted_consistency and not treatment_covered:
                    warnings.append(
                        ValidationWarning(
                            code="CONSISTENCY_DATA_ABSENT",
                            message=(
                                f"SideCondition 'consistency' requires treatment variable "
                                f"'{treatment}' to be present in the knowledge base."
                            ),
                            context={"treatment": treatment},
                        )
                    )
                    emitted_consistency = True

            # SUTVA / NO_INTERFERENCE / TIME_STATIONARITY / EXCLUSION_RESTRICTION
            # are design assumptions — no data check needed; no warnings emitted.

    def _check_kb_coverage(
        self,
        estimand_ast: "EstimandAST",
        knowledge_base: "DataKnowledgeBase",
        errors: list[ValidationError],
        warnings: list[ValidationWarning],
    ) -> None:
        """Check overall feasibility score from the KB."""
        score, missing_refs = knowledge_base.score_estimand(estimand_ast)

        if score < _INFEASIBLE_SCORE_THRESHOLD:
            errors.append(
                ValidationError(
                    code="KB_INFEASIBLE",
                    message=(
                        f"Knowledge base feasibility score {score:.2f} is below the minimum "
                        f"threshold {_INFEASIBLE_SCORE_THRESHOLD:.2f}. The estimand cannot be "
                        "estimated from the available data."
                    ),
                    context={
                        "feasibility_score": score,
                        "missing_dataset_refs": missing_refs,
                    },
                )
            )
        elif score < _PARTIAL_SCORE_THRESHOLD:
            warnings.append(
                ValidationWarning(
                    code="KB_PARTIAL",
                    message=(
                        f"Knowledge base feasibility score {score:.2f} < 1.0. Some distributions "
                        "required by the estimand are only partially covered or available as "
                        "proxy data."
                    ),
                    context={
                        "feasibility_score": score,
                        "missing_dataset_refs": missing_refs,
                    },
                )
            )

    def _check_sample_sizes(
        self,
        knowledge_base: "DataKnowledgeBase",
        warnings: list[ValidationWarning],
    ) -> None:
        """Warn for datasets whose sample size is below the minimum threshold."""
        for entry in knowledge_base.datasets:
            if entry.n_obs is not None and entry.n_obs < _SMALL_SAMPLE_THRESHOLD:
                warnings.append(
                    ValidationWarning(
                        code="SMALL_SAMPLE",
                        message=(
                            f"Dataset '{entry.dataset_ref}' has only {entry.n_obs} observations "
                            f"(minimum recommended: {_SMALL_SAMPLE_THRESHOLD}). Estimates may be "
                            "unreliable."
                        ),
                        context={
                            "dataset_ref": entry.dataset_ref,
                            "n_obs": entry.n_obs,
                            "threshold": _SMALL_SAMPLE_THRESHOLD,
                        },
                    )
                )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _treatment_covered_in_kb(treatment: str, knowledge_base: "DataKnowledgeBase") -> bool:
    """Return True if treatment variable appears in any source-domain KB dataset."""
    if not treatment:
        return True  # no treatment to check
    from polisyos.ir.analytics.estimand import DistributionDomain

    for entry in knowledge_base.datasets:
        if entry.domain is DistributionDomain.SOURCE and treatment in entry.variables:
            return True
    return False


__all__ = ["CausalQueryValidator"]
