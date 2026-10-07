"""Test plugin that removes IR profile-policy checks while retaining DTO parsing."""

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

from polisyos.ir.artifacts.contracts import CanonInfo
import polisyos.ir.artifacts.io as ir_io


def _shape_only_profile(value: Any) -> CanonInfo:
    """Preserve model-shape parsing while removing supported-profile enforcement."""
    if isinstance(value, Mapping):
        payload = dict(value)
    elif hasattr(value, "model_dump"):
        payload = value.model_dump(mode="python")
    elif is_dataclass(value) and not isinstance(value, type):
        payload = asdict(value)
    else:
        payload = dict(vars(value))
    return CanonInfo.model_validate(payload)


def pytest_configure(config: Any) -> None:
    del config
    ir_io._validated_ir_canon_info = _shape_only_profile
