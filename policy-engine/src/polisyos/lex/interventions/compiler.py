"""Compile typed legal provision directives into IR interventions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from polisyos.ir import (
    CompiledLexIntervention as _CompiledLexIntervention,
)
from polisyos.ir import IdentificationMode, ParameterSpec, StrategicResponseChannel
from polisyos.ir.governance import InterventionSpec, ScheduleSpec, SelectorExpr
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.values import (
    CountValue,
    DurationValue,
    MoneyValue,
    ParamValue,
    RateValue,
)
from polisyos.lex.interventions.artifacts import LexProvisionMappingRegistry


class InterventionKnobSpec(KernelModel):
    """Tunable parameter exposed by a legal provision mapping.

    Bounds are validated by ``LexInterventionCompiler`` against ``default_value`` and duplicate
    ``param_id`` / ``param_path`` values are rejected per directive.
    """

    param_id: str = Field(..., pattern=ID_PATTERN)
    param_path: str = Field(..., min_length=1, max_length=120)
    default_value: ParamValue
    min_value: ParamValue | None = None
    max_value: ParamValue | None = None
    tunable: bool = True
    sensitivity_priority: int = Field(default=5, ge=1, le=10)
    notes: list[str] = Field(default_factory=list, max_length=10)


class LexProvisionDirective(KernelModel):
    """Provision-level request that compiles one legal clause into an ``InterventionSpec``.

    The directive is usually produced by ``LexProvisionMappingRegistry.resolve`` and then passed
    to ``LexInterventionCompiler.compile``. Strategic-response settings must be internally
    consistent: when ``strategic_response_expected`` is true, at least one transmission channel
    must be declared.
    """

    provision_ref: str = Field(..., min_length=1, max_length=200)
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    intervention_kind: str = Field(..., pattern=ID_PATTERN)
    target: SelectorExpr
    schedule: ScheduleSpec
    params: dict[str, ParamValue] = Field(default_factory=dict)
    knobs: list[InterventionKnobSpec] = Field(default_factory=list)
    target_population_type: str | None = Field(None, max_length=120)
    target_sector_ids: list[str] = Field(default_factory=list)
    target_region_ids: list[str] = Field(default_factory=list)
    measurement_expectations: dict[str, Any] = Field(default_factory=dict)
    identification_mode: IdentificationMode | None = None
    strategic_response_expected: bool = False
    transmission_channels: list[StrategicResponseChannel] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, max_length=10)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_strategy_channels(self) -> LexProvisionDirective:
        if self.strategic_response_expected and not self.transmission_channels:
            raise ValueError(
                "transmission_channels are required when strategic_response_expected=True"
            )
        return self


class LexInterventionCompiler:
    """Compile Lex provision directives into executable intervention contracts."""

    def compile(
        self,
        directive: LexProvisionDirective | Mapping[str, Any],
    ) -> _CompiledLexIntervention:
        """Compile one directive into an intervention contract plus tunable parameter specs.

        Args:
            directive: Typed ``LexProvisionDirective`` or a mapping accepted by its Pydantic model.

        Returns:
            ``CompiledLexIntervention`` containing the IR intervention contract, generated
            ``ParameterSpec`` rows, and mapping metadata.

        Raises:
            ValueError: If knob identifiers/paths are duplicated, point to unknown params, or
                define inverted/out-of-range bounds.
        """
        resolved = (
            directive
            if isinstance(directive, LexProvisionDirective)
            else LexProvisionDirective.model_validate(directive)
        )
        self._validate_knobs(resolved)
        intervention = InterventionSpec(
            intervention_id=resolved.intervention_id,
            kind=resolved.intervention_kind,
            target=resolved.target,
            schedule=resolved.schedule,
            params=resolved.params,
            lex_provision_ref=resolved.provision_ref,
            target_population_type=resolved.target_population_type,
            target_sector_ids=resolved.target_sector_ids,
            target_region_ids=resolved.target_region_ids,
            measurement_expectations=resolved.measurement_expectations,
            identification_mode=resolved.identification_mode,
            strategic_response_expected=resolved.strategic_response_expected,
            transmission_channels=resolved.transmission_channels,
            notes=resolved.notes,
        )
        parameters = [
            ParameterSpec(
                param_id=knob.param_id,
                intervention_id=resolved.intervention_id,
                param_path=knob.param_path,
                default_value=knob.default_value,
                min_value=knob.min_value,
                max_value=knob.max_value,
                tunable=knob.tunable,
                sensitivity_priority=knob.sensitivity_priority,
            )
            for knob in resolved.knobs
        ]
        compiled_metadata = dict(resolved.metadata)
        compiled_metadata.setdefault("knob_ids", [knob.param_id for knob in resolved.knobs])
        compiled_metadata.setdefault("provision_ref", resolved.provision_ref)
        return _CompiledLexIntervention(
            intervention=intervention,
            parameters=parameters,
            metadata=compiled_metadata,
        )

    def compile_from_mapping(
        self,
        registry: LexProvisionMappingRegistry,
        provision_ref: str,
        *,
        intervention_id: str,
        target: SelectorExpr | Mapping[str, Any],
        schedule: ScheduleSpec | Mapping[str, Any],
        params: Mapping[str, ParamValue] | None = None,
        knob_value_overrides: Mapping[str, ParamValue] | None = None,
        target_population_type: str | None = None,
        target_sector_ids: Sequence[str] | None = None,
        target_region_ids: Sequence[str] | None = None,
        measurement_expectations: Mapping[str, Any] | None = None,
        identification_mode: IdentificationMode | None = None,
        strategic_response_expected: bool | None = None,
        transmission_channels: Sequence[StrategicResponseChannel] | None = None,
        notes: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> _CompiledLexIntervention:
        """Resolve a provision mapping from a registry and compile it into IR contracts.

        Args:
            registry: Provision mapping and knob registry.
            provision_ref: Legal provision key expected by the registry.
            intervention_id: Target intervention id to place on the compiled IR contract.
            target: Selector expression for intervention targeting.
            schedule: Schedule contract for the intervention lifecycle.
            params: Optional base parameter payload before knob overrides are applied.
            knob_value_overrides: Optional values keyed by knob id.
            target_population_type: Optional override for registry population metadata.
            target_sector_ids: Optional explicit sector override.
            target_region_ids: Optional explicit region override.
            measurement_expectations: Optional expectation metadata merged with the registry entry.
            identification_mode: Optional override for the registry identification mode.
            strategic_response_expected: Optional consistency-checked override.
            transmission_channels: Optional consistency-checked channel override.
            notes: Additional notes appended to the compiled directive.
            metadata: Additional metadata merged into the compiled payload.

        Returns:
            Compiled intervention and parameter specs.

        Raises:
            KeyError: If the provision mapping or one of its knob ids is unknown.
            ValueError: If explicit strategic-response overrides conflict with the registry.
        """
        mapping_entry = registry.require_mapping(provision_ref)
        if (
            strategic_response_expected is not None
            and strategic_response_expected != mapping_entry.strategic_response_expected
        ):
            raise ValueError("explicit strategic_response_expected conflicts with registry mapping")
        if transmission_channels is not None and tuple(transmission_channels) != tuple(
            mapping_entry.transmission_channels
        ):
            raise ValueError("explicit transmission_channels conflict with registry mapping")
        directive = registry.resolve(
            provision_ref,
            intervention_id=intervention_id,
            target=target,
            schedule=schedule,
            params=params,
            knob_value_overrides=knob_value_overrides,
            target_population_type=target_population_type,
            target_sector_ids=target_sector_ids,
            target_region_ids=target_region_ids,
            measurement_expectations=measurement_expectations,
            identification_mode=identification_mode,
            strategic_response_expected=strategic_response_expected,
            transmission_channels=transmission_channels,
            notes=notes,
            metadata=metadata,
        )
        return self.compile(directive)

    def _validate_knobs(self, directive: LexProvisionDirective) -> None:
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for knob in directive.knobs:
            if knob.param_id in seen_ids:
                raise ValueError(f"duplicate knob param_id '{knob.param_id}'")
            if knob.param_path in seen_paths:
                raise ValueError(f"duplicate knob param_path '{knob.param_path}'")
            seen_ids.add(knob.param_id)
            seen_paths.add(knob.param_path)
            self._validate_knob_path(knob, directive.params)
            self._validate_knob_bounds(knob)

    def _validate_knob_path(
        self,
        knob: InterventionKnobSpec,
        params: Mapping[str, Any],
    ) -> None:
        value, ok = _resolve_param_path(params, knob.param_path)
        if not ok:
            raise ValueError(
                f"knob '{knob.param_id}' references unknown intervention param '{knob.param_path}'"
            )
        if value != knob.default_value and _param_value_to_decimal(
            value
        ) == _param_value_to_decimal(knob.default_value):
            return

    def _validate_knob_bounds(self, knob: InterventionKnobSpec) -> None:
        default_value = _param_value_to_decimal(knob.default_value)
        min_value = _param_value_to_decimal(knob.min_value)
        max_value = _param_value_to_decimal(knob.max_value)
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"knob '{knob.param_id}' has inverted bounds")
        if min_value is not None and default_value is not None and default_value < min_value:
            raise ValueError(f"knob '{knob.param_id}' default_value is below min_value")
        if max_value is not None and default_value is not None and default_value > max_value:
            raise ValueError(f"knob '{knob.param_id}' default_value is above max_value")


def _resolve_param_key(param_path: str) -> str:
    normalized = param_path.removeprefix("params.")
    return normalized.split(".", 1)[0]


def _resolve_param_path(
    params: Mapping[str, Any],
    param_path: str,
) -> tuple[Any, bool]:
    parts = [part for part in param_path.removeprefix("params.").split(".") if part]
    if not parts:
        return None, False
    current: Any = dict(params)
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _param_value_to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, MoneyValue):
        return value.amount
    if isinstance(value, RateValue):
        return value.as_ratio()
    if isinstance(value, CountValue):
        return Decimal(value.value)
    if isinstance(value, DurationValue):
        return Decimal(value.value)
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            return None
    return None


__all__ = ["InterventionKnobSpec", "LexInterventionCompiler", "LexProvisionDirective"]
