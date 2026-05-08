"""CausalEngine mixin extracted during Phase 4.1."""

from __future__ import annotations

from . import artifacts as _artifacts

globals().update(
    {name: getattr(_artifacts, name) for name in dir(_artifacts) if not name.startswith("__")}
)


def _sync_public_algorithm_overrides() -> None:
    """Honor monkeypatches on the legacy causal_engine module/package surface."""
    import sys

    runtime = sys.modules.get(__package__)
    if runtime is None:
        return
    for name in (
        "conditional_intervention_id",
        "dynamic_intervention_id",
        "id_star_algorithm",
        "id_with_oracle_fallback",
        "idc_algorithm",
        "idc_star_algorithm",
        "multi_outcome_id",
        "mz_id_algorithm",
        "sid_algorithm",
        "tr_algorithm",
        "z_id_algorithm",
    ):
        if hasattr(runtime, name):
            globals()[name] = getattr(runtime, name)


class CausalEngineIdentificationMixin:
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

        proxy_annotation = (
            proximal_annotation
            if isinstance(proximal_annotation, ProxyAnnotation)
            else ProxyAnnotation.model_validate(proximal_annotation)
        )
        proximal_identifier = (
            proximal_spatial_identify_v1
            if proxy_annotation.spatial_proxy_specs
            else proximal_identify_v1
        )
        proximal_result = proximal_identifier(
            graph,
            CausalQuery(
                query_type=QueryType.INTERVENTIONAL,
                treatment_variable=treatment_name,
                treatment_value=1.0,
                outcome_variable=outcome_name,
            ),
            proxy_annotation,
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
        _sync_public_algorithm_overrides()
        if distribution_query is not None:
            return self.identify_distribution_law(
                query=distribution_query,
                graph=graph,
                oracle=oracle,
                dataset_ref=dataset_ref,
            )

        if counterfactual_query is not None:
            has_ctf_transport_context = (
                bool(s_nodes) or bool(source_domains) or bool(z_interventions)
            )
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
                            "recoverability_certificate": joint.recoverability.model_dump(
                                mode="json"
                            ),
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
                    trace=list(result.trace)
                    + ["identify: joint recoverability direct-query path passed"],
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

            s_var_names = frozenset(getattr(sn, "target_variable", str(sn)) for sn in s_nodes)
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
            heads = [
                path[0] for path in (*intervention.active_paths, *intervention.frozen_paths) if path
            ]
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
            blocking_description=certificate.fallback.fallback_explanation
            or "ill-typed intervention composition",
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
                "soft transport currently supports atomic node or stochastic base interventions"
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
                proof_trace=list(certificate.quantitative_diagnostics.get("proof_trace", ()) or ()),
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
                    variables_affected=tuple(
                        sorted(
                            {
                                mediator,
                                *certificate.variable_roles.get("Z", ()),
                                *certificate.variable_roles.get("W", ()),
                            }
                        )
                    ),
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
                compilation.path_policy_hash
                if compilation is not None
                else report.metadata.get("path_policy_hash")
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
                {variable for witness in report.witnesses for variable in witness.variables}
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
                        variables_affected=tuple(
                            sorted({treatment_name, outcome_name, *mediators})
                        ),
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
                        variables_affected=tuple(
                            sorted(compilation.relevant_nodes if compilation is not None else ())
                        ),
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

        witness_kinds = {item.kind for item in report.witnesses}
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
                        variables_affected=tuple(
                            sorted({treatment_name, outcome_name, *mediators})
                        ),
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
                        variables_affected=tuple(
                            sorted(compilation.relevant_nodes if compilation is not None else ())
                        ),
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
            blocking_description = "The path-specific policy is edge-inconsistent: at least one edge is both active and frozen."
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
            constructive_message=report.constructive_message
            or (
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

        base_status = str(
            interference_result.base_identification_status or interference_result.status
        )
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
                                        *(
                                            item.source
                                            for item in effective_intervention.assignments
                                        ),
                                        *(
                                            item.target
                                            for item in effective_intervention.assignments
                                        ),
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
        _sync_public_algorithm_overrides()
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
                    "recoverability": dict(getattr(result, "metadata", {}) or {}).get(
                        "recoverability_certificate"
                    ),
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
        if result.status == IdentificationStatus.ORACLE_NEEDED and (
            (source_domains and len(source_domains) > 1) or (s_nodes and z_int)
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
            from polisyos.ir.analytics.context import ContextProfile
            from polisyos.ir.analytics.transportability import SelectionDiagram, SNode

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


__all__ = ["CausalEngineIdentificationMixin"]
