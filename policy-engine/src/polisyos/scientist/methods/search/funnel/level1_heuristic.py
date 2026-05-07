"""Level 1 — Cheap Domain Heuristics and Prior-Based Screening.

Cost: 1-100 ms.  Mostly deterministic, some learned components.

Produces the full ``CheapSignalVector`` that drives funnel routing.
Integrates (optionally) with historic failure patterns, domain priors,
and policy-conflict rules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.methods.search.funnel._rules import (
    check_forbidden_combinations,
    compute_conflict_score,
)
from polisyos.scientist.methods.search.funnel.types import (
    CheapSignalVector,
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
    UncertaintyEstimate,
    UncertaintyType,
)
from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context

logger = get_logger(__name__)


def _candidate_structure_hash(candidate: dict[str, Any]) -> str:
    """Stable hash of the candidate's intervention+objective structure."""
    semantic = candidate.get("semantic", {})
    interventions = semantic.get("interventions", [])
    objectives = semantic.get("objectives", [])

    # Extract structural fingerprint (types only, not parameter values).
    sig = {
        "intervention_types": sorted(
            iv.get("type", iv.get("intervention_type", "")) for iv in interventions
        ),
        "objective_names": sorted(obj.get("name", obj.get("objective", "")) for obj in objectives),
    }
    return hashlib.sha256(json.dumps(sig, sort_keys=True).encode()).hexdigest()[:16]


