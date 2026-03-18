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

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.estimand import EstimandAST
from polisyos.ir.analytics.evidence_bundle import (
    CompilationStep,
    DataProvenance,
    EstimationStep,
    EvidenceBundle,
    ProofStep as IRProofStep,
    _fingerprint,
)
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
    id_algorithm,
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
    ExecutorGraph,
    ExecutorNode,
)
from polisyos.foundry.methods.catalog.causal.schema_resolver import (
    SchemaResolver,
    SchemaResolutionReport,
)


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
    ) -> None:
        self._registry = registry
        self._kb = knowledge_base

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
        }

        # Try to compute Manski bounds as a partial identification fallback
        partial_bounds = None
        try:
            from polisyos.ir.analytics.partial_identification import (
                BoundMethod,
                PartialIdentificationResult,
            )
            partial_bounds = PartialIdentificationResult(
                method=BoundMethod.MANSKI,
                lower_bound=-1.0,
                upper_bound=1.0,
                confidence=0.0,
                assumptions_used=["no_assumptions_on_selection"],
                display_label="Manski Worst-Case Bounds (hedge fallback)",
            )
            quant_diagnostics["partial_bounds_computed"] = True
        except Exception:
            quant_diagnostics["partial_bounds_computed"] = False

        return NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description=description,
            technical_detail=cert.description or "",
            required_distributions=required_dists,
            suggested_experiments=suggested,
            partial_bounds=partial_bounds,
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
        )

    # ------------------------------------------------------------------
    # compile
    # ------------------------------------------------------------------

    def compile(
        self,
        identification_result: IdentificationResult,
        *,
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

            fqn_full = f"{node.method_fqn}@{node.method_version}"
            try:
                method_cls = self._registry.get(fqn_full)
                output = method_cls.pure_step(state, node.params)
                node_outputs[node_id] = output
                if "report" in output:
                    last_report = output["report"]
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

    # ------------------------------------------------------------------
    # audit
    # ------------------------------------------------------------------

    def audit(
        self,
        identification_result: IdentificationResult,
        estimation_result: Any | None,
        *,
        run_id: str,
        graph: CausalGraphModel | None = None,
        executor_graph: ExecutorGraph | None = None,
        schema_report: SchemaResolutionReport | None = None,
        node_outputs: dict[str, Any] | None = None,
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

        # -- Proof steps -------------------------------------------------
        ir_steps: list[IRProofStep] = [
            _internal_proof_step_to_ir(s)
            for s in getattr(identification_result, "proof_steps", [])
        ]

        # -- DataProvenance ----------------------------------------------
        provenance: list[DataProvenance] = []
        for dr in getattr(identification_result, "required_distributions", []):
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
        ast = identification_result.estimand_ast
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
                query_str=getattr(identification_result, "query_str", "") or "",
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
                query_str=getattr(identification_result, "query_str", "") or "",
                data_provenance=tuple(provenance),
                estimation_steps=tuple(estimation_steps),
                node_outputs=node_outputs,
            )
            quality_dict = quality_report.model_dump(mode="json")
        except Exception:
            pass

        return EvidenceBundle(
            run_id=run_id,
            query_str=getattr(identification_result, "query_str", "") or "",
            estimand_ast=estimand_dict,
            proof_steps=tuple(ir_steps),
            data_provenance=tuple(provenance),
            diagnostic_scores=diag,
            identification_status=identification_result.status.value,
            algorithm_version=getattr(identification_result, "algorithm_version", "id_v1"),
            created_at=datetime.now(timezone.utc).isoformat(),
            graph_fingerprint=graph_fp,
            estimand_fingerprint=estimand_fp,
            compilation_steps=tuple(compilation_steps),
            estimation_steps=tuple(estimation_steps),
            diagnostic_dashboard=dashboard_dict,
            quality_report=quality_dict,
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
        )

        # If identification failed, return NegativeCertificate
        if isinstance(id_result, NegativeCertificate):
            dummy_ir = _make_dummy_identification_result(treatment, outcome)
            bundle = self.audit(dummy_ir, None, run_id=run_id, schema_report=schema_report)
            return None, bundle, id_result

        # G4: validate query structure and KB feasibility before compiling
        from polisyos.foundry.methods.catalog.causal.query_validator import CausalQueryValidator
        val_report = CausalQueryValidator().validate(graph, id_result.estimand_ast, self._kb)
        if val_report.has_errors():
            neg_cert = NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description="; ".join(e.message for e in val_report.errors),
                constructive_message=(
                    "Fix graph structure or provide required data before proceeding."
                ),
            )
            dummy_ir = _make_dummy_identification_result(treatment, outcome)
            bundle = self.audit(dummy_ir, None, run_id=run_id)
            return None, bundle, neg_cert

        # 2. Optional schema resolution (now that we have the estimand)
        if df_columns is not None and df_dtypes is not None and id_result.estimand_ast is not None:
            resolver = SchemaResolver()
            schema_report = resolver.resolve(
                id_result.estimand_ast,
                df_columns=df_columns,
                df_dtypes=df_dtypes,
            )

        # 3. Compile
        try:
            executor_graph = self.compile(
                id_result,
                n_obs=n_obs,
                covariate_dim=covariate_dim,
                run_id=run_id,
                use_cross_fitting=use_cross_fitting,
            )
        except Exception as exc:
            bundle = self.audit(id_result, None, run_id=run_id, schema_report=schema_report)
            neg_cert = NegativeCertificate(
                blocking_type=BlockingType.MISSING_DISTRIBUTION,
                blocking_description=f"Compilation failed: {exc}",
                constructive_message="Check that the estimand AST is valid.",
            )
            return None, bundle, neg_cert

        # G2: inject diagnostic nodes (PositivityDiagnostic always; SupportMismatch for transport)
        executor_graph = self._inject_diagnostic_nodes(executor_graph, id_result.estimand_ast)

        # 4. Estimate (only if data and registry available)
        effect_report: Any = None
        node_outputs: dict[str, Any] = {}
        if data_dict is not None and self._registry is not None:
            try:
                effect_report, node_outputs = self.estimate(executor_graph, data_dict)
            except Exception:
                pass  # estimate is best-effort; audit still proceeds

        # 5. Audit
        bundle = self.audit(
            id_result,
            effect_report,
            run_id=run_id,
            graph=graph,
            executor_graph=executor_graph,
            schema_report=schema_report,
            node_outputs=node_outputs,
        )

        # 6. Build CausalRunSnapshot for reproducibility
        try:
            from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot

            estimand_dict: dict[str, Any] = {}
            if id_result.estimand_ast is not None:
                try:
                    estimand_dict = id_result.estimand_ast.model_dump(mode="json")
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
        from polisyos.foundry.methods.catalog.causal.fairness import (
            CounterfactualFairnessEstimator,
            PathSpecificFairnessEstimator,
            TVFairnessDecomposer,
        )

        _method_dispatch: dict[str, type] = {
            "tv_decomposition": TVFairnessDecomposer,
            "path_specific": PathSpecificFairnessEstimator,
            "counterfactual": CounterfactualFairnessEstimator,
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
                "external_validity".
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
        }

        result = DataFusionEngine.pure_step(state, params)
        return result.get("fusion_result") or result


def _make_dummy_identification_result(
    treatment: str | frozenset[str],
    outcome: str | frozenset[str],
) -> IdentificationResult:
    """Build a minimal IdentificationResult for audit when identification failed."""
    tx = frozenset({treatment} if isinstance(treatment, str) else treatment)
    oy = frozenset({outcome} if isinstance(outcome, str) else outcome)
    return IdentificationResult(
        status=IdentificationStatus.HEDGE_FOUND,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[],
        required_distributions=[],
    )


__all__ = ["CausalEngine"]
