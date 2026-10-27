"""Public search objective module API."""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.ir.kernel import UnitSpecType

_MISSING = object()
_INVALID = object()
_SOURCE_RESULT_CONTAINERS = ("simulation_results", "metrics")
_BALANCE_ALIASES = ("gov_balance", "government_balance")
_DEFICIT_ALIASES = ("budget_deficit", "deficit")


class SourceMetricObservation(BaseModel):
    """A candidate-only, content-bound observation of the canonical balance stock."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    source_status: Literal["observed", "unavailable", "invalid", "not_established"]
    predicate_status: Literal["recomputed", "not_established"]
    metric_id: Literal["government_balance"] | None = None
    slot_id: Literal["government.balance"] | None = None
    value: float | None = Field(default=None, strict=True)
    unit_id: Literal["usd"] | None = None
    scope: Literal["global"] | None = None
    quantity_kind: Literal["stock"] | None = None
    simulation_step: int | None = Field(default=None, strict=True, ge=0)
    time_basis: Literal["simulation_step", "not_established"]
    source_result_ref: ArtifactRef | None = None
    source_metrics_ref: ArtifactRef | None = None
    source_snapshot_ref: ArtifactRef | None = None
    objective_id: Literal["budget_deficit"] = "budget_deficit"
    objective_status: Literal["not_established"] = "not_established"
    objective_value: None = None
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_observation_boundary(self) -> SourceMetricObservation:
        """Keep source observation separate from any unproven fiscal objective mapping."""
        if self.objective_status != "not_established" or self.objective_value is not None:
            raise ValueError("government_balance_does_not_establish_budget_deficit")
        if self.source_status == "observed":
            if (
                self.predicate_status != "recomputed"
                or self.metric_id != "government_balance"
                or self.slot_id != "government.balance"
                or self.value is None
                or not math.isfinite(self.value)
                or self.unit_id != "usd"
                or self.scope != "global"
                or self.quantity_kind != "stock"
                or self.simulation_step is None
                or self.time_basis != "simulation_step"
                or any(
                    ref is None or ref.manifest_profile_sha256 is None
                    for ref in (
                        self.source_result_ref,
                        self.source_metrics_ref,
                        self.source_snapshot_ref,
                    )
                )
            ):
                raise ValueError("observed_government_balance_source_basis_is_incomplete")
        elif (
            self.predicate_status != "not_established"
            or self.value is not None
            or self.metric_id is not None
            or self.slot_id is not None
            or self.unit_id is not None
            or self.scope is not None
            or self.quantity_kind is not None
            or self.simulation_step is not None
            or self.time_basis != "not_established"
        ):
            raise ValueError("non_observed_government_balance_cannot_carry_a_measurement")
        return self


class SelectedMethodMetricArtifactRef(ArtifactRef):
    """Deep-immutable, selected-profile ArtifactRef used in metric evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_profile_sha256: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")


_METHOD_METRIC_REF_KINDS = {
    "binding_set": "foundry.method_metric_binding_set",
    "execution_bundle": "foundry.method_execution_bundle",
    "simulation_result": "foundry.simulation_result",
    "output": "foundry.method_output",
    "environment": "foundry.environment_manifest",
    "input_capture": "foundry.method_metric_input_capture",
}
_SHA256_DIGEST_PATTERN = r"^(?:sha256:)?[0-9a-f]{64}$"


class MethodMetricSourceUnit(BaseModel):
    """Immutable Foundry unit representation captured for one selected method output."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    dimension: StrictStr = Field(min_length=1)
    symbol: StrictStr
    scale: float = Field(gt=0.0)

    @model_validator(mode="before")
    @classmethod
    def normalize_numeric_scale(cls, value: Any) -> Any:
        """Reject booleans and text while preserving Foundry's numeric scale value."""
        if isinstance(value, Mapping):
            payload = dict(value)
            raw_scale = payload.get("scale", 1.0)
            if isinstance(raw_scale, bool) or not isinstance(raw_scale, (int, float)):
                raise ValueError("method_metric_source_unit_scale_must_be_numeric")
            payload["scale"] = float(raw_scale)
            return payload
        raw_scale = getattr(value, "scale", None)
        if raw_scale is not None:
            if isinstance(raw_scale, bool) or not isinstance(raw_scale, (int, float)):
                raise ValueError("method_metric_source_unit_scale_must_be_numeric")
            return {
                "dimension": getattr(value, "dimension", None),
                "symbol": getattr(value, "symbol", None),
                "scale": float(raw_scale),
            }
        return value

    @model_validator(mode="after")
    def validate_finite_scale(self) -> MethodMetricSourceUnit:
        """Keep source unit scale finite and strictly positive."""
        if not math.isfinite(self.scale) or self.scale <= 0.0:
            raise ValueError("method_metric_source_unit_scale_must_be_finite_positive")
        return self


