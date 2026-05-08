"""CausalEngine mixin extracted during Phase 4.1."""

from __future__ import annotations

from . import artifacts as _artifacts

globals().update(
    {name: getattr(_artifacts, name) for name in dir(_artifacts) if not name.startswith("__")}
)


class CausalEngineEstimationMixin:
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
            recoverability_certificate=(identification_metadata.get("recoverability_certificate")),
            data_readiness=(
                data_readiness_report
                if data_readiness_report is not None
                else identification_metadata.get("data_readiness_report")
            ),
        )
        return executor_graph


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
            EstimandShape,
            classify_estimand,
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
        return dataclasses.replace(executor_graph, nodes=(*executor_graph.nodes, *new_nodes))


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
                else ["CyclicExecutionBlock did not converge within the iteration budget."]
            ),
        }
        if last_report is not None:
            block_output["report"] = last_report
        return block_output


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
        dataset_context = resolve_dataset_context(data_dict)
        flagship_ids = set(load_phase1_flagship_dataset_ids())
        government_dataset = is_government_dataset(
            dataset_context,
            flagship_dataset_ids=flagship_ids,
        )
        survey_quality_certificate, survey_quality_certificate_ref = _resolve_survey_quality_inputs(
            data_dict,
            artifact_store=self._artifact_store,
        )
        phase1_gate_summary = (
            build_phase1_gate_summary(self._artifact_store) if government_dataset else None
        )
        base_report = build_data_readiness_report(
            sample_size=sample_size,
            measurement_quality="unknown",
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_certificate,
            missingness_assessment=missingness_assessment,
            survey_quality_certificate=survey_quality_certificate,
            survey_quality_certificate_ref=survey_quality_certificate_ref,
            phase1_gate_summary=phase1_gate_summary,
        )
        base_report = _apply_government_phase1_requirements(
            base_report,
            government_dataset=government_dataset,
            survey_quality_certificate_present=survey_quality_certificate is not None,
            phase1_gate_summary=phase1_gate_summary,
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
            survey_quality_certificate=survey_quality_certificate,
            survey_quality_certificate_ref=survey_quality_certificate_ref,
            phase1_gate_summary=phase1_gate_summary,
            government_dataset=government_dataset,
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
        dataset_context = resolve_dataset_context(data_dict)
        flagship_ids = set(load_phase1_flagship_dataset_ids())
        government_dataset = is_government_dataset(
            dataset_context,
            flagship_dataset_ids=flagship_ids,
        )
        survey_quality_certificate, survey_quality_certificate_ref = _resolve_survey_quality_inputs(
            data_dict,
            artifact_store=self._artifact_store,
        )
        phase1_gate_summary = (
            build_phase1_gate_summary(self._artifact_store) if government_dataset else None
        )
        base_report = build_data_readiness_report(
            sample_size=sample_size,
            measurement_quality="unknown",
            fallback_data_available=fallback_data_available,
            survey_quality_certificate=survey_quality_certificate,
            survey_quality_certificate_ref=survey_quality_certificate_ref,
            phase1_gate_summary=phase1_gate_summary,
        )
        base_report = _apply_government_phase1_requirements(
            base_report,
            government_dataset=government_dataset,
            survey_quality_certificate_present=survey_quality_certificate is not None,
            phase1_gate_summary=phase1_gate_summary,
        )
        if base_report.decision == "block":
            return base_report
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
            survey_quality_certificate=survey_quality_certificate,
            survey_quality_certificate_ref=survey_quality_certificate_ref,
            phase1_gate_summary=phase1_gate_summary,
            government_dataset=government_dataset,
        )
        if report is not None and report.decision == "block":
            return report
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


__all__ = ["CausalEngineEstimationMixin"]
