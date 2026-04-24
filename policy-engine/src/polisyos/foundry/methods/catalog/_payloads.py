"""Public catalog payloads module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def filter_model_mapping(model_cls: type, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Filter model mapping helper."""
    allowed = set(getattr(model_cls, "model_fields", {}))
    return {key: value for key, value in payload.items() if key in allowed}


def extract_model_payload(
    state: Any,
    *,
    model_cls: type,
    nested_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Extract model payload helper."""
    if isinstance(state, model_cls):
        return state.model_dump(mode="python")

    if not isinstance(state, Mapping):
        raise TypeError(f"state must be {model_cls.__name__} or mapping")

    base_payload: dict[str, Any] = {}
    for nested_key in nested_keys:
        nested = state.get(nested_key)
        if isinstance(nested, model_cls):
            base_payload = nested.model_dump(mode="python")
            break
        if isinstance(nested, Mapping):
            base_payload = filter_model_mapping(model_cls, nested)
            break

    direct_fields = filter_model_mapping(model_cls, state)
    if direct_fields:
        base_payload.update(direct_fields)

    return base_payload


__all__ = ["extract_model_payload", "filter_model_mapping"]
