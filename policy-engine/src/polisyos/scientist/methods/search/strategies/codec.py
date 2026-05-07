"""Parameter codecs bridging policy dictionaries and vectorized search params."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class ParameterCodec(Protocol):
    """Encode/decode between policy candidates and strategy parameter dictionaries."""

    def encode(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """Extract searchable parameters from policy candidate."""

    def decode(
        self,
        params: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Materialize full policy candidate from strategy parameter dictionary."""


def _segment_index(segment: str) -> int | None:
    if not segment:
        return None
    if segment.isdigit():
        return int(segment)
    return None


def _get_path(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for segment in dotted.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
            continue
        if isinstance(current, list):
            index = _segment_index(segment)
            if index is None or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _set_path(payload: dict[str, Any], dotted: str, value: Any) -> None:
    current: Any = payload
    segments = dotted.split(".")
    for idx, segment in enumerate(segments[:-1]):
        next_segment = segments[idx + 1]
        next_is_index = _segment_index(next_segment) is not None

        if isinstance(current, dict):
            next_value = current.get(segment)
            if next_is_index:
                if not isinstance(next_value, list):
                    next_value = []
                    current[segment] = next_value
            else:
                if not isinstance(next_value, dict):
                    next_value = {}
                    current[segment] = next_value
            current = next_value
            continue

        if isinstance(current, list):
            current_index = _segment_index(segment)
            if current_index is None:
                return
            while len(current) <= current_index:
                current.append([] if next_is_index else {})
            next_value = current[current_index]
            if next_is_index:
                if not isinstance(next_value, list):
                    next_value = []
                    current[current_index] = next_value
            else:
                if not isinstance(next_value, dict):
                    next_value = {}
                    current[current_index] = next_value
            current = next_value
            continue

        return

    last = segments[-1]
    if isinstance(current, dict):
        current[last] = value
        return
    if isinstance(current, list):
        index = _segment_index(last)
        if index is None:
            return
        while len(current) <= index:
            current.append(None)
        current[index] = value


@dataclass(slots=True)
class ScalarParameterCodec:
    """
    Path-based codec for scalar strategy parameters.

    - If `parameter_paths` is empty, encode/decode uses top-level keys unchanged.
    - If `parameter_paths` provided: maps strategy-param-name -> dotted path in candidate dict.
    """

    parameter_paths: dict[str, str] = field(default_factory=dict)
    default_semantic: dict[str, Any] = field(default_factory=lambda: {"interventions": []})

    def encode(self, candidate: dict[str, Any]) -> dict[str, Any]:
        if not self.parameter_paths:
            return {key: value for key, value in candidate.items() if key != "semantic"}

        params: dict[str, Any] = {}
        for param_name, path in self.parameter_paths.items():
            params[param_name] = _get_path(candidate, path)
        return params

    def decode(
        self,
        params: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output: dict[str, Any] = {}
        if template:
            output.update(template)
            if "semantic" in template and isinstance(template["semantic"], dict):
                output["semantic"] = dict(template["semantic"])
        if "semantic" not in output:
            output["semantic"] = dict(self.default_semantic)

        if not self.parameter_paths:
            for key, value in params.items():
                output[key] = value
            return output

        for param_name, value in params.items():
            path = self.parameter_paths.get(param_name, param_name)
            _set_path(output, path, value)
        return output
