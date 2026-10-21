"""Typed compile-time and runtime rules for method-produced metrics.

These rules are deliberately small: method output semantics are candidate
evidence. Only the registered Ex-Ante mean-change law plus its exact unit identity
can produce an available numeric observation; the generic direct-output path is
fail-closed.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

if TYPE_CHECKING:
    from collections.abc import Sequence

from .base import KernelModel
from .units import GenericUnit, RateUnit, UnitSpecType

METHOD_METRIC_DIRECT_OUTPUT_LAW_ID = "policyos.ir.method_metric.direct_output.v1"
METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION = "1.0"
METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID = "policyos.ir.method_metric.ex_ante_mean_change.v1"
METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_VERSION = "1.0"
METHOD_METRIC_UNIT_ADAPTER_ID = "policyos.ir.method_metric.unit_adapter.v1"
METHOD_METRIC_UNIT_ADAPTER_VERSION = "1.0"


class MethodMetricInputRole(KernelModel):
    """A declared method input role that would be required to establish an output."""

    role_id: str = Field(min_length=1)
    method_input_slot_id: str = Field(min_length=1)


class MethodMetricSemanticContract(KernelModel):
    """Declared meaning of a method output, kept distinct from its numeric value."""

    quantity_kind: str = Field(min_length=1)
    quantity_role: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    axes: tuple[str, ...] = Field(min_length=1)
    denominator_id: str | None = None
    time_role: str = Field(min_length=1)
    producer_contract_id: str = Field(min_length=1)
    input_roles: tuple[MethodMetricInputRole, ...] = ()
    output_value_path: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_semantics(self) -> MethodMetricSemanticContract:
        if any(
            not value.strip()
            for value in (
                self.quantity_kind,
                self.quantity_role,
                self.population_id,
                self.time_role,
                self.producer_contract_id,
            )
        ):
            raise ValueError("method_metric_semantic_identity_must_be_non_empty")
        if self.denominator_id is not None and not self.denominator_id.strip():
            raise ValueError("method_metric_denominator_id_must_be_non_empty")
        if any(not axis.strip() for axis in self.axes):
            raise ValueError("method_metric_axes_must_be_non_empty")
        if any(not segment.strip() for segment in self.output_value_path):
            raise ValueError("method_metric_output_value_path_must_be_non_empty")
        if len(set(self.axes)) != len(self.axes):
            raise ValueError("duplicate_method_metric_axis")
        role_ids = [item.role_id for item in self.input_roles]
        slot_ids = [item.method_input_slot_id for item in self.input_roles]
        if len(set(role_ids)) != len(role_ids):
            raise ValueError("duplicate_method_metric_input_role")
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("duplicate_method_metric_input_slot")
        return self


class MethodMetricParameterContext(KernelModel):
    """Captured effective parameter identity and default/request provenance."""

    name: StrictStr = Field(min_length=1)
    source: Literal[
        "requested",
        "signature_default",
        "signature_default_unresolved",
        "requested_unresolved",
    ]
    status: Literal["captured", "unsupported_codec"]
    value_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_parameter(self) -> MethodMetricParameterContext:
        if self.status == "captured":
            if self.value_sha256 is None or self.source in {
                "requested_unresolved",
                "signature_default_unresolved",
            }:
                raise ValueError("captured_method_metric_parameter_requires_resolved_digest")
        elif self.value_sha256 is not None:
            raise ValueError("unsupported_method_metric_parameter_cannot_have_digest")
        return self


class MethodMetricInputContext(KernelModel):
    """Captured actual content identity for one method input slot."""

    method_input_slot_id: StrictStr = Field(min_length=1)
    status: Literal["captured", "not_established"]
    value_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_input(self) -> MethodMetricInputContext:
        if self.status == "captured":
            if self.value_sha256 is None:
                raise ValueError("captured_method_metric_input_requires_digest")
        elif self.value_sha256 is not None:
            raise ValueError("unestablished_method_metric_input_cannot_have_digest")
        return self


class MethodMetricInputRoleContext(KernelModel):
    """Reconciled semantic role to actual ABI slot and captured input identity."""

    role_id: StrictStr = Field(min_length=1)
    method_input_slot_id: StrictStr = Field(min_length=1)
    value_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class MethodMetricBackendAttempt(KernelModel):
    """One backend attempt copied from the selected dispatch trace."""

    backend: StrictStr = Field(min_length=1)
    outcome: StrictStr = Field(min_length=1)


class MethodMetricExecutionContext(KernelModel):
    """Strict replay context the registered output law requires before observation."""

    dispatch_outcome: Literal["succeeded", "failed", "not_run"]
    method_fqn: StrictStr = Field(min_length=1)
    method_version: StrictStr = Field(min_length=1)
    method_abi_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    method_abi_digest_algorithm: Literal["blake2b"]
    method_build_digest: StrictStr | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    method_build_digest_scope: Literal["class_source_only", "unavailable"] = "unavailable"
    output_slot_id: StrictStr = Field(min_length=1)
    output_value_path: tuple[StrictStr, ...] = Field(default_factory=tuple, max_length=16)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dispatch_elapsed_ms: StrictFloat | None = Field(default=None, ge=0)
    runner_wall_time_ms: StrictFloat | None = Field(default=None, ge=0)
    runner_cpu_time_ms: StrictFloat | None = Field(default=None, ge=0)
    runner_compile_time_ms: StrictFloat | None = Field(default=None, ge=0)
    graph_input_ids: tuple[StrictStr, ...] = Field(max_length=256)
    signature_input_slot_ids: tuple[StrictStr, ...] = Field(max_length=256)
    signature_output_slot_ids: tuple[StrictStr, ...] = Field(max_length=256)
    signature_parameter_names: tuple[StrictStr, ...] = Field(max_length=256)
    parameter_resolution_status: Literal["captured", "not_established"]
    parameter_values: tuple[MethodMetricParameterContext, ...] = Field(max_length=256)
    prestate_identity_status: Literal["captured", "not_established"]
    prestate_identity_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    input_slot_values: tuple[MethodMetricInputContext, ...] = Field(max_length=256)
    input_role_values: tuple[MethodMetricInputRoleContext, ...] = Field(max_length=256)
    seed_status: Literal["reconciled", "mismatch", "not_established"]
    root_seed: StrictInt | None = None
    step: StrictInt | None = None
    method_seed: StrictInt | None = None
    reproducibility_seed: StrictInt | None = None
    method_key_words: tuple[StrictInt, ...] = Field(max_length=16)
    rng_state_status: Literal["key_captured", "runner_rng_state_not_retained"]
    requested_backend: StrictStr | None = None
    selected_backend: StrictStr | None = None
    backend_selection_reason: StrictStr | None = None
    backend_trace_status: Literal["captured", "not_established", "not_started"]
    backend_attempts: tuple[MethodMetricBackendAttempt, ...] = Field(max_length=32)
    fallback_status: Literal["fell_back", "not_fell_back", "not_established", "not_started"]
    backend_identity_status: Literal["reconciled", "mismatch", "not_established"]
    actual_backend: StrictStr | None = None

    @model_validator(mode="after")
    def validate_execution_context(self) -> MethodMetricExecutionContext:
        if len(set(self.signature_input_slot_ids)) != len(self.signature_input_slot_ids):
            raise ValueError("duplicate_method_metric_context_input_slot")
        if len(set(self.signature_output_slot_ids)) != len(self.signature_output_slot_ids):
            raise ValueError("duplicate_method_metric_context_output_slot")
        if len(set(self.signature_parameter_names)) != len(self.signature_parameter_names):
            raise ValueError("duplicate_method_metric_signature_parameter")
        parameter_names = [item.name for item in self.parameter_values]
        input_ids = [item.method_input_slot_id for item in self.input_slot_values]
        role_ids = [item.role_id for item in self.input_role_values]
        role_slots = [item.method_input_slot_id for item in self.input_role_values]
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("duplicate_method_metric_context_parameter")
        if len(set(input_ids)) != len(input_ids):
            raise ValueError("duplicate_method_metric_context_input_value")
        if len(set(role_ids)) != len(role_ids) or len(set(role_slots)) != len(role_slots):
            raise ValueError("duplicate_method_metric_context_role_value")
        if self.dispatch_outcome == "not_run":
            if (
                self.started_at is not None
                or self.completed_at is not None
                or self.backend_trace_status != "not_started"
                or self.backend_attempts
                or self.fallback_status != "not_started"
            ):
                raise ValueError("not_run_method_metric_context_has_dispatch_observations")
        elif (
            self.started_at is None
            or self.completed_at is None
            or self.completed_at < self.started_at
        ):
            raise ValueError("dispatched_method_metric_context_requires_ordered_timestamps")
        if self.backend_trace_status == "captured":
            if (
                self.requested_backend is None
                or self.selected_backend is None
                or not self.backend_attempts
                or self.backend_attempts[-1].outcome != "success"
                or self.backend_attempts[-1].backend != self.selected_backend
                or self.fallback_status not in {"fell_back", "not_fell_back"}
            ):
                raise ValueError("captured_method_metric_backend_trace_is_incomplete")
            expected_fallback = (
                "fell_back"
                if any(attempt.outcome != "success" for attempt in self.backend_attempts[:-1])
                else "not_fell_back"
            )
            if self.fallback_status != expected_fallback:
                raise ValueError("method_metric_backend_fallback_differs_from_trace")
        elif self.backend_attempts:
            raise ValueError("unestablished_method_metric_backend_trace_has_attempts")
        if self.backend_trace_status == "not_started" and self.fallback_status != "not_started":
            raise ValueError("not_started_method_metric_trace_requires_not_started_fallback")
        if (
            self.backend_trace_status == "not_established"
            and self.fallback_status != "not_established"
        ):
            raise ValueError("unestablished_method_metric_trace_requires_limited_fallback")
        if not set(input_ids).issubset(set(self.signature_input_slot_ids)):
            raise ValueError("method_metric_context_input_not_in_signature")
        if any(
            item.method_input_slot_id not in set(self.signature_input_slot_ids)
            for item in self.input_role_values
        ):
            raise ValueError("method_metric_context_role_input_not_in_signature")
        if self.prestate_identity_status == "captured":
            if self.prestate_identity_sha256 is None:
                raise ValueError("captured_method_metric_prestate_requires_digest")
        elif self.prestate_identity_sha256 is not None:
            raise ValueError("unestablished_method_metric_prestate_cannot_have_digest")
        if self.backend_identity_status == "reconciled":
            if (
                self.actual_backend is None
                or not self.actual_backend.strip()
                or self.selected_backend != self.actual_backend
                or self.backend_trace_status != "captured"
                or self.backend_attempts[-1].backend != self.actual_backend
                or self.requested_backend is None
                or not self.requested_backend.strip()
            ):
                raise ValueError("reconciled_method_metric_backend_requires_identity")
        elif self.actual_backend is not None:
            raise ValueError("unreconciled_method_metric_backend_cannot_have_identity")
        if self.seed_status == "reconciled" and (
            self.method_seed is None
            or self.reproducibility_seed != self.method_seed
            or self.root_seed is None
            or self.step is None
            or not self.method_key_words
        ):
            raise ValueError("reconciled_method_metric_seed_requires_graph_and_runner_identity")
        if (self.method_build_digest is None) != (
            self.method_build_digest_scope != "class_source_only"
        ):
            raise ValueError("method_metric_context_build_identity_scope_mismatch")
        if self.parameter_resolution_status == "captured" and (
            any(item.status != "captured" for item in self.parameter_values)
            or {item.name for item in self.parameter_values} != set(self.signature_parameter_names)
        ):
            raise ValueError("captured_method_metric_parameters_must_cover_signature")
        return self


class MethodMetricSourceUnit(KernelModel):
    """Exact unit descriptor taken from a method ABI output slot."""

    dimension: str = Field(min_length=1)
    symbol: str
    scale: StrictInt | StrictFloat = Field(gt=0)

    @model_validator(mode="after")
    def finite_positive_scale(self) -> MethodMetricSourceUnit:
        if isinstance(self.scale, float) and not math.isfinite(self.scale):
            raise ValueError("method_metric_source_scale_not_finite")
        return self


class MethodMetricCapturedInputArray(KernelModel):
    """Law-required numeric input retained once with its exact runtime layout."""

    slot_id: StrictStr = Field(min_length=1)
    dtype: StrictStr = Field(min_length=1)
    shape: tuple[StrictInt, ...] = Field(max_length=4)
    values: tuple[StrictInt | StrictFloat, ...] = Field(max_length=1_000_000)
    value_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    unit: MethodMetricSourceUnit | None = None

    @model_validator(mode="after")
    def validate_capture_layout(self) -> MethodMetricCapturedInputArray:
        if any(size < 0 for size in self.shape):
            raise ValueError("method_metric_input_shape_must_be_non_negative")
        expected = math.prod(self.shape) if self.shape else 1
        if len(self.values) != expected:
            raise ValueError("method_metric_input_value_count_differs_from_shape")
        if any(isinstance(value, float) and not math.isfinite(value) for value in self.values):
            raise ValueError("method_metric_input_values_must_be_finite")
        if self.dtype.lstrip("<>=|")[:1] not in {"i", "u", "f"}:
            raise ValueError("method_metric_input_dtype_must_be_numeric")
        if _captured_array_value_sha256(self.dtype, self.shape, self.values) != self.value_sha256:
            raise ValueError("method_metric_input_value_digest_mismatch")
        return self


class RegisteredMethodMetricUnitAdapter(KernelModel):
    """Owner-computed outcome of exact source-to-target unit admission."""

    adapter_id: str
    adapter_version: str
    code_digest: str
    operation: Literal[
        "identity",
        "ratio_to_percent",
        "percent_to_ratio",
        "unsupported",
    ]
    factor_numerator: int | None = None
    factor_denominator: int | None = None
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_factor(self) -> RegisteredMethodMetricUnitAdapter:
        if self.operation == "unsupported":
            if not self.limitation or self.factor_numerator is not None:
                raise ValueError("unsupported_unit_adapter_requires_limitation")
        elif (
            self.limitation is not None
            or self.factor_numerator is None
            or self.factor_denominator is None
            or self.factor_denominator <= 0
        ):
            raise ValueError("registered_unit_adapter_requires_exact_factor")
        return self


class MethodMetricPredicateEvidence(KernelModel):
    """Owner-computed evidence for one semantic predicate of a metric law."""

    predicate_id: StrictStr = Field(min_length=1)
    classification: Literal[
        "recomputed",
        "independently_reconciled",
        "not_established",
    ]
    evidence_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    limitation: StrictStr | None = None

    @model_validator(mode="after")
    def validate_predicate_evidence(self) -> MethodMetricPredicateEvidence:
        if self.classification == "not_established" and not self.limitation:
            raise ValueError("unestablished_method_metric_predicate_requires_limitation")
        if self.classification != "not_established" and self.limitation is not None:
            raise ValueError("established_method_metric_predicate_cannot_have_limitation")
        return self


class RegisteredMethodMetricLawResult(KernelModel):
    """Finite direct output with exact rational identity or a typed limitation."""

    law_id: str
    law_version: str
    code_digest: str
    status: Literal["available", "unavailable"]
    value: StrictInt | StrictFloat | None = None
    exact_value_numerator: StrictInt | None = None
    exact_value_denominator: StrictInt | None = None
    limitation: str | None = None
    predicate_evidence: tuple[MethodMetricPredicateEvidence, ...] = ()

    @model_validator(mode="after")
    def validate_outcome(self) -> RegisteredMethodMetricLawResult:
        exact_pair_present = (
            self.exact_value_numerator is not None
            and self.exact_value_denominator is not None
            and self.exact_value_denominator > 0
        )
        if (self.exact_value_numerator is None) != (self.exact_value_denominator is None):
            raise ValueError("exact_method_metric_value_requires_fraction_pair")
        if self.status == "available":
            if (
                self.value is None
                or (isinstance(self.value, float) and not math.isfinite(self.value))
                or not exact_pair_present
                or self.limitation is not None
            ):
                raise ValueError("available_direct_output_requires_finite_exact_value")
        elif self.value is not None or not self.limitation:
            raise ValueError("unavailable_direct_output_requires_limitation")
        return self


class RegisteredMethodMetricUnitResult(KernelModel):
    """Exact converted quantity, available as float only when conversion is exact."""

    adapter_id: str
    adapter_version: str
    code_digest: str
    status: Literal["available", "unavailable"]
    value: StrictFloat | None = None
    exact_value_numerator: StrictInt | None = None
    exact_value_denominator: StrictInt | None = None
    limitation: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> RegisteredMethodMetricUnitResult:
        if (self.exact_value_numerator is None) != (self.exact_value_denominator is None):
            raise ValueError("exact_method_metric_unit_value_requires_fraction_pair")
        if self.exact_value_denominator is not None and self.exact_value_denominator <= 0:
            raise ValueError("exact_method_metric_unit_denominator_must_be_positive")
        if self.status == "available":
            if (
                self.value is None
                or not math.isfinite(self.value)
                or self.exact_value_numerator is None
                or self.exact_value_denominator is None
                or self.limitation is not None
            ):
                raise ValueError("available_method_metric_unit_value_requires_exact_float")
        elif self.value is not None or not self.limitation:
            raise ValueError("unavailable_method_metric_unit_requires_limitation")
        return self


def _code_digest() -> str:
    """Return a digest covering this module's registered law and adapter implementation."""
    payload = Path(__file__).read_bytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def registered_method_metric_law_metadata() -> tuple[str, str, str]:
    """Return the exact owner-pinned law identity and implementation digest."""
    return (
        METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
        METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION,
        _code_digest(),
    )


