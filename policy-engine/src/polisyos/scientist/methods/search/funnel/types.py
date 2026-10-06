"""Core types for the multi-fidelity evaluation funnel."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
from math import isfinite
from typing import Any, Literal

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir import TypedFailureCard, UncertaintyType
from polisyos.scientist.methods.search.stages import SearchStage, StageResult
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope,
    UncertaintyEstimate,
)

FunnelEvaluationStatus = Literal["not_evaluated", "partial", "evaluated"]
_RESOURCE_RESPONSE_OBSERVER: ContextVar[Callable[[Any], None] | None] = ContextVar(
    "funnel_resource_response_observer", default=None
)


@contextmanager
def funnel_resource_response_observer(
    observer: Callable[[Any], None] | None,
) -> Iterator[None]:
    """Bind operational response accounting to this stage execution only.

    The observer consumes the existing producer settlement; it issues neither
    accounting receipts nor permission. Async worker calls inherit this context.
    """
    token = _RESOURCE_RESPONSE_OBSERVER.set(observer)
    try:
        yield
    finally:
        _RESOURCE_RESPONSE_OBSERVER.reset(token)


def observe_funnel_resource_response(response: Any) -> None:
    """Forward a native returned settlement before any fallible payload parsing."""
    observer = _RESOURCE_RESPONSE_OBSERVER.get()
    if observer is not None:
        from polisyos.core.llm.settlement import producer_settlement
        from polisyos.core.llm.traced_client import LLMAccountingError

        settlement = producer_settlement(response)
        try:
            if settlement is None:
                raise ValueError("configured funnel resource producer returned no typed settlement")
            observer(settlement)
        except (ValueError, OSError) as exc:
            raise LLMAccountingError(
                response=response,
                event={"funnel_accounting_status": "not_established", "settlement": settlement},
                cause=exc,
            ) from exc


@dataclass(frozen=True)
class FunnelResourceAccountingFailure:
    """Actual producer input retained when its accounting acknowledgment failed."""

    event: Any
    budget_keys: tuple[str, ...]


def observe_funnel_resource_accounting_failure(
    failure: Any, *, budget_keys: tuple[str, ...]
) -> None:
    """Carry a native B error's observed event without issuing an acknowledgment."""
    from polisyos.core.llm.settlement import LLMProducerEvent, LLMProducerSettlement
    from polisyos.core.llm.traced_client import LLMAccountingError

    observer = _RESOURCE_RESPONSE_OBSERVER.get()
    if observer is None or not isinstance(failure, LLMAccountingError):
        return
    event = failure.event.get("producer_event")
    settlement = failure.event.get("settlement")
    if event is None and isinstance(settlement, LLMProducerSettlement):
        event = settlement.event
    if isinstance(event, LLMProducerEvent):
        observer(FunnelResourceAccountingFailure(event, budget_keys))


def statistical_uncertainty_from_ci_width(
    simulation_results: dict[str, Any],
    *,
    source: str,
    quantification_method: str,
    recommended_action: str | None = None,
) -> UncertaintyEstimate:
    """Build a statistical estimate without laundering missing CI data.

    A missing, malformed, non-finite, or negative confidence-interval width is
    unassessed uncertainty.  A finite zero width remains a measured zero-width
    interval, including when the effect itself is zero.
    """

    bootstrap = simulation_results.get("bootstrap")
    if not isinstance(bootstrap, Mapping) or "ci_width" not in bootstrap:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width missing",
            quantification_method="ci_width_missing",
            is_reducible=True,
            recommended_action=recommended_action,
        )

    raw_width = bootstrap.get("ci_width")
    if raw_width is None:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width missing",
            quantification_method="ci_width_missing",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    if isinstance(raw_width, bool):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width invalid",
            quantification_method="ci_width_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    try:
        ci_width = float(raw_width)
    except (TypeError, ValueError, OverflowError):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width invalid",
            quantification_method="ci_width_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    if not isfinite(ci_width) or ci_width < 0.0:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; confidence-interval width invalid",
            quantification_method="ci_width_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )

    if "ate" not in simulation_results:
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    raw_effect = simulation_results["ate"]
    if raw_effect is None or isinstance(raw_effect, bool):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    try:
        effect = abs(float(raw_effect))
    except (TypeError, ValueError, OverflowError):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )
    if not isfinite(effect):
        return UncertaintyEstimate(
            level=1.0,
            source=f"{source}; effect scale invalid",
            quantification_method="effect_invalid",
            is_reducible=True,
            recommended_action=recommended_action,
        )

    if effect == 0.0:
        level = 0.0 if ci_width == 0.0 else 1.0
    else:
        level = min(1.0, ci_width / (2.0 * effect))
    return UncertaintyEstimate(
        level=level,
        source=source,
        quantification_method=quantification_method,
        is_reducible=True,
        recommended_action=recommended_action,
    )


