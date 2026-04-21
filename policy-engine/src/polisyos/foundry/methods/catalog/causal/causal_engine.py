"""CausalEngine — Pearl-Bareinboim causal inference orchestrator.

Wires together identification (id_engine), compilation (estimand_compiler),
estimation (foundry methods), and audit trail (EvidenceBundle).

Usage::

    engine = CausalEngine(registry=MethodRegistry.get_instance(), knowledge_base=kb)
    report, bundle, cert = engine.run(
        treatment="X", outcome="Y", graph=graph, data_dict=data,
        s_nodes=s_nodes, n_obs=500,
    )
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from polisyos.ir.canon import CanonSpec
from polisyos.ir.analytics.causal import (
    DataReadinessReport,
    EstimationStatus,
    ProofBundle,
    build_data_readiness_report,
    build_dynamic_proof_bundle,
    persist_data_readiness_report,
    persist_proof_bundle,
    proof_bundle_from_negative_certificate,
    proof_bundle_from_identification_result,
    proof_bundle_from_proximal_certificate,
)
from polisyos.ir.analytics.dual_certificate import hydrate_bounds_bundle_with_dual_certificate
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.dynamic_causal_semantics import (
    DynamicReductionStatus,
    DynamicScopeStatement,
    DynamicSemanticsAttachment,
    DynamicSemanticsFamily,
    GraphicalMarkovCertificate,
    GraphicalOracleKind,
    InterventionKind,
    InterventionScope,
    LocalIndependenceAttachment,
    SeparationClaim,
    WellPosednessStatus,
    WellPosednessWitness,
)
from polisyos.ir.analytics.frontier import (
    FrontierSketch,
    persist_frontier_sketch,
)
from polisyos.ir.analytics.estimand import (
    DistributionLawQuery,
    DistributionRef,
    EdgeInterventionAssignment,
    EdgeInterventionNode,
    EstimandAST,
    ModifiedTreatmentPolicyNode,
    PathSpecificNode,
    StochasticInterventionNode,
    StochasticPolicy,
    make_distribution_law_estimand,
)
from polisyos.ir.analytics.interventions import (
    CompositeIntervention,
    ConditionalIntervention,
    ConditionalPolicy,
    EdgeIntervention,
    InterferenceIntervention,
    InterventionCertificate,
    InterventionFallback,
    InterventionFallbackMode,
    InterventionIdentificationStatus,
    InterventionQuery,
    MTPIntervention,
    ModifiedTreatmentPolicySpec,
    NodeIntervention,
    PathIntervention,
    QueryTarget,
    QueryTargetKind,
    StochasticIntervention,
    StochasticPolicySpec,
    TransportIntervention,
    VariableAssignment,
    build_intervention_certificate,
    certificate_for_typecheck_failure,
    check_intervention_composition,
    persist_intervention_certificate,
    persist_intervention_query,
    render_intervention_query,
)
from polisyos.ir.analytics.local_independence import (
    CensoringInterventionSpec,
    EliminabilityCheck,
    EliminabilityStep,
    IndependentCensoringCheck,
    IntensityModelRequirement,
    LocalIndependenceEdge,
    LocalIndependenceGraphicalChecks,
    LocalIndependenceGraphSpec,
    LocalIndependenceIdentificationSpec,
    LocalIndependenceRuntimeRequirements,
    LocalIndependenceTarget,
    LocalIndependenceWeightingCertificate,
    TreatmentIntensityInterventionSpec,
    persist_local_independence_weighting_certificate,
)
from polisyos.ir.analytics.proximal import (
    BridgePlausibilityReport,
    ProximalIdentificationCertificate,
    ProxyAnnotation,
    persist_bridge_plausibility_report,
    persist_proximal_identification_certificate,
)
from polisyos.ir.analytics.recoverability import (
    JointDecisionCertificate,
    RecoverabilityCertificate,
    persist_joint_decision_certificate,
    persist_recoverability_certificate,
)
from polisyos.ir.analytics.evidence_bundle import (
    CompilationStep,
    DataProvenance,
    EstimationStep,
    EvidenceBundle,
    ProofStep as IRProofStep,
    _fingerprint,
    persist_causal_evidence_bundle,
)
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    EpistemicTier,
    FallbackResult,
    NegativeCertificate,
    ParametricRescueResult,
    persist_negative_certificate,
    recovery_plan_from_negative_certificate,
)
from polisyos.ir.analytics.partial_identification import (
    BoundsBundle,
    bounds_bundle_from_partial_identification_result,
    persist_bounds_bundle,
)
from polisyos.ir.analytics.proof_composability import (
    attach_proof_composability_to_proof_bundle,
    persist_proof_composability_certificate,
    persist_proof_witness_index,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    EffectTrajectoryBundle,
    InterventionInterpolationPolicy,
    StrategicAdaptationMode,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionTrajectory,
    TemporalQueryMode,
    TemporalSamplingScheme,
    load_temporal_intervention_trajectory,
    persist_continuous_time_query,
    persist_dynamic_treatment_regime,
    persist_effect_trajectory_bundle,
    persist_temporal_identification_certificate,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, put_json_artifact
from polisyos.ir.refs import (
    ArtifactRefModel,
    DynamicTreatmentRegimeRef,
    TemporalIdentificationCertificateRef,
    TemporalInterventionTrajectoryRef,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
    id_algorithm,
    id_star_algorithm,
    idc_star_algorithm,
    idc_algorithm,
    id_with_oracle_fallback,
    z_id_algorithm,
    mz_id_algorithm,
    tr_algorithm,
    # Phase-5 additions
    sid_algorithm,
    conditional_intervention_id,
    dynamic_intervention_id,
    joint_id_algorithm,
    multi_outcome_id,
)
from polisyos.foundry.methods.catalog.causal.local_independence_id import (
    build_temporal_identification_certificate,
    li_id_algorithm,
)
from polisyos.foundry.methods.catalog.causal.proof_trace_composability import (
    build_witness_index_from_proof_steps,
    check_proof_trace_composability,
)
from polisyos.foundry.methods.catalog.causal.proximal_identify import proximal_identify_v1
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    compile_estimand,
    CyclicExecutionBlock,
    ExecutorGraph,
    ExecutorNode,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import (
    ancestors,
    do_operator,
    has_directed_cycle,
    induced_subgraph,
)
from polisyos.foundry.methods.catalog.causal.cyclic_id import (
    cyclic_id_algorithm,
    well_posedness_check,
)
from polisyos.foundry.methods.catalog.causal.schema_resolver import (
    SchemaResolver,
    SchemaResolutionReport,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.mgraph import MGraphMetadata
    from polisyos.ir.analytics.recoverability import JointDecisionCertificate


class DataReadinessBlockedError(RuntimeError):
    """Typed pre-execution failure raised when an estimation path is not ready."""

    def __init__(self, report: DataReadinessReport, *, reason: str) -> None:
        self.report = report
        self.reason = reason
        super().__init__(reason)


class CausalEngine:
    """Pearl-Bareinboim causal engine: identify → compile → estimate → audit.

    Parameters
    ----------
    registry:
        A MethodRegistry instance (used to look up estimator methods).
        If None, the engine can still identify and compile but cannot estimate.
    knowledge_base:
        Optional DataKnowledgeBase for data-availability-aware compilation.
    """

    def __init__(
        self,
        registry: Any = None,
        knowledge_base: Any | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._registry = registry
        self._kb = knowledge_base
        self._artifact_store = artifact_store

    @staticmethod
    def _distribution_family_for_query(query: DistributionLawQuery) -> str:
        if query.generator_type == "orthant_cdf":
            return "orthant_cdf"
        if query.generator_type == "finite_atoms":
            return "finite_pmf"
        return "cdf"

    @staticmethod
    def _distribution_regularity_assumptions(query: DistributionLawQuery) -> list[str]:
        if query.generator_type == "orthant_cdf":
            return [
                "orthant_monotone",
                "orthant_right_continuous",
                "orthant_limits_0_1",
            ]
        if query.generator_type == "finite_atoms":
            return [
                "pmf_nonnegative",
                "pmf_sums_to_one",
            ]
        return [
            "cdf_monotone",
            "cdf_right_continuous",
            "cdf_limits_0_1",
        ]

    @staticmethod
    def _distribution_derived_functionals(query: DistributionLawQuery) -> list[str]:
        if query.generator_type == "finite_atoms":
            return [
                "atom_probability",
                "tail_probability",
                "expected_shortfall",
            ]
        if query.generator_type == "orthant_cdf":
            return [
                "orthant_probability",
                "tail_probability",
            ]
        return [
            "survival",
            "tail_probability",
            "quantile",
            "expected_shortfall",
            "quantile_shift",
            "tail_risk_delta",
            "histogram",
        ]

    @staticmethod
    def _distribution_not_identified_objects() -> list[str]:
        return [
            "ot_coupling",
            "joint_potential_outcome_law",
            "individual_treatment_effect_distribution",
            "cross_world_transport_map",
        ]

    def _wrap_distribution_identification_result(
        self,
        *,
        base_result: IdentificationResult,
        query: DistributionLawQuery,
        dataset_ref: str | None,
    ) -> IdentificationResult:
        preview_ast = make_distribution_law_estimand(
            query=query,
            dataset_ref=dataset_ref,
            side_conditions=(
                tuple(base_result.estimand_ast.side_conditions)
                if base_result.estimand_ast is not None
                else ()
            ),
            identification_method=(
                "dist_idc_reduction" if query.conditioning else "dist_id_reduction"
            ),
        )
        metadata = {
            **dict(base_result.metadata or {}),
            "query_kind": "distribution_law",
            "distributional_query_kind": "interventional_law",
            "distribution_family": self._distribution_family_for_query(query),
            "generator_type": query.generator_type,
            "parameter_domain": query.resolved_parameter_domain,
            "measure_determination_regime": "countable_generator_reduction",
            "regularity_assumptions": self._distribution_regularity_assumptions(query),
            "derived_functionals_allowed": self._distribution_derived_functionals(query),
            "not_identified_objects": self._distribution_not_identified_objects(),
            "base_identification_algorithm": base_result.algorithm_version,
            "support_space": query.support_space,
            "representation": query.representation,
        }
        if query.conditioning:
            metadata["conditioning_variables"] = list(query.conditioning)
        return dataclasses.replace(
            base_result,
            algorithm_version="dist_idc_v1" if query.conditioning else "dist_id_v1",
            estimand_ast=(
                preview_ast if base_result.status is IdentificationStatus.IDENTIFIED else None
            ),
            query_str=preview_ast.query_str,
            metadata=metadata,
        )

    def identify_distribution_law(
        self,
        *,
        query: DistributionLawQuery,
        graph: CausalGraphModel,
        oracle: str = "none",
        dataset_ref: str | None = None,
    ) -> IdentificationResult:
        """Identify a marginal or conditional interventional law.

        This is a proof-only reduction layer: it reuses ID/IDC for the
        underlying interventional distribution and then lifts the result into a
        distribution-law AST node with explicit generator metadata.
        """
        treatment = frozenset(query.intervention_set)
        outcome = frozenset(query.outcome_variables)
        if query.conditioning:
            base_result = idc_algorithm(
                treatment=treatment,
                outcome=outcome,
                conditions=frozenset(query.conditioning),
                graph=graph,
                dataset_ref=dataset_ref,
            )
        else:
            base_result = id_with_oracle_fallback(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                oracle=oracle,
                dataset_ref=dataset_ref,
            )
        return self._wrap_distribution_identification_result(
            base_result=base_result,
            query=query,
            dataset_ref=dataset_ref,
        )

    @staticmethod
    def _graph_artifact_ref(graph: CausalGraphModel) -> str:
        payload = graph.model_dump(mode="python")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
        return f"graph:{hashlib.sha256(raw).hexdigest()}"

    @staticmethod
    def _selection_target_vars(s_nodes: list[Any] | None) -> frozenset[str]:
        if not s_nodes:
            return frozenset()
        resolved: set[str] = set()
        for node in s_nodes:
            target = getattr(node, "target_variable", None)
            if target is None and isinstance(node, dict):
                target = node.get("target_variable")
            resolved.add(str(target if target is not None else node))
        return frozenset(resolved)

    @staticmethod
    def _source_domain_s_nodes(source_domains: list[Any] | None) -> frozenset[str]:
        if not source_domains:
            return frozenset()
        resolved: set[str] = set()
        for domain in source_domains:
            s_nodes = getattr(domain, "s_nodes", None)
            if s_nodes is None and isinstance(domain, dict):
                s_nodes = domain.get("s_nodes")
            for node in s_nodes or ():
                resolved.add(str(node))
        return frozenset(resolved)

    @staticmethod
    def _source_domain_z_interventions(source_domains: list[Any] | None) -> frozenset[str]:
        if not source_domains:
            return frozenset()
        resolved: set[str] = set()
        for domain in source_domains:
            z_nodes = getattr(domain, "z_interventions", None)
            if z_nodes is None and isinstance(domain, dict):
                z_nodes = domain.get("z_interventions")
            for node in z_nodes or ():
                resolved.add(str(node))
        return frozenset(resolved)

    def _maybe_proximal_identify(
        self,
        *,
        base_result: IdentificationResult,
        treatment: frozenset[str],
        outcome: frozenset[str],
        graph: CausalGraphModel,
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None,
    ) -> IdentificationResult | NegativeCertificate | ProximalIdentificationCertificate:
        """Attempt a proof-only proximal fallback after a classical hedge."""
        if proximal_annotation is None:
            return base_result
        if base_result.status is not IdentificationStatus.HEDGE_FOUND:
            return base_result

        treatment_name = _singleton_query_name(treatment, "treatment")
        outcome_name = _singleton_query_name(outcome, "outcome")
        if treatment_name is None or outcome_name is None:
            return NegativeCertificate(
                blocking_type=BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1,
                blocking_description=(
                    "Proximal v1 currently supports exactly one treatment and one outcome."
                ),
                quantitative_diagnostics={
                    "failed_check": "singleton_query_scope",
                    "upstream_identification_status": base_result.status.value,
                    "upstream_algorithm_version": base_result.algorithm_version,
                },
                constructive_message=(
                    "Reduce the query to a single treatment/outcome pair before "
                    "requesting proximal identification."
                ),
            )

        proximal_result = proximal_identify_v1(
            graph,
            CausalQuery(
                query_type=QueryType.INTERVENTIONAL,
                treatment_variable=treatment_name,
                treatment_value=1.0,
                outcome_variable=outcome_name,
            ),
            proximal_annotation,
        )
        upstream_hedge = _coerce_mapping_like_data(base_result.hedge_certificate)
        upstream_metadata: dict[str, Any] = {
            "upstream_identification_status": base_result.status.value,
            "upstream_algorithm_version": base_result.algorithm_version,
            "upstream_trace": list(base_result.trace or []),
        }
        if upstream_hedge is not None:
            upstream_metadata["upstream_hedge_certificate"] = upstream_hedge

        if isinstance(proximal_result, NegativeCertificate):
            diagnostics = {
                **dict(proximal_result.quantitative_diagnostics or {}),
                **upstream_metadata,
            }
            return proximal_result.model_copy(update={"quantitative_diagnostics": diagnostics})

        proof_trace = list(proximal_result.proof_trace)
        proof_trace.append("Fallback triggered after classical ID hedge.")
        return proximal_result.model_copy(
            update={
                "proof_trace": tuple(proof_trace),
                "metadata": {
                    **dict(proximal_result.metadata or {}),
                    **upstream_metadata,
                },
            }
        )

    @staticmethod
    def _well_posedness_witness(result: Any) -> WellPosednessWitness:
        method = str(getattr(result, "method", "") or "")
        if method == "exact_linear":
            status = (
                WellPosednessStatus.PROVED
                if bool(getattr(result, "well_posed", False))
                else WellPosednessStatus.REFUTED
            )
            family = "linear_unique"
        else:
            status = WellPosednessStatus.HEURISTIC_BLOCKED
            family = "contraction" if method == "lipschitz_heuristic" else "numerical_fixed_point"
        evidence: dict[str, Any] = {
            "well_posed": bool(getattr(result, "well_posed", False)),
            "method": method,
            "confidence": str(getattr(result, "confidence", "") or ""),
        }
        lipschitz_constant = getattr(result, "lipschitz_constant", None)
        if lipschitz_constant is not None:
            evidence["lipschitz_constant"] = float(lipschitz_constant)
        warning = getattr(result, "warning", None)
        if warning:
            evidence["warning"] = str(warning)
        return WellPosednessWitness(
            status=status,
            family=family,
            method=method,
            confidence=str(getattr(result, "confidence", "") or ""),
            lipschitz_constant=lipschitz_constant,
            warning=str(warning) if warning else None,
            evidence=evidence,
        )

    @staticmethod
    def _dynamic_scope_statement(
        *,
        covered_families: tuple[str, ...] = (),
        notes: tuple[str, ...] = (),
    ) -> DynamicScopeStatement:
        return DynamicScopeStatement(
            covered_families=covered_families,
            excluded_families=(
                "multi_equilibrium",
                "non_unique_intervention_response",
                "unsupported_soft_dynamic_interventions",
                "continuous_time_local_independence_unreduced",
            ),
            notes=notes,
        )

    def _query_relevant_reduction_nodes(
        self,
        *,
        graph: CausalGraphModel,
        treatment: frozenset[str],
        outcome: frozenset[str],
        conditions: frozenset[str],
        z_interventions: frozenset[str],
        source_domains: list[Any] | None,
        s_nodes: list[Any] | None,
        distribution_query: DistributionLawQuery | None,
    ) -> frozenset[str]:
        focus = set(outcome)
        focus.update(conditions)
        focus.update(z_interventions)
        focus.update(self._selection_target_vars(s_nodes))
        focus.update(self._source_domain_s_nodes(source_domains))
        focus.update(self._source_domain_z_interventions(source_domains))
        if distribution_query is not None:
            focus.update(distribution_query.conditioning)
        focus.update(treatment)
        mutilated = do_operator(graph, treatment)
        return ancestors(mutilated, frozenset(focus), include_self=True) | treatment

    @staticmethod
    def _supports_dynamic_snapshot_dispatch(
        *,
        counterfactual_query: CtfQuery | None,
        proxy_map: dict[str, str] | None,
        policy: Any | None,
        condition_vars: frozenset[str] | None,
        treatment_sequence: list[str] | None,
        outcomes: list[str] | None,
    ) -> bool:
        return not any(
            (
                counterfactual_query is not None,
                proxy_map is not None,
                policy is not None,
                condition_vars is not None and len(condition_vars) > 0,
                treatment_sequence is not None and len(treatment_sequence) > 0,
                outcomes is not None and len(outcomes) > 0,
            )
        )

    def _build_validated_cyclic_reduction_attachment(
        self,
        *,
        source_graph: CausalGraphModel,
        treatment: frozenset[str],
        outcome: frozenset[str],
        reduction_nodes: frozenset[str],
        reduction_graph: CausalGraphModel,
        extra_z: frozenset[str] = frozenset(),
    ) -> DynamicSemanticsAttachment:
        pruned_nodes = tuple(sorted(set(source_graph.nodes) - set(reduction_nodes)))
        intervention_scope = InterventionScope(
            kind=InterventionKind.NODE_DO,
            targets=tuple(sorted(treatment)),
            admissible=True,
            admissibility_theorem="query_relevant_acyclic_reduction",
        )
        notes = (
            "Cycles were pruned outside the query-relevant mutilated ancestral graph before dispatch.",
        )
        if pruned_nodes:
            notes = notes + (f"Pruned nodes: {', '.join(pruned_nodes)}.",)
        certificate = GraphicalMarkovCertificate(
            semantics_family=DynamicSemanticsFamily.IOSCM,
            graphical_oracle=GraphicalOracleKind.D,
            theorem_family="dynamic_acyclic_reduction_v1",
            source_graph_ref=self._graph_artifact_ref(source_graph),
            latent_projection_ref=self._graph_artifact_ref(reduction_graph),
            intervention_spec=intervention_scope,
            separation_claim=SeparationClaim(
                x_set=tuple(sorted(treatment)),
                y_set=tuple(sorted(outcome)),
                z_set=tuple(sorted(extra_z)),
                holds=True,
                criterion=GraphicalOracleKind.D,
            ),
            transformation_trace=(
                "do_operator",
                "ancestral_reduction",
                "induced_subgraph",
                "acyclic_backend_dispatch",
            ),
            notes=notes,
        )
        return DynamicSemanticsAttachment(
            semantics_family=DynamicSemanticsFamily.IOSCM,
            reduction_status=DynamicReductionStatus.VALIDATED_REDUCTION,
            markov_criterion_certificate=certificate,
            intervention_scope=intervention_scope,
            scope_statement=self._dynamic_scope_statement(
                covered_families=("query_relevant_acyclic_reduction",),
                notes=(
                    "Validated only when the mutilated ancestral subgraph is acyclic.",
                ),
            ),
        )

    def _build_blocked_cyclic_attachment(
        self,
        *,
        graph: CausalGraphModel,
        treatment: frozenset[str],
        outcome: frozenset[str],
        reason: str,
        intervention_scope: InterventionScope,
        well_posedness_witness: WellPosednessWitness | None = None,
        transformation_trace: tuple[str, ...] = (),
    ) -> DynamicSemanticsAttachment:
        certificate = GraphicalMarkovCertificate(
            certificate_type="sigma_separation",
            semantics_family=DynamicSemanticsFamily.IOSCM,
            graphical_oracle=GraphicalOracleKind.SIGMA,
            theorem_family="Forre-Mooij-2020",
            source_graph_ref=self._graph_artifact_ref(graph),
            intervention_spec=intervention_scope,
            separation_claim=SeparationClaim(
                x_set=tuple(sorted(treatment)),
                y_set=tuple(sorted(outcome)),
                z_set=(),
                holds=False,
                criterion=GraphicalOracleKind.SIGMA,
            ),
            transformation_trace=transformation_trace,
            notes=(reason,),
        )
        return DynamicSemanticsAttachment(
            semantics_family=DynamicSemanticsFamily.IOSCM,
            reduction_status=DynamicReductionStatus.BLOCKED,
            markov_criterion_certificate=certificate,
            well_posedness_witness=well_posedness_witness,
            intervention_scope=intervention_scope,
            scope_statement=self._dynamic_scope_statement(
                notes=(
                    "Unsupported dynamic queries are blocked unless reduced to an acyclic backend.",
                ),
            ),
        )

    @staticmethod
    def _attach_dynamic_semantics(
        result: IdentificationResult,
        attachment: DynamicSemanticsAttachment,
        *,
        algorithm_version: str | None = None,
        trace_note: str | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> IdentificationResult:
        metadata = {
            **dict(result.metadata or {}),
            "dynamic_semantics": attachment.model_dump(mode="json"),
            **dict(metadata_updates or {}),
        }
        trace = list(result.trace or [])
        if trace_note:
            trace.append(trace_note)
        update_payload: dict[str, Any] = {
            "metadata": metadata,
            "trace": trace,
        }
        if algorithm_version:
            update_payload["algorithm_version"] = algorithm_version
        return dataclasses.replace(result, **update_payload)

    @staticmethod
    def _attach_dynamic_semantics_to_negative_certificate(
        certificate: NegativeCertificate,
        attachment: DynamicSemanticsAttachment,
        *,
        algorithm_version: str,
        proof_trace: list[str],
    ) -> NegativeCertificate:
        diagnostics = {
            **dict(certificate.quantitative_diagnostics or {}),
            "identification_status": dict(certificate.quantitative_diagnostics or {}).get(
                "identification_status",
                "blocked",
            ),
            "algorithm_version": algorithm_version,
            "proof_trace": proof_trace,
            "dynamic_semantics": attachment.model_dump(mode="json"),
        }
        return certificate.model_copy(update={"quantitative_diagnostics": diagnostics})

    @staticmethod
    def _dynamic_oracle_needed_result(
        *,
        attachment: DynamicSemanticsAttachment,
        algorithm_version: str,
        trace: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=None,
            hedge_certificate=None,
            trace=list(trace),
            required_distributions=[],
            algorithm_version=algorithm_version,
            metadata={
                **dict(metadata or {}),
                "dynamic_semantics": attachment.model_dump(mode="json"),
            },
        )

    @staticmethod
    def _dynamic_semantics_not_well_defined_certificate(
        *,
        attachment: DynamicSemanticsAttachment,
        witness: WellPosednessWitness,
        trace: list[str],
        graph: CausalGraphModel,
    ) -> NegativeCertificate:
        return NegativeCertificate(
            blocking_type=BlockingType.SEMANTICS_NOT_WELL_DEFINED,
            blocking_description=(
                "Dynamic SCM semantics are not certified for this cyclic query; "
                "the intervention response is not machine-checkably well defined."
            ),
            technical_detail=str(
                witness.warning
                or f"{witness.family}:{witness.method}:{witness.status.value}"
            ),
            suggested_experiments=NegativeCertificate.auto_suggest_experiments(
                BlockingType.SEMANTICS_NOT_WELL_DEFINED,
            ),
            quantitative_diagnostics={
                "identification_status": "blocked",
                "algorithm_version": "dynamic_semantics_gate_v1",
                "proof_trace": list(trace),
                "dynamic_semantics": attachment.model_dump(mode="json"),
                "source_graph_ref": CausalEngine._graph_artifact_ref(graph),
            },
            constructive_message=(
                "Provide a machine-checkable well-posedness witness or reduce the query "
                "to an acyclic ancestral slice before requesting identification."
            ),
        )

    def _dispatch_static_identification(
        self,
        *,
        treatment: frozenset[str],
        outcome: frozenset[str],
        graph: CausalGraphModel,
        source_domains: list[Any] | None,
        s_nodes: list[Any] | None,
        z_interventions: frozenset[str],
        conditions: frozenset[str],
        oracle: str,
        dataset_ref: str | None,
        mgraph_meta: Any | None,
        counterfactual_query: CtfQuery | None,
        distribution_query: DistributionLawQuery | None,
        policy: Any | None,
        condition_vars: frozenset[str] | None,
        treatment_sequence: list[str] | None,
        time_points: list[int] | None,
        outcomes: list[str] | None,
        proxy_map: dict[str, str] | None,
        measurement_model: str,
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None = None,
    ) -> (
        IdentificationResult
        | NegativeCertificate
        | ProximalIdentificationCertificate
        | dict[str, IdentificationResult]
    ):
        if distribution_query is not None:
            return self.identify_distribution_law(
                query=distribution_query,
                graph=graph,
                oracle=oracle,
                dataset_ref=dataset_ref,
            )

        if counterfactual_query is not None:
            has_ctf_transport_context = bool(s_nodes) or bool(source_domains) or bool(z_interventions)
            if has_ctf_transport_context:
                from polisyos.foundry.methods.catalog.causal.ctf_transport import (
                    build_ctf_selection_diagram,
                    ctf_transportability,
                )
                from polisyos.foundry.methods.catalog.causal.id_engine import SourceDomain

                ctf_domains = list(source_domains or [])
                if not ctf_domains and z_interventions:
                    s_var_names = frozenset(
                        getattr(sn, "target_variable", str(sn)) for sn in (s_nodes or [])
                    )
                    ctf_domains = [
                        SourceDomain(
                            domain_id="ctf_source",
                            s_nodes=s_var_names,
                            z_interventions=z_interventions,
                            dataset_ref=dataset_ref,
                        )
                    ]

                selection_diagram = build_ctf_selection_diagram(
                    graph=graph,
                    s_nodes=s_nodes,
                    source_domains=ctf_domains,
                )
                result = ctf_transportability(
                    counterfactual_query,
                    selection_diagram,
                    source_domains=ctf_domains,
                    dataset_ref=dataset_ref,
                )
                if isinstance(result, NegativeCertificate):
                    return result
                if result.status == IdentificationStatus.HEDGE_FOUND:
                    return self._hedge_to_negative_cert(result)
                return result

            if counterfactual_query.evidence:
                result = idc_star_algorithm(counterfactual_query, graph)
            else:
                result = id_star_algorithm(counterfactual_query, graph)
            if result.status == IdentificationStatus.HEDGE_FOUND:
                return self._hedge_to_negative_cert(result)
            return result

        if proxy_map is not None:
            from polisyos.foundry.methods.catalog.causal.measurement_error import (
                identify_with_proxy,
            )

            t_str = next(iter(sorted(treatment)))
            y_str = next(iter(sorted(outcome)))
            return identify_with_proxy(
                graph=graph,
                treatment=t_str,
                outcome=y_str,
                proxy_map=proxy_map,
                measurement_model=measurement_model,  # type: ignore[arg-type]
            )

        if outcomes is not None and len(outcomes) > 0:
            return multi_outcome_id(
                treatment=treatment,
                outcomes=outcomes,
                graph=graph,
                dataset_ref=dataset_ref,
            )

        if treatment_sequence is not None and len(treatment_sequence) > 0:
            t_pts = time_points or list(range(len(treatment_sequence)))
            y_str = next(iter(sorted(outcome)))
            return dynamic_intervention_id(
                treatment_sequence=treatment_sequence,
                outcome=y_str,
                graph=graph,
                time_points=t_pts,
                dataset_ref=dataset_ref,
            )

        if condition_vars is not None and len(condition_vars) > 0:
            return conditional_intervention_id(
                treatment=treatment,
                outcome=outcome,
                condition_vars=condition_vars,
                graph=graph,
                dataset_ref=dataset_ref,
            )

        if policy is not None:
            if mgraph_meta is not None:
                from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
                    full_law_identify,
                )
                from polisyos.ir.analytics.mgraph import (
                    MGraphMetadata,
                    extract_mgraph_metadata,
                )

                if isinstance(mgraph_meta, MGraphMetadata):
                    meta = mgraph_meta
                elif isinstance(mgraph_meta, dict):
                    meta = MGraphMetadata.model_validate(mgraph_meta)
                else:
                    meta = extract_mgraph_metadata(graph)

                return full_law_identify(
                    treatment=treatment,
                    outcome=outcome,
                    graph=graph,
                    mgraph_meta=meta,
                    dataset_ref=dataset_ref,
                    oracle=oracle,
                    policy=policy,
                )

            policy_result = sid_algorithm(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                policy=policy,
                dataset_ref=dataset_ref,
                s_nodes=s_nodes,
            )
            proximal_candidate = (
                self._maybe_proximal_identify(
                    base_result=policy_result,
                    treatment=treatment,
                    outcome=outcome,
                    graph=graph,
                    proximal_annotation=proximal_annotation,
                )
                if getattr(policy, "policy_type", None) == "soft"
                else policy_result
            )
            if proximal_candidate is not policy_result and isinstance(
                proximal_candidate,
                ProximalIdentificationCertificate,
            ):
                return proximal_candidate.model_copy(
                    update={
                        "metadata": {
                            **dict(proximal_candidate.metadata or {}),
                            "policy_type": getattr(policy, "policy_type", None),
                            "policy_conditioning_vars": list(
                                getattr(policy, "conditioning_vars", ()) or ()
                            ),
                            "policy_expr": getattr(policy, "policy_expr", None),
                            "policy_lifting": "stochastic_policy_mixture",
                        }
                    }
                )
            return proximal_candidate

        if mgraph_meta is not None:
            from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
                _project_to_base_dag,
                full_law_identify,
                identify_joint_recoverability,
            )
            from polisyos.ir.analytics.mgraph import (
                MGraphMetadata,
                extract_mgraph_metadata,
            )
            from polisyos.ir.analytics.recoverability import (
                JointDecisionStatus,
                RecoveryScope,
            )

            if isinstance(mgraph_meta, MGraphMetadata):
                meta = mgraph_meta
            elif isinstance(mgraph_meta, dict):
                meta = MGraphMetadata.model_validate(mgraph_meta)
            else:
                meta = extract_mgraph_metadata(graph)

            joint = identify_joint_recoverability(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                mgraph_meta=meta,
                dataset_ref=dataset_ref,
                oracle=oracle,
            )
            if joint.verdict is JointDecisionStatus.IDENTIFIED_AND_RECOVERABLE:
                if joint.recoverability.recovery_scope is RecoveryScope.FULL_LAW:
                    result = full_law_identify(
                        treatment=treatment,
                        outcome=outcome,
                        graph=graph,
                        mgraph_meta=meta,
                        dataset_ref=dataset_ref,
                        oracle=oracle,
                    )
                    return dataclasses.replace(
                        result,
                        metadata={
                            **dict(getattr(result, "metadata", {}) or {}),
                            "recoverability_certificate": joint.recoverability.model_dump(mode="json"),
                            "joint_decision": joint.model_dump(mode="json"),
                            "computable_functionals": list(joint.computable_functionals),
                        },
                    )

                base_graph = _project_to_base_dag(graph, meta)
                result = id_with_oracle_fallback(
                    treatment=treatment,
                    outcome=outcome,
                    graph=base_graph,
                    oracle=oracle,
                    dataset_ref=dataset_ref,
                )
                recovery_steps = [
                    ProofStep(
                        rule_name=f"MGRAPH_{step.rule_name}",
                        antecedent_vars=tuple(step.variables_affected),
                        consequent_vars=tuple(sorted(outcome)),
                        applied_to_graph_state=step.description or step.rule_name,
                        depth=step.depth,
                    )
                    for step in joint.recoverability.recovery_steps
                ]
                recovery_steps.append(
                    ProofStep(
                        rule_name="JOINT_RECOVERABILITY_DECISION",
                        antecedent_vars=tuple(sorted(treatment)),
                        consequent_vars=tuple(sorted(outcome)),
                        applied_to_graph_state=(
                            f"Joint verdict={joint.verdict.value}; "
                            f"recovery_scope={joint.recoverability.recovery_scope.value}"
                        ),
                        depth=0,
                    )
                )
                return dataclasses.replace(
                    result,
                    proof_steps=list(result.proof_steps) + recovery_steps,
                    trace=list(result.trace) + [
                        "identify: joint recoverability direct-query path passed"
                    ],
                    metadata={
                        **dict(getattr(result, "metadata", {}) or {}),
                        "recoverability_certificate": joint.recoverability.model_dump(mode="json"),
                        "joint_decision": joint.model_dump(mode="json"),
                        "computable_functionals": list(joint.computable_functionals),
                    },
                )

            if joint.negative_certificate is not None:
                return joint.negative_certificate

            return NegativeCertificate(
                blocking_type=BlockingType.MISSINGNESS_NOT_RECOVERABLE,
                blocking_description=(
                    "Joint identification-recoverability decision did not yield "
                    "an executable causal proof."
                ),
                quantitative_diagnostics={
                    "joint_decision": joint.model_dump(mode="json"),
                    "recoverability_certificate": joint.recoverability.model_dump(mode="json"),
                },
                constructive_message=(
                    "Inspect the joint decision certificate for recoverability "
                    "repairs or computable observational functionals."
                ),
            )

        if source_domains and len(source_domains) > 1:
            return mz_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                source_domains=source_domains,
                graph=graph,
                dataset_ref=dataset_ref,
            )

        if s_nodes and z_interventions:
            from polisyos.foundry.methods.catalog.causal.id_engine import SourceDomain

            s_var_names = frozenset(
                getattr(sn, "target_variable", str(sn)) for sn in s_nodes
            )
            domain = SourceDomain(
                domain_id="combined",
                s_nodes=s_var_names,
                z_interventions=z_interventions,
                dataset_ref=dataset_ref,
            )
            return mz_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                source_domains=[domain],
                graph=graph,
                dataset_ref=dataset_ref,
            )

        if s_nodes:
            return self._identify_with_s_nodes(
                treatment,
                outcome,
                graph,
                s_nodes,
                dataset_ref,
            )

        if z_interventions:
            return z_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                z_interventions=z_interventions,
                graph=graph,
                dataset_ref=dataset_ref,
            )

        if conditions:
            return idc_algorithm(
                treatment=treatment,
                outcome=outcome,
                conditions=conditions,
                graph=graph,
                dataset_ref=dataset_ref,
            )

        base_result = id_with_oracle_fallback(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            oracle=oracle,
            dataset_ref=dataset_ref,
        )
        return self._maybe_proximal_identify(
            base_result=base_result,
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            proximal_annotation=proximal_annotation,
        )

    def _identify_with_dynamic_semantics(
        self,
        *,
        treatment: frozenset[str],
        outcome: frozenset[str],
        graph: CausalGraphModel,
        source_domains: list[Any] | None,
        s_nodes: list[Any] | None,
        z_interventions: frozenset[str],
        conditions: frozenset[str],
        oracle: str,
        dataset_ref: str | None,
        mgraph_meta: Any | None,
        counterfactual_query: CtfQuery | None,
        distribution_query: DistributionLawQuery | None,
        policy: Any | None,
        condition_vars: frozenset[str] | None,
        treatment_sequence: list[str] | None,
        time_points: list[int] | None,
        outcomes: list[str] | None,
        proxy_map: dict[str, str] | None,
        measurement_model: str,
    ) -> IdentificationResult | NegativeCertificate | dict[str, IdentificationResult]:
        reduction_nodes = self._query_relevant_reduction_nodes(
            graph=graph,
            treatment=treatment,
            outcome=outcome,
            conditions=conditions,
            z_interventions=z_interventions,
            source_domains=source_domains,
            s_nodes=s_nodes,
            distribution_query=distribution_query,
        )
        reduced_graph = induced_subgraph(graph, reduction_nodes)
        if not has_directed_cycle(reduced_graph) and self._supports_dynamic_snapshot_dispatch(
            counterfactual_query=counterfactual_query,
            proxy_map=proxy_map,
            policy=policy,
            condition_vars=condition_vars,
            treatment_sequence=treatment_sequence,
            outcomes=outcomes,
        ):
            static_result = self._dispatch_static_identification(
                treatment=treatment,
                outcome=outcome,
                graph=reduced_graph,
                source_domains=source_domains,
                s_nodes=s_nodes,
                z_interventions=z_interventions,
                conditions=conditions,
                oracle=oracle,
                dataset_ref=dataset_ref,
                mgraph_meta=mgraph_meta,
                counterfactual_query=counterfactual_query,
                distribution_query=distribution_query,
                policy=policy,
                condition_vars=condition_vars,
                treatment_sequence=treatment_sequence,
                time_points=time_points,
                outcomes=outcomes,
                proxy_map=proxy_map,
                measurement_model=measurement_model,
            )
            attachment = self._build_validated_cyclic_reduction_attachment(
                source_graph=graph,
                treatment=treatment,
                outcome=outcome,
                reduction_nodes=reduction_nodes,
                reduction_graph=reduced_graph,
                extra_z=conditions | z_interventions,
            )
            proof_trace = [
                "dynamic_semantics_dispatch",
                "do_operator",
                "ancestral_reduction",
                "acyclic_backend_dispatch",
            ]
            if isinstance(static_result, NegativeCertificate):
                return self._attach_dynamic_semantics_to_negative_certificate(
                    static_result,
                    attachment,
                    algorithm_version="dynamic_acyclic_reduction_v1",
                    proof_trace=proof_trace,
                )
            return self._attach_dynamic_semantics(
                static_result,
                attachment,
                algorithm_version="dynamic_acyclic_reduction_v1",
                trace_note="[dynamic] validated reduction to an acyclic ancestral slice",
                metadata_updates={
                    "reduced_backend_algorithm": static_result.algorithm_version,
                    "reduction_node_count": len(reduction_nodes),
                    "pruned_nodes": sorted(set(graph.nodes) - set(reduction_nodes)),
                },
            )

        well_posed = well_posedness_check(
            graph,
            getattr(graph, "metadata", {}).get("well_posedness_spec"),
        )
        witness = self._well_posedness_witness(well_posed)
        intervention_scope = InterventionScope(
            kind=InterventionKind.NODE_DO,
            targets=tuple(sorted(treatment)),
            admissible=True,
            admissibility_theorem="snapshot_node_intervention_only",
        )
        if not self._supports_dynamic_snapshot_dispatch(
            counterfactual_query=counterfactual_query,
            proxy_map=proxy_map,
            policy=policy,
            condition_vars=condition_vars,
            treatment_sequence=treatment_sequence,
            outcomes=outcomes,
        ):
            intervention_scope = intervention_scope.model_copy(
                update={
                    "admissible": False,
                    "admissibility_theorem": "unsupported_dynamic_query_kind",
                }
            )

        blocked_reason = (
            "Dynamic query requires a theorem-backed cyclic reduction before the proof kernel can proceed."
        )
        blocked_attachment = self._build_blocked_cyclic_attachment(
            graph=graph,
            treatment=treatment,
            outcome=outcome,
            reason=blocked_reason,
            intervention_scope=intervention_scope,
            well_posedness_witness=witness,
            transformation_trace=(
                "well_posedness_gate",
                "dynamic_context_check",
                "reduction_failed" if has_directed_cycle(reduced_graph) else "unsupported_dynamic_query",
            ),
        )
        if witness.status is not WellPosednessStatus.PROVED:
            plain_snapshot_query = (
                distribution_query is None
                and not source_domains
                and not s_nodes
                and not z_interventions
                and not conditions
                and mgraph_meta is None
                and counterfactual_query is None
                and policy is None
                and condition_vars is None
                and not treatment_sequence
                and not outcomes
                and proxy_map is None
            )
            if plain_snapshot_query:
                return cyclic_id_algorithm(
                    treatment=treatment,
                    outcome=outcome,
                    graph=graph,
                    scm_spec=getattr(graph, "metadata", {}).get("well_posedness_spec"),
                    dataset_ref=dataset_ref,
                )
            return self._dynamic_semantics_not_well_defined_certificate(
                attachment=blocked_attachment,
                witness=witness,
                trace=[
                    "dynamic_semantics_dispatch",
                    "well_posedness_gate",
                    "semantics_not_well_defined",
                ],
                graph=graph,
            )

        if (
            distribution_query is None
            and not source_domains
            and not s_nodes
            and not z_interventions
            and not conditions
            and mgraph_meta is None
            and counterfactual_query is None
            and policy is None
            and condition_vars is None
            and not treatment_sequence
            and not outcomes
            and proxy_map is None
        ):
            return cyclic_id_algorithm(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                scm_spec=getattr(graph, "metadata", {}).get("well_posedness_spec"),
                dataset_ref=dataset_ref,
            )

        return self._dynamic_oracle_needed_result(
            attachment=blocked_attachment,
            algorithm_version="dynamic_semantics_oracle_v1",
            trace=[
                "dynamic_semantics_dispatch",
                "well_posedness_gate",
                "blocked_dynamic_context",
            ],
            metadata={
                "reduction_node_count": len(reduction_nodes),
                "pruned_nodes": sorted(set(graph.nodes) - set(reduction_nodes)),
            },
        )

    def _continuous_time_dynamic_attachment(
        self,
        query: ContinuousTimeQuery,
    ) -> DynamicSemanticsAttachment:
        metadata = dict(query.metadata or {})
        process_family = str(metadata.get("process_family") or "counting_process").strip().lower()
        semantics_family = str(
            metadata.get("graph_semantics") or metadata.get("semantics_family") or ""
        ).strip()
        oracle_raw = str(
            metadata.get("graphical_oracle") or metadata.get("markov_oracle") or "mu"
        ).strip()
        try:
            oracle_kind = GraphicalOracleKind(oracle_raw)
        except ValueError:
            oracle_kind = GraphicalOracleKind.MU
        theorem_family = str(
            metadata.get("theorem_family") or "local_independence_identification_v1"
        )
        intervention_targets = tuple(
            str(item) for item in metadata.get("intervention_targets", ()) if str(item)
        )
        intervention_scope = InterventionScope(
            kind=InterventionKind.INTENSITY_INTERVENTION,
            targets=intervention_targets,
            admissible=bool(metadata.get("causal_validity_verified", False)),
            admissibility_theorem=str(
                metadata.get("admissibility_theorem") or "continuous_time_validity"
            ),
        )
        eliminable_processes = tuple(
            str(item) for item in metadata.get("eliminable_processes", ()) if str(item)
        )
        eliminability_checked = bool(
            metadata.get("eliminability_verified", bool(eliminable_processes))
        )
        independent_censoring_checked = bool(
            metadata.get("independent_censoring_verified", False)
        )
        if not independent_censoring_checked and metadata.get("identification_via_reweighting", False):
            independent_censoring_checked = True
        weighting_components = tuple(
            str(item)
            for item in metadata.get("weight_components", ("W_treatment", "W_censoring"))
            if str(item)
        )
        validated = (
            (
                semantics_family in {"local_independence", "local_independence_graph"}
                or process_family in {"counting_process", "marked_point_process", "event_log"}
            )
            and bool(metadata.get("causal_validity_verified", False))
            and bool(metadata.get("identification_via_reweighting", False))
            and independent_censoring_checked
            and eliminability_checked
        )
        certificate = GraphicalMarkovCertificate(
            semantics_family=DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH,
            graphical_oracle=oracle_kind,
            theorem_family=theorem_family,
            intervention_spec=intervention_scope,
            separation_claim=SeparationClaim(
                x_set=intervention_targets,
                y_set=(query.outcome_process,),
                z_set=tuple(
                    str(item)
                    for item in metadata.get("conditioning_processes", ())
                    if str(item)
                ),
                holds=validated,
                criterion=oracle_kind,
            ),
            transformation_trace=(
                "continuous_time_query",
                "event_process_view",
                "local_independence_graph",
                "reweighting_reduction",
            ),
            notes=(
                "Continuous-time proof path tracks local independence separately from numerical path representation.",
            ),
        )
        return DynamicSemanticsAttachment(
            semantics_family=DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH,
            reduction_status=(
                DynamicReductionStatus.VALIDATED_REDUCTION
                if validated
                else DynamicReductionStatus.BLOCKED
            ),
            markov_criterion_certificate=certificate,
            intervention_scope=intervention_scope,
            continuous_time_attachment=LocalIndependenceAttachment(
                graphical_oracle=oracle_kind,
                causal_validity_rule=str(
                    metadata.get("causal_validity_rule") or "causally_valid_local_independence"
                ),
                eliminable_processes=eliminable_processes,
                process_family=process_family,
                policy_semantics=str(
                    metadata.get("policy_semantics") or "intensity_replacement"
                ),
                censoring_mode=str(
                    metadata.get("censoring_semantics")
                    or metadata.get("censoring_mode")
                    or "prevent_or_randomize"
                ),
                identification_method=str(
                    metadata.get("identification_method") or "continuous_time_reweighting"
                ),
                weighting_components=weighting_components,
                independent_censoring_checked=independent_censoring_checked,
                positivity_assumed=bool(metadata.get("positivity_assumed", True)),
                notes=tuple(
                    str(item) for item in metadata.get("continuous_time_notes", ()) if str(item)
                ),
            ),
            scope_statement=self._dynamic_scope_statement(
                covered_families=(
                    ("causally_valid_local_independence",) if validated else ()
                ),
                notes=(
                    "Continuous-time proofs require causal-validity and eliminability metadata; otherwise the proof kernel stays oracle-needed.",
                ),
            ),
        )

    @staticmethod
    def _continuous_time_string_tuple(payload: Any) -> tuple[str, ...]:
        if payload in (None, "", (), []):
            return ()
        if not isinstance(payload, (tuple, list, set)):
            payload = (payload,)
        return tuple(str(item).strip() for item in payload if str(item).strip())

    @classmethod
    def _continuous_time_graph_edges(
        cls,
        payload: Any,
    ) -> tuple[LocalIndependenceEdge, ...]:
        if payload in (None, "", (), []):
            return ()
        if not isinstance(payload, (tuple, list)):
            return ()
        edges: list[LocalIndependenceEdge] = []
        for item in payload:
            if isinstance(item, dict):
                src = str(item.get("src", "")).strip()
                dst = str(item.get("dst", "")).strip()
                edge_type = str(item.get("type") or item.get("edge_type") or "directed").strip()
                if src and dst:
                    edges.append(LocalIndependenceEdge(src=src, dst=dst, edge_type=edge_type))
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                src = str(item[0]).strip()
                dst = str(item[1]).strip()
                if src and dst:
                    edges.append(LocalIndependenceEdge(src=src, dst=dst))
        return tuple(edges)

    @classmethod
    def _continuous_time_elimination_sequence(
        cls,
        payload: Any,
    ) -> tuple[EliminabilityStep, ...]:
        if payload in (None, "", (), []):
            return ()
        if not isinstance(payload, (tuple, list)):
            return ()
        steps: list[EliminabilityStep] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                continue
            removed = cls._continuous_time_string_tuple(item.get("removed"))
            if not removed:
                continue
            steps.append(
                EliminabilityStep(
                    step=int(item.get("step", index)),
                    removed=removed,
                    justification_kind=str(
                        item.get("justification_kind")
                        or item.get("kind")
                        or "delta_separation"
                    ),
                    witness=(
                        str(item.get("witness")).strip()
                        if item.get("witness") not in (None, "")
                        else None
                    ),
                )
            )
        return tuple(steps)

    def _build_local_independence_certificate(
        self,
        query: ContinuousTimeQuery,
        attachment: DynamicSemanticsAttachment,
        *,
        proof_status: Literal["identified", "oracle_needed"],
        query_ref: str | None = None,
    ) -> tuple[LocalIndependenceWeightingCertificate, ArtifactRefModel | None]:
        metadata = dict(query.metadata or {})
        continuous = attachment.continuous_time_attachment
        markov_certificate = attachment.markov_criterion_certificate
        oracle = (
            continuous.graphical_oracle
            if continuous is not None
            else GraphicalOracleKind.MU
        )
        process_family = str(
            metadata.get("process_family")
            or (continuous.process_family if continuous is not None else "counting_process")
            or "counting_process"
        ).strip().lower()
        if process_family not in {"counting_process", "marked_point_process", "event_log"}:
            process_family = "counting_process"
        theorem_family = str(
            metadata.get("theorem_family")
            or metadata.get("algorithm_version")
            or "local_independence_weighting_v1"
        ).strip()
        theorem_reference = self._continuous_time_string_tuple(
            metadata.get("theorem_reference")
            or (
                "Røysland–Ryalen–Nygård–Didelez (2024/2025), Theorem 2",
                "Røysland et al., Proposition 1 (likelihood ratio / change of measure)",
            )
        )
        intervention_targets = self._continuous_time_string_tuple(
            metadata.get("intervention_targets")
        )
        treatment_node = (
            intervention_targets[0]
            if intervention_targets
            else str(metadata.get("treatment_process") or "X").strip()
        )
        eliminable_processes = self._continuous_time_string_tuple(
            metadata.get("eliminable_processes")
        )
        elimination_sequence = self._continuous_time_elimination_sequence(
            metadata.get("elimination_sequence")
        )
        eliminability_checked = bool(
            metadata.get("eliminability_verified", bool(eliminable_processes or elimination_sequence))
        )
        independent_censoring_checked = bool(
            metadata.get("independent_censoring_verified", proof_status == "identified")
        )
        positivity_assumed = bool(metadata.get("positivity_assumed", True))
        assumptions: list[str] = []
        if bool(metadata.get("causal_validity_verified", False)):
            assumptions.append("causal_validity_intensity_replacement")
        if independent_censoring_checked:
            assumptions.append("independent_censoring_local")
        if eliminability_checked:
            assumptions.append("eliminable_latent_processes")
        if positivity_assumed:
            assumptions.append("bounded_likelihood_ratio")

        proof_trace: list[str] = [
            "continuous_time_query",
            "event_process_view",
            "local_independence_graph",
            "LI_CAUSAL_VALIDITY",
        ]
        if independent_censoring_checked:
            proof_trace.append("LI_IC_CENSORING")
        if elimination_sequence:
            proof_trace.extend(
                f"LI_ELIMINABILITY_STEP:{step.step}:{','.join(step.removed)}"
                for step in elimination_sequence
            )
        elif eliminability_checked:
            proof_trace.append("LI_ELIMINABILITY_STEP")
        if proof_status == "identified":
            proof_trace.append("LI_WEIGHTING_IDENTIFY")
        else:
            proof_trace.append("LI_RESEARCH_BOUNDARY")
        if markov_certificate is not None:
            proof_trace.extend(
                item
                for item in markov_certificate.transformation_trace
                if item not in proof_trace
            )

        certificate = LocalIndependenceWeightingCertificate(
            verification_status=proof_status,
            theorem_family=theorem_family,
            target=LocalIndependenceTarget(
                functional=str(
                    metadata.get("event_functional")
                    or metadata.get("target_functional_override")
                    or "cumulative_incidence_difference"
                ),
                outcome_process=query.outcome_process,
                horizon_start=float(query.horizon_start),
                horizon_end=float(query.horizon_end),
                time_scale=query.time_scale,
                contrast_policy=str(metadata.get("contrast_policy") or "pi"),
                contrast_baseline=str(
                    metadata.get("contrast_baseline") or metadata.get("baseline_policy") or "natural_or_pi0"
                ),
            ),
            graph=LocalIndependenceGraphSpec(
                process_family=process_family,
                representation=str(
                    metadata.get("lig_representation")
                    or metadata.get("graph_representation")
                    or "LIG_or_muDMG"
                ),
                separation_criterion=(
                    "delta_or_mu"
                    if oracle not in {GraphicalOracleKind.DELTA, GraphicalOracleKind.MU}
                    else oracle.value
                ),
                graph_ref=str(
                    metadata.get("lig_graph_ref") or metadata.get("graph_ref") or ""
                ).strip()
                or None,
                latent_projection_ref=str(
                    metadata.get("latent_projection_ref") or ""
                ).strip()
                or None,
                nodes=self._continuous_time_string_tuple(metadata.get("graph_nodes")),
                edges=self._continuous_time_graph_edges(metadata.get("graph_edges")),
                latent_nodes=self._continuous_time_string_tuple(metadata.get("latent_nodes")),
                notes=self._continuous_time_string_tuple(metadata.get("graph_notes")),
            ),
            treatment_intervention=TreatmentIntensityInterventionSpec(
                node=treatment_node,
                predictable_wrt=self._continuous_time_string_tuple(
                    metadata.get("conditioning_processes")
                    or metadata.get("predictable_wrt")
                ),
                lambda_pi_ref=str(metadata.get("lambda_pi_ref") or "").strip() or None,
                absolute_continuity_assumed=bool(
                    metadata.get("absolute_continuity_assumed", True)
                ),
                bound_note=str(metadata.get("bound_note") or "").strip() or None,
            ),
            censoring_intervention=CensoringInterventionSpec(
                node=str(metadata.get("censoring_node") or "C").strip() or "C",
                mode=str(
                    metadata.get("censoring_semantics")
                    or metadata.get("censoring_mode")
                    or "prevent_or_randomize"
                ),
                lambda_c_ref=str(metadata.get("lambda_c_ref") or "").strip() or None,
                value=metadata.get("censoring_value"),
            ),
            identification=LocalIndependenceIdentificationSpec(
                theorem_reference=theorem_reference,
                weight_components=self._continuous_time_string_tuple(
                    metadata.get("weight_components")
                    or ("W_treatment", "W_censoring")
                ),
                formula_hint=str(metadata.get("formula_hint") or "").strip() or None,
                marginalize_over=self._continuous_time_string_tuple(
                    metadata.get("marginalize_over")
                ),
                decensoring_map_used=bool(metadata.get("decensoring_map_used", True)),
                decensoring_note=str(metadata.get("decensoring_note") or "").strip() or None,
            ),
            graphical_checks=LocalIndependenceGraphicalChecks(
                independent_censoring=IndependentCensoringCheck(
                    checked=independent_censoring_checked,
                    criterion=str(
                        metadata.get("independent_censoring_criterion")
                        or ("mu_separation" if oracle is GraphicalOracleKind.MU else "delta_separation")
                    ),
                    statement=str(
                        metadata.get("independent_censoring_statement")
                        or "C is locally independent of the target given the declared conditioning history."
                    ),
                    conditioning_set=self._continuous_time_string_tuple(
                        metadata.get("independent_censoring_conditioning_set")
                        or metadata.get("conditioning_processes")
                    ),
                    blocked_trails=self._continuous_time_string_tuple(
                        metadata.get("blocked_trails")
                    ),
                ),
                eliminability=EliminabilityCheck(
                    checked=eliminability_checked,
                    target_node=treatment_node,
                    eliminate_set=eliminable_processes,
                    elimination_sequence=elimination_sequence,
                ),
            ),
            runtime_requirements=LocalIndependenceRuntimeRequirements(
                needed_intensity_models=tuple(
                    IntensityModelRequirement(
                        process=str(item.get("process")),
                        conditioning=self._continuous_time_string_tuple(item.get("conditioning")),
                        estimation=str(item.get("estimation") or "parametric"),
                    )
                    for item in metadata.get("needed_intensity_models", ())
                    if isinstance(item, dict) and str(item.get("process", "")).strip()
                ),
                data_contract=str(
                    metadata.get("event_data_contract")
                    or metadata.get("data_contract")
                    or "event_log_or_counting_process_panel"
                ),
                positivity_assumed=positivity_assumed,
                diagnostics_required=bool(metadata.get("positivity_diagnostics_required", True)),
            ),
            assumptions=tuple(assumptions),
            proof_trace=tuple(proof_trace),
            metadata={
                "query_ref": query_ref,
                "runtime_support_status": query.runtime_support_status.value,
                "runtime_blockers": list(query.runtime_blockers),
            },
        )
        certificate_ref: ArtifactRefModel | None = None
        if self._artifact_store is not None:
            certificate_ref = persist_local_independence_weighting_certificate(
                self._artifact_store,
                certificate,
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (query.intervention_trajectory_ref, "intervention_trajectory"),
                ),
            )
        return certificate, certificate_ref

    @staticmethod
    def _normalize_temporal_identification_certificate(
        identification_certificate: TemporalIdentificationCertificate | dict[str, Any] | None = None,
        *,
        query: ContinuousTimeQuery | None = None,
    ) -> TemporalIdentificationCertificate | None:
        payload = identification_certificate
        if payload is None and query is not None:
            payload = (query.metadata or {}).get("temporal_identification_certificate")
        if payload is None:
            return None
        if isinstance(payload, TemporalIdentificationCertificate):
            return payload
        return TemporalIdentificationCertificate.model_validate(payload)

    @staticmethod
    def _temporal_strategic_adaptation_mode(query: ContinuousTimeQuery) -> str:
        raw = (query.metadata or {}).get(
            "strategic_adaptation_mode",
            StrategicAdaptationMode.ABSENT.value,
        )
        if isinstance(raw, StrategicAdaptationMode):
            return raw.value
        candidate = str(raw).strip().lower()
        return candidate or StrategicAdaptationMode.ABSENT.value

    @classmethod
    def _temporal_identification_scope_is_supported(
        cls,
        query: ContinuousTimeQuery,
        certificate: TemporalIdentificationCertificate,
    ) -> bool:
        if query.query_mode is not TemporalQueryMode.FIXED_INTERVENTION:
            return False
        if query.sampling_scheme is not TemporalSamplingScheme.REGULAR_GRID:
            return False
        if query.target_functional not in set(certificate.identified_functionals):
            return False
        if cls._temporal_strategic_adaptation_mode(query) != StrategicAdaptationMode.ABSENT.value:
            return False
        if str(certificate.intervention_semantics.value) != "surgical_replacement":
            return False
        if str(certificate.observability_regime.value) != "full_state":
            return False
        if not certificate.law_invariant:
            return False
        if (
            certificate.theorem_family
            is TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
        ):
            return certificate.law_object.value in {
                "generator",
                "semimartingale_characteristics",
            }
        if (
            certificate.theorem_family
            is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
        ):
            return (
                certificate.law_object.value == "canonical_control_path"
                and certificate.canonical_control_required
                and query.interpolation_policy
                in {
                    InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
                    InterventionInterpolationPolicy.LINEAR,
                }
                and certificate.control_canonicalization is query.interpolation_policy
            )
        return True

    @classmethod
    def _temporal_identification_scope_snapshot(
        cls,
        query: ContinuousTimeQuery,
        certificate: TemporalIdentificationCertificate,
    ) -> dict[str, Any]:
        notes = dict(certificate.notes or {})
        return {
            "theorem_family": certificate.theorem_family.value,
            "identified_functionals": [
                item.value for item in certificate.identified_functionals
            ],
            "intervention_semantics": certificate.intervention_semantics.value,
            "observability_regime": certificate.observability_regime.value,
            "law_object": certificate.law_object.value,
            "law_invariant": bool(certificate.law_invariant),
            "canonical_control_required": bool(certificate.canonical_control_required),
            "control_canonicalization": (
                None
                if certificate.control_canonicalization is None
                else certificate.control_canonicalization.value
            ),
            "support_status": certificate.support_status.value,
            "query_mode": query.query_mode.value,
            "sampling_scheme": query.sampling_scheme.value,
            "target_functional": query.target_functional.value,
            "interpolation_policy": query.interpolation_policy.value,
            "strategic_adaptation_mode": cls._temporal_strategic_adaptation_mode(query),
            "scope_covered": cls._temporal_identification_scope_is_supported(
                query,
                certificate,
            ),
            "tree_like_invariant_estimand": bool(
                notes.get("tree_like_invariant_estimand", False)
            ),
        }

    @classmethod
    def _continuous_time_theorem_attachment(
        cls,
        query: ContinuousTimeQuery,
        certificate: TemporalIdentificationCertificate,
    ) -> DynamicSemanticsAttachment:
        metadata = dict(query.metadata or {})
        intervention_targets = cls._continuous_time_string_tuple(
            metadata.get("intervention_targets")
            or metadata.get("observed_intervention_channel")
        )
        supported = cls._temporal_identification_scope_is_supported(query, certificate)
        notes = [
            "Continuous-time theorem path identifies law-invariant trajectory functionals only.",
            f"intervention_semantics={certificate.intervention_semantics.value}",
            f"observability_regime={certificate.observability_regime.value}",
            f"law_object={certificate.law_object.value}",
        ]
        if certificate.theorem_family is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1:
            notes.append(
                "Canonical control representative is required for neural CDE identification."
            )
        return DynamicSemanticsAttachment(
            semantics_family=DynamicSemanticsFamily.IOSCM,
            reduction_status=(
                DynamicReductionStatus.VALIDATED_REDUCTION
                if supported
                else DynamicReductionStatus.BLOCKED
            ),
            intervention_scope=InterventionScope(
                kind=InterventionKind.MECHANISM_SWAP,
                targets=intervention_targets,
                admissible=supported,
                admissibility_theorem=certificate.theorem_family.value,
            ),
            well_posedness_witness=WellPosednessWitness(
                status=(
                    WellPosednessStatus.PROVED
                    if supported
                    else WellPosednessStatus.HEURISTIC_BLOCKED
                ),
                family=certificate.theorem_family.value,
                method="temporal_identification_certificate",
                confidence="assumption_backed",
                warning=(
                    None
                    if supported
                    else "The supplied certificate does not cover the declared continuous-time query."
                ),
                evidence={
                    "identified_functionals": [
                        item.value for item in certificate.identified_functionals
                    ],
                    "assumptions": list(certificate.assumptions),
                    "support_status": certificate.support_status.value,
                },
            ),
            scope_statement=DynamicScopeStatement(
                covered_families=(
                    (certificate.theorem_family.value,) if supported else ()
                ),
                excluded_families=(
                    ()
                    if supported
                    else ("optimal_policy_discovery", "irregular_grid", "strategic_adaptation")
                ),
                notes=tuple(notes),
            ),
        )

    def identify_continuous_time_query(
        self,
        query: ContinuousTimeQuery,
        *,
        identification_certificate: TemporalIdentificationCertificate | dict[str, Any] | None = None,
        query_ref: str | None = None,
    ) -> ProofBundle:
        temporal_certificate = self._normalize_temporal_identification_certificate(
            identification_certificate,
            query=query,
        )
        if temporal_certificate is not None and temporal_certificate.theorem_family in {
            TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1,
            TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1,
        }:
            scope_snapshot = self._temporal_identification_scope_snapshot(
                query,
                temporal_certificate,
            )
            proof_status: Literal["identified", "non_identified", "oracle_needed"] = (
                "identified" if scope_snapshot["scope_covered"] else "oracle_needed"
            )
            attachment = self._continuous_time_theorem_attachment(query, temporal_certificate)
            metadata = {
                "status": proof_status,
                "query_mode": query.query_mode.value,
                "runtime_support_status": query.runtime_support_status.value,
                "runtime_blockers": list(query.runtime_blockers),
                "preferred_backend": str(
                    query.metadata.get("preferred_backend", "linear_sde")
                ).strip(),
                "outcome_process": query.outcome_process,
                "temporal_identification_certificate": temporal_certificate.model_dump(
                    mode="json"
                ),
                "identification_scope": scope_snapshot,
            }
            temporal_certificate_ref = None
            if self._artifact_store is not None:
                temporal_certificate_ref = persist_temporal_identification_certificate(
                    self._artifact_store,
                    temporal_certificate,
                    inputs=self._temporal_input_refs(
                        (query_ref, "query"),
                        (query.intervention_trajectory_ref, "intervention_trajectory"),
                    ),
                )
                metadata["temporal_identification_certificate_ref"] = self._serialize_ref(
                    temporal_certificate_ref
                )
            return build_dynamic_proof_bundle(
                dynamic_semantics=attachment,
                theorem_family=temporal_certificate.theorem_family.value,
                proof_status=proof_status,
                query_ref=query_ref,
                proof_trace=[
                    "observational_law_to_law_invariant_object",
                    "surgical_replacement_on_observed_channel",
                    "post_intervention_weak_uniqueness",
                ],
                assumptions=list(temporal_certificate.assumptions),
                metadata=metadata,
            )

        attachment = self._continuous_time_dynamic_attachment(query)
        proof_status: Literal["identified", "non_identified", "oracle_needed"]
        if attachment.reduction_status is DynamicReductionStatus.VALIDATED_REDUCTION:
            proof_status = "identified"
        else:
            proof_status = "oracle_needed"
        certificate, certificate_ref = self._build_local_independence_certificate(
            query,
            attachment,
            proof_status=proof_status,
            query_ref=query_ref,
        )
        result = li_id_algorithm(
            dynamic_semantics=attachment,
            certificate=certificate,
            query_ref=query_ref,
        )
        metadata = {
            **dict(result.metadata or {}),
            "status": proof_status,
            "query_mode": query.query_mode.value,
            "runtime_support_status": query.runtime_support_status.value,
            "runtime_blockers": list(query.runtime_blockers),
            "outcome_process": query.outcome_process,
            "local_independence_missing_requirements": [
                item
                for item in (
                    None
                    if "causal_validity_intensity_replacement" in certificate.assumptions
                    else "causal_validity_intensity_replacement",
                    None
                    if "independent_censoring_local" in certificate.assumptions
                    else "independent_censoring_local",
                    None
                    if "eliminable_latent_processes" in certificate.assumptions
                    else "eliminable_latent_processes",
                    None
                    if "bounded_likelihood_ratio" in certificate.assumptions
                    else "bounded_likelihood_ratio",
                )
                if item is not None
            ],
        }
        if certificate_ref is not None:
            metadata["local_independence_certificate_ref"] = self._serialize_ref(
                certificate_ref
            )
        temporal_certificate_ref = None
        if proof_status == "identified":
            temporal_certificate = build_temporal_identification_certificate(certificate)
            metadata["temporal_identification_certificate"] = temporal_certificate.model_dump(
                mode="json"
            )
        if proof_status == "identified" and self._artifact_store is not None:
            temporal_certificate_ref = persist_temporal_identification_certificate(
                self._artifact_store,
                temporal_certificate,
                inputs=self._temporal_input_refs(
                    (query.intervention_trajectory_ref, "intervention_trajectory"),
                    (certificate_ref, "local_independence_certificate"),
                ),
            )
            metadata["temporal_identification_certificate_ref"] = self._serialize_ref(
                temporal_certificate_ref
            )
        result = dataclasses.replace(
            result,
            metadata=metadata,
        )
        return proof_bundle_from_identification_result(
            result,
            query_ref=query_ref,
        )

    @staticmethod
    def _intervention_status_from_identification_status(
        status: IdentificationStatus,
    ) -> InterventionIdentificationStatus:
        if status is IdentificationStatus.IDENTIFIED:
            return InterventionIdentificationStatus.IDENTIFIED
        if status in {
            IdentificationStatus.HEDGE_FOUND,
            IdentificationStatus.NOT_RECOVERABLE,
        }:
            return InterventionIdentificationStatus.NOT_IDENTIFIABLE
        return InterventionIdentificationStatus.ORACLE_NEEDED

    @staticmethod
    def _intervention_target_vars(
        intervention: NodeIntervention
        | ConditionalIntervention
        | StochasticIntervention
        | MTPIntervention
        | EdgeIntervention
        | PathIntervention
        | TransportIntervention
        | InterferenceIntervention
        | CompositeIntervention,
    ) -> frozenset[str]:
        if isinstance(intervention, NodeIntervention):
            return frozenset(item.variable for item in intervention.assignments)
        if isinstance(intervention, ConditionalIntervention):
            return frozenset(item.target for item in intervention.assignments)
        if isinstance(intervention, StochasticIntervention):
            return frozenset(item.target for item in intervention.policies)
        if isinstance(intervention, MTPIntervention):
            return frozenset(item.target for item in intervention.policies)
        if isinstance(intervention, EdgeIntervention):
            return frozenset(item.source for item in intervention.assignments)
        if isinstance(intervention, PathIntervention):
            heads = [path[0] for path in (*intervention.active_paths, *intervention.frozen_paths) if path]
            return frozenset(heads)
        if isinstance(intervention, TransportIntervention):
            if intervention.base_intervention is None:
                return frozenset()
            return CausalEngine._intervention_target_vars(intervention.base_intervention)
        if isinstance(intervention, InterferenceIntervention):
            return frozenset(item.target for item in intervention.policies)
        if isinstance(intervention, CompositeIntervention):
            return frozenset().union(
                *(CausalEngine._intervention_target_vars(step) for step in intervention.steps)
            )
        return frozenset()

    @staticmethod
    def _effective_intervention_expr(
        intervention: NodeIntervention
        | ConditionalIntervention
        | StochasticIntervention
        | MTPIntervention
        | EdgeIntervention
        | PathIntervention
        | TransportIntervention
        | InterferenceIntervention
        | CompositeIntervention,
    ) -> Any:
        if isinstance(intervention, TransportIntervention):
            base = (
                CausalEngine._effective_intervention_expr(intervention.base_intervention)
                if intervention.base_intervention is not None
                else None
            )
            return intervention.model_copy(update={"base_intervention": base})
        if not isinstance(intervention, CompositeIntervention):
            return intervention

        steps = [CausalEngine._effective_intervention_expr(step) for step in intervention.steps]
        transport = next(
            (step for step in reversed(steps) if isinstance(step, TransportIntervention)),
            None,
        )
        non_transport_steps = [
            step for step in steps if not isinstance(step, TransportIntervention)
        ]
        if transport is not None:
            if not non_transport_steps:
                return transport
            base = (
                non_transport_steps[0]
                if len(non_transport_steps) == 1
                else CausalEngine._effective_intervention_expr(
                    CompositeIntervention(steps=tuple(non_transport_steps))
                )
            )
            return transport.model_copy(update={"base_intervention": base})
        for kind in (PathIntervention, EdgeIntervention, InterferenceIntervention):
            matched = [step for step in steps if isinstance(step, kind)]
            if matched:
                return matched[-1]
        return steps[-1]

    @staticmethod
    def _legacy_intervention_query(
        *,
        treatment: frozenset[str],
        outcome: frozenset[str],
        dataset_ref: str | None,
        conditions: frozenset[str],
        condition_vars: frozenset[str] | None,
        policy: Any | None,
        treatment_sequence: list[str] | None,
        s_nodes: list[Any] | None,
        counterfactual_query: CtfQuery | None,
        distribution_query: DistributionLawQuery | None,
        outcomes: list[str] | None,
        proxy_map: dict[str, str] | None,
    ) -> InterventionQuery | None:
        if (
            counterfactual_query is not None
            or distribution_query is not None
            or outcomes is not None
            or proxy_map is not None
        ):
            return None

        target = QueryTarget(
            target_kind=(
                QueryTargetKind.CONDITIONAL_DISTRIBUTION
                if conditions
                else QueryTargetKind.DISTRIBUTION
            ),
            outcome_variables=tuple(sorted(outcome)),
            conditioning=tuple(sorted(conditions)),
        )

        if treatment_sequence:
            intervention: Any = ConditionalIntervention(
                assignments=tuple(
                    ConditionalPolicy(
                        target=name,
                        policy_expr=f"g_{index}(H_{index})",
                        history_vars=tuple(treatment_sequence[:index]),
                    )
                    for index, name in enumerate(treatment_sequence)
                ),
                regime_kind="dynamic",
            )
        elif condition_vars:
            history_vars = tuple(sorted(condition_vars))
            intervention = ConditionalIntervention(
                assignments=tuple(
                    ConditionalPolicy(
                        target=name,
                        policy_expr="g(Z)",
                        history_vars=history_vars,
                    )
                    for name in sorted(treatment)
                )
            )
        elif policy is not None:
            conditioning_vars = tuple(getattr(policy, "conditioning_vars", ()) or ())
            policy_expr = str(getattr(policy, "policy_expr", "") or "").strip()
            policy_type = str(getattr(policy, "policy_type", "") or "soft").strip().lower()
            if policy_type == "conditional":
                intervention = ConditionalIntervention(
                    assignments=tuple(
                        ConditionalPolicy(
                            target=name,
                            policy_expr=policy_expr or "g(Z)",
                            history_vars=conditioning_vars,
                        )
                        for name in sorted(treatment)
                    )
                )
            elif policy_type == "shift":
                shift_delta = getattr(policy, "shift_delta", None)
                intervention = MTPIntervention(
                    policies=tuple(
                        ModifiedTreatmentPolicySpec(
                            target=name,
                            policy_expr=(
                                policy_expr
                                or (
                                    f"{name}+{shift_delta}"
                                    if shift_delta is not None
                                    else f"shift({name})"
                                )
                            ),
                            natural_treatment=name,
                            covariates=conditioning_vars,
                        )
                        for name in sorted(treatment)
                    )
                )
            else:
                intervention = StochasticIntervention(
                    policies=tuple(
                        StochasticPolicySpec(
                            target=name,
                            distribution_expr=(
                                policy_expr
                                or (
                                    f"pi({name}|{','.join(conditioning_vars)})"
                                    if conditioning_vars
                                    else f"pi({name})"
                                )
                            ),
                            conditioning_vars=conditioning_vars,
                        )
                        for name in sorted(treatment)
                    )
                )
        else:
            intervention = NodeIntervention(
                assignments=tuple(
                    VariableAssignment(variable=name, value_expr="query-assignment")
                    for name in sorted(treatment)
                )
            )

        if s_nodes:
            selection_nodes = tuple(
                sorted(getattr(node, "target_variable", str(node)) for node in s_nodes)
            )
            intervention = TransportIntervention(
                source_domain="source",
                target_domain="target",
                selection_nodes=selection_nodes,
                available_data_refs=((dataset_ref,) if dataset_ref else ()),
                soft_transport=isinstance(intervention, StochasticIntervention),
                base_intervention=intervention,
            )

        return InterventionQuery(target=target, intervention=intervention)

    def _decorate_identification_result_with_intervention_query(
        self,
        result: IdentificationResult,
        query: InterventionQuery,
    ) -> IdentificationResult:
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir

        fallback = (
            InterventionFallback(
                fallback_attempted=True,
                fallback_mode=InterventionFallbackMode.ORACLE,
                fallback_explanation=(
                    "Current proof kernel does not natively identify this intervention class."
                ),
            )
            if result.status is not IdentificationStatus.IDENTIFIED
            else InterventionFallback()
        )
        certificate = build_intervention_certificate(
            query=query,
            identification_status=self._intervention_status_from_identification_status(
                result.status
            ),
            estimand_ast=result.estimand_ast,
            proof_steps=tuple(_internal_proof_step_to_ir(step) for step in result.proof_steps),
            required_distributions=tuple(result.required_distributions),
            fallback=fallback,
        )
        metadata = {
            **dict(getattr(result, "metadata", {}) or {}),
            "query_kind": "intervention",
            "intervention_query": query.model_dump(mode="json"),
            "intervention_query_string": render_intervention_query(query),
            **certificate.proofbundle_metadata,
        }
        return dataclasses.replace(
            result,
            query_str=getattr(result, "query_str", "") or render_intervention_query(query),
            metadata=metadata,
        )

    @staticmethod
    def _intervention_typecheck_negative_certificate(
        query: InterventionQuery,
    ) -> NegativeCertificate:
        certificate = certificate_for_typecheck_failure(query)
        proof_trace = [
            reduction.description or reduction.rule_name
            for reduction in certificate.reduction_chain
        ]
        return NegativeCertificate(
            blocking_type=BlockingType.INTERVENTION_TYPECHECK,
            blocking_description=certificate.fallback.fallback_explanation or "ill-typed intervention composition",
            technical_detail=render_intervention_query(query),
            quantitative_diagnostics={
                **certificate.proofbundle_metadata,
                "intervention_query": query.model_dump(mode="json"),
                "intervention_query_string": render_intervention_query(query),
                "identification_status": certificate.identification_status.value,
                "algorithm_version": "intervention_type_system_v1",
                "proof_trace": proof_trace,
            },
            constructive_message=(
                "Revise the intervention composition so natural-value dependencies, "
                "granularity, and transport/interference wrappers remain well-defined."
            ),
        )

    @staticmethod
    def _oracle_needed_intervention_result(
        *,
        query: InterventionQuery,
        algorithm_version: str,
        trace_message: str,
        estimand_ast: EstimandAST | None = None,
    ) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.ORACLE_NEEDED,
            estimand_ast=estimand_ast,
            hedge_certificate=None,
            trace=[trace_message],
            required_distributions=[],
            algorithm_version=algorithm_version,
            query_str=render_intervention_query(query),
        )

    @staticmethod
    def _graph_has_bidirected_confounding(graph: CausalGraphModel) -> bool:
        return any(
            edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
            for edge in graph.edges
        )

    @staticmethod
    def _directed_adjacency(graph: CausalGraphModel) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = {node: [] for node in graph.nodes}
        for edge in graph.edges:
            if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
                adjacency.setdefault(edge.src, []).append(edge.dst)
        for node in adjacency:
            adjacency[node] = sorted(dict.fromkeys(adjacency[node]))
        return adjacency

    @staticmethod
    def _effective_intervention_type_name(query: InterventionQuery) -> str:
        effective = CausalEngine._effective_intervention_expr(query.intervention)
        return str(getattr(effective, "intervention_type", query.intervention.intervention_type))

    @staticmethod
    def _intervention_negative_certificate(
        *,
        query: InterventionQuery,
        blocking_type: BlockingType,
        blocking_description: str,
        algorithm_version: str,
        constructive_message: str,
        proof_trace: list[str] | tuple[str, ...],
        intervention_status: InterventionIdentificationStatus = (
            InterventionIdentificationStatus.NOT_IDENTIFIABLE
        ),
        negative_payload: dict[str, Any] | None = None,
        extra_diagnostics: dict[str, Any] | None = None,
    ) -> NegativeCertificate:
        certificate = build_intervention_certificate(
            query=query,
            identification_status=intervention_status,
            negative_certificate=negative_payload
            or {
                "blocking_type": blocking_type.value,
                "blocking_description": blocking_description,
            },
        )
        diagnostics = {
            **certificate.proofbundle_metadata,
            "query_kind": "intervention",
            "intervention_query": query.model_dump(mode="json"),
            "intervention_query_string": render_intervention_query(query),
            "intervention_type": CausalEngine._effective_intervention_type_name(query),
            "identification_status": intervention_status.value,
            "algorithm_version": algorithm_version,
            "proof_trace": list(proof_trace),
        }
        if extra_diagnostics:
            diagnostics.update(extra_diagnostics)
        return NegativeCertificate(
            blocking_type=blocking_type,
            blocking_description=blocking_description,
            technical_detail=render_intervention_query(query),
            quantitative_diagnostics=diagnostics,
            constructive_message=constructive_message,
        )

    def _identify_sigma_stochastic_intervention(
        self,
        *,
        query: InterventionQuery,
        graph: CausalGraphModel,
        oracle: str,
        dataset_ref: str | None,
        intervention: StochasticIntervention,
        outcome: frozenset[str],
    ) -> IdentificationResult:
        from polisyos.foundry.methods.catalog.causal.sigma_calculus import sigma_identify

        policy_spec = intervention.policies[0]
        base_result = id_with_oracle_fallback(
            treatment=frozenset({policy_spec.target}),
            outcome=outcome,
            graph=graph,
            oracle=oracle,
            dataset_ref=dataset_ref,
        )
        if (
            base_result.status is not IdentificationStatus.IDENTIFIED
            or base_result.estimand_ast is None
        ):
            return dataclasses.replace(
                base_result,
                algorithm_version="sigma_calculus_v1",
                query_str=render_intervention_query(query),
                trace=[
                    *list(base_result.trace),
                    "sigma_calculus: base atomic identification failed",
                ],
                metadata={
                    **dict(getattr(base_result, "metadata", {}) or {}),
                    "policy_type": "soft",
                    "policy_conditioning_vars": list(policy_spec.conditioning_vars),
                    "policy_expr": policy_spec.distribution_expr,
                },
            )

        sigma_ast, sigma_steps = sigma_identify(
            base_result.estimand_ast,
            graph,
            selection_vars=frozenset({policy_spec.target}),
        )
        outcome_name = next(iter(sorted(outcome)))
        root = StochasticInterventionNode(
            treatment_var=policy_spec.target,
            policy=StochasticPolicy(
                policy_type="soft",
                conditioning_vars=policy_spec.conditioning_vars,
                policy_expr=policy_spec.distribution_expr,
            ),
            inner_do_node=sigma_ast.root,
            integration_var=policy_spec.target,
        )
        return IdentificationResult(
            status=IdentificationStatus.IDENTIFIED,
            estimand_ast=EstimandAST(
                query_str=render_intervention_query(query),
                root=root,
                treatment=policy_spec.target,
                outcome=outcome_name,
                all_variables=tuple(
                    sorted(
                        {
                            policy_spec.target,
                            outcome_name,
                            *policy_spec.conditioning_vars,
                        }
                    )
                ),
                identification_method="sigma_calculus",
            ),
            hedge_certificate=None,
            trace=[
                *list(base_result.trace),
                (
                    "sigma_calculus: rewrote atomic do-estimand under a mechanism "
                    f"shift for {policy_spec.target}"
                ),
            ],
            required_distributions=list(base_result.required_distributions),
            algorithm_version="sigma_calculus_v1",
            proof_steps=[*list(base_result.proof_steps), *sigma_steps],
            metadata={
                **dict(getattr(base_result, "metadata", {}) or {}),
                "policy_type": "soft",
                "policy_conditioning_vars": list(policy_spec.conditioning_vars),
                "policy_expr": policy_spec.distribution_expr,
                "sigma_selection_vars": [policy_spec.target],
            },
        )

    def _identify_sigma_transport_intervention(
        self,
        *,
        query: InterventionQuery,
        graph: CausalGraphModel,
        dataset_ref: str | None,
        intervention: TransportIntervention,
        outcome: frozenset[str],
    ) -> IdentificationResult:
        from polisyos.foundry.methods.catalog.causal.sigma_calculus import sigma_identify

        selection_vars = frozenset(intervention.selection_nodes)
        base_intervention = intervention.base_intervention
        if isinstance(base_intervention, StochasticIntervention):
            policy_spec = base_intervention.policies[0]
            base_result = self._identify_with_s_nodes(
                frozenset({policy_spec.target}),
                outcome,
                graph,
                list(selection_vars or {policy_spec.target}),
                dataset_ref,
            )
            if (
                base_result.status is not IdentificationStatus.IDENTIFIED
                or base_result.estimand_ast is None
            ):
                return dataclasses.replace(
                    base_result,
                    algorithm_version="sigma_transport_v1",
                    query_str=render_intervention_query(query),
                    trace=[
                        *list(base_result.trace),
                        "sigma_transport: base transport identification failed",
                    ],
                )
            sigma_ast, sigma_steps = sigma_identify(
                base_result.estimand_ast,
                graph,
                selection_vars=selection_vars or frozenset({policy_spec.target}),
            )
            outcome_name = next(iter(sorted(outcome)))
            root = StochasticInterventionNode(
                treatment_var=policy_spec.target,
                policy=StochasticPolicy(
                    policy_type="soft",
                    conditioning_vars=policy_spec.conditioning_vars,
                    policy_expr=policy_spec.distribution_expr,
                ),
                inner_do_node=sigma_ast.root,
                integration_var=policy_spec.target,
            )
            return IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=EstimandAST(
                    query_str=render_intervention_query(query),
                    root=root,
                    treatment=policy_spec.target,
                    outcome=outcome_name,
                    all_variables=tuple(
                        sorted(
                            {
                                policy_spec.target,
                                outcome_name,
                                *policy_spec.conditioning_vars,
                            }
                        )
                    ),
                    identification_method="sigma_transport",
                ),
                hedge_certificate=None,
                trace=[
                    *list(base_result.trace),
                    (
                        "sigma_transport: combined transport identification with "
                        f"selection-aware sigma-calculus for {policy_spec.target}"
                    ),
                ],
                required_distributions=list(base_result.required_distributions),
                algorithm_version="sigma_transport_v1",
                proof_steps=[*list(base_result.proof_steps), *sigma_steps],
                metadata={
                    **dict(getattr(base_result, "metadata", {}) or {}),
                    "transport_source_domain": intervention.source_domain,
                    "transport_target_domain": intervention.target_domain,
                    "transport_selection_nodes": list(intervention.selection_nodes),
                    "policy_type": "soft",
                    "policy_conditioning_vars": list(policy_spec.conditioning_vars),
                    "policy_expr": policy_spec.distribution_expr,
                },
            )

        if isinstance(base_intervention, NodeIntervention):
            treatment = frozenset(item.variable for item in base_intervention.assignments)
            base_result = self._identify_with_s_nodes(
                treatment,
                outcome,
                graph,
                list(selection_vars),
                dataset_ref,
            )
            if (
                base_result.status is not IdentificationStatus.IDENTIFIED
                or base_result.estimand_ast is None
            ):
                return dataclasses.replace(
                    base_result,
                    algorithm_version="sigma_transport_v1",
                    query_str=render_intervention_query(query),
                    trace=[
                        *list(base_result.trace),
                        "sigma_transport: base transport identification failed",
                    ],
                )
            sigma_ast, sigma_steps = sigma_identify(
                base_result.estimand_ast,
                graph,
                selection_vars=selection_vars,
            )
            return dataclasses.replace(
                base_result,
                estimand_ast=sigma_ast,
                algorithm_version="sigma_transport_v1",
                query_str=render_intervention_query(query),
                trace=[
                    *list(base_result.trace),
                    (
                        "sigma_transport: rewrote transport estimand with explicit "
                        f"selection vars {sorted(selection_vars)}"
                    ),
                ],
                proof_steps=[*list(base_result.proof_steps), *sigma_steps],
                metadata={
                    **dict(getattr(base_result, "metadata", {}) or {}),
                    "transport_source_domain": intervention.source_domain,
                    "transport_target_domain": intervention.target_domain,
                    "transport_selection_nodes": list(intervention.selection_nodes),
                },
            )

        return self._oracle_needed_intervention_result(
            query=query,
            algorithm_version="sigma_transport_v1",
            trace_message=(
                "soft transport currently supports atomic node or stochastic "
                "base interventions"
            ),
        )

    def _maybe_identify_proximal_path_intervention(
        self,
        *,
        query: InterventionQuery,
        graph: CausalGraphModel,
        dataset_ref: str | None,
        intervention: PathIntervention,
        outcome: frozenset[str],
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None,
    ) -> IdentificationResult | NegativeCertificate | None:
        """Try the Stage 11.3 single-mediator proximal mediation template."""

        if proximal_annotation is None or not self._graph_has_bidirected_confounding(graph):
            return None

        paths = tuple(intervention.active_paths) + tuple(intervention.frozen_paths)
        if not paths:
            return None
        treatment_name = paths[0][0]
        outcome_name = next(iter(sorted(outcome)))
        mediator_candidates = sorted(
            {
                *intervention.natural_value_vars,
                *(node for path in paths for node in path[1:-1]),
            }
        )
        if len(mediator_candidates) != 1:
            return None
        mediator = mediator_candidates[0]

        from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
            PROXIMAL_MEDIATION_V1_THEOREM,
            proximal_mediation_identify_v1,
        )

        certificate = proximal_mediation_identify_v1(
            graph,
            treatment=treatment_name,
            mediator=mediator,
            outcome=outcome_name,
            proxies=proximal_annotation,
            target_effect=_infer_proximal_path_target(
                treatment=treatment_name,
                mediator=mediator,
                outcome=outcome_name,
                intervention=intervention,
            ),
        )
        if isinstance(certificate, NegativeCertificate):
            return self._intervention_negative_certificate(
                query=query,
                blocking_type=certificate.blocking_type,
                blocking_description=certificate.blocking_description,
                algorithm_version=PROXIMAL_MEDIATION_V1_THEOREM,
                constructive_message=certificate.constructive_message,
                proof_trace=list(
                    certificate.quantitative_diagnostics.get("proof_trace", ()) or ()
                ),
                negative_payload={
                    "blocking_type": certificate.blocking_type.value,
                    "blocking_description": certificate.blocking_description,
                    "failed_check": certificate.quantitative_diagnostics.get("failed_check"),
                },
                extra_diagnostics={
                    **dict(certificate.quantitative_diagnostics or {}),
                    "path_specific_proximal": True,
                    "target_effect": _infer_proximal_path_target(
                        treatment=treatment_name,
                        mediator=mediator,
                        outcome=outcome_name,
                        intervention=intervention,
                    ),
                    "mediator": mediator,
                },
            )

        all_variables = tuple(
            sorted(
                {
                    treatment_name,
                    mediator,
                    outcome_name,
                    *certificate.variable_roles.get("X", ()),
                    *certificate.variable_roles.get("Z", ()),
                    *certificate.variable_roles.get("W", ()),
                }
            )
        )
        target_effect = certificate.query.target_effect
        proxy_annotation = (
            proximal_annotation
            if isinstance(proximal_annotation, ProxyAnnotation)
            else ProxyAnnotation.model_validate(proximal_annotation)
        )
        oracle_assumptions_accepted = bool(
            getattr(proxy_annotation, "accept_oracle_assumptions", False)
        )
        root = PathSpecificNode(
            treatment=treatment_name,
            outcome=outcome_name,
            active_paths=intervention.active_paths,
            frozen_paths=intervention.frozen_paths,
            conditioning=tuple(query.target.conditioning),
            reference_treatment=certificate.query.reference_treatment_value,
            active_treatment=certificate.query.active_treatment_value,
            dataset_ref=dataset_ref,
        )
        proof_trace = list(certificate.proof_trace)
        if oracle_assumptions_accepted:
            proof_trace.append(
                "Proximal mediation template matched and oracle-level completeness assumptions were accepted for execution."
            )
        else:
            proof_trace.append(
                "Proximal mediation template matched; completeness remains an oracle-backed requirement."
            )
        if query.target.conditioning:
            proof_trace.append(
                "Conditioning variables were preserved on the semantic path-specific node; execution still relies on the proximal template contract."
            )
        return IdentificationResult(
            status=(
                IdentificationStatus.IDENTIFIED
                if oracle_assumptions_accepted
                else IdentificationStatus.ORACLE_NEEDED
            ),
            estimand_ast=EstimandAST(
                query_str=render_intervention_query(query),
                root=root,
                treatment=treatment_name,
                outcome=outcome_name,
                all_variables=all_variables,
                identification_method=(
                    f"proximal_mediation|target={target_effect}|mediator={mediator}"
                ),
            ),
            hedge_certificate=None,
            trace=proof_trace,
            required_distributions=[],
            algorithm_version=PROXIMAL_MEDIATION_V1_THEOREM,
            proof_steps=[
                IRProofStep(
                    rule_name="PROXIMAL_MEDIATION_TEMPLATE",
                    description=(
                        "Matched the Stage 11.3 single-mediator proximal mediation "
                        "template and constructed the oracle-backed path-specific proof."
                    ),
                    variables_affected=tuple(sorted({treatment_name, mediator, outcome_name})),
                    graph_subset=graph.graph_type.value,
                    rule_formal_name="Proximal mediation template",
                    applicable_theorem="Dukes, Shpitser & Tchetgen Tchetgen (2023)",
                    graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
                    graph_state_after="proximal mediation oracle contract recorded",
                ),
                IRProofStep(
                    rule_name="PROXIMAL_MEDIATION_ORACLE_GATE",
                    description=(
                        "Recorded completeness and cross-world assumptions as explicit "
                        "oracle-level obligations and resolved the governance gate for execution."
                    ),
                    variables_affected=tuple(sorted({mediator, *certificate.variable_roles.get("Z", ()), *certificate.variable_roles.get("W", ())})),
                    graph_subset=graph.graph_type.value,
                    rule_formal_name="Oracle gate",
                    applicable_theorem=PROXIMAL_MEDIATION_V1_THEOREM,
                    graph_state_before="template matched",
                    graph_state_after=(
                        "proof status promoted to identified"
                        if oracle_assumptions_accepted
                        else "proof status downgraded to oracle_needed"
                    ),
                ),
            ],
            metadata={
                "proximal_mediation_certificate": certificate.model_dump(mode="json"),
                "path_specific_proximal": True,
                "path_specific_mode": "template_proximal",
                "target_effect": target_effect,
                "fallback_policy": certificate.diagnostics_and_gates.get("fallback_policy"),
                "oracle_flags": certificate.diagnostics_and_gates.get("oracle_flags", []),
                "oracle_assumptions_accepted": oracle_assumptions_accepted,
                "conditioning_variables": list(query.target.conditioning),
            },
            query_str=render_intervention_query(query),
        )

    def _identify_path_intervention_backend(
        self,
        *,
        query: InterventionQuery,
        graph: CausalGraphModel,
        dataset_ref: str | None,
        intervention: PathIntervention,
        outcome: frozenset[str],
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None = None,
    ) -> IdentificationResult | NegativeCertificate:
        proximal_template_result = self._maybe_identify_proximal_path_intervention(
            query=query,
            graph=graph,
            dataset_ref=dataset_ref,
            intervention=intervention,
            outcome=outcome,
            proximal_annotation=proximal_annotation,
        )
        if proximal_template_result is not None:
            if isinstance(proximal_template_result, IdentificationResult):
                return self._decorate_identification_result_with_intervention_query(
                    proximal_template_result,
                    query,
                )
            return proximal_template_result

        from polisyos.foundry.methods.catalog.causal.path_specific_identify import (
            identify_path_specific,
        )
        from polisyos.ir.analytics.path_specific_identification import (
            PathSpecificDecisionMode,
            PathSpecificWitnessKind,
        )

        outcome_name = next(iter(sorted(outcome)))
        width_budget_raw = (graph.metadata or {}).get("path_specific_width_budget")
        width_budget = None
        if isinstance(width_budget_raw, int) and width_budget_raw > 0:
            width_budget = width_budget_raw
        report = identify_path_specific(
            graph=graph,
            intervention=intervention,
            outcome=outcome_name,
            query_str=render_intervention_query(query),
            dataset_ref=dataset_ref,
            conditioning=tuple(query.target.conditioning),
            available_experimental_distributions=tuple(query.context.available_data_refs),
            width_budget=width_budget,
        )

        compilation = report.compilation_plan
        treatment_name = report.treatment
        mediators = report.semantic_query.mediators
        proof_trace = [*report.proof_trace, *report.fallback_trace]
        diagnostics = {
            "path_specific_mode": report.mode.value,
            "path_policy_hash": (
                compilation.path_policy_hash if compilation is not None else report.metadata.get("path_policy_hash")
            ),
            "district_partition": (
                [list(item) for item in compilation.district_partition]
                if compilation is not None
                else []
            ),
            "treatment_frontier": (
                [list(item) for item in compilation.treatment_frontier]
                if compilation is not None
                else []
            ),
            "intrinsic_width_bound": (
                compilation.intrinsic_width_bound if compilation is not None else None
            ),
            "witnesses": [item.model_dump(mode="json") for item in report.witnesses],
            "witness_variables": sorted(
                {
                    variable
                    for witness in report.witnesses
                    for variable in witness.variables
                }
            ),
        }
        if compilation is not None and compilation.compiled_estimand_ast is not None:
            diagnostics["compiled_path_specific_estimand_ast"] = (
                compilation.compiled_estimand_ast.model_dump(mode="json")
            )
            diagnostics["path_specific_compilation_plan"] = compilation.model_dump(mode="json")

        if report.mode is PathSpecificDecisionMode.EXACT_IDENTIFIED:
            all_variables = tuple(
                sorted(
                    {
                        outcome_name,
                        treatment_name,
                        *(
                            compilation.relevant_nodes
                            if compilation is not None
                            else [node for path in intervention.active_paths + intervention.frozen_paths for node in path]
                        ),
                    }
                )
            )
            result = IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=EstimandAST(
                    query_str=render_intervention_query(query),
                    root=PathSpecificNode(
                        treatment=treatment_name,
                        outcome=outcome_name,
                        active_paths=intervention.active_paths,
                        frozen_paths=intervention.frozen_paths,
                        conditioning=tuple(report.semantic_query.conditioning),
                        dataset_ref=dataset_ref,
                    ),
                    treatment=treatment_name,
                    outcome=outcome_name,
                    all_variables=all_variables,
                    identification_method="path_specific_id",
                ),
                hedge_certificate=None,
                trace=proof_trace,
                required_distributions=list(report.required_distributions),
                algorithm_version="path_intervention_v1",
                proof_steps=[
                    IRProofStep(
                        rule_name="PATH_ID_START",
                        description=(
                            "Constructed a path-specific effect query from the declared "
                            "active and frozen paths."
                        ),
                        variables_affected=tuple(sorted({treatment_name, outcome_name, *mediators})),
                        graph_subset=graph.graph_type.value,
                        rule_formal_name="Path-specific effect construction",
                        applicable_theorem="Avin, Shpitser & Pearl (2005), IJCAI",
                        graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
                        graph_state_after="path-specific query instantiated",
                    ),
                    IRProofStep(
                        rule_name="PATH_DISTRICT_COMPILE",
                        description=(
                            "Compiled the path policy into a district-local symbolic plan "
                            "with explicit frontier labels."
                        ),
                        variables_affected=tuple(sorted(compilation.relevant_nodes if compilation is not None else ())),
                        graph_subset=graph.graph_type.value,
                        rule_formal_name="District-local path compilation",
                        applicable_theorem=report.theorem_family,
                        graph_state_before="candidate path-specific effect",
                        graph_state_after="district-local compiled plan",
                    ),
                ],
                metadata={
                    **diagnostics,
                    **dict(report.metadata),
                    "required_distributions": [
                        item.model_dump(mode="json") for item in report.required_distributions
                    ],
                },
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        witness_kinds = {
            item.kind for item in report.witnesses
        }
        if report.mode is PathSpecificDecisionMode.EXACT_WITH_EXPERIMENTS:
            all_variables = tuple(
                sorted(
                    {
                        outcome_name,
                        treatment_name,
                        *(
                            compilation.relevant_nodes
                            if compilation is not None
                            else [
                                node
                                for path in intervention.active_paths + intervention.frozen_paths
                                for node in path
                            ]
                        ),
                    }
                )
            )
            result = IdentificationResult(
                status=IdentificationStatus.ORACLE_NEEDED,
                estimand_ast=EstimandAST(
                    query_str=render_intervention_query(query),
                    root=PathSpecificNode(
                        treatment=treatment_name,
                        outcome=outcome_name,
                        active_paths=intervention.active_paths,
                        frozen_paths=intervention.frozen_paths,
                        conditioning=tuple(report.semantic_query.conditioning),
                        dataset_ref=dataset_ref,
                    ),
                    treatment=treatment_name,
                    outcome=outcome_name,
                    all_variables=all_variables,
                    identification_method="path_specific_id",
                ),
                hedge_certificate=None,
                trace=proof_trace,
                required_distributions=list(report.required_distributions),
                algorithm_version="path_intervention_surrogate_v1",
                proof_steps=[
                    IRProofStep(
                        rule_name="PATH_ID_START",
                        description=(
                            "Constructed a path-specific effect query from the declared "
                            "active and frozen paths."
                        ),
                        variables_affected=tuple(sorted({treatment_name, outcome_name, *mediators})),
                        graph_subset=graph.graph_type.value,
                        rule_formal_name="Path-specific effect construction",
                        applicable_theorem="Avin, Shpitser & Pearl (2005), IJCAI",
                        graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
                        graph_state_after="path-specific query instantiated",
                    ),
                    IRProofStep(
                        rule_name="PATH_SURROGATE_COMPILE",
                        description=(
                            "Compiled the path query into a hybrid source/experimental "
                            "district-local formula that can be discharged once the "
                            "required surrogate distributions are bound."
                        ),
                        variables_affected=tuple(sorted(compilation.relevant_nodes if compilation is not None else ())),
                        graph_subset=graph.graph_type.value,
                        rule_formal_name="Surrogate-experiment path compilation",
                        applicable_theorem=report.theorem_family,
                        graph_state_before="observational path query blocked",
                        graph_state_after="hybrid source/experimental compiled plan",
                    ),
                ],
                metadata={
                    **diagnostics,
                    **dict(report.metadata),
                },
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        if report.mode is PathSpecificDecisionMode.TEMPLATE_PROXIMAL:
            return self._intervention_negative_certificate(
                query=query,
                blocking_type=BlockingType.OUT_OF_SCOPE_FOR_PROXIMAL_V1,
                blocking_description=(
                    "This path-specific query requires a certified proximal template "
                    "reducer that is not yet wired into the native backend."
                ),
                algorithm_version="path_intervention_v1",
                constructive_message=report.constructive_message,
                proof_trace=proof_trace,
                negative_payload={"blocking_type": "template_proximal"},
                extra_diagnostics={
                    **diagnostics,
                    **dict(report.metadata),
                },
            )

        if PathSpecificWitnessKind.WIDTH_BUDGET_EXCEEDED in witness_kinds:
            blocking_description = (
                "Path-specific exact compilation exceeded the configured width budget."
            )
        elif PathSpecificWitnessKind.UNSUPPORTED_CONDITIONING in witness_kinds:
            blocking_description = (
                "Conditional path-specific queries are not yet certified in the native backend."
            )
        elif PathSpecificWitnessKind.EDGE_INCONSISTENCY in witness_kinds:
            blocking_description = (
                "The path-specific policy is edge-inconsistent: at least one edge is both active and frozen."
            )
        elif PathSpecificWitnessKind.TOTAL_EFFECT_NOT_IDENTIFIED in witness_kinds:
            blocking_description = (
                "The corresponding total/interventional effect is not observationally identified."
            )
        elif PathSpecificWitnessKind.RECANTING_DISTRICT in witness_kinds:
            blocking_description = (
                "Path-specific query is blocked by the recanting district criterion."
            )
        else:
            blocking_description = (
                "Path-specific query is blocked by the recanting witness criterion."
            )

        negative = self._intervention_negative_certificate(
            query=query,
            blocking_type=BlockingType.SEMANTICS_NOT_WELL_DEFINED,
            blocking_description=blocking_description,
            algorithm_version="path_intervention_v1",
            constructive_message=report.constructive_message or (
                "Collect interventional data on the mediator-specific channels or "
                "restate the query as an edge/node intervention that avoids natural "
                "value cross-world semantics."
            ),
            proof_trace=proof_trace,
            negative_payload={
                "blocking_type": (
                    report.witnesses[0].kind.value if report.witnesses else report.mode.value
                ),
                "treatment": treatment_name,
                "outcome": outcome_name,
            },
            extra_diagnostics={
                **diagnostics,
                **dict(report.metadata),
            },
        )
        if report.bounds_bundle is not None:
            negative = negative.model_copy(update={"bounds_bundle": report.bounds_bundle})
        if report.required_distributions:
            negative = negative.model_copy(
                update={
                    "required_distributions": tuple(
                        item.model_dump(mode="json") for item in report.required_distributions
                    )
                }
            )
        return negative

    def _identify_interference_intervention_backend(
        self,
        *,
        query: InterventionQuery,
        graph: CausalGraphModel,
        intervention: InterferenceIntervention,
        outcome: frozenset[str],
    ) -> IdentificationResult | NegativeCertificate:
        from polisyos.foundry.methods.catalog.causal.interference import (
            build_interference_topology_contracts,
            identify_interference_effect,
        )
        from polisyos.ir.analytics.interference import (
            ExposureMappingType,
            load_interaction_complex,
            load_interference_certificate,
        )

        def _exposure_mapping_from_ref(value: str) -> ExposureMappingType:
            lowered = value.strip().lower()
            if "threshold" in lowered:
                return ExposureMappingType.THRESHOLD
            if "count" in lowered:
                return ExposureMappingType.COUNT
            if "kernel" in lowered or "spatial" in lowered:
                return ExposureMappingType.KERNEL
            return ExposureMappingType.FRACTIONAL

        treatment_name = intervention.policies[0].target
        outcome_name = next(iter(sorted(outcome)))
        exposure_mapping = _exposure_mapping_from_ref(intervention.exposure_map_ref)
        cluster_var = (
            "cluster_map"
            if intervention.interference_mode in {"partial", "cluster"}
            or intervention.fallback_mode == "clustered"
            else None
        )
        reduction_policy = {
            "pairwise": "pairwise_projection",
            "clustered": "cluster_projection",
            "unsupported": "full_complex",
        }[intervention.fallback_mode]

        interference_result = identify_interference_effect(
            graph,
            treatment_name,
            outcome_name,
            exposure_mapping=exposure_mapping,
            cluster_var=cluster_var,
        )
        interaction_complex, interference_certificate = build_interference_topology_contracts(
            interference_result,
            reduction_policy=reduction_policy,
        )
        effective_mode = (
            interference_certificate.mode_used or interference_certificate.fallback_mode
        )
        estimand_label = {
            "complex": "complex_exposure_effect",
            "clustered": "clustered_exposure_effect",
            "pairwise": "pairwise_projection_effect",
            "unsupported": "unsupported_complex_effect",
        }[effective_mode]
        metadata: dict[str, Any] = {
            "interaction_complex": (
                interaction_complex.model_dump(mode="json")
                if interaction_complex is not None
                else None
            ),
            "interference_certificate": interference_certificate.model_dump(mode="json"),
            "interference_mode": intervention.interference_mode,
            "interference_fallback_mode": intervention.fallback_mode,
            "interference_mode_requested": (
                interference_certificate.mode_requested or intervention.interference_mode
            ),
            "interference_mode_used": effective_mode,
            "interference_fallback_triggered": interference_certificate.fallback_triggered,
            "interference_estimand_label": estimand_label,
            "exposure_mapping": exposure_mapping.value,
        }
        if self._artifact_store is not None and intervention.interaction_complex_ref is not None:
            try:
                metadata["declared_interaction_complex"] = load_interaction_complex(
                    self._artifact_store,
                    intervention.interaction_complex_ref,
                ).model_dump(mode="json")
            except Exception:
                pass
        if (
            self._artifact_store is not None
            and query.context.interference_certificate_ref is not None
        ):
            try:
                metadata["declared_interference_certificate"] = load_interference_certificate(
                    self._artifact_store,
                    query.context.interference_certificate_ref,
                ).model_dump(mode="json")
            except Exception:
                pass

        if interference_result.status == "identified":
            estimand_ast = (
                EstimandAST.model_validate(interference_result.estimand_ast)
                if interference_result.estimand_ast is not None
                else None
            )
            required_distributions = [
                DistributionRef.model_validate(item)
                for item in interference_result.required_distributions
            ]
            result = IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=estimand_ast,
                hedge_certificate=None,
                trace=[
                    *list(interference_result.trace),
                    "interference_intervention_id: identified on exposure-augmented graph",
                ],
                required_distributions=required_distributions,
                algorithm_version="interference_intervention_v1",
                proof_steps=list(interference_result.proof_steps),
                query_str=render_intervention_query(query),
                metadata=metadata,
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        base_status = str(interference_result.base_identification_status or interference_result.status)
        blocking_type = (
            BlockingType.HEDGE_STRUCTURE
            if base_status == IdentificationStatus.HEDGE_FOUND.value
            else BlockingType.SEMANTICS_NOT_WELL_DEFINED
        )
        proof_trace = [
            *list(interference_result.trace),
            "interference_intervention_id: augmented-graph identification failed",
        ]
        return self._intervention_negative_certificate(
            query=query,
            blocking_type=blocking_type,
            blocking_description=(
                "Interference reduction did not identify the requested query on the "
                "exposure-augmented graph."
            ),
            algorithm_version="interference_intervention_v1",
            constructive_message=(
                "Provide a certified cluster/network exposure design, or reduce the "
                "query to a clustered partial-interference setting with explicit "
                "topology metadata."
            ),
            proof_trace=proof_trace,
            negative_payload={
                "blocking_type": blocking_type.value,
                "base_identification_status": base_status,
                "interference_mode": intervention.interference_mode,
                "fallback_mode": intervention.fallback_mode,
            },
            extra_diagnostics=metadata,
        )

    def _identify_from_intervention_query(
        self,
        *,
        query: InterventionQuery,
        graph: CausalGraphModel,
        oracle: str,
        dataset_ref: str | None,
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None = None,
    ) -> IdentificationResult | NegativeCertificate:
        composition = check_intervention_composition(query.intervention)
        if not composition.well_typed:
            return self._intervention_typecheck_negative_certificate(query)

        effective_intervention = self._effective_intervention_expr(query.intervention)
        outcome = frozenset(query.target.outcome_variables)

        if isinstance(effective_intervention, TransportIntervention):
            if effective_intervention.base_intervention is None:
                result = self._oracle_needed_intervention_result(
                    query=query,
                    algorithm_version="transport_intervention_v1",
                    trace_message="transport intervention missing base_intervention",
                )
                return self._decorate_identification_result_with_intervention_query(result, query)
            if effective_intervention.soft_transport:
                result = self._identify_sigma_transport_intervention(
                    query=query,
                    graph=graph,
                    dataset_ref=dataset_ref,
                    intervention=effective_intervention,
                    outcome=outcome,
                )
                return self._decorate_identification_result_with_intervention_query(result, query)
            if not isinstance(effective_intervention.base_intervention, NodeIntervention):
                result = self._oracle_needed_intervention_result(
                    query=query,
                    algorithm_version="transport_intervention_v1",
                    trace_message="non-atomic transport interventions require a dedicated backend",
                )
                return self._decorate_identification_result_with_intervention_query(result, query)
            treatment = frozenset(
                item.variable for item in effective_intervention.base_intervention.assignments
            )
            base_result = self._identify_with_s_nodes(
                treatment,
                outcome,
                graph,
                list(effective_intervention.selection_nodes),
                dataset_ref,
            )
            return self._decorate_identification_result_with_intervention_query(
                base_result,
                query,
            )

        if isinstance(effective_intervention, NodeIntervention):
            treatment = frozenset(item.variable for item in effective_intervention.assignments)
            result = id_with_oracle_fallback(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                oracle=oracle,
                dataset_ref=dataset_ref,
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        if isinstance(effective_intervention, ConditionalIntervention):
            treatment = frozenset(item.target for item in effective_intervention.assignments)
            if (
                effective_intervention.regime_kind == "dynamic"
                or len(effective_intervention.assignments) > 1
            ):
                result = dynamic_intervention_id(
                    treatment_sequence=[item.target for item in effective_intervention.assignments],
                    outcome=next(iter(sorted(outcome))),
                    graph=graph,
                    time_points=list(range(len(effective_intervention.assignments))),
                    covariate_sequence=sorted(
                        {
                            hist
                            for item in effective_intervention.assignments
                            for hist in item.history_vars
                        }
                    ),
                    dataset_ref=dataset_ref,
                )
            else:
                history = frozenset(effective_intervention.assignments[0].history_vars)
                result = conditional_intervention_id(
                    treatment=treatment,
                    outcome=outcome,
                    condition_vars=history,
                    graph=graph,
                    dataset_ref=dataset_ref,
                )
            return self._decorate_identification_result_with_intervention_query(result, query)

        if isinstance(effective_intervention, StochasticIntervention):
            if len(effective_intervention.policies) != 1:
                result = self._oracle_needed_intervention_result(
                    query=query,
                    algorithm_version="sid_v1",
                    trace_message="multi-target stochastic interventions are not yet executable",
                )
                return self._decorate_identification_result_with_intervention_query(result, query)
            if effective_intervention.semantics == "sigma_calculus":
                result = self._identify_sigma_stochastic_intervention(
                    query=query,
                    graph=graph,
                    oracle=oracle,
                    dataset_ref=dataset_ref,
                    intervention=effective_intervention,
                    outcome=outcome,
                )
                return self._decorate_identification_result_with_intervention_query(result, query)
            policy_spec = effective_intervention.policies[0]
            result = sid_algorithm(
                treatment=frozenset({policy_spec.target}),
                outcome=outcome,
                graph=graph,
                policy=StochasticPolicy(
                    policy_type="soft",
                    conditioning_vars=policy_spec.conditioning_vars,
                    policy_expr=policy_spec.distribution_expr,
                ),
                dataset_ref=dataset_ref,
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        if isinstance(effective_intervention, MTPIntervention):
            if len(effective_intervention.policies) != 1:
                result = self._oracle_needed_intervention_result(
                    query=query,
                    algorithm_version="mtp_g_formula_v1",
                    trace_message="multi-target modified treatment policies are not yet executable",
                )
                return self._decorate_identification_result_with_intervention_query(result, query)
            policy_spec = effective_intervention.policies[0]
            base_result = id_with_oracle_fallback(
                treatment=frozenset({policy_spec.target}),
                outcome=outcome,
                graph=graph,
                oracle=oracle,
                dataset_ref=dataset_ref,
            )
            if base_result.status is not IdentificationStatus.IDENTIFIED:
                return self._decorate_identification_result_with_intervention_query(
                    base_result,
                    query,
                )
            outcome_name = next(iter(sorted(outcome)))
            root = ModifiedTreatmentPolicyNode(
                treatment_var=policy_spec.target,
                policy_expr=policy_spec.policy_expr,
                natural_treatment_var=policy_spec.natural_treatment,
                covariates=policy_spec.covariates,
                inner_node=base_result.estimand_ast.root,  # type: ignore[union-attr]
                dataset_ref=dataset_ref,
            )
            result = IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=EstimandAST(
                    query_str=f"E_d[{outcome_name}|mtp({policy_spec.target})]",
                    root=root,
                    treatment=policy_spec.target,
                    outcome=outcome_name,
                    all_variables=tuple(
                        sorted({policy_spec.target, outcome_name, *policy_spec.covariates})
                    ),
                    identification_method="mtp_g_formula",
                ),
                hedge_certificate=None,
                trace=[
                    *list(base_result.trace),
                    "mtp_intervention_id: compiled base ID estimand into ModifiedTreatmentPolicyNode",
                ],
                required_distributions=list(base_result.required_distributions),
                algorithm_version="mtp_g_formula_v1",
                proof_steps=list(base_result.proof_steps),
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        if isinstance(effective_intervention, EdgeIntervention):
            per_source_values: dict[str, set[str]] = {}
            for assignment in effective_intervention.assignments:
                stable_value = (
                    assignment.value_expr
                    if assignment.value_expr is not None
                    else repr(assignment.value)
                )
                per_source_values.setdefault(assignment.source, set()).add(stable_value)
            reducible = all(len(values) == 1 for values in per_source_values.values())
            if not reducible:
                if has_directed_cycle(graph) or self._graph_has_bidirected_confounding(graph):
                    result = self._oracle_needed_intervention_result(
                        query=query,
                        algorithm_version="edge_g_formula_v1",
                        trace_message=(
                            "edge g-formula backend currently requires an acyclic "
                            "graph without hidden confounding"
                        ),
                    )
                    return self._decorate_identification_result_with_intervention_query(
                        result,
                        query,
                    )
                outcome_name = next(iter(sorted(outcome)))
                root = EdgeInterventionNode(
                    assignments=tuple(
                        EdgeInterventionAssignment(
                            source=item.source,
                            target=item.target,
                            value_expr=item.value_expr or repr(item.value),
                        )
                        for item in effective_intervention.assignments
                    ),
                    inner_node=None,
                    dataset_ref=dataset_ref,
                )
                result = IdentificationResult(
                    status=IdentificationStatus.IDENTIFIED,
                    estimand_ast=EstimandAST(
                        query_str=render_intervention_query(query),
                        root=root,
                        treatment=",".join(sorted(per_source_values)),
                        outcome=outcome_name,
                        all_variables=tuple(
                            sorted(
                                {
                                    outcome_name,
                                    *(item.source for item in effective_intervention.assignments),
                                    *(item.target for item in effective_intervention.assignments),
                                }
                            )
                        ),
                        identification_method="edge_g_formula",
                    ),
                    hedge_certificate=None,
                    trace=[
                        "edge_g_formula: identified a non-uniform edge intervention "
                        "on an acyclic graph without hidden confounding"
                    ],
                    required_distributions=[],
                    algorithm_version="edge_g_formula_v1",
                    proof_steps=[
                        IRProofStep(
                            rule_name="EDGE_G_FORMULA",
                            description=(
                                "Identified the edge intervention with the edge g-formula "
                                "under acyclicity and no hidden confounding."
                            ),
                            variables_affected=tuple(
                                sorted(
                                    {
                                        *(item.source for item in effective_intervention.assignments),
                                        *(item.target for item in effective_intervention.assignments),
                                    }
                                )
                            ),
                            graph_subset="directed acyclic graph",
                            rule_formal_name="Edge g-formula",
                            applicable_theorem=(
                                "Avin, Shpitser & Pearl (2005); graphical hierarchy "
                                "of interventions"
                            ),
                            graph_state_before=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges",
                            graph_state_after="edge intervention compiled symbolically",
                        )
                    ],
                )
                return self._decorate_identification_result_with_intervention_query(
                    result,
                    query,
                )
            treatment = frozenset(per_source_values)
            base_result = id_with_oracle_fallback(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
                oracle=oracle,
                dataset_ref=dataset_ref,
            )
            if base_result.status is not IdentificationStatus.IDENTIFIED:
                return self._decorate_identification_result_with_intervention_query(
                    base_result,
                    query,
                )
            outcome_name = next(iter(sorted(outcome)))
            root = EdgeInterventionNode(
                assignments=tuple(
                    EdgeInterventionAssignment(
                        source=item.source,
                        target=item.target,
                        value_expr=item.value_expr or repr(item.value),
                    )
                    for item in effective_intervention.assignments
                ),
                inner_node=base_result.estimand_ast.root,  # type: ignore[union-attr]
                dataset_ref=dataset_ref,
            )
            result = IdentificationResult(
                status=IdentificationStatus.IDENTIFIED,
                estimand_ast=EstimandAST(
                    query_str=render_intervention_query(query),
                    root=root,
                    treatment=",".join(sorted(treatment)),
                    outcome=outcome_name,
                    all_variables=tuple(sorted({outcome_name, *treatment})),
                    identification_method="edge_reduce_to_node",
                ),
                hedge_certificate=None,
                trace=[
                    *list(base_result.trace),
                    "edge_intervention_id: reduced uniform edge intervention to node-level ID",
                ],
                required_distributions=list(base_result.required_distributions),
                algorithm_version="edge_intervention_v1",
                proof_steps=list(base_result.proof_steps),
            )
            return self._decorate_identification_result_with_intervention_query(result, query)

        if isinstance(effective_intervention, PathIntervention):
            return self._identify_path_intervention_backend(
                query=query,
                graph=graph,
                dataset_ref=dataset_ref,
                intervention=effective_intervention,
                outcome=outcome,
                proximal_annotation=proximal_annotation,
            )

        if isinstance(effective_intervention, InterferenceIntervention):
            return self._identify_interference_intervention_backend(
                query=query,
                graph=graph,
                intervention=effective_intervention,
                outcome=outcome,
            )

        result = self._oracle_needed_intervention_result(
            query=query,
            algorithm_version="intervention_type_system_v1",
            trace_message="unsupported intervention expression",
        )
        return self._decorate_identification_result_with_intervention_query(result, query)

    # ------------------------------------------------------------------
    # identify
    # ------------------------------------------------------------------

    def identify(
        self,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        graph: CausalGraphModel,
        *,
        source_domains: list[Any] | None = None,
        s_nodes: list[Any] | None = None,
        z_interventions: frozenset[str] | None = None,
        conditions: frozenset[str] | None = None,
        oracle: str = "none",
        dataset_ref: str | None = None,
        mgraph_meta: Any | None = None,
        counterfactual_query: CtfQuery | None = None,
        distribution_query: DistributionLawQuery | None = None,
        intervention_query: InterventionQuery | dict[str, Any] | None = None,
        # Phase-5: Extended identification keyword arguments
        policy: Any | None = None,
        condition_vars: frozenset[str] | None = None,
        treatment_sequence: list[str] | None = None,
        time_points: list[int] | None = None,
        outcomes: list[str] | None = None,
        proxy_map: dict[str, str] | None = None,
        measurement_model: str = "unknown",
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None = None,
    ) -> (
        IdentificationResult
        | NegativeCertificate
        | ProximalIdentificationCertificate
        | dict[str, IdentificationResult]
    ):
        """Run identification and return IdentificationResult or NegativeCertificate.

        Routing logic (in priority order):
        - intervention_query → typed proof-kernel intervention dispatch
        - distribution_query → proof-only distribution law reduction via ID/IDC
        - counterfactual_query + transport/fusion context → ctf_transportability
        - counterfactual_query → id_star_algorithm / idc_star_algorithm
        - proxy_map → identify_with_proxy (Phase 5.3: measurement error)
        - outcomes (list) → multi_outcome_id (Phase 5.2: multi-outcome)
        - policy → sid_algorithm (Phase 5.1: stochastic/soft intervention)
        - condition_vars → conditional_intervention_id (Phase 5.1: conditional do)
        - treatment_sequence → dynamic_intervention_id (Phase 5.1: dynamic/sequential)
        - mgraph_meta → full_law_identify (Phase 2: M-graph two-stage pipeline)
        - source_domains (len > 1) → mz_id_algorithm (G1)
        - s_nodes AND z_interventions → mz_id_algorithm (single combined domain)
        - s_nodes only → tr_algorithm (via SelectionDiagram)
        - z_interventions only → z_id_algorithm
        - conditions → idc_algorithm
        - else → id_with_oracle_fallback, then optional proximal fallback on hedge
        """
        effective_intervention_query = (
            InterventionQuery.model_validate(intervention_query)
            if intervention_query is not None
            else None
        )

        # Normalise treatment / outcome to frozenset[str]
        if effective_intervention_query is not None:
            tx = self._intervention_target_vars(effective_intervention_query.intervention)
            oy = frozenset(effective_intervention_query.target.outcome_variables)
        else:
            tx = frozenset({treatment} if isinstance(treatment, str) else treatment)
            oy = frozenset({outcome} if isinstance(outcome, str) else outcome)

        z_int = z_interventions or frozenset()
        cond = conditions or frozenset()

        try:
            if mgraph_meta is None and graph.graph_type is GraphType.MGRAPH:
                from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

                mgraph_meta = extract_mgraph_metadata(graph)
            if effective_intervention_query is not None:
                result = self._identify_from_intervention_query(
                    query=effective_intervention_query,
                    graph=graph,
                    oracle=oracle,
                    dataset_ref=dataset_ref,
                    proximal_annotation=proximal_annotation,
                )
            elif has_directed_cycle(graph):
                result = self._identify_with_dynamic_semantics(
                    treatment=tx,
                    outcome=oy,
                    graph=graph,
                    source_domains=source_domains,
                    s_nodes=s_nodes,
                    z_interventions=z_int,
                    conditions=cond,
                    oracle=oracle,
                    dataset_ref=dataset_ref,
                    mgraph_meta=mgraph_meta,
                    counterfactual_query=counterfactual_query,
                    distribution_query=distribution_query,
                    policy=policy,
                    condition_vars=condition_vars,
                    treatment_sequence=treatment_sequence,
                    time_points=time_points,
                    outcomes=outcomes,
                    proxy_map=proxy_map,
                    measurement_model=measurement_model,
                )
            else:
                result = self._dispatch_static_identification(
                    treatment=tx,
                    outcome=oy,
                    graph=graph,
                    source_domains=source_domains,
                    s_nodes=s_nodes,
                    z_interventions=z_int,
                    conditions=cond,
                    oracle=oracle,
                    dataset_ref=dataset_ref,
                    mgraph_meta=mgraph_meta,
                    counterfactual_query=counterfactual_query,
                    distribution_query=distribution_query,
                    policy=policy,
                    condition_vars=condition_vars,
                    treatment_sequence=treatment_sequence,
                    time_points=time_points,
                    outcomes=outcomes,
                    proxy_map=proxy_map,
                    measurement_model=measurement_model,
                    proximal_annotation=proximal_annotation,
                )
                if isinstance(result, NegativeCertificate):
                    return result
                if isinstance(result, IdentificationResult) and counterfactual_query is not None:
                    if result.status == IdentificationStatus.HEDGE_FOUND:
                        return self._hedge_to_negative_cert(result)
                    return result
        except Exception as exc:
            # Convert unexpected errors to NegativeCertificate
            return NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description=f"Identification failed with exception: {exc}",
                technical_detail=str(exc),
                quantitative_diagnostics={
                    "identification_status": "exception",
                    "algorithm_version": "id_exception_wrapper",
                },
                constructive_message="Check that graph nodes/edges are valid.",
            )

        if effective_intervention_query is None and isinstance(result, IdentificationResult):
            derived_query = self._legacy_intervention_query(
                treatment=tx,
                outcome=oy,
                dataset_ref=dataset_ref,
                conditions=cond,
                condition_vars=condition_vars,
                policy=policy,
                treatment_sequence=treatment_sequence,
                s_nodes=s_nodes,
                counterfactual_query=counterfactual_query,
                distribution_query=distribution_query,
                outcomes=outcomes,
                proxy_map=proxy_map,
            )
            if derived_query is not None:
                result = self._decorate_identification_result_with_intervention_query(
                    result,
                    derived_query,
                )

        if isinstance(result, ProximalIdentificationCertificate):
            return result
        if isinstance(result, NegativeCertificate):
            return result
        if isinstance(result, dict):
            return result

        # Convert NOT_RECOVERABLE (M-graph Stage 1 failure) to NegativeCertificate
        if result.status == IdentificationStatus.NOT_RECOVERABLE:
            return NegativeCertificate(
                blocking_type=BlockingType.MISSINGNESS_NOT_RECOVERABLE,
                blocking_description=(
                    "M-graph recoverability check failed: the full-data distribution "
                    "P(V) cannot be recovered from incomplete data. "
                    "Check for MNAR variables with self-affecting missingness paths."
                ),
                technical_detail="; ".join(result.trace[-3:] if result.trace else []),
                quantitative_diagnostics={
                    "identification_status": result.status.value,
                    "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
                    "proof_trace": list(result.trace or []),
                    "recoverability": dict(
                        getattr(result, "metadata", {}) or {}
                    ).get("recoverability_certificate"),
                },
                constructive_message=(
                    "Inspect blocking_r_nodes in the proof trace. "
                    "Consider collecting auxiliary data to break the MNAR path, "
                    "or use sensitivity analysis for bounds under MNAR."
                ),
            )

        # Convert HEDGE_FOUND to NegativeCertificate
        if result.status == IdentificationStatus.HEDGE_FOUND:
            # For mz-ID failures, use the richer from_mz_id_failure constructor
            if source_domains and len(source_domains) > 1:
                return self._mz_id_failure_to_negative_cert(
                    result=result,
                    tx=tx,
                    oy=oy,
                    source_domains=source_domains,
                    s_nodes=s_nodes,
                )
            return self._hedge_to_negative_cert(result)

        # Convert mz-ID ORACLE_NEEDED + S-nodes to NegativeCertificate
        if (
            result.status == IdentificationStatus.ORACLE_NEEDED
            and (
                (source_domains and len(source_domains) > 1)
                or (s_nodes and z_int)
            )
        ):
            return self._mz_id_failure_to_negative_cert(
                result=result,
                tx=tx,
                oy=oy,
                source_domains=source_domains,
                s_nodes=s_nodes,
            )

        return result

    def identify_joint(
        self,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        graph: CausalGraphModel,
        *,
        mgraph_meta: MGraphMetadata | dict[str, Any] | None = None,
        oracle: str = "none",
        dataset_ref: str | None = None,
    ) -> JointDecisionCertificate:
        """Return the Stage 12.1 joint ID + recoverability certificate.

        This entrypoint keeps the legacy ``identify()`` return contract intact
        while exposing the four-way proof-kernel verdict required by graphical
        missing-data recoverability.
        """
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            identify_joint_recoverability,
        )
        from polisyos.ir.analytics.mgraph import (
            MGraphMetadata,
            extract_mgraph_metadata,
        )

        tx = frozenset({treatment} if isinstance(treatment, str) else treatment)
        oy = frozenset({outcome} if isinstance(outcome, str) else outcome)
        if isinstance(mgraph_meta, MGraphMetadata):
            meta = mgraph_meta
        elif isinstance(mgraph_meta, dict):
            meta = MGraphMetadata.model_validate(mgraph_meta)
        else:
            meta = extract_mgraph_metadata(graph)
        return identify_joint_recoverability(
            treatment=tx,
            outcome=oy,
            graph=graph,
            mgraph_meta=meta,
            dataset_ref=dataset_ref,
            oracle=oracle,
        )

    def _identify_with_s_nodes(
        self,
        tx: frozenset[str],
        oy: frozenset[str],
        graph: CausalGraphModel,
        s_nodes: list[Any],
        dataset_ref: str | None,
    ) -> IdentificationResult:
        """Run tr_algorithm via a SelectionDiagram built from s_nodes."""
        try:
            from polisyos.ir.analytics.transportability import SelectionDiagram, SNode
            from polisyos.ir.analytics.context import ContextProfile

            # Build minimal SelectionDiagram
            if s_nodes and isinstance(s_nodes[0], SNode):
                snode_list = s_nodes
            else:
                # s_nodes is list of variable names — create SNode objects
                # SNode requires: target_variable, context_dimension, source_value,
                # target_value, delta, severity
                snode_list = [
                    SNode(
                        target_variable=str(s),
                        context_dimension="unknown",
                        source_value=0.0,
                        target_value=1.0,
                        delta=1.0,
                        severity="low",
                    )
                    for s in s_nodes
                ]

            sel_diag = SelectionDiagram(
                base_graph=graph,
                s_nodes=snode_list,
                source_context=ContextProfile(),
                target_context=ContextProfile(),
            )
            return tr_algorithm(
                treatment=tx,
                outcome=oy,
                selection_diagram=sel_diag,
                dataset_ref=dataset_ref,
            )
        except Exception:
            # If SelectionDiagram not available or fails, fall back to standard ID
            return id_with_oracle_fallback(treatment=tx, outcome=oy, graph=graph)

    def _hedge_to_negative_cert(self, result: IdentificationResult) -> NegativeCertificate:
        """Convert HedgeCertificate → NegativeCertificate."""
        from polisyos.ir.analytics.negative_certificate import SuggestedExperiment as _SE

        cert = result.hedge_certificate
        result_metadata = dict(getattr(result, "metadata", {}) or {})
        dynamic_semantics = result_metadata.get("dynamic_semantics")
        witness = None
        if isinstance(dynamic_semantics, dict):
            witness = dynamic_semantics.get("well_posedness_witness")
        if cert is None:
            auto_suggestions = NegativeCertificate.auto_suggest_experiments(
                BlockingType.HEDGE_STRUCTURE,
            )
            return NegativeCertificate(
                blocking_type=BlockingType.HEDGE_STRUCTURE,
                blocking_description="Non-identifiable: hedge structure found",
                suggested_experiments=auto_suggestions,
                quantitative_diagnostics={
                    "identification_status": str(result.status.value),
                    "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
                    "proof_trace": list(getattr(result, "trace", []) or []),
                },
                constructive_message=(
                    "The query is not nonparametrically identifiable. "
                    "Consider: adding instruments, running an experiment, or computing bounds."
                ),
            )

        required_dists: tuple[dict, ...] = ()
        missing_vars: tuple[str, ...] = ()
        suggested: tuple[Any, ...] = ()
        if cert.required_data is not None:
            required_dists = tuple(
                dr.model_dump(mode="json") if hasattr(dr, "model_dump") else {}
                for dr in cert.required_data.missing_distributions
            )
            # Extract missing variable names for auto-suggestions
            missing_vars = tuple(
                v
                for dr in cert.required_data.missing_distributions
                for v in (dr.variables if hasattr(dr, "variables") else ())
            )
            # G6: wrap string hint into structured SuggestedExperiment
            if cert.required_data.suggested_experiment:
                suggested = (
                    _SE(
                        required_variables=missing_vars,
                        description=cert.required_data.suggested_experiment,
                    ),
                )

        # Auto-populate suggested experiments if none were derived from cert
        if not suggested:
            suggested = NegativeCertificate.auto_suggest_experiments(
                BlockingType.HEDGE_STRUCTURE,
                missing_vars=missing_vars,
            )

        blocking_type = BlockingType.HEDGE_STRUCTURE
        description = (
            f"Non-identifiable: hedge forest F={sorted(cert.hedge_forest)}, "
            f"F'={sorted(cert.hedge_root)}"
        )
        constructive_message = (
            "The estimand is not nonparametrically identifiable given this graph. "
            + (
                cert.required_data.alternative_identification
                if cert.required_data and cert.required_data.alternative_identification
                else "Consider: randomizing treatment, adding instruments, or using bounds."
            )
        )
        if isinstance(witness, dict):
            witness_status = str(witness.get("status", "") or "")
            if witness_status in {"refuted", "heuristic_blocked"}:
                blocking_type = BlockingType.SEMANTICS_NOT_WELL_DEFINED
                description = (
                    "Dynamic SCM semantics are not certified for this cyclic query; "
                    "a unique intervention response was not established."
                )
                constructive_message = (
                    "Provide a machine-checkable well-posedness witness or reduce the query "
                    "to an acyclic identification path before claiming identification."
                )

        # Quantitative diagnostics from hedge structure
        quant_diagnostics: dict[str, Any] = {
            "hedge_forest_size": len(cert.hedge_forest),
            "hedge_root_size": len(cert.hedge_root),
            "missing_distributions_count": len(required_dists),
            "identification_status": str(result.status.value),
            "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
            "proof_trace": list(getattr(result, "trace", []) or []),
        }
        for key in (
            "query_kind",
            "distribution_family",
            "generator_type",
            "parameter_domain",
            "measure_determination_regime",
            "derived_functionals_allowed",
            "not_identified_objects",
            "support_space",
            "representation",
            "conditioning_variables",
            "intervention_query",
            "intervention_query_string",
            "intervention_type",
            "intervention_identification_status",
            "intervention_reduction_chain",
            "intervention_certificate",
        ):
            if key in result_metadata:
                quant_diagnostics[key] = result_metadata[key]
        if dynamic_semantics is not None:
            quant_diagnostics["dynamic_semantics"] = dynamic_semantics

        return NegativeCertificate(
            blocking_type=blocking_type,
            blocking_description=description,
            technical_detail=cert.description or "",
            required_distributions=required_dists,
            suggested_experiments=(
                suggested
                if blocking_type is BlockingType.HEDGE_STRUCTURE
                else NegativeCertificate.auto_suggest_experiments(blocking_type, missing_vars=missing_vars)
            ),
            quantitative_diagnostics=quant_diagnostics,
            constructive_message=constructive_message,
        )

    def _mz_id_failure_to_negative_cert(
        self,
        *,
        result: IdentificationResult,
        tx: frozenset[str],
        oy: frozenset[str],
        source_domains: list[Any] | None,
        s_nodes: list[Any] | None,
    ) -> NegativeCertificate:
        """Convert mz-ID failure to NegativeCertificate via from_mz_id_failure()."""
        result_metadata = dict(getattr(result, "metadata", {}) or {})
        # Collect available domain IDs
        available_domain_ids: list[str] = []
        if source_domains:
            for d in source_domains:
                did = getattr(d, "domain_id", str(d))
                available_domain_ids.append(str(did))

        # Collect unresolved S-node variable names
        unresolved_s_vars: frozenset[str] = frozenset()
        if s_nodes:
            unresolved_s_vars = frozenset(
                getattr(sn, "target_variable", str(sn)) for sn in s_nodes
            )
        elif source_domains:
            # Collect all S-node variables from all source domains
            all_s: set[str] = set()
            for d in source_domains:
                for sv in getattr(d, "s_nodes", frozenset()):
                    all_s.add(str(sv))
            unresolved_s_vars = frozenset(all_s)

        # Suggest missing domains from hedge certificate if available
        missing_domains: list[str] = []
        hedge_cert = result.hedge_certificate
        if hedge_cert is not None:
            minimal = getattr(hedge_cert, "minimal_required_s_nodes", frozenset())
            if minimal:
                missing_domains = [
                    f"domain_with_experiment_on_{v}" for v in sorted(minimal)
                ]

        return NegativeCertificate.from_mz_id_failure(
            treatment=tx,
            outcome=oy,
            unresolved_s_nodes=unresolved_s_vars,
            available_domains=available_domain_ids,
            missing_domains=missing_domains or None,
            hedge_certificate=hedge_cert,
        ).model_copy(
            update={
                "quantitative_diagnostics": {
                    "unresolved_s_node_count": len(unresolved_s_vars),
                    "available_domain_count": len(available_domain_ids),
                    "missing_domain_count": len(missing_domains or []),
                    "identification_status": str(result.status.value),
                    "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
                    "proof_trace": list(getattr(result, "trace", []) or []),
                    **{
                        key: result_metadata[key]
                        for key in (
                            "query_kind",
                            "intervention_query",
                            "intervention_query_string",
                            "intervention_type",
                            "intervention_identification_status",
                            "intervention_reduction_chain",
                            "intervention_certificate",
                        )
                        if key in result_metadata
                    },
                }
            }
        )

    def _materialize_identification_artifacts(
        self,
        identification_outcome: (
            IdentificationResult | NegativeCertificate | ProximalIdentificationCertificate
        ),
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[
        IdentificationResult | None,
        ProofBundle,
        NegativeCertificate | None,
        BoundsBundle | None,
        dict[str, Any] | None,
        Any | None,
        ProximalIdentificationCertificate | None,
    ]:
        """Normalize positive and negative ID outcomes into canonical public artifacts."""
        if isinstance(identification_outcome, ProximalIdentificationCertificate):
            proof_bundle = proof_bundle_from_proximal_certificate(
                identification_outcome,
                graph_ref=self._graph_artifact_ref(graph),
                query_ref=_query_str_from_io(treatment, outcome),
            )
            return None, proof_bundle, None, None, None, None, identification_outcome

        if isinstance(identification_outcome, NegativeCertificate):
            completed, dual_certificate_payload = self._complete_negative_certificate(
                identification_outcome,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )
            proof_bundle = proof_bundle_from_negative_certificate(
                completed,
                query_ref=(
                    str(
                        completed.quantitative_diagnostics.get("intervention_query_string")
                        or ""
                    )
                    or _query_str_from_io(treatment, outcome)
                ),
                theorem_family=str(
                    completed.quantitative_diagnostics.get("algorithm_version") or ""
                )
                or None,
                status_raw=str(
                    completed.quantitative_diagnostics.get("identification_status")
                    or ""
                )
                or None,
            )
            return (
                None,
                proof_bundle,
                completed,
                completed.bounds_bundle,
                dual_certificate_payload,
                None,
                None,
            )

        proof_bundle = proof_bundle_from_identification_result(identification_outcome)
        from polisyos.ir.analytics.dp_robustness import (
            attach_dp_robustness_to_proof_bundle,
            bounds_bundle_from_dp_robustness_certificate,
            coerce_dp_robustness_certificate,
        )

        dp_certificate = coerce_dp_robustness_certificate(
            getattr(identification_outcome, "metadata", None)
        )
        dp_bounds_bundle = None
        if dp_certificate is not None:
            proof_bundle = attach_dp_robustness_to_proof_bundle(
                proof_bundle,
                None,
                dp_certificate,
            )
            if dp_certificate.effective_validity.status.value == "bounded":
                dp_bounds_bundle = bounds_bundle_from_dp_robustness_certificate(
                    dp_certificate,
                    estimand_type="causal_effect",
                )
        proximal_mediation_bounds = None
        metadata = dict(getattr(identification_outcome, "metadata", {}) or {})
        cert_payload = metadata.get("proximal_mediation_certificate")
        if (
            cert_payload is not None
            and getattr(identification_outcome, "status", None) is IdentificationStatus.ORACLE_NEEDED
        ):
            try:
                from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
                    proximal_mediation_bounds_bundle,
                )
                from polisyos.ir.analytics.proximal import ProximalMediationCertificate

                certificate = ProximalMediationCertificate.model_validate(cert_payload)
                outcome_vector = None
                if data_dict:
                    outcome_vector = _coerce_aligned_vector(
                        _first_non_null(
                            data_dict,
                            ("outcome", certificate.query.outcome),
                        )
                    )
                proximal_mediation_bounds = proximal_mediation_bounds_bundle(
                    outcome=outcome_vector,
                    target_effect=certificate.query.target_effect,
                    outcome_support=_resolve_graph_outcome_support(
                        graph,
                        outcome=certificate.query.outcome,
                    ),
                    assumption_tag="proximal_mediation_oracle_not_accepted",
                    metadata={
                        "path_specific_proximal": True,
                        "query_target_effect": certificate.query.target_effect,
                    },
                    warnings=[
                        "Proof kernel certified the proximal mediation template, but oracle assumptions were not accepted; returned bounds instead of a point estimate.",
                    ],
                )
            except Exception:
                proximal_mediation_bounds = None

        return (
            identification_outcome,
            proof_bundle,
            None,
            proximal_mediation_bounds or dp_bounds_bundle,
            None,
            dp_certificate,
            None,
        )

    def _complete_negative_certificate(
        self,
        negative_cert: NegativeCertificate,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[NegativeCertificate, dict[str, Any] | None]:
        """Attach recovery/bounds artifacts for any supported non-identification path."""
        if negative_cert.blocking_type is BlockingType.HEDGE_STRUCTURE:
            return self._hedge_fallback_chain(
                negative_cert,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )

        diagnostics = dict(negative_cert.quantitative_diagnostics)
        y, t, extraction_notes = self._extract_hedge_fallback_arrays(
            data_dict=data_dict,
            treatment=treatment,
            outcome=outcome,
        )
        notes = list(extraction_notes)
        bounds_bundle: BoundsBundle | None = negative_cert.bounds_bundle
        dual_certificate_payload: dict[str, Any] | None = None
        if bounds_bundle is None and diagnostics.get("path_specific_proximal"):
            try:
                from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
                    proximal_mediation_bounds_bundle,
                )

                bounds_bundle = proximal_mediation_bounds_bundle(
                    outcome=y,
                    target_effect=str(diagnostics.get("target_effect") or "psi"),
                    outcome_support=_resolve_graph_outcome_support(
                        graph,
                        outcome=(
                            outcome
                            if isinstance(outcome, str)
                            else next(iter(sorted(outcome)), "outcome")
                        ),
                    ),
                    assumption_tag="proximal_mediation_structure_failed",
                    metadata={
                        "path_specific_proximal": True,
                        "failed_check": diagnostics.get("failed_check"),
                    },
                    warnings=[
                        "Structural proximal mediation checks failed; returned theorem-specific outer bounds when support information was available.",
                    ],
                )
                notes.append("Computed proximal mediation support-implied bounds bundle.")
            except Exception as exc:
                notes.append(f"Proximal mediation bounds completion failed: {exc}")
        if bounds_bundle is None and y is not None and t is not None:
            bounds_bundle, bounds_notes, dual_certificate_payload = self._compute_generic_bounds_bundle(
                y=y,
                t=t,
            )
            notes.extend(bounds_notes)
        elif bounds_bundle is None:
            notes.append(
                "Observed treatment/outcome vectors unavailable; bounds completion skipped."
            )

        diagnostics.update(
            {
                "bounds_completion_attempted": True,
                "bounds_completion_available": bounds_bundle is not None,
            }
        )
        if notes:
            diagnostics["bounds_completion_notes"] = list(notes)

        updated = negative_cert.model_copy(
            update={
                "bounds_bundle": bounds_bundle,
                "quantitative_diagnostics": diagnostics,
            }
        )
        updated = updated.model_copy(
            update={"recovery_plan": recovery_plan_from_negative_certificate(updated)}
        )
        return updated, dual_certificate_payload

    def _hedge_fallback_chain(
        self,
        negative_cert: NegativeCertificate,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[NegativeCertificate, dict[str, Any] | None]:
        """Attach an honest typed fallback chain for hedge-style non-identification."""
        if negative_cert.blocking_type is not BlockingType.HEDGE_STRUCTURE:
            return negative_cert, None

        suggestions = (
            negative_cert.suggested_experiments
            or NegativeCertificate.auto_suggest_experiments(BlockingType.HEDGE_STRUCTURE)
        )

        y, t, extraction_notes = self._extract_hedge_fallback_arrays(
            data_dict=data_dict,
            treatment=treatment,
            outcome=outcome,
        )
        notes = list(extraction_notes)

        bounds_result = None
        bounds_tier = None
        dual_certificate_payload = None
        if y is not None and t is not None:
            bounds_result, bounds_tier, bounds_notes, dual_certificate_payload = (
                self._compute_hedge_bounds(y=y, t=t)
            )
            notes.extend(bounds_notes)
        else:
            notes.append("Observed treatment/outcome vectors unavailable; skipped tiers 1-3.")

        parametric_rescue = None
        if y is not None and t is not None:
            monotone_rescue, monotone_notes = self._compute_monotone_rescue(
                y=y,
                t=t,
                base_bounds=bounds_result,
            )
            notes.extend(monotone_notes)
            linearity_rescue, linearity_notes = self._compute_linearity_rescue(
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )
            notes.extend(linearity_notes)
            if linearity_rescue is not None:
                parametric_rescue = linearity_rescue
                if monotone_rescue is not None:
                    notes.append(
                        "Monotonicity rescue was also available, but linear-IV rescue was preferred because it yields a point-identifying estimand under the stronger linearity assumption."
                    )
            else:
                parametric_rescue = monotone_rescue

        sensitivity_sweep = None
        if y is not None and t is not None:
            sensitivity_sweep, sensitivity_notes = self._compute_sensitivity_sweep(y=y, t=t)
            notes.extend(sensitivity_notes)

        fallback_result = FallbackResult(
            bounds=bounds_result,
            bounds_tier=bounds_tier,
            parametric_rescue=parametric_rescue,
            parametric_tier=(
                EpistemicTier.ASSUMPTION_DEPENDENT if parametric_rescue is not None else None
            ),
            sensitivity_sweep=sensitivity_sweep,
            sensitivity_tier=(
                EpistemicTier.DIAGNOSTIC_GUIDANCE if sensitivity_sweep is not None else None
            ),
            suggested_experiments=suggestions,
            experiments_tier=(
                EpistemicTier.DIAGNOSTIC_GUIDANCE if suggestions else None
            ),
            notes=tuple(notes),
        )

        diagnostics = {
            **dict(negative_cert.quantitative_diagnostics),
            **fallback_result.to_diagnostics_dict(),
            "graph_type": graph.graph_type.value if hasattr(graph.graph_type, "value") else str(graph.graph_type),
        }
        constructive_parts = [negative_cert.constructive_message.strip()]
        if bounds_result is not None and bounds_tier is not None:
            constructive_parts.append(
                f"Tier 1/2 fallback produced {bounds_tier.value} bounds."
            )
        if parametric_rescue is not None:
            constructive_parts.append(
                "An additional assumption-dependent rescue is available, but it is valid only under the stated parametric assumptions."
            )
        if sensitivity_sweep is not None:
            constructive_parts.append(
                "Sensitivity sweep is diagnostic only and should not be read as an identification proof."
            )
        if suggestions:
            constructive_parts.append(
                "Suggested experiments remain Tier-4 guidance for resolving the hedge directly."
            )
        constructive_message = " ".join(part for part in constructive_parts if part)
        bounds_bundle = (
            bounds_bundle_from_partial_identification_result(
                bounds_result,
                rescue_actions=[item.description for item in suggestions if item.description],
                warnings=list(notes),
                metadata={
                    "epistemic_tier": bounds_tier.value if bounds_tier is not None else None,
                    "fallback_level": fallback_result.fallback_level,
                },
            )
            if bounds_result is not None
            else None
        )
        updated = negative_cert.model_copy(
            update={
                "partial_bounds": bounds_result,
                "suggested_experiments": suggestions,
                "quantitative_diagnostics": diagnostics,
                "constructive_message": constructive_message,
                "fallback_result": fallback_result,
                "bounds_bundle": bounds_bundle,
            }
        )

        updated = updated.model_copy(
            update={
                "recovery_plan": recovery_plan_from_negative_certificate(updated),
            }
        )
        return updated, dual_certificate_payload

    def _compute_generic_bounds_bundle(
        self,
        *,
        y: np.ndarray,
        t: np.ndarray,
    ) -> tuple[BoundsBundle | None, list[str], dict[str, Any] | None]:
        """Compute generic fallback bounds for non-hedge blockers when data permit it."""
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        try:
            result = BoundsEngineMethod.pure_step(
                {"outcome": y, "treatment": t},
                {
                    "run_intersection": True,
                    "use_auto_bounds": True,
                },
            )
            payload = result.get("bounds_report")
            if payload is None:
                return None, ["Bounds engine returned no canonical bounds bundle."], None
            bundle = (
                payload
                if isinstance(payload, BoundsBundle)
                else BoundsBundle.model_validate(payload)
            )
            dual_certificate_payload = result.get("dual_certificate_payload")
            return (
                bundle,
                [
                    "Computed bounds-first completion via the canonical bounds engine.",
                ],
                dual_certificate_payload if isinstance(dual_certificate_payload, dict) else None,
            )
        except Exception as exc:
            return None, [f"Bounds completion failed: {exc}"], None

    def _extract_hedge_fallback_arrays(
        self,
        *,
        data_dict: dict[str, Any] | None,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
    ) -> tuple[np.ndarray | None, np.ndarray | None, list[str]]:
        """Extract aligned treatment/outcome vectors for fallback analysis."""
        if not data_dict:
            return None, None, []

        treatment_name = (
            treatment if isinstance(treatment, str) else next(iter(sorted(treatment)), "treatment")
        )
        outcome_name = (
            outcome if isinstance(outcome, str) else next(iter(sorted(outcome)), "outcome")
        )
        treatment_candidates = (
            data_dict.get(treatment_name),
            data_dict.get("treatment"),
            data_dict.get("protected"),
        )
        outcome_candidates = (
            data_dict.get(outcome_name),
            data_dict.get("outcome"),
        )
        t_raw = next((candidate for candidate in treatment_candidates if candidate is not None), None)
        y_raw = next((candidate for candidate in outcome_candidates if candidate is not None), None)
        if t_raw is None or y_raw is None:
            return None, None, []

        try:
            t = np.asarray(t_raw, dtype=float).ravel()
            y = np.asarray(y_raw, dtype=float).ravel()
        except Exception:
            return None, None, ["Could not coerce treatment/outcome into numeric arrays."]

        if len(t) != len(y) or len(t) == 0:
            return None, None, ["Treatment/outcome arrays were missing or misaligned."]

        finite_mask = np.isfinite(t) & np.isfinite(y)
        if not np.all(finite_mask):
            t = t[finite_mask]
            y = y[finite_mask]

        if len(t) == 0:
            return None, None, ["No finite treatment/outcome pairs remained after filtering."]
        return y, t, []

    def _compute_hedge_bounds(
        self,
        *,
        y: np.ndarray,
        t: np.ndarray,
    ) -> tuple[Any | None, EpistemicTier | None, list[str], dict[str, Any] | None]:
        """Step 1: valid partial-identification bounds."""
        from polisyos.foundry.methods.catalog.causal.lp_bounds import auto_bounds_with_metadata

        auto_bounds_kwargs: dict[str, Any] = {}
        if not _looks_discrete_vector(t, max_levels=8) or not _looks_discrete_vector(y, max_levels=8):
            auto_bounds_kwargs = {
                "max_cardinality": 4,
                "initial_bins": 4,
                "max_bins": 8,
                "convergence_tol": 0.05,
            }

        try:
            bounds, metadata = auto_bounds_with_metadata(y, t, **auto_bounds_kwargs)
        except Exception as exc:
            return None, None, [f"Tier 1/2 bounds unavailable: {exc}"], None

        tier = (
            EpistemicTier.EXACT_NONPARAMETRIC
            if bounds.bounds_type == "sharp_lp"
            else EpistemicTier.PARTIAL_IDENTIFICATION
        )
        notes = [f"Computed {bounds.bounds_type} bounds via auto_bounds()."]
        if auto_bounds_kwargs:
            notes.append(
                "Used coarse adaptive discretization for continuous fallback bounds to keep the interactive hedge path computationally bounded."
            )
        dual_certificate_payload = metadata.get("dual_certificate_payload")
        return (
            bounds,
            tier,
            notes,
            dual_certificate_payload if isinstance(dual_certificate_payload, dict) else None,
        )

    def _compute_monotone_rescue(
        self,
        *,
        y: np.ndarray,
        t: np.ndarray,
        base_bounds: Any | None,
    ) -> tuple[ParametricRescueResult | None, list[str]]:
        """Step 2: assumption-dependent monotone-treatment rescue."""
        if not _is_binary_treatment_vector(t):
            return None, ["Monotone-treatment rescue skipped: treatment is not binary."]

        from polisyos.foundry.methods.catalog.causal.bounds import (
            OptimizationBasedBoundsEstimator,
        )
        from polisyos.ir.analytics.partial_identification import PartialIdentificationResult

        y_lo = float(np.nanmin(y))
        y_hi = float(np.nanmax(y))
        try:
            out = OptimizationBasedBoundsEstimator.pure_step(
                {"outcome": y, "treatment": t},
                {
                    "assumption": "mtr",
                    "y_lower": y_lo,
                    "y_upper": y_hi,
                },
            )
            rescue_raw = out.get("result", {}).get("partial_id_result")
            if rescue_raw is None:
                return None, ["Monotone-treatment rescue returned no bounds."]
            rescue_bounds = PartialIdentificationResult.model_validate(rescue_raw)
        except Exception as exc:
            return None, [f"Monotone-treatment rescue failed: {exc}"]

        if base_bounds is not None and rescue_bounds.bound_width >= base_bounds.bound_width - 1e-12:
            return None, ["Monotone-treatment rescue did not tighten the nonparametric bounds."]

        rescue = ParametricRescueResult(
            assumption="monotone_treatment_response",
            method="mtr_bounds",
            description=(
                "Tighter bounds under the monotone treatment response assumption "
                "(Y(1) >= Y(0) for all units)."
            ),
            bounds=rescue_bounds,
            estimand_formula="ATE under MTR bounds",
            warnings=(
                "Assumption-dependent result: verify monotonicity before using operationally.",
            ),
        )
        return rescue, ["Added monotone-treatment-response rescue bounds."]

    def _compute_linearity_rescue(
        self,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[ParametricRescueResult | None, list[str]]:
        """Step 2 alternative: linear-SEM rescue via valid observed instruments."""
        if not data_dict:
            return None, ["Linearity rescue skipped: no observed data were provided."]

        treatment_name = _singleton_query_name(treatment, "treatment")
        outcome_name = _singleton_query_name(outcome, "outcome")
        if treatment_name is None or outcome_name is None:
            return None, ["Linearity rescue currently supports single treatment and single outcome only."]

        iv_rescue, iv_notes = _linear_iv_rescue_result(
            graph=graph,
            treatment=treatment_name,
            outcome=outcome_name,
            data_dict=data_dict,
        )
        if iv_rescue is not None:
            return iv_rescue, iv_notes

        wright_rescue, wright_notes = _wright_path_tracing_rescue_result(
            graph=graph,
            treatment=treatment_name,
            outcome=outcome_name,
            data_dict=data_dict,
        )
        return wright_rescue, [*iv_notes, *wright_notes]

    def _compute_sensitivity_sweep(
        self,
        *,
        y: np.ndarray,
        t: np.ndarray,
    ) -> tuple[Any | None, list[str]]:
        """Step 3: diagnostic sensitivity sweep under MSM."""
        if not _is_binary_treatment_vector(t):
            return None, ["Sensitivity sweep skipped: treatment is not binary."]

        from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import TanBoundsEstimator
        from polisyos.ir.analytics.partial_identification import SensitivitySweepResult

        try:
            out = TanBoundsEstimator.pure_step(
                {"outcome": y, "treatment": t},
                {"lambda_values": [1.0, 1.25, 1.5, 1.75, 2.0]},
            )
            sweep_raw = out.get("result", {}).get("sweep")
            if sweep_raw is None:
                return None, ["Sensitivity sweep returned no sweep artifact."]
            sweep = SensitivitySweepResult.model_validate(sweep_raw)
        except Exception as exc:
            return None, [f"Sensitivity sweep failed: {exc}"]

        return sweep, ["Added Tan (2006) sensitivity sweep as Tier-4 guidance."]

    # ------------------------------------------------------------------
    # compile
    # ------------------------------------------------------------------

    def compile(
        self,
        identification_result: IdentificationResult,
        *,
        graph: CausalGraphModel | None = None,
        n_obs: int | None = None,
        covariate_dim: int | None = None,
        run_id: str | None = None,
        use_cross_fitting: bool = True,
        data_readiness_report: Any | None = None,
    ) -> ExecutorGraph:
        """Compile an IdentificationResult into an ExecutorGraph.

        Requires that identification_result.status == IDENTIFIED and
        identification_result.estimand_ast is not None.
        """
        if identification_result.status != IdentificationStatus.IDENTIFIED:
            raise ValueError(
                f"Cannot compile non-identified result (status={identification_result.status})"
            )
        if identification_result.estimand_ast is None:
            raise ValueError("IdentificationResult has no estimand_ast to compile")

        identification_metadata = dict(getattr(identification_result, "metadata", {}) or {})
        _, executor_graph = compile_estimand(
            identification_result.estimand_ast,
            run_id=run_id or "",
            n_obs=n_obs,
            covariate_dim=covariate_dim,
            use_cross_fitting=use_cross_fitting,
            knowledge_base=self._kb,
            proof_steps=tuple(identification_result.proof_steps),
            causal_graph=graph,
            identification_metadata=identification_metadata,
            recoverability_certificate=(
                identification_metadata.get("recoverability_certificate")
            ),
            data_readiness=(
                data_readiness_report
                if data_readiness_report is not None
                else identification_metadata.get("data_readiness_report")
            ),
        )
        return executor_graph

    # ------------------------------------------------------------------
    # _inject_diagnostic_nodes (G2)
    # ------------------------------------------------------------------

    def _inject_diagnostic_nodes(
        self,
        executor_graph: ExecutorGraph,
        ast: EstimandAST | None,
    ) -> ExecutorGraph:
        """Inject PositivityDiagnostic (always) and SupportMismatchDiagnostic (transport shape).

        Nodes are appended only if not already present; result is a new frozen ExecutorGraph.
        """
        if ast is None:
            return executor_graph

        from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
            classify_estimand,
            EstimandShape,
        )
        shape = classify_estimand(ast)
        if shape == EstimandShape.COUNTERFACTUAL_IDENTIFIED:
            return executor_graph
        existing_fqns = {n.method_fqn for n in executor_graph.nodes}
        new_nodes: list[ExecutorNode] = []

        if "causal.diagnostics.positivity" not in existing_fqns:
            new_nodes.append(
                ExecutorNode(
                    node_id=f"diag_positivity_{executor_graph.run_id}",
                    method_fqn="causal.diagnostics.positivity",
                    method_version="1.0.0",
                    params={},
                    depends_on=(),
                    reads_slots=(),
                    writes_slots=(),
                    is_nuisance=False,
                    dataset_ref=None,
                    skip_if_failed=(),
                )
            )

        if shape == EstimandShape.TRANSPORT_REWEIGHT and (
            "causal.diagnostics.support_mismatch" not in existing_fqns
        ):
            new_nodes.append(
                ExecutorNode(
                    node_id=f"diag_support_{executor_graph.run_id}",
                    method_fqn="causal.diagnostics.support_mismatch",
                    method_version="1.0.0",
                    params={},
                    depends_on=(),
                    reads_slots=(),
                    writes_slots=(),
                    is_nuisance=False,
                    dataset_ref=None,
                    skip_if_failed=(),
                )
            )

        if not new_nodes:
            return executor_graph
        return dataclasses.replace(
            executor_graph, nodes=(*executor_graph.nodes, *new_nodes)
        )

    def _execute_cyclic_block(
        self,
        block: CyclicExecutionBlock,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a cyclic fixed-point block with simple Picard iteration."""
        if self._registry is None:
            raise RuntimeError("CausalEngine has no registry; cannot execute cyclic blocks.")

        cycle_keys = tuple(block.params.get("cycle_state_keys", ()))
        if not cycle_keys:
            cycle_keys = tuple(sorted(state.keys())[:2])

        current_state = dict(state)
        previous_vector: np.ndarray | None = None
        inner_outputs: dict[str, Any] = {}
        last_report: Any = None
        converged = False
        iterations = 0

        for iteration in range(block.max_iterations):
            iterations = iteration + 1
            for inner in block.inner_nodes:
                fqn_full = f"{inner.method_fqn}@{inner.method_version}"
                try:
                    method_cls = _resolve_method_class(self._registry, fqn_full)
                    output = method_cls.pure_step(current_state, inner.params)
                except Exception as exc:
                    inner_outputs[f"{block.node_id}:{inner.node_id}:{iteration}"] = {
                        "warnings": [f"inner cyclic node {fqn_full} failed: {exc}"],
                    }
                    continue
                inner_outputs[f"{block.node_id}:{inner.node_id}:{iteration}"] = output
                if isinstance(output, dict):
                    current_state.update(output)
                    if "report" in output:
                        last_report = output["report"]

            current_vector = np.asarray(
                [float(current_state.get(key, 0.0)) for key in cycle_keys],
                dtype=float,
            )
            if previous_vector is not None:
                delta = float(np.max(np.abs(current_vector - previous_vector)))
                if delta < block.convergence_tol:
                    converged = True
                    break
            previous_vector = current_vector
        else:
            converged = False

        block_output: dict[str, Any] = {
            "convergence_reached": converged,
            "n_iterations": iterations,
            "cycle_state": {key: current_state.get(key) for key in cycle_keys},
            "inner_outputs": inner_outputs,
            "warnings": (
                []
                if converged
                else [
                    "CyclicExecutionBlock did not converge within the iteration budget."
                ]
            ),
        }
        if last_report is not None:
            block_output["report"] = last_report
        return block_output

    # ------------------------------------------------------------------
    # estimate
    # ------------------------------------------------------------------

    def estimate(
        self,
        executor_graph: ExecutorGraph,
        data_dict: dict[str, Any],
    ) -> tuple[Any, dict[str, Any]]:
        """Execute an ExecutorGraph to produce a CausalEffectReport.

        Walks executor_graph.nodes in topological order (respecting depends_on).
        Nuisance nodes are executed first (via nuisance_schedule), then primary nodes.

        Returns
        -------
        (CausalEffectReport | None, node_outputs)
            node_outputs contains the raw dict output of every executed node,
            including sensitivity and diagnostic results.
        """
        from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus

        if self._registry is None:
            raise RuntimeError("CausalEngine has no registry; cannot estimate.")

        state: dict[str, Any] = dict(data_dict)
        node_outputs: dict[str, dict[str, Any]] = {}

        # Topological order: nuisance_schedule first, then remaining nodes
        ordered_ids: list[str] = list(executor_graph.nuisance_schedule)
        for node in executor_graph.nodes:
            if node.node_id not in ordered_ids:
                ordered_ids.append(node.node_id)

        node_map = {n.node_id: n for n in executor_graph.nodes}
        last_report: Any = None
        failed_nodes: set[str] = set()

        for node_id in ordered_ids:
            node = node_map.get(node_id)
            if node is None:
                continue

            # G5: skip if a required predecessor failed
            if any(dep in failed_nodes for dep in getattr(node, "skip_if_failed", ())):
                continue

            # Merge outputs of dependencies into state
            for dep_id in node.depends_on:
                if dep_id in node_outputs:
                    state.update(node_outputs[dep_id])

            if isinstance(node, CyclicExecutionBlock):
                try:
                    output = self._execute_cyclic_block(node, state)
                    node_outputs[node_id] = output
                    if "report" in output:
                        last_report = output["report"]
                except Exception as exc:
                    failed_nodes.add(node_id)
                    if not getattr(node, "is_nuisance", False):
                        try:
                            from polisyos.ir.analytics.causal import CausalMethod
                            last_report = CausalEffectReport(
                                method=getattr(CausalMethod, "AIPW", "unknown"),
                                status=EstimationStatus.NUMERICAL_FAILURE,
                                estimand="unknown",
                                point_estimate=float("nan"),
                                confidence_interval=(-1e12, 1e12),
                                inference_method="none",
                                notes=f"Cyclic block {node_id} failed: {exc}",
                            )
                        except Exception:
                            pass
                        break
                continue

            fqn_full = f"{node.method_fqn}@{node.method_version}"
            try:
                method_cls = _resolve_method_class(self._registry, fqn_full)
                method_state = _prepare_executor_state(node, state)
                output = method_cls.pure_step(method_state, node.params)
                node_outputs[node_id] = output
                if "report" in output:
                    last_report = output["report"]
                elif "twin_network_result" in output:
                    last_report = output["twin_network_result"]
                elif "envelope" in output and last_report is None:
                    last_report = output["envelope"]
            except Exception as exc:
                failed_nodes.add(node_id)
                if not getattr(node, "is_nuisance", False):
                    # Main estimator failure → build report and stop
                    try:
                        from polisyos.ir.analytics.causal import CausalMethod
                        last_report = CausalEffectReport(
                            method=getattr(CausalMethod, "AIPW", "unknown"),
                            status=EstimationStatus.NUMERICAL_FAILURE,
                            estimand="unknown",
                            point_estimate=float("nan"),
                            confidence_interval=(-1e12, 1e12),
                            inference_method="none",
                            notes=f"Node {node_id} failed: {exc}",
                        )
                    except Exception:
                        pass
                    break
                # Nuisance failure → continue; downstream nodes skip via skip_if_failed

        return last_report, node_outputs

    def _diagnostic_only_executor_graph(self, executor_graph: ExecutorGraph) -> ExecutorGraph:
        """Reduce an executor graph to diagnostic nodes for readiness preflight."""
        diagnostic_nodes = tuple(
            node
            for node in executor_graph.nodes
            if str(getattr(node, "method_fqn", "")).startswith("causal.diagnostics.")
        )
        nuisance_schedule = tuple(
            node_id
            for node_id in executor_graph.nuisance_schedule
            if any(node.node_id == node_id for node in diagnostic_nodes)
        )
        return dataclasses.replace(
            executor_graph,
            nodes=diagnostic_nodes,
            nuisance_schedule=nuisance_schedule,
        )

    def _run_readiness_preflight(
        self,
        *,
        executor_graph: ExecutorGraph,
        data_dict: dict[str, Any] | None,
        sample_size: int | None,
        fallback_data_available: bool,
        recoverability_certificate: dict[str, Any] | None = None,
        missingness_assessment: Any | None = None,
    ) -> tuple[DataReadinessReport, dict[str, Any]]:
        """Build readiness from diagnostic nodes before any estimator executes."""
        base_report = build_data_readiness_report(
            sample_size=sample_size,
            measurement_quality="unknown",
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_certificate,
            missingness_assessment=missingness_assessment,
        )
        if data_dict is None or self._registry is None:
            return base_report, {}

        diagnostic_graph = self._diagnostic_only_executor_graph(executor_graph)
        if not diagnostic_graph.nodes:
            # Counterfactual/twin-network executors intentionally skip G2 diagnostic
            # injection, so the absence of diagnostic nodes is not itself a blocker.
            return (
                base_report,
                {},
            )
        try:
            _, diagnostic_outputs = self.estimate(diagnostic_graph, data_dict)
        except Exception:
            return (
                _unknown_data_readiness_report(
                    sample_size=sample_size,
                    fallback_data_available=fallback_data_available,
                    reason="diagnostic_execution_failed",
                ),
                {},
            )
        resolved_report = _build_postrun_readiness_report(
            node_outputs=diagnostic_outputs,
            sample_size=sample_size,
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_certificate,
            missingness_assessment=missingness_assessment,
        )
        return (
            resolved_report
            or _unknown_data_readiness_report(
                sample_size=sample_size,
                fallback_data_available=fallback_data_available,
                reason="diagnostic_outputs_unverified",
            ),
            diagnostic_outputs,
        )

    def _resolve_direct_estimation_readiness(
        self,
        *,
        data: Any,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
    ) -> DataReadinessReport:
        """Verify readiness for direct estimator wrappers using concrete diagnostics."""
        data_dict = _coerce_mapping_like_data(data)
        sample_size = _infer_sample_size(data_dict)
        fallback_data_available = _has_fallback_arrays(data_dict, treatment, outcome)
        registry = _ensure_readiness_registry(self._registry)
        if registry is None:
            return _unknown_data_readiness_report(
                sample_size=sample_size,
                fallback_data_available=fallback_data_available,
                reason="diagnostic_registry_unavailable",
            )

        diagnostic_outputs, status = _run_direct_readiness_diagnostics(
            registry=registry,
            data=data,
            data_dict=data_dict,
            treatment=treatment,
            outcome=outcome,
        )
        report = _build_postrun_readiness_report(
            node_outputs=diagnostic_outputs,
            sample_size=sample_size,
            fallback_data_available=fallback_data_available,
        )
        if status["positivity"] != "verified":
            return _unknown_data_readiness_report(
                sample_size=sample_size,
                fallback_data_available=fallback_data_available,
                reason=status["positivity"],
            )
        if status["support_required"] and status["support"] != "verified":
            return _unknown_data_readiness_report(
                sample_size=sample_size,
                fallback_data_available=fallback_data_available,
                reason=status["support"],
            )
        if report is None:
            return _unknown_data_readiness_report(
                sample_size=sample_size,
                fallback_data_available=fallback_data_available,
                reason="diagnostic_outputs_unverified",
            )
        return report

    def _require_estimation_readiness(
        self,
        *,
        data: Any,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
    ) -> DataReadinessReport:
        """Block direct estimator wrappers before execution when readiness is insufficient."""
        readiness = self._resolve_direct_estimation_readiness(
            data=data,
            treatment=treatment,
            outcome=outcome,
        )
        if readiness.decision in {"block", "unknown"}:
            raise DataReadinessBlockedError(
                readiness,
                reason=(
                    "Estimation path blocked by DataReadinessReport before execution: "
                    f"{readiness.decision}"
                ),
            )
        return readiness

    # ------------------------------------------------------------------
    # audit
    # ------------------------------------------------------------------

    def audit(
        self,
        identification_result: IdentificationResult | NegativeCertificate | None,
        estimation_result: Any | None,
        *,
        run_id: str,
        graph: CausalGraphModel | None = None,
        executor_graph: ExecutorGraph | None = None,
        schema_report: SchemaResolutionReport | None = None,
        node_outputs: dict[str, Any] | None = None,
        negative_certificate: NegativeCertificate | None = None,
        fallback_result: FallbackResult | None = None,
        proof_bundle: Any | None = None,
        bounds_bundle: Any | None = None,
        dual_certificate_payload: dict[str, Any] | None = None,
        data_readiness_report: DataReadinessReport | Any | None = None,
        dp_robustness_certificate: Any | None = None,
    ) -> EvidenceBundle:
        """Build an EvidenceBundle from identification and estimation results.

        Parameters
        ----------
        graph:
            The CausalGraphModel used for identification (for fingerprinting).
        executor_graph:
            Compiled ExecutorGraph (for CompilationStep records).
        """
        from polisyos.foundry.methods.catalog.causal.id_engine import _internal_proof_step_to_ir
        query_str = (
            _identification_query_str(identification_result)
            if isinstance(identification_result, IdentificationResult)
            else ""
        )
        if not query_str and negative_certificate is not None:
            query_str = str(
                negative_certificate.quantitative_diagnostics.get("intervention_query_string")
                or ""
            )
        if proof_bundle is not None:
            proof_payload = proof_bundle
        elif isinstance(identification_result, IdentificationResult):
            proof_payload = proof_bundle_from_identification_result(identification_result)
        elif negative_certificate is not None:
            proof_payload = proof_bundle_from_negative_certificate(
                negative_certificate,
                query_ref=query_str or None,
            )
        else:
            raise ValueError("audit() requires either an identification result or a proof bundle.")
        if not isinstance(proof_payload, ProofBundle):
            proof_payload = ProofBundle.model_validate(proof_payload)
        if self._artifact_store is not None:
            metadata_update = dict(proof_payload.metadata)
            if "bridge_plausibility_report" not in metadata_update:
                for outputs in (node_outputs or {}).values():
                    if isinstance(outputs, dict) and isinstance(
                        outputs.get("bridge_plausibility_report"), dict
                    ):
                        metadata_update["bridge_plausibility_report"] = outputs[
                            "bridge_plausibility_report"
                        ]
                        break
            resolved_query_ref = proof_payload.query_ref
            resolved_frontier_sketch_ref = proof_payload.frontier_sketch_ref
            resolved_bridge_plausibility_report_ref = proof_payload.bridge_plausibility_report_ref
            resolved_proximal_certificate_ref = proof_payload.proximal_certificate_ref
            resolved_recoverability_certificate_ref = proof_payload.recoverability_certificate_ref
            resolved_joint_decision_ref = proof_payload.joint_decision_ref
            intervention_query_payload = metadata_update.get("intervention_query")
            intervention_certificate_payload = metadata_update.get("intervention_certificate")
            frontier_sketch_payload = metadata_update.get("frontier_sketch")
            bridge_plausibility_payload = metadata_update.get("bridge_plausibility_report")
            proximal_certificate_payload = metadata_update.get("proximal_certificate")
            recoverability_certificate_payload = metadata_update.get("recoverability_certificate")
            joint_decision_payload = metadata_update.get("joint_decision")
            intervention_query_ref = None
            if isinstance(intervention_query_payload, dict):
                intervention_query_model = InterventionQuery.model_validate(
                    intervention_query_payload
                )
                intervention_query_ref = persist_intervention_query(
                    self._artifact_store,
                    intervention_query_model,
                )
                metadata_update["intervention_query_ref"] = intervention_query_ref.model_dump(
                    mode="json"
                )
                resolved_query_ref = str(intervention_query_ref.artifact_id)
            if isinstance(intervention_certificate_payload, dict):
                intervention_certificate_model = InterventionCertificate.model_validate(
                    intervention_certificate_payload
                )
                if intervention_query_ref is None:
                    intervention_query_ref = persist_intervention_query(
                        self._artifact_store,
                        intervention_certificate_model.query,
                    )
                    metadata_update["intervention_query_ref"] = intervention_query_ref.model_dump(
                        mode="json"
                    )
                    resolved_query_ref = str(intervention_query_ref.artifact_id)
                intervention_certificate_ref = persist_intervention_certificate(
                    self._artifact_store,
                    intervention_certificate_model,
                    inputs=[
                        InputRef(
                            artifact_id=intervention_query_ref.artifact_id,
                            role="intervention_query",
                        )
                    ],
                )
                metadata_update["intervention_certificate_ref"] = (
                    intervention_certificate_ref.model_dump(mode="json")
                )
            if isinstance(frontier_sketch_payload, dict):
                frontier_sketch_model = FrontierSketch.model_validate(frontier_sketch_payload)
                resolved_frontier_sketch_ref = persist_frontier_sketch(
                    self._artifact_store,
                    frontier_sketch_model,
                )
                metadata_update["frontier_sketch_ref"] = resolved_frontier_sketch_ref.model_dump(
                    mode="json"
                )
            if isinstance(bridge_plausibility_payload, dict):
                bridge_plausibility_model = BridgePlausibilityReport.model_validate(
                    bridge_plausibility_payload
                )
                resolved_bridge_plausibility_report_ref = persist_bridge_plausibility_report(
                    self._artifact_store,
                    bridge_plausibility_model,
                )
                metadata_update["bridge_plausibility_report_ref"] = (
                    resolved_bridge_plausibility_report_ref.model_dump(mode="json")
                )
            if isinstance(proximal_certificate_payload, dict):
                proximal_certificate_model = ProximalIdentificationCertificate.model_validate(
                    proximal_certificate_payload
                )
                resolved_proximal_certificate_ref = persist_proximal_identification_certificate(
                    self._artifact_store,
                    proximal_certificate_model,
                )
                metadata_update["proximal_certificate_ref"] = (
                    resolved_proximal_certificate_ref.model_dump(mode="json")
                )
            if isinstance(recoverability_certificate_payload, dict):
                recoverability_certificate_model = RecoverabilityCertificate.model_validate(
                    recoverability_certificate_payload
                )
                resolved_recoverability_certificate_ref = persist_recoverability_certificate(
                    self._artifact_store,
                    recoverability_certificate_model,
                )
                metadata_update["recoverability_certificate_ref"] = (
                    resolved_recoverability_certificate_ref.model_dump(mode="json")
                )
            if isinstance(joint_decision_payload, dict):
                joint_decision_model = JointDecisionCertificate.model_validate(
                    joint_decision_payload
                )
                if resolved_recoverability_certificate_ref is None:
                    resolved_recoverability_certificate_ref = persist_recoverability_certificate(
                        self._artifact_store,
                        joint_decision_model.recoverability,
                    )
                    metadata_update["recoverability_certificate_ref"] = (
                        resolved_recoverability_certificate_ref.model_dump(mode="json")
                    )
                joint_inputs = (
                    [
                        InputRef(
                            artifact_id=resolved_recoverability_certificate_ref.artifact_id,
                            role="recoverability_certificate",
                        )
                    ]
                    if resolved_recoverability_certificate_ref is not None
                    else None
                )
                resolved_joint_decision_ref = persist_joint_decision_certificate(
                    self._artifact_store,
                    joint_decision_model,
                    inputs=joint_inputs,
                )
                metadata_update["joint_decision_ref"] = resolved_joint_decision_ref.model_dump(
                    mode="json"
                )
            if (
                metadata_update != proof_payload.metadata
                or resolved_query_ref != proof_payload.query_ref
            ):
                proof_payload = proof_payload.model_copy(
                    update={
                        "metadata": metadata_update,
                        "query_ref": resolved_query_ref,
                        "frontier_sketch_ref": resolved_frontier_sketch_ref,
                        "bridge_plausibility_report_ref": resolved_bridge_plausibility_report_ref,
                        "proximal_certificate_ref": resolved_proximal_certificate_ref,
                        "recoverability_certificate_ref": resolved_recoverability_certificate_ref,
                        "joint_decision_ref": resolved_joint_decision_ref,
                    }
                )
        from polisyos.ir.analytics.dp_robustness import (
            attach_dp_robustness_to_proof_bundle,
            coerce_dp_robustness_certificate,
            persist_dp_robustness_certificate,
        )

        resolved_dp_certificate = coerce_dp_robustness_certificate(dp_robustness_certificate)
        if resolved_dp_certificate is None and isinstance(
            getattr(identification_result, "metadata", None),
            dict,
        ):
            resolved_dp_certificate = coerce_dp_robustness_certificate(
                identification_result.metadata
            )
        if resolved_dp_certificate is not None:
            proof_payload = attach_dp_robustness_to_proof_bundle(
                proof_payload,
                getattr(proof_payload, "dp_robustness_ref", None),
                resolved_dp_certificate,
            )
        if not query_str:
            query_str = str(proof_payload.query_ref or "")
        fallback_payload = (
            fallback_result
            or (negative_certificate.fallback_result if negative_certificate is not None else None)
        )
        bounds_payload = bounds_bundle or (
            negative_certificate.bounds_bundle if negative_certificate is not None else None
        )
        if bounds_payload is None and fallback_result is not None and fallback_result.bounds is not None:
            bounds_payload = bounds_bundle_from_partial_identification_result(
                fallback_result.bounds,
                metadata={
                    "epistemic_tier": (
                        fallback_result.bounds_tier.value
                        if fallback_result.bounds_tier is not None
                        else None
                    ),
                    "fallback_level": fallback_result.fallback_level,
                },
            )
        if bounds_payload is not None and not isinstance(bounds_payload, BoundsBundle):
            bounds_payload = BoundsBundle.model_validate(bounds_payload)
        if bounds_payload is None and fallback_payload is not None and fallback_payload.bounds is not None:
            bounds_payload = bounds_bundle_from_partial_identification_result(
                fallback_payload.bounds,
                metadata={
                    "epistemic_tier": (
                        fallback_payload.bounds_tier.value
                        if fallback_payload.bounds_tier is not None
                        else None
                    ),
                    "fallback_level": fallback_payload.fallback_level,
                },
            )

        # -- Proof steps -------------------------------------------------
        ir_steps: list[IRProofStep] = (
            [
                _internal_proof_step_to_ir(s)
                for s in getattr(identification_result, "proof_steps", [])
            ]
            if isinstance(identification_result, IdentificationResult)
            else []
        )

        # -- DataProvenance ----------------------------------------------
        provenance: list[DataProvenance] = []
        for dr in (
            getattr(identification_result, "required_distributions", [])
            if isinstance(identification_result, IdentificationResult)
            else []
        ):
            ref = getattr(dr, "dataset_ref", None) or ""
            quality = 1.0
            n_obs = None
            avail = "available"
            if self._kb is not None and ref:
                try:
                    av, _ = self._kb.can_identify_distribution(dr)
                    avail = av.value if hasattr(av, "value") else str(av)
                    for entry in self._kb.datasets:
                        if entry.dataset_ref == ref:
                            quality = entry.quality_score
                            n_obs = entry.n_obs
                            break
                except Exception:
                    pass
            provenance.append(
                DataProvenance(
                    dataset_ref=ref or "unknown",
                    n_obs=n_obs,
                    quality_score=quality,
                    domain=getattr(dr, "domain", "source").value
                    if hasattr(getattr(dr, "domain", ""), "value")
                    else str(getattr(dr, "domain", "source")),
                    availability_status=avail,
                )
            )

        # -- Diagnostic scores (legacy flat dict) ------------------------
        diag: dict[str, float] = {}
        if schema_report is not None:
            diag["schema_warnings_count"] = float(len(schema_report.support_warnings))
            diag["schema_feasible"] = 1.0 if schema_report.is_feasible else 0.0

        if estimation_result is not None:
            pt = getattr(estimation_result, "point_estimate", None)
            if pt is not None and isinstance(pt, float) and pt == pt:  # not NaN
                diag["point_estimate"] = pt

        for outputs in (node_outputs or {}).values():
            if not isinstance(outputs, dict):
                continue
            sr = outputs.get("sensitivity_result")
            if sr is not None:
                e_val = getattr(sr, "e_value", None) if not isinstance(sr, dict) else sr.get("e_value")
                if e_val is not None:
                    try:
                        diag["e_value"] = float(e_val)
                    except (TypeError, ValueError):
                        pass
                rb = getattr(sr, "rosenbaum_gamma", None) if not isinstance(sr, dict) else sr.get("rosenbaum_gamma")
                if rb is not None:
                    try:
                        diag["rosenbaum_gamma"] = float(rb)
                    except (TypeError, ValueError):
                        pass
            # Also extract from nested "result" dict (PositivityDiagnostic, SupportMismatch)
            result_dict = outputs.get("result", {})
            if isinstance(result_dict, dict):
                for key in ("ess_fraction", "overlap_score"):
                    val = result_dict.get(key)
                    if val is not None and key not in diag:
                        try:
                            diag[key] = float(val)
                        except (TypeError, ValueError):
                            pass
            for key in ("ess_fraction", "overlap_score", "support_mismatch_score"):
                val = outputs.get(key)
                if val is not None and key not in diag:
                    try:
                        diag[key] = float(val)
                    except (TypeError, ValueError):
                        pass
            bridge_report = outputs.get("bridge_plausibility_report")
            if isinstance(bridge_report, dict):
                bridge_metric_keys = {
                    "residual_r": "bridge_residual_r",
                    "effective_rank": "bridge_effective_rank",
                    "sigma_min": "bridge_sigma_min",
                    "ill_posedness_index": "bridge_ill_posedness_index",
                    "proxy_association_score": "bridge_proxy_association",
                }
                for source_key, target_key in bridge_metric_keys.items():
                    val = bridge_report.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass
            kernel_report = outputs.get("kernel_report")
            if isinstance(kernel_report, dict):
                for source_key, target_key in {
                    "effect_norm": "kernel_effect_norm",
                    "condition_number": "kernel_condition_number",
                }.items():
                    val = kernel_report.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass
                if "characteristic" in kernel_report:
                    diag["kernel_characteristic"] = (
                        1.0 if bool(kernel_report["characteristic"]) else 0.0
                    )
                if "weak_metrizing" in kernel_report:
                    diag["kernel_weak_metrizing"] = (
                        1.0 if bool(kernel_report["weak_metrizing"]) else 0.0
                    )
            kernel_semantics = outputs.get("kernel_semantics")
            if isinstance(kernel_semantics, dict):
                if "passed" in kernel_semantics:
                    diag["kernel_semantics_passed"] = (
                        1.0 if bool(kernel_semantics["passed"]) else 0.0
                    )
                if (
                    "characteristic" in kernel_semantics
                    and "kernel_characteristic" not in diag
                ):
                    diag["kernel_characteristic"] = (
                        1.0 if bool(kernel_semantics["characteristic"]) else 0.0
                    )
                if (
                    "weak_metrizing" in kernel_semantics
                    and "kernel_weak_metrizing" not in diag
                ):
                    diag["kernel_weak_metrizing"] = (
                        1.0 if bool(kernel_semantics["weak_metrizing"]) else 0.0
                    )
            kernel_regularization = outputs.get("kernel_regularization")
            if isinstance(kernel_regularization, dict):
                for source_key, target_key in {
                    "condition_number": "kernel_condition_number",
                    "instability": "kernel_regularization_instability",
                }.items():
                    val = kernel_regularization.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass
            kernel_effect_test = outputs.get("kernel_effect_test")
            if isinstance(kernel_effect_test, dict):
                p_val = kernel_effect_test.get("p_value")
                if p_val is not None:
                    try:
                        diag["kernel_effect_test_p_value"] = float(p_val)
                    except (TypeError, ValueError):
                        pass
                if "effect_norm" in kernel_effect_test and "kernel_effect_norm" not in diag:
                    try:
                        diag["kernel_effect_norm"] = float(kernel_effect_test["effect_norm"])
                    except (TypeError, ValueError):
                        pass
            if isinstance(result_dict, dict):
                for source_key, target_key in {
                    "operator_injectivity_score": "operator_injectivity_score",
                    "proxy_association_score": "proxy_association_score",
                }.items():
                    val = result_dict.get(source_key)
                    if val is not None and target_key not in diag:
                        try:
                            diag[target_key] = float(val)
                        except (TypeError, ValueError):
                            pass

        # -- Estimand AST -----------------------------------------------
        estimand_dict: dict[str, Any] = {}
        ast = (
            identification_result.estimand_ast
            if isinstance(identification_result, IdentificationResult)
            else None
        )
        if ast is not None:
            try:
                estimand_dict = ast.model_dump(mode="json")
            except Exception:
                estimand_dict = {}

        method_config: dict[str, Any] = {}
        kernel_spec_payload: dict[str, Any] | None = None
        resolved_kernel_spec = None
        if executor_graph is not None:
            primary_nodes = [
                node
                for node in executor_graph.nodes
                if not getattr(node, "is_nuisance", False)
                and node.method_fqn != "causal.sensitivity.sensitivity_metrics"
            ]
            if primary_nodes:
                primary_node = primary_nodes[-1]
                method_config["primary_method_fqn"] = (
                    f"{primary_node.method_fqn}@{primary_node.method_version}"
                )
            method_config["executor_node_count"] = len(executor_graph.nodes)
            nuisance_fqns = [
                f"{node.method_fqn}@{node.method_version}"
                for node in executor_graph.nodes
                if getattr(node, "is_nuisance", False)
            ]
            if nuisance_fqns:
                method_config["nuisance_method_fqns"] = nuisance_fqns
            for node in executor_graph.nodes:
                payload = node.params.get("kernel_spec")
                if isinstance(payload, dict):
                    kernel_spec_payload = payload
                    break
        if kernel_spec_payload is not None:
            try:
                from polisyos.ir.analytics.kernel_causal import KernelEstimatorSpec

                resolved_kernel_spec = KernelEstimatorSpec.model_validate(kernel_spec_payload)
                method_config.update(
                    {
                        "kernel_template": resolved_kernel_spec.template.value,
                        "kernel_target_representation": (
                            resolved_kernel_spec.target_representation.value
                        ),
                        "kernel_consistency_claim": (
                            resolved_kernel_spec.consistency_claim.value
                        ),
                        "kernel_lowering_disposition": (
                            resolved_kernel_spec.lowering_disposition.value
                        ),
                        "kernel_output_kernel": resolved_kernel_spec.output_kernel.model_dump(
                            mode="json"
                        ),
                    }
                )
            except Exception:
                resolved_kernel_spec = None

        # -- 5.1: fingerprints ------------------------------------------
        graph_fp = ""
        if graph is not None:
            try:
                graph_fp = _fingerprint(graph.model_dump(mode="json"))
            except Exception:
                pass

        estimand_fp = _fingerprint(estimand_dict) if estimand_dict else ""

        # -- 5.1: CompilationStep from executor_graph --------------------
        compilation_steps: list[CompilationStep] = []
        if executor_graph is not None:
            try:
                from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
                    classify_estimand,
                    recommend_estimator,
                )
                shape_val = ""
                strategy_val = ""
                if ast is not None:
                    try:
                        rec = recommend_estimator(ast, n_obs=None, covariate_dim=None)
                        shape_val = rec.shape.value
                        strategy_val = rec.strategy.value
                    except Exception:
                        try:
                            shape_val = classify_estimand(ast).value
                        except Exception:
                            pass
                nuisance_fqns = tuple(
                    n.method_fqn
                    for n in executor_graph.nodes
                    if getattr(n, "is_nuisance", False)
                )
                compilation_steps.append(
                    CompilationStep(
                        estimand_shape=shape_val,
                        estimation_strategy=strategy_val,
                        n_executor_nodes=len(executor_graph.nodes),
                        nuisance_components=nuisance_fqns,
                        compiler_warnings=tuple(str(w) for w in getattr(executor_graph, "warnings", ())),
                    )
                )
            except Exception:
                pass

        # -- 5.1: EstimationStep per executor node -----------------------
        estimation_steps: list[EstimationStep] = []
        if executor_graph is not None and node_outputs:
            import hashlib, json as _json
            for node in executor_graph.nodes:
                nid = node.node_id
                out = (node_outputs or {}).get(nid, {})
                params_hash = ""
                try:
                    params_hash = hashlib.sha256(
                        _json.dumps(node.params, sort_keys=True, default=str).encode()
                    ).hexdigest()[:16]
                except Exception:
                    pass
                node_warnings: list[str] = []
                if isinstance(out, dict):
                    node_warnings = [str(w) for w in out.get("warnings", [])]
                estimation_steps.append(
                    EstimationStep(
                        node_id=nid,
                        method_fqn=node.method_fqn,
                        method_version=node.method_version,
                        backend="",
                        params_hash=params_hash,
                        wall_time_ms=None,
                        determinism_tier="",
                        warnings=tuple(node_warnings),
                        is_nuisance=getattr(node, "is_nuisance", False),
                    )
                )

        # -- 5.2: DiagnosticDashboardData --------------------------------
        dashboard_dict: dict[str, Any] | None = None
        try:
            from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData
            dashboard = DiagnosticDashboardData.from_node_outputs(
                run_id=run_id,
                query_str=query_str,
                node_outputs=node_outputs or {},
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            dashboard_dict = dashboard.model_dump(mode="json")
        except Exception:
            pass

        # -- 5.4: CausalQualityReport ------------------------------------
        quality_dict: dict[str, Any] | None = None
        try:
            from polisyos.foundry.methods.catalog.causal.quality_aggregator import QualityScoreAggregator
            quality_report = QualityScoreAggregator().score(
                run_id=run_id,
                query_str=query_str,
                data_provenance=tuple(provenance),
                estimation_steps=tuple(estimation_steps),
                node_outputs=node_outputs,
            )
            quality_dict = quality_report.model_dump(mode="json")
        except Exception:
            pass

        witness_index = None
        if graph is not None and ir_steps:
            try:
                witness_index = build_witness_index_from_proof_steps(
                    ir_steps,
                    graph=graph,
                    theorem_family=proof_payload.theorem_family,
                )
            except Exception:
                witness_index = None

        proof_trace_ref = proof_payload.proof_trace_ref
        witness_index_ref = proof_payload.witness_index_ref
        if self._artifact_store is not None and proof_trace_ref is None and ir_steps:
            trace_bundle_payload = EvidenceBundle(
                run_id=run_id,
                query_str=query_str,
                estimand_ast=estimand_dict,
                proof_steps=tuple(ir_steps),
                data_provenance=tuple(provenance),
                diagnostic_scores=diag,
                method_config=method_config,
                identification_status=(
                    identification_result.status.value
                    if isinstance(identification_result, IdentificationResult)
                    else str(proof_payload.metadata.get("status") or proof_payload.proof_status)
                ),
                algorithm_version=(
                    getattr(identification_result, "algorithm_version", "id_v1")
                    if isinstance(identification_result, IdentificationResult)
                    else str(
                        negative_certificate.quantitative_diagnostics.get("algorithm_version")
                        if negative_certificate is not None
                        else proof_payload.theorem_family
                    )
                ),
                created_at=datetime.now(timezone.utc).isoformat(),
                graph_fingerprint=graph_fp,
                estimand_fingerprint=estimand_fp,
                compilation_steps=tuple(compilation_steps),
                estimation_steps=tuple(estimation_steps),
                diagnostic_dashboard=dashboard_dict,
                quality_report=quality_dict,
            )
            proof_trace_ref = persist_causal_evidence_bundle(
                self._artifact_store,
                trace_bundle_payload,
            )
        if (
            self._artifact_store is not None
            and witness_index_ref is None
            and witness_index is not None
        ):
            witness_inputs = (
                [
                    InputRef(
                        artifact_id=proof_trace_ref.artifact_id,
                        role="proof_trace",
                    )
                ]
                if proof_trace_ref is not None
                else None
            )
            witness_index_ref = persist_proof_witness_index(
                self._artifact_store,
                witness_index,
                inputs=witness_inputs,
            )
        if proof_trace_ref is not None or witness_index_ref is not None or witness_index is not None:
            metadata_update = dict(proof_payload.metadata)
            if proof_trace_ref is not None:
                metadata_update["proof_trace_ref"] = proof_trace_ref.model_dump(mode="json")
            if witness_index_ref is not None:
                metadata_update["witness_index_ref"] = witness_index_ref.model_dump(mode="json")
            proof_support_projection_hash = (
                proof_payload.proof_support_projection_hash
                or (
                    witness_index.proof_support_projection_hash
                    if witness_index is not None
                    else None
                )
            )
            metadata_update["proof_support_projection_hash"] = proof_support_projection_hash
            metadata_update.setdefault(
                "composability_status",
                proof_payload.composability_status,
            )
            proof_payload = proof_payload.model_copy(
                update={
                    "proof_trace_ref": proof_trace_ref,
                    "witness_index_ref": witness_index_ref,
                    "proof_support_projection_hash": proof_support_projection_hash,
                    "metadata": metadata_update,
                }
            )
        if (
            self._artifact_store is not None
            and graph is not None
            and witness_index is not None
            and witness_index.witnesses
        ):
            proof_payload = _attach_proof_composability_certificate(
                store=self._artifact_store,
                proof_payload=proof_payload,
                witness_index=witness_index,
                graph=graph,
                query_str=query_str,
                graph_fingerprint=graph_fp,
            )

        proof_bundle_ref = None
        bounds_bundle_ref = None
        negative_certificate_ref = None
        data_readiness_report_ref = None
        kernel_estimator_spec_ref = None
        if self._artifact_store is not None:
            if resolved_dp_certificate is not None:
                dp_robustness_ref = persist_dp_robustness_certificate(
                    self._artifact_store,
                    resolved_dp_certificate,
                )
                proof_payload = attach_dp_robustness_to_proof_bundle(
                    proof_payload,
                    dp_robustness_ref,
                    resolved_dp_certificate,
                )
            proof_bundle_inputs = [
                InputRef(artifact_id=trace_ref.artifact_id, role="proof_trace")
                for trace_ref in (proof_payload.proof_trace_ref,)
                if trace_ref is not None
            ]
            proof_bundle_inputs.extend(
                InputRef(
                    artifact_id=witness_ref.artifact_id,
                    role="proof_witness_index",
                )
                for witness_ref in (proof_payload.witness_index_ref,)
                if witness_ref is not None
            )
            proof_bundle_inputs.extend(
                InputRef(
                    artifact_id=composability_ref.artifact_id,
                    role="proof_composability_certificate",
                )
                for composability_ref in (proof_payload.composability_certificate_ref,)
                if composability_ref is not None
            )
            proof_bundle_ref = persist_proof_bundle(
                self._artifact_store,
                proof_payload,
                inputs=proof_bundle_inputs or None,
            )
            if bounds_payload is not None:
                bounds_payload, bounds_inputs = hydrate_bounds_bundle_with_dual_certificate(
                    self._artifact_store,
                    bounds_payload,
                    dual_certificate_payload,
                )
                bounds_bundle_ref = persist_bounds_bundle(
                    self._artifact_store,
                    bounds_payload,
                    inputs=bounds_inputs,
                )
            if data_readiness_report is not None:
                readiness_payload = (
                    data_readiness_report
                    if isinstance(data_readiness_report, DataReadinessReport)
                    else DataReadinessReport.model_validate(data_readiness_report)
                )
                readiness_update: dict[str, Any] = {}
                if (
                    proof_payload.recoverability_certificate_ref is not None
                    and readiness_payload.recoverability_certificate_ref is None
                ):
                    readiness_update["recoverability_certificate_ref"] = (
                        proof_payload.recoverability_certificate_ref
                    )
                if (
                    proof_payload.joint_decision_ref is not None
                    and readiness_payload.joint_decision_ref is None
                ):
                    readiness_update["joint_decision_ref"] = proof_payload.joint_decision_ref
                if readiness_update:
                    readiness_payload = readiness_payload.model_copy(update=readiness_update)
                if (
                    resolved_dp_certificate is not None
                    and readiness_payload.dp_distortion is None
                ):
                    from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

                    readiness_payload = apply_dp_readiness_gate(
                        readiness_payload,
                        resolved_dp_certificate,
                    )
                data_readiness_report_ref = persist_data_readiness_report(
                    self._artifact_store,
                    readiness_payload,
                )
            if negative_certificate is not None:
                negative_inputs = (
                    [
                        InputRef(
                            artifact_id=bounds_bundle_ref.artifact_id,
                            role="bounds_bundle",
                        )
                    ]
                    if bounds_bundle_ref is not None
                    else None
                )
                negative_certificate_ref = persist_negative_certificate(
                    self._artifact_store,
                    negative_certificate,
                    inputs=negative_inputs,
                )
            if resolved_kernel_spec is not None:
                from polisyos.ir.analytics.kernel_causal import persist_kernel_estimator_spec

                if proof_bundle_ref is not None and resolved_kernel_spec.proof_bundle_ref is None:
                    resolved_kernel_spec = resolved_kernel_spec.model_copy(
                        update={"proof_bundle_ref": proof_bundle_ref}
                    )
                kernel_inputs = (
                    [
                        InputRef(
                            artifact_id=proof_bundle_ref.artifact_id,
                            role="proof_bundle",
                        )
                    ]
                    if proof_bundle_ref is not None
                    else None
                )
                kernel_estimator_spec_ref = persist_kernel_estimator_spec(
                    self._artifact_store,
                    resolved_kernel_spec,
                    inputs=kernel_inputs,
                )
                method_config["kernel_estimator_spec_ref"] = (
                    kernel_estimator_spec_ref.model_dump(mode="json")
                )

        return EvidenceBundle(
            run_id=run_id,
            query_str=query_str,
            estimand_ast=estimand_dict,
            proof_steps=tuple(ir_steps),
            data_provenance=tuple(provenance),
            diagnostic_scores=diag,
            method_config=method_config,
            identification_status=(
                identification_result.status.value
                if isinstance(identification_result, IdentificationResult)
                else str(proof_payload.metadata.get("status") or proof_payload.proof_status)
            ),
            algorithm_version=(
                getattr(identification_result, "algorithm_version", "id_v1")
                if isinstance(identification_result, IdentificationResult)
                else str(
                    negative_certificate.quantitative_diagnostics.get("algorithm_version")
                    if negative_certificate is not None
                    else proof_payload.theorem_family
                )
            ),
            created_at=datetime.now(timezone.utc).isoformat(),
            graph_fingerprint=graph_fp,
            estimand_fingerprint=estimand_fp,
            compilation_steps=tuple(compilation_steps),
            estimation_steps=tuple(estimation_steps),
            diagnostic_dashboard=dashboard_dict,
            quality_report=quality_dict,
            proof_bundle_ref=proof_bundle_ref,
            bounds_bundle_ref=bounds_bundle_ref,
            negative_certificate_ref=negative_certificate_ref,
            data_readiness_report_ref=data_readiness_report_ref,
            kernel_estimator_spec_ref=kernel_estimator_spec_ref,
        )

    # ------------------------------------------------------------------
    # run (full pipeline)
    # ------------------------------------------------------------------

    def run(
        self,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        graph: CausalGraphModel,
        data_dict: dict[str, Any] | None = None,
        *,
        df_columns: list[str] | None = None,
        df_dtypes: dict[str, str] | None = None,
        source_domains: list[Any] | None = None,
        s_nodes: list[Any] | None = None,
        z_interventions: frozenset[str] | None = None,
        conditions: frozenset[str] | None = None,
        n_obs: int | None = None,
        covariate_dim: int | None = None,
        run_id: str | None = None,
        oracle: str = "none",
        use_cross_fitting: bool = True,
        dataset_ref: str | None = None,
        mgraph_meta: Any | None = None,
        counterfactual_query: CtfQuery | None = None,
        intervention_query: InterventionQuery | None = None,
        proximal_annotation: ProxyAnnotation | dict[str, Any] | None = None,
    ) -> tuple[Any, EvidenceBundle, NegativeCertificate | None]:
        """Run the full Pearl-Bareinboim pipeline: identify → compile → estimate → audit.

        Returns
        -------
        (CausalEffectReport | None, EvidenceBundle, NegativeCertificate | None)
        """
        run_id = run_id or uuid.uuid4().hex

        schema_report: SchemaResolutionReport | None = None

        # 1. Identify
        id_result = self.identify(
            treatment=treatment,
            outcome=outcome,
            graph=graph,
            source_domains=source_domains,
            s_nodes=s_nodes,
            z_interventions=z_interventions,
            conditions=conditions,
            oracle=oracle,
            dataset_ref=dataset_ref,
            mgraph_meta=mgraph_meta,
            counterfactual_query=counterfactual_query,
            intervention_query=intervention_query,
            proximal_annotation=proximal_annotation,
        )

        sample_size = _infer_sample_size(data_dict, explicit_n_obs=n_obs)
        fallback_data_available = _has_fallback_arrays(data_dict, treatment, outcome)
        (
            resolved_id_result,
            proof_bundle,
            negative_cert,
            resolved_bounds_bundle,
            dual_certificate_payload,
            dp_robustness_certificate,
            proximal_certificate,
        ) = self._materialize_identification_artifacts(
            id_result,
            graph=graph,
            treatment=treatment,
            outcome=outcome,
            data_dict=data_dict,
        )
        recoverability_summary = _extract_recoverability_summary(
            resolved_id_result if negative_cert is None else negative_cert
        ) or _extract_recoverability_summary(proof_bundle)
        missingness_assessment = _resolve_missingness_assessment(
            graph=graph,
            data_dict=data_dict,
            mgraph_meta=mgraph_meta,
            treatment=treatment,
            outcome=outcome,
        )

        # If identification failed, return canonical impossibility artifacts.
        if negative_cert is not None:
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="unknown",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
                extra_metrics=_float_metrics_from_mapping(negative_cert.quantitative_diagnostics),
            )
            bundle = self.audit(
                None,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                negative_certificate=negative_cert,
                fallback_result=negative_cert.fallback_result,
                proof_bundle=proof_bundle,
                bounds_bundle=resolved_bounds_bundle,
                dual_certificate_payload=dual_certificate_payload,
                data_readiness_report=readiness_report,
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, negative_cert

        if proximal_certificate is not None:
            proximal_state = _derive_proximal_bridge_state(
                data_dict=data_dict,
                treatment=treatment,
                outcome=outcome,
                certificate=proximal_certificate,
            )
            proximal_output: dict[str, Any] | None = None
            proximal_metrics: dict[str, Any] = {
                "bridge_functions_count": proof_bundle.metadata.get(
                    "bridge_functions_count"
                ),
                "graph_checks_count": proof_bundle.metadata.get("graph_checks_count"),
            }
            if proximal_state is not None:
                from polisyos.foundry.methods.catalog.causal.frontier import (
                    ProximalBridgeEstimator,
                )

                proximal_output = ProximalBridgeEstimator.pure_step(
                    proximal_state,
                    {
                        "n_bootstrap": 200,
                        "confidence_level": 0.95,
                        "ridge": 1.0e-4,
                        "__seed__": int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16),
                    },
                )
                bridge_report_payload = proximal_output.get("bridge_plausibility_report")
                if isinstance(bridge_report_payload, dict):
                    proximal_metrics.update(
                        {
                            "bridge_residual_r": bridge_report_payload.get("residual_r"),
                            "bridge_effective_rank": bridge_report_payload.get("effective_rank"),
                            "bridge_sigma_min": bridge_report_payload.get("sigma_min"),
                            "bridge_proxy_association": bridge_report_payload.get(
                                "proxy_association_score"
                            ),
                        }
                    )

            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="proxy_only",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
                extra_metrics=_float_metrics_from_mapping(proximal_metrics),
            )
            if proximal_output is not None:
                proximal_report = proximal_output.get("report")
                node_outputs = {"proximal_bridge": proximal_output}
                negative_payload = proximal_output.get("negative_certificate")
                bounds_payload = proximal_output.get("bounds_bundle")
                proximal_negative_cert = (
                    NegativeCertificate.model_validate(negative_payload)
                    if isinstance(negative_payload, dict)
                    else None
                )
                proximal_bounds_bundle = None
                if proximal_negative_cert is not None:
                    proximal_bounds_bundle = proximal_negative_cert.bounds_bundle
                if proximal_bounds_bundle is None and isinstance(bounds_payload, dict):
                    proximal_bounds_bundle = BoundsBundle.model_validate(bounds_payload)
                if proximal_negative_cert is not None:
                    bundle = self.audit(
                        None,
                        proximal_report,
                        run_id=run_id,
                        graph=graph,
                        schema_report=schema_report,
                        node_outputs=node_outputs,
                        negative_certificate=proximal_negative_cert,
                        proof_bundle=proof_bundle,
                        bounds_bundle=proximal_bounds_bundle,
                        data_readiness_report=readiness_report,
                    )
                    return None, bundle, proximal_negative_cert
                if proximal_report is not None:
                    bundle = self.audit(
                        None,
                        proximal_report,
                        run_id=run_id,
                        graph=graph,
                        schema_report=schema_report,
                        node_outputs=node_outputs,
                        proof_bundle=proof_bundle,
                        data_readiness_report=readiness_report,
                    )
                    return proximal_report, bundle, None
            bundle = self.audit(
                None,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                proof_bundle=proof_bundle,
                data_readiness_report=readiness_report,
            )
            return None, bundle, None

        assert resolved_id_result is not None

        proximal_mediation_payload = dict(
            getattr(resolved_id_result, "metadata", {}) or {}
        ).get("proximal_mediation_certificate")
        if proximal_mediation_payload is not None:
            from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
                PROXIMAL_MEDIATION_V1_THEOREM,
                ProximalMediationEstimator,
            )
            from polisyos.ir.analytics.proximal import ProximalMediationCertificate

            proximal_mediation_certificate = ProximalMediationCertificate.model_validate(
                proximal_mediation_payload
            )
            proximal_mediation_state = _derive_proximal_mediation_state(
                data_dict=data_dict,
                certificate=proximal_mediation_certificate,
            )
            bridge_metrics: dict[str, Any] = {
                "bridge_equations_count": len(proximal_mediation_certificate.bridge_equations),
                "graph_checks_count": len(proximal_mediation_certificate.graph_checks),
            }
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="proxy_only",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
                extra_metrics=_float_metrics_from_mapping(bridge_metrics),
            )
            if proximal_mediation_state is None:
                bundle = self.audit(
                    resolved_id_result,
                    None,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    proof_bundle=proof_bundle,
                    bounds_bundle=resolved_bounds_bundle,
                    dual_certificate_payload=dual_certificate_payload,
                    data_readiness_report=readiness_report,
                    dp_robustness_certificate=dp_robustness_certificate,
                )
                return None, bundle, None

            proximal_mediation_output = ProximalMediationEstimator.pure_step(
                proximal_mediation_state,
                {
                    "theorem_family": PROXIMAL_MEDIATION_V1_THEOREM,
                    "oracle_gate": (
                        "accepted"
                        if bool(
                            dict(getattr(resolved_id_result, "metadata", {}) or {}).get(
                                "oracle_assumptions_accepted",
                                False,
                            )
                        )
                        else "required"
                    ),
                    "target_effect": proximal_mediation_certificate.query.target_effect,
                    "treatment_name": proximal_mediation_certificate.query.treatment,
                    "mediator_name": proximal_mediation_certificate.query.mediator,
                    "outcome_name": proximal_mediation_certificate.query.outcome,
                    "treatment_proxy_names": list(
                        proximal_mediation_certificate.variable_roles.get("Z", ())
                    ),
                    "outcome_proxy_names": list(
                        proximal_mediation_certificate.variable_roles.get("W", ())
                    ),
                    "covariate_names": list(
                        proximal_mediation_certificate.variable_roles.get("X", ())
                    ),
                    "n_bootstrap": 200,
                    "confidence_level": 0.95,
                    "ridge": 1.0e-4,
                    "y_lower": (
                        _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )[0]
                        if _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )
                        is not None
                        else None
                    ),
                    "y_upper": (
                        _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )[1]
                        if _resolve_graph_outcome_support(
                            graph,
                            outcome=proximal_mediation_certificate.query.outcome,
                        )
                        is not None
                        else None
                    ),
                    "__seed__": int(hashlib.sha256(run_id.encode()).hexdigest()[:8], 16),
                },
            )
            bridge_report_payload = proximal_mediation_output.get("bridge_plausibility_report")
            if isinstance(bridge_report_payload, dict):
                bridge_metrics.update(
                    {
                        "bridge_residual_r": bridge_report_payload.get("residual_r"),
                        "bridge_effective_rank": bridge_report_payload.get("effective_rank"),
                        "bridge_sigma_min": bridge_report_payload.get("sigma_min"),
                        "bridge_proxy_association": bridge_report_payload.get(
                            "proxy_association_score"
                        ),
                    }
                )
                readiness_report = build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="proxy_only",
                    fallback_data_available=fallback_data_available,
                    recoverability_certificate=recoverability_summary,
                    missingness_assessment=missingness_assessment,
                    extra_metrics=_float_metrics_from_mapping(bridge_metrics),
                )
            proximal_report = proximal_mediation_output.get("report")
            node_outputs = {"proximal_mediation": proximal_mediation_output}
            negative_payload = proximal_mediation_output.get("negative_certificate")
            bounds_payload = proximal_mediation_output.get("bounds_bundle")
            proximal_negative_cert = (
                NegativeCertificate.model_validate(negative_payload)
                if isinstance(negative_payload, dict)
                else None
            )
            proximal_bounds_bundle = None
            if proximal_negative_cert is not None:
                proximal_bounds_bundle = proximal_negative_cert.bounds_bundle
            if proximal_bounds_bundle is None and isinstance(bounds_payload, dict):
                proximal_bounds_bundle = BoundsBundle.model_validate(bounds_payload)
            if proximal_negative_cert is not None:
                bundle = self.audit(
                    resolved_id_result,
                    proximal_report,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    node_outputs=node_outputs,
                    negative_certificate=proximal_negative_cert,
                    proof_bundle=proof_bundle,
                    bounds_bundle=proximal_bounds_bundle,
                    data_readiness_report=readiness_report,
                )
                return None, bundle, proximal_negative_cert
            if proximal_report is not None and getattr(
                proximal_report, "status", None
            ) is EstimationStatus.SUCCESS:
                bundle = self.audit(
                    resolved_id_result,
                    proximal_report,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    node_outputs=node_outputs,
                    proof_bundle=proof_bundle,
                    data_readiness_report=readiness_report,
                )
                return proximal_report, bundle, None
            bundle = self.audit(
                resolved_id_result,
                proximal_report,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                node_outputs=node_outputs,
                proof_bundle=proof_bundle,
                bounds_bundle=proximal_bounds_bundle or resolved_bounds_bundle,
                data_readiness_report=readiness_report,
            )
            return None, bundle, None

        if resolved_id_result.status is not IdentificationStatus.IDENTIFIED:
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="unknown",
                fallback_data_available=fallback_data_available,
                recoverability_certificate=recoverability_summary,
                missingness_assessment=missingness_assessment,
            )
            bundle = self.audit(
                resolved_id_result,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                proof_bundle=proof_bundle,
                bounds_bundle=resolved_bounds_bundle,
                dual_certificate_payload=dual_certificate_payload,
                data_readiness_report=readiness_report,
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, None

        if dp_robustness_certificate is not None:
            from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

            dp_readiness = apply_dp_readiness_gate(
                build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                    recoverability_certificate=recoverability_summary,
                    missingness_assessment=missingness_assessment,
                ),
                dp_robustness_certificate,
            )
            if not dp_readiness.can_run_estimation:
                bundle = self.audit(
                    resolved_id_result,
                    None,
                    run_id=run_id,
                    graph=graph,
                    schema_report=schema_report,
                    proof_bundle=proof_bundle,
                    bounds_bundle=resolved_bounds_bundle,
                    dual_certificate_payload=dual_certificate_payload,
                    data_readiness_report=dp_readiness,
                    dp_robustness_certificate=dp_robustness_certificate,
                )
                return None, bundle, None

        # G4: validate query structure and KB feasibility before compiling
        from polisyos.foundry.methods.catalog.causal.query_validator import CausalQueryValidator
        val_report = CausalQueryValidator().validate(graph, resolved_id_result.estimand_ast, self._kb)
        if val_report.has_errors():
            neg_cert = NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description="; ".join(e.message for e in val_report.errors),
                quantitative_diagnostics={
                    "identification_status": str(resolved_id_result.status.value),
                    "algorithm_version": str(
                        getattr(resolved_id_result, "algorithm_version", "") or ""
                    ),
                },
                constructive_message=(
                    "Fix graph structure or provide required data before proceeding."
                ),
            )
            bundle = self.audit(
                resolved_id_result,
                None,
                run_id=run_id,
                graph=graph,
                negative_certificate=neg_cert,
                proof_bundle=proof_bundle,
                data_readiness_report=build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                    recoverability_certificate=recoverability_summary,
                    missingness_assessment=missingness_assessment,
                ),
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, neg_cert

        # 2. Optional schema resolution (now that we have the estimand)
        if (
            df_columns is not None
            and df_dtypes is not None
            and resolved_id_result.estimand_ast is not None
        ):
            resolver = SchemaResolver()
            schema_report = resolver.resolve(
                resolved_id_result.estimand_ast,
                df_columns=df_columns,
                df_dtypes=df_dtypes,
            )

        # 3. Compile
        try:
            executor_graph = self.compile(
                resolved_id_result,
                graph=graph,
                n_obs=n_obs,
                covariate_dim=covariate_dim,
                run_id=run_id,
                use_cross_fitting=use_cross_fitting,
            )
        except Exception as exc:
            neg_cert = NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description=f"Compilation failed: {exc}",
                quantitative_diagnostics={
                    "identification_status": str(resolved_id_result.status.value),
                    "algorithm_version": str(
                        getattr(resolved_id_result, "algorithm_version", "") or ""
                    ),
                },
                constructive_message="Check that the estimand AST is valid.",
            )
            bundle = self.audit(
                resolved_id_result,
                None,
                run_id=run_id,
                graph=graph,
                schema_report=schema_report,
                negative_certificate=neg_cert,
                proof_bundle=proof_bundle,
                bounds_bundle=resolved_bounds_bundle,
                data_readiness_report=build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                    missingness_assessment=missingness_assessment,
                ),
                dp_robustness_certificate=dp_robustness_certificate,
            )
            return None, bundle, neg_cert

        # G2: inject diagnostic nodes (PositivityDiagnostic always; SupportMismatch for transport)
        executor_graph = self._inject_diagnostic_nodes(
            executor_graph,
            resolved_id_result.estimand_ast,
        )

        preflight_readiness, preflight_outputs = self._run_readiness_preflight(
            executor_graph=executor_graph,
            data_dict=data_dict,
            sample_size=sample_size,
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_summary,
            missingness_assessment=missingness_assessment,
        )
        if dp_robustness_certificate is not None:
            from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

            preflight_readiness = apply_dp_readiness_gate(
                preflight_readiness,
                dp_robustness_certificate,
            )

        # 4. Estimate only after readiness preflight has allowed execution.
        effect_report: Any = None
        node_outputs: dict[str, Any] = dict(preflight_outputs)
        if (
            data_dict is not None
            and self._registry is not None
            and preflight_readiness.can_run_estimation
        ):
            try:
                effect_report, execution_outputs = self.estimate(executor_graph, data_dict)
                if (
                    effect_report is not None
                    and isinstance(getattr(resolved_id_result, "metadata", None), dict)
                    and resolved_id_result.metadata
                ):
                    effect_report = effect_report.model_copy(
                        update={
                            "metadata": {
                                **dict(effect_report.metadata),
                                **dict(resolved_id_result.metadata),
                            }
                        }
                    )
                node_outputs.update(execution_outputs)
            except Exception:
                pass  # estimate is best-effort; audit still proceeds
        postrun_readiness = _build_postrun_readiness_report(
            node_outputs=node_outputs,
            sample_size=sample_size,
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_summary,
            missingness_assessment=missingness_assessment,
        )
        if postrun_readiness is not None and dp_robustness_certificate is not None:
            from polisyos.ir.analytics.dp_robustness import apply_dp_readiness_gate

            postrun_readiness = apply_dp_readiness_gate(
                postrun_readiness,
                dp_robustness_certificate,
            )
        data_readiness = (
            preflight_readiness
            if not preflight_readiness.can_run_estimation
            else (postrun_readiness or preflight_readiness)
        )

        # 5. Audit
        bundle = self.audit(
            resolved_id_result,
            effect_report,
            run_id=run_id,
            graph=graph,
            executor_graph=executor_graph,
            schema_report=schema_report,
            node_outputs=node_outputs,
            proof_bundle=proof_bundle,
            bounds_bundle=resolved_bounds_bundle,
            data_readiness_report=data_readiness,
            dp_robustness_certificate=dp_robustness_certificate,
        )

        # 6. Build CausalRunSnapshot for reproducibility
        try:
            from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot

            estimand_dict: dict[str, Any] = {}
            if resolved_id_result.estimand_ast is not None:
                try:
                    estimand_dict = resolved_id_result.estimand_ast.model_dump(mode="json")
                except Exception:
                    pass

            snapshot = CausalRunSnapshot.build(
                run_id=run_id,
                graph=graph,
                estimand_ast_dict=estimand_dict,
                estimand_shape=bundle.compilation_steps[0].estimand_shape
                if bundle.compilation_steps
                else "",
                query_str=bundle.query_str,
                estimation_steps=bundle.estimation_steps,
                data_dict=data_dict,
                algorithm_version=bundle.algorithm_version,
                compilation_steps=bundle.compilation_steps,
            )
            # Attach snapshot to bundle metadata for downstream consumers
            bundle = dataclasses.replace(bundle, snapshot=snapshot) if hasattr(bundle, "snapshot") else bundle
            # Store on engine instance for programmatic access
            self._last_snapshot = snapshot
        except Exception:
            pass  # snapshot is best-effort; never blocks the pipeline

        return effect_report, bundle, None

    def _persist_temporal_payload(
        self,
        payload: dict[str, Any],
        *,
        kind: str,
        schema_name: str,
        schema_version: str = "1.0",
        inputs: list[Any] | None = None,
    ) -> ArtifactRefModel:
        if self._artifact_store is None:
            raise RuntimeError("Temporal payload persistence requires an ArtifactStore")
        ref = put_json_artifact(
            self._artifact_store,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version=schema_version,
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return ArtifactRefModel.model_validate(ref)

    @staticmethod
    def _artifact_input_ref(ref: Any, *, role: str) -> dict[str, str]:
        artifact_id = getattr(ref, "artifact_id", ref)
        return {"artifact_id": str(artifact_id), "role": role}

    def _temporal_input_refs(self, *refs_and_roles: tuple[Any | None, str]) -> list[dict[str, str]]:
        inputs: list[dict[str, str]] = []
        for ref, role in refs_and_roles:
            if ref is None:
                continue
            inputs.append(self._artifact_input_ref(ref, role=role))
        return inputs

    @staticmethod
    def _serialize_ref(ref: Any | None) -> dict[str, Any] | None:
        if ref is None:
            return None
        if hasattr(ref, "model_dump"):
            return ref.model_dump(mode="python")
        if isinstance(ref, dict):
            return dict(ref)
        return None

    def _resolve_temporal_intervention(
        self,
        query: ContinuousTimeQuery,
        *,
        intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
    ) -> tuple[TemporalInterventionTrajectory, ArtifactRefModel | None, str]:
        from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
            TemporalCompileError,
        )

        if intervention is not None:
            resolved = (
                intervention
                if isinstance(intervention, TemporalInterventionTrajectory)
                else TemporalInterventionTrajectory.model_validate(intervention)
            )
            return resolved, None, "override"

        if self._artifact_store is None:
            raise TemporalCompileError(
                "missing_intervention_contract",
                "CausalEngine.temporal_causal_effect requires an intervention override or an ArtifactStore-backed intervention contract.",
            )

        if query.intervention_trajectory_ref is None:
            raise TemporalCompileError(
                "missing_intervention_contract",
                "ContinuousTimeQuery.intervention_trajectory_ref is required for fixed_intervention execution when no override is provided.",
            )

        if query.intervention_trajectory_ref.kind != "ir.temporal_intervention_trajectory":
            raise TemporalCompileError(
                "invalid_intervention_contract_ref",
                "ContinuousTimeQuery.intervention_trajectory_ref must point to an ir.temporal_intervention_trajectory artifact for engine-level execution.",
                details={"kind": query.intervention_trajectory_ref.kind},
            )

        intervention_ref = TemporalInterventionTrajectoryRef.model_validate(
            query.intervention_trajectory_ref.model_dump(mode="python")
        )
        return (
            load_temporal_intervention_trajectory(self._artifact_store, intervention_ref),
            intervention_ref,
            "artifact_store",
        )

    def dynamic_causal_effect(
        self,
        data: "DynamicTreatmentData",
        regime: "DynamicTreatmentRegime | None" = None,
        method: str = "ice_g",
        run_id: "str | None" = None,
    ) -> "GComputationResult":
        """Estimate the causal effect of a dynamic treatment regime.

        Bypasses the standard identify → compile → estimate → audit pipeline
        (which is designed for cross-sectional identification). Uses sequential
        ignorability: A_t ⊥ Y^{ā} | H_t for all t.

        Args:
            data:   DynamicTreatmentData with time-varying treatment and covariates.
            regime: Optional DynamicTreatmentRegime spec. If None, uses the regime
                    specified in params (default: always_treat).
            method: One of "parametric_g", "ice_g", "ltmle", "g_estimation".
            run_id: Optional run identifier for logging.

        Returns:
            GComputationResult (not EvidenceBundle — no graph-based ID step).
        """
        self._require_estimation_readiness(
            data=data,
            treatment="treatment",
            outcome="outcome",
        )
        from polisyos.foundry.methods.catalog.causal.causal_rl import (  # noqa: F401
            CausalBandit,
        )
        from polisyos.foundry.methods.catalog.causal.dtr import (  # noqa: F401
            ALearningDTR,
            DoublyRobustDTR,
            OutcomeWeightedLearning,
            QLearningDTR,
        )
        from polisyos.foundry.methods.catalog.causal.g_computation import (
            ICEGFormula,
            LTMLEEstimator,
            ParametricGFormula,
        )
        from polisyos.foundry.methods.catalog.causal.g_estimation import (
            StructuralNestedMeanModel,
        )
        from polisyos.ir.analytics.dynamic_regime import GComputationResult

        _method_dispatch: dict[str, type] = {
            "parametric_g": ParametricGFormula,
            "ice_g": ICEGFormula,
            "ltmle": LTMLEEstimator,
            "g_estimation": StructuralNestedMeanModel,
        }

        method_cls = _method_dispatch.get(method)
        if method_cls is None:
            raise ValueError(
                f"Unknown dynamic method {method!r}. "
                f"Choose from: {sorted(_method_dispatch)}"
            )

        params: dict[str, object] = {}
        if regime is not None:
            params["regime"] = regime.rule.value
            params["threshold_covariate_index"] = regime.threshold_covariate_index
            params["threshold_value"] = regime.threshold_value

        result = method_cls.pure_step(data, params)
        g_result = result.get("g_result")
        if g_result is None:
            # g_estimation returns snmm_result, not g_result — wrap into GComputationResult
            report = result.get("report")
            if report is not None and hasattr(report, "point_estimate"):
                from polisyos.ir.analytics.dynamic_regime import GComputationResult

                g_result = GComputationResult(
                    counterfactual_mean=float(report.point_estimate or 0.0),
                    confidence_interval=report.confidence_interval or (0.0, 0.0),
                    confidence_level=0.95,
                    standard_error=float(report.standard_error or 0.0),
                    regime=str(params.get("regime", "always_treat")),
                    n_units=report.sample_size,
                    n_periods=report.pre_periods,
                    method="ice_g",
                )
            else:
                raise RuntimeError(
                    f"Method {method!r} did not return a GComputationResult. "
                    "Check that the estimator succeeded."
                )
        return g_result

    def temporal_causal_effect(
        self,
        data: Any,
        query: ContinuousTimeQuery,
        *,
        regime: DynamicTreatmentRegime | None = None,
        intervention: TemporalInterventionTrajectory | dict[str, Any] | None = None,
        method: str = "linear_sde",
        identification_certificate: TemporalIdentificationCertificate | dict[str, Any] | None = None,
    ) -> Any:
        """Estimate a temporal effect trajectory and optionally persist its bundle."""

        readiness_treatment = "treatment"
        readiness_outcome = "outcome"
        if str(method).strip().lower() == "event_process_weighting":
            readiness_treatment = "policy_weights"
            readiness_outcome = "outcome_events"
        if str(method).strip().lower() != "event_process_weighting":
            self._require_estimation_readiness(
                data=data,
                treatment=readiness_treatment,
                outcome=readiness_outcome,
            )
        from polisyos.foundry.methods.catalog.causal.dtr import estimate_dtr_trajectory
        from polisyos.foundry.methods.catalog.causal.g_computation import (
            estimate_g_computation_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.event_process_weighting import (
            estimate_event_process_weighting_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.protocols import (
            DynamicTreatmentData,
            EventProcessObservationalData,
            PanelObservationalData,
        )
        from polisyos.foundry.methods.catalog.causal.structural_time_series import (
            estimate_structural_time_series_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
            TemporalCompileError,
        )

        resolved_identification_certificate = self._normalize_temporal_identification_certificate(
            identification_certificate,
            query=query,
        )
        effective_query = query.model_copy(
            update={
                "metadata": {
                    **query.metadata,
                    "preferred_backend": method,
                    **(
                        {
                            "temporal_identification_certificate": (
                                resolved_identification_certificate.model_dump(mode="json")
                            )
                        }
                        if resolved_identification_certificate is not None
                        else {}
                    ),
                }
            }
        )
        if resolved_identification_certificate is not None:
            effective_query = effective_query.model_copy(
                update={
                    "metadata": {
                        **effective_query.metadata,
                        "identification_scope": self._temporal_identification_scope_snapshot(
                            effective_query,
                            resolved_identification_certificate,
                        ),
                    }
                }
            )

        panel_data: PanelObservationalData | None = None
        dynamic_data: DynamicTreatmentData | None = None
        event_process_data: EventProcessObservationalData | None = None
        if isinstance(data, EventProcessObservationalData):
            event_process_data = data
        elif isinstance(data, PanelObservationalData):
            panel_data = data
        elif isinstance(data, DynamicTreatmentData):
            dynamic_data = data
        else:
            preferred_backend = str(
                effective_query.metadata.get("preferred_backend", "linear_sde")
            ).strip()
            if preferred_backend == "event_process_weighting":
                event_process_data = EventProcessObservationalData.model_validate(data)
            else:
                try:
                    panel_data = PanelObservationalData.model_validate(data)
                except Exception:
                    try:
                        dynamic_data = DynamicTreatmentData.model_validate(data)
                    except Exception:
                        event_process_data = EventProcessObservationalData.model_validate(data)

        if (
            effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
            and (panel_data is not None or regime is not None)
        ):
            raise TemporalCompileError(
                "query_mode_conflict",
                "optimal_policy_discovery is only supported for the DTR temporal route.",
            )
        if (
            effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
            and intervention is not None
        ):
            raise TemporalCompileError(
                "query_mode_conflict",
                "optimal_policy_discovery queries do not accept a fixed intervention override.",
            )

        resolved_intervention: TemporalInterventionTrajectory | None
        intervention_ref: ArtifactRefModel | None
        intervention_resolution_source: str
        if effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY:
            resolved_intervention = None
            intervention_ref = None
            intervention_resolution_source = "policy_discovery"
        else:
            resolved_intervention, intervention_ref, intervention_resolution_source = (
                self._resolve_temporal_intervention(
                    effective_query,
                    intervention=intervention,
                )
            )

        scalar_result: Any | None = None
        policy_ref: DynamicTreatmentRegimeRef | None = None
        derived_schedule_ref: ArtifactRefModel | None = None
        if event_process_data is not None:
            trajectory = estimate_event_process_weighting_trajectory(
                event_process_data,
                effective_query,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
            )
        elif panel_data is not None:
            trajectory = estimate_structural_time_series_trajectory(
                panel_data,
                effective_query,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
            )
        elif regime is not None:
            estimator_method = str(
                effective_query.metadata.get("temporal_estimator_method", "parametric_g")
            )
            scalar_result, trajectory = estimate_g_computation_trajectory(
                dynamic_data,
                effective_query,
                regime=regime,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
                method=estimator_method,
            )
        else:
            estimator_method = str(
                effective_query.metadata.get("temporal_estimator_method", "q_learning")
            )
            scalar_result, trajectory = estimate_dtr_trajectory(
                dynamic_data,
                effective_query,
                resolved_intervention=resolved_intervention,
                identification_certificate=resolved_identification_certificate,
                intervention_contract_status=(
                    "derived_optimal_policy"
                    if effective_query.query_mode
                    is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
                    else None
                ),
                method=estimator_method,
            )
            if effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY:
                resolved_intervention = trajectory.plan.resolved_intervention

        if (
            intervention_ref is None
            and resolved_intervention is not None
            and self._artifact_store is not None
        ):
            intervention_ref = persist_temporal_intervention_trajectory(
                self._artifact_store,
                resolved_intervention,
            )
            if effective_query.query_mode is TemporalQueryMode.FIXED_INTERVENTION:
                effective_query = effective_query.model_copy(
                    update={"intervention_trajectory_ref": intervention_ref}
                )
            else:
                derived_schedule_ref = intervention_ref

        if self._artifact_store is not None:
            if (
                effective_query.query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
                and scalar_result is not None
            ):
                policy_ref = persist_dynamic_treatment_regime(
                    self._artifact_store,
                    scalar_result.optimal_regime,
                )
                derived_schedule_ref = intervention_ref
            query_ref = persist_continuous_time_query(self._artifact_store, effective_query)
            proof_payload = self.identify_continuous_time_query(
                effective_query,
                identification_certificate=resolved_identification_certificate,
                query_ref=str(query_ref.artifact_id),
            )
            local_independence_certificate_ref = None
            temporal_identification_certificate_ref = None
            proof_temporal_certificate = resolved_identification_certificate
            identification_scope = None
            try:
                payload = proof_payload.metadata.get("local_independence_certificate_ref")
                if isinstance(payload, dict):
                    local_independence_certificate_ref = ArtifactRefModel.model_validate(payload)
            except Exception:
                local_independence_certificate_ref = None
            try:
                payload = proof_payload.metadata.get("temporal_identification_certificate_ref")
                if isinstance(payload, dict):
                    temporal_identification_certificate_ref = (
                        TemporalIdentificationCertificateRef.model_validate(payload)
                    )
            except Exception:
                temporal_identification_certificate_ref = None
            try:
                payload = proof_payload.metadata.get("temporal_identification_certificate")
                if payload is not None:
                    proof_temporal_certificate = self._normalize_temporal_identification_certificate(
                        payload
                    )
            except Exception:
                pass
            payload = proof_payload.metadata.get("identification_scope")
            if isinstance(payload, dict):
                identification_scope = dict(payload)
            elif proof_temporal_certificate is not None:
                identification_scope = self._temporal_identification_scope_snapshot(
                    effective_query,
                    proof_temporal_certificate,
                )
            if identification_scope is not None:
                trajectory.metadata["identification_scope"] = identification_scope
                trajectory.metadata["identification_support_status"] = str(
                    identification_scope.get("support_status")
                )
            proof_bundle_ref = persist_proof_bundle(
                self._artifact_store,
                proof_payload,
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (
                        temporal_identification_certificate_ref,
                        "temporal_identification_certificate",
                    ),
                    (
                        local_independence_certificate_ref,
                        "local_independence_certificate",
                    ),
                ),
            )
            trajectory_ref = self._persist_temporal_payload(
                trajectory.trajectory_payload(),
                kind="ir.temporal_trajectory",
                schema_name="ir.temporal_trajectory",
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                ),
            )
            confidence_band_ref = self._persist_temporal_payload(
                trajectory.confidence_band_payload(),
                kind="ir.temporal_confidence_band",
                schema_name="ir.temporal_confidence_band",
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (trajectory_ref, "trajectory"),
                ),
            )
            if proof_temporal_certificate is not None:
                trajectory.metadata["temporal_identification_certificate"] = (
                    proof_temporal_certificate.model_dump(mode="json")
                )
            solver_diagnostics_payload = trajectory.solver_diagnostics_payload()
            diagnostics_ref = self._persist_temporal_payload(
                solver_diagnostics_payload,
                kind="ir.temporal_solver_diagnostics",
                schema_name="ir.temporal_solver_diagnostics",
                schema_version=str(solver_diagnostics_payload.get("schema_version", "1.0")),
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (trajectory_ref, "trajectory"),
                ),
            )
            rough_path_metadata = {
                key: value
                for key, value in {
                    "path_semantics": trajectory.metadata.get("path_semantics"),
                    "rough_path_certificate": trajectory.metadata.get(
                        "rough_path_certificate"
                    ),
                    "rough_path_identification_status": trajectory.metadata.get(
                        "rough_path_identification_status"
                    ),
                    "rough_path_runtime_support": trajectory.metadata.get(
                        "rough_path_runtime_support"
                    ),
                }.items()
                if value is not None
            }
            bundle = EffectTrajectoryBundle(
                query_ref=query_ref,
                trajectory_ref=trajectory_ref,
                confidence_band_ref=confidence_band_ref,
                solver_diagnostics_ref=diagnostics_ref,
                identification_certificate_ref=temporal_identification_certificate_ref,
                discretization_error=trajectory.discretization_error,
                discretization_note=trajectory.discretization_note,
                path_representation=trajectory.path_representation,
                solver_family=trajectory.solver_family,
                time_scale=effective_query.time_scale,
                interpolation_policy=effective_query.interpolation_policy,
                strategic_adaptation_mode=StrategicAdaptationMode.ABSENT,
                continuous_time_degraded=trajectory.continuous_time_degraded,
                metadata={
                    "backend_target": trajectory.plan.backend_target.value,
                    "fallback_mode": trajectory.plan.fallback_mode.value,
                    "comparator_semantics": trajectory.plan.comparator_semantics.value,
                    "scalar_result_method": getattr(scalar_result, "method", None),
                    "execution_contract_kind": effective_query.query_mode.value,
                    "intervention_contract_status": trajectory.plan.intervention_contract_status,
                    "intervention_resolution_source": intervention_resolution_source,
                    "intervention_artifact_ref": self._serialize_ref(intervention_ref),
                    "policy_artifact_ref": self._serialize_ref(policy_ref),
                    "derived_schedule_ref": self._serialize_ref(derived_schedule_ref),
                    "temporal_identification_certificate_ref": self._serialize_ref(
                        temporal_identification_certificate_ref
                    ),
                    "local_independence_certificate_ref": self._serialize_ref(
                        local_independence_certificate_ref
                    ),
                    "proof_bundle_ref": self._serialize_ref(proof_bundle_ref),
                    "proof_bundle_artifact_id": str(proof_bundle_ref.artifact_id),
                    "proof_status": proof_payload.proof_status,
                    "identification_scope": identification_scope,
                    "identification_support_status": (
                        None
                        if identification_scope is None
                        else identification_scope.get("support_status")
                    ),
                    **rough_path_metadata,
                },
            )
            bundle_ref = persist_effect_trajectory_bundle(
                self._artifact_store,
                bundle,
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (
                        temporal_identification_certificate_ref,
                        "temporal_identification_certificate",
                    ),
                    (trajectory_ref, "trajectory"),
                    (confidence_band_ref, "confidence_band"),
                    (diagnostics_ref, "solver_diagnostics"),
                ),
            )
            trajectory.effect_bundle = bundle
            trajectory.metadata["effect_bundle_artifact_id"] = str(bundle_ref.artifact_id)
            trajectory.metadata["proof_bundle_artifact_id"] = str(proof_bundle_ref.artifact_id)
            trajectory.metadata["proof_status"] = proof_payload.proof_status
        elif (
            effective_query.query_mode is TemporalQueryMode.FIXED_INTERVENTION
            and intervention is None
        ):
            raise TemporalCompileError(
                "missing_intervention_contract",
                "Engine-level temporal execution without ArtifactStore requires an explicit intervention override.",
            )

        if scalar_result is not None:
            trajectory.metadata["scalar_result_method"] = getattr(scalar_result, "method", None)
        trajectory.metadata["intervention_resolution_source"] = intervention_resolution_source
        trajectory.metadata["execution_contract_kind"] = effective_query.query_mode.value
        if (
            "identification_scope" not in trajectory.metadata
            and resolved_identification_certificate is not None
        ):
            identification_scope = self._temporal_identification_scope_snapshot(
                effective_query,
                resolved_identification_certificate,
            )
            trajectory.metadata["identification_scope"] = identification_scope
            trajectory.metadata["identification_support_status"] = str(
                identification_scope.get("support_status")
            )
            trajectory.metadata["temporal_identification_certificate"] = (
                resolved_identification_certificate.model_dump(mode="json")
            )
        if policy_ref is not None:
            trajectory.metadata["policy_artifact_id"] = str(policy_ref.artifact_id)
        if derived_schedule_ref is not None:
            trajectory.metadata["derived_schedule_artifact_id"] = str(
                derived_schedule_ref.artifact_id
            )
        return trajectory


    # ------------------------------------------------------------------
    # identify_with_missing_data
    # ------------------------------------------------------------------

    def identify_with_missing_data(
        self,
        treatment: str,
        outcome: str,
        mgraph_meta: Any,
        *,
        run_id: str | None = None,
    ) -> "IdentificationResult | NegativeCertificate":
        """Identify P(Y|do(X)) from incomplete data via M-graph recoverability.

        Routes through the Mohan-Pearl (2021) RecoverabilityTest before
        delegating to the standard identification pipeline.

        Parameters
        ----------
        treatment:   Treatment variable X.
        outcome:     Outcome variable Y.
        mgraph_meta: MGraph / MGraphMetadata with base_graph and missingness info.
        run_id:      Optional run identifier for logging.

        Returns
        -------
        IdentificationResult or NegativeCertificate
        """
        from polisyos.foundry.methods.catalog.causal.missing_data import RecoverabilityTest
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate, BlockingType

        # Step 1: test recoverability via M-graph criterion
        mgraph_dict: dict[str, Any] = {}
        if hasattr(mgraph_meta, "model_dump"):
            try:
                mgraph_dict = mgraph_meta.model_dump(mode="json")
            except Exception:
                pass
        elif isinstance(mgraph_meta, dict):
            mgraph_dict = mgraph_meta

        recoverable = True
        blocking_nodes: list[str] = []
        try:
            rec_result = RecoverabilityTest.pure_step(
                state={"mgraph_data": mgraph_dict},
                params={"query_variables": [treatment, outcome]},
            )
            status = rec_result.get("recoverability_result", {}).get("status", "recoverable")
            recoverable = status == "recoverable"
            blocking_nodes = rec_result.get("recoverability_result", {}).get("blocking_r_nodes", [])
        except Exception:
            # If recoverability test fails, fall through to standard identification
            recoverable = True

        if not recoverable:
            return NegativeCertificate(
                blocking_type=BlockingType.MISSINGNESS_NOT_RECOVERABLE,
                blocking_description=(
                    f"Query P({outcome}|do({treatment})) is not recoverable from incomplete data. "
                    f"Blocking R-nodes: {blocking_nodes}"
                ),
                quantitative_diagnostics={
                    "recoverability": {
                        "status": "not_recoverable",
                        "blocking_r_nodes": list(blocking_nodes),
                        "blocking_r_nodes_count": len(blocking_nodes),
                    }
                },
                constructive_message=(
                    "The query cannot be recovered under the given M-graph structure. "
                    "Consider collecting complete-case data or relaxing MAR/MCAR assumptions."
                ),
            )

        # Step 2: delegate to standard identification with mgraph_meta
        base_graph = getattr(mgraph_meta, "base_graph", None)
        if base_graph is None and isinstance(mgraph_meta, dict):
            base_graph = mgraph_meta.get("base_graph")
        if base_graph is None:
            base_graph = getattr(mgraph_meta, "graph", None)

        if base_graph is None:
            return NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description="mgraph_meta has no base_graph attribute.",
                constructive_message="Provide a MGraph with a valid base_graph field.",
            )

        return self.identify(
            treatment=treatment,
            outcome=outcome,
            graph=base_graph,
            mgraph_meta=mgraph_meta,
        )

    # ------------------------------------------------------------------
    # mediation_analysis
    # ------------------------------------------------------------------

    def mediation_analysis(
        self,
        data: Any,
        treatment: str,
        outcome: str,
        mediators: "list[str]",
        graph: "CausalGraphModel | None" = None,
        *,
        method: str = "semiparametric",
        run_id: str | None = None,
    ) -> Any:
        """Decompose total causal effect into direct and indirect components.

        Parameters
        ----------
        data:       Data object (dict or HTEObservationalData-compatible).
        treatment:  Treatment variable X.
        outcome:    Outcome variable Y.
        mediators:  Mediator variable(s) M.
        graph:      Optional causal graph (used for path-specific routing).
        method:     One of "semiparametric", "linear", "cde".
        run_id:     Optional run identifier for logging.

        Returns
        -------
        dict with mediation decomposition (MediationDecomposition or result dict).
        """
        self._require_estimation_readiness(
            data=data,
            treatment=treatment,
            outcome=outcome,
        )
        from polisyos.foundry.methods.catalog.causal.path_specific import (
            PathSpecificEffectEstimator,
        )
        from polisyos.foundry.methods.catalog.causal.mediation import (
            NaturalEffectEstimator,
            ControlledDirectEffectEstimator,
        )

        _method_dispatch: dict[str, type] = {
            "semiparametric": PathSpecificEffectEstimator,
            "linear": NaturalEffectEstimator,
            "cde": ControlledDirectEffectEstimator,
        }
        method_cls = _method_dispatch.get(method)
        if method_cls is None:
            raise ValueError(
                f"Unknown mediation method {method!r}. "
                f"Choose from: {sorted(_method_dispatch)}"
            )

        params: dict[str, Any] = {
            "treatment_variable": treatment,
            "outcome_variable": outcome,
            "mediator_variables": mediators,
        }

        # Build state dict from data
        state: dict[str, Any] = {}
        if isinstance(data, dict):
            state.update(data)
        elif hasattr(data, "model_dump"):
            state.update(data.model_dump())
        else:
            # Pass raw object; estimator will handle extraction
            state["data"] = data

        result = method_cls.pure_step(state, params)
        # Return whichever key is present
        return result.get("mediation_result") or result.get("result") or result

    # ------------------------------------------------------------------
    # interference_effect
    # ------------------------------------------------------------------

    def interference_effect(
        self,
        data: Any,
        treatment: str,
        outcome: str,
        *,
        method: str = "network_aipw",
        run_id: str | None = None,
    ) -> Any:
        """Estimate causal effects under network interference.

        Parameters
        ----------
        data:       NetworkCausalData or compatible object.
        treatment:  Treatment variable A.
        outcome:    Outcome variable Y.
        method:     One of "partial", "network_aipw", "spatial", "bipartite".
        run_id:     Optional run identifier.

        Returns
        -------
        NetworkInterferenceReport result dict.
        """
        self._require_estimation_readiness(
            data=data,
            treatment=treatment,
            outcome=outcome,
        )
        from polisyos.foundry.methods.catalog.causal.interference import (
            BipartiteInterferenceEstimator,
            NetworkAIPWEstimator,
            PartialInterferenceEstimator,
            SpatialInterferenceEstimator,
        )

        _method_dispatch: dict[str, type] = {
            "partial": PartialInterferenceEstimator,
            "network_aipw": NetworkAIPWEstimator,
            "spatial": SpatialInterferenceEstimator,
            "bipartite": BipartiteInterferenceEstimator,
        }
        method_cls = _method_dispatch.get(method)
        if method_cls is None:
            raise ValueError(
                f"Unknown interference method {method!r}. "
                f"Choose from: {sorted(_method_dispatch)}"
            )

        params: dict[str, Any] = {
            "treatment_variable": treatment,
            "outcome_variable": outcome,
        }

        result = method_cls.pure_step(data, params)
        return result.get("result") or result

    # ------------------------------------------------------------------
    # counterfactual_query
    # ------------------------------------------------------------------

    def counterfactual_query(
        self,
        ncm: Any,
        query: str,
        evidence: "dict[str, Any]",
        *,
        treatment: "str | None" = None,
        outcome: "str | None" = None,
        treatment_value: Any = 1,
        outcome_value: Any = 1,
        run_id: str | None = None,
    ) -> Any:
        """Execute a Layer-3 (counterfactual) query against an NCM.

        Parameters
        ----------
        ncm:             NCMSpec or NCMQueryData.
        query:           Query type: "PN", "PS", "PNS", "abduction", "twin_network", "all".
        evidence:        Observed context as {variable: value}.
        treatment:       Treatment variable X (for PN/PS/PNS queries).
        outcome:         Outcome variable Y (for PN/PS/PNS queries).
        treatment_value: Treated value x (default 1).
        outcome_value:   Outcome threshold (default 1).
        run_id:          Optional run identifier.

        Returns
        -------
        dict with query-specific result keys (pn_result, ps_result, pns_result,
        counterfactual_result, etc.).
        """
        from polisyos.foundry.methods.catalog.causal.actual_causality import ActualCausalityEngine
        from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod

        pn_queries = {"PN", "PS", "PNS", "pn", "ps", "pns", "all"}
        ncm_queries = {"abduction", "twin_network", "counterfactual"}

        # Build NCMQueryData-compatible state
        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
        if isinstance(ncm, NCMQueryData):
            state: dict[str, Any] = {"ncm_query_data": ncm}
        elif hasattr(ncm, "model_dump"):
            ncm_dict = ncm.model_dump(mode="json") if hasattr(ncm, "model_dump") else ncm
            state = {
                "ncm_query_data": {
                    "ncm_spec": ncm_dict,
                    "interventions": {},
                    "observations": evidence,
                    "metadata": {
                        "treatment_variable": treatment or "",
                        "outcome_variable": outcome or "",
                    },
                }
            }
        else:
            state = {"ncm_query_data": ncm}

        params: dict[str, Any] = {
            "treatment_variable": treatment or "",
            "outcome_variable": outcome or "",
            "treatment_value": treatment_value,
            "outcome_threshold": float(outcome_value) if isinstance(outcome_value, (int, float)) else 0.5,
        }

        query_upper = query.upper() if query not in ncm_queries else query

        if query_upper in {q.upper() for q in pn_queries}:
            # Route PN/PS/PNS/all to ActualCausalityEngine
            estimand_key = query.lower() if query.lower() in ("pn", "ps", "pns", "all") else "pns"
            params["estimand"] = estimand_key
            result = ActualCausalityEngine.pure_step(state, params)
            return result
        elif query in ncm_queries or query.lower() in ncm_queries:
            # Route to NCM counterfactual engine
            params["abduction_method"] = "linear"
            result = NCMEngineMethod.pure_step(state, params)
            return result.get("counterfactual_result") or result
        else:
            raise ValueError(
                f"Unknown counterfactual query type {query!r}. "
                f"Choose from: PN, PS, PNS, all, abduction, twin_network"
            )

    # ------------------------------------------------------------------
    # fairness_audit
    # ------------------------------------------------------------------

    def fairness_audit(
        self,
        data: Any,
        protected: str,
        outcome: str,
        graph: "CausalGraphModel | None" = None,
        *,
        method: str = "tv_decomposition",
        run_id: str | None = None,
    ) -> Any:
        """Decompose causal disparity into direct, indirect, and spurious components.

        Parameters
        ----------
        data:      FairnessObservationalData or compatible object.
        protected: Protected attribute variable A.
        outcome:   Outcome variable Y.
        graph:     Causal DAG (required for path-specific and counterfactual methods).
        method:    One of "tv_decomposition", "path_specific", "counterfactual".
        run_id:    Optional run identifier.

        Returns
        -------
        CausalFairnessReport result dict.
        """
        self._require_estimation_readiness(
            data=data,
            treatment=protected,
            outcome=outcome,
        )
        from polisyos.foundry.methods.catalog.causal.fairness import (
            CounterfactualFairnessEstimator,
            PathSpecificFairnessEstimator,
            TVFairnessDecomposer,
        )
        from polisyos.foundry.methods.catalog.causal.causal_fairness import (
            CausalFairnessEngine,
        )

        _method_dispatch: dict[str, type] = {
            "tv_decomposition": TVFairnessDecomposer,
            "path_specific": PathSpecificFairnessEstimator,
            "counterfactual": CounterfactualFairnessEstimator,
            "bounds": CausalFairnessEngine,
            "standard": CausalFairnessEngine,
        }
        method_cls = _method_dispatch.get(method)
        if method_cls is None:
            raise ValueError(
                f"Unknown fairness method {method!r}. "
                f"Choose from: {sorted(_method_dispatch)}"
            )

        params: dict[str, Any] = {
            "protected_variable": protected,
            "outcome_variable": outcome,
        }
        if graph is not None and method in {"bounds", "standard"}:
            params["graph"] = graph
            if isinstance(data, dict):
                params["mediators"] = list(data.get("mediator_names", []))
                params["confounders"] = list(data.get("feature_names", []))
            params["method"] = "bounds" if method == "bounds" else "tv_decomposition"

        result = method_cls.pure_step(data, params)
        return result.get("fairness_report") or result

    # ------------------------------------------------------------------
    # data_fusion
    # ------------------------------------------------------------------

    def data_fusion(
        self,
        data: Any,
        *,
        mode: str = "multi_study",
        run_id: str | None = None,
    ) -> Any:
        """Fuse multiple data sources to identify a target causal query.

        Parameters
        ----------
        data:   MultiStudyFusionData or compatible object.
        mode:   Fusion mode: "multi_study", "rct_plus_obs", "optimal_combine",
                "external_validity", "ctf_fusion".
        run_id: Optional run identifier.

        Returns
        -------
        FusionResult dict (varies by mode).
        """
        from polisyos.foundry.methods.catalog.causal.data_fusion import DataFusionEngine

        # Build state and params from data
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump(mode="json") if hasattr(data, "model_dump") else {}
        elif isinstance(data, dict):
            data_dict = dict(data)
        else:
            data_dict = {}

        graph = data_dict.get("graph") or getattr(data, "graph", None)
        treatment = data_dict.get("treatment", "") or getattr(data, "treatment", "")
        outcome = data_dict.get("outcome", "") or getattr(data, "outcome", "")
        datasets = data_dict.get("datasets", []) or getattr(data, "datasets", [])
        counterfactual_query = (
            data_dict.get("counterfactual_query")
            if isinstance(data_dict, dict)
            else None
        ) or getattr(data, "counterfactual_query", None)

        state: dict[str, Any] = {}
        if hasattr(graph, "model_dump"):
            state["graph"] = graph
        elif isinstance(graph, dict):
            from polisyos.ir.analytics.causal_graph import CausalGraphModel
            try:
                state["graph"] = CausalGraphModel.model_validate(graph)
            except Exception:
                state["graph"] = graph
        else:
            state["graph"] = graph

        params: dict[str, Any] = {
            "mode": mode,
            "treatment": treatment,
            "outcome": outcome,
            "datasets": datasets,
            "counterfactual_query": counterfactual_query,
        }

        result = DataFusionEngine.pure_step(state, params)
        return result.get("fusion_result") or result


