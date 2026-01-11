from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

ID_PATTERN = r"^[a-z][a-z0-9_.-]*$"
SLOT_ID_PATTERN = r"^[a-z][a-z0-9_.]*$"
ARTIFACT_ID_PATTERN = r"^sha256:[0-9a-f]{64}$"


class KernelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("float forbidden; use string or int")
    return value


def reject_floats_deep(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("float forbidden; use string or int")
    if isinstance(value, list):
        for item in value:
            reject_floats_deep(item)
        return value
    if isinstance(value, dict):
        for item in value.values():
            reject_floats_deep(item)
        return value
    return value
