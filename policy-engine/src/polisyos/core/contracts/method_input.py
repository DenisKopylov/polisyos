"""Typed source bindings for ABI-local method inputs."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from polisyos.ir.kernel.base import SLOT_ID_PATTERN


def _validate_trimmed_name(value: str) -> str:
    """Require a bounded, nonempty name without surrounding whitespace."""
    if not value or value != value.strip():
        raise ValueError("method_input_source_identifier_invalid")
    return value


def validate_method_input_port_name(value: str) -> str:
    """Validate one ABI-local input port name."""
    if len(value) > 256:
        raise ValueError("method_input_source_identifier_invalid")
    return _validate_trimmed_name(value)


class RegistrySlotInputPortSource(BaseModel):
    """Bind one ABI-local method input to a selected global registry slot."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_kind: Literal["registry_slot"]
    slot_id: StrictStr = Field(min_length=1, max_length=256, pattern=SLOT_ID_PATTERN)


class MethodOutputInputPortSource(BaseModel):
    """Describe a future binding from one selected method output occurrence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_kind: Literal["method_output"]
    producer_node_id: StrictStr = Field(min_length=1, max_length=128)
    output_slot_id: StrictStr = Field(min_length=1, max_length=256)

    @field_validator("producer_node_id", "output_slot_id")
    @classmethod
    def _source_names_are_trimmed(cls, value: str) -> str:
        return _validate_trimmed_name(value)


type MethodInputPortSource = Annotated[
    RegistrySlotInputPortSource | MethodOutputInputPortSource,
    Field(discriminator="source_kind"),
]