def _infer_sample_size(
    data_dict: dict[str, Any] | None,
    *,
    explicit_n_obs: int | None = None,
) -> int | None:
    """Infer sample size from explicit metadata or the first array-like value."""
    if explicit_n_obs is not None:
        return int(explicit_n_obs)
    if not data_dict:
        return None
    for value in data_dict.values():
        try:
            size = int(len(value))  # type: ignore[arg-type]
        except Exception:
            continue
        if size >= 0:
            return size
    return None


def _has_fallback_arrays(
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> bool:
    """Return True when treatment and outcome arrays appear to be available."""
    if not data_dict:
        return False
    treatment_name = _singleton_query_name(treatment, "treatment")
    outcome_name = _singleton_query_name(outcome, "outcome")
    if treatment_name is None or outcome_name is None:
        return False
    treatment_candidates = (
        data_dict.get(treatment_name),
        data_dict.get("treatment"),
        data_dict.get("protected"),
    )
    outcome_candidates = (
        data_dict.get(outcome_name),
        data_dict.get("outcome"),
    )
    return any(candidate is not None for candidate in treatment_candidates) and any(
        candidate is not None for candidate in outcome_candidates
    )


def _coerce_aligned_vector(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 2 and arr.shape[1] == 1:
        arr = arr[:, 0]
    if arr.ndim != 1:
        return None
    return arr


def _coerce_aligned_covariates(value: Any, *, n_obs: int) -> np.ndarray | None:
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    elif arr.ndim > 2:
        try:
            arr = arr.reshape(arr.shape[0], -1)
        except Exception:
            return None
    if arr.ndim != 2 or arr.shape[0] != n_obs:
        return None
    return arr


def _derive_proximal_bridge_state(
    *,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
    certificate: ProximalIdentificationCertificate,
) -> dict[str, np.ndarray] | None:
    """Build the B-layer proximal estimator state from graph variable names."""

    if not data_dict:
        return None

    treatment_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, _treatment_candidate_keys(treatment))
    )
    outcome_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, _outcome_candidate_keys(outcome))
    )
    z_proxy = _coerce_aligned_vector(
        _first_non_null(data_dict, ("treatment_proxy", *certificate.proxies.treatment_inducing))
    )
    w_proxy = _coerce_aligned_vector(
        _first_non_null(data_dict, ("outcome_proxy", *certificate.proxies.outcome_inducing))
    )
    if (
        treatment_vector is None
        or outcome_vector is None
        or z_proxy is None
        or w_proxy is None
    ):
        return None
    n_obs = int(outcome_vector.shape[0])
    if any(
        vector.shape[0] != n_obs
        for vector in (treatment_vector, z_proxy, w_proxy)
    ):
        return None

    covariates = _coerce_aligned_covariates(data_dict.get("covariates"), n_obs=n_obs)
    if covariates is None:
        covariate_names = tuple(certificate.query.covariates or certificate.proxies.covariates)
        covariate_columns: list[np.ndarray] = []
        for name in covariate_names:
            column = _coerce_aligned_vector(data_dict.get(name))
            if column is None or column.shape[0] != n_obs:
                return None
            covariate_columns.append(column)
        covariates = (
            np.column_stack(covariate_columns)
            if covariate_columns
            else np.empty((n_obs, 0), dtype=float)
        )

    finite_mask = (
        np.isfinite(outcome_vector)
        & np.isfinite(treatment_vector)
        & np.isfinite(z_proxy)
        & np.isfinite(w_proxy)
        & np.isfinite(covariates).all(axis=1)
    )
    binary_mask = np.isclose(treatment_vector, 0.0) | np.isclose(treatment_vector, 1.0)
    mask = finite_mask & binary_mask
    if int(np.sum(mask)) < 60:
        return None
    return {
        "outcome": outcome_vector[mask].astype(float),
        "treatment": treatment_vector[mask].astype(float),
        "covariates": covariates[mask].astype(float),
        "treatment_proxy": z_proxy[mask].astype(float),
        "outcome_proxy": w_proxy[mask].astype(float),
    }