def registered_method_metric_law_metadata_for(
    method_fqn: str,
    method_version: str,
) -> tuple[str, str, str] | None:
    """Resolve a law only for an exact registered producer identity."""
    if method_fqn == "policy.evaluation.ex_ante_simulation@1.0.0" and method_version == "1.0.0":
        return (
            METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
            METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_VERSION,
            _code_digest(),
        )
    return None


def _is_exact_ex_ante_mean_change_semantics(
    semantics: MethodMetricSemanticContract,
) -> bool:
    """Return whether the compile-time semantics match the owned model-relative law."""
    actual_roles = tuple(
        sorted((item.role_id, item.method_input_slot_id) for item in semantics.input_roles)
    )
    return (
        semantics.quantity_kind == "value"
        and semantics.quantity_role == "scenario_delta"
        and semantics.population_id == "captured_model_input_rows"
        and semantics.axes == ("n_agents",)
        and semantics.denominator_id == "n_agents"
        and semantics.time_role == "pre_dispatch_state"
        and semantics.producer_contract_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        and semantics.output_value_path == ("mean_change",)
        and actual_roles == (("baseline", "baseline"), ("scenario", "scenario"))
    )


def registered_method_metric_input_unit_contract(
    law_id: str,
    semantics: MethodMetricSemanticContract | None,
) -> tuple[tuple[str, str, MethodMetricSourceUnit], ...] | None:
    """Return the exact registered input units required by a method metric law.

    The result is ``None`` unless the supplied law and role contract match the
    registered Ex-Ante producer exactly. A successful result covers every
    semantic role and preserves both role and ABI slot identity.
    """
    if (
        law_id != METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        or semantics is None
        or not _is_exact_ex_ante_mean_change_semantics(semantics)
    ):
        return None
    expected_unit = MethodMetricSourceUnit(
        dimension="value",
        symbol="amount",
        scale=1,
    )
    return tuple(
        (
            item.role_id,
            item.method_input_slot_id,
            expected_unit,
        )
        for item in sorted(
            semantics.input_roles, key=lambda role: (role.role_id, role.method_input_slot_id)
        )
    )


