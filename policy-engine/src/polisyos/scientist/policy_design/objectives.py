"""Typed multi-objective evaluation stack for policy candidates."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from polisyos.foundry.methods.catalog.optimization.protocols import (
    AmbiguityCertificate,
    ConstraintCertificate,
)
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceStatus,
    TransportStatus,
)
from polisyos.ir.analytics.distributional import DistributionalReport
from polisyos.ir.analytics.uncertainty import (
    UncertaintyEnvelope as IRUncertaintyEnvelope,
)
from polisyos.scientist.agent.constraint_context import extract_budget_envelope
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.objective import (
    ObjectiveScoreAssessment,
    ObjectiveScoreStatus,
    _make_score_assessment,
    _unestablished_score_assessment,
    canonical_objective_rule_spec,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyEnvelope as SearchUncertaintyEnvelope,
)
from polisyos.scientist.methods.search.uncertainty import (
    UncertaintyType,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


class ObjectiveKind(str, Enum):
    """Objective kind public type."""

    PRIMARY = "primary"
    HARD_CONSTRAINT = "hard_constraint"
    SECONDARY = "secondary"
    PENALTY = "penalty"


class ObjectiveDirection(str, Enum):
    """Objective direction public type."""

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class ConstraintStatus(str, Enum):
    """Constraint status public type."""

    FEASIBLE = "feasible"
    NEAR_BINDING = "near_binding"
    VIOLATED = "violated"
    NOT_ASSESSED = "not_assessed"


class ObjectiveChannelValue(BaseModel):
    """Single typed objective channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    kind: ObjectiveKind
    value: float
    direction: ObjectiveDirection
    weight: float = 1.0
    threshold: float | None = None
    status: ConstraintStatus | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    expected_unit: StrictStr | None = None

    @property
    def normalized_value(self) -> float:
        if self.direction is ObjectiveDirection.MAXIMIZE:
            return -self.value
        return self.value

    @property
    def higher_is_better(self) -> float:
        if self.direction is ObjectiveDirection.MAXIMIZE:
            return self.value
        return -self.value

    @property
    def satisfied(self) -> bool | None:
        if self.status is None:
            return None
        return self.status in {ConstraintStatus.FEASIBLE, ConstraintStatus.NEAR_BINDING}

    @property
    def margin(self) -> float | None:
        if self.threshold is None:
            return None
        if self.direction is ObjectiveDirection.MAXIMIZE:
            return self.value - self.threshold
        return self.threshold - self.value


