"""CausalEngine mixin extracted during Phase 4.1."""

from __future__ import annotations

from . import artifacts as _artifacts

globals().update(
    {name: getattr(_artifacts, name) for name in dir(_artifacts) if not name.startswith("__")}
)


class CausalEngineDiscoveryMixin:
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
                notes=("Validated only when the mutilated ancestral subgraph is acyclic.",),
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
                witness.warning or f"{witness.family}:{witness.method}:{witness.status.value}"
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

        blocked_reason = "Dynamic query requires a theorem-backed cyclic reduction before the proof kernel can proceed."
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
                "reduction_failed"
                if has_directed_cycle(reduced_graph)
                else "unsupported_dynamic_query",
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
        independent_censoring_checked = bool(metadata.get("independent_censoring_verified", False))
        if not independent_censoring_checked and metadata.get(
            "identification_via_reweighting", False
        ):
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
                    str(item) for item in metadata.get("conditioning_processes", ()) if str(item)
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
                policy_semantics=str(metadata.get("policy_semantics") or "intensity_replacement"),
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
                covered_families=(("causally_valid_local_independence",) if validated else ()),
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
                        item.get("justification_kind") or item.get("kind") or "delta_separation"
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
        oracle = continuous.graphical_oracle if continuous is not None else GraphicalOracleKind.MU
        process_family = (
            str(
                metadata.get("process_family")
                or (continuous.process_family if continuous is not None else "counting_process")
                or "counting_process"
            )
            .strip()
            .lower()
        )
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
            metadata.get(
                "eliminability_verified", bool(eliminable_processes or elimination_sequence)
            )
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
                item for item in markov_certificate.transformation_trace if item not in proof_trace
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
                    metadata.get("contrast_baseline")
                    or metadata.get("baseline_policy")
                    or "natural_or_pi0"
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
                latent_projection_ref=str(metadata.get("latent_projection_ref") or "").strip()
                or None,
                nodes=self._continuous_time_string_tuple(metadata.get("graph_nodes")),
                edges=self._continuous_time_graph_edges(metadata.get("graph_edges")),
                latent_nodes=self._continuous_time_string_tuple(metadata.get("latent_nodes")),
                notes=self._continuous_time_string_tuple(metadata.get("graph_notes")),
            ),
            treatment_intervention=TreatmentIntensityInterventionSpec(
                node=treatment_node,
                predictable_wrt=self._continuous_time_string_tuple(
                    metadata.get("conditioning_processes") or metadata.get("predictable_wrt")
                ),
                lambda_pi_ref=str(metadata.get("lambda_pi_ref") or "").strip() or None,
                absolute_continuity_assumed=bool(metadata.get("absolute_continuity_assumed", True)),
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
                    metadata.get("weight_components") or ("W_treatment", "W_censoring")
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
                        or (
                            "mu_separation"
                            if oracle is GraphicalOracleKind.MU
                            else "delta_separation"
                        )
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
        identification_certificate: TemporalIdentificationCertificate
        | dict[str, Any]
        | None = None,
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
            "identified_functionals": [item.value for item in certificate.identified_functionals],
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
            "tree_like_invariant_estimand": bool(notes.get("tree_like_invariant_estimand", False)),
        }


    @classmethod
    def _continuous_time_theorem_attachment(
        cls,
        query: ContinuousTimeQuery,
        certificate: TemporalIdentificationCertificate,
    ) -> DynamicSemanticsAttachment:
        metadata = dict(query.metadata or {})
        intervention_targets = cls._continuous_time_string_tuple(
            metadata.get("intervention_targets") or metadata.get("observed_intervention_channel")
        )
        supported = cls._temporal_identification_scope_is_supported(query, certificate)
        notes = [
            "Continuous-time theorem path identifies law-invariant trajectory functionals only.",
            f"intervention_semantics={certificate.intervention_semantics.value}",
            f"observability_regime={certificate.observability_regime.value}",
            f"law_object={certificate.law_object.value}",
        ]
        if (
            certificate.theorem_family
            is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1
        ):
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
                covered_families=((certificate.theorem_family.value,) if supported else ()),
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
        identification_certificate: TemporalIdentificationCertificate
        | dict[str, Any]
        | None = None,
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
                "temporal_identification_certificate": temporal_certificate.model_dump(mode="json"),
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
            metadata["local_independence_certificate_ref"] = self._serialize_ref(certificate_ref)
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


__all__ = ["CausalEngineDiscoveryMixin"]
