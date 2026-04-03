"""Public analytics strategic module API."""
from __future__ import annotations

import itertools
import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    ArtifactRefModel,
    StrategicPayoffTableRef,
    StrategicResponseBundleRef,
    StrategicSCMRef,
)
from polisyos.ir.analytics.dynamic_regime import RuntimeSupportStatus
from polisyos.scientist.kernel.budgets import ComputeBudget

_STRATEGIC_PAYOFF_TABLE_SCHEMA_NAME = "ir.strategic_payoff_table"
_STRATEGIC_PAYOFF_TABLE_SCHEMA_VERSION = "1.0"
_STRATEGIC_SCM_SCHEMA_NAME = "ir.strategic_scm"
_STRATEGIC_SCM_SCHEMA_VERSION = "1.0"
_STRATEGIC_RESPONSE_BUNDLE_SCHEMA_NAME = "ir.strategic_response_bundle"
_STRATEGIC_RESPONSE_BUNDLE_SCHEMA_VERSION = "1.0"
_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_NAME = "ir.strategic_closure_summary"
_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_VERSION = "1.0"
_EQUILIBRIUM_SET_SUMMARY_SCHEMA_NAME = "ir.equilibrium_set_summary"
_EQUILIBRIUM_SET_SUMMARY_SCHEMA_VERSION = "1.0"
_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_NAME = "ir.equilibrium_selection_summary"
_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_VERSION = "1.0"
_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_NAME = "ir.performative_shift_summary"
_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_VERSION = "1.0"
_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_NAME = "ir.post_adaptation_policy_value_summary"
_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_VERSION = "1.0"