class MethodMetricPredicateEvidence(BaseModel):
    """One typed predicate outcome retained with a method metric observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_id: StrictStr = Field(min_length=1)
    classification: Literal[
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ]
    evidence_ref: SelectedMethodMetricArtifactRef | None = None
    evidence_sha256: StrictStr | None = Field(default=None, pattern=_SHA256_DIGEST_PATTERN)
    limitation: StrictStr | None = None

    @model_validator(mode="after")
    def validate_evidence_boundary(self) -> MethodMetricPredicateEvidence:
        """Require an evidence pointer for recomputed predicates and label limitations."""
        if self.evidence_ref is not None and self.evidence_ref.manifest_profile_sha256 is None:
            raise ValueError("method_metric_predicate_evidence_ref_requires_selected_profile")
        if self.classification in {"recomputed", "independently_reconciled"} and (
            self.evidence_ref is None
        ):
            raise ValueError("method_metric_predicate_evidence_basis_missing")
        if self.classification in {
            "consumer_asserted",
            "institutionally_supplied",
            "not_established",
        } and not (self.limitation and self.limitation.strip()):
            raise ValueError("method_metric_unestablished_predicate_requires_limitation")
        return self


class MethodMetricObservation(BaseModel):
    """Candidate-only, source-bound observation produced by the AD01 admission worker.

    The status and evidence fields describe the worker's result; they do not grant
    authority on their own. Consumers require the Runtime-owned selected projection
    association before using this observation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.3"] = "1.3"
    source_status: Literal["observed", "unavailable", "invalid", "not_established"]
    binding_set_ref: SelectedMethodMetricArtifactRef
    execution_bundle_ref: SelectedMethodMetricArtifactRef
    simulation_result_ref: SelectedMethodMetricArtifactRef
    environment_manifest_ref: SelectedMethodMetricArtifactRef | None = None
    output_ref: SelectedMethodMetricArtifactRef | None = None
    input_capture_ref: SelectedMethodMetricArtifactRef | None = None
    binding_id: StrictStr = Field(min_length=1)
    objective_id: StrictStr = Field(min_length=1)
    metric_id: StrictStr = Field(min_length=1)
    metric_unit_id: StrictStr | None = Field(default=None, min_length=1)
    objective_direction: StrictStr | None = None
    objective_weight: StrictStr | None = None
    objective_target_present: bool | None = None
    objective_target_sha256: StrictStr | None = Field(default=None, pattern=_SHA256_DIGEST_PATTERN)
    objective_spec_sha256: StrictStr | None = Field(default=None, pattern=_SHA256_DIGEST_PATTERN)
    configured_objective_count: StrictInt | None = Field(default=None, ge=1)
    occurrence_id: StrictStr | None = Field(default=None, min_length=1)
    invocation_id: StrictStr | None = Field(default=None, min_length=1)
    plan_index: StrictInt | None = Field(default=None, ge=0)
    node_id: StrictStr = Field(min_length=1)
    method_fqn: StrictStr = Field(min_length=1)
    method_version: StrictStr = Field(min_length=1)
    method_abi_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    method_abi_digest_algorithm: Literal["blake2b"]
    method_build_digest: StrictStr | None = Field(default=None, pattern=_SHA256_DIGEST_PATTERN)
    method_build_digest_scope: Literal["class_source_only", "unavailable"] = "unavailable"
    slot_id: StrictStr = Field(min_length=1)
    population_id: StrictStr | None = None
    axes: tuple[StrictStr, ...] = Field(default_factory=tuple)
    denominator_id: StrictStr | None = None
    time_role: StrictStr | None = None
    quantity_kind: StrictStr | None = None
    quantity_role: StrictStr | None = None
    source_unit: MethodMetricSourceUnit
    target_unit: UnitSpecType
    value: float | None = Field(default=None, strict=True)
    law_id: StrictStr = Field(min_length=1)
    law_version: StrictStr = Field(min_length=1)
    law_code_digest: StrictStr = Field(pattern=_SHA256_DIGEST_PATTERN)
    adapter_id: StrictStr = Field(min_length=1)
    adapter_version: StrictStr = Field(min_length=1)
    adapter_code_digest: StrictStr = Field(pattern=_SHA256_DIGEST_PATTERN)
    verifier_id: StrictStr = Field(min_length=1)
    verifier_revision: StrictStr = Field(min_length=1)
    verifier_code_digest: StrictStr = Field(pattern=_SHA256_DIGEST_PATTERN)
    checked_context_sha256: StrictStr = Field(pattern=_SHA256_DIGEST_PATTERN)
    predicate_evidence: tuple[MethodMetricPredicateEvidence, ...] = Field(default_factory=tuple)
    limitations: tuple[StrictStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="before")
    @classmethod
    def reject_coercible_metric_values(cls, value: Any) -> Any:
        """Reject bool/text values before Pydantic can coerce them to floats."""
        if isinstance(value, Mapping):
            payload = dict(value)
            raw_value = payload.get("value")
            if raw_value is not None:
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                    raise ValueError("method_metric_value_must_be_numeric")
                payload["value"] = float(raw_value)
            return payload
        return value

    @model_validator(mode="after")
    def validate_observation_boundary(self) -> MethodMetricObservation:
        """Require exact profiled source refs and a finite value for observed outputs."""
        expected_refs = (
            (self.binding_set_ref, _METHOD_METRIC_REF_KINDS["binding_set"]),
            (self.execution_bundle_ref, _METHOD_METRIC_REF_KINDS["execution_bundle"]),
            (self.simulation_result_ref, _METHOD_METRIC_REF_KINDS["simulation_result"]),
        )
        if self.environment_manifest_ref is not None:
            expected_refs += (
                (self.environment_manifest_ref, _METHOD_METRIC_REF_KINDS["environment"]),
            )
        for ref, kind in expected_refs:
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("method_metric_source_ref_must_be_selected_and_typed")
        if self.output_ref is not None and (
            self.output_ref.kind != _METHOD_METRIC_REF_KINDS["output"]
            or self.output_ref.media_type != "application/json"
            or self.output_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_metric_output_ref_must_be_selected_and_typed")
        if self.input_capture_ref is not None and (
            self.input_capture_ref.kind != _METHOD_METRIC_REF_KINDS["input_capture"]
            or self.input_capture_ref.media_type != "application/json"
            or self.input_capture_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_metric_input_capture_ref_must_be_selected_and_typed")
        if self.source_status == "observed":
            if (
                self.occurrence_id is None
                or self.invocation_id is None
                or self.plan_index is None
                or self.output_ref is None
                or self.input_capture_ref is None
                or self.environment_manifest_ref is None
                or self.population_id is None
                or not self.axes
                or self.time_role is None
                or self.quantity_kind is None
                or self.quantity_role is None
                or self.value is None
                or not math.isfinite(self.value)
                or not self.predicate_evidence
                or self.metric_unit_id is None
                or self.objective_direction is None
                or self.objective_weight is None
                or self.objective_target_present is None
                or self.objective_spec_sha256 is None
                or self.configured_objective_count is None
                or (self.objective_target_present != (self.objective_target_sha256 is not None))
            ):
                raise ValueError("observed_method_metric_source_basis_is_incomplete")
            try:
                from decimal import Decimal, InvalidOperation

                parsed_weight = Decimal(self.objective_weight)
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError("observed_method_metric_objective_weight_invalid") from exc
            if not parsed_weight.is_finite() or parsed_weight < 0:
                raise ValueError("observed_method_metric_objective_weight_invalid")
        elif self.value is not None:
            raise ValueError("non_observed_method_metric_cannot_carry_a_value")
        elif not any(note.strip() for note in self.limitations):
            raise ValueError("non_observed_method_metric_requires_limitation")
        if self.occurrence_id is None:
            if (
                self.invocation_id is not None
                or self.plan_index is not None
                or self.output_ref is not None
            ):
                raise ValueError("unmatched_method_metric_binding_cannot_claim_an_occurrence")
        elif (
            self.invocation_id is None
            or self.plan_index is None
            or self.occurrence_id != f"{self.invocation_id}:{self.plan_index}:{self.node_id}"
        ):
            raise ValueError("method_metric_occurrence_identity_mismatch")
        if self.method_build_digest_scope == "class_source_only":
            if self.method_build_digest is None:
                raise ValueError("class_source_method_build_scope_requires_digest")
        elif self.method_build_digest is not None:
            raise ValueError("unavailable_method_build_scope_cannot_carry_digest")
        if len({item.predicate_id for item in self.predicate_evidence}) != len(
            self.predicate_evidence
        ):
            raise ValueError("method_metric_predicate_evidence_ids_must_be_unique")
        return self


def method_metric_observation_input_refs(
    observations: tuple[MethodMetricObservation, ...],
) -> tuple[tuple[str, SelectedMethodMetricArtifactRef], ...]:
    """Return deterministic selected CAS input edges for inline method observations."""
    by_role: dict[str, SelectedMethodMetricArtifactRef] = {}
    for observation in observations:
        refs: list[tuple[str, SelectedMethodMetricArtifactRef | None]] = [
            ("method_metric_binding_set", observation.binding_set_ref),
            ("method_execution_bundle", observation.execution_bundle_ref),
            ("method_simulation_result", observation.simulation_result_ref),
            ("method_environment_manifest", observation.environment_manifest_ref),
            (
                f"method_metric_output:{observation.binding_id}:"
                f"{observation.occurrence_id or 'unmatched'}",
                observation.output_ref,
            ),
            (
                f"method_metric_input_capture:{observation.binding_id}:"
                f"{observation.occurrence_id or 'unmatched'}",
                observation.input_capture_ref,
            ),
        ]
        refs.extend(
            (
                "method_metric_evidence:"
                f"{observation.binding_id}:{observation.occurrence_id or 'unmatched'}:"
                f"{evidence.predicate_id}",
                evidence.evidence_ref,
            )
            for evidence in observation.predicate_evidence
        )
        for role, ref in refs:
            if ref is None:
                continue
            if ref.manifest_profile_sha256 is None:
                raise ValueError("method_metric_input_ref_requires_selected_profile")
            prior = by_role.get(role)
            if prior is not None and artifact_ref_identity_key(prior) != artifact_ref_identity_key(
                ref
            ):
                raise ValueError("method_metric_input_role_conflicts_across_observations")
            by_role[role] = ref
    return tuple((role, by_role[role]) for role in sorted(by_role))


def observe_source_government_balance(
    store: Any,
    *,
    simulation_result_ref: ArtifactRef | None,
    metrics_ref: ArtifactRef | None,
    state_snapshot_ref: ArtifactRef | None = None,
) -> SourceMetricObservation:
    """Recompute a global USD balance-stock observation from exact Foundry artifacts.

    This routine deliberately stops at the existing ``government.balance`` stock
    contract. It does not assign a fiscal period or map that stock to the separate
    ``budget_deficit`` objective.
    """
    source_result_ref = simulation_result_ref
    source_metrics_ref = metrics_ref
    source_snapshot_ref = state_snapshot_ref

    def not_observed(
        status: Literal["unavailable", "invalid", "not_established"],
        reason: str,
        *,
        snapshot_ref: ArtifactRef | None = source_snapshot_ref,
    ) -> SourceMetricObservation:
        return SourceMetricObservation(
            source_status=status,
            predicate_status="not_established",
            source_result_ref=source_result_ref,
            source_metrics_ref=source_metrics_ref,
            source_snapshot_ref=snapshot_ref,
            time_basis="not_established",
            limitation=reason,
        )

    if source_result_ref is None or source_metrics_ref is None:
        return not_observed("unavailable", "selected_simulation_result_or_metrics_ref_missing")

    try:
        from polisyos.core.artifacts import (
            artifact_manifest_profile_sha256,
            load_core_json_artifact,
        )
        from polisyos.core.contracts.foundry import Metrics, SimulationResult, StateSnapshot
        from polisyos.foundry.execute import load_state_snapshot
        from polisyos.ir.kernel import (
            DEFAULT_METRIC_REGISTRY,
            DEFAULT_SLOT_REGISTRY,
            SlotKind,
            SlotScope,
        )

        def require_selected_ref(ref: ArtifactRef, expected_kind: str) -> Any:
            if ref.kind != expected_kind or ref.manifest_profile_sha256 is None:
                raise ValueError("source_artifact_selected_profile_missing_or_wrong_kind")
            manifest = store.get_manifest(ref)
            if (
                manifest.artifact_id != ref.artifact_id
                or manifest.kind != expected_kind
                or manifest.media_type != ref.media_type
                or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
            ):
                raise ValueError("source_artifact_manifest_profile_mismatch")
            return manifest

        result_manifest = require_selected_ref(source_result_ref, "foundry.simulation_result")
        metrics_manifest = require_selected_ref(source_metrics_ref, Metrics.ARTIFACT_KIND)
        if (
            result_manifest.artifact_schema is None
            or result_manifest.artifact_schema.name != SimulationResult.ARTIFACT_SCHEMA_NAME
            or metrics_manifest.artifact_schema is None
            or metrics_manifest.artifact_schema.name != Metrics.ARTIFACT_SCHEMA_NAME
            or metrics_manifest.artifact_schema.version != Metrics.ARTIFACT_SCHEMA_VERSION
        ):
            raise ValueError("source_artifact_schema_identity_unavailable")

        simulation = SimulationResult.model_validate(
            load_core_json_artifact(store, source_result_ref)
        )
        if (
            simulation.schema_version not in {"1.3", "1.4"}
            or result_manifest.artifact_schema.version != simulation.schema_version
        ):
            return not_observed("invalid", "simulation_result_schema_version_mismatch")
        if simulation.metrics_ref.model_dump(mode="json") != source_metrics_ref.model_dump(
            mode="json"
        ):
            return not_observed("invalid", "simulation_result_metrics_ref_mismatch")
        embedded_snapshot_ref = simulation.state_snapshot_ref
        if state_snapshot_ref is not None and (
            embedded_snapshot_ref is None
            or embedded_snapshot_ref.model_dump(mode="json")
            != state_snapshot_ref.model_dump(mode="json")
        ):
            return not_observed(
                "invalid",
                "simulation_result_state_snapshot_ref_mismatch",
                snapshot_ref=embedded_snapshot_ref,
            )
        source_snapshot_ref = embedded_snapshot_ref
        if source_snapshot_ref is None:
            return not_observed("not_established", "simulation_state_snapshot_ref_missing")
        snapshot_manifest = require_selected_ref(source_snapshot_ref, "foundry.state_snapshot")
        if (
            snapshot_manifest.artifact_schema is None
            or snapshot_manifest.artifact_schema.name != "polisyos.core.StateSnapshot"
        ):
            raise ValueError("state_snapshot_schema_identity_unavailable")

        metrics = Metrics.model_validate(load_core_json_artifact(store, source_metrics_ref))
        snapshot = StateSnapshot.model_validate(load_core_json_artifact(store, source_snapshot_ref))
        expected_snapshot_schema = StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION.get(
            snapshot.schema_version
        )
        if snapshot_manifest.artifact_schema.version != expected_snapshot_schema:
            return not_observed(
                "invalid",
                "state_snapshot_schema_version_mismatch",
                snapshot_ref=source_snapshot_ref,
            )
        if snapshot.layout is not None:
            return not_observed(
                "invalid",
                "simulation_state_snapshot_layout_not_global_state",
                snapshot_ref=source_snapshot_ref,
            )
        if snapshot.step is None:
            return not_observed(
                "not_established",
                "simulation_step_not_recorded",
                snapshot_ref=source_snapshot_ref,
            )
        if (
            isinstance(snapshot.step, bool)
            or not isinstance(snapshot.step, int)
            or snapshot.step < 0
        ):
            return not_observed(
                "invalid", "simulation_step_invalid", snapshot_ref=source_snapshot_ref
            )

        slot = DEFAULT_SLOT_REGISTRY.slots.get("government.balance")
        metric = DEFAULT_METRIC_REGISTRY.metrics.get("government_balance")
        if (
            slot is None
            or metric is None
            or slot.state_path != "government_balance"
            or slot.unit is None
            or slot.unit.unit_id != "usd"
            or slot.scope is not SlotScope.GLOBAL
            or slot.kind is not SlotKind.STOCK
        ):
            return not_observed(
                "not_established",
                "canonical_balance_slot_contract_changed",
                snapshot_ref=source_snapshot_ref,
            )

        raw_metric = metrics.values.get("government_balance")
        if raw_metric is None:
            return not_observed(
                "unavailable", "government_balance_metric_missing", snapshot_ref=source_snapshot_ref
            )
        if isinstance(raw_metric, bool) or not isinstance(raw_metric, (int, float)):
            return not_observed(
                "invalid",
                "government_balance_metric_not_numeric",
                snapshot_ref=source_snapshot_ref,
            )
        metric_value = float(raw_metric)
        if not math.isfinite(metric_value):
            return not_observed(
                "invalid",
                "government_balance_metric_not_finite",
                snapshot_ref=source_snapshot_ref,
            )

        other_balance = metrics.values.get("gov_balance")
        if other_balance is not None:
            if isinstance(other_balance, bool) or not isinstance(other_balance, (int, float)):
                return not_observed(
                    "invalid",
                    "government_balance_alias_not_numeric",
                    snapshot_ref=source_snapshot_ref,
                )
            alias_value = float(other_balance)
            if not math.isfinite(alias_value) or alias_value != metric_value:
                return not_observed(
                    "invalid", "government_balance_alias_conflict", snapshot_ref=source_snapshot_ref
                )

        materialized_state = load_state_snapshot(store, snapshot_ref=source_snapshot_ref)
        state_value = float(materialized_state.government_balance)
        if not math.isfinite(state_value) or state_value != metric_value:
            return not_observed(
                "invalid",
                "government_balance_metrics_snapshot_mismatch",
                snapshot_ref=source_snapshot_ref,
            )

        return SourceMetricObservation(
            source_status="observed",
            predicate_status="recomputed",
            metric_id="government_balance",
            slot_id="government.balance",
            value=metric_value,
            unit_id=slot.unit.unit_id,
            scope=slot.scope.value,
            quantity_kind=slot.kind.value,
            simulation_step=snapshot.step,
            time_basis="simulation_step",
            source_result_ref=source_result_ref,
            source_metrics_ref=source_metrics_ref,
            source_snapshot_ref=source_snapshot_ref,
            limitation="government_balance_stock_not_budget_deficit_period_measurement",
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError, OverflowError):
        return not_observed("invalid", "source_artifact_readback_or_contract_failed")


def recompute_source_government_balance(
    store: Any,
    observation: SourceMetricObservation,
) -> SourceMetricObservation:
    """Re-resolve every exact source ref and reproduce one reported observation."""
    return observe_source_government_balance(
        store,
        simulation_result_ref=observation.source_result_ref,
        metrics_ref=observation.source_metrics_ref,
        state_snapshot_ref=observation.source_snapshot_ref,
    )


def source_observation_input_refs(
    observation: SourceMetricObservation,
) -> tuple[tuple[str, ArtifactRef], ...]:
    """Return exact CAS input edges for all selected source artifacts in an observation."""
    return tuple(
        (role, ref)
        for role, ref in (
            ("source_simulation_result", observation.source_result_ref),
            ("source_metrics", observation.source_metrics_ref),
            ("source_state_snapshot", observation.source_snapshot_ref),
        )
        if ref is not None
    )


def objective_metrics_without_unestablished_fiscal_source(
    metrics: Mapping[str, Any] | None,
    observation: SourceMetricObservation | None,
) -> dict[str, Any] | None:
    """Keep an unmapped physical balance out of the budget-deficit score input."""
    if not isinstance(metrics, Mapping):
        return None if metrics is None else dict(metrics)
    if observation is None or observation.source_status not in {"observed", "invalid"}:
        return dict(metrics)
    return {
        key: value
        for key, value in metrics.items()
        if key not in {*_BALANCE_ALIASES, *_DEFICIT_ALIASES}
    }


def _read_metric_aliases(results: dict[str, Any], aliases: tuple[str, ...]) -> object:
    """Read one numeric metric from aliases without hiding conflicts or invalid values."""
    values: list[float] = []
    for alias in aliases:
        raw_value = results.get(alias, _MISSING)
        if raw_value is _MISSING or raw_value is None:
            continue
        if isinstance(raw_value, bool):
            return _INVALID
        try:
            value = float(raw_value)
        except (OverflowError, TypeError, ValueError):
            return _INVALID
        if not math.isfinite(value):
            return _INVALID
        values.append(value)

    if not values:
        return _MISSING
    if any(value != values[0] for value in values[1:]):
        return _INVALID
    return values[0]


class ObjectiveScoreStatus(str, Enum):
    """Availability of a score on its declared objective basis."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    NOT_ESTABLISHED = "not_established"


_POLICY_RUNTIME_INVOCATION_FIELDS = (
    "evaluation_attempt_id",
    "requested_draw_count",
    "requested_draw_source",
    "effective_estimation_config_sha256",
)
_POLICY_RUNTIME_INVOCATION_ABSENT = object()


class _PolicyRuntimeInvocationBinding(BaseModel):
    """Typed current-schema runtime tuple, including explicitly limited identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_attempt_id: str | None = Field(default=None, min_length=1)
    requested_draw_count: int | None = Field(default=None, ge=0, strict=True)
    requested_draw_source: Literal["effective_estimation_config", "unavailable"] | None = None
    effective_estimation_config_sha256: str | None = Field(
        default=None, pattern=r"^[a-f0-9]{64}$", strict=True
    )

    @model_validator(mode="after")
    def _validate_draw_request_binding(self) -> _PolicyRuntimeInvocationBinding:
        if self.requested_draw_source == "effective_estimation_config":
            if self.effective_estimation_config_sha256 is None:
                raise ValueError("effective draw configuration digest is required")
        elif self.requested_draw_source == "unavailable":
            if (
                self.requested_draw_count is not None
                or self.effective_estimation_config_sha256 is not None
            ):
                raise ValueError("unavailable draw source cannot carry a request")
        elif (
            self.requested_draw_count is not None
            or self.effective_estimation_config_sha256 is not None
        ):
            raise ValueError("draw request values require a declared source")
        return self


def _policy_runtime_invocation_binding(value: Any) -> _PolicyRuntimeInvocationBinding | None:
    """Parse supplied tuple fields without requiring an invocation to be identifiable."""
    if not isinstance(value, Mapping):
        return None
    supplied = {name: value[name] for name in _POLICY_RUNTIME_INVOCATION_FIELDS if name in value}
    try:
        return _PolicyRuntimeInvocationBinding.model_validate(supplied)
    except (TypeError, ValueError, ValidationError):
        return None


def _policy_runtime_invocation_bindings_status(left: Any, right: Any) -> ObjectiveScoreStatus:
    """Classify absent, malformed-present, limited, and fully bound invocation inputs."""
    left_present = left is not _POLICY_RUNTIME_INVOCATION_ABSENT
    right_present = right is not _POLICY_RUNTIME_INVOCATION_ABSENT
    if (left_present and not isinstance(left, Mapping)) or (
        right_present and not isinstance(right, Mapping)
    ):
        return ObjectiveScoreStatus.INVALID
    left_binding = _policy_runtime_invocation_binding(left) if left_present else None
    right_binding = _policy_runtime_invocation_binding(right) if right_present else None
    if (left_present and left_binding is None) or (right_present and right_binding is None):
        return ObjectiveScoreStatus.INVALID
    if not left_present or not right_present:
        return ObjectiveScoreStatus.NOT_ESTABLISHED
    assert isinstance(left, Mapping)
    assert isinstance(right, Mapping)
    assert left_binding is not None
    assert right_binding is not None
    shared_fields = set(left).intersection(right).intersection(_POLICY_RUNTIME_INVOCATION_FIELDS)
    if any(left[name] != right[name] for name in shared_fields):
        return ObjectiveScoreStatus.INVALID
    if (
        not set(_POLICY_RUNTIME_INVOCATION_FIELDS).issubset(left)
        or not set(_POLICY_RUNTIME_INVOCATION_FIELDS).issubset(right)
        or left_binding.evaluation_attempt_id is None
        or left_binding.requested_draw_source is None
    ):
        return ObjectiveScoreStatus.NOT_ESTABLISHED
    if left_binding != right_binding:
        return ObjectiveScoreStatus.INVALID
    return ObjectiveScoreStatus.AVAILABLE


@dataclass(frozen=True, slots=True)
class ObjectiveScoreAssessment:
    """Carry one recomputable objective score and its selected input basis.

    The assessment is a record, not authority: consumers that cross a persistence
    boundary must recompute it from the retained source result before admitting the
    value to comparison, training, or selection.
    """

    objective_ref: str | None
    rule_spec: str | None
    required_input_groups: tuple[tuple[str, ...], ...]
    source_field_names: tuple[str, ...]
    source_values: tuple[tuple[str, float], ...]
    source_sha256: str | None
    value: float | None
    status: ObjectiveScoreStatus
    limitation: str | None = None
    source_unit_bindings: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.status is ObjectiveScoreStatus.AVAILABLE:
            if (
                self.value is None
                or not math.isfinite(self.value)
                or not self.objective_ref
                or not self.rule_spec
                or not self.source_sha256
                or any(
                    not set(group).intersection(self.source_field_names)
                    for group in self.required_input_groups
                )
            ):
                raise ValueError("available score assessment lacks its complete source basis")
            try:
                rule_payload = json.loads(self.rule_spec)
            except (TypeError, ValueError, json.JSONDecodeError):
                raise ValueError("available score assessment has no canonical selected rule")
            if not isinstance(rule_payload, dict):
                raise ValueError("available score assessment has no canonical selected rule")
            rule_kind = rule_payload.get("kind")
            if rule_kind in {
                "gdp_growth",
                "budget_deficit",
                "inequality",
                "employment",
                "search_metric",
                "default_policy_scalar",
                "composite",
                "policy_vector_channel",
                "policy_vector_legacy_scalar",
                "completed_method_metric_objectives",
            } and (
                not self.source_unit_bindings
                or any(
                    not name
                    or not unit
                    or unit != unit.strip()
                    or f"metric_units.{name}" not in self.source_field_names
                    for name, unit in self.source_unit_bindings
                )
            ):
                raise ValueError("available measured objective lacks exact source unit bindings")
        elif self.value is not None:
            raise ValueError("non-available score assessment cannot carry a numeric value")

    def to_payload(self) -> dict[str, Any]:
        """Return the strict JSON-compatible representation used by history artifacts."""
        return {
            "schema_version": "2.0",
            "objective_ref": self.objective_ref,
            "rule_spec": self.rule_spec,
            "required_input_groups": [list(group) for group in self.required_input_groups],
            "source_field_names": list(self.source_field_names),
            "source_values": {name: value for name, value in self.source_values},
            "source_unit_bindings": {name: unit for name, unit in self.source_unit_bindings},
            "source_sha256": self.source_sha256,
            "value": self.value,
            "status": self.status.value,
            "limitation": self.limitation,
        }

    @classmethod
    def from_payload(cls, payload: Any) -> ObjectiveScoreAssessment:
        """Parse one versioned assessment; old or malformed payloads stay unbound."""
        if not isinstance(payload, dict) or payload.get("schema_version") != "2.0":
            return _unestablished_score_assessment(
                "objective_assessment_legacy_or_schema_unavailable"
            )
        try:
            groups = tuple(
                tuple(str(name) for name in group) for group in payload["required_input_groups"]
            )
            raw_values = payload["source_values"]
            if not isinstance(raw_values, dict):
                raise TypeError("source_values must be an object")
            source_values = tuple(
                sorted((str(name), float(value)) for name, value in raw_values.items())
            )
            if any(not math.isfinite(value) for _, value in source_values):
                raise ValueError("source values must be finite")
            raw_unit_bindings = payload["source_unit_bindings"]
            if not isinstance(raw_unit_bindings, dict):
                raise TypeError("source unit bindings must be an object")
            if any(
                not isinstance(name, str)
                or not isinstance(unit, str)
                or not unit.strip()
                or unit != unit.strip()
                for name, unit in raw_unit_bindings.items()
            ):
                raise ValueError("source unit bindings must use canonical non-empty strings")
            source_unit_bindings = tuple(sorted(raw_unit_bindings.items()))
            return cls(
                objective_ref=payload.get("objective_ref"),
                rule_spec=payload.get("rule_spec"),
                required_input_groups=groups,
                source_field_names=tuple(str(name) for name in payload["source_field_names"]),
                source_values=source_values,
                source_unit_bindings=source_unit_bindings,
                source_sha256=payload.get("source_sha256"),
                value=None if payload.get("value") is None else float(payload["value"]),
                status=ObjectiveScoreStatus(payload["status"]),
                limitation=payload.get("limitation"),
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            return _unestablished_score_assessment("objective_assessment_payload_invalid")


@dataclass(frozen=True)
class ObjectiveScoreAdmission:
    """Carry one consumer-recomputed score status and the basis it checked.

    This record is a result of replay, not authority by itself. Consumers at an
    action boundary must recompute it from ``reported_assessment`` and the live
    source. The reported and replayed assessments remain separate so a changed
    source cannot turn a previous invalidation into an absent score.
    """

    __slots__ = (
        "_policyos_ephemeral_score_owner_context",
        "predicate_status",
        "reason",
        "recomputed_assessment",
        "reported_assessment",
        "status",
    )

    status: ObjectiveScoreStatus
    predicate_status: Literal["recomputed", "not_established"]
    reported_assessment: ObjectiveScoreAssessment | None
    recomputed_assessment: ObjectiveScoreAssessment | None
    reason: str

    @property
    def _owner_context(self) -> object | None:
        """Return an in-process basis held outside fields and serializer-visible state."""
        return getattr(self, "_policyos_ephemeral_score_owner_context", None)

    def __post_init__(self) -> None:
        if self.predicate_status not in {"recomputed", "not_established"}:
            raise ValueError("score admission predicate status is unsupported")
        if not self.reason:
            raise ValueError("score admission requires a reason")
        if self.status is ObjectiveScoreStatus.AVAILABLE:
            if (
                self.predicate_status != "recomputed"
                or self.reported_assessment is None
                or self.recomputed_assessment is None
                or self.reported_assessment.status is not ObjectiveScoreStatus.AVAILABLE
                or self.recomputed_assessment != self.reported_assessment
            ):
                raise ValueError("available admission requires a matching recomputed assessment")
        elif self.status is ObjectiveScoreStatus.UNAVAILABLE:
            if (
                self.predicate_status != "recomputed"
                or self.reported_assessment is None
                or self.recomputed_assessment != self.reported_assessment
                or self.reported_assessment.status is not ObjectiveScoreStatus.UNAVAILABLE
            ):
                raise ValueError("unavailable admission requires a matching recomputed assessment")
        elif self.status is ObjectiveScoreStatus.NOT_ESTABLISHED:
            if self.predicate_status == "recomputed" and (
                self.reported_assessment is None
                or self.recomputed_assessment != self.reported_assessment
                or self.reported_assessment.status is not ObjectiveScoreStatus.NOT_ESTABLISHED
            ):
                raise ValueError("recomputed unestablished admission requires matching evidence")
        elif self.status is ObjectiveScoreStatus.INVALID and (
            self.predicate_status == "recomputed" and self.recomputed_assessment is None
        ):
            raise ValueError("recomputed invalid admission requires replay evidence")

    def to_payload(self) -> dict[str, Any]:
        """Return the versioned typed record used by persisted projections."""
        return {
            "schema_version": "1.0",
            "status": self.status.value,
            "predicate_status": self.predicate_status,
            "reported_assessment": (
                None if self.reported_assessment is None else self.reported_assessment.to_payload()
            ),
            "recomputed_assessment": (
                None
                if self.recomputed_assessment is None
                else self.recomputed_assessment.to_payload()
            ),
            "reason": self.reason,
        }

    def to_surface_payload(self) -> dict[str, Any]:
        """Project status and hashes without copying selected source values."""
        reported = self.reported_assessment
        recomputed = self.recomputed_assessment
        return {
            "schema_version": "1.0",
            "status": self.status.value,
            "predicate_status": self.predicate_status,
            "reason": self.reason,
            "reported_assessment_status": (None if reported is None else reported.status.value),
            "reported_source_sha256": None if reported is None else reported.source_sha256,
            "recomputed_assessment_status": (
                None if recomputed is None else recomputed.status.value
            ),
            "recomputed_source_sha256": None if recomputed is None else recomputed.source_sha256,
        }

    def __deepcopy__(self, memo: dict[int, Any]) -> ObjectiveScoreAdmission:
        """Copy only persisted fields; owner context must be reacquired after copying."""
        copied = type(self)(
            status=self.status,
            predicate_status=self.predicate_status,
            reported_assessment=self.reported_assessment,
            recomputed_assessment=self.recomputed_assessment,
            reason=self.reason,
        )
        memo[id(self)] = copied
        return copied

    def __reduce__(self) -> tuple[Any, tuple[Any, ...]]:
        """Keep pickle snapshots limited to the declared, reloadable score record."""
        return (
            type(self),
            (
                self.status,
                self.predicate_status,
                self.reported_assessment,
                self.recomputed_assessment,
                self.reason,
            ),
        )

    @classmethod
    def from_payload(cls, payload: Any) -> ObjectiveScoreAdmission:
        """Parse a complete admission record without treating malformed data as absence."""
        required = {
            "schema_version",
            "status",
            "predicate_status",
            "reported_assessment",
            "recomputed_assessment",
            "reason",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("score admission payload is malformed")
        if payload["schema_version"] != "1.0":
            raise ValueError("score admission schema is unsupported")

        def parse_assessment(raw: Any) -> ObjectiveScoreAssessment | None:
            if raw is None:
                return None
            if not isinstance(raw, dict) or raw.get("schema_version") != "2.0":
                raise ValueError("score admission assessment is malformed")
            assessment = ObjectiveScoreAssessment.from_payload(raw)
            if assessment.to_payload() != raw:
                raise ValueError("score admission assessment failed exact readback")
            return assessment

        return cls(
            status=ObjectiveScoreStatus(payload["status"]),
            predicate_status=payload["predicate_status"],
            reported_assessment=parse_assessment(payload["reported_assessment"]),
            recomputed_assessment=parse_assessment(payload["recomputed_assessment"]),
            reason=payload["reason"],
        )


def _attach_score_admission_owner_context(
    admission: ObjectiveScoreAdmission,
    owner_context: object | None,
) -> ObjectiveScoreAdmission:
    """Attach an ephemeral replay capability outside declared serialization fields."""
    if owner_context is not None:
        object.__setattr__(admission, "_policyos_ephemeral_score_owner_context", owner_context)
    return admission


def _unestablished_score_assessment(reason: str) -> ObjectiveScoreAssessment:
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


def canonical_objective_rule_spec(rule: dict[str, Any]) -> str:
    """Serialize a configured objective rule to its stable identity string."""
    return json.dumps(rule, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _make_score_assessment(
    *,
    rule: dict[str, Any],
    required_input_groups: tuple[tuple[str, ...], ...],
    source_fields: tuple[str, ...],
    source_values: tuple[tuple[str, float], ...],
    status: ObjectiveScoreStatus,
    value: float | None,
    limitation: str | None = None,
    source_unit_bindings: tuple[tuple[str, str], ...] = (),
) -> ObjectiveScoreAssessment:
    """Create a deterministic typed assessment for an owned score producer."""
    rule_spec = canonical_objective_rule_spec(rule)
    objective_ref = hashlib.sha256(rule_spec.encode("utf-8")).hexdigest()
    digest_payload = json.dumps(
        {
            "rule_spec": rule_spec,
            "source_fields": source_fields,
            "source_values": source_values,
            "source_unit_bindings": source_unit_bindings,
            "value": value,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    source_sha256 = (
        hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
        if status is ObjectiveScoreStatus.AVAILABLE
        else None
    )
    return ObjectiveScoreAssessment(
        objective_ref=objective_ref,
        rule_spec=rule_spec,
        required_input_groups=required_input_groups,
        source_field_names=source_fields,
        source_values=source_values,
        source_sha256=source_sha256,
        value=value,
        status=status,
        limitation=limitation,
        source_unit_bindings=source_unit_bindings,
    )


def _validate_objective_score_state(
    objective_value: float | None, score_status: ObjectiveScoreStatus
) -> None:
    if score_status is ObjectiveScoreStatus.AVAILABLE and objective_value is None:
        raise ValueError("available objective score requires a value")
    if score_status in {
        ObjectiveScoreStatus.UNAVAILABLE,
        ObjectiveScoreStatus.INVALID,
    } and (objective_value is not None):
        raise ValueError("unavailable objective score cannot carry a value")
    if score_status is ObjectiveScoreStatus.NOT_ESTABLISHED and objective_value is not None:
        if isinstance(objective_value, bool) or not math.isfinite(float(objective_value)):
            raise ValueError("unbound diagnostic objective value must remain finite")


class OptimizationDirection(str, Enum):
    """Direction for objective optimization."""

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


@dataclass(frozen=True)
class ObjectiveValue:
    """
    Evaluated value of a single objective.

    Attributes:
        name: Objective identifier
        raw_value: Actual metric value from simulation
        direction: Whether to minimize or maximize
        weight: Importance weight for composite objectives
        is_satisfied: Whether value meets any constraint thresholds
    """

    name: str
    raw_value: float
    direction: OptimizationDirection
    weight: float = 1.0
    is_satisfied: bool = True
    threshold: float | None = None
    score_status: ObjectiveScoreStatus = ObjectiveScoreStatus.NOT_ESTABLISHED
    score_assessment: ObjectiveScoreAssessment | None = None

    def __post_init__(self) -> None:
        if self.score_assessment is None:
            if self.score_status is ObjectiveScoreStatus.AVAILABLE:
                object.__setattr__(self, "score_status", ObjectiveScoreStatus.NOT_ESTABLISHED)
            return
        if self.score_status is not self.score_assessment.status:
            raise ValueError("objective value status must match its assessment")
        if self.score_status is ObjectiveScoreStatus.AVAILABLE and (
            self.score_assessment.value != self.raw_value
        ):
            raise ValueError("objective value differs from its score assessment")

    @property
    def normalized_value(self) -> float:
        """
        Normalize to minimization convention.

        This enables uniform comparison: lower is always better.
        """
        if self.score_status is not ObjectiveScoreStatus.AVAILABLE:
            return math.nan
        if self.direction == OptimizationDirection.MAXIMIZE:
            return -self.raw_value
        return self.raw_value

    @property
    def weighted_value(self) -> float:
        """Return normalized value scaled by weight."""
        return self.normalized_value * self.weight


class SearchObjective(Protocol):
    """Protocol for search objectives."""

    @property
    def name(self) -> str:
        """Unique identifier for this objective."""

    @property
    def direction(self) -> OptimizationDirection:
        """Optimization direction."""

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        """
        Evaluate objective from simulation results.

        Args:
            results: Dict containing simulation outputs (gdp_change, etc.)

        Returns:
            ObjectiveValue with evaluation details
        """


class BaseObjective(ABC):
    """Abstract base class for objectives with common functionality."""

    def __init__(
        self,
        weight: float = 1.0,
        threshold: float | None = None,
        *,
        expected_unit: str | None = None,
    ):
        if expected_unit is not None and (
            not isinstance(expected_unit, str)
            or not expected_unit.strip()
            or expected_unit != expected_unit.strip()
        ):
            raise ValueError("expected_unit must be a non-empty canonical unit string")
        self._weight = weight
        self._threshold = threshold
        self._expected_unit = expected_unit

    @property
    def expected_unit(self) -> str | None:
        """Return the explicitly selected measurement unit, if configured."""
        return self._expected_unit

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def direction(self) -> OptimizationDirection: ...

    @abstractmethod
    def _extract_value(self, results: dict[str, Any]) -> float:
        """Extract raw metric value from results dict."""
        ...

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        assessment = _assess_configured_objective(self, results)
        raw = assessment.value if assessment.value is not None else math.nan
        score_status = assessment.status
        is_satisfied = score_status is ObjectiveScoreStatus.AVAILABLE
        if self._threshold is not None and is_satisfied:
            if self.direction == OptimizationDirection.MINIMIZE:
                is_satisfied = raw <= self._threshold
            else:
                is_satisfied = raw >= self._threshold

        return ObjectiveValue(
            name=self.name,
            raw_value=raw,
            direction=self.direction,
            weight=self._weight,
            is_satisfied=is_satisfied,
            threshold=self._threshold,
            score_status=score_status,
            score_assessment=assessment,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Concrete Objective Implementations
# ─────────────────────────────────────────────────────────────────────────────


class GDPGrowthObjective(BaseObjective):
    """Maximize GDP growth rate."""

    @property
    def name(self) -> str:
        return "gdp_growth"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MAXIMIZE

    def _extract_value(self, results: dict[str, Any]) -> float:
        value, status = _read_finite_numeric_metric(results, "gdp_change")
        return value if status is ObjectiveScoreStatus.AVAILABLE and value is not None else math.nan


class BudgetDeficitObjective(BaseObjective):
    """Minimize budget deficit (absolute value)."""

    @property
    def name(self) -> str:
        return "budget_deficit"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: dict[str, Any]) -> float:
        assessment = _assess_configured_objective(self, results)
        return (
            assessment.value
            if assessment.status is ObjectiveScoreStatus.AVAILABLE and assessment.value is not None
            else math.nan
        )

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        """Preserve whether a fiscal value was absent or malformed."""
        assessment = _assess_configured_objective(self, results)
        raw = assessment.value if assessment.value is not None else math.nan
        status = assessment.status

        is_satisfied = status is ObjectiveScoreStatus.AVAILABLE
        if self._threshold is not None and is_satisfied:
            is_satisfied = raw <= self._threshold
        return ObjectiveValue(
            name=self.name,
            raw_value=raw,
            direction=self.direction,
            weight=self._weight,
            is_satisfied=is_satisfied,
            threshold=self._threshold,
            score_status=status,
            score_assessment=assessment,
        )


_DefaultSearchObjectiveLimitation = Literal[
    "search_objective_fiscal_measurement_unavailable",
    "search_objective_fiscal_measurement_invalid",
]
_DEFAULT_SEARCH_OBJECTIVE_FALLBACK_LIMITATION: _DefaultSearchObjectiveLimitation = (
    "search_objective_fiscal_measurement_unavailable"
)


@dataclass(frozen=True)
class _DefaultSearchObjectiveAssessment:
    """One source-derived scalar assessment and its typed limitations."""

    objective_value: float | None
    score_status: ObjectiveScoreStatus
    score_assessment: ObjectiveScoreAssessment
    limitations: tuple[_DefaultSearchObjectiveLimitation, ...] = ()

    def __post_init__(self) -> None:
        _validate_objective_score_state(self.objective_value, self.score_status)


def _read_finite_numeric_metric(
    results: dict[str, Any], name: str
) -> tuple[float | None, ObjectiveScoreStatus]:
    """Read a declared numeric field, distinguishing absence from null/invalid input."""
    raw = results.get(name, _MISSING)
    if raw is _MISSING:
        return None, ObjectiveScoreStatus.UNAVAILABLE
    if isinstance(raw, bool):
        return None, ObjectiveScoreStatus.INVALID
    try:
        value = float(raw)
    except (OverflowError, TypeError, ValueError):
        return None, ObjectiveScoreStatus.INVALID
    if not math.isfinite(value):
        return None, ObjectiveScoreStatus.INVALID
    return value, ObjectiveScoreStatus.AVAILABLE


def _assess_search_fiscal_measurement(
    results: dict[str, Any], *, expected_unit: str | None = None
) -> tuple[float | None, ObjectiveScoreStatus]:
    """Admit the existing fiscal value only when actual aliases support it."""
    # Explicit null on the primary aliases remains an absence signal under the
    # B108 fallback contract; malformed non-null values remain invalid.
    objective = BudgetDeficitObjective(expected_unit=expected_unit).evaluate(results)
    has_usable_marker = "budget_deficit_objective_usable" in results
    has_value_marker = "budget_deficit_objective_value" in results
    if not has_usable_marker and not has_value_marker:
        return (
            (objective.raw_value, ObjectiveScoreStatus.AVAILABLE)
            if objective.score_status is ObjectiveScoreStatus.AVAILABLE
            else (None, objective.score_status)
        )
    if not has_usable_marker or not has_value_marker:
        return None, ObjectiveScoreStatus.INVALID

    usable = results["budget_deficit_objective_usable"]
    if type(usable) is not bool:
        return None, ObjectiveScoreStatus.INVALID
    if usable is False:
        if results["budget_deficit_objective_value"] is not None:
            return None, ObjectiveScoreStatus.INVALID
        if objective.score_status not in {
            ObjectiveScoreStatus.UNAVAILABLE,
            ObjectiveScoreStatus.NOT_ESTABLISHED,
        }:
            return None, ObjectiveScoreStatus.INVALID
        return None, objective.score_status

    normalized_value, value_status = _read_finite_numeric_metric(
        results, "budget_deficit_objective_value"
    )
    if normalized_value is None or value_status is not ObjectiveScoreStatus.AVAILABLE:
        return None, ObjectiveScoreStatus.INVALID
    if objective.score_status is ObjectiveScoreStatus.INVALID:
        return None, ObjectiveScoreStatus.INVALID
    if objective.score_status is not ObjectiveScoreStatus.AVAILABLE:
        return None, ObjectiveScoreStatus.INVALID
    if objective.raw_value != normalized_value:
        return None, ObjectiveScoreStatus.INVALID
    return normalized_value, ObjectiveScoreStatus.AVAILABLE


def _assess_default_search_objective(
    results: dict[str, Any], *, expected_unit: str | None = None
) -> _DefaultSearchObjectiveAssessment:
    """Use the existing scalar only when values and its selected unit basis are present."""
    fiscal_fields = _BALANCE_ALIASES + _DEFICIT_ALIASES
    expected_units = dict.fromkeys(("gdp_change", *fiscal_fields), expected_unit)
    score_assessment = _evaluate_configured_objective_source(
        {"kind": "default_policy_scalar", "expected_units": expected_units}, results
    )
    status = score_assessment.status
    if status is ObjectiveScoreStatus.AVAILABLE:
        return _DefaultSearchObjectiveAssessment(
            objective_value=score_assessment.value,
            score_status=status,
            score_assessment=score_assessment,
        )
    limitation = (
        "search_objective_fiscal_measurement_unavailable"
        if status is ObjectiveScoreStatus.UNAVAILABLE
        else (
            "search_objective_fiscal_period_flow_not_established"
            if status is ObjectiveScoreStatus.NOT_ESTABLISHED
            else "search_objective_fiscal_measurement_invalid"
        )
    )
    return _DefaultSearchObjectiveAssessment(
        objective_value=None,
        score_status=status,
        score_assessment=score_assessment,
        limitations=(limitation,),
    )


def _apply_default_search_objective_limitations(
    feedback: dict[str, Any],
    assessment: _DefaultSearchObjectiveAssessment,
) -> None:
    """Publish the typed score state and replace only this objective's limitation."""
    old_limitations = {
        "budget_deficit_unavailable_required_float_legacy_zero",
        "search_objective_score_unavailable_required_metrics",
        "search_objective_score_invalid_present_metric",
        "search_objective_fiscal_measurement_unavailable",
        "search_objective_fiscal_measurement_invalid",
        "search_objective_fiscal_period_flow_not_established",
    }
    previous = feedback.get("objective_limitations")
    retained = (
        [item for item in previous if item not in old_limitations]
        if isinstance(previous, (list, tuple))
        else []
    )
    limitations = [*retained, *assessment.limitations]
    feedback["objective_score_status"] = assessment.score_status.value
    if limitations:
        feedback["objective_limitations"] = limitations
    else:
        feedback.pop("objective_limitations", None)


class InequalityObjective(BaseObjective):
    """Minimize Gini coefficient (inequality)."""

    @property
    def name(self) -> str:
        return "inequality"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: dict[str, Any]) -> float:
        value, status = _read_finite_numeric_metric(results, "gini_coefficient")
        return value if status is ObjectiveScoreStatus.AVAILABLE and value is not None else math.nan


class EmploymentObjective(BaseObjective):
    """Maximize employment rate."""

    @property
    def name(self) -> str:
        return "employment"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MAXIMIZE

    def _extract_value(self, results: dict[str, Any]) -> float:
        value, status = _read_finite_numeric_metric(results, "employment_rate")
        return value if status is ObjectiveScoreStatus.AVAILABLE and value is not None else math.nan


# ─────────────────────────────────────────────────────────────────────────────
# Composite Objective
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompositeObjective:
    """
    Weighted combination of multiple objectives.

    Example:
        objective = CompositeObjective([
            GDPGrowthObjective(weight=0.7),
            InequalityObjective(weight=0.3),
        ])
    """

    objectives: list[SearchObjective] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "composite"

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]) -> ObjectiveValue:
        """Evaluate all objectives and return weighted sum."""
        assessment = _assess_configured_objective(self, results)
        total = assessment.value if assessment.value is not None else math.nan
        all_satisfied = assessment.status is ObjectiveScoreStatus.AVAILABLE
        return ObjectiveValue(
            name=self.name,
            raw_value=total,
            direction=self.direction,
            is_satisfied=all_satisfied,
            score_status=assessment.status,
            score_assessment=assessment,
        )

    def evaluate_detailed(self, results: dict[str, Any]) -> list[ObjectiveValue]:
        """Return individual objective evaluations for analysis."""
        return [obj.evaluate(results) for obj in self.objectives]


def _objective_rule_spec(objective: SearchObjective) -> dict[str, Any] | None:
    """Describe built-in objective rules without relying on a consumer marker."""
    if isinstance(objective, CompositeObjective):
        children = [_objective_rule_spec(item) for item in objective.objectives]
        if not children or any(item is None for item in children):
            return None
        return {"kind": "composite", "children": children}
    if isinstance(objective, BaseObjective):
        if isinstance(objective, GDPGrowthObjective):
            kind = "gdp_growth"
        elif isinstance(objective, BudgetDeficitObjective):
            kind = "budget_deficit"
        elif isinstance(objective, InequalityObjective):
            kind = "inequality"
        elif isinstance(objective, EmploymentObjective):
            kind = "employment"
        else:
            return None
        return {
            "kind": kind,
            "weight": float(objective._weight),
            "threshold": objective._threshold,
            "expected_unit": objective.expected_unit,
        }
    return None


def configured_objective_rule_spec(objective: SearchObjective) -> str | None:
    """Return the source-recomputable identity of an actually configured objective."""
    spec = _objective_rule_spec(objective)
    return None if spec is None else canonical_objective_rule_spec(spec)


def _policy_vector_channel_field_name(spec: dict[str, Any]) -> str | None:
    """Return the typed source key for one selected policy-vector channel."""
    group = spec.get("group")
    name = spec.get("name")
    if (
        group not in {"primary", "secondary", "penalties"}
        or not isinstance(name, str)
        or not name.strip()
    ):
        return None
    return f"channel:{group}:{name}"


def _rule_input_groups(spec: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    kind = spec.get("kind")
    if kind == "policy_vector_channel":
        field_name = _policy_vector_channel_field_name(spec)
        return ((field_name,),) if field_name is not None else ()
    if kind == "gdp_growth":
        return (("gdp_change",),)
    if kind == "budget_deficit":
        return ((_BALANCE_ALIASES + _DEFICIT_ALIASES),)
    if kind == "inequality":
        return (("gini_coefficient",),)
    if kind == "employment":
        return (("employment_rate",),)
    if kind == "search_metric":
        metric_name = spec.get("metric_name")
        return ((metric_name,),) if isinstance(metric_name, str) and metric_name else ()
    if kind == "default_policy_scalar":
        return (("gdp_change",), (_BALANCE_ALIASES + _DEFICIT_ALIASES))
    if kind == "composite":
        return tuple(
            group for child in spec.get("children", []) for group in _rule_input_groups(child)
        )
    return ()


def _rule_source_field_names(spec: dict[str, Any]) -> tuple[str, ...]:
    names = {name for group in _rule_input_groups(spec) for name in group}
    if spec.get("kind") == "default_policy_scalar":
        names.update(("budget_deficit_objective_usable", "budget_deficit_objective_value"))
    if spec.get("kind") == "composite":
        for child in spec.get("children", []):
            names.update(_rule_source_field_names(child))
    return tuple(sorted(names))


def _rule_metric_unit_requirements(spec: dict[str, Any]) -> dict[str, str | None] | None:
    """Derive each operand unit from the selected rule, never from a label."""
    kind = spec.get("kind")
    if kind == "composite":
        requirements: dict[str, str | None] = {}
        children = spec.get("children")
        if not isinstance(children, list) or not children:
            return None
        for child in children:
            if not isinstance(child, dict):
                return None
            child_requirements = _rule_metric_unit_requirements(child)
            if child_requirements is None:
                return None
            for field_name, unit in child_requirements.items():
                if field_name in requirements and requirements[field_name] != unit:
                    return None
                requirements[field_name] = unit
        return requirements
    if kind == "policy_vector_channel":
        field_name = _policy_vector_channel_field_name(spec)
        if field_name is None:
            return None
        expected = spec.get("expected_unit")
        if expected is None:
            return {field_name: None}
        if not isinstance(expected, str) or not expected.strip() or expected != expected.strip():
            return None
        return {field_name: expected}
    if kind == "default_policy_scalar":
        field_names = {"gdp_change", *_BALANCE_ALIASES, *_DEFICIT_ALIASES}
        raw_units = spec.get("expected_units")
        if raw_units is None:
            return dict.fromkeys(field_names, None)
        if not isinstance(raw_units, dict) or set(raw_units) != field_names:
            return None
        requirements: dict[str, str | None] = {}
        for name, unit in raw_units.items():
            if unit is None:
                requirements[name] = None
            elif isinstance(unit, str) and unit.strip() and unit == unit.strip():
                requirements[name] = unit
            else:
                return None
        return requirements

    field_names = {name for group in _rule_input_groups(spec) for name in group}
    if not field_names:
        return None
    expected = spec.get("expected_unit")
    if expected is None:
        return dict.fromkeys(field_names, None)
    if not isinstance(expected, str) or not expected.strip() or expected != expected.strip():
        return None
    return dict.fromkeys(field_names, expected)


def configured_objective_unit_bindings(rule_spec: str) -> dict[str, str] | None:
    """Return complete, single-unit operand bindings from one configured rule.

    A scalar formula cannot safely combine distinct measurement units without an
    explicit conversion rule. This source owner declares no such conversion.
    """
    try:
        spec = json.loads(rule_spec)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(spec, dict):
        return None
    requirements = _rule_metric_unit_requirements(spec)
    if not requirements or any(
        not isinstance(unit, str) or not unit.strip() or unit != unit.strip()
        for unit in requirements.values()
    ):
        return None
    units = set(requirements.values())
    if len(units) != 1:
        return None
    return dict(sorted((name, unit) for name, unit in requirements.items() if unit is not None))


def configured_objective_unit(rule_spec: str) -> str | None:
    """Return the single exact unit identity admitted by a configured scalar rule."""
    bindings = configured_objective_unit_bindings(rule_spec)
    if bindings is None or not bindings:
        return None
    units = set(bindings.values())
    return next(iter(units)) if len(units) == 1 else None


def _selected_measurement_fields(spec: dict[str, Any], results: dict[str, Any]) -> tuple[str, ...]:
    """Return actual non-null measurements consumed by this configured rule."""
    kind = spec.get("kind")
    if kind == "composite":
        children = spec.get("children")
        if not isinstance(children, list):
            return ()
        return tuple(
            sorted(
                {
                    name
                    for child in children
                    if isinstance(child, dict)
                    for name in _selected_measurement_fields(child, results)
                }
            )
        )
    if kind == "policy_vector_channel":
        field_name = _policy_vector_channel_field_name(spec)
        candidates = (field_name,) if field_name is not None else ()
    elif kind == "gdp_growth":
        candidates = ("gdp_change",)
    elif kind == "inequality":
        candidates = ("gini_coefficient",)
    elif kind == "employment":
        candidates = ("employment_rate",)
    elif kind == "search_metric":
        metric_name = spec.get("metric_name")
        candidates = (metric_name,) if isinstance(metric_name, str) else ()
    elif kind in {"budget_deficit", "default_policy_scalar"}:
        candidates = _BALANCE_ALIASES + _DEFICIT_ALIASES
        if kind == "default_policy_scalar":
            candidates = ("gdp_change", *candidates)
    else:
        candidates = ()
    return tuple(
        name
        for name in candidates
        if name in results and results[name] is not _MISSING and results[name] is not None
    )


def _fiscal_alias_source_unit_error(spec: dict[str, Any], results: dict[str, Any]) -> str | None:
    """Reject malformed or contradictory units without treating units as fiscal law."""
    requirements = _rule_metric_unit_requirements(spec)
    if requirements is None:
        return "objective_rule_unit_binding_malformed"
    selected_fields = _selected_measurement_fields(spec, results)
    raw_units = results.get("metric_units", _MISSING)
    if raw_units is _MISSING:
        raw_units = {}
    elif not isinstance(raw_units, dict):
        return "objective_source_unit_malformed_or_conflicting"

    selected_units: list[str] = []
    for field_name in selected_fields:
        observed_unit = raw_units.get(field_name, _MISSING)
        expected_unit = requirements.get(field_name, _MISSING)
        if observed_unit is _INVALID:
            return "objective_source_unit_malformed_or_conflicting"
        if observed_unit is _MISSING:
            if (
                field_name in _DEFICIT_ALIASES
                and expected_unit is not _MISSING
                and expected_unit is not None
            ):
                return "objective_source_unit_not_established"
            continue
        if (
            not isinstance(observed_unit, str)
            or not observed_unit.strip()
            or observed_unit != observed_unit.strip()
        ):
            return "objective_source_unit_malformed_or_conflicting"
        if expected_unit is _INVALID or (
            expected_unit is not _MISSING
            and expected_unit is not None
            and observed_unit != expected_unit
        ):
            return "objective_source_unit_malformed_or_conflicting"
        selected_units.append(observed_unit)

    if len(set(selected_units)) > 1:
        return "objective_source_unit_malformed_or_conflicting"
    return None


def _objective_source_results(source: Any, spec: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve only selected rule operands from actual result containers.

    Search result envelopes can expose the same operand at the root and beneath
    ``simulation_results`` or ``metrics``.  Reconcile those values before scoring;
    selecting the first convenient container would let a contradictory sibling
    source hide from the selected objective's basis.
    """
    if hasattr(source, "model_dump"):
        try:
            source = source.model_dump(mode="python")
        except (TypeError, ValueError):
            return None
    if not isinstance(source, dict):
        return None
    containers = [source]
    for key in _SOURCE_RESULT_CONTAINERS:
        nested = source.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    names = _rule_source_field_names(spec)
    resolved: dict[str, Any] = {}
    nullable_fiscal_aliases = set(_BALANCE_ALIASES + _DEFICIT_ALIASES)
    for name in names:
        observed: list[Any] = [container[name] for container in containers if name in container]
        if name in nullable_fiscal_aliases:
            # The fiscal objective contract treats an explicit null as an absent
            # alias, allowing a valid alternative measurement to supply the value.
            # Non-null malformed values remain present and fail closed below.
            observed = [value for value in observed if value is not None]
        if not observed:
            continue
        if name == "budget_deficit_objective_usable":
            normalized = observed
            if any(type(value) is not bool for value in normalized):
                resolved[name] = _INVALID
                continue
        elif name == "budget_deficit_objective_value" and all(value is None for value in observed):
            # The existing typed unavailable marker uses usable=False plus a null
            # value; _assess_search_fiscal_measurement validates that pair.
            normalized = observed
        else:
            numeric: list[float] = []
            invalid = False
            for raw in observed:
                value, status = _read_finite_numeric_metric({name: raw}, name)
                if status is not ObjectiveScoreStatus.AVAILABLE or value is None:
                    invalid = True
                    break
                numeric.append(value)
            if invalid:
                resolved[name] = _INVALID
                continue
            normalized = numeric
        first = normalized[0]
        if any(value != first or type(value) is not type(first) for value in normalized[1:]):
            resolved[name] = _INVALID
        else:
            resolved[name] = first
    unit_fields = set(_rule_metric_unit_requirements(spec))
    observed_units: dict[str, list[Any]] = {name: [] for name in unit_fields}
    units_invalid = False
    for container in containers:
        if "metric_units" not in container:
            continue
        raw_units = container["metric_units"]
        if not isinstance(raw_units, dict):
            units_invalid = True
            continue
        for name in unit_fields:
            if name in raw_units:
                observed_units[name].append(raw_units[name])
    normalized_units: dict[str, Any] = {}
    if units_invalid:
        normalized_units = dict.fromkeys(unit_fields, _INVALID)
    else:
        for name, values in observed_units.items():
            if not values:
                normalized_units[name] = _MISSING
            elif any(
                value != values[0] or type(value) is not type(values[0]) for value in values[1:]
            ):
                normalized_units[name] = _INVALID
            else:
                normalized_units[name] = values[0]
    resolved["metric_units"] = normalized_units
    return resolved


def _configured_search_metric_rule_spec(
    metric_name: str, source_direction: str, expected_unit: str | None = None
) -> str | None:
    """Describe the configured scalar metric and its existing minimization mapping.

    This is a mechanical search-coordinate rule: maximize metrics are negated and
    minimize metrics are retained, matching the candidate generator's existing
    scalarization. The exact selected unit is identity only; no conversion or scientific
    authority is inferred.
    """
    if not isinstance(metric_name, str) or not metric_name.strip():
        return None
    if source_direction not in {"minimize", "maximize"}:
        return None
    if expected_unit is not None and (
        not isinstance(expected_unit, str)
        or not expected_unit.strip()
        or expected_unit != expected_unit.strip()
    ):
        return None
    return canonical_objective_rule_spec(
        {
            "kind": "search_metric",
            "metric_name": metric_name,
            "source_direction": source_direction,
            "normalized_direction": "minimize",
            "expected_unit": expected_unit,
        }
    )


def _configured_search_metric_binding(
    metric_name: str, source_direction: str, expected_unit: str | None = None
) -> tuple[str, OptimizationDirection, str] | None:
    """Return the actual selected search coordinate, normalized direction, and rule.

    The direction comes from the same canonical rule used by source recomputation,
    so producer, optimizer, and verifier cannot independently negate the score.
    """
    rule_spec = _configured_search_metric_rule_spec(metric_name, source_direction, expected_unit)
    if rule_spec is None:
        return None
    try:
        rule = json.loads(rule_spec)
        direction = OptimizationDirection(rule["normalized_direction"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return metric_name, direction, rule_spec


def _configured_search_metric_profile_fingerprint(
    metric_name: str, source_direction: str, unit: str | None
) -> str | None:
    """Bind a configured scalar's metric, rule, direction, and declared unit.

    This is a compatibility fingerprint for candidate-grade optimizer state.
    It does not establish that the producer measured the configured unit.
    """
    binding = _configured_search_metric_binding(metric_name, source_direction, unit)
    if binding is None or (unit is not None and not isinstance(unit, str)):
        return None
    _, normalized_direction, rule_spec = binding
    payload = {
        "kind": "configured_search_metric_profile",
        "version": "1",
        "metric_name": metric_name,
        "source_direction": source_direction,
        "normalized_direction": normalized_direction.value,
        "rule_spec": rule_spec,
        "unit": unit,
        "scalarization": "finite_scalar_score_minimize",
    }
    return hashlib.sha256(canonical_objective_rule_spec(payload).encode("utf-8")).hexdigest()


def _assess_search_metric(
    source: Any, metric_name: str, source_direction: str, expected_unit: str | None = None
) -> ObjectiveScoreAssessment:
    """Recompute a Bayesian search scalar from its configured result source."""
    rule_spec = _configured_search_metric_rule_spec(metric_name, source_direction, expected_unit)
    if rule_spec is None:
        return _unestablished_score_assessment("search_metric_rule_not_declared")
    return _evaluate_configured_objective_source(json.loads(rule_spec), source)


def _source_fields_and_values(
    results: dict[str, Any], groups: tuple[tuple[str, ...], ...]
) -> tuple[tuple[str, ...], tuple[tuple[str, float], ...]]:
    names = tuple(sorted({name for group in groups for name in group if name in results}))
    values: list[tuple[str, float]] = []
    for name in names:
        raw = results[name]
        if isinstance(raw, bool) or raw is None:
            continue
        try:
            value = float(raw)
        except (OverflowError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append((name, value))
    return names, tuple(values)


def _assessment_for_rule_spec(
    spec: dict[str, Any], results: dict[str, Any]
) -> ObjectiveScoreAssessment:
    """Recompute one built-in objective from its declared source operands."""
    kind = spec.get("kind")
    groups = _rule_input_groups(spec)
    derived_values: dict[str, Any] = {}
    status: ObjectiveScoreStatus
    score: float | None = None
    limitation: str | None = None

    if kind in {"gdp_growth", "inequality", "employment"}:
        input_name = {
            "gdp_growth": "gdp_change",
            "inequality": "gini_coefficient",
            "employment": "employment_rate",
        }[kind]
        score, status = _read_finite_numeric_metric(results, input_name)
        derived_values[input_name] = score
    elif kind == "search_metric":
        metric_name = spec.get("metric_name")
        source_direction = spec.get("source_direction")
        raw_value, status = (
            _read_finite_numeric_metric(results, metric_name)
            if isinstance(metric_name, str) and metric_name
            else (None, ObjectiveScoreStatus.NOT_ESTABLISHED)
        )
        if source_direction not in {"minimize", "maximize"}:
            status = ObjectiveScoreStatus.NOT_ESTABLISHED
        elif status is ObjectiveScoreStatus.AVAILABLE and raw_value is not None:
            score = -raw_value if source_direction == "maximize" else raw_value
        if isinstance(metric_name, str) and metric_name:
            derived_values[metric_name] = raw_value
    elif kind == "budget_deficit":
        balance = _read_metric_aliases(results, _BALANCE_ALIASES)
        deficit = _read_metric_aliases(results, _DEFICIT_ALIASES)
        balance_score = None
        deficit_score = None
        if balance is _INVALID or deficit is _INVALID:
            status = ObjectiveScoreStatus.INVALID
        elif balance is _MISSING and deficit is _MISSING:
            status = ObjectiveScoreStatus.UNAVAILABLE
        else:
            balance_score = max(-float(balance), 0.0) if balance is not _MISSING else None
            deficit_score = abs(float(deficit)) if deficit is not _MISSING else None
            if (
                balance_score is not None
                and deficit_score is not None
                and balance_score != deficit_score
            ):
                status = ObjectiveScoreStatus.INVALID
                limitation = "objective_basis_conflicting_fiscal_measurements"
            else:
                unit_error = _fiscal_alias_source_unit_error(spec, results)
                if unit_error is not None:
                    status = (
                        ObjectiveScoreStatus.NOT_ESTABLISHED
                        if unit_error == "objective_source_unit_not_established"
                        else ObjectiveScoreStatus.INVALID
                    )
                    limitation = unit_error
                elif deficit_score is not None:
                    # A configured deficit operand is the selected objective input.
                    # A balance-stock alias alone cannot establish that period measure.
                    status = ObjectiveScoreStatus.AVAILABLE
                    score = deficit_score
                else:
                    status = ObjectiveScoreStatus.NOT_ESTABLISHED
                    limitation = "budget_deficit_period_flow_source_not_established"
        derived_values["balance_score"] = balance_score if balance is not _INVALID else None
        derived_values["deficit_score"] = deficit_score if deficit is not _INVALID else None
        derived_values["score"] = score
    elif kind == "default_policy_scalar":
        gdp, gdp_status = _read_finite_numeric_metric(results, "gdp_change")
        expected_units = spec.get("expected_units")
        fiscal_unit = (
            expected_units.get("budget_deficit") if isinstance(expected_units, dict) else None
        )
        fiscal_value, fiscal_status = _assess_search_fiscal_measurement(
            results, expected_unit=fiscal_unit
        )
        if (
            gdp_status is ObjectiveScoreStatus.INVALID
            or fiscal_status is ObjectiveScoreStatus.INVALID
        ):
            status = ObjectiveScoreStatus.INVALID
        elif gdp_status is not ObjectiveScoreStatus.AVAILABLE or (
            fiscal_status is not ObjectiveScoreStatus.AVAILABLE
        ):
            status = (
                ObjectiveScoreStatus.NOT_ESTABLISHED
                if fiscal_status is ObjectiveScoreStatus.NOT_ESTABLISHED
                else ObjectiveScoreStatus.UNAVAILABLE
            )
            if fiscal_status is ObjectiveScoreStatus.NOT_ESTABLISHED:
                limitation = "budget_deficit_period_flow_source_not_established"
        else:
            assert gdp is not None
            assert fiscal_value is not None
            status = ObjectiveScoreStatus.AVAILABLE
            score = -(gdp - 0.5 * fiscal_value)
        derived_values["gdp_change"] = gdp
        derived_values["fiscal_status"] = fiscal_status.value
        derived_values["fiscal_value"] = fiscal_value
    elif kind == "composite":
        child_specs = spec.get("children", [])
        children = [_assessment_for_rule_spec(child, results) for child in child_specs]
        if not children:
            status = ObjectiveScoreStatus.NOT_ESTABLISHED
        elif any(item.status is ObjectiveScoreStatus.INVALID for item in children):
            status = ObjectiveScoreStatus.INVALID
        elif any(item.status is ObjectiveScoreStatus.NOT_ESTABLISHED for item in children):
            status = ObjectiveScoreStatus.NOT_ESTABLISHED
            limitation = next(
                (
                    item.limitation
                    for item in children
                    if item.status is ObjectiveScoreStatus.NOT_ESTABLISHED
                    and item.limitation is not None
                ),
                None,
            )
        elif any(item.status is ObjectiveScoreStatus.UNAVAILABLE for item in children):
            status = ObjectiveScoreStatus.UNAVAILABLE
        else:
            status = ObjectiveScoreStatus.AVAILABLE
            score = 0.0
            for child_spec, child_assessment in zip(child_specs, children, strict=True):
                child_value = child_assessment.value
                assert child_value is not None
                direction_sign = -1.0 if child_spec["kind"] in {"gdp_growth", "employment"} else 1.0
                score += direction_sign * child_value * float(child_spec.get("weight", 1.0))
        derived_values["children"] = [item.source_sha256 for item in children]
    else:
        status = ObjectiveScoreStatus.NOT_ESTABLISHED
        limitation = "objective_rule_not_recomputable"

    source_unit_bindings: tuple[tuple[str, str], ...] = ()
    if status is ObjectiveScoreStatus.AVAILABLE:
        requirements = _rule_metric_unit_requirements(spec)
        if requirements is None:
            status = ObjectiveScoreStatus.INVALID
            limitation = "objective_rule_unit_binding_malformed"
        elif any(unit is None for unit in requirements.values()):
            status = ObjectiveScoreStatus.UNAVAILABLE
            limitation = "objective_rule_unit_not_established"
        elif len(set(requirements.values())) != 1:
            status = ObjectiveScoreStatus.INVALID
            limitation = "objective_rule_combines_incompatible_units"
        else:
            selected_fields = _selected_measurement_fields(spec, results)
            raw_units = results.get("metric_units")
            if not selected_fields or not isinstance(raw_units, dict):
                status = ObjectiveScoreStatus.UNAVAILABLE
                limitation = "objective_source_unit_not_established"
            else:
                bound_units: list[tuple[str, str]] = []
                for field_name in selected_fields:
                    expected_unit = requirements.get(field_name, _MISSING)
                    observed_unit = raw_units.get(field_name, _MISSING)
                    if expected_unit is _MISSING:
                        status = ObjectiveScoreStatus.NOT_ESTABLISHED
                        limitation = "objective_rule_unit_operand_not_declared"
                        break
                    if observed_unit is _INVALID:
                        status = ObjectiveScoreStatus.INVALID
                        limitation = "objective_source_unit_malformed_or_conflicting"
                        break
                    if observed_unit is _MISSING:
                        status = ObjectiveScoreStatus.UNAVAILABLE
                        limitation = "objective_source_unit_not_established"
                        break
                    if (
                        not isinstance(observed_unit, str)
                        or not observed_unit.strip()
                        or observed_unit != observed_unit.strip()
                    ):
                        status = ObjectiveScoreStatus.INVALID
                        limitation = "objective_source_unit_malformed"
                        break
                    if observed_unit != expected_unit:
                        status = ObjectiveScoreStatus.INVALID
                        limitation = "objective_source_unit_incompatible"
                        break
                    bound_units.append((field_name, observed_unit))
                if status is ObjectiveScoreStatus.AVAILABLE:
                    source_unit_bindings = tuple(sorted(bound_units))

    if status is not ObjectiveScoreStatus.AVAILABLE:
        # A score computed before source-unit admission is diagnostic only.
        # Do not let it escape on any unavailable or invalid assessment.
        score = None
        if "score" in derived_values:
            derived_values["score"] = None

    if status is not ObjectiveScoreStatus.AVAILABLE and limitation is None:
        limitation = (
            "objective_basis_invalid"
            if status is ObjectiveScoreStatus.INVALID
            else "objective_basis_incomplete"
        )
    rule_spec = canonical_objective_rule_spec(spec)
    objective_ref = hashlib.sha256(rule_spec.encode("utf-8")).hexdigest()
    source_fields, source_values = _source_fields_and_values(results, groups)
    if source_unit_bindings:
        source_fields = tuple(
            sorted(
                set(source_fields) | {f"metric_units.{name}" for name, _ in source_unit_bindings}
            )
        )
    source_payload = json.dumps(
        {
            "rule_spec": rule_spec,
            "source_fields": source_fields,
            "source_values": source_values,
            "derived_values": derived_values,
            "source_unit_bindings": source_unit_bindings,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    source_sha256 = (
        hashlib.sha256(source_payload.encode("utf-8")).hexdigest()
        if status is ObjectiveScoreStatus.AVAILABLE
        else None
    )
    return ObjectiveScoreAssessment(
        objective_ref=objective_ref,
        rule_spec=rule_spec,
        required_input_groups=groups,
        source_field_names=source_fields,
        source_values=source_values,
        source_unit_bindings=source_unit_bindings,
        source_sha256=source_sha256,
        value=score,
        status=status,
        limitation=limitation,
    )


def _evaluate_configured_objective_source(
    spec: dict[str, Any], source: Any
) -> ObjectiveScoreAssessment:
    """Evaluate one configured rule from the same normalized source at production and replay.

    Both objective producers and admission-time source reconciliation enter here.
    Keeping source resolution and rule execution together prevents a persisted
    assessment from being reinterpreted with different alias/null semantics.
    """
    if not isinstance(spec, dict):
        return _unestablished_score_assessment("objective_rule_not_declared")
    resolved_results = _objective_source_results(source, spec)
    if resolved_results is None:
        return _unestablished_score_assessment("objective_source_not_resolved")
    try:
        return _assessment_for_rule_spec(spec, resolved_results)
    except (TypeError, ValueError, KeyError, OverflowError, json.JSONDecodeError):
        return _unestablished_score_assessment("objective_source_or_rule_invalid")


def _assess_configured_objective(
    objective: SearchObjective, results: dict[str, Any]
) -> ObjectiveScoreAssessment:
    spec = _objective_rule_spec(objective)
    if spec is None:
        return _unestablished_score_assessment("objective_rule_not_declared")
    return _evaluate_configured_objective_source(spec, results)


def _recompute_score_assessment(
    assessment: ObjectiveScoreAssessment | None,
    source: Any,
    *,
    owner_context: object | None = None,
) -> ObjectiveScoreAssessment | None:
    """Recompute every carried score state from its selected rule and source."""
    if assessment is None or not assessment.rule_spec:
        return None
    try:
        spec = json.loads(assessment.rule_spec)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(spec, dict):
        return None
    if spec.get("kind") == "completed_method_metric_objectives":
        try:
            from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
                recompute_completed_method_metric_score,
            )

            return recompute_completed_method_metric_score(
                assessment,
                owner_context=owner_context,
            )
        except (ImportError, TypeError, ValueError):
            return None
    if spec.get("kind") == "policy_vector_channel":
        payload = source
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="python")
        if not isinstance(payload, dict):
            return None
        vector_payload = payload.get("policy_evaluation", payload)
        if hasattr(vector_payload, "model_dump"):
            vector_payload = vector_payload.model_dump(mode="python")
        if not isinstance(vector_payload, dict):
            return None
        try:
            from polisyos.scientist.policy_design.objectives import (
                _normalize_policy_evaluation_vector,
                _policy_vector_channel_assessment,
            )

            normalized_vector = _normalize_policy_evaluation_vector(
                vector_payload, allow_mapping=True
            )
        except (ImportError, TypeError, ValueError):
            return None
        group = spec.get("group")
        name = spec.get("name")
        if group not in {"primary", "secondary", "penalties"} or not isinstance(name, str):
            return None
        channel = getattr(normalized_vector, group).get(name)
        if channel is None:
            return None
        simulation_results = payload.get("simulation_results")
        if not isinstance(simulation_results, dict) and isinstance(vector_payload, dict):
            simulation_results = vector_payload.get("simulation_results")
        if not isinstance(simulation_results, dict):
            return None
        return _policy_vector_channel_assessment(channel, group, simulation_results)
    try:
        return _evaluate_configured_objective_source(spec, source)
    except (TypeError, ValueError, KeyError, OverflowError, json.JSONDecodeError):
        return None


def score_assessment_matches_source(
    assessment: ObjectiveScoreAssessment | None,
    source: Any,
    *,
    owner_context: object | None = None,
) -> bool:
    """Recompute a carried assessment from its actual source result payload."""
    if assessment is None:
        return False
    return (
        _recompute_score_assessment(
            assessment,
            source,
            owner_context=owner_context,
        )
        == assessment
    )


def reconcile_objective_score_assessment(
    assessment: ObjectiveScoreAssessment | None,
    source: Any,
    *,
    prior_admission: ObjectiveScoreAdmission | None = None,
    reported_status: ObjectiveScoreStatus | None = None,
    reported_value: float | None = None,
    owner_context: object | None = None,
) -> ObjectiveScoreAdmission:
    """Produce one typed source-recomputed score state for all consumers.

    A missing assessment is not allowed to erase a prior INVALID result. An
    unbound assessment remains NOT_ESTABLISHED; a declared rule whose current
    source cannot replay is INVALID. A numeric value is admitted only when the
    current replay exactly matches both the carried assessment and value.
    """
    if owner_context is None and prior_admission is not None:
        owner_context = prior_admission._owner_context

    def _admission(**values: Any) -> ObjectiveScoreAdmission:
        return _attach_score_admission_owner_context(
            ObjectiveScoreAdmission(**values), owner_context
        )

    if assessment is None:
        if reported_status is ObjectiveScoreStatus.INVALID or (
            prior_admission is not None and prior_admission.status is ObjectiveScoreStatus.INVALID
        ):
            return _admission(
                status=ObjectiveScoreStatus.INVALID,
                predicate_status=(
                    "not_established"
                    if prior_admission is None
                    else prior_admission.predicate_status
                ),
                reported_assessment=None,
                recomputed_assessment=(
                    None if prior_admission is None else prior_admission.recomputed_assessment
                ),
                reason=(
                    prior_admission.reason
                    if prior_admission is not None
                    else "invalid_score_status_without_assessment"
                ),
            )
        return _admission(
            status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            predicate_status="not_established",
            reported_assessment=None,
            recomputed_assessment=None,
            reason="score_assessment_missing",
        )

    if not assessment.rule_spec:
        if assessment.status is ObjectiveScoreStatus.NOT_ESTABLISHED:
            return _admission(
                status=ObjectiveScoreStatus.NOT_ESTABLISHED,
                predicate_status="not_established",
                reported_assessment=assessment,
                recomputed_assessment=None,
                reason=assessment.limitation or "selected_rule_not_established",
            )
        return _admission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="not_established",
            reported_assessment=assessment,
            recomputed_assessment=None,
            reason="declared_score_has_no_replayable_rule",
        )

    try:
        selected_rule = json.loads(assessment.rule_spec)
    except (TypeError, ValueError, json.JSONDecodeError):
        selected_rule = None
    if (
        isinstance(selected_rule, dict)
        and selected_rule.get("kind") == "completed_method_metric_objectives"
        and owner_context is None
    ):
        invalid_was_already_selected = reported_status is ObjectiveScoreStatus.INVALID or (
            prior_admission is not None and prior_admission.status is ObjectiveScoreStatus.INVALID
        )
        if invalid_was_already_selected:
            reason = (
                prior_admission.reason
                if prior_admission is not None
                else "reported_score_status_invalid"
            )
            return _admission(
                status=ObjectiveScoreStatus.INVALID,
                predicate_status="not_established",
                reported_assessment=assessment,
                recomputed_assessment=None,
                reason=reason,
            )
        return _admission(
            status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            predicate_status="not_established",
            reported_assessment=assessment,
            recomputed_assessment=None,
            reason="completed_method_metric_owner_context_not_retained",
        )

    recomputed = _recompute_score_assessment(
        assessment,
        source,
        owner_context=owner_context,
    )
    if recomputed is None:
        return _admission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="not_established",
            reported_assessment=assessment,
            recomputed_assessment=None,
            reason="selected_score_source_replay_failed",
        )
    if recomputed != assessment:
        return _admission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="recomputed",
            reported_assessment=assessment,
            recomputed_assessment=recomputed,
            reason="selected_score_source_mismatch",
        )
    if reported_status is ObjectiveScoreStatus.INVALID:
        return _admission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="recomputed",
            reported_assessment=assessment,
            recomputed_assessment=recomputed,
            reason="reported_score_status_invalid",
        )
    if (
        assessment.status is ObjectiveScoreStatus.AVAILABLE
        and reported_value is not None
        and reported_value != assessment.value
    ):
        return _admission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="recomputed",
            reported_assessment=assessment,
            recomputed_assessment=recomputed,
            reason="reported_score_value_mismatch",
        )
    return _admission(
        status=assessment.status,
        predicate_status="recomputed",
        reported_assessment=assessment,
        recomputed_assessment=recomputed,
        reason="selected_score_source_recomputed",
    )


def _source_field_path(
    source: Mapping[str, Any], field_name: str
) -> tuple[tuple[str, ...], Any] | None:
    """Resolve an exact source key first, then a declared dotted mapping path."""
    if field_name in source:
        return (field_name,), source[field_name]
    path = tuple(field_name.split("."))
    if len(path) < 2:
        return None
    value: Any = source
    for component in path:
        if not isinstance(value, Mapping) or component not in value:
            return None
        value = value[component]
    return path, value


def _insert_source_path(target: dict[str, Any], path: tuple[str, ...], value: Any) -> bool:
    """Insert one projected path without masking a conflicting path shape."""
    node = target
    for component in path[:-1]:
        existing = node.get(component)
        if existing is None:
            existing = {}
            node[component] = existing
        if not isinstance(existing, dict):
            return False
        node = existing
    leaf = path[-1]
    if leaf in node:
        try:
            return bool(node[leaf] == value)
        except (TypeError, ValueError):
            return node[leaf] is value
    node[leaf] = value
    return True


def _project_score_assessment_source(
    assessment: ObjectiveScoreAssessment,
    source: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Retain only selected source paths, preserving their mapping structure.

    The assessment's source-field set and selected rule's unit operands are the
    projection contract. Known result envelopes are preserved at their original
    location so admission replay sees the same root, ``simulation_results``, and
    ``metrics`` operands. Dotted paths such as ``metric_units.gdp_change`` remain
    nested paths rather than disappearing as nonexistent top-level keys.
    """
    if not isinstance(source, Mapping):
        return None
    projected: dict[str, Any] = {}
    source_containers: list[tuple[str | None, Mapping[str, Any]]] = [(None, source)]
    for container_name in _SOURCE_RESULT_CONTAINERS:
        nested = source.get(container_name)
        if isinstance(nested, Mapping):
            source_containers.append((container_name, nested))

    for field_name in sorted(set(assessment.source_field_names)):
        if not isinstance(field_name, str) or not field_name:
            return None
        for container_name, container in source_containers:
            resolved = _source_field_path(container, field_name)
            if resolved is None:
                continue
            path, value = resolved
            destination = projected
            if container_name is not None:
                nested_destination = destination.setdefault(container_name, {})
                if not isinstance(nested_destination, dict):
                    return None
                destination = nested_destination
            if not _insert_source_path(destination, path, value):
                return None

    try:
        rule = json.loads(assessment.rule_spec or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(rule, dict):
        return None
    unit_fields = _rule_metric_unit_requirements(rule)
    if unit_fields is not None:
        for container_name, container in source_containers:
            if "metric_units" not in container:
                continue
            raw_units = container["metric_units"]
            destination = projected
            if container_name is not None:
                nested_destination = destination.setdefault(container_name, {})
                if not isinstance(nested_destination, dict):
                    return None
                destination = nested_destination
            if not isinstance(raw_units, Mapping):
                if not _insert_source_path(destination, ("metric_units",), raw_units):
                    return None
                continue
            for field_name in unit_fields:
                if field_name in raw_units and not _insert_source_path(
                    destination,
                    ("metric_units", field_name),
                    raw_units[field_name],
                ):
                    return None

    if rule.get("kind") == "policy_vector_channel":
        vector_source = source.get("policy_evaluation", source)
        if hasattr(vector_source, "model_dump"):
            vector_source = vector_source.model_dump(mode="python")
        group, name = rule.get("group"), rule.get("name")
        if (
            not isinstance(vector_source, Mapping)
            or group
            not in {
                "primary",
                "secondary",
                "penalties",
            }
            or not isinstance(name, str)
        ):
            return None
        channels = vector_source.get(group)
        channel = channels.get(name) if isinstance(channels, Mapping) else None
        if hasattr(channel, "model_dump"):
            channel = channel.model_dump(mode="python")
        if not isinstance(channel, Mapping):
            return None
        projected["policy_evaluation"] = {group: {name: dict(channel)}}
        simulation_source = source.get("simulation_results", vector_source)
        if not isinstance(simulation_source, Mapping):
            return None
        objective_channels = simulation_source.get("objective_channels")
        if not isinstance(objective_channels, Mapping) or name not in objective_channels:
            return None
        simulation_projection = projected.setdefault("simulation_results", {})
        if not isinstance(simulation_projection, dict):
            return None
        projected_channels = simulation_projection.setdefault("objective_channels", {})
        if not isinstance(projected_channels, dict):
            return None
        projected_channels[name] = objective_channels[name]

    return projected


def selected_score_admission_status(
    assessment: ObjectiveScoreAssessment | None,
    source: Any,
    *,
    owner_context: object | None = None,
) -> ObjectiveScoreStatus:
    """Return only a source-recomputed available score as admissible."""
    if assessment is None:
        return ObjectiveScoreStatus.NOT_ESTABLISHED
    if assessment.status is not ObjectiveScoreStatus.AVAILABLE:
        return assessment.status
    if score_assessment_matches_source(
        assessment,
        source,
        owner_context=owner_context,
    ):
        return ObjectiveScoreStatus.AVAILABLE
    return ObjectiveScoreStatus.INVALID


def objective_value_matches_rule(
    objective: ObjectiveValue | None,
    source: Any,
    *,
    expected_name: str,
    expected_direction: OptimizationDirection,
    expected_rule_spec: str,
) -> bool:
    """Reconcile a scored coordinate with the selected configured rule and source."""
    if (
        objective is None
        or objective.name != expected_name
        or objective.direction is not expected_direction
        or objective.score_status is not ObjectiveScoreStatus.AVAILABLE
        or objective.score_assessment is None
        or objective.score_assessment.rule_spec != expected_rule_spec
        or objective.raw_value != objective.score_assessment.value
        or not score_assessment_matches_source(objective.score_assessment, source)
    ):
        return False
    try:
        rule = json.loads(expected_rule_spec)
        rule_direction = rule.get("direction", rule.get("normalized_direction"))
        if rule_direction is not None and rule_direction != expected_direction.value:
            return False
        expected_weight = rule.get("weight")
        expected_threshold = rule.get("threshold", _MISSING)
        if expected_weight is not None and objective.weight != float(expected_weight):
            return False
        if expected_threshold is not _MISSING and objective.threshold != expected_threshold:
            return False
    except (TypeError, ValueError, json.JSONDecodeError, OverflowError):
        return False
    return True


def _evaluation_execution_succeeded(evaluation: Any) -> bool:
    """Check execution and feasibility independently of a selected score basis."""
    status = getattr(evaluation, "status", None)
    status_value = getattr(status, "value", status)
    return status_value == "success" and getattr(evaluation, "stage_a_passed", False) is True


def _evaluation_matches_selected_objectives(
    evaluation: Any,
    *,
    objective_names: list[str],
    objective_directions: dict[str, OptimizationDirection],
    objective_rule_specs: dict[str, str],
    source_result: Any = _MISSING,
    require_scalar_score: bool = False,
) -> bool:
    """Check each score coordinate against the consumer's configured rule map.

    Names and carried assessments are labels only.  This shared admission check
    requires a unique coordinate for every selected objective and recomputes that
    coordinate from the evaluation's retained result source under the consumer's
    expected direction and rule specification.
    """
    selected = set(objective_names)
    if (
        not objective_names
        or len(selected) != len(objective_names)
        or set(objective_directions) != selected
        or set(objective_rule_specs) != selected
    ):
        return False
    objectives = (
        evaluation if isinstance(evaluation, list) else getattr(evaluation, "objectives", None)
    )
    if not isinstance(objectives, list):
        return False
    if not isinstance(evaluation, list) and not _evaluation_execution_succeeded(evaluation):
        return False
    by_name: dict[str, list[ObjectiveValue]] = {}
    for objective in objectives:
        if not isinstance(objective, ObjectiveValue):
            return False
        by_name.setdefault(objective.name, []).append(objective)
    source = (
        getattr(evaluation, "stage_b_result", None) if source_result is _MISSING else source_result
    )
    try:
        if set(by_name) != selected or not all(
            len(by_name.get(name, [])) == 1
            and objective_value_matches_rule(
                by_name[name][0],
                source,
                expected_name=name,
                expected_direction=objective_directions[name],
                expected_rule_spec=objective_rule_specs[name],
            )
            for name in objective_names
        ):
            return False
        if not require_scalar_score:
            return True
        if len(objective_names) != 1:
            return False
        name = objective_names[0]
        selected = by_name[name][0]
        assessment = getattr(evaluation, "score_assessment", None)
        scalar_score = getattr(evaluation, "scalar_score", None)
        return (
            getattr(evaluation, "score_status", None) is ObjectiveScoreStatus.AVAILABLE
            and assessment is not None
            and assessment == selected.score_assessment
            and assessment.rule_spec == objective_rule_specs[name]
            and assessment.value == selected.raw_value
            and scalar_score == selected.raw_value
            and isinstance(scalar_score, (int, float))
            and not isinstance(scalar_score, bool)
            and math.isfinite(float(scalar_score))
        )
    except (KeyError, TypeError, ValueError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Factory for Common Objective Configurations
# ─────────────────────────────────────────────────────────────────────────────


class ObjectivePresets:
    """Pre-configured objective combinations for common use cases."""

    @staticmethod
    def balanced_growth() -> CompositeObjective:
        """Balance GDP growth with fiscal responsibility."""
        return CompositeObjective(
            [
                GDPGrowthObjective(weight=0.5),
                BudgetDeficitObjective(weight=0.3),
                InequalityObjective(weight=0.2),
            ]
        )

    @staticmethod
    def growth_focused() -> CompositeObjective:
        """Prioritize GDP growth."""
        return CompositeObjective(
            [
                GDPGrowthObjective(weight=0.8),
                BudgetDeficitObjective(weight=0.2),
            ]
        )

    @staticmethod
    def equity_focused() -> CompositeObjective:
        """Prioritize reducing inequality."""
        return CompositeObjective(
            [
                InequalityObjective(weight=0.6),
                EmploymentObjective(weight=0.3),
                GDPGrowthObjective(weight=0.1),
            ]
        )
