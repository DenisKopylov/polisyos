"""Computed coverage over exact required model-input step scopes."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from polisyos.core.contracts.model_input_period_steps import ModelInputStepScope


class ModelInputStepCoverage(BaseModel):
    """Reconcile selected model-input step scopes against a required denominator.

    This helper records exact scope coverage only. It does not establish source
    authority, currentness, or execution.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    required_step_scopes: tuple[ModelInputStepScope, ...]
    supplied_step_scopes: tuple[ModelInputStepScope, ...] = ()

    @model_validator(mode="after")
    def _validate_exact_coverage(self) -> Self:
        """Require canonical unique scopes and exact supplied matches."""
        required_keys = tuple((item.port_id, item.step) for item in self.required_step_scopes)
        supplied_keys = tuple((item.port_id, item.step) for item in self.supplied_step_scopes)

        for field_name, keys in (
            ("required", required_keys),
            ("supplied", supplied_keys),
        ):
            if keys != tuple(sorted(keys)):
                raise ValueError(f"model_input_step_coverage_{field_name}_order_invalid")
            if len(keys) != len(set(keys)):
                raise ValueError(f"model_input_step_coverage_{field_name}_duplicate")

        required_by_key = {(item.port_id, item.step): item for item in self.required_step_scopes}
        for key, supplied in zip(supplied_keys, self.supplied_step_scopes, strict=True):
            required = required_by_key.get(key)
            if required is None:
                raise ValueError("model_input_step_coverage_supplied_scope_extra")
            if required != supplied:
                raise ValueError("model_input_step_coverage_supplied_scope_mismatch")

        return self

    @property
    def missing_step_scopes(self) -> tuple[ModelInputStepScope, ...]:
        """Return required scopes without an exact supplied match."""
        supplied_keys = {(item.port_id, item.step) for item in self.supplied_step_scopes}
        return tuple(
            item
            for item in self.required_step_scopes
            if (item.port_id, item.step) not in supplied_keys
        )

    @property
    def is_complete(self) -> bool:
        """Return whether every required step scope is supplied."""
        return not self.missing_step_scopes

    def require_complete(self) -> Self:
        """Return this coverage only when no required scopes are missing.

        Raises:
            ValueError: If one or more required step scopes are missing.
        """
        if not self.is_complete:
            raise ValueError("model_input_step_coverage_incomplete")
        return self


def reconcile_model_input_step_coverage(
    *,
    required_step_scopes: tuple[ModelInputStepScope, ...],
    supplied_step_scopes: tuple[ModelInputStepScope, ...] = (),
) -> ModelInputStepCoverage:
    """Validate supplied scopes against the full required step denominator.

    Empty and partial supplied selections remain valid candidates so callers
    can stage acquisition or other follow-up work. Completeness is derived by
    ``ModelInputStepCoverage`` and cannot be supplied as an assertion.
    """
    return ModelInputStepCoverage(
        required_step_scopes=required_step_scopes,
        supplied_step_scopes=supplied_step_scopes,
    )