def _ensure_non_empty(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _ensure_finite(value: float, *, field_name: str) -> float:
    casted = float(value)
    if not math.isfinite(casted):
        raise ValueError(f"{field_name} must be finite")
    return casted


def _validate_artifact_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


def _persist_strategic_leaf(
    store: ArtifactStore,
    payload: BaseModel,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    ref = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _load_strategic_leaf(
    store: ArtifactStore,
    ref: ArtifactRefModel,
    model: type[BaseModel],
) -> Any:
    payload = get_json_artifact(store, ref.artifact_id)
    return model.model_validate(payload)


def encode_action_profile(
    profile: dict[str, str],
    *,
    agent_order: tuple[str, ...],
) -> str:
    """Encode a joint action profile using a stable agent order."""

    return "|".join(f"{agent}={profile[agent]}" for agent in agent_order)


def decode_action_profile(
    encoded: str,
    *,
    agent_order: tuple[str, ...],
) -> dict[str, str]:
    """Decode a joint action profile emitted by ``encode_action_profile``."""

    raw_parts = [part.strip() for part in str(encoded).split("|") if str(part).strip()]
    parsed: dict[str, str] = {}
    for part in raw_parts:
        if "=" not in part:
            raise ValueError(f"Invalid action profile fragment {part!r}")
        agent, action = part.split("=", 1)
        parsed[_ensure_non_empty(agent, field_name="profile.agent")] = _ensure_non_empty(
            action,
            field_name="profile.action",
        )
    if tuple(parsed) != agent_order:
        raise ValueError(
            "Action profile must specify every agent exactly once in strategic_agents order"
        )
    return parsed


class StrategicEquilibriumConcept(str, Enum):
    """Strategic equilibrium concept public type."""
    NASH = "nash"
    STACKELBERG = "stackelberg"
    BEST_RESPONSE_FIXED_POINT = "best_response_fixed_point"


class StrategicFallbackMode(str, Enum):
    """Strategic fallback mode public type."""
    EXACT_EQUILIBRIUM = "exact_equilibrium"
    STRATEGIC_BOUNDS = "strategic_bounds"
    MACRO_ABSTRACTED = "macro_abstracted"
    BLOCKED = "blocked"


class FiniteStrategicPayoffTable(BaseModel):
    """Dense normal-form payoff surface over finite action spaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    agent: str = Field(min_length=1)
    strategic_agents: tuple[str, ...]
    action_spaces: dict[str, tuple[str, ...]]
    payoffs: dict[str, float]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent", mode="before")
    @classmethod
    def _validate_agent(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="agent")

    @model_validator(mode="after")
    def _validate_dense_surface(self) -> "FiniteStrategicPayoffTable":
        if not self.strategic_agents:
            raise ValueError("strategic_agents must be non-empty")
        if len(set(self.strategic_agents)) != len(self.strategic_agents):
            raise ValueError("strategic_agents must be unique")
        if self.agent not in self.strategic_agents:
            raise ValueError("agent must be listed in strategic_agents")
        expected_agents = set(self.strategic_agents)
        if set(self.action_spaces) != expected_agents:
            raise ValueError("action_spaces must match strategic_agents exactly")

        normalized_action_spaces: dict[str, tuple[str, ...]] = {}
        for agent in self.strategic_agents:
            actions = tuple(
                _ensure_non_empty(action, field_name=f"action_spaces.{agent}")
                for action in self.action_spaces[agent]
            )
            if not actions:
                raise ValueError(f"action_spaces.{agent} must be non-empty")
            if len(set(actions)) != len(actions):
                raise ValueError(f"action_spaces.{agent} must contain unique actions")
            normalized_action_spaces[agent] = actions

        expected_profiles = {
            encode_action_profile(
                dict(zip(self.strategic_agents, action_tuple, strict=True)),
                agent_order=self.strategic_agents,
            )
            for action_tuple in itertools.product(
                *(normalized_action_spaces[agent] for agent in self.strategic_agents)
            )
        }
        observed_profiles = set(self.payoffs)
        missing = sorted(expected_profiles - observed_profiles)
        extra = sorted(observed_profiles - expected_profiles)
        if missing or extra:
            raise ValueError(
                "payoffs must define a dense normal-form table; "
                f"missing={missing}, extra={extra}"
            )
        for key, value in self.payoffs.items():
            decode_action_profile(key, agent_order=self.strategic_agents)
            _ensure_finite(value, field_name=f"payoffs.{key}")
        return self


class StrategicSCM(BaseModel):
    """Strategic augmentation of a causal policy rule over a small finite game."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    base_graph_ref: ArtifactRefModel
    strategic_agents: tuple[str, ...]
    utility_refs: dict[str, StrategicPayoffTableRef]
    macro_utility_refs: dict[str, StrategicPayoffTableRef] | None = None
    policy_rule_ref: ArtifactRefModel
    equilibrium_concept: StrategicEquilibriumConcept
    compute_budget: ComputeBudget = Field(default_factory=ComputeBudget)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_contract(self) -> "StrategicSCM":
        _validate_artifact_ref(self.base_graph_ref, field_name="base_graph_ref")
        _validate_artifact_ref(self.policy_rule_ref, field_name="policy_rule_ref")
        if not self.strategic_agents:
            raise ValueError("strategic_agents must be non-empty")
        if len(set(self.strategic_agents)) != len(self.strategic_agents):
            raise ValueError("strategic_agents must be unique")
        if set(self.utility_refs) != set(self.strategic_agents):
            raise ValueError("utility_refs keys must match strategic_agents exactly")
        for agent, ref in self.utility_refs.items():
            _ensure_non_empty(agent, field_name="utility_refs.agent")
            _validate_artifact_ref(ref, field_name=f"utility_refs.{agent}")
        if self.macro_utility_refs is not None:
            if set(self.macro_utility_refs) != set(self.strategic_agents):
                raise ValueError("macro_utility_refs keys must match strategic_agents exactly")
            for agent, ref in self.macro_utility_refs.items():
                _ensure_non_empty(agent, field_name="macro_utility_refs.agent")
                _validate_artifact_ref(ref, field_name=f"macro_utility_refs.{agent}")
        return self

    @property
    def runtime_blockers(self) -> tuple[str, ...]:
        if self.equilibrium_concept is StrategicEquilibriumConcept.NASH:
            return ("research_gated_equilibrium_concept",)
        return ()

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        if self.equilibrium_concept is StrategicEquilibriumConcept.NASH:
            return RuntimeSupportStatus.BLOCKED_RESEARCH
        return RuntimeSupportStatus.SUPPORTED

    @property
    def runtime_eligible(self) -> bool:
        return self.runtime_support_status is RuntimeSupportStatus.SUPPORTED


class StrategicClosureSummary(BaseModel):
    """Persisted strategic fallback / equilibrium closure summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fallback_mode: StrategicFallbackMode
    equilibrium_concept: StrategicEquilibriumConcept | None = None
    equilibrium_selection_dependence: str = Field(min_length=1)
    profile_count: int = Field(default=0, ge=0)
    equilibrium_count: int = Field(default=0, ge=0)
    blocked_reason: str | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "equilibrium_selection_dependence",
        "blocked_reason",
        mode="before",
    )
    @classmethod
    def _validate_strings(cls, value: Any, info: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name=str(info.field_name))


class EquilibriumSetSummary(BaseModel):
    """Persisted equilibrium surface disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    equilibrium_profiles: tuple[dict[str, str], ...] = ()
    equilibrium_count: int = Field(default=0, ge=0)
    multiplicity_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("multiplicity_note", mode="before")
    @classmethod
    def _validate_multiplicity_note(cls, value: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name="multiplicity_note")

    @model_validator(mode="after")
    def _validate_profiles(self) -> "EquilibriumSetSummary":
        if self.equilibrium_count != len(self.equilibrium_profiles):
            raise ValueError("equilibrium_count must match equilibrium_profiles length")
        return self


class EquilibriumSelectionSummary(BaseModel):
    """Persisted selected equilibrium disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    selected_equilibrium: dict[str, str]
    equilibrium_selection_dependence: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("equilibrium_selection_dependence", mode="before")
    @classmethod
    def _validate_selection_dependence(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="equilibrium_selection_dependence")

    @model_validator(mode="after")
    def _validate_selected_equilibrium(self) -> "EquilibriumSelectionSummary":
        if not self.selected_equilibrium:
            raise ValueError("selected_equilibrium must be non-empty")
        for agent, action in self.selected_equilibrium.items():
            _ensure_non_empty(agent, field_name="selected_equilibrium.agent")
            _ensure_non_empty(action, field_name="selected_equilibrium.action")
        return self


class PerformativeShiftSummary(BaseModel):
    """Persisted strategic performative shift disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    performative_shift: float
    baseline_policy_value: float | None = None
    post_adaptation_policy_value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shift_values(self) -> "PerformativeShiftSummary":
        _ensure_finite(self.performative_shift, field_name="performative_shift")
        if self.baseline_policy_value is not None:
            _ensure_finite(self.baseline_policy_value, field_name="baseline_policy_value")
        if self.post_adaptation_policy_value is not None:
            _ensure_finite(
                self.post_adaptation_policy_value,
                field_name="post_adaptation_policy_value",
            )
        return self


class PostAdaptationPolicyValueSummary(BaseModel):
    """Persisted post-adaptation policy-value disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fallback_mode: StrategicFallbackMode
    baseline_policy_value: float | None = None
    point_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    blocked_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("blocked_reason", mode="before")
    @classmethod
    def _validate_blocked_reason(cls, value: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name="blocked_reason")

    @model_validator(mode="after")
    def _validate_value_summary(self) -> "PostAdaptationPolicyValueSummary":
        for field_name in (
            "baseline_policy_value",
            "point_value",
            "lower_bound",
            "upper_bound",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _ensure_finite(value, field_name=field_name)
        if self.lower_bound is not None and self.upper_bound is not None and self.lower_bound > self.upper_bound:
            raise ValueError("lower_bound must be <= upper_bound")
        if self.fallback_mode is StrategicFallbackMode.BLOCKED:
            if self.blocked_reason is None:
                raise ValueError("blocked_reason is required when fallback_mode=blocked")
        elif self.blocked_reason is not None:
            raise ValueError("blocked_reason is only allowed when fallback_mode=blocked")
        return self


class StrategicResponseBundle(BaseModel):
    """Disclosed strategic closure around a causal policy recommendation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    causal_component_ref: ArtifactRefModel
    strategic_closure_ref: ArtifactRefModel
    equilibrium_selection_dependence: str = Field(min_length=1)
    behavioral_assumption_sensitivity_ref: ArtifactRefModel | None = None
    equilibrium_set_ref: ArtifactRefModel
    selected_equilibrium_ref: ArtifactRefModel | None = None
    multiplicity_note: str | None = None
    performative_shift_ref: ArtifactRefModel | None = None
    post_adaptation_policy_value_ref: ArtifactRefModel
    fallback_mode: StrategicFallbackMode = StrategicFallbackMode.EXACT_EQUILIBRIUM
    blocked_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "equilibrium_selection_dependence",
        "multiplicity_note",
        "blocked_reason",
        mode="before",
    )
    @classmethod
    def _validate_strings(cls, value: Any, info: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_bundle(self) -> "StrategicResponseBundle":
        _validate_artifact_ref(self.causal_component_ref, field_name="causal_component_ref")
        _validate_artifact_ref(self.strategic_closure_ref, field_name="strategic_closure_ref")
        _validate_artifact_ref(self.equilibrium_set_ref, field_name="equilibrium_set_ref")
        _validate_artifact_ref(
            self.post_adaptation_policy_value_ref,
            field_name="post_adaptation_policy_value_ref",
        )
        if self.behavioral_assumption_sensitivity_ref is not None:
            _validate_artifact_ref(
                self.behavioral_assumption_sensitivity_ref,
                field_name="behavioral_assumption_sensitivity_ref",
            )
        if self.performative_shift_ref is not None:
            _validate_artifact_ref(
                self.performative_shift_ref,
                field_name="performative_shift_ref",
            )
        if self.selected_equilibrium_ref is not None:
            _validate_artifact_ref(
                self.selected_equilibrium_ref,
                field_name="selected_equilibrium_ref",
            )
        if self.fallback_mode is StrategicFallbackMode.BLOCKED:
            if self.blocked_reason is None:
                raise ValueError("blocked_reason is required when fallback_mode=blocked")
            if self.selected_equilibrium_ref is not None:
                raise ValueError("selected_equilibrium_ref must be omitted when blocked")
        elif self.blocked_reason is not None:
            raise ValueError("blocked_reason is only allowed when fallback_mode=blocked")
        if self.fallback_mode in {
            StrategicFallbackMode.EXACT_EQUILIBRIUM,
            StrategicFallbackMode.MACRO_ABSTRACTED,
        } and self.selected_equilibrium_ref is None:
            raise ValueError(
                "selected_equilibrium_ref is required for exact_equilibrium and macro_abstracted"
            )
        return self


def persist_strategic_solve_artifacts(
    store: ArtifactStore,
    *,
    causal_component_ref: ArtifactRefModel,
    result: Any,
    equilibrium_concept: StrategicEquilibriumConcept | None,
    baseline_policy_value: float | None = None,
    inputs: list[InputRef] | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[StrategicResponseBundle, StrategicResponseBundleRef]:
    """Persist strategic solve artifacts helper."""
    from polisyos.foundry.methods.catalog.causal.strategic import build_strategic_response_bundle

    bundle_metadata = {
        **dict(getattr(result, "closure_summary", {}) or {}),
        **dict(metadata or {}),
    }
    closure_summary = StrategicClosureSummary(
        fallback_mode=result.fallback_mode,
        equilibrium_concept=equilibrium_concept,
        equilibrium_selection_dependence=result.equilibrium_selection_dependence,
        profile_count=int(result.closure_summary.get("profile_count") or 0),
        equilibrium_count=int(
            result.closure_summary.get("equilibrium_count") or len(result.equilibrium_profiles)
        ),
        blocked_reason=result.blocked_reason,
        warnings=tuple(str(item) for item in result.warnings),
        metadata=bundle_metadata,
    )
    strategic_closure_ref = persist_strategic_closure_summary(store, closure_summary, inputs=inputs)
    equilibrium_set_ref = persist_equilibrium_set_summary(
        store,
        EquilibriumSetSummary(
            equilibrium_profiles=tuple(dict(profile) for profile in result.equilibrium_profiles),
            equilibrium_count=len(result.equilibrium_profiles),
            multiplicity_note=result.multiplicity_note,
            metadata=bundle_metadata,
        ),
        inputs=inputs,
    )
    selected_equilibrium_ref = None
    if result.selected_equilibrium is not None:
        selected_equilibrium_ref = persist_equilibrium_selection_summary(
            store,
            EquilibriumSelectionSummary(
                selected_equilibrium=dict(result.selected_equilibrium),
                equilibrium_selection_dependence=result.equilibrium_selection_dependence,
                metadata=bundle_metadata,
            ),
            inputs=inputs,
        )
    performative_shift_ref = None
    if result.performative_shift is not None:
        performative_shift_ref = persist_performative_shift_summary(
            store,
            PerformativeShiftSummary(
                performative_shift=float(result.performative_shift),
                baseline_policy_value=baseline_policy_value,
                post_adaptation_policy_value=result.post_adaptation_policy_value,
                metadata=bundle_metadata,
            ),
            inputs=inputs,
        )
    post_adaptation_policy_value_ref = persist_post_adaptation_policy_value_summary(
        store,
        PostAdaptationPolicyValueSummary(
            fallback_mode=result.fallback_mode,
            baseline_policy_value=baseline_policy_value,
            point_value=result.post_adaptation_policy_value if result.bounds is None else None,
            lower_bound=None if result.bounds is None else float(result.bounds[0]),
            upper_bound=None if result.bounds is None else float(result.bounds[1]),
            blocked_reason=result.blocked_reason,
            metadata=bundle_metadata,
        ),
        inputs=inputs,
    )
    bundle = build_strategic_response_bundle(
        causal_component_ref=causal_component_ref,
        strategic_closure_ref=strategic_closure_ref,
        equilibrium_set_ref=equilibrium_set_ref,
        post_adaptation_policy_value_ref=post_adaptation_policy_value_ref,
        selected_equilibrium_ref=selected_equilibrium_ref,
        performative_shift_ref=performative_shift_ref,
        result=result,
    ).model_copy(update={"metadata": bundle_metadata})
    bundle_ref = persist_strategic_response_bundle(store, bundle, inputs=inputs)
    return bundle, bundle_ref


def persist_strategic_payoff_table(
    store: ArtifactStore,
    table: FiniteStrategicPayoffTable,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _STRATEGIC_PAYOFF_TABLE_SCHEMA_NAME,
    schema_version: str = _STRATEGIC_PAYOFF_TABLE_SCHEMA_VERSION,
) -> StrategicPayoffTableRef:
    """Persist strategic payoff table helper."""
    ref = put_json_artifact(
        store,
        table.model_dump(mode="json"),
        kind="ir.strategic_payoff_table",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StrategicPayoffTableRef.model_validate(ref)


def load_strategic_payoff_table(
    store: ArtifactStore,
    ref: StrategicPayoffTableRef,
) -> FiniteStrategicPayoffTable:
    """Load strategic payoff table."""
    payload = get_json_artifact(store, ref.artifact_id)
    return FiniteStrategicPayoffTable.model_validate(payload)


def persist_strategic_scm(
    store: ArtifactStore,
    contract: StrategicSCM,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _STRATEGIC_SCM_SCHEMA_NAME,
    schema_version: str = _STRATEGIC_SCM_SCHEMA_VERSION,
) -> StrategicSCMRef:
    """Persist strategic scm helper."""
    ref = put_json_artifact(
        store,
        contract.model_dump(mode="json"),
        kind="ir.strategic_scm",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StrategicSCMRef.model_validate(ref)


def load_strategic_scm(
    store: ArtifactStore,
    ref: StrategicSCMRef,
) -> StrategicSCM:
    """Load strategic scm."""
    payload = get_json_artifact(store, ref.artifact_id)
    return StrategicSCM.model_validate(payload)


def persist_strategic_response_bundle(
    store: ArtifactStore,
    bundle: StrategicResponseBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _STRATEGIC_RESPONSE_BUNDLE_SCHEMA_NAME,
    schema_version: str = _STRATEGIC_RESPONSE_BUNDLE_SCHEMA_VERSION,
) -> StrategicResponseBundleRef:
    """Persist strategic response bundle helper."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.strategic_response_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StrategicResponseBundleRef.model_validate(ref)


def load_strategic_response_bundle(
    store: ArtifactStore,
    ref: StrategicResponseBundleRef,
) -> StrategicResponseBundle:
    """Load strategic response bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return StrategicResponseBundle.model_validate(payload)


def persist_strategic_closure_summary(
    store: ArtifactStore,
    summary: StrategicClosureSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist strategic closure summary helper."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_NAME,
        schema_name=_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_NAME,
        schema_version=_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_strategic_closure_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> StrategicClosureSummary:
    """Load strategic closure summary."""
    return StrategicClosureSummary.model_validate(
        _load_strategic_leaf(store, ref, StrategicClosureSummary)
    )


def persist_equilibrium_set_summary(
    store: ArtifactStore,
    summary: EquilibriumSetSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist equilibrium set summary helper."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_EQUILIBRIUM_SET_SUMMARY_SCHEMA_NAME,
        schema_name=_EQUILIBRIUM_SET_SUMMARY_SCHEMA_NAME,
        schema_version=_EQUILIBRIUM_SET_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_equilibrium_set_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> EquilibriumSetSummary:
    """Load equilibrium set summary."""
    return EquilibriumSetSummary.model_validate(
        _load_strategic_leaf(store, ref, EquilibriumSetSummary)
    )


def persist_equilibrium_selection_summary(
    store: ArtifactStore,
    summary: EquilibriumSelectionSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist equilibrium selection summary helper."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_NAME,
        schema_name=_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_NAME,
        schema_version=_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_equilibrium_selection_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> EquilibriumSelectionSummary:
    """Load equilibrium selection summary."""
    return EquilibriumSelectionSummary.model_validate(
        _load_strategic_leaf(store, ref, EquilibriumSelectionSummary)
    )


def persist_performative_shift_summary(
    store: ArtifactStore,
    summary: PerformativeShiftSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist performative shift summary helper."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_NAME,
        schema_name=_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_NAME,
        schema_version=_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_performative_shift_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> PerformativeShiftSummary:
    """Load performative shift summary."""
    return PerformativeShiftSummary.model_validate(
        _load_strategic_leaf(store, ref, PerformativeShiftSummary)
    )


def persist_post_adaptation_policy_value_summary(
    store: ArtifactStore,
    summary: PostAdaptationPolicyValueSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist post adaptation policy value summary helper."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_NAME,
        schema_name=_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_NAME,
        schema_version=_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_post_adaptation_policy_value_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> PostAdaptationPolicyValueSummary:
    """Load post adaptation policy value summary."""
    return PostAdaptationPolicyValueSummary.model_validate(
        _load_strategic_leaf(store, ref, PostAdaptationPolicyValueSummary)
    )


__all__ = [
    "EquilibriumSelectionSummary",
    "EquilibriumSetSummary",
    "FiniteStrategicPayoffTable",
    "PerformativeShiftSummary",
    "PostAdaptationPolicyValueSummary",
    "StrategicClosureSummary",
    "StrategicEquilibriumConcept",
    "StrategicFallbackMode",
    "StrategicResponseBundle",
    "StrategicSCM",
    "decode_action_profile",
    "encode_action_profile",
    "load_equilibrium_selection_summary",
    "load_equilibrium_set_summary",
    "load_performative_shift_summary",
    "load_post_adaptation_policy_value_summary",
    "load_strategic_closure_summary",
    "load_strategic_payoff_table",
    "load_strategic_response_bundle",
    "load_strategic_scm",
    "persist_equilibrium_selection_summary",
    "persist_equilibrium_set_summary",
    "persist_performative_shift_summary",
    "persist_post_adaptation_policy_value_summary",
    "persist_strategic_closure_summary",
    "persist_strategic_payoff_table",
    "persist_strategic_solve_artifacts",
    "persist_strategic_response_bundle",
    "persist_strategic_scm",
]