def registered_method_metric_semantics_match(
    law_id: str,
    semantics: MethodMetricSemanticContract | None,
) -> bool:
    """Check semantics against the exact owner-registered law definition."""
    return (
        law_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        and semantics is not None
        and _is_exact_ex_ante_mean_change_semantics(semantics)
    )


def _captured_array_value_sha256(
    dtype: str,
    shape: tuple[int, ...],
    values: Sequence[int | float],
) -> str:
    """Recreate the exact bounded NumPy identity bytes from a captured array row."""
    byte_order = dtype[0] if dtype and dtype[0] in "<>=|" else "="
    dtype_body = dtype[1:] if byte_order != "=" or (dtype and dtype[0] == "=") else dtype
    kind = dtype_body[:1]
    try:
        item_size = int(dtype_body[1:])
    except ValueError as exc:
        raise ValueError("method_metric_input_dtype_not_canonical") from exc
    if kind == "f" and item_size in {2, 4, 8}:
        format_char = {2: "e", 4: "f", 8: "d"}[item_size]
    elif kind in {"i", "u"} and item_size in {1, 2, 4, 8}:
        format_char = {
            ("i", 1): "b",
            ("i", 2): "h",
            ("i", 4): "i",
            ("i", 8): "q",
            ("u", 1): "B",
            ("u", 2): "H",
            ("u", 4): "I",
            ("u", 8): "Q",
        }[(kind, item_size)]
    else:
        raise ValueError("method_metric_input_dtype_not_supported")
    prefix = "<" if byte_order in {"<", "|"} else ">" if byte_order == ">" else "="
    try:
        value_bytes = b"".join(struct.pack(prefix + format_char, value) for value in values)
    except (OverflowError, TypeError, ValueError, struct.error) as exc:
        raise ValueError("method_metric_input_value_not_representable_by_dtype") from exc
    digest = hashlib.sha256()
    digest.update(dtype.encode("ascii"))
    digest.update(json.dumps(shape, separators=(",", ":")).encode("ascii"))
    digest.update(value_bytes)
    return digest.hexdigest()


