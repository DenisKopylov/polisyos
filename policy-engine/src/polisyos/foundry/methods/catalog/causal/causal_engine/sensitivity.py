"""CausalEngine mixin extracted during Phase 4.1."""

from __future__ import annotations

from . import artifacts as _artifacts

globals().update(
    {name: getattr(_artifacts, name) for name in dir(_artifacts) if not name.startswith("__")}
)


class CausalEngineSensitivityMixin:
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
                else NegativeCertificate.auto_suggest_experiments(
                    blocking_type, missing_vars=missing_vars
                )
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
            unresolved_s_vars = frozenset(getattr(sn, "target_variable", str(sn)) for sn in s_nodes)
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
                missing_domains = [f"domain_with_experiment_on_{v}" for v in sorted(minimal)]

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
            experiments_tier=(EpistemicTier.DIAGNOSTIC_GUIDANCE if suggestions else None),
            notes=tuple(notes),
        )

        diagnostics = {
            **dict(negative_cert.quantitative_diagnostics),
            **fallback_result.to_diagnostics_dict(),
            "graph_type": graph.graph_type.value
            if hasattr(graph.graph_type, "value")
            else str(graph.graph_type),
        }
        constructive_parts = [negative_cert.constructive_message.strip()]
        if bounds_result is not None and bounds_tier is not None:
            constructive_parts.append(f"Tier 1/2 fallback produced {bounds_tier.value} bounds.")
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
        t_raw = next(
            (candidate for candidate in treatment_candidates if candidate is not None), None
        )
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
        if not _looks_discrete_vector(t, max_levels=8) or not _looks_discrete_vector(
            y, max_levels=8
        ):
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
            return None, [
                "Linearity rescue currently supports single treatment and single outcome only."
            ]

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


    def identify_with_missing_data(
        self,
        treatment: str,
        outcome: str,
        mgraph_meta: Any,
        *,
        run_id: str | None = None,
    ) -> IdentificationResult | NegativeCertificate:
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
        from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

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


    def mediation_analysis(
        self,
        data: Any,
        treatment: str,
        outcome: str,
        mediators: list[str],
        graph: CausalGraphModel | None = None,
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
        from polisyos.foundry.methods.catalog.causal.mediation import (
            ControlledDirectEffectEstimator,
            NaturalEffectEstimator,
        )
        from polisyos.foundry.methods.catalog.causal.path_specific import (
            PathSpecificEffectEstimator,
        )

        _method_dispatch: dict[str, type] = {
            "semiparametric": PathSpecificEffectEstimator,
            "linear": NaturalEffectEstimator,
            "cde": ControlledDirectEffectEstimator,
        }
        method_cls = _method_dispatch.get(method)
        if method_cls is None:
            raise ValueError(
                f"Unknown mediation method {method!r}. Choose from: {sorted(_method_dispatch)}"
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
                f"Unknown interference method {method!r}. Choose from: {sorted(_method_dispatch)}"
            )

        params: dict[str, Any] = {
            "treatment_variable": treatment,
            "outcome_variable": outcome,
        }

        result = method_cls.pure_step(data, params)
        return result.get("result") or result


    def counterfactual_query(
        self,
        ncm: Any,
        query: str,
        evidence: dict[str, Any],
        *,
        treatment: str | None = None,
        outcome: str | None = None,
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
            "outcome_threshold": float(outcome_value)
            if isinstance(outcome_value, (int, float))
            else 0.5,
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


    def fairness_audit(
        self,
        data: Any,
        protected: str,
        outcome: str,
        graph: CausalGraphModel | None = None,
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
        from polisyos.foundry.methods.catalog.causal.causal_fairness import (
            CausalFairnessEngine,
        )
        from polisyos.foundry.methods.catalog.causal.fairness import (
            CounterfactualFairnessEstimator,
            PathSpecificFairnessEstimator,
            TVFairnessDecomposer,
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
                f"Unknown fairness method {method!r}. Choose from: {sorted(_method_dispatch)}"
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
            data_dict.get("counterfactual_query") if isinstance(data_dict, dict) else None
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


__all__ = ["CausalEngineSensitivityMixin"]
