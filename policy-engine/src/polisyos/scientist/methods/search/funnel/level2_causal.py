"""Level 2 — Fast Causal Plausibility.

Cost: 100 ms – 5 s.  Uses the symbolic causal engine.

Checks identifiability, adjustment-set existence, positivity risk,
fast proxy estimation, transport compatibility, and refutation
susceptibility.  Does NOT produce welfare estimates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.causal import (
    build_data_readiness_report,
    persist_data_readiness_report,
    persist_proof_bundle,
)
from polisyos.ir.analytics.dual_certificate import hydrate_bounds_bundle_with_dual_certificate
from polisyos.ir.analytics.negative_certificate import (
    NegativeCertificate,
    persist_negative_certificate,
)
from polisyos.ir.analytics.partial_identification import persist_bounds_bundle
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)

if TYPE_CHECKING:
    from polisyos.foundry.methods.catalog.causal.query_validator import (
        CausalQueryValidator,
    )

logger = get_logger(__name__)

_LEVEL2_CAUSAL_RUNTIME_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


class Level2CausalPlausibility(FunnelStage):
    """Funnel Level 2: symbolic causal plausibility screening."""

    def __init__(
        self,
        query_validator: CausalQueryValidator | None = None,
        knowledge_base: Any | None = None,
        artifact_store: Any | None = None,
        subsample_fraction: float = 0.1,
        timeout_seconds: float = 5.0,
    ):
        """
        Args:
            query_validator: Optional ``CausalQueryValidator`` for structural
                checks against graph + KB.
            knowledge_base: Optional ``DataKnowledgeBase`` for KB-gated checks.
            subsample_fraction: Fraction of data for fast positivity check.
            timeout_seconds: Hard cap on per-candidate wall time.
        """
        self._query_validator = query_validator
        self._knowledge_base = knowledge_base
        self._artifact_store = artifact_store
        self._subsample_fraction = subsample_fraction
        self._timeout_seconds = timeout_seconds
        self._last_identification_artifacts: dict[str, Any] = {}
        self._last_identification_audit_refs: list[ArtifactRef] = []

    # ------------------------------------------------------------------
    # FunnelStage interface
    # ------------------------------------------------------------------

    @property
    def stage_name(self) -> str:
        return "funnel_L2_causal"

    @property
    def fidelity_level(self) -> int:
        return 2

    @property
    def estimated_cost_usd(self) -> float:
        return 0.005

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        start = datetime.now(UTC)
        cards: list[TypedFailureCard] = []
        self._last_identification_artifacts = {}
        self._last_identification_audit_refs = []

        # Inherit cheap signal from L1 if available.
        l1_result = context.get("_funnel_L1_result")
        prev_signal = l1_result.cheap_signal if l1_result else None

        # Extract or construct causal graph.
        graph = self._resolve_graph(candidate)
        treatment, outcome = self._resolve_treatment_outcome(candidate)

        # --- Signal updates ---
        identifiability = prev_signal.causal_identifiability if prev_signal else 0.5
        positivity_risk = prev_signal.positivity_risk if prev_signal else 0.5
        transportability_risk = prev_signal.transportability_risk if prev_signal else 0.5

        # 1. Symbolic identifiability
        if graph is not None and treatment and outcome:
            id_score, id_cards = self._check_identifiability(graph, treatment, outcome, context)
            identifiability = id_score
            cards.extend(id_cards)
        causal_feedback = dict(self._last_identification_artifacts)
        context_for_validation = dict(context)
        if causal_feedback.get("estimand_ast") is not None:
            context_for_validation["_funnel_estimand_ast"] = causal_feedback["estimand_ast"]

        # 2. Admissible adjustment sets
        if graph is not None and treatment and outcome:
            adj_cards = self._check_adjustment_sets(graph, treatment, outcome)
            cards.extend(adj_cards)

        # 3. Positivity / overlap risk
        if graph is not None:
            positivity_risk = self._estimate_positivity_risk(
                candidate,
                graph,
                context,
            )

        # 4. Fast proxy estimation (association detection)
        proxy_value = self._fast_proxy_estimate(candidate, context)

        # 5. Transport / missingness compatibility
        if graph is not None:
            t_risk, t_cards = self._check_transport_compatibility(
                graph,
                candidate,
                context_for_validation,
            )
            transportability_risk = max(transportability_risk, t_risk)
            cards.extend(t_cards)

        # 6. Refutation susceptibility
        if graph is not None:
            r_cards = self._check_refutation_susceptibility(graph)
            cards.extend(r_cards)

        # --- Build updated CheapSignalVector ---
        base = prev_signal or CheapSignalVector()
        signal = CheapSignalVector(
            structural_validity=base.structural_validity,
            causal_identifiability=identifiability,
            positivity_risk=positivity_risk,
            transportability_risk=transportability_risk,
            uncertainty_prior=base.uncertainty_prior,
            policy_conflict=base.policy_conflict,
            feasibility=base.feasibility,
            expected_value_proxy=max(base.expected_value_proxy, proxy_value),
            expected_harm_proxy=base.expected_harm_proxy,
            expected_information_gain=base.expected_information_gain,
        )

        # Causal plausibility rank as objective.
        plausibility_rank = (
            0.4 * identifiability
            + 0.3 * (1.0 - positivity_risk)
            + 0.2 * (1.0 - transportability_risk)
            + 0.1 * min(1.0, proxy_value)
        )

        has_blockers = any(c.is_blocker for c in cards)
        is_promising = not has_blockers and identifiability > 0.1

        duration = (datetime.now(UTC) - start).total_seconds()

        # Build uncertainty envelope.
        envelope = UncertaintyEnvelope.unknown(source="L2 causal plausibility")
        envelope = envelope.with_update(
            UncertaintyType.STRUCTURAL,
            UncertaintyEstimate(
                level=1.0 - identifiability,
                source="symbolic identification",
                quantification_method="id_algorithm",
                is_reducible=False,
            ),
        )
        envelope = envelope.with_update(
            UncertaintyType.STATISTICAL,
            UncertaintyEstimate(
                level=positivity_risk,
                source="positivity heuristic",
                quantification_method="overlap_proxy",
                is_reducible=True,
                recommended_action="Collect more data or relax treatment definition.",
            ),
        )
        sample_size = self._infer_sample_size(context)
        fallback_data_available = (
            context.get("data") is not None
            and context.get("treatment_col") is not None
            and context.get("outcome_col") is not None
        )
        recoverability_summary = causal_feedback.get("recoverability")
        data_readiness = build_data_readiness_report(
            sample_size=sample_size,
            measurement_quality="unknown",
            fallback_data_available=fallback_data_available,
            recoverability_certificate=recoverability_summary,
        )
        causal_feedback["data_readiness_decision"] = data_readiness.decision
        causal_feedback["data_readiness_can_run_estimation"] = data_readiness.can_run_estimation
        audit_refs = list(self._last_identification_audit_refs)
        readiness_ref = self._persist_data_readiness_report(data_readiness)
        if readiness_ref is not None:
            causal_feedback["data_readiness_report_ref"] = readiness_ref.model_dump(mode="json")
            audit_refs.append(readiness_ref)

        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=plausibility_rank,
            is_promising=is_promising,
            stage_name=self.stage_name,
            duration_seconds=duration,
            uncertainty_envelope=envelope,
            cheap_signal=signal,
            failure_cards=cards,
            compute_actual_usd=duration * 0.001,  # rough estimate
            fidelity_level=self.fidelity_level,
            audit_refs=audit_refs,
            feedback={
                "identifiability": identifiability,
                "positivity_risk": positivity_risk,
                "plausibility_rank": plausibility_rank,
                **causal_feedback,
            },
        )

    # ------------------------------------------------------------------
    # Check implementations
    # ------------------------------------------------------------------

    def _check_identifiability(
        self,
        graph: Any,
        treatment: frozenset[str],
        outcome: frozenset[str],
        context: dict[str, Any],
    ) -> tuple[float, list[TypedFailureCard]]:
        """Run symbolic ID algorithm and map status to score."""
        cards: list[TypedFailureCard] = []
        try:
            from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

            engine = CausalEngine(
                registry=None,
                knowledge_base=self._knowledge_base,
                artifact_store=self._artifact_store,
            )
            raw_result = engine.identify(
                treatment=treatment,
                outcome=outcome,
                graph=graph,
            )
            _, proof_bundle, negative_certificate, bounds_bundle, dual_certificate_payload, _, _ = (
                engine._materialize_identification_artifacts(
                    raw_result,
                    graph=graph,
                    treatment=treatment,
                    outcome=outcome,
                    data_dict=self._coerce_context_data(context),
                )
            )
            if negative_certificate is not None:
                proof_ref = self._persist_proof_bundle(proof_bundle)
                negative_ref = self._persist_negative_certificate(negative_certificate)
                bounds_ref = self._persist_bounds_bundle(bounds_bundle, dual_certificate_payload)
                recoverability = self._extract_recoverability_summary(
                    negative_certificate,
                    proof_bundle,
                )
                self._last_identification_artifacts = {
                    "proof_status": proof_bundle.proof_status,
                    "proof_stratum": proof_bundle.proof_stratum,
                    "negative_certificate_blocking_type": negative_certificate.blocking_type.value,
                    "negative_certificate_summary": negative_certificate.to_summary(),
                }
                if recoverability is not None:
                    self._last_identification_artifacts["recoverability"] = recoverability
                audit_refs: list[ArtifactRef] = []
                if proof_ref is not None:
                    self._last_identification_artifacts["proof_bundle_ref"] = proof_ref.model_dump(
                        mode="json"
                    )
                    audit_refs.append(proof_ref)
                if negative_ref is not None:
                    self._last_identification_artifacts["negative_certificate_ref"] = (
                        negative_ref.model_dump(mode="json")
                    )
                    audit_refs.append(negative_ref)
                if bounds_ref is not None:
                    self._last_identification_artifacts["bounds_bundle_ref"] = (
                        bounds_ref.model_dump(mode="json")
                    )
                    audit_refs.append(bounds_ref)
                self._last_identification_audit_refs = audit_refs
                cards.append(self._failure_card_from_negative_certificate(negative_certificate))
                return 0.0, cards

            proof_ref = self._persist_proof_bundle(proof_bundle)
            estimand_ast = (
                raw_result.estimand_ast.model_dump(mode="json")
                if getattr(raw_result, "estimand_ast", None) is not None
                else None
            )
            recoverability = self._extract_recoverability_summary(proof_bundle, raw_result)
            self._last_identification_artifacts = {
                "proof_status": proof_bundle.proof_status,
                "proof_stratum": proof_bundle.proof_stratum,
                "estimand_ast": estimand_ast,
            }
            if recoverability is not None:
                self._last_identification_artifacts["recoverability"] = recoverability
            if proof_ref is not None:
                self._last_identification_artifacts["proof_bundle_ref"] = proof_ref.model_dump(
                    mode="json"
                )
                self._last_identification_audit_refs = [proof_ref]
            score_map = {
                "identified": 1.0,
                "oracle_needed": 0.3,
                "non_identified": 0.0,
            }
            score = score_map.get(proof_bundle.proof_status, 0.3)
            if proof_bundle.proof_status == "oracle_needed":
                cards.append(
                    TypedFailureCard(
                        judge_name="L2_causal",
                        failure_type="oracle_needed",
                        severity="warning",
                        description=(
                            "Identification is not fully closed under the currently available "
                            "symbolic path."
                        ),
                        uncertainty_type=UncertaintyType.STRUCTURAL,
                        remediation_hint="Provide a fully specified DAG or stronger causal evidence.",
                    )
                )
            return score, cards

        except ImportError:
            logger.debug("id_engine not available; skipping identifiability check.")
            return 0.5, []
        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            logger.warning("Identifiability check failed.", exc_info=True)
            cards.append(
                TypedFailureCard(
                    judge_name="L2_causal",
                    failure_type="id_check_error",
                    severity="warning",
                    description="Identifiability check raised an unexpected error.",
                )
            )
            return 0.3, cards

    def _persist_proof_bundle(self, proof_bundle: Any) -> ArtifactRef | None:
        if self._artifact_store is None:
            return None
        ref = persist_proof_bundle(self._artifact_store, proof_bundle)
        return _to_artifact_ref(ref)

    def _persist_negative_certificate(
        self,
        certificate: NegativeCertificate,
    ) -> ArtifactRef | None:
        if self._artifact_store is None:
            return None
        ref = persist_negative_certificate(self._artifact_store, certificate)
        return _to_artifact_ref(ref)

    def _persist_data_readiness_report(self, report: Any) -> ArtifactRef | None:
        if self._artifact_store is None:
            return None
        ref = persist_data_readiness_report(self._artifact_store, report)
        return _to_artifact_ref(ref)

    def _persist_bounds_bundle(
        self,
        payload: Any,
        certificate_payload: Any | None = None,
    ) -> ArtifactRef | None:
        if self._artifact_store is None or payload is None:
            return None
        bundle, bundle_inputs = hydrate_bounds_bundle_with_dual_certificate(
            self._artifact_store,
            payload,
            certificate_payload,
        )
        ref = persist_bounds_bundle(self._artifact_store, bundle, inputs=bundle_inputs)
        return _to_artifact_ref(ref)

    @staticmethod
    def _coerce_context_data(context: dict[str, Any]) -> dict[str, Any] | None:
        data = context.get("data")
        if isinstance(data, dict):
            return dict(data)
        model_dump = getattr(data, "model_dump", None)
        if callable(model_dump):
            try:
                payload = model_dump(mode="json")
                if isinstance(payload, dict):
                    return payload
            except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
                return None
        return None

    @staticmethod
    def _failure_card_from_negative_certificate(
        certificate: NegativeCertificate,
    ) -> TypedFailureCard:
        """Translate canonical non-identification artifact into an L2 failure card."""
        recovery = certificate.recovery_plan
        return TypedFailureCard(
            judge_name="L2_causal",
            failure_type=certificate.blocking_type.value,
            severity="blocker",
            description=certificate.blocking_description,
            uncertainty_type=UncertaintyType.STRUCTURAL,
            remediation_hint=(
                recovery.candidate_actions[0]
                if recovery is not None and recovery.candidate_actions
                else certificate.constructive_message or None
            ),
        )

    @staticmethod
    def _extract_recoverability_summary(*payloads: Any) -> dict[str, Any] | None:
        """Pull the compact Stage 12.1 recoverability summary from causal artifacts."""
        for payload in payloads:
            if payload is None:
                continue
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
                    return dict(candidate["recoverability_certificate"])
                if isinstance(candidate.get("recoverability"), dict):
                    return dict(candidate["recoverability"])
        return None

    @staticmethod
    def _infer_sample_size(context: dict[str, Any]) -> int | None:
        """Infer sample size from context data or explicit metadata."""
        explicit = context.get("sample_size")
        if explicit is not None:
            try:
                return int(explicit)
            except (TypeError, ValueError):
                pass
        data = context.get("data")
        if data is None:
            return None
        treatment_col = context.get("treatment_col")
        outcome_col = context.get("outcome_col")
        for key in (treatment_col, outcome_col):
            if key is None:
                continue
            try:
                return len(data[key])
            except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
                continue
        try:
            return len(data)
        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            return None

    def _check_adjustment_sets(
        self,
        graph: Any,
        treatment: frozenset[str],
        outcome: frozenset[str],
    ) -> list[TypedFailureCard]:
        """Check whether admissible adjustment sets exist."""
        cards: list[TypedFailureCard] = []
        try:
            from polisyos.foundry.methods.catalog.causal.admg_ops import (
                ancestors,
                m_separation,
            )

            # Simple backdoor criterion check: does conditioning on
            # non-descendants of treatment block all backdoor paths?
            # Candidate adjustment set: ancestors of outcome minus treatment.
            potential_adjustments = ancestors(graph, outcome, include_self=False) - treatment

            # Check if any subset achieves m-separation.
            # We try the full potential adjustment set first (greedy).
            if potential_adjustments:
                separated = m_separation(
                    graph,
                    x_set=treatment,
                    y_set=outcome,
                    z_set=potential_adjustments,
                )
                if not separated:
                    cards.append(
                        TypedFailureCard(
                            judge_name="L2_causal",
                            failure_type="no_adjustment_set",
                            severity="warning",
                            description=(
                                "No simple adjustment set found that blocks all backdoor paths."
                            ),
                            uncertainty_type=UncertaintyType.STRUCTURAL,
                            remediation_hint=(
                                "Consider instrumental variables or front-door criterion."
                            ),
                        )
                    )
            else:
                # No ancestors of outcome besides treatment — may be trivially
                # identified or the graph is very simple.
                pass

        except ImportError:
            logger.debug("admg_ops not available; skipping adjustment set check.")
        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            logger.warning("Adjustment set check failed.", exc_info=True)

        return cards

    def _estimate_positivity_risk(
        self,
        candidate: dict[str, Any],
        graph: Any,
        context: dict[str, Any],
    ) -> float:
        """Estimate positivity/overlap risk.

        If data is available in context, performs a fast propensity check on
        a subsample.  Otherwise falls back to a structural estimate.
        """
        # Structural estimate: more bidirected edges → higher risk.
        try:
            bidirected_count = sum(
                1
                for e in graph.edges
                if getattr(e, "edge_type", None) == "bidirected"
                or (
                    getattr(e, "source_mark", None) == "ARROW"
                    and getattr(e, "target_mark", None) == "ARROW"
                )
            )
            structural_risk = min(1.0, bidirected_count * 0.15)
        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            structural_risk = 0.5

        # Data-based check (if data available).
        data = context.get("data")
        treatment_col = context.get("treatment_col")
        if data is not None and treatment_col is not None:
            try:
                return self._fast_propensity_check(data, treatment_col)
            except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
                logger.debug("Fast propensity check failed; using structural estimate.")

        return structural_risk

    @staticmethod
    def _fast_propensity_check(
        data: Any,
        treatment_col: str,
    ) -> float:
        """Quick propensity score extremeness check on a subsample."""
        try:
            import numpy as np

            if hasattr(data, "sample"):
                sample = data.sample(frac=0.1, random_state=42)
            else:
                sample = data

            treatment = np.asarray(sample[treatment_col])
            p_treat = treatment.mean()

            # Very extreme propensity scores indicate positivity issues.
            if p_treat < 0.02 or p_treat > 0.98:
                return 0.9
            if p_treat < 0.05 or p_treat > 0.95:
                return 0.7
            if p_treat < 0.1 or p_treat > 0.9:
                return 0.4
            return 0.1

        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            return 0.5

    @staticmethod
    def _fast_proxy_estimate(
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> float:
        """Run a fast association test (difference-in-means) on a subsample.

        Returns a normalized association strength in [0, 1].
        NOT a welfare estimate — just detects whether the treatment-outcome
        association exists.
        """
        data = context.get("data")
        treatment_col = context.get("treatment_col")
        outcome_col = context.get("outcome_col")

        if data is None or treatment_col is None or outcome_col is None:
            return 0.5  # unknown

        try:
            import numpy as np

            if hasattr(data, "sample"):
                sample = data.sample(frac=0.1, random_state=42)
            else:
                sample = data

            treat = np.asarray(sample[treatment_col])
            outcome = np.asarray(sample[outcome_col])

            treated_mask = treat == 1
            if treated_mask.sum() < 5 or (~treated_mask).sum() < 5:
                return 0.3  # insufficient data

            mean_treated = outcome[treated_mask].mean()
            mean_control = outcome[~treated_mask].mean()
            pooled_std = outcome.std()

            if pooled_std == 0:
                return 0.5

            # Cohen's d as a proxy for effect presence.
            cohens_d = abs(mean_treated - mean_control) / pooled_std
            # Map to [0, 1]: d=0 → 0, d≥1 → 1.
            return float(min(1.0, cohens_d))

        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            return 0.5

    def _check_transport_compatibility(
        self,
        graph: Any,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[float, list[TypedFailureCard]]:
        """Check transport and missingness compatibility via query validator."""
        cards: list[TypedFailureCard] = []
        risk = 0.0

        if self._query_validator is None:
            return risk, cards

        # We need an estimand to validate.  If L2 identifiability produced one,
        # use it; otherwise skip.
        estimand_ast = context.get("_funnel_estimand_ast")
        if estimand_ast is None:
            return risk, cards

        try:
            report = self._query_validator.validate(
                graph=graph,
                estimand_ast=estimand_ast,
                knowledge_base=self._knowledge_base,
            )

            if not report.is_valid:
                risk = 0.8
                for err in report.errors:
                    cards.append(
                        TypedFailureCard(
                            judge_name="L2_causal",
                            failure_type=f"validation_{err.code}"
                            if hasattr(err, "code")
                            else "validation_error",
                            severity="warning",
                            description=str(err.message) if hasattr(err, "message") else str(err),
                            uncertainty_type=UncertaintyType.TRANSPORT,
                        )
                    )

            for warn in report.warnings:
                cards.append(
                    TypedFailureCard(
                        judge_name="L2_causal",
                        failure_type="validation_warning",
                        severity="info",
                        description=str(warn.message) if hasattr(warn, "message") else str(warn),
                    )
                )

        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            logger.debug("Query validation failed.", exc_info=True)

        return risk, cards

    @staticmethod
    def _check_refutation_susceptibility(
        graph: Any,
    ) -> list[TypedFailureCard]:
        """Flag structural features indicating high refutation susceptibility."""
        cards: list[TypedFailureCard] = []

        try:
            # Count bidirected edges (unmeasured confounding).
            bidirected_count = sum(
                1
                for e in graph.edges
                if getattr(e, "edge_type", None) == "bidirected"
                or (
                    getattr(e, "source_mark", None) == "ARROW"
                    and getattr(e, "target_mark", None) == "ARROW"
                )
            )

            if bidirected_count > 3:
                cards.append(
                    TypedFailureCard(
                        judge_name="L2_causal",
                        failure_type="high_unmeasured_confounding",
                        severity="warning",
                        description=(
                            f"{bidirected_count} bidirected edges suggest "
                            "substantial unmeasured confounding."
                        ),
                        uncertainty_type=UncertaintyType.STRUCTURAL,
                        remediation_hint=(
                            "Consider sensitivity analysis or collect additional covariates."
                        ),
                    )
                )

        except _LEVEL2_CAUSAL_RUNTIME_ERRORS:
            pass

        return cards

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_graph(candidate: dict[str, Any]) -> Any | None:
        """Extract or construct a CausalGraphModel from the candidate."""
        # Direct graph reference.
        graph = candidate.get("causal_graph")
        if graph is not None:
            return graph

        # Attempt to construct from semantic layer.
        semantic = candidate.get("semantic", {})
        graph_spec = semantic.get("causal_graph")
        if graph_spec is not None:
            return graph_spec

        return None

    @staticmethod
    def _resolve_treatment_outcome(
        candidate: dict[str, Any],
    ) -> tuple[frozenset[str], frozenset[str]]:
        """Extract treatment and outcome variable sets from the candidate."""
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])
        objectives = semantic.get("objectives", [])

        treatment_vars: set[str] = set()
        for iv in interventions:
            var = iv.get("variable", iv.get("treatment_variable"))
            if var:
                treatment_vars.add(var)

        outcome_vars: set[str] = set()
        for obj in objectives:
            var = obj.get("variable", obj.get("outcome_variable"))
            if var:
                outcome_vars.add(var)

        return frozenset(treatment_vars), frozenset(outcome_vars)


def _to_artifact_ref(ref: Any) -> ArtifactRef:
    return ArtifactRef.model_validate(ref.model_dump(mode="json"))
