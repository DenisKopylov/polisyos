from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any, Mapping


def _as_model_dump(value: Any) -> Any | None:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="python", by_alias=True, exclude_none=False)
    return None


def _try_tolist(value: Any) -> Any | None:
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:
            return None
    return None


def _try_item(value: Any) -> Any | None:
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            return None
    return None


def to_python_data(value: Any, *, sort_keys: bool = False) -> Any:
    """Convert nested values to JSON/canonical-friendly python data."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return to_python_data(value.value, sort_keys=sort_keys)

    dumped = _as_model_dump(value)
    if dumped is not None:
        return to_python_data(dumped, sort_keys=sort_keys)

    if dataclasses.is_dataclass(value):
        return to_python_data(dataclasses.asdict(value), sort_keys=sort_keys)

    if isinstance(value, Mapping):
        items = value.items()
        if sort_keys:
            items = sorted(items, key=lambda pair: str(pair[0]))
        return {str(key): to_python_data(item, sort_keys=sort_keys) for key, item in items}

    if isinstance(value, (list, tuple)):
        return [to_python_data(item, sort_keys=sort_keys) for item in value]

    if isinstance(value, (set, frozenset)):
        return [
            to_python_data(item, sort_keys=sort_keys)
            for item in sorted(value, key=lambda item: repr(item))
        ]

    listed = _try_tolist(value)
    if listed is not None:
        return to_python_data(listed, sort_keys=sort_keys)

    scalar = _try_item(value)
    if scalar is not None:
        return to_python_data(scalar, sort_keys=sort_keys)

    return value


def strip_none(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def stable_json_dumps(value: Any, *, ensure_ascii: bool = True, sort_keys: bool = True) -> str:
    payload = to_python_data(value, sort_keys=sort_keys)
    return json.dumps(
        payload,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        separators=(",", ":"),
    )


__all__ = [
    "strip_none",
    "stable_json_dumps",
    "to_python_data",
]