# ---------------------------------------------------------------------------
# §8.5 — CheapSignalVector
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CheapSignalVector:
    """Multi-dimensional cheap signal produced by Level 1 (blueprint §8.5).

    All scores are in [0, 1] unless documented otherwise.
    """

    structural_validity: float = 0.5
    causal_identifiability: float = 0.5
    positivity_risk: float = 0.5
    transportability_risk: float = 0.5
    uncertainty_prior: float = 0.5
    policy_conflict: float = 0.0
    feasibility: float = 0.5
    expected_value_proxy: float = 0.0
    expected_harm_proxy: float = 0.5
    expected_information_gain: float = 0.5

    def routing_decision(self) -> Literal["reject", "defer", "advance", "fast_track"]:
        """Deterministic routing based on vector thresholds (blueprint §8.5)."""
        if self.structural_validity < 0.5 or self.causal_identifiability < 0.2:
            return "reject"
        if self.positivity_risk > 0.8 or self.policy_conflict > 0.8:
            return "reject"
        if (
            self.expected_value_proxy > 0.9
            and self.feasibility > 0.8
            and self.expected_harm_proxy < 0.1
            and self.positivity_risk < 0.2
            and self.uncertainty_prior < 0.3
        ):
            return "fast_track"
        return "advance"


# ---------------------------------------------------------------------------
# §8.6 — FunnelStageResult and FunnelStage
# ---------------------------------------------------------------------------


@dataclass
class FunnelStageResult(StageResult):
    """Extended stage result carrying funnel-specific metadata."""

    uncertainty_envelope: UncertaintyEnvelope = field(
        default_factory=UncertaintyEnvelope.unknown,
    )
    cheap_signal: CheapSignalVector | None = None
    failure_cards: list[TypedFailureCard] = field(default_factory=list)
    compute_actual_usd: float = 0.0
    compute_cost_source: Literal["estimated", "provider_reported_only", "cache_reuse", "mixed"] = (
        "estimated"
    )
    provider_spend_usd: Decimal | None = None
    resource_event_ids: tuple[str, ...] = ()
    fidelity_level: int = 0
    audit_refs: list[ArtifactRef] = field(default_factory=list)
    actionable_side_information_ref: ArtifactRef | None = None
    terminal_action: (
        Literal[
            "advance",
            "defer",
            "reject",
            "retry_cheaper",
            "complete",
            "defer_to_human",
        ]
        | None
    ) = None

    @property
    def has_blockers(self) -> bool:
        return any(fc.is_blocker for fc in self.failure_cards)


class FunnelStage(SearchStage):
    """Abstract base for a stage within the multi-fidelity funnel.

    Extends ``SearchStage`` with fidelity metadata and richer result type.
    """

    @property
    @abstractmethod
    def fidelity_level(self) -> int:
        """Numeric fidelity level (0 = cheapest, higher = more expensive)."""
        ...

    @property
    @abstractmethod
    def estimated_cost_usd(self) -> float:
        """Estimated per-candidate cost in USD."""
        ...

    @abstractmethod
    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> FunnelStageResult:
        """Evaluate a candidate and return a funnel-aware result."""
        ...