def _derive_proximal_mediation_state(
    *,
    data_dict: dict[str, Any] | None,
    certificate: "ProximalMediationCertificate",
) -> dict[str, np.ndarray] | None:
    """Build the proximal mediation estimator state from certificate variable roles."""

    if not data_dict:
        return None

    treatment_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, ("treatment", certificate.query.treatment))
    )
    outcome_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, ("outcome", certificate.query.outcome))
    )
    mediator_vector = _coerce_aligned_vector(
        _first_non_null(data_dict, ("mediator", certificate.query.mediator))
    )
    z_proxy = _coerce_aligned_vector(
        _first_non_null(
            data_dict,
            ("treatment_proxy", *certificate.variable_roles.get("Z", ())),
        )
    )
    w_proxy = _coerce_aligned_vector(
        _first_non_null(
            data_dict,
            ("outcome_proxy", *certificate.variable_roles.get("W", ())),
        )
    )
    if (
        treatment_vector is None
        or outcome_vector is None
        or mediator_vector is None
        or z_proxy is None
        or w_proxy is None
    ):
        return None
    n_obs = int(outcome_vector.shape[0])
    if any(
        vector.shape[0] != n_obs
        for vector in (treatment_vector, mediator_vector, z_proxy, w_proxy)
    ):
        return None

    covariates = _coerce_aligned_covariates(data_dict.get("covariates"), n_obs=n_obs)
    if covariates is None:
        covariate_names = tuple(certificate.variable_roles.get("X", ()))
        covariate_columns: list[np.ndarray] = []
        for name in covariate_names:
            column = _coerce_aligned_vector(data_dict.get(name))
            if column is None or column.shape[0] != n_obs:
                return None
            covariate_columns.append(column)
        covariates = (
            np.column_stack(covariate_columns)
            if covariate_columns
            else np.empty((n_obs, 0), dtype=float)
        )

    finite_mask = (
        np.isfinite(outcome_vector)
        & np.isfinite(treatment_vector)
        & np.isfinite(mediator_vector)
        & np.isfinite(z_proxy)
        & np.isfinite(w_proxy)
        & np.isfinite(covariates).all(axis=1)
    )
    binary_mask = np.isclose(treatment_vector, 0.0) | np.isclose(treatment_vector, 1.0)
    mask = finite_mask & binary_mask
    if int(np.sum(mask)) < 60:
        return None
    return {
        "outcome": outcome_vector[mask].astype(float),
        "treatment": treatment_vector[mask].astype(float),
        "mediator": mediator_vector[mask].astype(float),
        "covariates": covariates[mask].astype(float),
        "treatment_proxy": z_proxy[mask].astype(float),
        "outcome_proxy": w_proxy[mask].astype(float),
    }


