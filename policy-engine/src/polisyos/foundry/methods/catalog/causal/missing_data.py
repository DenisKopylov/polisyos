"""missing_data — Foundry methods for M-graph missing data analysis.

Three registered methods in the ``causal.missing_data`` namespace:

  RecoverabilityTest  — test whether P(S) is recoverable from P*(V)
  OrderedRecovery     — build the recovery EstimandAST via ordered fixing operator
  FullLawIdentify     — two-stage pipeline: recover P(V) then identify P(Y|do(X))

All three are thin Foundry wrappers around pure algorithm functions in
``recoverability_engine.py``.

References
----------
Mohan, K. & Pearl, J. (2021). "Graphical Models for Processing Missing Data."
    Journal of the American Statistical Association.
Mohan, K., Pearl, J. & Tian, J. (2013). "Missing Data as a Causal and
    Probabilistic Problem." UAI 2013.
Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). "Full law identification in
    graphical models of missing data."
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, ClassVar, Mapping

_logger = logging.getLogger(__name__)

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _json_slot(name: str) -> SlotSpec:
    return SlotSpec(name, SlotType.SCALAR, Unit(name, "json"))


# ---------------------------------------------------------------------------
# RecoverabilityTest
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "recoverability", "m-graph"},
)
class RecoverabilityTest:
    """Test whether a query P(S) is recoverable from incomplete data.

    Implements the Mohan & Pearl (2021) graphical recoverability criterion
    (Theorem 1): P(S) is recoverable iff no R_V ∈ desc(V) in G' = G[V∪R \\ proxies].

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph" and
        ``metadata["mgraph"]`` containing the serialised MGraphMetadata.

    Output
    ------
    recoverability_result : dict
        status, query_variables, blocking_r_nodes, proof_steps, algorithm_version.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="recoverability_test",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset({_json_slot("recoverability_result")}),
        parameters=(
            ParameterSpec(name="query_variables", default=[]),
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Test recoverability of a query P(S) from incomplete data using "
            "the Mohan & Pearl (2021) M-graph graphical criterion."
        ),
        tags=frozenset({
            "causal", "missing-data", "recoverability", "m-graph",
            "mcar", "mar", "mnar",
        }),
        citations=(
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing "
            "Missing Data. Journal of the American Statistical Association.",
            "Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal "
            "and Probabilistic Problem. UAI 2013.",
        ),
        equations={
            "criterion": (
                "P(S) recoverable iff ∀V_i∈S: R_{V_i} ∉ desc(V_i) "
                "in G[V∪R \\ proxy_nodes]"
            ),
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "Before causal analysis when the dataset has systematic missing values; "
            "to determine whether identification is feasible."
        ),
        when_not_to_use="Data is fully observed (no missing values).",
        output_interpretation=(
            "status='recoverable' → safe to proceed with full law identification. "
            "status='not_recoverable' → blocking_r_nodes identifies MNAR variables "
            "that prevent recovery."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            test_recoverability,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw)
            if isinstance(raw, dict)
            else raw
        )
        meta = extract_mgraph_metadata(graph)

        qvars_raw = params.get("query_variables", [])
        query_vars = (
            frozenset(qvars_raw)
            if qvars_raw
            else frozenset(meta.substantive_vars)
        )

        result = test_recoverability(
            query_vars=query_vars,
            graph=graph,
            mgraph_meta=meta,
        )

        return {
            "recoverability_result": {
                "status": result.status.value,
                "query_variables": sorted(result.query_variables),
                "blocking_r_nodes": sorted(result.blocking_r_nodes),
                "proof_steps": [
                    {
                        "rule_name": s.rule_name,
                        "antecedent_vars": list(s.antecedent_vars),
                        "consequent_vars": list(s.consequent_vars),
                        "applied_to_graph_state": s.applied_to_graph_state,
                        "depth": s.depth,
                    }
                    for s in result.proof_steps
                ],
                "trace": result.trace,
                "algorithm_version": result.algorithm_version,
            }
        }