def registered_method_metric_unit_adapter_metadata() -> tuple[str, str, str]:
    """Return the exact owner-pinned adapter identity and implementation digest."""
    return (
        METHOD_METRIC_UNIT_ADAPTER_ID,
        METHOD_METRIC_UNIT_ADAPTER_VERSION,
        _code_digest(),
    )


def _unsupported(limitation: str) -> RegisteredMethodMetricUnitAdapter:
    return RegisteredMethodMetricUnitAdapter(
        adapter_id=METHOD_METRIC_UNIT_ADAPTER_ID,
        adapter_version=METHOD_METRIC_UNIT_ADAPTER_VERSION,
        code_digest=_code_digest(),
        operation="unsupported",
        limitation=limitation,
    )


def resolve_registered_method_metric_unit_adapter(
    source: MethodMetricSourceUnit,
    target: UnitSpecType,
    *,
    law_id: str | None = None,
    semantics: MethodMetricSemanticContract | None = None,
) -> RegisteredMethodMetricUnitAdapter:
    """Resolve only exact identities and the registered ratio/percent relation.

    No conversion is authorized by dimensional compatibility alone. The only
    non-identity conversion is the exact rational ratio/percent pair.
    """
    factor: Fraction | None = None
    operation: Literal["identity", "ratio_to_percent", "percent_to_ratio"] | None = None

    if (
        law_id == METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        and semantics is not None
        and _is_exact_ex_ante_mean_change_semantics(semantics)
        and source.dimension == "value"
        and source.symbol == "amount"
        and source.scale == 1
        and isinstance(target, GenericUnit)
        and target.label == "value"
    ):
        # The registered producer subtracts two values with the same input ABI
        # unit. This is an exact identity for the scenario-delta role only.
        factor, operation = Fraction(1), "identity"
    elif (
        isinstance(target, RateUnit)
        and source.dimension == "ratio"
        and law_id == METHOD_METRIC_DIRECT_OUTPUT_LAW_ID
        and semantics is not None
        and semantics.quantity_kind == "ratio"
    ):
        source_scale = {
            "1": Fraction(1),
            "ratio": Fraction(1),
            "%": Fraction(1, 100),
            "percent": Fraction(1, 100),
        }.get(source.symbol)
        declared_scale = (
            Fraction(source.scale) if isinstance(source.scale, int) else Fraction(str(source.scale))
        )
        if source_scale is not None and declared_scale == source_scale:
            target_scale = Fraction(1) if target.base == "ratio" else Fraction(1, 100)
            factor = source_scale / target_scale
            if factor == 1:
                operation = "identity"
            elif target.base == "percent":
                operation = "ratio_to_percent"
            else:
                operation = "percent_to_ratio"
    # Other dimensional identities are not inferred from matching labels. They need
    # an exact method law that establishes the same quantity and is registered here.

    if factor is None or operation is None:
        return _unsupported("unit_relation_not_registered")
    return RegisteredMethodMetricUnitAdapter(
        adapter_id=METHOD_METRIC_UNIT_ADAPTER_ID,
        adapter_version=METHOD_METRIC_UNIT_ADAPTER_VERSION,
        code_digest=_code_digest(),
        operation=operation,
        factor_numerator=factor.numerator,
        factor_denominator=factor.denominator,
    )