class PolicyEvaluationBundle(BaseModel):
    """Canonical typed inputs for policy objective extraction."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidate: PolicyCandidateSchema | None = None
    simulation_metrics: dict[str, float] = Field(default_factory=dict)
    distributional_report: DistributionalReport | None = None
    causal_effect_report: CausalEffectReport | None = None
    cross_graph_profile: CrossGraphEvidenceProfile | None = None
    governance_report: GovernanceReport | None = None
    uncertainty_envelope: SearchUncertaintyEnvelope | IRUncertaintyEnvelope | None = None
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluationVector(BaseModel):
    """Tiered multi-objective evaluation without scalar truth collapse."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    candidate_id: str | None = None
    primary: dict[str, ObjectiveChannelValue] = Field(default_factory=dict)
    hard_constraints: dict[str, ObjectiveChannelValue] = Field(default_factory=dict)
    secondary: dict[str, ObjectiveChannelValue] = Field(default_factory=dict)
    penalties: dict[str, ObjectiveChannelValue] = Field(default_factory=dict)
    feasible: bool = True
    blocking_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    score_assessment: ObjectiveScoreAssessment | None = None
    score_source: dict[str, Any] | None = None

    @property
    def legacy_scalar_proxy(self) -> float:
        total = 0.0
        for channel in self.primary.values():
            total += channel.normalized_value * channel.weight
        for channel in self.secondary.values():
            total += 0.35 * channel.normalized_value * channel.weight
        for channel in self.penalties.values():
            total += channel.normalized_value * channel.weight
        if not self.feasible:
            total += 1_000_000.0 + (1000.0 * float(len(self.blocking_reasons)))
        return total

    def legacy_scalar_proxy_for_search(
        self,
        source_results: Mapping[str, Any] | None = None,
    ) -> tuple[float | None, ObjectiveScoreStatus]:
        """Return only a scalar whose carried source basis still matches its channels."""
        assessment = self.score_assessment
        if assessment is None:
            return None, ObjectiveScoreStatus.NOT_ESTABLISHED
        if assessment.status is not ObjectiveScoreStatus.AVAILABLE:
            return None, assessment.status
        if not self.score_assessment_matches_channels(source_results):
            return None, ObjectiveScoreStatus.NOT_ESTABLISHED
        return assessment.value, ObjectiveScoreStatus.AVAILABLE

    def score_assessment_matches_channels(
        self,
        source_results: Mapping[str, Any] | None = None,
    ) -> bool:
        """Recompute the vector scalar from a content-bound, emitted source basis."""
        assessment = self.score_assessment
        if (
            assessment is None
            or assessment.status is not ObjectiveScoreStatus.AVAILABLE
            or not isinstance(self.score_source, Mapping)
        ):
            return False
        try:
            rule = json.loads(assessment.rule_spec or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(rule, dict):
            return False
        if rule.get("kind") != "policy_vector_legacy_scalar":
            return False
        embedded_source = _score_source_projection(self.score_source)
        if embedded_source is None or embedded_source != self.score_source:
            return False
        if source_results is not None:
            observed_source = _score_source_projection(source_results)
            if observed_source is None or observed_source != embedded_source:
                return False
        expected_channels = {
            channel.name: channel.value for channel in self.all_channels().values()
        }
        if embedded_source.get("objective_channels") != expected_channels:
            return False
        if (
            embedded_source.get("blocking_reasons") != list(self.blocking_reasons)
            or embedded_source.get("feasible") is not self.feasible
            or self.feasible is not (not self.blocking_reasons)
        ):
            return False
        runtime_execution = self.metadata.get("policy_runtime_invocation")
        runtime_execution_sha256: str | None = None
        if runtime_execution is not None:
            if not isinstance(runtime_execution, Mapping) or not runtime_execution:
                return False
            bootstrap = embedded_source.get("bootstrap")
            if not isinstance(bootstrap, Mapping):
                return False
            for name in _RUNTIME_SCORE_BINDING_FIELDS:
                if name not in runtime_execution or name not in bootstrap:
                    return False
                if runtime_execution[name] != bootstrap[name]:
                    return False
            runtime_execution_sha256 = _mapping_sha256(runtime_execution)
            if runtime_execution_sha256 is None:
                return False
        source_binding_sha256 = _mapping_sha256(embedded_source)
        if source_binding_sha256 is None or source_binding_sha256 != rule.get(
            "source_binding_sha256"
        ):
            return False
        expected = _policy_vector_score_assessment(
            self.primary,
            self.secondary,
            self.penalties,
            feasible=self.feasible,
            blocking_reasons=self.blocking_reasons,
            source_binding_sha256=source_binding_sha256,
            runtime_execution_sha256=runtime_execution_sha256,
            source=embedded_source,
        )
        return expected == assessment

    def with_runtime_score_assessment(
        self, runtime_execution: Mapping[str, Any]
    ) -> PolicyEvaluationVector:
        """Retain runtime attempt context until the emitted source is attached."""
        runtime_sha256 = _mapping_sha256(runtime_execution)
        assessment = _policy_vector_score_assessment(
            self.primary,
            self.secondary,
            self.penalties,
            feasible=self.feasible,
            blocking_reasons=self.blocking_reasons,
            source_binding_sha256=None,
            runtime_execution_sha256=runtime_sha256,
            source=None,
        )
        return self.model_copy(
            update={
                "score_assessment": assessment,
                "metadata": {
                    **self.metadata,
                    "policy_runtime_invocation": dict(runtime_execution),
                },
            }
        )

    def with_score_source_results(
        self, source_results: Mapping[str, Any]
    ) -> PolicyEvaluationVector:
        """Bind score channels to the emitted source record used by search consumers."""
        source = _score_source_projection(source_results)
        if source is None:
            return self.model_copy(
                update={
                    "score_source": None,
                    "score_assessment": _unestablished_vector_score_assessment(
                        "policy_vector_source_basis_missing_or_invalid"
                    ),
                }
            )
        embedded_channels = source.get("objective_channels")
        expected_channels = {
            channel.name: channel.value for channel in self.all_channels().values()
        }
        runtime_execution = self.metadata.get("policy_runtime_invocation")
        runtime_sha256: str | None = None
        binding_valid = (
            embedded_channels == expected_channels
            and source.get("blocking_reasons") == list(self.blocking_reasons)
            and source.get("feasible") is self.feasible
            and self.feasible is (not self.blocking_reasons)
        )
        if runtime_execution is not None:
            bootstrap = source.get("bootstrap")
            binding_valid = (
                binding_valid
                and isinstance(runtime_execution, Mapping)
                and isinstance(bootstrap, Mapping)
            )
            if binding_valid:
                binding_valid = all(
                    name in runtime_execution
                    and name in bootstrap
                    and runtime_execution[name] == bootstrap[name]
                    for name in _RUNTIME_SCORE_BINDING_FIELDS
                )
            runtime_sha256 = (
                _mapping_sha256(runtime_execution)
                if isinstance(runtime_execution, Mapping)
                else None
            )
            binding_valid = binding_valid and runtime_sha256 is not None
        source_sha256 = _mapping_sha256(source)
        binding_valid = binding_valid and source_sha256 is not None
        assessment = (
            _policy_vector_score_assessment(
                self.primary,
                self.secondary,
                self.penalties,
                feasible=self.feasible,
                blocking_reasons=self.blocking_reasons,
                source_binding_sha256=source_sha256,
                runtime_execution_sha256=runtime_sha256,
                source=source,
            )
            if binding_valid
            else _unestablished_vector_score_assessment(
                "policy_vector_source_channels_not_reconciled"
            )
        )
        return self.model_copy(update={"score_source": source, "score_assessment": assessment})

    def runtime_score_available_for_search(
        self, source_results: Mapping[str, Any] | None = None
    ) -> bool:
        """Whether the typed vector score is source-bound for score consumers."""
        _, status = self.legacy_scalar_proxy_for_search(source_results)
        return status is ObjectiveScoreStatus.AVAILABLE

    @property
    def constraint_statuses(self) -> dict[str, ConstraintStatus]:
        return {
            name: channel.status or ConstraintStatus.NOT_ASSESSED
            for name, channel in self.hard_constraints.items()
        }

    def all_channels(self) -> dict[str, ObjectiveChannelValue]:
        return {
            **self.primary,
            **self.hard_constraints,
            **self.secondary,
            **self.penalties,
        }

    def channel(self, name: str) -> ObjectiveChannelValue | None:
        return self.all_channels().get(name)

    def _first_value_axis(self) -> ObjectiveChannelValue | None:
        for name in ("policy_value", "welfare", "gdp_growth", "employment"):
            channel = self.primary.get(name)
            if channel is not None:
                return channel
        if self.primary:
            return next(iter(self.primary.values()))
        return None

    def frontier_objectives(
        self,
        view: str,
        source_results: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        """Return only selected axes with exact configured/source unit matches.

        Pareto views consume their selected coordinates, not the unrelated legacy
        scalar aggregate. Every returned axis is independently source-recomputed.
        """
        value_axis = self._first_value_axis()
        if value_axis is None:
            return {}
        selected: list[tuple[str, ObjectiveChannelValue, str]] = [
            (value_axis.name, value_axis, "primary")
        ]
        if view == "global_feasible":
            employment = self.primary.get("employment")
            if employment is not None:
                selected.append(("employment", employment, "primary"))
        elif view == "equity_aware":
            inequality = self.secondary.get("inequality")
            if inequality is not None:
                selected.append(("inequality", inequality, "secondary"))
        elif view == "low_risk":
            robustness = self.secondary.get("robustness")
            if robustness is not None:
                selected.append(("robustness", robustness, "secondary"))
        elif view == "implementation_simple":
            simplicity = self.secondary.get("simplicity")
            if simplicity is not None:
                selected.append(("simplicity", simplicity, "secondary"))

        source = source_results if source_results is not None else self.score_source
        if not isinstance(source, Mapping):
            return {}
        for _, channel, group in selected:
            assessment = _policy_vector_channel_assessment(channel, group, source)
            if assessment.status is not ObjectiveScoreStatus.AVAILABLE:
                return {}
            if source_results is not None and self.score_source is not None:
                embedded = _policy_vector_channel_assessment(channel, group, self.score_source)
                if assessment != embedded:
                    return {}
        return {name: channel.higher_is_better for name, channel, _ in selected}

    def as_legacy_objectives(
        self,
        source_results: Mapping[str, Any] | None = None,
    ) -> list[Any]:
        """Project channel details without upgrading an unbound runtime vector."""
        raw_source = source_results if source_results is not None else self.score_source
        channel_source = raw_source if isinstance(raw_source, Mapping) else None
        from polisyos.scientist.methods.search.objective import (
            ObjectiveValue,
            OptimizationDirection,
        )

        channels = [
            *[("primary", item) for item in self.primary.values()],
            *[("secondary", item) for item in self.secondary.values()],
            *[("penalties", item) for item in self.penalties.values()],
        ]
        objectives: list[Any] = []
        for group, channel in channels:
            assessment = _policy_vector_channel_assessment(channel, group, channel_source)
            objectives.append(
                ObjectiveValue(
                    name=channel.name,
                    raw_value=channel.value,
                    direction=(
                        OptimizationDirection.MAXIMIZE
                        if channel.direction is ObjectiveDirection.MAXIMIZE
                        else OptimizationDirection.MINIMIZE
                    ),
                    weight=channel.weight,
                    is_satisfied=(True if channel.satisfied is None else bool(channel.satisfied)),
                    threshold=channel.threshold,
                    score_status=assessment.status,
                    score_assessment=assessment,
                )
            )
        return objectives


def _policy_vector_channel_rule(
    channel: ObjectiveChannelValue,
    group: str,
) -> dict[str, Any]:
    """Project the selected channel's actual configured comparison rule."""
    return {
        "kind": "policy_vector_channel",
        "group": group,
        "name": channel.name,
        "direction": channel.direction.value,
        "weight": float(channel.weight),
        "expected_unit": channel.expected_unit,
    }


def _policy_vector_channel_rule_spec(
    channel: ObjectiveChannelValue,
    group: str,
) -> str:
    """Return the stable selected-rule identity for one policy objective channel."""
    return canonical_objective_rule_spec(_policy_vector_channel_rule(channel, group))


def _policy_vector_channel_assessment(
    channel: ObjectiveChannelValue,
    group: str,
    source_results: Mapping[str, Any] | None,
) -> ObjectiveScoreAssessment:
    """Recompute one selected axis from its emitted value and exact unit evidence."""
    field_name = f"channel:{group}:{channel.name}"
    value = float(channel.value)
    weight = float(channel.weight)
    source = source_results
    if isinstance(source, Mapping) and isinstance(source.get("simulation_results"), Mapping):
        source = source["simulation_results"]
    source_units = source.get("metric_units") if isinstance(source, Mapping) else None
    source_channels = source.get("objective_channels") if isinstance(source, Mapping) else None
    source_value = (
        source_channels.get(channel.name) if isinstance(source_channels, Mapping) else None
    )
    status = ObjectiveScoreStatus.AVAILABLE
    limitation: str | None = None
    unit_bindings: tuple[tuple[str, str], ...] = ()
    source_fields = [field_name]
    if not math.isfinite(value) or not math.isfinite(weight):
        status = ObjectiveScoreStatus.INVALID
        limitation = "channel_value_invalid"
    elif not isinstance(source_channels, Mapping) or source_value != value:
        status = ObjectiveScoreStatus.NOT_ESTABLISHED
        limitation = "policy_vector_channel_source_not_reconciled"
    elif channel.expected_unit is None:
        status = ObjectiveScoreStatus.UNAVAILABLE
        limitation = "policy_vector_channel_selected_unit_not_established"
    elif (
        not isinstance(channel.expected_unit, str)
        or not channel.expected_unit.strip()
        or channel.expected_unit != channel.expected_unit.strip()
    ):
        status = ObjectiveScoreStatus.INVALID
        limitation = "policy_vector_channel_selected_unit_invalid"
    elif not isinstance(source_units, Mapping):
        status = (
            ObjectiveScoreStatus.UNAVAILABLE
            if not isinstance(source, Mapping) or "metric_units" not in source
            else ObjectiveScoreStatus.INVALID
        )
        limitation = "policy_vector_channel_source_unit_not_established"
    elif field_name not in source_units:
        status = ObjectiveScoreStatus.UNAVAILABLE
        limitation = "policy_vector_channel_source_unit_not_established"
    else:
        observed_unit = source_units[field_name]
        if (
            not isinstance(observed_unit, str)
            or not observed_unit.strip()
            or observed_unit != observed_unit.strip()
        ):
            status = ObjectiveScoreStatus.INVALID
            limitation = "policy_vector_channel_source_unit_invalid"
        elif observed_unit != channel.expected_unit:
            status = ObjectiveScoreStatus.INVALID
            limitation = "policy_vector_channel_source_unit_incompatible"
        else:
            unit_bindings = ((field_name, observed_unit),)
            source_fields.append(f"metric_units.{field_name}")
    return _make_score_assessment(
        rule=_policy_vector_channel_rule(channel, group),
        required_input_groups=((field_name,),),
        source_fields=tuple(sorted(source_fields)),
        source_values=((field_name, value),),
        source_unit_bindings=unit_bindings,
        status=status,
        value=value if status is ObjectiveScoreStatus.AVAILABLE else None,
        limitation=limitation,
    )


_RUNTIME_SCORE_BINDING_FIELDS = (
    "evaluation_attempt_id",
    "requested_draw_count",
    "requested_draw_source",
    "effective_estimation_config_sha256",
)


def _score_source_projection(source: Mapping[str, Any]) -> dict[str, Any] | None:
    """Reduce emitted simulation results to every score-formula operand."""
    raw_metric_units = source.get("metric_units")
    if not isinstance(raw_metric_units, Mapping) or any(
        not isinstance(name, str) or not name.strip() for name in raw_metric_units
    ):
        return None
    try:
        metric_units = dict(raw_metric_units)
        json.dumps(metric_units, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return None
    raw_blocking_reasons = source.get("blocking_reasons")
    raw_feasible = source.get("feasible")
    if (
        not isinstance(raw_blocking_reasons, list)
        or any(not isinstance(reason, str) or not reason for reason in raw_blocking_reasons)
        or type(raw_feasible) is not bool
        or raw_feasible is not (not raw_blocking_reasons)
    ):
        return None
    raw_channels = source.get("objective_channels")
    if not isinstance(raw_channels, Mapping) or not raw_channels:
        return None
    channels: dict[str, float] = {}
    for name, raw_value in raw_channels.items():
        if not isinstance(name, str) or isinstance(raw_value, bool):
            return None
        try:
            value = float(raw_value)
        except (TypeError, ValueError, OverflowError):
            return None
        if not math.isfinite(value):
            return None
        channels[name] = value
    projection: dict[str, Any] = {
        "objective_channels": channels,
        "metric_units": metric_units,
        "feasible": raw_feasible,
        "blocking_reasons": list(raw_blocking_reasons),
    }
    raw_bootstrap = source.get("bootstrap")
    if raw_bootstrap is not None:
        if not isinstance(raw_bootstrap, Mapping):
            return None
        bootstrap: dict[str, Any] = {}
        for name in _RUNTIME_SCORE_BINDING_FIELDS:
            if name not in raw_bootstrap:
                return None
            bootstrap[name] = raw_bootstrap[name]
        projection["bootstrap"] = bootstrap
    return projection


def _unestablished_vector_score_assessment(reason: str) -> ObjectiveScoreAssessment:
    """Preserve a vector's score limitation until its emitted source is bound."""
    return ObjectiveScoreAssessment(
        objective_ref=None,
        rule_spec=None,
        required_input_groups=(),
        source_field_names=(),
        source_values=(),
        source_sha256=None,
        value=None,
        status=ObjectiveScoreStatus.NOT_ESTABLISHED,
        limitation=reason,
    )


def _policy_vector_score_assessment(
    primary: Mapping[str, ObjectiveChannelValue],
    secondary: Mapping[str, ObjectiveChannelValue],
    penalties: Mapping[str, ObjectiveChannelValue],
    *,
    feasible: bool,
    blocking_reasons: list[str],
    source_binding_sha256: str | None,
    runtime_execution_sha256: str | None = None,
    source: Mapping[str, Any] | None = None,
) -> ObjectiveScoreAssessment:
    """Recompute the existing vector scalar from its selected channels and source binding."""
    groups: list[tuple[str, ...]] = []
    source_fields: list[str] = []
    source_values: list[tuple[str, float]] = []
    source_unit_bindings: list[tuple[str, str]] = []
    channel_rule: list[dict[str, Any]] = []
    status = ObjectiveScoreStatus.AVAILABLE
    limitation: str | None = None
    total = 0.0
    channel_sets = (
        ("primary", primary, 1.0),
        ("secondary", secondary, 0.35),
        ("penalties", penalties, 1.0),
    )
    count = 0
    for group, channels, factor in channel_sets:
        for name, channel in channels.items():
            field_name = f"channel:{group}:{name}"
            value = float(channel.value)
            weight = float(channel.weight)
            channel_assessment = _policy_vector_channel_assessment(channel, group, source)
            if channel_assessment.status is ObjectiveScoreStatus.INVALID:
                status = ObjectiveScoreStatus.INVALID
                limitation = channel_assessment.limitation
            elif (
                channel_assessment.status is not ObjectiveScoreStatus.AVAILABLE
                and status is not ObjectiveScoreStatus.INVALID
            ):
                status = channel_assessment.status
                limitation = channel_assessment.limitation
            else:
                source_unit_bindings.extend(channel_assessment.source_unit_bindings)
            source_fields.append(field_name)
            source_values.append((field_name, value))
            groups.append((field_name,))
            channel_rule.append(
                {
                    "field": field_name,
                    "direction": channel.direction.value,
                    "factor": factor,
                    "weight": weight,
                    "expected_unit": channel.expected_unit,
                }
            )
            normalized = -value if channel.direction is ObjectiveDirection.MAXIMIZE else value
            total += normalized * weight * factor
            count += 1

    if source_binding_sha256 is None:
        status = ObjectiveScoreStatus.NOT_ESTABLISHED
    if count == 0 and status is ObjectiveScoreStatus.AVAILABLE:
        status = ObjectiveScoreStatus.NOT_ESTABLISHED
    if (
        status is ObjectiveScoreStatus.AVAILABLE
        and len({unit for _, unit in source_unit_bindings}) != 1
    ):
        status = ObjectiveScoreStatus.INVALID
        limitation = "policy_vector_scalar_combines_incompatible_units"
    if status is ObjectiveScoreStatus.AVAILABLE and not math.isfinite(total):
        status = ObjectiveScoreStatus.INVALID
        limitation = "policy_vector_scalar_invalid"
    if status is ObjectiveScoreStatus.AVAILABLE and not feasible:
        total += 1_000_000.0 + (1000.0 * float(len(blocking_reasons)))
    rule = {
        "kind": "policy_vector_legacy_scalar",
        "channels": channel_rule,
        "feasible": bool(feasible),
        "blocking_reasons": list(blocking_reasons),
        "blocking_count": len(blocking_reasons),
        "source_binding_sha256": source_binding_sha256,
        "runtime_execution_sha256": runtime_execution_sha256,
    }
    if status is ObjectiveScoreStatus.AVAILABLE:
        source_fields.extend(f"metric_units.{name}" for name, _ in source_unit_bindings)
        limitation = None
    elif limitation is None:
        limitation = f"policy_vector_score_{status.value}"
    return _make_score_assessment(
        rule=rule,
        required_input_groups=tuple(groups),
        source_fields=tuple(sorted(set(source_fields))),
        source_values=tuple(sorted(source_values)),
        source_unit_bindings=tuple(sorted(source_unit_bindings)),
        status=status,
        value=total if status is ObjectiveScoreStatus.AVAILABLE else None,
        limitation=limitation,
    )


def _mapping_sha256(value: Mapping[str, Any]) -> str | None:
    """Hash a JSON-compatible source-binding mapping without interpreting its claims."""
    try:
        payload = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_policy_evaluation_vector(
    value: object, *, allow_mapping: bool = False
) -> PolicyEvaluationVector:
    """Validate an owner vector into this module generation's DTO class.

    A Python module reload changes class identity without changing persisted vector
    semantics. Serialized mappings are accepted only at explicitly declared ingress.

    Args:
        value: A vector from this owner or a serialized mapping at an admitted ingress.
        allow_mapping: Whether the caller accepts serialized mapping input.

    Returns:
        A vector validated against this module generation's schema.

    Raises:
        TypeError: The value is not an admitted owner vector or mapping.
        ValueError: The vector's declared fields fail current schema validation.
    """

    if isinstance(value, Mapping):
        if not allow_mapping:
            raise TypeError("ObjectiveStack must return an owner PolicyEvaluationVector")
        payload = dict(value)
    elif (
        isinstance(value, BaseModel)
        and type(value).__module__ == PolicyEvaluationVector.__module__
        and type(value).__qualname__ == PolicyEvaluationVector.__qualname__
    ):
        payload = value.model_dump(mode="python")
    else:
        raise TypeError("policy evaluation is not an owner vector or admitted mapping")
    return PolicyEvaluationVector.model_validate(payload)


class ObjectiveStack:
    """Deterministic extractor for policy-tier objective channels."""

    def __init__(
        self,
        *,
        max_statistical_uncertainty: float = 0.5,
        max_transport_uncertainty: float = 0.5,
        near_binding_ratio: float = 0.9,
    ) -> None:
        self._max_statistical_uncertainty = float(max_statistical_uncertainty)
        self._max_transport_uncertainty = float(max_transport_uncertainty)
        self._near_binding_ratio = float(near_binding_ratio)

    def evaluate(self, bundle: PolicyEvaluationBundle) -> PolicyEvaluationVector:
        metrics = dict(bundle.simulation_metrics)
        candidate = bundle.candidate
        uncertainties = _resolve_uncertainties(
            bundle.uncertainty_envelope,
            bundle.causal_effect_report,
        )
        ambiguity_certificate = _resolve_ambiguity_certificate(
            bundle.ambiguity_certificate,
            bundle.metadata,
        )
        ambiguity_summary = _summarize_ambiguity_certificate(
            ambiguity_certificate,
            near_binding_ratio=self._near_binding_ratio,
        )
        budget_ratio = _budget_ratio(candidate)
        governance_report = bundle.governance_report
        governance_blockers = _governance_blockers(governance_report)
        equity_concern = _equity_concern(bundle.distributional_report, governance_report)
        transport_score = _transport_score(bundle.cross_graph_profile)
        statistical_uncertainty = uncertainties.get(UncertaintyType.STATISTICAL, 1.0)
        transport_uncertainty = uncertainties.get(UncertaintyType.TRANSPORT, 1.0)
        if ambiguity_summary is not None:
            statistical_uncertainty = max(
                statistical_uncertainty,
                float(ambiguity_summary["statistical_uncertainty"]),
            )

        robustness_value = _robustness_score(bundle.causal_effect_report)
        robustness_source = "causal_effect_report"
        robustness_metadata: dict[str, Any] = {}
        if ambiguity_summary is not None:
            ambiguity_robustness = float(ambiguity_summary["robustness_score"])
            robustness_value = (
                min(robustness_value, ambiguity_robustness)
                if bundle.causal_effect_report is not None
                else ambiguity_robustness
            )
            robustness_source = (
                "causal_effect_report+ambiguity_certificate"
                if bundle.causal_effect_report is not None
                else "ambiguity_certificate"
            )
            robustness_metadata = {
                "ambiguity_status": ambiguity_summary["overall_status"],
                "price_of_ambiguity": ambiguity_summary["price_of_ambiguity"],
                "quantification_method": ambiguity_summary["quantification_method"],
            }

        primary = {
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=_metric(metrics, "policy_value", "welfare", "value", "gdp_change"),
                direction=ObjectiveDirection.MAXIMIZE,
                source="simulation_metrics",
            ),
            "employment": ObjectiveChannelValue(
                name="employment",
                kind=ObjectiveKind.PRIMARY,
                value=_metric(metrics, "employment", "employment_rate", default=0.0),
                direction=ObjectiveDirection.MAXIMIZE,
                source="simulation_metrics",
            ),
            "welfare": ObjectiveChannelValue(
                name="welfare",
                kind=ObjectiveKind.PRIMARY,
                value=_metric(metrics, "net_social_welfare", "welfare", "gdp_change"),
                direction=ObjectiveDirection.MAXIMIZE,
                source="simulation_metrics",
            ),
        }

        secondary = {
            "inequality": ObjectiveChannelValue(
                name="inequality",
                kind=ObjectiveKind.SECONDARY,
                value=_inequality_value(bundle.distributional_report, metrics),
                direction=ObjectiveDirection.MINIMIZE,
                source="distributional_report",
            ),
            "robustness": ObjectiveChannelValue(
                name="robustness",
                kind=ObjectiveKind.SECONDARY,
                value=robustness_value,
                direction=ObjectiveDirection.MAXIMIZE,
                source=robustness_source,
                metadata=robustness_metadata,
            ),
            "transportability": ObjectiveChannelValue(
                name="transportability",
                kind=ObjectiveKind.SECONDARY,
                value=transport_score,
                direction=ObjectiveDirection.MAXIMIZE,
                source="cross_graph_profile",
            ),
            "evidence_depth": ObjectiveChannelValue(
                name="evidence_depth",
                kind=ObjectiveKind.SECONDARY,
                value=_evidence_depth_score(bundle.cross_graph_profile, candidate),
                direction=ObjectiveDirection.MAXIMIZE,
                source="cross_graph_profile",
            ),
            "simplicity": ObjectiveChannelValue(
                name="simplicity",
                kind=ObjectiveKind.SECONDARY,
                value=_simplicity_score(candidate),
                direction=ObjectiveDirection.MAXIMIZE,
                source="candidate_metadata",
            ),
            "interpretability": ObjectiveChannelValue(
                name="interpretability",
                kind=ObjectiveKind.SECONDARY,
                value=_metadata_score(candidate, "interpretability_score", default=0.6),
                direction=ObjectiveDirection.MAXIMIZE,
                source="candidate_metadata",
            ),
            "administrative_feasibility": ObjectiveChannelValue(
                name="administrative_feasibility",
                kind=ObjectiveKind.SECONDARY,
                value=_administrative_feasibility(candidate),
                direction=ObjectiveDirection.MAXIMIZE,
                source="candidate_metadata",
            ),
        }

        penalties = {
            "statistical_uncertainty_penalty": ObjectiveChannelValue(
                name="statistical_uncertainty_penalty",
                kind=ObjectiveKind.PENALTY,
                value=statistical_uncertainty,
                direction=ObjectiveDirection.MINIMIZE,
                source=(
                    "uncertainty_envelope+ambiguity_certificate"
                    if ambiguity_summary is not None
                    else "uncertainty_envelope"
                ),
                metadata=(
                    {}
                    if ambiguity_summary is None
                    else {
                        "ambiguity_status": ambiguity_summary["overall_status"],
                        "quantification_method": ambiguity_summary["quantification_method"],
                    }
                ),
            ),
            "governance_penalty": ObjectiveChannelValue(
                name="governance_penalty",
                kind=ObjectiveKind.PENALTY,
                value=float(_issue_count(governance_report)),
                direction=ObjectiveDirection.MINIMIZE,
                source="governance_report",
            ),
            "implementation_penalty": ObjectiveChannelValue(
                name="implementation_penalty",
                kind=ObjectiveKind.PENALTY,
                value=max(0.0, 1.0 - _simplicity_score(candidate)),
                direction=ObjectiveDirection.MINIMIZE,
                source="candidate_metadata",
            ),
        }

        hard_constraints = {
            "policy_budget_constraint": (
                ambiguity_summary["budget_channel"]
                if ambiguity_summary is not None and ambiguity_summary["budget_channel"] is not None
                else _constraint_channel(
                    name="policy_budget_constraint",
                    value=budget_ratio,
                    threshold=1.0,
                    direction=ObjectiveDirection.MINIMIZE,
                    source="policy_candidate",
                    near_binding_ratio=self._near_binding_ratio,
                )
            ),
            "compliance_constraint": _status_channel(
                name="compliance_constraint",
                passed=not governance_blockers,
                source="governance_report",
                failure_score=float(len(governance_blockers)),
            ),
            "equity_constraint": (
                ambiguity_summary["equity_channel"]
                if ambiguity_summary is not None and ambiguity_summary["equity_channel"] is not None
                else _status_channel(
                    name="equity_constraint",
                    passed=not equity_concern,
                    source="distributional_report",
                    failure_score=1.0 if equity_concern else 0.0,
                )
            ),
            "statistical_constraint": _constraint_channel(
                name="statistical_constraint",
                value=statistical_uncertainty,
                threshold=self._max_statistical_uncertainty,
                direction=ObjectiveDirection.MINIMIZE,
                source=(
                    "uncertainty_envelope+ambiguity_certificate"
                    if ambiguity_summary is not None
                    else "uncertainty_envelope"
                ),
                near_binding_ratio=self._near_binding_ratio,
                metadata=(
                    {}
                    if ambiguity_summary is None
                    else {
                        "ambiguity_status": ambiguity_summary["overall_status"],
                        "price_of_ambiguity": ambiguity_summary["price_of_ambiguity"],
                        "quantification_method": ambiguity_summary["quantification_method"],
                    }
                ),
            ),
            "transport_constraint": _constraint_channel(
                name="transport_constraint",
                value=transport_uncertainty,
                threshold=self._max_transport_uncertainty,
                direction=ObjectiveDirection.MINIMIZE,
                source="uncertainty_envelope",
                near_binding_ratio=self._near_binding_ratio,
            ),
        }

        blocking_reasons = [
            name
            for name, channel in hard_constraints.items()
            if channel.status is ConstraintStatus.VIOLATED
        ]
        if governance_blockers:
            blocking_reasons.extend(
                sorted(f"governance:{reason}" for reason in governance_blockers)
            )

        evaluation = PolicyEvaluationVector(
            candidate_id=(candidate.candidate_id if candidate is not None else None),
            primary=primary,
            hard_constraints=hard_constraints,
            secondary=secondary,
            penalties=penalties,
            feasible=not blocking_reasons,
            blocking_reasons=blocking_reasons,
            metadata={
                "policy_family": _policy_family(candidate),
                "statistical_uncertainty": statistical_uncertainty,
                "transport_uncertainty": transport_uncertainty,
                "budget_ratio": budget_ratio,
                "ambiguity_certificate_status": (
                    None if ambiguity_summary is None else ambiguity_summary["overall_status"]
                ),
                "ambiguity_set_type": (
                    None
                    if ambiguity_summary is None
                    else ambiguity_summary["quantification_method"]
                ),
                "price_of_ambiguity": (
                    None if ambiguity_summary is None else ambiguity_summary["price_of_ambiguity"]
                ),
            },
        )
        runtime_required = (
            "policy_runtime_fiscal_measurement" in bundle.metadata
            or "policy_runtime_invocation" in bundle.metadata
            or str(bundle.metadata.get("generated_by") or "").startswith("policy_runtime::")
        )
        if runtime_required:
            return evaluation.with_runtime_score_assessment(
                bundle.metadata.get("policy_runtime_invocation")
                if isinstance(bundle.metadata.get("policy_runtime_invocation"), Mapping)
                else {}
            )
        return evaluation.model_copy(
            update={
                "score_assessment": _unestablished_vector_score_assessment(
                    "policy_vector_source_not_bound"
                )
            }
        )


def _metric(metrics: dict[str, float], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in metrics:
            return float(metrics[key])
    return float(default)


def _inequality_value(
    report: DistributionalReport | None,
    metrics: dict[str, float],
) -> float:
    if report is not None and report.overall_gini_delta is not None:
        return float(report.overall_gini_delta)
    return _metric(metrics, "gini_delta", "gini_coefficient", default=0.0)


def _robustness_score(report: CausalEffectReport | None) -> float:
    if report is None or not report.refutation_results:
        return 0.5
    required = [item for item in report.refutation_results]
    passed = sum(1 for item in required if item.passed)
    return passed / max(len(required), 1)


def _transport_score(profile: CrossGraphEvidenceProfile | None) -> float:
    if profile is None or not profile.needs:
        return 0.5
    supported = 0
    for assessment in profile.needs:
        if assessment.transport_status in {
            TransportStatus.IDENTIFIED,
            TransportStatus.PARTIALLY_IDENTIFIED,
        }:
            supported += 1
    return supported / len(profile.needs)


def _evidence_depth_score(
    profile: CrossGraphEvidenceProfile | None,
    candidate: PolicyCandidateSchema | None,
) -> float:
    if candidate is not None:
        evidence_depth = str(candidate.metadata.get("evidence_depth", "")).strip().lower()
        if evidence_depth == "replicated":
            return 1.0
        if evidence_depth == "meta_analytic":
            return 0.8
    if profile is None or not profile.needs:
        return 0.5
    supported = sum(
        1 for assessment in profile.needs if assessment.evidence_status is EvidenceStatus.SUPPORTED
    )
    mixed = sum(
        1 for assessment in profile.needs if assessment.evidence_status is EvidenceStatus.MIXED
    )
    return min(1.0, (supported + 0.5 * mixed) / len(profile.needs))


def _simplicity_score(candidate: PolicyCandidateSchema | None) -> float:
    if candidate is None:
        return 0.5
    interventions = len(candidate.trinity_bundle.policy_spec.interventions)
    params = len(candidate.trinity_bundle.policy_spec.parameters)
    rollout_steps = len(candidate.rollout_plan)
    complexity = interventions + params + max(rollout_steps - interventions, 0)
    return 1.0 / (1.0 + (complexity / 4.0))


def _administrative_feasibility(candidate: PolicyCandidateSchema | None) -> float:
    if candidate is None:
        return 0.5
    monitoring_penalty = min(len(candidate.monitoring_plan), 10) / 20.0
    fallback_penalty = min(len(candidate.fallback_variants), 5) / 10.0
    return max(
        0.0,
        min(1.0, _simplicity_score(candidate) - monitoring_penalty - fallback_penalty),
    )


def _metadata_score(
    candidate: PolicyCandidateSchema | None,
    key: str,
    *,
    default: float,
) -> float:
    if candidate is None:
        return default
    raw = candidate.metadata.get(key, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, value))


def _budget_ratio(candidate: PolicyCandidateSchema | None) -> float:
    if candidate is None:
        return 0.0
    envelope = extract_budget_envelope(candidate.trinity_bundle.problem_frame)
    if envelope in {None, 0}:
        return 0.0
    allocated = sum(entry.amount.amount for entry in candidate.budget_allocation)
    return float(allocated / envelope)


def _policy_family(candidate: PolicyCandidateSchema | None) -> str | None:
    if candidate is None:
        return None
    families = sorted(
        {
            intervention.kind
            for intervention in candidate.trinity_bundle.policy_spec.interventions
            if intervention.kind
        }
    )
    if not families:
        return None
    return "+".join(families)


def _governance_blockers(report: GovernanceReport | None) -> list[str]:
    if report is None:
        return []
    verdict = str(report.verdict).strip().lower()
    blockers: list[str] = []
    if verdict == "reject":
        blockers.append("verdict_reject")
    for issue in report.issues:
        severity = str(issue.get("severity", "")).strip().lower()
        if severity == "blocker":
            blockers.append(str(issue.get("code") or issue.get("pass_id") or "issue"))
    return blockers


def _issue_count(report: GovernanceReport | None) -> int:
    if report is None:
        return 0
    return len(report.issues)


def _equity_concern(
    distributional_report: DistributionalReport | None,
    governance_report: GovernanceReport | None,
) -> bool:
    if distributional_report is not None and distributional_report.has_equity_concerns():
        return True
    if governance_report is None:
        return False
    for issue in governance_report.issues:
        pass_id = str(issue.get("pass_id", "")).strip().lower()
        severity = str(issue.get("severity", "")).strip().lower()
        if pass_id == "equity" and severity in {"warning", "blocker"}:
            return True
    return False


def _resolve_ambiguity_certificate(
    certificate: AmbiguityCertificate | dict[str, Any] | None,
    metadata: dict[str, Any],
) -> AmbiguityCertificate | None:
    candidate = certificate
    if candidate is None:
        payload = metadata.get("ambiguity_certificate")
        if isinstance(payload, dict):
            candidate = payload
    if isinstance(candidate, AmbiguityCertificate):
        return candidate
    if isinstance(candidate, dict):
        return AmbiguityCertificate.from_mapping(candidate)
    return None


def _constraint_subset(
    certificate: AmbiguityCertificate,
    constraint_class: str,
) -> list[ConstraintCertificate]:
    return [
        item for item in certificate.per_constraint if item.constraint_class == constraint_class
    ]


def _uncertainty_level_from_status(
    certificate: AmbiguityCertificate,
) -> float:
    base = max(0.0, min(1.0, 1.0 - float(certificate.confidence_level)))
    if certificate.overall_status == "fail":
        return 1.0
    if certificate.overall_status == "warn":
        return max(base, 0.45)
    return max(base, 0.1)


def _budget_channel_from_certificate(
    certificate: AmbiguityCertificate,
    *,
    near_binding_ratio: float,
) -> ObjectiveChannelValue | None:
    budget_constraints = _constraint_subset(certificate, "budget")
    if not budget_constraints:
        return None
    ratios = [
        float(item.worst_case_bound) / float(item.threshold)
        for item in budget_constraints
        if abs(float(item.threshold)) > 1e-9
    ]
    if not ratios:
        return None
    worst = max(
        budget_constraints,
        key=lambda item: (
            float("-inf")
            if abs(float(item.threshold)) <= 1e-9
            else float(item.worst_case_bound) / float(item.threshold)
        ),
    )
    return _constraint_channel(
        name="policy_budget_constraint",
        value=max(ratios),
        threshold=1.0,
        direction=ObjectiveDirection.MINIMIZE,
        source="ambiguity_certificate",
        near_binding_ratio=near_binding_ratio,
        metadata={
            "constraint_name": worst.name,
            "worst_case_bound": worst.worst_case_bound,
            "threshold": worst.threshold,
            "slack": worst.slack,
            "violation_probability_bound": worst.violation_probability_bound,
            "ambiguity_status": certificate.overall_status,
            "quantification_method": certificate.ambiguity_set_type,
        },
    )


def _equity_channel_from_certificate(
    certificate: AmbiguityCertificate,
    *,
    near_binding_ratio: float,
) -> ObjectiveChannelValue | None:
    equity_constraints = _constraint_subset(certificate, "equity")
    if not equity_constraints:
        return None

    ratios = []
    for item in equity_constraints:
        if item.violation_probability_bound is not None and item.epsilon not in {
            None,
            0.0,
        }:
            ratios.append(float(item.violation_probability_bound) / float(item.epsilon))
        else:
            ratios.append(1.0 if float(item.slack) < 0.0 else 0.0)

    worst_index = max(range(len(ratios)), key=ratios.__getitem__)
    worst = equity_constraints[worst_index]
    return _constraint_channel(
        name="equity_constraint",
        value=float(ratios[worst_index]),
        threshold=1.0,
        direction=ObjectiveDirection.MINIMIZE,
        source="ambiguity_certificate",
        near_binding_ratio=near_binding_ratio,
        metadata={
            "constraint_name": worst.name,
            "slack": worst.slack,
            "epsilon": worst.epsilon,
            "violation_probability_bound": worst.violation_probability_bound,
            "ambiguity_status": certificate.overall_status,
            "quantification_method": certificate.ambiguity_set_type,
        },
    )


def _summarize_ambiguity_certificate(
    certificate: AmbiguityCertificate | None,
    *,
    near_binding_ratio: float,
) -> dict[str, Any] | None:
    if certificate is None:
        return None
    uncertainty_level = _uncertainty_level_from_status(certificate)
    return {
        "overall_status": certificate.overall_status,
        "quantification_method": certificate.ambiguity_set_type,
        "statistical_uncertainty": uncertainty_level,
        "robustness_score": max(0.0, 1.0 - uncertainty_level),
        "price_of_ambiguity": certificate.price_of_ambiguity,
        "budget_channel": _budget_channel_from_certificate(
            certificate,
            near_binding_ratio=near_binding_ratio,
        ),
        "equity_channel": _equity_channel_from_certificate(
            certificate,
            near_binding_ratio=near_binding_ratio,
        ),
    }


def _constraint_channel(
    *,
    name: str,
    value: float,
    threshold: float,
    direction: ObjectiveDirection,
    source: str,
    near_binding_ratio: float,
    metadata: dict[str, Any] | None = None,
) -> ObjectiveChannelValue:
    if direction is ObjectiveDirection.MINIMIZE:
        status = ConstraintStatus.FEASIBLE
        if value > threshold:
            status = ConstraintStatus.VIOLATED
        elif threshold > 0 and value >= threshold * near_binding_ratio:
            status = ConstraintStatus.NEAR_BINDING
    else:
        status = ConstraintStatus.FEASIBLE
        if value < threshold:
            status = ConstraintStatus.VIOLATED
        elif threshold > 0 and value <= threshold / max(near_binding_ratio, 1e-6):
            status = ConstraintStatus.NEAR_BINDING
    return ObjectiveChannelValue(
        name=name,
        kind=ObjectiveKind.HARD_CONSTRAINT,
        value=value,
        threshold=threshold,
        direction=direction,
        status=status,
        source=source,
        metadata={} if metadata is None else metadata,
    )


def _status_channel(
    *,
    name: str,
    passed: bool,
    source: str,
    failure_score: float,
    metadata: dict[str, Any] | None = None,
) -> ObjectiveChannelValue:
    return ObjectiveChannelValue(
        name=name,
        kind=ObjectiveKind.HARD_CONSTRAINT,
        value=failure_score,
        threshold=0.0,
        direction=ObjectiveDirection.MINIMIZE,
        status=ConstraintStatus.FEASIBLE if passed else ConstraintStatus.VIOLATED,
        source=source,
        metadata={} if metadata is None else metadata,
    )


def _resolve_uncertainties(
    envelope: SearchUncertaintyEnvelope | IRUncertaintyEnvelope | None,
    causal_report: CausalEffectReport | None,
) -> dict[UncertaintyType, float]:
    if isinstance(envelope, SearchUncertaintyEnvelope):
        return {
            uncertainty_type: float(estimate.level)
            for uncertainty_type, estimate in envelope.uncertainties.items()
        }
    ir_envelope = envelope
    if ir_envelope is None and causal_report is not None:
        ir_envelope = causal_report.to_uncertainty_envelope()
    if isinstance(ir_envelope, IRUncertaintyEnvelope):
        relative = ir_envelope.relative_uncertainty
        ratio = 1.0 if relative is None else max(0.0, min(1.0, float(relative)))
        return {
            UncertaintyType.STATISTICAL: ratio,
            UncertaintyType.STRUCTURAL: ratio,
            UncertaintyType.TRANSPORT: min(1.0, ratio + 0.1),
            UncertaintyType.MEASUREMENT: ratio,
            UncertaintyType.MODEL: min(1.0, ratio + 0.05),
            UncertaintyType.OPTIMIZATION: 0.5,
        }
    return dict.fromkeys(UncertaintyType, 1.0)


__all__ = [
    "ConstraintStatus",
    "ObjectiveChannelValue",
    "ObjectiveDirection",
    "ObjectiveKind",
    "ObjectiveStack",
    "PolicyEvaluationBundle",
    "PolicyEvaluationVector",
]
