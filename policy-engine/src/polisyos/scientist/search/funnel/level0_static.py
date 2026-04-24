"""Level 0 — Static Legality and Structural Validity.

Cost: < 1 ms.  Deterministic.  No data access.

Checks schema validity, parameter domains, forbidden combinations,
unit consistency, fiscal sanity, legal red flags, and mechanism
completeness.  Extends the logic formerly in ``CheapStage``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.search.funnel._rules import (
    MAX_FISCAL_RATIO,
    UNIT_CONSISTENCY_MAP,
    check_forbidden_combinations,
    check_legal_red_flags,
    check_parameter_domains,
)
from polisyos.scientist.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    TypedFailureCard,
    UncertaintyEnvelope,
    UncertaintyType,
)

logger = get_logger(__name__)


class Level0StaticValidator(FunnelStage):
    """Funnel Level 0: deterministic structural and domain validation."""

    # ------------------------------------------------------------------
    # FunnelStage interface
    # ------------------------------------------------------------------

    @property
    def stage_name(self) -> str:
        return "funnel_L0_static"

    @property
    def fidelity_level(self) -> int:
        return 0

    @property
    def estimated_cost_usd(self) -> float:
        return 0.0

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

        # 1. Schema / structure completeness
        self._check_structure(candidate, cards)

        # 2. Parameter domain validity
        self._check_parameters(candidate, cards)

        # 3. Forbidden policy combinations
        self._check_forbidden_combinations(candidate, cards)

        # 4. Unit / dimension consistency
        self._check_unit_consistency(candidate, cards)

        # 5. Policy-budget envelope sanity
        self._check_fiscal_sanity(candidate, cards)

        # 6. Legal red flags
        self._check_legal_red_flags(candidate, cards)

        # 7. Mechanism completeness
        self._check_mechanism_completeness(candidate, cards)

        duration = (datetime.now(UTC) - start).total_seconds()
        has_blockers = any(c.is_blocker for c in cards)

        if has_blockers:
            logger.debug(
                "L0 rejected candidate: %d blockers, %d warnings",
                sum(1 for c in cards if c.is_blocker),
                sum(1 for c in cards if not c.is_blocker),
            )

        return FunnelStageResult(
            policy_candidate=candidate,
            objective_value=0.0 if not has_blockers else 1.0,
            is_promising=not has_blockers,
            stage_name=self.stage_name,
            duration_seconds=duration,
            uncertainty_envelope=UncertaintyEnvelope.deterministic(),
            failure_cards=cards,
            compute_actual_usd=0.0,
            fidelity_level=self.fidelity_level,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_structure(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        semantic = candidate.get("semantic")
        if semantic is None:
            cards.append(
                TypedFailureCard(
                    judge_name="L0_static",
                    failure_type="missing_semantic",
                    severity="blocker",
                    description="Candidate is missing the 'semantic' layer.",
                    remediation_hint="Add a 'semantic' dict with 'interventions' and 'objectives'.",
                )
            )
            return

        if not isinstance(semantic, dict):
            cards.append(
                TypedFailureCard(
                    judge_name="L0_static",
                    failure_type="invalid_semantic_type",
                    severity="blocker",
                    description=f"'semantic' must be a dict, got {type(semantic).__name__}.",
                )
            )
            return

        if not semantic.get("interventions"):
            cards.append(
                TypedFailureCard(
                    judge_name="L0_static",
                    failure_type="no_interventions",
                    severity="blocker",
                    description="No interventions defined in semantic layer.",
                    remediation_hint="Define at least one intervention.",
                )
            )

        if not semantic.get("objectives"):
            cards.append(
                TypedFailureCard(
                    judge_name="L0_static",
                    failure_type="no_objectives",
                    severity="warning",
                    description="No objectives defined in semantic layer.",
                    remediation_hint="Define at least one objective for evaluation.",
                )
            )

    @staticmethod
    def _check_parameters(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])

        for idx, intervention in enumerate(interventions):
            params = intervention.get("parameters", {})
            for name, value in params.items():
                issues = check_parameter_domains(name, value)
                for issue in issues:
                    # NaN/Inf are blockers; domain violations are warnings
                    is_nan_inf = "NaN" in issue or "infinite" in issue
                    cards.append(
                        TypedFailureCard(
                            judge_name="L0_static",
                            failure_type="parameter_domain_violation",
                            severity="blocker" if is_nan_inf else "warning",
                            description=f"Intervention {idx}: {issue}",
                            uncertainty_type=UncertaintyType.MODEL,
                        )
                    )

    @staticmethod
    def _check_forbidden_combinations(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])
        types = [iv.get("type", iv.get("intervention_type", "")) for iv in interventions]
        types = [t for t in types if t]

        violations = check_forbidden_combinations(types)
        for a, b in violations:
            cards.append(
                TypedFailureCard(
                    judge_name="L0_static",
                    failure_type="forbidden_combination",
                    severity="blocker",
                    description=f"Forbidden policy combination: '{a}' + '{b}'.",
                    remediation_hint="Remove one of the conflicting interventions.",
                )
            )

    @staticmethod
    def _check_unit_consistency(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        """Check that parameters sharing economic concepts have compatible dimensions."""
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])

        # Collect (dimension, param_name) pairs across all interventions.
        dimension_groups: dict[str, list[str]] = {}
        for intervention in interventions:
            params = intervention.get("parameters", {})
            for name in params:
                name_lower = name.lower()
                for pattern, dimension in UNIT_CONSISTENCY_MAP.items():
                    if pattern in name_lower:
                        dimension_groups.setdefault(dimension, []).append(name)
                        break

        # If a single intervention mixes "currency" and "ratio" params under the
        # same economic variable root, flag it.  For now, this is informational.
        # More sophisticated checks will be added as the IR evolves.
        for dimension, names in dimension_groups.items():
            if len(names) > 10:
                cards.append(
                    TypedFailureCard(
                        judge_name="L0_static",
                        failure_type="unit_consistency_warning",
                        severity="info",
                        description=(
                            f"Dimension '{dimension}' has {len(names)} parameters — "
                            f"verify unit consistency."
                        ),
                    )
                )

    @staticmethod
    def _check_fiscal_sanity(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        """Policy-budget envelope sanity (not compute-budget)."""
        semantic = candidate.get("semantic", {})
        constraints = semantic.get("constraints", {})
        budget = constraints.get("fiscal_budget")
        gdp_ref = constraints.get("gdp_reference")

        if budget is not None and gdp_ref is not None:
            try:
                budget_f = float(budget)
                gdp_f = float(gdp_ref)
                if gdp_f > 0 and budget_f / gdp_f > MAX_FISCAL_RATIO:
                    cards.append(
                        TypedFailureCard(
                            judge_name="L0_static",
                            failure_type="fiscal_sanity",
                            severity="blocker",
                            description=(
                                f"Fiscal budget ({budget_f}) exceeds "
                                f"{MAX_FISCAL_RATIO}× GDP reference ({gdp_f})."
                            ),
                            remediation_hint="Reduce fiscal budget or verify GDP reference.",
                        )
                    )
            except (TypeError, ValueError):
                pass

    @staticmethod
    def _check_legal_red_flags(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])

        for idx, intervention in enumerate(interventions):
            itype = intervention.get("type", intervention.get("intervention_type", ""))
            if not itype:
                continue
            flags = check_legal_red_flags(itype)
            for flag in flags:
                cards.append(
                    TypedFailureCard(
                        judge_name="L0_static",
                        failure_type="legal_red_flag",
                        severity="warning",
                        description=(
                            f"Intervention {idx} ('{itype}') matches legal red-flag "
                            f"pattern '{flag}'."
                        ),
                        remediation_hint="Verify legal compliance before proceeding.",
                    )
                )

    @staticmethod
    def _check_mechanism_completeness(
        candidate: dict[str, Any],
        cards: list[TypedFailureCard],
    ) -> None:
        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])
        objectives = semantic.get("objectives", [])

        if interventions and not objectives:
            cards.append(
                TypedFailureCard(
                    judge_name="L0_static",
                    failure_type="mechanism_incomplete",
                    severity="blocker",
                    description="Interventions defined but no objectives — cannot evaluate.",
                    remediation_hint="Add at least one objective.",
                )
            )