class Level1CheapHeuristic(FunnelStage):
    """Funnel Level 1: cheap heuristic screening producing ``CheapSignalVector``."""

    def __init__(
        self,
        failure_pattern_cache: dict[str, float] | None = None,
        domain_prior_provider: Callable[[dict[str, Any]], dict[str, float]] | None = None,
        conflict_rules: dict[str, dict[str, float]] | None = None,
        evaluated_hashes: set[str] | None = None,
        lesson_registry: Any | None = None,
    ):
        """
        Args:
            failure_pattern_cache: Maps structure-hash → historical failure rate
                (0.0 = always succeeded, 1.0 = always failed).
            domain_prior_provider: Callable taking a candidate dict and returning
                a dict with keys like ``causal_identifiability``,
                ``transportability_risk``, ``uncertainty_prior``,
                ``expected_harm_proxy``.
            conflict_rules: Override for default CONFLICT_RULES.
            evaluated_hashes: Set of previously-evaluated candidate hashes
                (for information-gain estimation).
        """
        self._failure_cache = failure_pattern_cache or {}
        self._domain_prior_provider = domain_prior_provider
        self._conflict_rules = conflict_rules
        self._evaluated_hashes = evaluated_hashes or set()
        self._lesson_registry = lesson_registry

    # ------------------------------------------------------------------
    # FunnelStage interface
    # ------------------------------------------------------------------

    @property
    def stage_name(self) -> str:
        return "funnel_L1_heuristic"

    @property
    def fidelity_level(self) -> int:
        return 1

    @property
    def estimated_cost_usd(self) -> float:
        return 0.0001

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

        # Inherit L0 structural validity from context if available.
        l0_result = context.get("_funnel_L0_result")
        structural_validity = 1.0
        if l0_result is not None:
            structural_validity = 0.0 if l0_result.has_blockers else 1.0

        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])
        objectives = semantic.get("objectives", [])
        intervention_types = [
            iv.get("type", iv.get("intervention_type", "")) for iv in interventions
        ]
        intervention_types = [t for t in intervention_types if t]

        # --- Signal computation ---

        # 1. Causal identifiability (from domain priors or default)
        causal_identifiability = 0.5

        # 2. Domain priors
        transportability_risk = 0.5
        uncertainty_prior = 0.5
        expected_harm_proxy = 0.5
        domain_priors = self._get_domain_priors(candidate)
        if domain_priors:
            causal_identifiability = domain_priors.get(
                "causal_identifiability",
                causal_identifiability,
            )
            transportability_risk = domain_priors.get(
                "transportability_risk",
                transportability_risk,
            )
            uncertainty_prior = domain_priors.get(
                "uncertainty_prior",
                uncertainty_prior,
            )
            expected_harm_proxy = domain_priors.get(
                "expected_harm_proxy",
                expected_harm_proxy,
            )

        # 3. Positivity risk — structural heuristic.
        # More confounders declared → higher positivity risk.
        causal_graph = candidate.get("causal_graph", {})
        n_confounders = len(causal_graph.get("confounders", []))
        n_covariates = len(causal_graph.get("covariates", []))
        positivity_risk = min(1.0, (n_confounders + n_covariates) * 0.1)
        # If no graph declared, remain uncertain.
        if not causal_graph:
            positivity_risk = 0.5

        # 4. Transportability risk — S-node check.
        s_nodes = causal_graph.get("s_nodes", [])
        if s_nodes:
            transportability_risk = max(
                transportability_risk,
                min(1.0, len(s_nodes) * 0.3),
            )

        # 5. Policy conflict.
        conflict_score = compute_conflict_score(intervention_types)
        # Also check forbidden combinations (should have been caught by L0
        # but may still arrive if L0 was skipped).
        forbidden = check_forbidden_combinations(intervention_types)
        if forbidden:
            conflict_score = max(conflict_score, 1.0)
            for a, b in forbidden:
                cards.append(
                    TypedFailureCard(
                        judge_name="L1_heuristic",
                        failure_type="forbidden_combination",
                        severity="blocker",
                        description=f"Forbidden combination: '{a}' + '{b}'.",
                    )
                )

        # 6. Feasibility — composite of structure + mechanism coverage.
        feasibility = 1.0
        if not interventions:
            feasibility = 0.0
        elif not objectives:
            feasibility *= 0.5
        if structural_validity < 0.5:
            feasibility *= 0.3

        # 7. Expected value proxy — from failure pattern cache.
        structure_hash = _candidate_structure_hash(candidate)
        hist_failure_rate = self._failure_cache.get(structure_hash)
        if hist_failure_rate is not None:
            expected_value_proxy = 1.0 - hist_failure_rate
            if hist_failure_rate > 0.9:
                cards.append(
                    TypedFailureCard(
                        judge_name="L1_heuristic",
                        failure_type="historic_failure_pattern",
                        severity="warning",
                        description=(
                            f"Structure hash {structure_hash} has "
                            f"{hist_failure_rate:.0%} historic failure rate."
                        ),
                        remediation_hint="Consider varying the intervention structure.",
                    )
                )
        else:
            expected_value_proxy = 0.5

        # 8. Expected information gain — lower if similar candidates evaluated.
        if structure_hash in self._evaluated_hashes:
            expected_information_gain = 0.2
        else:
            expected_information_gain = 0.8

        lesson_hits = self._query_lessons(
            context.get("lesson_registry", self._lesson_registry),
            candidate=candidate,
            context=context,
            stage_name=self.stage_name,
            candidate_hash=structure_hash,
            intervention_types=intervention_types,
            objectives=objectives,
        )
        if lesson_hits:
            weighted_mass = sum(
                max(0.2, float(getattr(lesson, "provenance_weight", 1.0) or 0.0))
                for lesson in lesson_hits
            )
            avg_confidence = sum(
                float(lesson.confidence)
                * max(0.2, float(getattr(lesson, "provenance_weight", 1.0) or 0.0))
                for lesson in lesson_hits
            ) / max(weighted_mass, 1e-6)
            prevalence = min(1.0, weighted_mass / 3.0)
            expected_value_proxy = max(
                0.0,
                expected_value_proxy - (0.25 * prevalence * avg_confidence),
            )
            expected_information_gain = max(
                0.2,
                expected_information_gain - (0.35 * prevalence),
            )
            cards.append(
                TypedFailureCard(
                    judge_name="L1_heuristic",
                    failure_type="lesson_registry_match",
                    severity="warning",
                    description=(
                        f"Matched {len(lesson_hits)} prior lesson(s) for this candidate pattern."
                    ),
                    remediation_hint=lesson_hits[0].remediation_hint,
                    metadata={
                        "matched_lesson_ids": [lesson.lesson_id for lesson in lesson_hits],
                    },
                )
            )

        # --- Build CheapSignalVector ---
        signal = CheapSignalVector(
            structural_validity=structural_validity,
            causal_identifiability=causal_identifiability,
            positivity_risk=positivity_risk,
            transportability_risk=transportability_risk,
            uncertainty_prior=uncertainty_prior,
            policy_conflict=conflict_score,
            feasibility=feasibility,
            expected_value_proxy=expected_value_proxy,
            expected_harm_proxy=expected_harm_proxy,
            expected_information_gain=expected_information_gain,
        )

        # Routing decision
        routing = signal.routing_decision()
        is_promising = routing != "reject"

        if not is_promising:
            logger.debug(
                "L1 rejected candidate (hash=%s): routing=%s, signal=%s",
                structure_hash,
                routing,
                signal,
            )

        duration = (datetime.now(UTC) - start).total_seconds()

        # Build uncertainty envelope — heuristic level.
        envelope = UncertaintyEnvelope.unknown(source="L1 heuristic")
        envelope = envelope.with_update(
            UncertaintyType.OPTIMIZATION,
            UncertaintyEstimate(
                level=0.7,
                source="cheap heuristic screening",
                quantification_method="heuristic",
                is_reducible=True,
                recommended_action="Advance to L2 for causal validation.",
            ),
        )

        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=expected_value_proxy,
            is_promising=is_promising,
            stage_name=self.stage_name,
            duration_seconds=duration,
            uncertainty_envelope=envelope,
            cheap_signal=signal,
            failure_cards=cards,
            compute_actual_usd=0.0,
            fidelity_level=self.fidelity_level,
            feedback={"routing_decision": routing, "structure_hash": structure_hash},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_domain_priors(
        self,
        candidate: dict[str, Any],
    ) -> dict[str, float]:
        """Fetch domain priors from the provider, with timeout guard."""
        if self._domain_prior_provider is None:
            return {}
        try:
            return self._domain_prior_provider(candidate)
        except Exception:
            logger.debug("Domain prior provider failed; using defaults.", exc_info=True)
            return {}

    def record_evaluated(self, candidate: dict[str, Any]) -> None:
        """Register a candidate hash as evaluated (for info-gain tracking)."""
        self._evaluated_hashes.add(_candidate_structure_hash(candidate))

    def _query_lessons(
        self,
        lesson_registry: Any,
        *,
        candidate: dict[str, Any],
        context: dict[str, Any],
        stage_name: str,
        candidate_hash: str,
        intervention_types: list[str],
        objectives: list[dict[str, Any]],
    ) -> list[Any]:
        if lesson_registry is None or not hasattr(lesson_registry, "query"):
            return []
        try:
            from polisyos.scientist.methods.search.lessons import LessonQuery

            transfer_context = resolve_transfer_context(
                candidate=candidate,
                context=context,
            )
            objective_tags = [obj.get("name", obj.get("objective", "")) for obj in objectives]
            tags = [
                *(tag for tag in intervention_types if tag),
                *(tag for tag in objective_tags if tag),
                f"structure:{candidate_hash}",
            ]
            query = LessonQuery(
                stage_name=stage_name,
                tags=tags,
                task_family=transfer_context.task_family,
                min_confidence=0.5,
                limit=3,
            )
            if hasattr(lesson_registry, "query_with_transfer"):
                return lesson_registry.query_with_transfer(
                    query,
                    target_context=transfer_context,
                )
            return lesson_registry.query(query)
        except Exception:
            logger.debug("Lesson registry query failed; continuing without lessons.", exc_info=True)
            return []
