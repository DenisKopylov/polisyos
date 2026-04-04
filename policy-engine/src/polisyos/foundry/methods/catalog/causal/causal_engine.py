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
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np

from polisyos.ir.canon import CanonSpec
from polisyos.ir.analytics.causal import (
    DataReadinessReport,
    ProofBundle,
    build_data_readiness_report,
    persist_data_readiness_report,
    persist_proof_bundle,
    proof_bundle_from_negative_certificate,
    proof_bundle_from_identification_result,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark
from polisyos.ir.analytics.estimand import EstimandAST
from polisyos.ir.analytics.evidence_bundle import (
    CompilationStep,
    DataProvenance,
    EstimationStep,
    EvidenceBundle,
    ProofStep as IRProofStep,
    _fingerprint,
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
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    EffectTrajectoryBundle,
    StrategicAdaptationMode,
    TemporalInterventionTrajectory,
    TemporalQueryMode,
    load_temporal_intervention_trajectory,
    persist_continuous_time_query,
    persist_dynamic_treatment_regime,
    persist_effect_trajectory_bundle,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, put_json_artifact
from polisyos.ir.refs import (
    ArtifactRefModel,
    DynamicTreatmentRegimeRef,
    TemporalInterventionTrajectoryRef,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
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
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    compile_estimand,
    CyclicExecutionBlock,
    ExecutorGraph,
    ExecutorNode,
)
from polisyos.foundry.methods.catalog.causal.admg_ops import has_directed_cycle
from polisyos.foundry.methods.catalog.causal.cyclic_id import cyclic_id_algorithm
from polisyos.foundry.methods.catalog.causal.schema_resolver import (
    SchemaResolver,
    SchemaResolutionReport,
)


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
        # Phase-5: Extended identification keyword arguments
        policy: Any | None = None,
        condition_vars: frozenset[str] | None = None,
        treatment_sequence: list[str] | None = None,
        time_points: list[int] | None = None,
        outcomes: list[str] | None = None,
        proxy_map: dict[str, str] | None = None,
        measurement_model: str = "unknown",
    ) -> IdentificationResult | NegativeCertificate | dict[str, IdentificationResult]:
        """Run identification and return IdentificationResult or NegativeCertificate.

        Routing logic (in priority order):
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
        - else → id_with_oracle_fallback
        """
        # Normalise treatment / outcome to frozenset[str]
        tx = frozenset({treatment} if isinstance(treatment, str) else treatment)
        oy = frozenset({outcome} if isinstance(outcome, str) else outcome)

        z_int = z_interventions or frozenset()
        cond = conditions or frozenset()

        try:
            # ------------------------------------------------------------------
            # Phase-5: Extended identification — check before standard routing
            # ------------------------------------------------------------------

            if counterfactual_query is not None:
                has_ctf_transport_context = bool(s_nodes) or bool(source_domains) or bool(z_int)
                if has_ctf_transport_context:
                    from polisyos.foundry.methods.catalog.causal.ctf_transport import (
                        build_ctf_selection_diagram,
                        ctf_transportability,
                    )
                    from polisyos.foundry.methods.catalog.causal.id_engine import SourceDomain

                    ctf_domains = list(source_domains or [])
                    if not ctf_domains and z_int:
                        s_var_names = frozenset(
                            getattr(sn, "target_variable", str(sn)) for sn in (s_nodes or [])
                        )
                        ctf_domains = [
                            SourceDomain(
                                domain_id="ctf_source",
                                s_nodes=s_var_names,
                                z_interventions=z_int,
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

            # 5.3  Measurement-error proxy identification
            if proxy_map is not None:
                from polisyos.foundry.methods.catalog.causal.measurement_error import (
                    identify_with_proxy,
                )
                t_str = next(iter(sorted(tx)))
                y_str = next(iter(sorted(oy)))
                return identify_with_proxy(
                    graph=graph,
                    treatment=t_str,
                    outcome=y_str,
                    proxy_map=proxy_map,
                    measurement_model=measurement_model,  # type: ignore[arg-type]
                )

            # 5.2  Multi-outcome identification
            if outcomes is not None and len(outcomes) > 0:
                return multi_outcome_id(
                    treatment=tx,
                    outcomes=outcomes,
                    graph=graph,
                    dataset_ref=dataset_ref,
                )

            # 5.1  Dynamic / sequential intervention
            if treatment_sequence is not None and len(treatment_sequence) > 0:
                t_pts = time_points or list(range(len(treatment_sequence)))
                y_str = next(iter(sorted(oy)))
                return dynamic_intervention_id(
                    treatment_sequence=treatment_sequence,
                    outcome=y_str,
                    graph=graph,
                    time_points=t_pts,
                    dataset_ref=dataset_ref,
                )

            # 5.1  Conditional intervention do(X | Z=z)
            if condition_vars is not None and len(condition_vars) > 0:
                return conditional_intervention_id(
                    treatment=tx,
                    outcome=oy,
                    condition_vars=condition_vars,
                    graph=graph,
                    dataset_ref=dataset_ref,
                )

            # 5.1  Stochastic / soft policy intervention
            if policy is not None:
                return sid_algorithm(
                    treatment=tx,
                    outcome=oy,
                    graph=graph,
                    policy=policy,
                    dataset_ref=dataset_ref,
                    s_nodes=s_nodes,
                )

            # Cyclic graphs are routed to the experimental fixed-point path.
            if has_directed_cycle(graph):
                result = cyclic_id_algorithm(
                    treatment=tx,
                    outcome=oy,
                    graph=graph,
                    scm_spec=getattr(graph, "metadata", {}).get("well_posedness_spec"),
                    dataset_ref=dataset_ref,
                )
            else:
                # ------------------------------------------------------------------
                if mgraph_meta is not None:
                    # Phase 2: M-graph two-stage full law identification
                    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
                        full_law_identify,
                    )
                    from polisyos.ir.analytics.mgraph import (
                        MGraphMetadata,
                        extract_mgraph_metadata,
                    )
                    meta = (
                        mgraph_meta
                        if isinstance(mgraph_meta, MGraphMetadata)
                        else extract_mgraph_metadata(graph)
                    )
                    result = full_law_identify(
                        treatment=tx,
                        outcome=oy,
                        graph=graph,
                        mgraph_meta=meta,
                        dataset_ref=dataset_ref,
                        oracle=oracle,
                    )
                elif source_domains and len(source_domains) > 1:
                    # G1: explicit multi-domain API — pass SourceDomain list directly
                    result = mz_id_algorithm(
                        treatment=tx,
                        outcome=oy,
                        source_domains=source_domains,
                        graph=graph,
                        dataset_ref=dataset_ref,
                    )
                elif s_nodes and z_int:
                    # Multi-source: build single SourceDomain from s_nodes
                    from polisyos.foundry.methods.catalog.causal.id_engine import SourceDomain
                    s_var_names = frozenset(
                        getattr(sn, "target_variable", str(sn)) for sn in s_nodes
                    )
                    domain = SourceDomain(
                        domain_id="combined",
                        s_nodes=s_var_names,
                        z_interventions=z_int,
                        dataset_ref=dataset_ref,
                    )
                    result = mz_id_algorithm(
                        treatment=tx,
                        outcome=oy,
                        source_domains=[domain],
                        graph=graph,
                        dataset_ref=dataset_ref,
                    )
                elif s_nodes:
                    # Build SelectionDiagram from s_nodes + graph
                    result = self._identify_with_s_nodes(tx, oy, graph, s_nodes, dataset_ref)
                elif z_int:
                    result = z_id_algorithm(
                        treatment=tx,
                        outcome=oy,
                        z_interventions=z_int,
                        graph=graph,
                        dataset_ref=dataset_ref,
                    )
                elif cond:
                    result = idc_algorithm(
                        treatment=tx,
                        outcome=oy,
                        conditions=cond,
                        graph=graph,
                        dataset_ref=dataset_ref,
                    )
                else:
                    result = id_with_oracle_fallback(
                        treatment=tx,
                        outcome=oy,
                        graph=graph,
                        oracle=oracle,
                        dataset_ref=dataset_ref,
                    )
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

        # Convert NOT_RECOVERABLE (M-graph Stage 1 failure) to NegativeCertificate
        if result.status == IdentificationStatus.NOT_RECOVERABLE:
            return NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
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

        # Quantitative diagnostics from hedge structure
        quant_diagnostics: dict[str, Any] = {
            "hedge_forest_size": len(cert.hedge_forest),
            "hedge_root_size": len(cert.hedge_root),
            "missing_distributions_count": len(required_dists),
            "identification_status": str(result.status.value),
            "algorithm_version": str(getattr(result, "algorithm_version", "") or ""),
            "proof_trace": list(getattr(result, "trace", []) or []),
        }

        return NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description=description,
            technical_detail=cert.description or "",
            required_distributions=required_dists,
            suggested_experiments=suggested,
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
                }
            }
        )

    def _materialize_identification_artifacts(
        self,
        identification_outcome: IdentificationResult | NegativeCertificate,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> tuple[IdentificationResult | None, ProofBundle, NegativeCertificate | None, BoundsBundle | None]:
        """Normalize positive and negative ID outcomes into canonical public artifacts."""
        if isinstance(identification_outcome, NegativeCertificate):
            completed = self._complete_negative_certificate(
                identification_outcome,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )
            proof_bundle = proof_bundle_from_negative_certificate(
                completed,
                query_ref=_query_str_from_io(treatment, outcome),
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
            return None, proof_bundle, completed, completed.bounds_bundle

        proof_bundle = proof_bundle_from_identification_result(identification_outcome)
        return identification_outcome, proof_bundle, None, None

    def _complete_negative_certificate(
        self,
        negative_cert: NegativeCertificate,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> NegativeCertificate:
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
        if bounds_bundle is None and y is not None and t is not None:
            bounds_bundle, bounds_notes = self._compute_generic_bounds_bundle(y=y, t=t)
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
        return updated.model_copy(
            update={"recovery_plan": recovery_plan_from_negative_certificate(updated)}
        )

    def _hedge_fallback_chain(
        self,
        negative_cert: NegativeCertificate,
        *,
        graph: CausalGraphModel,
        treatment: str | frozenset[str],
        outcome: str | frozenset[str],
        data_dict: dict[str, Any] | None,
    ) -> NegativeCertificate:
        """Attach an honest typed fallback chain for hedge-style non-identification."""
        if negative_cert.blocking_type is not BlockingType.HEDGE_STRUCTURE:
            return negative_cert

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
        if y is not None and t is not None:
            bounds_result, bounds_tier, bounds_notes = self._compute_hedge_bounds(y=y, t=t)
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

        return updated.model_copy(
            update={
                "recovery_plan": recovery_plan_from_negative_certificate(updated),
            }
        )

    def _compute_generic_bounds_bundle(
        self,
        *,
        y: np.ndarray,
        t: np.ndarray,
    ) -> tuple[BoundsBundle | None, list[str]]:
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
                return None, ["Bounds engine returned no canonical bounds bundle."]
            bundle = (
                payload
                if isinstance(payload, BoundsBundle)
                else BoundsBundle.model_validate(payload)
            )
            return (
                bundle,
                [
                    "Computed bounds-first completion via the canonical bounds engine.",
                ],
            )
        except Exception as exc:
            return None, [f"Bounds completion failed: {exc}"]

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
    ) -> tuple[Any | None, EpistemicTier | None, list[str]]:
        """Step 1: valid partial-identification bounds."""
        from polisyos.foundry.methods.catalog.causal.lp_bounds import auto_bounds

        auto_bounds_kwargs: dict[str, Any] = {}
        if not _looks_discrete_vector(t, max_levels=8) or not _looks_discrete_vector(y, max_levels=8):
            auto_bounds_kwargs = {
                "max_cardinality": 4,
                "initial_bins": 4,
                "max_bins": 8,
                "convergence_tol": 0.05,
            }

        try:
            bounds = auto_bounds(y, t, **auto_bounds_kwargs)
        except Exception as exc:
            return None, None, [f"Tier 1/2 bounds unavailable: {exc}"]

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
        return bounds, tier, notes

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

        _, executor_graph = compile_estimand(
            identification_result.estimand_ast,
            run_id=run_id or "",
            n_obs=n_obs,
            covariate_dim=covariate_dim,
            use_cross_fitting=use_cross_fitting,
            knowledge_base=self._kb,
            proof_steps=tuple(identification_result.proof_steps),
            causal_graph=graph,
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
    ) -> tuple[DataReadinessReport, dict[str, Any]]:
        """Build readiness from diagnostic nodes before any estimator executes."""
        base_report = build_data_readiness_report(
            sample_size=sample_size,
            measurement_quality="unknown",
            fallback_data_available=fallback_data_available,
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
        data_readiness_report: DataReadinessReport | Any | None = None,
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

        proof_bundle_ref = None
        bounds_bundle_ref = None
        negative_certificate_ref = None
        data_readiness_report_ref = None
        if self._artifact_store is not None:
            proof_bundle_ref = persist_proof_bundle(
                self._artifact_store,
                proof_payload,
            )
            if bounds_payload is not None:
                bounds_bundle_ref = persist_bounds_bundle(
                    self._artifact_store,
                    bounds_payload,
                )
            if data_readiness_report is not None:
                readiness_payload = (
                    data_readiness_report
                    if isinstance(data_readiness_report, DataReadinessReport)
                    else DataReadinessReport.model_validate(data_readiness_report)
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

        return EvidenceBundle(
            run_id=run_id,
            query_str=query_str,
            estimand_ast=estimand_dict,
            proof_steps=tuple(ir_steps),
            data_provenance=tuple(provenance),
            diagnostic_scores=diag,
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
        )

        sample_size = _infer_sample_size(data_dict, explicit_n_obs=n_obs)
        fallback_data_available = _has_fallback_arrays(data_dict, treatment, outcome)
        resolved_id_result, proof_bundle, negative_cert, resolved_bounds_bundle = (
            self._materialize_identification_artifacts(
                id_result,
                graph=graph,
                treatment=treatment,
                outcome=outcome,
                data_dict=data_dict,
            )
        )

        # If identification failed, return canonical impossibility artifacts.
        if negative_cert is not None:
            readiness_report = build_data_readiness_report(
                sample_size=sample_size,
                measurement_quality="unknown",
                fallback_data_available=fallback_data_available,
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
                data_readiness_report=readiness_report,
            )
            return None, bundle, negative_cert

        assert resolved_id_result is not None

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
                ),
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
                data_readiness_report=build_data_readiness_report(
                    sample_size=sample_size,
                    measurement_quality="unknown",
                    fallback_data_available=fallback_data_available,
                ),
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
            data_readiness_report=data_readiness,
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
        inputs: list[Any] | None = None,
    ) -> ArtifactRefModel:
        if self._artifact_store is None:
            raise RuntimeError("Temporal payload persistence requires an ArtifactStore")
        ref = put_json_artifact(
            self._artifact_store,
            payload,
            kind=kind,
            schema_name=schema_name,
            schema_version="1.0",
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
    ) -> Any:
        """Estimate a temporal effect trajectory and optionally persist its bundle."""

        self._require_estimation_readiness(
            data=data,
            treatment="treatment",
            outcome="outcome",
        )
        from polisyos.foundry.methods.catalog.causal.dtr import estimate_dtr_trajectory
        from polisyos.foundry.methods.catalog.causal.g_computation import (
            estimate_g_computation_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.protocols import (
            DynamicTreatmentData,
            PanelObservationalData,
        )
        from polisyos.foundry.methods.catalog.causal.structural_time_series import (
            estimate_structural_time_series_trajectory,
        )
        from polisyos.foundry.methods.catalog.causal.temporal_estimand_compiler import (
            TemporalCompileError,
        )

        effective_query = query.model_copy(
            update={
                "metadata": {
                    **query.metadata,
                    "preferred_backend": method,
                }
            }
        )

        panel_data: PanelObservationalData | None = None
        dynamic_data: DynamicTreatmentData | None = None
        if isinstance(data, PanelObservationalData):
            panel_data = data
        elif isinstance(data, DynamicTreatmentData):
            dynamic_data = data
        else:
            try:
                panel_data = PanelObservationalData.model_validate(data)
            except Exception:
                dynamic_data = DynamicTreatmentData.model_validate(data)

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
        if panel_data is not None:
            trajectory = estimate_structural_time_series_trajectory(
                panel_data,
                effective_query,
                resolved_intervention=resolved_intervention,
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
            diagnostics_ref = self._persist_temporal_payload(
                trajectory.solver_diagnostics_payload(),
                kind="ir.temporal_solver_diagnostics",
                schema_name="ir.temporal_solver_diagnostics",
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (trajectory_ref, "trajectory"),
                ),
            )
            bundle = EffectTrajectoryBundle(
                query_ref=query_ref,
                trajectory_ref=trajectory_ref,
                confidence_band_ref=confidence_band_ref,
                solver_diagnostics_ref=diagnostics_ref,
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
                },
            )
            bundle_ref = persist_effect_trajectory_bundle(
                self._artifact_store,
                bundle,
                inputs=self._temporal_input_refs(
                    (query_ref, "query"),
                    (intervention_ref, "intervention_trajectory"),
                    (policy_ref, "policy_artifact"),
                    (trajectory_ref, "trajectory"),
                    (confidence_band_ref, "confidence_band"),
                    (diagnostics_ref, "solver_diagnostics"),
                ),
            )
            trajectory.effect_bundle = bundle
            trajectory.metadata["effect_bundle_artifact_id"] = str(bundle_ref.artifact_id)
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
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description=(
                    f"Query P({outcome}|do({treatment})) is not recoverable from incomplete data. "
                    f"Blocking R-nodes: {blocking_nodes}"
                ),
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
) -> DataReadinessReport | None:
    """Build a richer readiness report from executor diagnostics when available."""
    positivity, support = _extract_readiness_diagnostics(node_outputs)
    if positivity is None and support is None and sample_size is None:
        return None
    return build_data_readiness_report(
        positivity=positivity,
        support_mismatch=support,
        sample_size=sample_size,
        measurement_quality="unknown",
        fallback_data_available=fallback_data_available,
    )


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


def _prepare_executor_state(node: ExecutorNode, state: dict[str, Any]) -> Any:
    """Adapt raw engine state to method-specific payload contracts when needed."""
    if node.method_fqn == "causal.structural.hybrid_scm_fit":
        return _build_scm_fit_payload(state, node.params)
    if node.method_fqn == "causal.structural.twin_network_query":
        return _build_twin_network_payload(state, node.params)
    return state


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