def _resolve_graph_outcome_support(
    graph: CausalGraphModel,
    *,
    outcome: str,
) -> tuple[float, float] | None:
    metadata = dict(graph.metadata or {})
    raw = metadata.get("outcome_support")
    candidate: Any = None
    if isinstance(raw, dict):
        candidate = raw.get(outcome)
    elif raw is not None:
        candidate = raw
    if not isinstance(candidate, (tuple, list)) or len(candidate) != 2:
        return None
    try:
        lower = float(candidate[0])
        upper = float(candidate[1])
    except (TypeError, ValueError):
        return None
    if not np.isfinite(lower) or not np.isfinite(upper) or lower >= upper:
        return None
    return (lower, upper)


def _infer_proximal_path_target(
    *,
    treatment: str,
    mediator: str,
    outcome: str,
    intervention: PathIntervention,
) -> str:
    """Classify the requested path policy as NDE, NIE, or generic psi."""

    direct_path = (treatment, outcome)

    def _uses_mediator(path: tuple[str, ...]) -> bool:
        return mediator in path[1:-1]

    active_uses_mediator = any(_uses_mediator(path) for path in intervention.active_paths)
    frozen_uses_mediator = any(_uses_mediator(path) for path in intervention.frozen_paths)
    active_has_direct = direct_path in intervention.active_paths
    frozen_has_direct = direct_path in intervention.frozen_paths

    if active_uses_mediator and frozen_has_direct:
        return "nie"
    if active_has_direct and frozen_uses_mediator:
        return "nde"
    return "psi"