def apply_registered_direct_output_law(
    value: object,
    semantics: MethodMetricSemanticContract,
    *,
    execution_context: MethodMetricExecutionContext | None = None,
    expected_method_fqn: str | None = None,
    expected_method_version: str | None = None,
    expected_method_abi_digest: str | None = None,
    expected_method_abi_digest_algorithm: str | None = None,
    expected_output_slot_id: str | None = None,
) -> RegisteredMethodMetricLawResult:
    """Refuse generic direct-output admission without a registered meaning law.

    A scalar shape and caller-declared roles do not establish quantity meaning.
    This compatibility entrypoint is intentionally unavailable for every input;
    method-specific registered laws must recompute their own scoped meaning.
    """
    del (
        value,
        semantics,
        execution_context,
        expected_method_fqn,
        expected_method_version,
        expected_method_abi_digest,
        expected_method_abi_digest_algorithm,
        expected_output_slot_id,
    )
    return RegisteredMethodMetricLawResult(
        law_id=METHOD_METRIC_DIRECT_OUTPUT_LAW_ID,
        law_version=METHOD_METRIC_DIRECT_OUTPUT_LAW_VERSION,
        code_digest=_code_digest(),
        status="unavailable",
        limitation="registered_method_metric_law_missing",
    )


def _ex_ante_unavailable(
    limitation: str,
    *,
    predicates: Sequence[MethodMetricPredicateEvidence] = (),
    exact_value: Fraction | None = None,
) -> RegisteredMethodMetricLawResult:
    return RegisteredMethodMetricLawResult(
        law_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        law_version=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_VERSION,
        code_digest=_code_digest(),
        status="unavailable",
        exact_value_numerator=None if exact_value is None else exact_value.numerator,
        exact_value_denominator=None if exact_value is None else exact_value.denominator,
        limitation=limitation,
        predicate_evidence=tuple(predicates),
    )


