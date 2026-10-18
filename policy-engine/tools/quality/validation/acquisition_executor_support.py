"""Shared acquisition execution values and byte/path helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from .acquisition_response_receipts import (
    AcquisitionSelectionError,
)

DEFAULT_TARGET_HARNESS_RECEIPT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_worldbank_government_balance_harness.json"
)


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(str(item) for item in value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return (value,)
        if isinstance(decoded, Sequence) and not isinstance(
            decoded,
            (str, bytes, bytearray),
        ):
            return tuple(str(item) for item in decoded)
        return (str(decoded),)
    return ()


def bytes_sha256(payload: bytes) -> str:
    """Return the raw file identity used by provision receipts."""

    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _json_object(value: object) -> dict[str, object]:
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AcquisitionSelectionError("target_harness_json_invalid") from exc
    if not isinstance(parsed, Mapping):
        raise AcquisitionSelectionError("target_harness_json_mapping_required")
    return {str(key): item for key, item in parsed.items()}


def _read_mapping(path: Path, *, code: str) -> dict[str, object]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise AcquisitionSelectionError(f"{code}_unreadable", type(exc).__name__) from exc
    if not isinstance(value, Mapping):
        raise AcquisitionSelectionError(f"{code}_mapping_required")
    return {str(key): item for key, item in value.items()}