def _float_metrics_from_mapping(values: dict[str, Any] | None) -> dict[str, float]:
    """Best-effort float extraction for readiness metrics."""
    metrics: dict[str, float] = {}
    for key, value in (values or {}).items():
        try:
            metrics[key] = float(value)
        except (TypeError, ValueError):
            continue
    return metrics


def _unknown_data_readiness_report(
    *,
    sample_size: int | None,
    fallback_data_available: bool,
    reason: str,
    metrics: dict[str, float] | None = None,
) -> DataReadinessReport:
    """Construct a fail-closed readiness artifact when verification cannot complete."""
    resolved_metrics = dict(metrics or {})
    if sample_size is not None:
        resolved_metrics.setdefault("sample_size", float(sample_size))
    return DataReadinessReport(
        decision="unknown",
        can_compile_estimation=False,
        can_run_estimation=False,
        sample_size=sample_size,
        measurement_quality="unknown",
        fallback_data_available=fallback_data_available,
        blocking_reasons=[reason],
        warnings=["measurement_quality_unknown"],
        metrics=resolved_metrics,
    )


def _ensure_readiness_registry(registry: Any) -> Any | None:
    """Resolve a registry instance and lazily register the causal catalog when needed."""
    if registry is not None:
        return registry
    try:
        from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
        from polisyos.foundry.methods.registry import MethodRegistry
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            register_causal_methods,
        )
    except Exception:
        return None

    resolved_registry = MethodRegistry.get_instance()
    try:
        for method_class in register_causal_methods():
            try:
                resolved_registry.register(method_class)
            except MethodAlreadyRegisteredError:
                continue
    except Exception:
        return None
    return resolved_registry