def _ex_ante_external_predicates() -> tuple[MethodMetricPredicateEvidence, ...]:
    """Keep institutional and external adequacy claims separate from recomputation."""
    return tuple(
        MethodMetricPredicateEvidence(
            predicate_id=predicate_id,
            classification="not_established",
            limitation=limitation,
        )
        for predicate_id, limitation in (
            (
                "method_metric.external_row_representativeness",
                "captured_model_input_rows_are_not_an_external_population_sample_claim",
            ),
            (
                "method_metric.external_causal_validity",
                "registered_output_recomputation_does_not_establish_causal_validity",
            ),
            (
                "method_metric.external_empirical_calibration",
                "registered_output_recomputation_does_not_establish_empirical_calibration",
            ),
            (
                "method_metric.external_legal_permission",
                "registered_output_recomputation_does_not_establish_legal_or_publication_permission",
            ),
        )
    )


def apply_registered_ex_ante_mean_change_law(
    value: float,
    semantics: MethodMetricSemanticContract,
    *,
    execution_context: MethodMetricExecutionContext,
    input_values: Sequence[MethodMetricCapturedInputArray],
    input_capture_prestate_identity_sha256: str | None,
    expected_method_fqn: str,
    expected_method_version: str,
    expected_method_abi_digest: str,
    expected_method_abi_digest_algorithm: str,
    expected_method_build_digest: str,
    expected_output_slot_id: str,
    expected_output_value_path: tuple[str, ...],
    target_unit: UnitSpecType,
) -> RegisteredMethodMetricLawResult:
    """Recompute the registered model-input-relative Ex-Ante mean change.

    This law establishes only the exact input-row computation performed by
    ``ExAnteSimulationEstimator``. It does not establish row representativeness,
    causal validity, calibration, external population identity, or permission.
    """
    digest = _code_digest()
    predicates = list(_ex_ante_external_predicates())
    if (
        expected_method_fqn != "policy.evaluation.ex_ante_simulation@1.0.0"
        or expected_method_version != "1.0.0"
        or expected_method_abi_digest_algorithm != "blake2b"
        or expected_output_slot_id != "result"
        or expected_output_value_path != ("mean_change",)
        or execution_context.method_fqn != expected_method_fqn
        or execution_context.method_version != expected_method_version
        or execution_context.method_abi_digest != expected_method_abi_digest
        or execution_context.method_abi_digest_algorithm != expected_method_abi_digest_algorithm
        or execution_context.method_build_digest != expected_method_build_digest
        or execution_context.method_build_digest_scope != "class_source_only"
        or execution_context.output_slot_id != expected_output_slot_id
        or execution_context.output_value_path != expected_output_value_path
        or "result" not in execution_context.signature_output_slot_ids
    ):
        return _ex_ante_unavailable("method_execution_binding_identity_mismatch")
    predicates.append(
        MethodMetricPredicateEvidence(
            predicate_id="method_metric.method_identity",
            classification="independently_reconciled",
        )
    )
    if not _is_exact_ex_ante_mean_change_semantics(semantics):
        return _ex_ante_unavailable(
            "ex_ante_mean_change_semantics_not_exact",
            predicates=predicates,
        )
    if (
        execution_context.dispatch_outcome != "succeeded"
        or execution_context.parameter_resolution_status != "captured"
        or len(execution_context.graph_input_ids) != 2
        or set(execution_context.graph_input_ids) != {"baseline", "scenario"}
        or {item.name for item in execution_context.parameter_values}
        != set(execution_context.signature_parameter_names)
        or execution_context.signature_parameter_names != ("poverty_line",)
        or execution_context.signature_input_slot_ids != ("baseline", "scenario")
        or execution_context.signature_output_slot_ids != ("result",)
        or execution_context.requested_backend != "numpy"
        or execution_context.selected_backend != "numpy"
        or execution_context.actual_backend != "numpy"
        or execution_context.backend_trace_status != "captured"
        or execution_context.backend_identity_status != "reconciled"
        or execution_context.fallback_status != "not_fell_back"
        or execution_context.seed_status != "reconciled"
        or execution_context.rng_state_status != "runner_rng_state_not_retained"
    ):
        return _ex_ante_unavailable(
            "ex_ante_execution_context_not_established",
            predicates=predicates,
        )
    predicates.append(
        MethodMetricPredicateEvidence(
            predicate_id="method_metric.execution_context",
            classification="independently_reconciled",
        )
    )
    if (
        execution_context.prestate_identity_status != "captured"
        or execution_context.prestate_identity_sha256 is None
        or input_capture_prestate_identity_sha256 != execution_context.prestate_identity_sha256
    ):
        return _ex_ante_unavailable(
            "ex_ante_input_capture_prestate_mismatch",
            predicates=predicates,
        )
    predicates.append(
        MethodMetricPredicateEvidence(
            predicate_id="method_metric.pre_dispatch_state_identity",
            classification="independently_reconciled",
        )
    )
    role_rows = {
        (item.role_id, item.method_input_slot_id, item.value_sha256)
        for item in execution_context.input_role_values
    }
    input_rows = {item.slot_id: item for item in input_values}
    input_digests = {
        item.method_input_slot_id: item.value_sha256
        for item in execution_context.input_slot_values
        if item.status == "captured"
    }
    expected_roles = {
        ("baseline", "baseline", input_digests.get("baseline")),
        ("scenario", "scenario", input_digests.get("scenario")),
    }
    if (
        set(input_rows) != {"baseline", "scenario"}
        or len(input_rows) != len(input_values)
        or role_rows != expected_roles
        or set(input_digests) != {"baseline", "scenario"}
        or any(input_rows[name].value_sha256 != input_digests[name] for name in input_rows)
    ):
        return _ex_ante_unavailable(
            "ex_ante_actual_input_roles_or_content_not_reconciled",
            predicates=predicates,
        )
    try:
        captured_input_digests = {
            item.slot_id: _captured_array_value_sha256(item.dtype, item.shape, item.values)
            for item in input_values
        }
    except (TypeError, ValueError, UnicodeError):
        return _ex_ante_unavailable(
            "ex_ante_captured_input_content_digest_mismatch",
            predicates=predicates,
        )
    if any(
        captured_input_digests.get(slot_id) != input_rows[slot_id].value_sha256
        for slot_id in input_rows
    ):
        return _ex_ante_unavailable(
            "ex_ante_captured_input_content_digest_mismatch",
            predicates=predicates,
        )
    predicates.append(
        MethodMetricPredicateEvidence(
            predicate_id="method_metric.actual_input_role_mapping",
            classification="recomputed",
        )
    )
    baseline = input_rows["baseline"]
    scenario = input_rows["scenario"]
    if (
        baseline.shape != scenario.shape
        or len(baseline.shape) != 1
        or baseline.shape[0] <= 0
        or len(baseline.values) != baseline.shape[0]
        or len(scenario.values) != scenario.shape[0]
    ):
        return _ex_ante_unavailable(
            "ex_ante_paired_input_rows_not_established",
            predicates=predicates,
        )
    predicates.extend(
        (
            MethodMetricPredicateEvidence(
                predicate_id="method_metric.paired_model_input_rows",
                classification="recomputed",
            ),
            MethodMetricPredicateEvidence(
                predicate_id="method_metric.n_agents_denominator",
                classification="recomputed",
            ),
            MethodMetricPredicateEvidence(
                predicate_id="method_metric.model_input_rowset_scope",
                classification="recomputed",
            ),
        )
    )
    input_unit_contract = registered_method_metric_input_unit_contract(
        METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        semantics,
    )
    expected_input_units = (
        {slot_id: expected_unit for _, slot_id, expected_unit in input_unit_contract}
        if input_unit_contract is not None
        else {}
    )
    if (
        set(expected_input_units) != {"baseline", "scenario"}
        or baseline.unit != expected_input_units.get("baseline")
        or scenario.unit != expected_input_units.get("scenario")
        or not isinstance(target_unit, GenericUnit)
        or target_unit.label != "value"
    ):
        return _ex_ante_unavailable(
            "ex_ante_scenario_delta_unit_or_quantity_role_not_established",
            predicates=predicates,
        )
    predicates.append(
        MethodMetricPredicateEvidence(
            predicate_id="method_metric.scenario_delta_quantity_role_and_unit",
            classification="recomputed",
        )
    )

    exact_differences: list[Fraction] = []
    for left, right in zip(baseline.values, scenario.values, strict=True):
        if isinstance(left, bool) or isinstance(right, bool):
            return _ex_ante_unavailable(
                "ex_ante_input_numeric_type_not_established",
                predicates=predicates,
            )
        try:
            baseline_float = float(left)
            scenario_float = float(right)
        except (OverflowError, TypeError, ValueError):
            return _ex_ante_unavailable(
                "ex_ante_input_numeric_precision_not_established",
                predicates=predicates,
            )
        if (
            not math.isfinite(baseline_float)
            or not math.isfinite(scenario_float)
            or (isinstance(left, int) and int(baseline_float) != left)
            or (isinstance(right, int) and int(scenario_float) != right)
        ):
            return _ex_ante_unavailable(
                "ex_ante_input_numeric_precision_not_established",
                predicates=predicates,
            )
        difference = scenario_float - baseline_float
        if not math.isfinite(difference):
            return _ex_ante_unavailable(
                "ex_ante_input_numeric_precision_not_established",
                predicates=predicates,
            )
        exact_differences.append(Fraction.from_float(difference))
    exact_mean = sum(exact_differences, Fraction()) / len(exact_differences)
    try:
        expected_float = float(exact_mean)
    except (OverflowError, ValueError):
        expected_float = math.inf
    if (
        not math.isfinite(expected_float)
        or Fraction.from_float(expected_float) != exact_mean
        or isinstance(value, bool)
        or not isinstance(value, float)
        or not math.isfinite(value)
        or value != expected_float
    ):
        return _ex_ante_unavailable(
            "ex_ante_mean_change_or_numeric_precision_not_reconciled",
            predicates=predicates,
            exact_value=exact_mean,
        )
    predicates.append(
        MethodMetricPredicateEvidence(
            predicate_id="method_metric.mean_change_recomputed_from_actual_inputs",
            classification="recomputed",
        )
    )
    return RegisteredMethodMetricLawResult(
        law_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        law_version=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_VERSION,
        code_digest=digest,
        status="available",
        value=value,
        exact_value_numerator=exact_mean.numerator,
        exact_value_denominator=exact_mean.denominator,
        predicate_evidence=tuple(predicates),
    )


