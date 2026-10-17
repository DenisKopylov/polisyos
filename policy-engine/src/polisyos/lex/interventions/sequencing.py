"""Compile ordered Lex intervention inputs into IR temporal sequences."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import Field

from polisyos.ir import (
    CompiledLexIntervention as _CompiledLexIntervention,
)
from polisyos.ir import (
    IdentificationMode,
    StrategicResponseChannel,
    TemporalInterventionSequence,
    TemporalInterventionStep,
)
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.values import ParamValue


class TemporalInterventionStepInput(KernelModel):
    """Friendly input shape for one time-ordered intervention activation step."""

    step_id: str | None = Field(None, pattern=ID_PATTERN)
    effective_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}(-\d{2})?$",
    )
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    parameter_overrides: dict[str, ParamValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list, max_length=20)


class TemporalInterventionSequencer:
    """Compile legal intervention timelines into DTR-ready sequence contracts."""

    def compile_sequence(
        self,
        *,
        sequence_id: str,
        dynamic_intervention_id: str,
        steps: Sequence[
            TemporalInterventionStepInput | TemporalInterventionStep | Mapping[str, Any]
        ],
        compiled_interventions: (
            Sequence[_CompiledLexIntervention | Mapping[str, Any]]
            | Mapping[str, _CompiledLexIntervention | Mapping[str, Any]]
            | None
        ) = None,
        identification_mode: IdentificationMode = IdentificationMode.SEQUENTIAL,
        strategic_response_expected: bool = False,
        transmission_channels: Sequence[StrategicResponseChannel] = (),
        notes: Sequence[str] = (),
    ) -> TemporalInterventionSequence:
        """Build an ordered ``TemporalInterventionSequence`` from step inputs.

        Raises:
            ValueError: If a step references an unknown intervention id or unknown parameter
                override when ``compiled_interventions`` are provided.
        """
        compiled_catalog = _normalize_compiled_intervention_catalog(compiled_interventions)
        normalized_steps = [
            self._normalize_step(step, index) for index, step in enumerate(steps, start=1)
        ]
        if compiled_catalog:
            for step in normalized_steps:
                compiled = compiled_catalog.get(step.intervention_id)
                if compiled is None:
                    raise ValueError(
                        f"unknown intervention_id '{step.intervention_id}' for temporal sequence"
                    )
                known_params = {parameter.param_id for parameter in compiled.parameters}
                unknown_params = sorted(set(step.parameter_overrides) - known_params)
                if unknown_params:
                    raise ValueError(
                        "unknown parameter_overrides for "
                        f"'{step.intervention_id}': {', '.join(unknown_params)}"
                    )
        return TemporalInterventionSequence(
            sequence_id=sequence_id,
            dynamic_intervention_id=dynamic_intervention_id,
            identification_mode=identification_mode,
            strategic_response_expected=strategic_response_expected,
            transmission_channels=list(transmission_channels),
            steps=normalized_steps,
            notes=list(notes),
        )

    def _normalize_step(
        self,
        step: TemporalInterventionStepInput | TemporalInterventionStep | Mapping[str, Any],
        index: int,
    ) -> TemporalInterventionStep:
        if isinstance(step, TemporalInterventionStep):
            return step
        if isinstance(step, TemporalInterventionStepInput):
            payload = step.model_dump(mode="python", exclude_none=True)
        else:
            payload = dict(step)
        payload.setdefault("step_id", f"step_{index}")
        return TemporalInterventionStep.model_validate(payload)


def _normalize_compiled_intervention_catalog(
    compiled_interventions: (
        Sequence[_CompiledLexIntervention | Mapping[str, Any]]
        | Mapping[str, _CompiledLexIntervention | Mapping[str, Any]]
        | None
    ),
) -> dict[str, _CompiledLexIntervention]:
    if compiled_interventions is None:
        return {}
    if isinstance(compiled_interventions, Mapping):
        values = compiled_interventions.values()
    else:
        values = compiled_interventions
    catalog: dict[str, _CompiledLexIntervention] = {}
    for item in values:
        compiled = (
            item
            if isinstance(item, _CompiledLexIntervention)
            else _CompiledLexIntervention.model_validate(item)
        )
        catalog[compiled.intervention.intervention_id] = compiled
    return catalog


__all__ = ["TemporalInterventionSequencer", "TemporalInterventionStepInput"]