def _coerce_numeric_matrix(value: Any) -> np.ndarray | None:
    """Convert arrays/lists into a finite 2D float matrix when possible."""
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float)
    except Exception:
        return None
    if arr.size == 0:
        return None
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    elif arr.ndim > 2:
        try:
            arr = arr.reshape(arr.shape[0], -1)
        except Exception:
            return None
    finite_mask = np.isfinite(arr).all(axis=1)
    if not finite_mask.any():
        return None
    arr = arr[finite_mask]
    return arr if arr.size > 0 else None


def _coerce_binary_vector(value: Any) -> np.ndarray | None:
    """Convert treatment-like inputs into a finite binary vector when possible."""
    if value is None:
        return None
    try:
        arr = np.asarray(value, dtype=float).reshape(-1)
    except Exception:
        return None
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    unique = np.unique(finite)
    if unique.size == 1:
        if np.isclose(unique[0], 0.0) or np.isclose(unique[0], 1.0):
            return finite.astype(float)
        return None
    if unique.size > 2 or not np.all(np.isclose(unique, 0.0) | np.isclose(unique, 1.0)):
        return None
    return finite.astype(float)


def _align_numeric_rows(
    matrix: np.ndarray | None,
    vector: np.ndarray | None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Align a covariate matrix and treatment vector on shared finite observations."""
    if matrix is None or vector is None:
        return None, None
    if matrix.shape[0] != vector.shape[0]:
        return None, None
    finite_mask = np.isfinite(vector) & np.isfinite(matrix).all(axis=1)
    if not finite_mask.any():
        return None, None
    aligned_matrix = matrix[finite_mask]
    aligned_vector = vector[finite_mask]
    if aligned_matrix.shape[0] == 0 or aligned_vector.size == 0:
        return None, None
    return aligned_matrix, aligned_vector


def _treatment_candidate_keys(
    treatment: str | frozenset[str],
) -> tuple[str, ...]:
    """Return likely treatment keys for direct-wrapper payloads."""
    treatment_name = _singleton_query_name(treatment, "treatment")
    candidates = [
        treatment_name,
        "treatment",
        "protected",
    ]
    return tuple(str(candidate) for candidate in candidates if candidate)


def _outcome_candidate_keys(
    outcome: str | frozenset[str],
) -> tuple[str, ...]:
    """Return likely outcome keys for direct-wrapper payloads."""
    outcome_name = _singleton_query_name(outcome, "outcome")
    candidates = [outcome_name, "outcome"]
    return tuple(str(candidate) for candidate in candidates if candidate)


def _first_non_null(
    data_dict: dict[str, Any] | None,
    candidate_keys: tuple[str, ...],
) -> Any | None:
    """Return the first non-null payload entry among candidate keys."""
    if not data_dict:
        return None
    for key in candidate_keys:
        value = data_dict.get(key)
        if value is not None:
            return value
    return None


def _derive_direct_positivity_state(
    *,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> dict[str, np.ndarray] | None:
    """Build the positivity diagnostic state for direct estimator wrappers."""
    if not data_dict:
        return None

    treatment_vector = _coerce_binary_vector(
        _first_non_null(data_dict, _treatment_candidate_keys(treatment))
    )
    if treatment_vector is None:
        treatment_sequence = data_dict.get("treatment_sequence")
        if treatment_sequence is not None:
            try:
                treatment_vector = _coerce_binary_vector(
                    np.asarray(treatment_sequence, dtype=float).reshape(-1)
                )
            except Exception:
                treatment_vector = None
    if treatment_vector is None:
        return None

    candidate_matrices = [
        _coerce_numeric_matrix(data_dict.get("covariates")),
        _coerce_numeric_matrix(data_dict.get("confounders")),
        _coerce_numeric_matrix(data_dict.get("covariate_sequence")),
    ]

    outcome_matrix = _coerce_numeric_matrix(
        _first_non_null(data_dict, _outcome_candidate_keys(outcome))
    )
    if outcome_matrix is not None:
        time_treatment = data_dict.get("time_treatment")
        if outcome_matrix.ndim == 2 and outcome_matrix.shape[1] > 1:
            try:
                boundary = int(time_treatment) if time_treatment is not None else outcome_matrix.shape[1] - 1
            except Exception:
                boundary = outcome_matrix.shape[1] - 1
            boundary = max(1, min(boundary, outcome_matrix.shape[1]))
            candidate_matrices.append(outcome_matrix[:, :boundary])

    for matrix in candidate_matrices:
        aligned_matrix, aligned_vector = _align_numeric_rows(matrix, treatment_vector)
        if aligned_matrix is not None and aligned_vector is not None:
            return {
                "X": aligned_matrix,
                "treatment": aligned_vector,
            }

    intercept = np.zeros((treatment_vector.shape[0], 1), dtype=float)
    aligned_matrix, aligned_vector = _align_numeric_rows(intercept, treatment_vector)
    if aligned_matrix is None or aligned_vector is None:
        return None
    return {
        "X": aligned_matrix,
        "treatment": aligned_vector,
    }


def _derive_direct_support_state(
    data_dict: dict[str, Any] | None,
) -> dict[str, np.ndarray] | None:
    """Build source/target covariate views when a direct wrapper carries them explicitly."""
    if not data_dict:
        return None
    source = _coerce_numeric_matrix(
        _first_non_null(
            data_dict,
            ("X_source", "source_covariates", "covariates_source"),
        )
    )
    target = _coerce_numeric_matrix(
        _first_non_null(
            data_dict,
            ("X_target", "target_covariates", "covariates_target"),
        )
    )
    if source is None or target is None:
        return None
    if source.shape[1] != target.shape[1]:
        return None
    return {
        "X_source": source,
        "X_target": target,
    }


def _execute_readiness_diagnostic(
    *,
    registry: Any,
    fqn_full: str,
    state: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve and execute a diagnostic method, returning its raw output."""
    method_cls = _resolve_method_class(registry, fqn_full)
    output = method_cls.pure_step(state, params or {})
    return output if isinstance(output, dict) else None


def _run_direct_readiness_diagnostics(
    *,
    registry: Any,
    data: Any,
    data_dict: dict[str, Any] | None,
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run concrete diagnostics for direct wrappers and report verification status."""
    del data
    diagnostic_outputs: dict[str, Any] = {}
    status: dict[str, Any] = {
        "positivity": "positivity_inputs_unavailable",
        "support": "not_requested",
        "support_required": False,
    }

    positivity_state = _derive_direct_positivity_state(
        data_dict=data_dict,
        treatment=treatment,
        outcome=outcome,
    )
    if positivity_state is not None:
        try:
            positivity_result = _execute_readiness_diagnostic(
                registry=registry,
                fqn_full="causal.diagnostics.positivity_check@1.0.0",
                state=positivity_state,
            )
        except Exception:
            positivity_result = None
            status["positivity"] = "positivity_diagnostic_failed"
        if positivity_result is not None:
            diagnostic_outputs["direct:positivity"] = positivity_result
            positivity_payload = positivity_result.get("result")
            if isinstance(positivity_payload, dict) and "passes_positivity" in positivity_payload:
                status["positivity"] = "verified"
            else:
                status["positivity"] = "positivity_diagnostic_invalid"

    support_state = _derive_direct_support_state(data_dict)
    if support_state is not None:
        status["support_required"] = True
        try:
            support_result = _execute_readiness_diagnostic(
                registry=registry,
                fqn_full="causal.diagnostics.support_mismatch@1.0.0",
                state=support_state,
            )
        except Exception:
            support_result = None
            status["support"] = "support_diagnostic_failed"
        if support_result is not None:
            diagnostic_outputs["direct:support"] = support_result
            support_payload = support_result.get("result")
            if isinstance(support_payload, dict) and "passes_support_check" in support_payload:
                status["support"] = "verified"
            else:
                status["support"] = "support_diagnostic_invalid"

    return diagnostic_outputs, status


def _extract_readiness_diagnostics(
    node_outputs: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Extract positivity/support diagnostics from executor node outputs."""
    positivity: dict[str, Any] | None = None
    support: dict[str, Any] | None = None
    for output in (node_outputs or {}).values():
        if not isinstance(output, dict):
            continue
        result_dict = output.get("result")
        if isinstance(result_dict, dict):
            if positivity is None and "passes_positivity" in result_dict:
                positivity = result_dict
            if support is None and (
                "passes_support_check" in result_dict or "support_mismatch_fraction" in result_dict
            ):
                support = result_dict
        if positivity is not None and support is not None:
            break
    return positivity, support


def _build_postrun_readiness_report(
    *,
    node_outputs: dict[str, Any] | None,
    sample_size: int | None,
    fallback_data_available: bool,
    recoverability_certificate: dict[str, Any] | None = None,
    missingness_assessment: Any | None = None,
) -> DataReadinessReport | None:
    """Build a richer readiness report from executor diagnostics when available."""
    positivity, support = _extract_readiness_diagnostics(node_outputs)
    if (
        positivity is None
        and support is None
        and sample_size is None
        and missingness_assessment is None
    ):
        return None
    return build_data_readiness_report(
        positivity=positivity,
        support_mismatch=support,
        sample_size=sample_size,
        measurement_quality="unknown",
        fallback_data_available=fallback_data_available,
        recoverability_certificate=recoverability_certificate,
        missingness_assessment=missingness_assessment,
    )


def _resolve_missingness_assessment(
    *,
    graph: Any | None,
    data_dict: dict[str, Any] | None,
    mgraph_meta: Any | None = None,
    query_variables: frozenset[str] | None = None,
    treatment: Any | None = None,
    outcome: Any | None = None,
) -> Any | None:
    """Best-effort administrative missingness assessment for M-graphs."""
    if graph is None:
        return None
    try:
        from polisyos.foundry.methods.catalog.causal.missing_data import (
            assess_administrative_missingness,
        )
        from polisyos.ir.analytics.causal_graph import GraphType
    except Exception:
        return None

    if getattr(graph, "graph_type", None) is not GraphType.MGRAPH:
        return None

    try:
        return assess_administrative_missingness(
            graph=graph,
            data=data_dict,
            mgraph_meta=mgraph_meta,
            query_variables=query_variables,
            treatment=treatment,
            outcome=outcome,
        )
    except Exception as exc:
        logger.warning("Failed to build missingness assessment for readiness: %s", exc)
        return None


def _extract_recoverability_summary(payload: Any) -> dict[str, Any] | None:
    """Extract a compact recoverability summary from results or proof artifacts."""
    def _compact(candidate: dict[str, Any]) -> dict[str, Any]:
        if "recoverability" in candidate and isinstance(candidate["recoverability"], dict):
            return _compact(dict(candidate["recoverability"]))
        if "status" not in candidate:
            return candidate
        blocking = candidate.get("blocking_r_nodes")
        repairs = candidate.get("minimal_repair_sets")
        warnings = candidate.get("warnings")
        return {
            "schema_version": candidate.get("schema_version", "1.0"),
            "target_query": candidate.get("target_query"),
            "mgraph_fingerprint": candidate.get("mgraph_fingerprint"),
            "status": candidate.get("status"),
            "recovery_scope": candidate.get("recovery_scope"),
            "blocking_r_nodes": list(blocking or []),
            "blocking_r_nodes_count": len(blocking or []),
            "minimal_repair_sets": list(repairs or []),
            "minimal_repair_set_count": len(repairs or []),
            "recommended_estimator_family": candidate.get("recommended_estimator_family"),
            "computable_functionals": list(candidate.get("computable_functionals") or []),
            "warnings": list(warnings or []),
            "completeness_regime": candidate.get("completeness_regime"),
            "theorem_family": candidate.get("theorem_family"),
        }

    candidates: list[Any] = [payload]
    if isinstance(payload, dict):
        metadata = payload.get("metadata")
        if metadata is not None:
            candidates.append(metadata)
        diagnostics = payload.get("quantitative_diagnostics")
        if diagnostics is not None:
            candidates.append(diagnostics)
    else:
        metadata = getattr(payload, "metadata", None)
        if metadata is not None:
            candidates.append(metadata)
        diagnostics = getattr(payload, "quantitative_diagnostics", None)
        if diagnostics is not None:
            candidates.append(diagnostics)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if isinstance(candidate.get("recoverability_certificate"), dict):
            return _compact(dict(candidate["recoverability_certificate"]))
        if isinstance(candidate.get("recoverability"), dict):
            return _compact(dict(candidate["recoverability"]))
        if isinstance(candidate.get("joint_decision"), dict):
            return _compact(dict(candidate["joint_decision"]))
    return None


def _query_str_from_io(
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> str:
    treatment_name = _singleton_query_name(treatment, "treatment") or "treatment"
    outcome_name = _singleton_query_name(outcome, "outcome") or "outcome"
    return f"P({outcome_name}|do({treatment_name}))"


def _coerce_mapping_like_data(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        return dict(data)
    model_dump = getattr(data, "model_dump", None)
    if callable(model_dump):
        try:
            payload = model_dump(mode="json")
            if isinstance(payload, dict):
                return payload
        except Exception:
            try:
                payload = model_dump()
                if isinstance(payload, dict):
                    return payload
            except Exception:
                return None
    raw_dict = getattr(data, "__dict__", None)
    if isinstance(raw_dict, dict):
        return dict(raw_dict)
    return None


def _make_dummy_identification_result(
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> IdentificationResult:
    """Build a minimal IdentificationResult for audit when identification failed."""
    tx = frozenset({treatment} if isinstance(treatment, str) else treatment)
    oy = frozenset({outcome} if isinstance(outcome, str) else outcome)
    tx_terms = ",".join(sorted(tx))
    oy_terms = ",".join(sorted(oy))
    return IdentificationResult(
        status=IdentificationStatus.HEDGE_FOUND,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[],
        required_distributions=[],
        query_str=f"P({oy_terms}|do({tx_terms}))",
    )


def _identification_query_str(identification_result: IdentificationResult) -> str:
    """Recover a readable query string for audit and diagnostics."""
    if identification_result.query_str:
        return identification_result.query_str
    estimand = identification_result.estimand_ast
    if estimand is not None and getattr(estimand, "query_str", ""):
        return str(estimand.query_str)
    return ""


def _attach_proof_composability_certificate(
    *,
    store: ArtifactStore,
    proof_payload: ProofBundle,
    witness_index: Any,
    graph: CausalGraphModel,
    query_str: str,
    graph_fingerprint: str,
) -> ProofBundle:
    """Persist and attach the Stage 2.2 replay certificate for an audited proof."""

    metadata = dict(proof_payload.metadata or {})
    source_fragment_id = _proof_composability_source_fragment_id(
        proof_payload,
        graph_fingerprint=graph_fingerprint,
    )
    composed_graph_ref = proof_payload.graph_ref or graph_fingerprint or None
    interface_vars = _proof_composability_interface_vars(metadata)
    proof_trace_hash = _proof_composability_trace_hash(proof_payload)
    certificate = check_proof_trace_composability(
        witness_index=witness_index,
        composed_graph=graph,
        source_fragment_id=source_fragment_id,
        checked_query=query_str or str(proof_payload.query_ref or ""),
        composed_graph_ref=composed_graph_ref,
        proof_trace_ref=proof_payload.proof_trace_ref,
        witness_index_ref=proof_payload.witness_index_ref,
        interface_vars=interface_vars,
        invalidated_by_graph_hashes=tuple(proof_payload.invalidated_by_graph_hashes),
        metadata={
            "theorem_family": proof_payload.theorem_family,
            "proof_trace_hash": proof_trace_hash,
            "source": "CausalEngine.audit",
        },
    )
    inputs = [
        InputRef(artifact_id=ref.artifact_id, role=role)
        for ref, role in (
            (proof_payload.proof_trace_ref, "proof_trace"),
            (proof_payload.witness_index_ref, "proof_witness_index"),
        )
        if ref is not None
    ]
    certificate_ref = persist_proof_composability_certificate(
        store,
        certificate,
        inputs=inputs or None,
    )
    return attach_proof_composability_to_proof_bundle(
        proof_payload,
        certificate_ref,
        certificate,
    )


def _proof_composability_source_fragment_id(
    proof_payload: ProofBundle,
    *,
    graph_fingerprint: str,
) -> str:
    metadata = dict(proof_payload.metadata or {})
    for candidate in (
        proof_payload.graph_ref,
        metadata.get("source_fragment_id"),
        metadata.get("fragment_id"),
        graph_fingerprint,
    ):
        text = str(candidate or "").strip()
        if text:
            return text
    return "unknown_source_fragment"


def _proof_composability_interface_vars(metadata: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[Any] = [
        metadata.get("interface_vars"),
        metadata.get("interface_variables"),
    ]
    for key in ("composition_certificate", "composition", "graph_composition"):
        payload = metadata.get(key)
        if isinstance(payload, dict):
            candidates.extend(
                [
                    payload.get("interface_vars"),
                    payload.get("interface_variables"),
                    payload.get("preserved_interface_vars"),
                ]
            )
    output: set[str] = set()
    for value in candidates:
        if isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set, frozenset)):
            items = list(value)
        else:
            continue
        for item in items:
            text = str(item).strip()
            if text:
                output.add(text)
    return tuple(sorted(output))


def _proof_composability_trace_hash(proof_payload: ProofBundle) -> str:
    if proof_payload.proof_trace_ref is not None:
        return str(proof_payload.proof_trace_ref.artifact_id)
    if proof_payload.proof_trace:
        return _fingerprint(list(proof_payload.proof_trace))
    metadata_trace = proof_payload.metadata.get("proof_trace")
    if isinstance(metadata_trace, (list, tuple)):
        return _fingerprint(list(metadata_trace))
    return ""


def _prepare_executor_state(node: ExecutorNode, state: dict[str, Any]) -> Any:
    """Adapt raw engine state to method-specific payload contracts when needed."""
    if node.method_fqn == "causal.structural.hybrid_scm_fit":
        return _build_scm_fit_payload(state, node.params)
    if node.method_fqn == "causal.structural.twin_network_query":
        return _build_twin_network_payload(state, node.params)
    if node.method_fqn == "causal.diagnostics.positivity_check":
        return _build_positivity_diagnostic_payload(state)
    if node.method_fqn == "causal.diagnostics.support_mismatch":
        return _build_support_mismatch_payload(state)
    return state


def _build_positivity_diagnostic_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Provide the slot names expected by positivity diagnostics."""
    payload = dict(state)
    if "X" not in payload:
        if "covariates" in state:
            payload["X"] = state["covariates"]
        elif "X_source" in state:
            payload["X"] = state["X_source"]
    if "treatment" not in payload:
        for candidate in ("T", "treatment_value"):
            if candidate in state:
                payload["treatment"] = state[candidate]
                break
    return payload


def _build_support_mismatch_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Provide source/target covariate matrices expected by support diagnostics."""
    payload = dict(state)
    if "X_source" not in payload:
        if "source_covariates" in state:
            payload["X_source"] = state["source_covariates"]
        elif "covariates" in state:
            payload["X_source"] = state["covariates"]
    if "X_target" not in payload:
        if "target_covariates" in state:
            payload["X_target"] = state["target_covariates"]
        elif "covariates" in state:
            payload["X_target"] = state["covariates"]
    return payload


def _build_scm_fit_payload(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Construct SCMFitData-compatible payload from columnar arrays."""
    graph = state.get("graph") or params.get("graph")
    if graph is None:
        raise ValueError("SCM fitting requires a graph in state or node params.")

    if "data" in state and "column_names" in state:
        payload = dict(state)
        payload.setdefault("graph", graph)
        return payload

    try:
        graph_model = (
            graph if isinstance(graph, CausalGraphModel) else CausalGraphModel.model_validate(graph)
        )
        graph_nodes = set(graph_model.nodes)
    except Exception:
        graph_nodes = set()

    column_names: list[str] = []
    columns: list[np.ndarray] = []
    expected_len: int | None = None
    for key, raw in state.items():
        if key.startswith("__") or key in {
            "graph",
            "scm_spec",
            "factual_condition",
            "treatment_variable",
            "outcome_variable",
            "factual_treatment_value",
            "counterfactual_treatment_value",
            "n_samples",
            "metadata",
        }:
            continue
        if graph_nodes and key not in graph_nodes:
            continue
        try:
            arr = np.asarray(raw, dtype=float).reshape(-1)
        except Exception:
            continue
        if arr.size < 2 or not np.isfinite(arr).all():
            continue
        if expected_len is None:
            expected_len = int(arr.size)
        if int(arr.size) != expected_len:
            continue
        column_names.append(str(key))
        columns.append(arr)

    if not columns:
        raise ValueError("Could not build SCM fitting payload from the provided data_dict.")

    payload: dict[str, Any] = {
        "data": np.column_stack(columns),
        "column_names": column_names,
        "graph": graph,
        "metadata": dict(state.get("metadata", {})),
    }
    for key in ("graph_ref", "literature_priors", "skg_snapshot_ref"):
        if key in state:
            payload[key] = state[key]
    return payload


def _build_twin_network_payload(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """Construct TwinNetworkQueryData-compatible payload from engine state."""
    payload = dict(state)
    if "scm_spec" not in payload:
        from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit

        scm_payload = _build_scm_fit_payload(state, params)
        payload.update(HybridSCMFit.pure_step(scm_payload, {}))

    scm_spec = payload["scm_spec"]
    treatment_variable = str(payload.get("treatment_variable") or params.get("treatment_variable") or "")
    outcome_variable = str(payload.get("outcome_variable") or params.get("outcome_variable") or "")
    if not treatment_variable or not outcome_variable:
        raise ValueError("Twin-network execution requires treatment and outcome variables.")

    factual_condition = payload.get("factual_condition")
    if not isinstance(factual_condition, dict) or not factual_condition:
        factual_condition = _first_observed_condition(payload, scm_spec)

    factual_treatment_value = payload.get("factual_treatment_value", params.get("factual_treatment_value"))
    if factual_treatment_value is None:
        factual_treatment_value = factual_condition.get(
            treatment_variable,
            _coerce_first_scalar(payload.get(treatment_variable), default=0.0),
        )

    counterfactual_treatment_value = payload.get(
        "counterfactual_treatment_value",
        params.get("counterfactual_treatment_value"),
    )
    if counterfactual_treatment_value is None:
        counterfactual_treatment_value = 1.0 if float(factual_treatment_value) != 1.0 else 0.0

    n_samples = int(payload.get("n_samples") or params.get("n_samples") or 2000)
    return {
        "scm_spec": scm_spec,
        "factual_condition": factual_condition,
        "treatment_variable": treatment_variable,
        "factual_treatment_value": float(factual_treatment_value),
        "counterfactual_treatment_value": float(counterfactual_treatment_value),
        "outcome_variable": outcome_variable,
        "n_samples": n_samples,
        "metadata": {
            "query_type": params.get("query_type", "counterfactual"),
        },
    }


def _first_observed_condition(state: dict[str, Any], scm_spec: Any) -> dict[str, float]:
    """Use the first observed row as the factual world when none is supplied."""
    try:
        nodes = set(scm_spec.graph.nodes)
    except Exception:
        nodes = set()

    condition: dict[str, float] = {}
    for key, raw in state.items():
        if nodes and key not in nodes:
            continue
        value = _coerce_first_scalar(raw)
        if value is not None:
            condition[str(key)] = value
    return condition


def _coerce_first_scalar(value: Any, default: float | None = None) -> float | None:
    """Best-effort conversion of scalars or vectors to a representative float."""
    if value is None:
        return default
    try:
        if np.isscalar(value):
            casted = float(value)
            return casted if np.isfinite(casted) else default
        arr = np.asarray(value, dtype=float).reshape(-1)
    except Exception:
        return default
    if arr.size == 0 or not np.isfinite(arr[0]):
        return default
    return float(arr[0])


def _is_binary_treatment_vector(values: np.ndarray) -> bool:
    """Return True when values look like a binary treatment assignment."""
    if values.size == 0:
        return False
    unique = np.unique(values[np.isfinite(values)])
    if unique.size != 2:
        return False
    return bool(np.all(np.isclose(unique, 0.0) | np.isclose(unique, 1.0)))


def _looks_discrete_vector(values: np.ndarray, *, max_levels: int) -> bool:
    """Heuristic support-size check used to keep interactive bounds tractable."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return False
    return int(np.unique(finite).size) <= int(max_levels)


def _singleton_query_name(
    value: str | frozenset[str],
    fallback_name: str,
) -> str | None:
    """Return the single variable name from a scalar-or-set query argument."""
    if isinstance(value, str):
        return value
    if len(value) != 1:
        return None
    return next(iter(value), fallback_name)


def _candidate_linear_instruments(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> tuple[str, ...]:
    """Find observed IV candidates that satisfy simple graph-based exclusion checks."""
    directed_edges = {
        (edge.src, edge.dst)
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
    }
    directed_children: dict[str, set[str]] = {}
    for src, dst in directed_edges:
        directed_children.setdefault(src, set()).add(dst)

    bidirected_pairs = {
        frozenset((edge.src, edge.dst))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
    }
    parents_of_treatment = sorted(
        src
        for src, dst in directed_edges
        if dst == treatment and src not in {treatment, outcome}
    )

    candidates: list[str] = []
    for instrument in parents_of_treatment:
        if frozenset((instrument, treatment)) in bidirected_pairs:
            continue
        if frozenset((instrument, outcome)) in bidirected_pairs:
            continue
        if (instrument, outcome) in directed_edges:
            continue
        if _has_directed_path_avoiding(
            directed_children=directed_children,
            src=instrument,
            dst=outcome,
            forbidden={treatment},
        ):
            continue
        candidates.append(instrument)
    return tuple(candidates)


def _has_directed_path_avoiding(
    *,
    directed_children: dict[str, set[str]],
    src: str,
    dst: str,
    forbidden: set[str],
) -> bool:
    """Return True if a directed path exists from src to dst without visiting forbidden nodes."""
    frontier = [src]
    seen = {src}
    while frontier:
        current = frontier.pop()
        for child in directed_children.get(current, ()):
            if child in forbidden or child in seen:
                continue
            if child == dst:
                return True
            seen.add(child)
            frontier.append(child)
    return False


def _extract_aligned_numeric_columns(
    *,
    data_dict: dict[str, Any],
    variable_names: tuple[str, ...],
) -> dict[str, np.ndarray] | None:
    """Extract numeric columns and align them on a common finite mask."""
    arrays: dict[str, np.ndarray] = {}
    expected_len: int | None = None

    for index, name in enumerate(variable_names):
        candidates = [data_dict.get(name)]
        if index == 0:
            candidates.append(data_dict.get("outcome"))
        elif index == 1:
            candidates.extend((data_dict.get("treatment"), data_dict.get("protected")))
        elif len(variable_names) == 3:
            candidates.append(data_dict.get("instrument"))

        raw = next((candidate for candidate in candidates if candidate is not None), None)
        if raw is None:
            return None
        try:
            arr = np.asarray(raw, dtype=float).reshape(-1)
        except Exception:
            return None
        if expected_len is None:
            expected_len = int(arr.size)
        if int(arr.size) != expected_len or arr.size == 0:
            return None
        arrays[name] = arr

    finite_mask = np.ones(expected_len or 0, dtype=bool)
    for arr in arrays.values():
        finite_mask &= np.isfinite(arr)
    if not finite_mask.any():
        return None
    return {
        name: arr[finite_mask]
        for name, arr in arrays.items()
    }


def _linear_iv_effect(
    *,
    y: np.ndarray,
    t: np.ndarray,
    instruments: np.ndarray,
) -> tuple[float | None, float | None, dict[str, Any]]:
    """Estimate a linear-IV rescue via Wald/2SLS using observed instruments."""
    n_obs = int(y.size)
    if n_obs != int(t.size) or n_obs != int(instruments.shape[0]) or n_obs < 5:
        return None, None, {"failure_reason": "insufficient or misaligned observations"}

    z = np.column_stack([np.ones(n_obs), instruments])
    x = np.column_stack([np.ones(n_obs), t])
    if np.linalg.matrix_rank(z) < z.shape[1]:
        return None, None, {"failure_reason": "instrument matrix is rank-deficient"}

    ztz_inv = np.linalg.pinv(z.T @ z)
    pz = z @ ztz_inv @ z.T
    xt_pz_x = x.T @ pz @ x
    if np.linalg.matrix_rank(xt_pz_x) < x.shape[1]:
        return None, None, {"failure_reason": "projected treatment design is rank-deficient"}

    beta = np.linalg.pinv(xt_pz_x) @ (x.T @ pz @ y)
    estimate = float(beta[1])
    if not np.isfinite(estimate):
        return None, None, {"failure_reason": "non-finite IV estimate"}

    residual = y - x @ beta
    sigma2 = float(np.dot(residual, residual) / max(n_obs - x.shape[1], 1))
    cov_beta = sigma2 * np.linalg.pinv(xt_pz_x)
    standard_error = float(np.sqrt(max(float(cov_beta[1, 1]), 0.0)))
    if not np.isfinite(standard_error):
        standard_error = None

    t_mean = float(np.mean(t))
    rss_reduced = float(np.dot(t - t_mean, t - t_mean))
    beta_fs = ztz_inv @ z.T @ t
    fs_residual = t - z @ beta_fs
    rss_full = float(np.dot(fs_residual, fs_residual))
    q = max(z.shape[1] - 1, 1)
    denom_df = max(n_obs - z.shape[1], 1)
    if rss_full <= 1e-12:
        first_stage_f = float("inf")
    else:
        explained = max(rss_reduced - rss_full, 0.0)
        first_stage_f = float((explained / q) / (rss_full / denom_df))

    return estimate, standard_error, {
        "first_stage_f": first_stage_f,
        "n_obs": n_obs,
        "n_instruments": int(instruments.shape[1]),
    }


def _linear_iv_rescue_result(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    data_dict: dict[str, Any],
) -> tuple[ParametricRescueResult | None, list[str]]:
    """Fast linear rescue when a graph-valid observed IV exists."""
    instruments = _candidate_linear_instruments(
        graph=graph,
        treatment=treatment,
        outcome=outcome,
    )
    if not instruments:
        return None, ["Linearity rescue: no graph-valid observed instrument was found for the direct IV/2SLS path."]

    aligned = _extract_aligned_numeric_columns(
        data_dict=data_dict,
        variable_names=(outcome, treatment, *instruments),
    )
    if aligned is None:
        return None, [
            "Linearity rescue: treatment/outcome/instrument columns were missing, non-numeric, or misaligned for the IV/2SLS path."
        ]

    y = aligned[outcome]
    t = aligned[treatment]
    z = np.column_stack([aligned[instrument] for instrument in instruments])
    estimate, standard_error, diagnostics = _linear_iv_effect(y=y, t=t, instruments=z)
    if estimate is None:
        message = diagnostics.get("failure_reason", "linear-IV solver could not produce a stable estimate")
        return None, [f"Linearity rescue: IV/2SLS path failed: {message}."]

    method = "wald_iv" if len(instruments) == 1 else "linear_2sls"
    if len(instruments) == 1:
        estimand_formula = f"Cov({instruments[0]}, {outcome}) / Cov({instruments[0]}, {treatment})"
    else:
        joined = ", ".join(instruments)
        estimand_formula = f"2SLS({outcome} ~ {treatment} | {joined})"

    warnings = [
        "Assumption-dependent result: valid only under linear structural equations, instrument exogeneity, and exclusion restriction."
    ]
    first_stage_f = diagnostics.get("first_stage_f")
    if isinstance(first_stage_f, float) and first_stage_f < 10.0:
        warnings.append(
            "Weak-instrument warning: first-stage F-statistic is below the conventional threshold of 10."
        )

    rescue = ParametricRescueResult(
        assumption="linearity",
        method=method,
        description="Point-identifying rescue under a linear SEM using a graph-validated observed instrument.",
        point_estimate=estimate,
        standard_error=standard_error,
        estimand_formula=estimand_formula,
        supporting_variables=tuple(instruments),
        diagnostics=diagnostics,
        warnings=tuple(warnings),
    )
    return rescue, [f"Added linearity rescue via {method} using instrument(s): {', '.join(instruments)}."]


def _wright_path_tracing_rescue_result(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
    data_dict: dict[str, Any],
) -> tuple[ParametricRescueResult | None, list[str]]:
    """General linear rescue via Wright/path-tracing covariance equations on an ancestor subgraph."""
    node_order, directed_edges, bidirected_edges, notes = _wright_subgraph_spec(
        graph=graph,
        treatment=treatment,
        outcome=outcome,
    )
    if node_order is None:
        return None, notes

    aligned = _extract_aligned_numeric_columns(
        data_dict=data_dict,
        variable_names=node_order,
    )
    if aligned is None:
        return None, [
            *notes,
            "Linearity rescue: ancestor-subgraph variables were missing, non-numeric, or misaligned for Wright/path tracing.",
        ]

    matrix = np.column_stack([aligned[name] for name in node_order])
    sample_cov = np.cov(matrix, rowvar=False, bias=True)
    solve = _solve_linear_path_system(
        node_order=node_order,
        directed_edges=directed_edges,
        bidirected_edges=bidirected_edges,
        sample_cov=sample_cov,
        treatment=treatment,
        outcome=outcome,
    )
    if solve is None:
        return None, [
            *notes,
            "Linearity rescue: Wright/path-tracing covariance equations were not stably identified on the ancestor subgraph.",
        ]

    effect, standard_error, diagnostics, formula = solve
    rescue = ParametricRescueResult(
        assumption="linearity",
        method="wright_path_tracing",
        description=(
            "Point-identifying rescue under a linear SEM using Wright/path-tracing covariance equations on the ancestor subgraph."
        ),
        point_estimate=effect,
        standard_error=standard_error,
        estimand_formula=formula,
        supporting_variables=node_order,
        diagnostics=diagnostics,
        warnings=(
            "Assumption-dependent result: valid only under linear structural equations and the specified mixed-graph error structure.",
            "Numerical Wright/path-tracing solve was accepted only after a stable multi-start covariance-equation fit; this is evidence of identification, not a symbolic proof.",
        ),
    )
    return rescue, [
        *notes,
        f"Added linearity rescue via wright_path_tracing on ancestor subgraph: {', '.join(node_order)}.",
    ]


def _wright_subgraph_spec(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> tuple[tuple[str, ...] | None, tuple[tuple[str, str], ...], tuple[tuple[str, str], ...], list[str]]:
    """Build the ancestor subgraph specification used by the general Wright solver."""
    directed_edges_all = tuple(
        (edge.src, edge.dst)
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
    )
    parent_map: dict[str, set[str]] = {}
    for src, dst in directed_edges_all:
        parent_map.setdefault(dst, set()).add(src)

    needed = {treatment, outcome}
    frontier = [treatment, outcome]
    while frontier:
        current = frontier.pop()
        for parent in parent_map.get(current, ()):
            if parent not in needed:
                needed.add(parent)
                frontier.append(parent)

    directed_edges = tuple(
        (src, dst)
        for src, dst in directed_edges_all
        if src in needed and dst in needed
    )
    bidirected_edges = tuple(
        tuple(sorted((edge.src, edge.dst)))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW
        and edge.mark_dst is EdgeMark.ARROW
        and edge.src in needed
        and edge.dst in needed
    )
    bidirected_edges = tuple(dict.fromkeys(bidirected_edges))

    node_order = _topological_order_from_edges(tuple(sorted(needed)), directed_edges)
    if node_order is None:
        return None, (), (), ["Linearity rescue: Wright/path tracing skipped because the ancestor subgraph is cyclic."]
    if len(node_order) > 6:
        return None, (), (), [
            "Linearity rescue: Wright/path tracing skipped because the ancestor subgraph is larger than 6 observed nodes."
        ]

    children = _children_from_directed_edges(directed_edges)
    paths = list(_enumerate_directed_paths(children, treatment, outcome))
    if not paths:
        return None, (), (), ["Linearity rescue: Wright/path tracing skipped because there is no directed treatment-to-outcome path."]

    return node_order, directed_edges, bidirected_edges, []


def _topological_order_from_edges(
    nodes: tuple[str, ...],
    directed_edges: tuple[tuple[str, str], ...],
) -> tuple[str, ...] | None:
    """Topological order for a directed acyclic edge list."""
    incoming: dict[str, set[str]] = {node: set() for node in nodes}
    children: dict[str, set[str]] = {node: set() for node in nodes}
    for src, dst in directed_edges:
        incoming.setdefault(dst, set()).add(src)
        children.setdefault(src, set()).add(dst)

    ready = sorted(node for node in nodes if not incoming.get(node))
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(children.get(node, ())):
            parents = incoming.get(child)
            if parents is None:
                continue
            parents.discard(node)
            if not parents:
                ready.append(child)
        ready.sort()

    if len(order) != len(nodes):
        return None
    return tuple(order)


def _children_from_directed_edges(
    directed_edges: tuple[tuple[str, str], ...],
) -> dict[str, tuple[str, ...]]:
    """Materialize adjacency from a directed edge list."""
    children: dict[str, list[str]] = {}
    for src, dst in directed_edges:
        children.setdefault(src, []).append(dst)
    return {src: tuple(sorted(dsts)) for src, dsts in children.items()}


def _enumerate_directed_paths(
    children: dict[str, tuple[str, ...]],
    src: str,
    dst: str,
    prefix: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], ...]:
    """Enumerate simple directed paths in a DAG."""
    path = (*prefix, src)
    if src == dst:
        return (path,)
    paths: list[tuple[str, ...]] = []
    for child in children.get(src, ()):
        if child in path:
            continue
        paths.extend(_enumerate_directed_paths(children, child, dst, path))
    return tuple(paths)


def _solve_linear_path_system(
    *,
    node_order: tuple[str, ...],
    directed_edges: tuple[tuple[str, str], ...],
    bidirected_edges: tuple[tuple[str, str], ...],
    sample_cov: np.ndarray,
    treatment: str,
    outcome: str,
) -> tuple[float, float | None, dict[str, Any], str] | None:
    """Solve linear mixed-graph covariance equations and recover the total effect."""
    from scipy.optimize import least_squares

    n_nodes = len(node_order)
    index = {node: idx for idx, node in enumerate(node_order)}
    directed_names = tuple(f"b_{src}_{dst}" for src, dst in directed_edges)
    bidirected_names = tuple(f"w_{src}_{dst}" for src, dst in bidirected_edges)
    variance_names = tuple(f"psi_{node}" for node in node_order)
    n_unknown = len(directed_names) + len(bidirected_names) + len(variance_names)
    n_equations = n_nodes * (n_nodes + 1) // 2
    if n_unknown > n_equations or n_unknown > 18:
        return None

    tri_upper = np.triu_indices(n_nodes)
    observed = sample_cov[tri_upper]
    directed_offset = 0
    bidirected_offset = len(directed_edges)
    variance_offset = bidirected_offset + len(bidirected_edges)

    def unpack(theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        b = np.zeros((n_nodes, n_nodes), dtype=float)
        omega = np.zeros((n_nodes, n_nodes), dtype=float)
        for offset, (src, dst) in enumerate(directed_edges):
            b[index[src], index[dst]] = float(theta[directed_offset + offset])
        for offset, (src, dst) in enumerate(bidirected_edges):
            value = float(theta[bidirected_offset + offset])
            i, j = index[src], index[dst]
            omega[i, j] = value
            omega[j, i] = value
        for offset, node in enumerate(node_order):
            omega[index[node], index[node]] = float(theta[variance_offset + offset] ** 2 + 1e-6)
        return b, omega

    def residual(theta: np.ndarray) -> np.ndarray:
        b, omega = unpack(theta)
        try:
            transform = np.linalg.inv(np.eye(n_nodes) - b.T)
        except np.linalg.LinAlgError:
            return np.full(observed.shape, 1e6, dtype=float)
        sigma = transform @ omega @ transform.T
        if not np.all(np.isfinite(sigma)):
            return np.full(observed.shape, 1e6, dtype=float)
        return sigma[tri_upper] - observed

    starts = [np.zeros(n_unknown, dtype=float)]
    rng = np.random.default_rng(0)
    for scale in (0.05, 0.15, 0.3, 0.6):
        starts.append(rng.standard_normal(n_unknown) * scale)

    candidates: list[tuple[float, float, float | None, np.ndarray]] = []
    for start in starts:
        result = least_squares(residual, start, method="trf", max_nfev=4000)
        resid = residual(result.x)
        rel_resid = float(np.linalg.norm(resid) / max(np.linalg.norm(observed), 1e-8))
        if not np.isfinite(rel_resid) or rel_resid > 0.12:
            continue
        b, _ = unpack(result.x)
        total_effect = _linear_total_effect(b, node_order, treatment, outcome)
        if total_effect is None or not np.isfinite(total_effect):
            continue
        jacobian = result.jac
        effect_se = _linear_effect_standard_error(
            jacobian=jacobian,
            residuals=resid,
            parameter_vector=result.x,
            unpack=unpack,
            node_order=node_order,
            treatment=treatment,
            outcome=outcome,
        )
        candidates.append((rel_resid, float(total_effect), effect_se, result.x))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best_rel_resid = candidates[0][0]
    stable = [item for item in candidates if item[0] <= max(best_rel_resid * 2.0, 0.02)]
    effect_values = np.asarray([item[1] for item in stable], dtype=float)
    if effect_values.size == 0 or float(np.std(effect_values)) > 0.05:
        return None

    best_effect = float(np.mean(effect_values))
    best_se = stable[0][2]
    best_theta = stable[0][3]
    best_b, _ = unpack(best_theta)
    diagnostics = {
        "relative_residual": best_rel_resid,
        "n_unknown_params": n_unknown,
        "n_equations": n_equations,
        "n_multistart_successes": len(stable),
        "path_formula_terms": len(_enumerate_directed_paths(_children_from_directed_edges(directed_edges), treatment, outcome)),
        "edge_coefficients": {
            f"{src}->{dst}": float(best_b[index[src], index[dst]])
            for src, dst in directed_edges
        },
    }
    formula = _wright_formula_string(
        directed_edges=directed_edges,
        treatment=treatment,
        outcome=outcome,
    )
    return best_effect, best_se, diagnostics, formula


def _linear_total_effect(
    b: np.ndarray,
    node_order: tuple[str, ...],
    treatment: str,
    outcome: str,
) -> float | None:
    """Compute total causal effect under a linear SEM from direct coefficients."""
    index = {node: idx for idx, node in enumerate(node_order)}
    if treatment not in index or outcome not in index:
        return None
    try:
        total = np.linalg.inv(np.eye(len(node_order)) - b.T) - np.eye(len(node_order))
    except np.linalg.LinAlgError:
        return None
    return float(total[index[outcome], index[treatment]])


def _linear_effect_standard_error(
    *,
    jacobian: np.ndarray,
    residuals: np.ndarray,
    parameter_vector: np.ndarray,
    unpack: Any,
    node_order: tuple[str, ...],
    treatment: str,
    outcome: str,
) -> float | None:
    """Approximate SE for the recovered total effect via numerical delta method."""
    dof = max(jacobian.shape[0] - jacobian.shape[1], 1)
    try:
        sigma2 = float(np.dot(residuals, residuals) / dof)
        cov_theta = sigma2 * np.linalg.pinv(jacobian.T @ jacobian)
    except np.linalg.LinAlgError:
        return None

    step = 1e-5
    grad = np.zeros(parameter_vector.shape[0], dtype=float)
    base_b, _ = unpack(parameter_vector)
    base_effect = _linear_total_effect(base_b, node_order, treatment, outcome)
    if base_effect is None:
        return None

    for idx in range(parameter_vector.shape[0]):
        bumped = parameter_vector.copy()
        bumped[idx] += step
        bumped_b, _ = unpack(bumped)
        bumped_effect = _linear_total_effect(bumped_b, node_order, treatment, outcome)
        if bumped_effect is None:
            return None
        grad[idx] = (bumped_effect - base_effect) / step

    variance = float(grad @ cov_theta @ grad)
    if variance < 0.0 or not np.isfinite(variance):
        return None
    return float(np.sqrt(variance))


def _wright_formula_string(
    *,
    directed_edges: tuple[tuple[str, str], ...],
    treatment: str,
    outcome: str,
) -> str:
    """Path-sum formula for the total effect in terms of structural coefficients."""
    children = _children_from_directed_edges(directed_edges)
    paths = _enumerate_directed_paths(children, treatment, outcome)
    terms: list[str] = []
    for path in paths:
        edges = tuple(zip(path, path[1:], strict=False))
        if not edges:
            continue
        terms.append("*".join(f"b_{src}_{dst}" for src, dst in edges))
    return " + ".join(terms)


def _resolve_method_class(registry: Any, fqn_full: str) -> Any:
    """Resolve a Foundry method via registry with direct-import fallbacks."""
    try:
        return registry.get(fqn_full)
    except Exception:
        bare_fqn = fqn_full.split("@", 1)[0]
        if bare_fqn == "causal.structural.twin_network_query":
            from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery

            return TwinNetworkQuery
        if bare_fqn == "causal.structural.hybrid_scm_fit":
            from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit

            return HybridSCMFit
        if bare_fqn == "causal.sensitivity.sensitivity_metrics":
            from polisyos.foundry.methods.catalog.causal.sensitivity_metrics import (
                SensitivityMetrics,
            )

            return SensitivityMetrics
        if bare_fqn == "causal.diagnostics.positivity_check":
            from polisyos.foundry.methods.catalog.causal.diagnostics import (
                PositivityDiagnostic,
            )

            return PositivityDiagnostic
        if bare_fqn == "causal.diagnostics.support_mismatch":
            from polisyos.foundry.methods.catalog.causal.diagnostics import (
                SupportMismatchDiagnostic,
            )

            return SupportMismatchDiagnostic
        raise


__all__ = ["CausalEngine"]