def apply_registered_method_metric_unit_adapter(
    value: RegisteredMethodMetricLawResult,
    adapter: RegisteredMethodMetricUnitAdapter,
) -> RegisteredMethodMetricUnitResult:
    """Apply a registered exact rational factor without silently rounding."""
    if value.status != "available":
        return RegisteredMethodMetricUnitResult(
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.adapter_version,
            code_digest=adapter.code_digest,
            status="unavailable",
            limitation=value.limitation or "direct_output_not_available",
        )
    if adapter.operation == "unsupported":
        return RegisteredMethodMetricUnitResult(
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.adapter_version,
            code_digest=adapter.code_digest,
            status="unavailable",
            limitation=adapter.limitation or "unit_relation_not_registered",
        )
    if adapter.factor_numerator is None or adapter.factor_denominator is None:
        return RegisteredMethodMetricUnitResult(
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.adapter_version,
            code_digest=adapter.code_digest,
            status="unavailable",
            limitation="unit_adapter_exact_factor_missing",
        )
    if value.exact_value_numerator is None or value.exact_value_denominator is None:
        return RegisteredMethodMetricUnitResult(
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.adapter_version,
            code_digest=adapter.code_digest,
            status="unavailable",
            limitation="direct_output_exact_value_missing",
        )
    exact_value = Fraction(
        value.exact_value_numerator,
        value.exact_value_denominator,
    ) * Fraction(adapter.factor_numerator, adapter.factor_denominator)
    try:
        numeric_value = float(exact_value)
    except (OverflowError, ValueError):
        numeric_value = math.inf
    if not math.isfinite(numeric_value) or Fraction.from_float(numeric_value) != exact_value:
        return RegisteredMethodMetricUnitResult(
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.adapter_version,
            code_digest=adapter.code_digest,
            status="unavailable",
            exact_value_numerator=exact_value.numerator,
            exact_value_denominator=exact_value.denominator,
            limitation="numeric_precision_not_established",
        )
    return RegisteredMethodMetricUnitResult(
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.adapter_version,
        code_digest=adapter.code_digest,
        status="available",
        value=numeric_value,
        exact_value_numerator=exact_value.numerator,
        exact_value_denominator=exact_value.denominator,
    )