# ---------------------------------------------------------------------------
# OrderedRecovery
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "ordered-recovery", "m-graph"},
)
class OrderedRecovery:
    """Recover full-data joint P(V) from incomplete data via topological ordering.

    Implements the Mohan, Pearl & Tian (2013) ordered fixing operator:
        P(V) = Π_i P(V_i | V_{<i})
    Each factor is recovered as P*(V_i | V_{<i}, R_{V_i}=1) for MCAR/MAR variables.

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph".

    Output
    ------
    recovery_estimand : dict
        Serialised EstimandAST with ProductNode of RecoveredDistNode factors.
    ordered_recovery_steps : list[dict]
        Proof steps for the topological recovery sequence.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ordered_recovery",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({_json_slot("mgraph_data")}),
        output_slots=frozenset({
            _json_slot("recovery_estimand"),
            _json_slot("ordered_recovery_steps"),
        }),
        parameters=(
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Recover full-data joint P(V) from incomplete data using the "
            "ordered fixing operator (Mohan, Pearl & Tian 2013)."
        ),
        tags=frozenset({
            "causal", "missing-data", "ordered-recovery", "m-graph",
            "estimand", "fixing-operator",
        }),
        citations=(
            "Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal "
            "and Probabilistic Problem. UAI 2013.",
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing "
            "Missing Data. Journal of the American Statistical Association.",
        ),
        equations={
            "recovery": "P(V) = Π_i P(V_i | V_{<i})",
            "mcar_mar_factor": "P(V_i | V_{<i}) = P*(V_i | V_{<i}, R_{V_i}=1)",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "After RecoverabilityTest confirms P(V) is recoverable; "
            "to obtain the explicit recovery formula."
        ),
        when_not_to_use=(
            "RecoverabilityTest returned NOT_RECOVERABLE — ordered recovery "
            "will not produce a valid result."
        ),
        output_interpretation=(
            "recovery_estimand is an EstimandAST with a ProductNode of "
            "RecoveredDistNode factors.  Each factor specifies the data query "
            "(variable, conditioning, missingness_indicator, proxy_variable) "
            "needed to estimate that factor from the incomplete dataset."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            ordered_recovery,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw)
            if isinstance(raw, dict)
            else raw
        )
        meta = extract_mgraph_metadata(graph)
        dataset_ref = params.get("dataset_ref")

        estimand = ordered_recovery(
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
        )

        # Extract proof steps from the estimand's root factors
        steps = []
        from polisyos.ir.analytics.estimand import ProductNode, RecoveredDistNode
        if isinstance(estimand.root, ProductNode):
            for i, factor in enumerate(estimand.root.factors):
                if isinstance(factor, RecoveredDistNode):
                    steps.append({
                        "rule_name": "ORDERED_RECOVERY_STEP",
                        "variable": factor.variable,
                        "conditioning": list(factor.conditioning),
                        "missingness_kind": factor.missingness_kind,
                        "missingness_indicator": factor.missingness_indicator,
                        "proxy_variable": factor.proxy_variable,
                        "depth": i,
                    })

        return {
            "recovery_estimand": estimand.model_dump(mode="json"),
            "ordered_recovery_steps": steps,
        }


# ---------------------------------------------------------------------------
# FullLawIdentify
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.missing_data",
    version="1.0.0",
    tags={"causal", "missing-data", "full-law", "identification", "m-graph"},
)
class FullLawIdentify:
    """Identify P(Y|do(X)) from incomplete data using the full law pipeline.

    Two-stage pipeline (Nabi, Bhattacharya & Shpitser 2020):
      Stage 1: RecoverabilityTest — check if P(V) is recoverable from P*(V).
      Stage 2: ID algorithm — identify P(Y|do(X)) from recovered P(V).

    Input
    -----
    mgraph_data : dict
        Serialised CausalGraphModel with graph_type="mgraph".

    Output
    ------
    identification_result : dict
        status, estimand_ast, proof_steps, algorithm_version, trace.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="full_law_identify",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({
            _json_slot("mgraph_data"),
            _json_slot("treatment"),
            _json_slot("outcome"),
        }),
        output_slots=frozenset({_json_slot("identification_result")}),
        parameters=(
            ParameterSpec(name="oracle", default="none"),
            ParameterSpec(name="dataset_ref", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Identify causal effects from incomplete data via the full law pipeline "
            "(Nabi, Bhattacharya & Shpitser 2020): recover P(V) then identify P(Y|do(X))."
        ),
        tags=frozenset({
            "causal", "missing-data", "full-law", "identification",
            "m-graph", "id-algorithm",
        }),
        citations=(
            "Nabi, R., Bhattacharya, R. & Shpitser, I. (2020). Full law identification "
            "in graphical models of missing data.",
            "Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data. "
            "Journal of the American Statistical Association.",
        ),
        equations={
            "pipeline": "P(Y|do(X)) identified from incomplete data via two-stage pipeline",
            "stage1": "Recover P(V) = Π_i P*(V_i|V_{<i}, R_{V_i}=1)",
            "stage2": "Identify P(Y|do(X)) from P(V) via ID algorithm",
        },
        determinism_tier=DeterminismTier.STRICT_CPU,
        required_deps=("numpy",),
        when_to_use=(
            "Causal identification when input data has systematic missingness "
            "(MCAR/MAR/MNAR patterns confirmed via m-graph analysis)."
        ),
        when_not_to_use="Data is fully observed; use standard ID algorithm instead.",
        output_interpretation=(
            "status='identified' → both stages succeeded; estimand_ast contains "
            "the full identification formula. "
            "status='not_recoverable' → Stage 1 failed; identification is impossible "
            "without additional assumptions. "
            "status='hedge_found' / 'oracle_needed' → Stage 2 failed; the causal query "
            "is non-identifiable even with complete data."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            full_law_identify,
        )
        from polisyos.ir.analytics.causal_graph import CausalGraphModel
        from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

        raw = state["mgraph_data"]
        graph = (
            CausalGraphModel.model_validate(raw)
            if isinstance(raw, dict)
            else raw
        )
        meta = extract_mgraph_metadata(graph)

        treatment_raw = state["treatment"]
        outcome_raw = state["outcome"]
        treatment = (
            frozenset(treatment_raw)
            if isinstance(treatment_raw, (list, tuple, frozenset, set))
            else frozenset({str(treatment_raw)})
        )
        outcome = (
            frozenset(outcome_raw)
            if isinstance(outcome_raw, (list, tuple, frozenset, set))
            else frozenset({str(outcome_raw)})
        )

        oracle = str(params.get("oracle", "none"))
        dataset_ref = params.get("dataset_ref")

        result = full_law_identify(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
            oracle=oracle,
        )

        estimand_dict = (
            result.estimand_ast.model_dump(mode="json")
            if result.estimand_ast is not None
            else None
        )

        return {
            "identification_result": {
                "status": result.status.value,
                "estimand_ast": estimand_dict,
                "algorithm_version": result.algorithm_version,
                "trace": result.trace,
                "proof_steps": [
                    {
                        "rule_name": s.rule_name,
                        "antecedent_vars": list(s.antecedent_vars),
                        "consequent_vars": list(s.consequent_vars),
                        "applied_to_graph_state": s.applied_to_graph_state,
                        "depth": s.depth,
                    }
                    for s in result.proof_steps
                ],
            }
        }


__all__ = [
    "RecoverabilityTest",
    "OrderedRecovery",
    "FullLawIdentify",
]
